/* Copyright (C) 2026 Sergei Vostrikov, SPDX-License-Identifier: Apache-2.0 */

/**
 * @file msp430_programmer.h
 * @brief Staged MSP430 firmware reception, persistent update state, and boot programming.
 */

#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"

#define MSP430_UPDATE_STATUS_VERSION 1
#define MSP430_UPDATE_FLAG_BOOT_PENDING 0x0001U
#define MSP430_DIAGNOSTICS_VERSION 1

typedef enum {
    MSP430_UPDATE_IDLE = 0,
    MSP430_UPDATE_RECEIVING,
    MSP430_UPDATE_READY,
    MSP430_UPDATE_VALIDATING,
    MSP430_UPDATE_PROGRAMMING,
    MSP430_UPDATE_VERIFYING,
    MSP430_UPDATE_RESETTING,
    MSP430_UPDATE_WAITING_FOR_BOOT,
    MSP430_UPDATE_COMPLETE,
    MSP430_UPDATE_FAILED,
    MSP430_UPDATE_ABORTED,
} msp430_update_state_t;

typedef struct __attribute__((packed)) {
    uint8_t version;
    uint8_t state;
    uint16_t flags;
    uint32_t received_bytes;
    uint32_t total_bytes;
    uint32_t processed_bytes;
    uint32_t current_address;
    uint32_t target_device_id;
    int32_t error;
} msp430_update_status_t;

typedef enum {
    MSP430_DIAG_NOT_STARTED = 0,
    MSP430_DIAG_JTAG_ENTRY,
    MSP430_DIAG_CORE_ID,
    MSP430_DIAG_DESCRIPTOR_POINTER,
    MSP430_DIAG_SYNCHRONIZATION,
    MSP430_DIAG_DEVICE_MEMORY_READ,
    MSP430_DIAG_DEVICE_VALIDATED,
} msp430_diagnostic_stage_t;

typedef struct __attribute__((packed)) {
    uint8_t version;
    uint8_t stage;
    uint16_t jtag_id;
    uint16_t core_id;
    uint16_t control_signal;
    uint32_t descriptor_pointer;
    uint16_t quick_device_id;
    uint16_t direct_device_id;
} msp430_diagnostics_t;

/**
 * @brief Locate the staging partition, create the mutex, and restore update status and diagnostics.
 */
esp_err_t msp430_programmer_init(void);
/**
 * @brief Return whether the persisted status requests an update at boot.
 */
bool msp430_programmer_boot_update_pending(void);
/**
 * @brief Validate and program a pending image synchronously, then persist the result.
 */
esp_err_t msp430_programmer_run_boot_update(void);
/**
 * @brief Prepare update reception and erase the required staging partition range.
 */
esp_err_t msp430_programmer_begin(uint32_t size, uint32_t crc32);
/**
 * @brief Append the next sequential image chunk to the staging partition.
 *
 * @param offset Byte offset; must equal the number of bytes already received.
 * @param data Non-null chunk data.
 * @param length Nonzero chunk size in bytes.
 * @return ESP_OK, an argument/state error, or a partition write error.
 */
esp_err_t msp430_programmer_write(uint32_t offset, const void* data, size_t length);
/**
 * @brief Persist the pending-update flag and schedule an ESP32 reboot.
 *
 * @note Success means the reboot was scheduled; programming occurs during the next boot.
 * @return ESP_OK, ESP_ERR_INVALID_STATE, ESP_ERR_NO_MEM, or an NVS persistence error.
 */
esp_err_t msp430_programmer_commit(void);
/**
 * @brief Request cancellation and mark the update aborted when no worker exists.
 */
esp_err_t msp430_programmer_abort(void);
/**
 * @brief Copy update status under the mutex; ignore a null destination.
 */
void msp430_programmer_get_status(msp430_update_status_t* status);
/**
 * @brief Copy diagnostics under the mutex; ignore a null destination.
 */
void msp430_programmer_get_diagnostics(msp430_diagnostics_t* diagnostics);
