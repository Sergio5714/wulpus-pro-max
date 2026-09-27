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
 * @file wulpus_pro_status.c
 * @brief Runtime error flags, counters, and frame-pool status snapshots.
 */

#include "wulpus_pro_status.h"

#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "wulpus_pro_frame_pool.h"

static SemaphoreHandle_t mutex;
static wulpus_pro_status_snapshot_t status;

esp_err_t wulpus_pro_status_init(void)
{
    mutex = xSemaphoreCreateMutex();
    if (mutex == NULL)
        return ESP_ERR_NO_MEM;
    memset(&status, 0, sizeof(status));
    status.version = 1;
    status.size = sizeof(status);
    return ESP_OK;
}

#define UPDATE(statement)                                                                          \
    do {                                                                                           \
        xSemaphoreTake(mutex, portMAX_DELAY);                                                      \
        statement;                                                                                 \
        xSemaphoreGive(mutex);                                                                     \
    } while (0)
void wulpus_pro_status_set_error(uint32_t flags)
{
    UPDATE(status.error_flags |= flags);
}
void wulpus_pro_status_increment_data_ready(void)
{
    UPDATE(++status.data_ready_count);
}
void wulpus_pro_status_increment_spi_complete(void)
{
    UPDATE(++status.completed_spi_count);
}
void wulpus_pro_status_increment_spi_error(void)
{
    UPDATE(++status.spi_error_count);
}
void wulpus_pro_status_increment_transmitted(void)
{
    UPDATE(++status.transmitted_frame_count);
}
void wulpus_pro_status_increment_discarded(void)
{
    UPDATE(++status.discarded_frame_count);
}
void wulpus_pro_status_increment_overflow(void)
{
    UPDATE(++status.buffer_overflow_count);
}
void wulpus_pro_status_increment_link_error(void)
{
    UPDATE(++status.link_error_count);
}

void wulpus_pro_status_snapshot(wulpus_pro_status_snapshot_t* snapshot)
{
    xSemaphoreTake(mutex, portMAX_DELAY);
    *snapshot = status;
    xSemaphoreGive(mutex);
    snapshot->current_buffer_usage = wulpus_pro_frame_pool_usage();
    snapshot->maximum_buffer_usage = wulpus_pro_frame_pool_max_usage();
}

void wulpus_pro_status_clear(uint32_t mask, bool clear_counters)
{
    xSemaphoreTake(mutex, portMAX_DELAY);
    status.error_flags &= ~mask;
    if (clear_counters) {
        uint8_t version = status.version;
        uint8_t size = status.size;
        memset(&status, 0, sizeof(status));
        status.version = version;
        status.size = size;
    }
    xSemaphoreGive(mutex);
    if (clear_counters)
        wulpus_pro_frame_pool_reset_max_usage();
}
