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
 * @file wulpus_pro_frame_pool.h
 * @brief DMA frame storage and slot transitions between acquisition and transmission.
 */

#pragma once

#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"
#include "freertos/FreeRTOS.h"

#define WULPUS_PRO_FRAME_SLOT_COUNT CONFIG_WP_FRAME_SLOT_COUNT

typedef struct wulpus_pro_frame_slot {
    uint8_t* payload;
    size_t length;
    uint32_t session_generation;
    int64_t data_ready_time_us;
    int64_t spi_complete_time_us;
    uint8_t private_index;
} wulpus_pro_frame_slot_t;

/**
 * @brief Allocate internal DMA-capable payload buffers and pool semaphores.
 *
 * @param payload_size Bytes allocated for each frame payload.
 * @return ESP_OK on success; ESP_ERR_NO_MEM if allocation fails.
 */
esp_err_t wulpus_pro_frame_pool_init(size_t payload_size);
/**
 * @brief Reserve a free slot for SPI reception and update pool usage.
 *
 * @param timeout FreeRTOS ticks to wait for an available slot.
 * @return A pool-owned slot, or NULL if no slot is obtained.
 * @note The caller must release the slot or, for SPI, publish it with mark_ready().
 */
wulpus_pro_frame_slot_t* wulpus_pro_frame_pool_acquire_for_spi(TickType_t timeout);
/**
 * @brief Publish a filled SPI slot for packet transmission.
 */
void wulpus_pro_frame_pool_mark_ready(wulpus_pro_frame_slot_t* slot);
/**
 * @brief Reserve a ready slot for packet transmission.
 *
 * @param timeout FreeRTOS ticks to wait for an available slot.
 * @return A pool-owned slot, or NULL if no slot is obtained.
 * @note The caller must release the slot or, for SPI, publish it with mark_ready().
 */
wulpus_pro_frame_slot_t* wulpus_pro_frame_pool_acquire_for_tx(TickType_t timeout);
/**
 * @brief Return a reserved slot to the free pool; ignore a null slot.
 */
void wulpus_pro_frame_pool_release(wulpus_pro_frame_slot_t* slot);
/**
 * @brief Return all currently queued ready slots to the free pool.
 */
void wulpus_pro_frame_pool_discard_ready(void);
/**
 * @brief Return the number of slots currently in use under the pool mutex.
 */
uint16_t wulpus_pro_frame_pool_usage(void);
/**
 * @brief Return the peak number of slots in use under the pool mutex.
 */
uint16_t wulpus_pro_frame_pool_max_usage(void);
/**
 * @brief Reset the peak usage to the current number of occupied slots.
 */
void wulpus_pro_frame_pool_reset_max_usage(void);
