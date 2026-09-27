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
 * @file wulpus_pro_status.h
 * @brief Runtime error flags, counters, and frame-pool status snapshots.
 */

#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "esp_err.h"

typedef enum {
    WULPUS_PRO_ERROR_ACQ_BUFFER_OVERFLOW = 1u << 0,
    WULPUS_PRO_ERROR_DATA_READY_OVERFLOW = 1u << 1,
    WULPUS_PRO_ERROR_SPI_TIMEOUT = 1u << 2,
    WULPUS_PRO_ERROR_SPI_FAILURE = 1u << 3,
    WULPUS_PRO_ERROR_LINK_TIMEOUT = 1u << 4,
    WULPUS_PRO_ERROR_LINK_DISCONNECTED = 1u << 5,
    WULPUS_PRO_ERROR_PROTOCOL = 1u << 6,
} wulpus_pro_error_t;

typedef struct __attribute__((packed)) {
    uint8_t version;
    uint8_t size;
    uint16_t reserved;
    uint32_t error_flags;
    uint32_t buffer_overflow_count;
    uint32_t data_ready_count;
    uint32_t completed_spi_count;
    uint32_t transmitted_frame_count;
    uint32_t discarded_frame_count;
    uint32_t spi_error_count;
    uint32_t link_error_count;
    uint16_t current_buffer_usage;
    uint16_t maximum_buffer_usage;
} wulpus_pro_status_snapshot_t;

/**
 * @brief Create the status mutex and initialize the versioned status snapshot.
 */
esp_err_t wulpus_pro_status_init(void);
/**
 * @brief Latch the supplied error bits into the status flags.
 */
void wulpus_pro_status_set_error(uint32_t flags);
/**
 * @brief Increment the counter for DATA_READY events under the status mutex.
 */
void wulpus_pro_status_increment_data_ready(void);
/**
 * @brief Increment the counter for completed SPI transfers under the status mutex.
 */
void wulpus_pro_status_increment_spi_complete(void);
/**
 * @brief Increment the counter for SPI errors under the status mutex.
 */
void wulpus_pro_status_increment_spi_error(void);
/**
 * @brief Increment the counter for transmitted frames under the status mutex.
 */
void wulpus_pro_status_increment_transmitted(void);
/**
 * @brief Increment the counter for discarded frames under the status mutex.
 */
void wulpus_pro_status_increment_discarded(void);
/**
 * @brief Increment the counter for buffer overflows under the status mutex.
 */
void wulpus_pro_status_increment_overflow(void);
/**
 * @brief Increment the counter for link errors under the status mutex.
 */
void wulpus_pro_status_increment_link_error(void);
/**
 * @brief Copy status counters and flags, then query current and peak pool usage.
 */
void wulpus_pro_status_snapshot(wulpus_pro_status_snapshot_t* snapshot);
/**
 * @brief Clear selected error bits and optionally reset all flags and counters.
 *
 * @param mask Error bits to clear.
 * @param clear_counters If true, clear all error flags and counters and reset peak pool usage.
 * @note The snapshot version and size are preserved.
 */
void wulpus_pro_status_clear(uint32_t mask, bool clear_counters);
