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
 * @file acquisition_internal.h
 * @brief Shared acquisition state and internal worker interfaces.
 */

#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "thread_internal.h"
#include "wulpus_pro_frame_pool.h"

#define ACQUISITION_HANDSHAKE_TIMEOUT pdMS_TO_TICKS(2000)
#define ACQUISITION_BUFFER_WAIT pdMS_TO_TICKS(100)

/** @brief Acquisition owner-task state. */
typedef enum {
    ACQ_STATE_RESET,
    ACQ_STATE_WAIT_CONFIG,
    ACQ_STATE_CONFIGURING,
    ACQ_STATE_CONFIGURED,
    ACQ_STATE_ACQUIRING,
    ACQ_STATE_QUIESCENT,
    ACQ_STATE_RESTARTING,
} acq_state_t;

/** @brief Reference-counted command submitted to the acquisition owner task. */
typedef struct {
    acq_command_type_t type;
    wulpus_pro_session_ref_t session;
    uint8_t config[CONFIG_WP_DATA_RX_LENGTH];
    SemaphoreHandle_t done;
    esp_err_t result;
    unsigned references;
    bool cancelled;
} acq_request_t;

/** @brief Owner task handle used by command submitters and the DATA_READY ISR. */
extern TaskHandle_t acquisition_task_handle;
/** @brief Critical-section lock protecting cancellation and DATA_READY edge accounting. */
extern portMUX_TYPE acquisition_lock;
/** @brief Current acquisition owner-task state. */
extern acq_state_t acquisition_state;
/** @brief Whether the active session successfully configured the MSP430. */
extern bool acquisition_configured;
/** @brief Whether the ESP32 currently holds the MSP430 in reset. */
extern bool acquisition_reset_asserted;
/** @brief Session that owns the current MSP430 configuration. */
extern wulpus_pro_session_ref_t acquisition_owner;
/** @brief Frame retained before acquisition forwarding is enabled. */
extern wulpus_pro_frame_slot_t* acquisition_pending_frame;

/** @brief Return whether a submitted acquisition request was cancelled. */
bool acquisition_request_cancelled(acq_request_t* request);
/** @brief Record an acquisition SPI timeout or failure in runtime status. */
void acquisition_report_error(esp_err_t result);

/** @brief Record a DATA_READY rising edge and wake the acquisition task. */
void acquisition_data_ready_isr(void* argument);
/** @brief Return an interrupt-safe snapshot of the DATA_READY rising-edge count. */
uint32_t acquisition_data_ready_rise_count(void);
/** @brief Return whether an unconsumed DATA_READY assertion is pending. */
bool acquisition_data_ready_pending(void);
/** @brief Wait for an unconsumed DATA_READY assertion or request cancellation. */
esp_err_t acquisition_wait_ready(acq_request_t* request);
/** @brief Mark the current DATA_READY assertion as consumed. */
void acquisition_consume_assertion(void);
/** @brief Resynchronize DATA_READY bookkeeping after an MSP430 reset. */
void acquisition_reset_handshake(void);
/** @brief Wait for the MSP430 to lower DATA_READY after an SPI transfer. */
esp_err_t acquisition_wait_transfer_low(acq_request_t* request);
/** @brief Restart the MSP430 application and wait for its configuration request. */
esp_err_t acquisition_restart_msp(acq_request_t* request);

/** @brief Stop forwarding and discard pending and ready frames. */
void acquisition_quiesce(void);
/** @brief Publish the frame retained before forwarding was enabled. */
void acquisition_publish_pending(void);
/** @brief Receive and validate one pending MSP430 acquisition frame. */
void acquisition_receive_frame(void);

/** @brief Process queued commands and at most one pending frame. */
bool acquisition_process_work(void);
