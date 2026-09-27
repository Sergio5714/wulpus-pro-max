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

/**
 * @file packet_tx_thread.c
 * @brief Serialized control responses and acquisition frame transmission.
 */

#include "thread_internal.h"

#include <string.h>
#include "freertos/queue.h"
#include "freertos/task.h"
#include "wulpus_pro_frame_pool.h"
#include "wulpus_pro_firmware_info.h"
#include "wulpus_pro_protocol.h"
#include "wulpus_pro_state.h"
#include "wulpus_pro_status.h"

#define CONTROL_PAYLOAD_MAX WULPUS_PRO_FIRMWARE_INFO_SIZE
#define CONTROL_DEPTH 8

typedef struct {
    link_t* link;
    uint32_t generation;
    bool require_current_session;
    uint8_t command;
    uint16_t length;
    uint8_t payload[CONTROL_PAYLOAD_MAX];
    TaskHandle_t requester;
} control_tx_t;

static TaskHandle_t task_handle;
static QueueHandle_t control_queue;

/**
 * @brief Write a protocol header followed by its optional payload to a link.
 */
static esp_err_t send_packet(link_t* link, uint8_t command, const void* payload, uint16_t length)
{
    wulpus_pro_header_t header;
    wulpus_pro_protocol_make_header(&header, command, length);
    esp_err_t result = link_write_all(link, &header, sizeof(header));
    if (result == ESP_OK && length > 0)
        result = link_write_all(link, payload, length);
    return result;
}

/**
 * @brief Notify the requesting task of a control transmission's result.
 */
static void complete_request(const control_tx_t* request, esp_err_t result)
{
    xTaskNotify(request->requester, (uint32_t)result, eSetValueWithOverwrite);
}

/**
 * @brief Process queued control responses and transmit or discard ready acquisition frames.
 */
static void packet_tx_task(void* argument)
{
    (void)argument;
    while (true) {
        ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(10));

        control_tx_t control;
        while (xQueueReceive(control_queue, &control, 0) == pdTRUE) {
            esp_err_t result = ESP_ERR_INVALID_STATE;
            if (!control.require_current_session ||
                wulpus_pro_session_is_current(
                    (wulpus_pro_session_ref_t){.link = control.link,
                                               .generation = control.generation,
                                               .kind = control.link->kind})) {
                result =
                    send_packet(control.link, control.command, control.payload, control.length);
            }
            if (result != ESP_OK) {
                wulpus_pro_status_set_error(WULPUS_PRO_ERROR_LINK_TIMEOUT);
                wulpus_pro_status_increment_link_error();
            }
            complete_request(&control, result);
        }

        wulpus_pro_frame_slot_t* slot = wulpus_pro_frame_pool_acquire_for_tx(0);
        if (slot == NULL)
            continue;
        wulpus_pro_session_ref_t session = wulpus_pro_session_current();
        if (session.link == NULL || session.generation != slot->session_generation ||
            !wulpus_pro_state_is_acquiring() || !link_is_connected(session.link)) {
            wulpus_pro_status_increment_discarded();
            wulpus_pro_frame_pool_release(slot);
            continue;
        }
        esp_err_t result =
            send_packet(session.link, WULPUS_PRO_GET_DATA, slot->payload, slot->length);
        if (result == ESP_OK) {
            wulpus_pro_status_increment_transmitted();
        } else {
            wulpus_pro_status_set_error(WULPUS_PRO_ERROR_LINK_TIMEOUT);
            wulpus_pro_status_increment_link_error();
            acquisition_thread_command(ACQ_CMD_QUIESCE, session, NULL, 0, pdMS_TO_TICKS(8000));
        }
        wulpus_pro_frame_pool_release(slot);
        // Schedule another pass. Notifications can coalesce while USB/TCP is
        // busy, so one wakeup must not strand additional READY slots.
        xTaskNotifyGive(task_handle);
    }
}

esp_err_t packet_tx_thread_start(void)
{
    control_queue = xQueueCreate(CONTROL_DEPTH, sizeof(control_tx_t));
    if (control_queue == NULL)
        return ESP_ERR_NO_MEM;
    return xTaskCreate(packet_tx_task, "packet_tx", CONFIG_WP_PACKET_TX_STACK_SIZE, NULL,
                       CONFIG_WP_PACKET_TX_PRIORITY, &task_handle) == pdPASS
               ? ESP_OK
               : ESP_ERR_NO_MEM;
}

/**
 * @brief Copy a control payload into the queue and wait for the transmitting task's result.
 */
static esp_err_t submit(link_t* link, uint32_t generation, bool require_current, uint8_t command,
                        const void* payload, uint16_t length, TickType_t timeout)
{
    if (link == NULL || length > CONTROL_PAYLOAD_MAX || (length > 0 && payload == NULL))
        return ESP_ERR_INVALID_ARG;
    control_tx_t request = {
        .link = link,
        .generation = generation,
        .require_current_session = require_current,
        .command = command,
        .length = length,
        .requester = xTaskGetCurrentTaskHandle(),
    };
    if (length)
        memcpy(request.payload, payload, length);
    uint32_t stale;
    xTaskNotifyWait(0, UINT32_MAX, &stale, 0);
    if (xQueueSend(control_queue, &request, timeout) != pdTRUE)
        return ESP_ERR_TIMEOUT;
    xTaskNotifyGive(task_handle);
    uint32_t result;
    if (xTaskNotifyWait(0, UINT32_MAX, &result, timeout) != pdTRUE)
        return ESP_ERR_TIMEOUT;
    return (esp_err_t)result;
}

esp_err_t packet_tx_submit_control(wulpus_pro_session_ref_t session, uint8_t command,
                                   const void* payload, uint16_t length, TickType_t timeout)
{
    return submit(session.link, session.generation, true, command, payload, length, timeout);
}

esp_err_t packet_tx_submit_to_link(link_t* link, uint8_t command, const void* payload,
                                   uint16_t length, TickType_t timeout)
{
    return submit(link, 0, false, command, payload, length, timeout);
}

void packet_tx_notify_frame_ready(void)
{
    if (task_handle)
        xTaskNotifyGive(task_handle);
}
void packet_tx_discard_session(wulpus_pro_session_ref_t session)
{
    (void)session;
    wulpus_pro_frame_pool_discard_ready();
}
