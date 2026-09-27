/*
Copyright (C) 2026 Sergei Vostrikov

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/
/** @file acquisition_thread.c
 * @brief Acquisition command serialization and owner-task lifecycle. */
#include "acquisition_internal.h"

#include <stdlib.h>
#include <string.h>
#include "board.h"
#include "wulpus_pro_state.h"
#include "wulpus_pro_status.h"
#include "wulpus_pro_firmware_info.h"

TaskHandle_t acquisition_task_handle;
portMUX_TYPE acquisition_lock = portMUX_INITIALIZER_UNLOCKED;
acq_state_t acquisition_state = ACQ_STATE_RESET;
bool acquisition_configured;
bool acquisition_reset_asserted = true;
wulpus_pro_session_ref_t acquisition_owner;

/* The command queue is owned and consumed entirely by this module. */
static QueueHandle_t acquisition_command_queue;

/** @brief Reports whether a request was cancelled or belongs to a stale session. */
bool acquisition_request_cancelled(acq_request_t* request)
{
    if (request == NULL)
        return false;
    portENTER_CRITICAL(&acquisition_lock);
    bool value = request->cancelled;
    portEXIT_CRITICAL(&acquisition_lock);
    value |= !wulpus_pro_session_is_current(request->session);
    if (request->type == ACQ_CMD_CONFIGURE || request->type == ACQ_CMD_ENABLE)
        value |= !link_is_connected(request->session.link);
    return value;
}

/** @brief Drops one request reference and destroys the request at zero references. */
static void release_request(acq_request_t* request)
{
    portENTER_CRITICAL(&acquisition_lock);
    bool destroy = --request->references == 0;
    portEXIT_CRITICAL(&acquisition_lock);
    if (destroy) {
        vSemaphoreDelete(request->done);
        free(request);
    }
}

/** @brief Converts an acquisition failure into persistent status and error counters. */
void acquisition_report_error(esp_err_t result)
{
    wulpus_pro_status_set_error(result == ESP_ERR_TIMEOUT ? WULPUS_PRO_ERROR_SPI_TIMEOUT
                                                          : WULPUS_PRO_ERROR_SPI_FAILURE);
    wulpus_pro_status_increment_spi_error();
}

/** @brief Applies one serialized command to the acquisition state machine. */
static esp_err_t acquisition_execute(acq_request_t* request)
{
    if (acquisition_request_cancelled(request))
        return ESP_ERR_INVALID_STATE;
    esp_err_t result = ESP_OK;
    switch (request->type) {
    case ACQ_CMD_BOOT:
    case ACQ_CMD_RESET:
        acquisition_quiesce();
        wulpus_pro_firmware_info_clear_msp();
        result = board_msp_reset(true);
        acquisition_state = ACQ_STATE_RESET;
        acquisition_configured = false;
        if (result != ESP_OK)
            return result;
        acquisition_reset_asserted = true;
        vTaskDelay(pdMS_TO_TICKS(10));
        ulTaskNotifyTake(pdTRUE, 0);
        acquisition_reset_handshake();
        if (request->type == ACQ_CMD_BOOT) {
            result = board_msp_reset(false);
            if (result == ESP_OK) {
                acquisition_reset_asserted = false;
                acquisition_state = ACQ_STATE_WAIT_CONFIG;
            }
        }
        return result;
    case ACQ_CMD_CONFIGURE:
        if (request->config[0] == 0xFB) {
            acquisition_quiesce();
            return acquisition_restart_msp(request);
        }
        if (acquisition_state != ACQ_STATE_WAIT_CONFIG)
            return ESP_ERR_INVALID_STATE;
        acquisition_state = ACQ_STATE_CONFIGURING;
        result = acquisition_wait_ready(request);
        if (result == ESP_OK) {
            uint8_t response[CONFIG_WP_DATA_RX_LENGTH] __attribute__((aligned(4)));
            acquisition_consume_assertion();
            result = board_spi_transceive(request->config, response, sizeof(response));
            if (result == ESP_OK)
                wulpus_pro_firmware_info_set_msp(response, sizeof(response));
            if (result == ESP_OK)
                result = acquisition_wait_transfer_low(request);
        }
        if (result == ESP_OK && !acquisition_request_cancelled(request)) {
            acquisition_owner = request->session;
            acquisition_configured = true;
            acquisition_state = ACQ_STATE_CONFIGURED;
        } else {
            acquisition_quiesce();
            if (result == ESP_OK)
                result = ESP_ERR_INVALID_STATE;
        }
        return result;
    case ACQ_CMD_ENABLE:
        if (!acquisition_configured ||
            acquisition_owner.generation != request->session.generation ||
            (acquisition_state != ACQ_STATE_CONFIGURED &&
             acquisition_state != ACQ_STATE_QUIESCENT && acquisition_state != ACQ_STATE_ACQUIRING))
            return ESP_ERR_INVALID_STATE;
        acquisition_state = ACQ_STATE_ACQUIRING;
        wulpus_pro_state_set_acquiring(true);
        acquisition_publish_pending();
        return ESP_OK;
    case ACQ_CMD_DISABLE:
        wulpus_pro_state_set_acquiring(false);
        if (acquisition_configured && acquisition_state == ACQ_STATE_ACQUIRING)
            acquisition_state = ACQ_STATE_CONFIGURED;
        return ESP_OK;
    case ACQ_CMD_QUIESCE:
        acquisition_quiesce();
        return ESP_OK;
    case ACQ_CMD_RESTART:
        return acquisition_restart_msp(request);
    }
    return ESP_ERR_INVALID_ARG;
}

