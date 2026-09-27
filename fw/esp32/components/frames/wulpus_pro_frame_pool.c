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
 * @file wulpus_pro_frame_pool.c
 * @brief DMA frame storage and slot transitions between acquisition and transmission.
 */

#include "wulpus_pro_frame_pool.h"

#include "esp_heap_caps.h"
#include "freertos/semphr.h"

typedef enum { SLOT_FREE, SLOT_SPI, SLOT_READY, SLOT_TX } slot_state_t;

static wulpus_pro_frame_slot_t slots[WULPUS_PRO_FRAME_SLOT_COUNT];
static slot_state_t states[WULPUS_PRO_FRAME_SLOT_COUNT];
static SemaphoreHandle_t mutex;
static SemaphoreHandle_t free_slots;
static SemaphoreHandle_t ready_slots;
static uint8_t producer_index;
static uint8_t consumer_index;
static uint16_t usage;
static uint16_t maximum_usage;

esp_err_t wulpus_pro_frame_pool_init(size_t payload_size)
{
    mutex = xSemaphoreCreateMutex();
    free_slots = xSemaphoreCreateCounting(WULPUS_PRO_FRAME_SLOT_COUNT, WULPUS_PRO_FRAME_SLOT_COUNT);
    ready_slots = xSemaphoreCreateCounting(WULPUS_PRO_FRAME_SLOT_COUNT, 0);
    if (mutex == NULL || free_slots == NULL || ready_slots == NULL) {
        return ESP_ERR_NO_MEM;
    }
    for (uint8_t index = 0; index < WULPUS_PRO_FRAME_SLOT_COUNT; ++index) {
        slots[index].payload =
            heap_caps_aligned_calloc(4, 1, payload_size, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
        if (slots[index].payload == NULL) {
            return ESP_ERR_NO_MEM;
        }
        slots[index].length = payload_size;
        slots[index].private_index = index;
        states[index] = SLOT_FREE;
    }
    return ESP_OK;
}

wulpus_pro_frame_slot_t* wulpus_pro_frame_pool_acquire_for_spi(TickType_t timeout)
{
    if (xSemaphoreTake(free_slots, timeout) != pdTRUE) {
        return NULL;
    }
    xSemaphoreTake(mutex, portMAX_DELAY);
    wulpus_pro_frame_slot_t* result = NULL;
    for (uint8_t count = 0; count < WULPUS_PRO_FRAME_SLOT_COUNT; ++count) {
        uint8_t index = (producer_index + count) % WULPUS_PRO_FRAME_SLOT_COUNT;
        if (states[index] == SLOT_FREE) {
            states[index] = SLOT_SPI;
            producer_index = (index + 1) % WULPUS_PRO_FRAME_SLOT_COUNT;
            ++usage;
            if (usage > maximum_usage)
                maximum_usage = usage;
            result = &slots[index];
            break;
        }
    }
    xSemaphoreGive(mutex);
    if (result == NULL)
        xSemaphoreGive(free_slots);
    return result;
}

void wulpus_pro_frame_pool_mark_ready(wulpus_pro_frame_slot_t* slot)
{
    xSemaphoreTake(mutex, portMAX_DELAY);
    states[slot->private_index] = SLOT_READY;
    xSemaphoreGive(mutex);
    xSemaphoreGive(ready_slots);
}

wulpus_pro_frame_slot_t* wulpus_pro_frame_pool_acquire_for_tx(TickType_t timeout)
{
    if (xSemaphoreTake(ready_slots, timeout) != pdTRUE)
        return NULL;
    xSemaphoreTake(mutex, portMAX_DELAY);
    wulpus_pro_frame_slot_t* result = NULL;
    for (uint8_t count = 0; count < WULPUS_PRO_FRAME_SLOT_COUNT; ++count) {
        uint8_t index = (consumer_index + count) % WULPUS_PRO_FRAME_SLOT_COUNT;
        if (states[index] == SLOT_READY) {
            states[index] = SLOT_TX;
            consumer_index = (index + 1) % WULPUS_PRO_FRAME_SLOT_COUNT;
            result = &slots[index];
            break;
        }
    }
    xSemaphoreGive(mutex);
    return result;
}

void wulpus_pro_frame_pool_release(wulpus_pro_frame_slot_t* slot)
{
    if (slot == NULL)
        return;
    xSemaphoreTake(mutex, portMAX_DELAY);
    states[slot->private_index] = SLOT_FREE;
    if (usage > 0)
        --usage;
    xSemaphoreGive(mutex);
    xSemaphoreGive(free_slots);
}

void wulpus_pro_frame_pool_discard_ready(void)
{
    while (xSemaphoreTake(ready_slots, 0) == pdTRUE) {
        xSemaphoreTake(mutex, portMAX_DELAY);
        for (uint8_t index = 0; index < WULPUS_PRO_FRAME_SLOT_COUNT; ++index) {
            if (states[index] == SLOT_READY) {
                states[index] = SLOT_FREE;
                if (usage > 0)
                    --usage;
                xSemaphoreGive(free_slots);
                break;
            }
        }
        xSemaphoreGive(mutex);
    }
}

uint16_t wulpus_pro_frame_pool_usage(void)
{
    xSemaphoreTake(mutex, portMAX_DELAY);
    uint16_t value = usage;
    xSemaphoreGive(mutex);
    return value;
}

uint16_t wulpus_pro_frame_pool_max_usage(void)
{
    xSemaphoreTake(mutex, portMAX_DELAY);
    uint16_t value = maximum_usage;
    xSemaphoreGive(mutex);
    return value;
}

void wulpus_pro_frame_pool_reset_max_usage(void)
{
    xSemaphoreTake(mutex, portMAX_DELAY);
    maximum_usage = usage;
    xSemaphoreGive(mutex);
}
