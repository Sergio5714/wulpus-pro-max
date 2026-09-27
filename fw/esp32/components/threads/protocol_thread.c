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
 * @file protocol_thread.c
 * @brief Session command processing and MSP430 control.
 */

#include "thread_internal.h"

#include <string.h>
#include "esp_system.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "provisioner.h"
#include "wulpus_pro_commands.h"
#include "wulpus_pro_protocol.h"
#include "wulpus_pro_state.h"
#include "wulpus_pro_status.h"
#include "wulpus_pro_firmware_info.h"
#include "wulpus_pro_persistent_config.h"
#include "msp430_programmer.h"
#include "msp430_image.h"

#define COMMAND_TIMEOUT pdMS_TO_TICKS(5000)
#define ACQUISITION_TIMEOUT pdMS_TO_TICKS(8000)

static QueueHandle_t session_queue;

/**
 * @brief Submit a session control response using the configured command timeout.
 */
static esp_err_t send_control(wulpus_pro_session_ref_t session, uint8_t command,
                              const void* payload, uint16_t length)
{
    return packet_tx_submit_control(session, command, payload, length, COMMAND_TIMEOUT);
}

/**
 * @brief Send an error response containing the rejected command and error code.
 */
static esp_err_t send_command_error(wulpus_pro_session_ref_t session, uint8_t command,
                                    esp_err_t error)
{
    wulpus_pro_error_response_t response = {.command = command, .error = error};
    return send_control(session, WULPUS_PRO_ERROR, &response, sizeof(response));
}

static esp_err_t acq_command(wulpus_pro_session_ref_t session, acq_command_type_t type)
{
    return acquisition_thread_command(type, session, NULL, 0, ACQUISITION_TIMEOUT);
}

static esp_err_t stop_acquisition(wulpus_pro_session_ref_t session)
{
    return acq_command(session, ACQ_CMD_QUIESCE);
}

static esp_err_t shutdown_msp(wulpus_pro_session_ref_t session)
{
    esp_err_t result = stop_acquisition(session);
    if (result != ESP_OK)
        return result;
    result = acq_command(session, ACQ_CMD_RESTART);
    /* Reset is serialized by the acquisition owner even on handshake failure. */
    esp_err_t reset_result = acq_command(session, ACQ_CMD_RESET);
    return result == ESP_OK ? reset_result : result;
}

/**
 * @brief Read a header's payload after checking the destination capacity.
 */
static esp_err_t read_payload(link_t* link, const wulpus_pro_header_t* header, uint8_t* payload,
                              size_t capacity)
{
    if (header->data_length > capacity)
        return ESP_ERR_INVALID_SIZE;
    return header->data_length ? link_read_exact(link, payload, header->data_length) : ESP_OK;
}

/**
 * @brief Process commands for the active link, then stop acquisition and release the session.
 */
