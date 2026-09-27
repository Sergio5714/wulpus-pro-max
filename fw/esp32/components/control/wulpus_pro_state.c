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
 * @file wulpus_pro_state.c
 * @brief Mutex-protected acquisition and firmware-update state.
 */

#include "wulpus_pro_state.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
static SemaphoreHandle_t mutex;
static bool acquiring;
static bool updating;
esp_err_t wulpus_pro_state_init(void)
{
    mutex = xSemaphoreCreateMutex();
    return mutex ? ESP_OK : ESP_ERR_NO_MEM;
}
void wulpus_pro_state_set_acquiring(bool value)
{
    xSemaphoreTake(mutex, portMAX_DELAY);
    acquiring = value;
    xSemaphoreGive(mutex);
}
bool wulpus_pro_state_is_acquiring(void)
{
    xSemaphoreTake(mutex, portMAX_DELAY);
    bool value = acquiring;
    xSemaphoreGive(mutex);
    return value;
}
void wulpus_pro_state_set_updating(bool value)
{
    xSemaphoreTake(mutex, portMAX_DELAY);
    updating = value;
    xSemaphoreGive(mutex);
}
bool wulpus_pro_state_is_updating(void)
{
    xSemaphoreTake(mutex, portMAX_DELAY);
    bool value = updating;
    xSemaphoreGive(mutex);
    return value;
}
