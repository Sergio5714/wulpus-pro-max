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

/** @file acquisition_handshake.c
 * @brief DATA_READY accounting and MSP430 SPI handshake sequencing. */

#include "acquisition_internal.h"
#include "board.h"
#include "wulpus_pro_firmware_info.h"
#include "wulpus_pro_status.h"

/* Edge bookkeeping is private; callers interact through handshake helpers. */
static uint32_t acquisition_rising_edges;
static uint32_t acquisition_consumed_rise;
static bool acquisition_assertion_consumed;

/** @brief Records a DATA_READY rising edge and wakes the acquisition task. */
void IRAM_ATTR acquisition_data_ready_isr(void* argument)
{
    (void)argument;
    BaseType_t wake = pdFALSE;
    portENTER_CRITICAL_ISR(&acquisition_lock);
    ++acquisition_rising_edges;
    portEXIT_CRITICAL_ISR(&acquisition_lock);
    vTaskNotifyGiveFromISR(acquisition_task_handle, &wake);
    if (wake)
        portYIELD_FROM_ISR();
}

/** @brief Returns an interrupt-safe snapshot of the DATA_READY rising-edge count. */
uint32_t acquisition_data_ready_rise_count(void)
{
    portENTER_CRITICAL(&acquisition_lock);
    uint32_t count = acquisition_rising_edges;
    portEXIT_CRITICAL(&acquisition_lock);
    return count;
}

/** @brief Reports whether DATA_READY has an asserted edge that has not been consumed. */
bool acquisition_data_ready_pending(void)
{
    return board_data_ready() && (!acquisition_assertion_consumed ||
                                  acquisition_data_ready_rise_count() != acquisition_consumed_rise);
}

/** @brief Waits for an unconsumed DATA_READY assertion or cancellation/timeout. */
esp_err_t acquisition_wait_ready(acq_request_t* request)
{
    TickType_t started = xTaskGetTickCount();
    while (!acquisition_data_ready_pending()) {
        if (acquisition_request_cancelled(request))
            return ESP_ERR_INVALID_STATE;
        if (xTaskGetTickCount() - started >= ACQUISITION_HANDSHAKE_TIMEOUT)
            return ESP_ERR_TIMEOUT;
        ulTaskNotifyTake(pdTRUE, 1);
    }
    return acquisition_request_cancelled(request) ? ESP_ERR_INVALID_STATE : ESP_OK;
}

/** @brief Marks the current DATA_READY assertion as handled. */
void acquisition_consume_assertion(void)
{
    acquisition_consumed_rise = acquisition_data_ready_rise_count();
    acquisition_assertion_consumed = true;
    wulpus_pro_status_increment_data_ready();
}

/** @brief Resynchronizes handshake bookkeeping after an MSP430 reset. */
void acquisition_reset_handshake(void)
{
    acquisition_consumed_rise = acquisition_data_ready_rise_count();
    acquisition_assertion_consumed = false;
}

/** @brief Waits for the MSP430 to acknowledge a transfer by lowering DATA_READY. */
esp_err_t acquisition_wait_transfer_low(acq_request_t* request)
{
    TickType_t started = xTaskGetTickCount();
    while (board_data_ready() && acquisition_data_ready_rise_count() == acquisition_consumed_rise) {
        if (acquisition_request_cancelled(request))
            return ESP_ERR_INVALID_STATE;
        if (xTaskGetTickCount() - started >= ACQUISITION_HANDSHAKE_TIMEOUT)
            return ESP_ERR_TIMEOUT;
        ulTaskNotifyTake(pdTRUE, 1);
    }
    return ESP_OK;
}

/** @brief Sends the restart command and waits for the next configuration request. */
esp_err_t acquisition_restart_msp(acq_request_t* request)
{
    if (acquisition_state != ACQ_STATE_QUIESCENT)
        return ESP_ERR_INVALID_STATE;
    if (acquisition_reset_asserted)
        return ESP_OK;
    wulpus_pro_firmware_info_clear_msp();
    acquisition_state = ACQ_STATE_RESTARTING;
    esp_err_t result = acquisition_wait_ready(request);
    if (result == ESP_OK) {
        uint8_t restart[CONFIG_WP_DATA_RX_LENGTH] = {0xFB};
        acquisition_consume_assertion();
        result = board_spi_transmit(restart, sizeof(restart));
        if (result == ESP_OK)
            result = acquisition_wait_transfer_low(request);
        if (result == ESP_OK)
            result = acquisition_wait_ready(request);
    }
    if (result == ESP_OK) {
        acquisition_configured = false;
        acquisition_state = ACQ_STATE_WAIT_CONFIG;
    } else {
        acquisition_quiesce();
    }
    return result;
}