static void run_session(wulpus_pro_session_ref_t session)
{
    provisioner_twt_suspend(1);
    esp_err_t boot_result = acq_command(session, ACQ_CMD_BOOT);
    uint8_t payload[CONFIG_WP_DATA_RX_LENGTH];
    bool running = boot_result == ESP_OK;

    while (running && wulpus_pro_session_is_current(session) && link_is_connected(session.link)) {
        wulpus_pro_header_t header;
        if (link_read_exact(session.link, &header, sizeof(header)) != ESP_OK ||
            !wulpus_pro_protocol_header_valid(&header) || header.data_length > sizeof(payload)) {
            wulpus_pro_status_set_error(WULPUS_PRO_ERROR_PROTOCOL);
            break;
        }

        bool acknowledge_after_action =
            header.command == WULPUS_PRO_SET_ACQ_CONFIG || header.command == WULPUS_PRO_START_RX ||
            header.command == WULPUS_PRO_RESET || header.command == WULPUS_PRO_STOP_RX ||
            header.command == WULPUS_PRO_CLEAR_STATUS || header.command == WULPUS_PRO_RESET_MSP ||
            header.command == WULPUS_PRO_SET_DEVICE_CONFIG ||
            header.command == WULPUS_PRO_SET_WIFI_CREDENTIALS ||
            header.command == WULPUS_PRO_CLEAR_WIFI_CREDENTIALS ||
            header.command == WULPUS_PRO_MSP_UPDATE_BEGIN ||
            header.command == WULPUS_PRO_MSP_UPDATE_DATA ||
            header.command == WULPUS_PRO_MSP_UPDATE_COMMIT ||
            header.command == WULPUS_PRO_MSP_UPDATE_ABORT ||
            header.command == WULPUS_PRO_MSP_UPDATE_GET_DIAGNOSTICS ||
            header.command == WULPUS_PRO_CLOSE;
        if (!acknowledge_after_action && send_control(session, header.command, NULL, 0) != ESP_OK)
            break;
        if (read_payload(session.link, &header, payload, sizeof(payload)) != ESP_OK)
            break;

        switch ((wulpus_pro_command_t)header.command) {
        case WULPUS_PRO_SET_ACQ_CONFIG: {
            if (wulpus_pro_state_is_updating()) {
                if (send_control(session, WULPUS_PRO_BUSY, NULL, 0) != ESP_OK)
                    running = false;
                break;
            }
            esp_err_t result = acquisition_thread_command(ACQ_CMD_CONFIGURE, session, payload,
                                                          header.data_length, ACQUISITION_TIMEOUT);
            if (result == ESP_OK)
                result = send_control(session, header.command, NULL, 0);
            else
                result = send_command_error(session, header.command, result);
            if (result != ESP_OK)
                running = false;
            break;
        }
        case WULPUS_PRO_GET_DEVICE_CONFIG: {
            wulpus_pro_device_config_t config;
            esp_err_t result = wulpus_pro_device_config_load(&config);
            if (result != ESP_OK ||
                send_control(session, WULPUS_PRO_DEVICE_CONFIG, &config, sizeof(config)) != ESP_OK)
                running = false;
            break;
        }
        case WULPUS_PRO_SET_DEVICE_CONFIG: {
            esp_err_t result = ESP_ERR_INVALID_SIZE;
            if (header.data_length == sizeof(wulpus_pro_device_config_t)) {
                wulpus_pro_device_config_t config;
                memcpy(&config, payload, sizeof(config));
                result = wulpus_pro_device_config_save(&config);
            }
            if (result == ESP_OK)
                result = send_control(session, header.command, NULL, 0);
            else
                result = send_command_error(session, header.command, result);
            if (result != ESP_OK)
                running = false;
            break;
        }
        case WULPUS_PRO_GET_WIFI_STATUS: {
            wulpus_pro_wifi_status_t status;
            esp_err_t result = provisioner_get_status(&status);
            if (result != ESP_OK ||
                send_control(session, WULPUS_PRO_WIFI_STATUS, &status, sizeof(status)) != ESP_OK)
                running = false;
            break;
        }
        case WULPUS_PRO_SET_WIFI_CREDENTIALS: {
            esp_err_t result = ESP_ERR_INVALID_SIZE;
            if (header.data_length >= sizeof(wulpus_pro_wifi_credentials_header_t)) {
                wulpus_pro_wifi_credentials_header_t request;
                memcpy(&request, payload, sizeof(request));
                size_t expected = sizeof(request) + request.ssid_length + request.password_length;
                if (request.version == 1 && request.reserved == 0 &&
                    expected == header.data_length) {
                    const uint8_t* ssid = payload + sizeof(request);
                    const uint8_t* password = ssid + request.ssid_length;
                    result = provisioner_set_credentials(ssid, request.ssid_length, password,
                                                         request.password_length);
                } else
                    result = ESP_ERR_INVALID_ARG;
            }
            if (result == ESP_OK)
                result = send_control(session, header.command, NULL, 0);
            else
                result = send_command_error(session, header.command, result);
            if (result != ESP_OK)
                running = false;
            break;
        }
        case WULPUS_PRO_CLEAR_WIFI_CREDENTIALS: {
            esp_err_t result =
                header.data_length == 0 ? provisioner_clear_credentials() : ESP_ERR_INVALID_SIZE;
            if (result == ESP_OK)
                result = send_control(session, header.command, NULL, 0);
            else
                result = send_command_error(session, header.command, result);
            if (result != ESP_OK)
                running = false;
            break;
        }
        case WULPUS_PRO_PING:
            if (send_control(session, WULPUS_PRO_PONG, "pong", 4) != ESP_OK)
                running = false;
            break;
        case WULPUS_PRO_START_RX: {
            if (wulpus_pro_state_is_updating()) {
                if (send_control(session, WULPUS_PRO_BUSY, NULL, 0) != ESP_OK)
                    running = false;
                break;
            }
            esp_err_t result = acq_command(session, ACQ_CMD_ENABLE);
            result = result == ESP_OK ? send_control(session, header.command, NULL, 0)
                                      : send_command_error(session, header.command, result);
            if (result != ESP_OK)
                running = false;
            break;
        }
        case WULPUS_PRO_STOP_RX: {
            esp_err_t result = stop_acquisition(session);
            result = result == ESP_OK ? send_control(session, header.command, NULL, 0)
                                      : send_command_error(session, header.command, result);
            if (result != ESP_OK)
                running = false;
            break;
        }
        case WULPUS_PRO_GET_STATUS: {
            wulpus_pro_status_snapshot_t snapshot;
            wulpus_pro_status_snapshot(&snapshot);
            if (send_control(session, WULPUS_PRO_STATUS, &snapshot, sizeof(snapshot)) != ESP_OK)
                running = false;
            break;
        }
        case WULPUS_PRO_GET_FIRMWARE_INFO: {
            wulpus_pro_firmware_info_t info;
            wulpus_pro_firmware_info_get(&info);
            if (send_control(session, WULPUS_PRO_FIRMWARE_INFO, &info, sizeof(info)) != ESP_OK)
                running = false;
            break;
        }
        case WULPUS_PRO_CLEAR_STATUS: {
            if (header.data_length != 0 &&
                header.data_length != sizeof(wulpus_pro_clear_status_t)) {
                wulpus_pro_status_set_error(WULPUS_PRO_ERROR_PROTOCOL);
                break;
            }
            uint32_t mask = UINT32_MAX;
            bool clear_counters = false;
            if (header.data_length) {
                wulpus_pro_clear_status_t request;
                memcpy(&request, payload, sizeof(request));
                mask = request.error_mask;
                clear_counters = request.clear_counters != 0;
            }
            wulpus_pro_status_clear(mask, clear_counters);
            if (send_control(session, WULPUS_PRO_CLEAR_STATUS, NULL, 0) != ESP_OK)
                running = false;
            break;
        }
        case WULPUS_PRO_CLOSE: {
            esp_err_t result = shutdown_msp(session);
            result = result == ESP_OK ? send_control(session, header.command, NULL, 0)
                                      : send_command_error(session, header.command, result);
            if (result != ESP_OK) {
                wulpus_pro_status_set_error(WULPUS_PRO_ERROR_LINK_TIMEOUT);
            }
            running = false;
            break;
        }
        case WULPUS_PRO_RESET:
            if (wulpus_pro_state_is_updating()) {
                if (send_control(session, WULPUS_PRO_BUSY, NULL, 0) != ESP_OK)
                    running = false;
                break;
            }
            {
                esp_err_t result = shutdown_msp(session);
                if (result == ESP_OK) {
                    send_control(session, WULPUS_PRO_RESET, NULL, 0);
                    esp_restart();
                } else if (send_command_error(session, header.command, result) != ESP_OK) {
                    running = false;
                }
            }
            break;
        case WULPUS_PRO_RESET_MSP:
            if (wulpus_pro_state_is_acquiring() || wulpus_pro_state_is_updating()) {
                if (send_control(session, WULPUS_PRO_BUSY, NULL, 0) != ESP_OK)
                    running = false;
                break;
            }
            if (acq_command(session, ACQ_CMD_BOOT) != ESP_OK) {
                wulpus_pro_status_set_error(WULPUS_PRO_ERROR_SPI_FAILURE);
                running = false;
                break;
            }
            if (send_control(session, WULPUS_PRO_RESET_MSP, NULL, 0) != ESP_OK)
                running = false;
            break;
        case WULPUS_PRO_MSP_UPDATE_BEGIN: {
            esp_err_t result = ESP_ERR_INVALID_SIZE;
            if (header.data_length == sizeof(wulpus_pro_msp_update_begin_t)) {
                wulpus_pro_msp_update_begin_t request;
                memcpy(&request, payload, sizeof(request));
                if (request.version == 1 && request.reserved == 0)
                    result = msp430_programmer_begin(request.image_size, request.image_crc32);
                else
                    result = ESP_ERR_INVALID_ARG;
            }
            if (result == ESP_OK)
                result = send_control(session, header.command, NULL, 0);
            else
                result = send_command_error(session, header.command, result);
            if (result != ESP_OK)
                running = false;
            break;
        }
        case WULPUS_PRO_MSP_UPDATE_DATA: {
            esp_err_t result = ESP_ERR_INVALID_SIZE;
            if (header.data_length >= sizeof(wulpus_pro_msp_update_data_t)) {
                wulpus_pro_msp_update_data_t request;
                memcpy(&request, payload, sizeof(request));
                const uint8_t* data = payload + sizeof(request);
                if (request.data_length == header.data_length - sizeof(request) &&
                    msp430_crc32(0, data, request.data_length) == request.data_crc32) {
                    result = msp430_programmer_write(request.offset, data, request.data_length);
                    if (result == ESP_OK) {
                        wulpus_pro_msp_update_data_response_t response = {
                            .next_offset = request.offset + request.data_length,
                            .accepted_sequence = request.sequence,
                        };
                        result = send_control(session, header.command, &response, sizeof(response));
                    }
                } else
                    result = ESP_ERR_INVALID_CRC;
            }
            if (result != ESP_OK && send_command_error(session, header.command, result) != ESP_OK)
                running = false;
            break;
        }
        case WULPUS_PRO_MSP_UPDATE_COMMIT: {
            esp_err_t result =
                header.data_length ? ESP_ERR_INVALID_SIZE : msp430_programmer_commit();
            if (result == ESP_OK)
                result = send_control(session, header.command, NULL, 0);
            else
                result = send_command_error(session, header.command, result);
            if (result != ESP_OK)
                running = false;
            break;
        }
        case WULPUS_PRO_MSP_UPDATE_ABORT: {
            esp_err_t result =
                header.data_length ? ESP_ERR_INVALID_SIZE : msp430_programmer_abort();
            if (result == ESP_OK)
                result = send_control(session, header.command, NULL, 0);
            else
                result = send_command_error(session, header.command, result);
            if (result != ESP_OK)
                running = false;
            break;
        }
        case WULPUS_PRO_MSP_UPDATE_GET_STATUS: {
            if (header.data_length) {
                if (send_command_error(session, header.command, ESP_ERR_INVALID_SIZE) != ESP_OK)
                    running = false;
                break;
            }
            msp430_update_status_t update_status;
            msp430_programmer_get_status(&update_status);
            if (send_control(session, WULPUS_PRO_MSP_UPDATE_STATUS, &update_status,
                             sizeof(update_status)) != ESP_OK)
                running = false;
            break;
        }
        case WULPUS_PRO_MSP_UPDATE_GET_DIAGNOSTICS: {
            if (header.data_length) {
                if (send_command_error(session, header.command, ESP_ERR_INVALID_SIZE) != ESP_OK)
                    running = false;
                break;
            }
            msp430_diagnostics_t diagnostics;
            msp430_programmer_get_diagnostics(&diagnostics);
            if (send_control(session, WULPUS_PRO_MSP_UPDATE_DIAGNOSTICS, &diagnostics,
                             sizeof(diagnostics)) != ESP_OK)
                running = false;
            break;
        }
        case WULPUS_PRO_GET_DATA:
        case WULPUS_PRO_PONG:
        case WULPUS_PRO_BUSY:
        case WULPUS_PRO_STATUS:
        case WULPUS_PRO_DEVICE_CONFIG:
        case WULPUS_PRO_WIFI_STATUS:
        case WULPUS_PRO_ERROR:
        case WULPUS_PRO_MSP_UPDATE_STATUS:
        case WULPUS_PRO_MSP_UPDATE_DIAGNOSTICS:
        case WULPUS_PRO_FIRMWARE_INFO:
            break;
        case WULPUS_PRO_CMD_ID_BEGIN:
        case WULPUS_PRO_CMD_ID_END:
            /* Not wire commands; rejected by header validation above. */
            break;
        }
    }

    if (shutdown_msp(session) != ESP_OK) {
        wulpus_pro_status_set_error(WULPUS_PRO_ERROR_SPI_TIMEOUT);
    }
    link_close(session.link);
    wulpus_pro_session_release(session);
    provisioner_twt_suspend(0);
}

/**
 * @brief Consume queued session references and run sessions that are still current.
 */
static void protocol_task(void* argument)
{
    (void)argument;
    wulpus_pro_session_ref_t session;
    while (xQueueReceive(session_queue, &session, portMAX_DELAY) == pdTRUE) {
        if (wulpus_pro_session_is_current(session))
            run_session(session);
    }
}

esp_err_t protocol_thread_start(void)
{
    session_queue = xQueueCreate(2, sizeof(wulpus_pro_session_ref_t));
    if (session_queue == NULL)
        return ESP_ERR_NO_MEM;
    return xTaskCreate(protocol_task, "protocol", CONFIG_WP_PROTOCOL_STACK_SIZE, NULL,
                       CONFIG_WP_PROTOCOL_PRIORITY, NULL) == pdPASS
               ? ESP_OK
               : ESP_ERR_NO_MEM;
}

esp_err_t protocol_thread_submit_session(wulpus_pro_session_ref_t session)
{
    return xQueueSend(session_queue, &session, pdMS_TO_TICKS(100)) == pdTRUE ? ESP_OK
                                                                             : ESP_ERR_TIMEOUT;
}