/** @brief Drains queued commands and receives at most one pending data frame. */
bool acquisition_process_work(void)
{
    bool work_to_do = false;
    acq_request_t* request;
    while (xQueueReceive(acquisition_command_queue, &request, 0) == pdTRUE) {
        request->result = acquisition_execute(request);
        if (request->result != ESP_OK && request->result != ESP_ERR_INVALID_STATE)
            acquisition_report_error(request->result);
        xSemaphoreGive(request->done);
        release_request(request);
    }
    if ((acquisition_state == ACQ_STATE_ACQUIRING || acquisition_state == ACQ_STATE_CONFIGURED) &&
        acquisition_pending_frame == NULL && acquisition_data_ready_pending()) {
        acquisition_receive_frame();
        work_to_do = true;
    }
    return work_to_do;
}

/** @brief Runs the acquisition work loop and sleeps until new work arrives. */
static void acquisition_task(void* argument)
{
    (void)argument;

    for (;;) {
        if (!acquisition_process_work())
            ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
    }
}

/** @brief Creates the command queue and owner task, then installs the DATA_READY ISR. */
esp_err_t acquisition_thread_start(void)
{
    acquisition_command_queue = xQueueCreate(4, sizeof(acq_request_t*));
    if (acquisition_command_queue == NULL)
        return ESP_ERR_NO_MEM;
    if (xTaskCreate(acquisition_task, "acquisition", CONFIG_WP_ACQUISITION_STACK_SIZE, NULL,
                    CONFIG_WP_ACQUISITION_PRIORITY, &acquisition_task_handle) != pdPASS) {
        vQueueDelete(acquisition_command_queue);
        acquisition_command_queue = NULL;
        return ESP_ERR_NO_MEM;
    }
    return board_data_ready_set_isr(acquisition_data_ready_isr, NULL);
}

/** @brief Queues a synchronous command and waits for completion within the timeout. */
esp_err_t acquisition_thread_command(acq_command_type_t type, wulpus_pro_session_ref_t session,
                                     const void* config, size_t length, TickType_t timeout)
{
    if (acquisition_command_queue == NULL || length > CONFIG_WP_DATA_RX_LENGTH ||
        (length && config == NULL) ||
        (type == ACQ_CMD_CONFIGURE && (length == 0 || (((const uint8_t*)config)[0] != 0xFA &&
                                                       ((const uint8_t*)config)[0] != 0xFB))))
        return ESP_ERR_INVALID_ARG;
    acq_request_t* request = calloc(1, sizeof(*request));
    if (request == NULL)
        return ESP_ERR_NO_MEM;
    request->done = xSemaphoreCreateBinary();
    if (request->done == NULL) {
        free(request);
        return ESP_ERR_NO_MEM;
    }
    request->type = type;
    request->session = session;
    request->references = 2;
    if (length)
        memcpy(request->config, config, length);
    TickType_t started = xTaskGetTickCount();
    if (xQueueSend(acquisition_command_queue, &request, timeout) != pdTRUE) {
        release_request(request);
        release_request(request);
        return ESP_ERR_TIMEOUT;
    }
    xTaskNotifyGive(acquisition_task_handle);
    TickType_t elapsed = xTaskGetTickCount() - started;
    TickType_t remaining = elapsed < timeout ? timeout - elapsed : 0;
    esp_err_t result;
    if (xSemaphoreTake(request->done, remaining) == pdTRUE) {
        result = request->result;
    } else {
        portENTER_CRITICAL(&acquisition_lock);
        request->cancelled = true;
        portEXIT_CRITICAL(&acquisition_lock);
        result = ESP_ERR_TIMEOUT;
    }
    release_request(request);
    return result;
}
