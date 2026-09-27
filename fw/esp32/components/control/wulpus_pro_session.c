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
 * @file wulpus_pro_session.c
 * @brief Active transport session ownership and generation tracking.
 */

#include "wulpus_pro_session.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
static SemaphoreHandle_t mutex;
static wulpus_pro_session_ref_t active;
esp_err_t wulpus_pro_session_init(void)
{
    mutex = xSemaphoreCreateMutex();
    return mutex ? ESP_OK : ESP_ERR_NO_MEM;
}
bool wulpus_pro_session_try_claim(link_t* link, wulpus_pro_session_ref_t* session)
{
    bool claimed = false;
    xSemaphoreTake(mutex, portMAX_DELAY);
    if (active.link == NULL) {
        active.link = link;
        active.kind = link->kind;
        ++active.generation;
        if (active.generation == 0)
            ++active.generation;
        *session = active;
        claimed = true;
    }
    xSemaphoreGive(mutex);
    return claimed;
}
void wulpus_pro_session_release(wulpus_pro_session_ref_t session)
{
    xSemaphoreTake(mutex, portMAX_DELAY);
    if (active.link == session.link && active.generation == session.generation) {
        active.link = NULL;
        active.kind = LINK_NONE;
        ++active.generation;
    }
    xSemaphoreGive(mutex);
}
wulpus_pro_session_ref_t wulpus_pro_session_current(void)
{
    xSemaphoreTake(mutex, portMAX_DELAY);
    wulpus_pro_session_ref_t value = active;
    xSemaphoreGive(mutex);
    return value;
}
bool wulpus_pro_session_is_current(wulpus_pro_session_ref_t session)
{
    xSemaphoreTake(mutex, portMAX_DELAY);
    bool result = active.link == session.link && active.generation == session.generation;
    xSemaphoreGive(mutex);
    return result;
}
