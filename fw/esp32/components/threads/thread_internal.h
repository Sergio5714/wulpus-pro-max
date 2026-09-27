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
 * @file thread_internal.h
 * @brief Internal task startup and inter-task communication interfaces.
 */

#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "wulpus_pro_session.h"

typedef enum {
    ACQ_CMD_CONFIGURE,
    ACQ_CMD_ENABLE,
    ACQ_CMD_DISABLE,
    ACQ_CMD_QUIESCE,
    ACQ_CMD_RESTART,
    ACQ_CMD_BOOT,  /* Quiesce, pulse reset, release into WAIT_CONFIG. */
    ACQ_CMD_RESET, /* Quiesce and hold reset asserted. */
} acq_command_type_t;

/** @brief Create the command queue and SPI owner, then register the GPIO ISR. */
esp_err_t acquisition_thread_start(void);
/**
 * @brief Submit a copied command and wait for its private completion object.
 * CONFIGURE accepts a 0xFA configuration or a legacy 0xFB restart block.
 * Timeout cancels work not yet started; an in-flight SPI transfer must finish.
 * QUIESCE success confirms no transfer/publication remains in progress.
 * RESTART success confirms a new configuration request, or an MSP already held in reset.
 */
esp_err_t acquisition_thread_command(acq_command_type_t type, wulpus_pro_session_ref_t session,
                                     const void* config, size_t length, TickType_t timeout);

/**
 * @brief Create the control-response queue and packet transmission task.
 */
esp_err_t packet_tx_thread_start(void);
/** @brief Queue a copied response for the current session and wait for transmission. */
esp_err_t packet_tx_submit_control(wulpus_pro_session_ref_t session, uint8_t command,
                                   const void* payload, uint16_t length, TickType_t timeout);
/** @brief Queue a copied response for a link and wait for transmission. */
esp_err_t packet_tx_submit_to_link(link_t* link, uint8_t command, const void* payload,
                                   uint16_t length, TickType_t timeout);
/**
 * @brief Wake the packet transmission task if it has been created.
 */
void packet_tx_notify_frame_ready(void);
/**
 * @brief Discard all ready frames; the session argument is currently unused.
 */
void packet_tx_discard_session(wulpus_pro_session_ref_t session);

/**
 * @brief Create the session queue and protocol processing task.
 */
esp_err_t protocol_thread_start(void);
/**
 * @brief Queue a session for protocol processing, waiting at most 100 milliseconds.
 */
esp_err_t protocol_thread_submit_session(wulpus_pro_session_ref_t session);

/**
 * @brief Create the USB connection task.
 */
esp_err_t usb_thread_start(void);
/**
 * @brief Create the TCP listener task.
 */
esp_err_t tcp_thread_start(void);
/**
 * @brief Create the task that runs Wi-Fi provisioning and connection management.
 */
esp_err_t provisioning_thread_start(bool reset);
