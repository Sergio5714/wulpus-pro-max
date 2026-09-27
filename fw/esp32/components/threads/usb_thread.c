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
 * @file usb_thread.c
 * @brief USB connection monitoring and session handoff.
 */

#include "thread_internal.h"

#include "board.h"
#include "freertos/task.h"
#include "usb_link.h"
#include "wulpus_pro_protocol.h"
#include "wulpus_pro_session.h"

/**
 * @brief Monitor USB connectivity, manage the sleep lock, and submit claimed sessions.
 */
static void usb_task(void* argument)
{
    (void)argument;
    static link_t link;
    ESP_ERROR_CHECK(usb_link_create(&link));
    while (true) {
        ESP_ERROR_CHECK(board_usb_no_sleep_acquire());
        vTaskDelay(pdMS_TO_TICKS(10));
        if (!link_is_connected(&link)) {
            ESP_ERROR_CHECK(board_usb_no_sleep_release());
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }
        if (wulpus_pro_protocol_wait_for_header(&link) != ESP_OK)
            continue;
        wulpus_pro_session_ref_t session;
        if (!wulpus_pro_session_try_claim(&link, &session)) {
            packet_tx_submit_to_link(&link, WULPUS_PRO_BUSY, NULL, 0, pdMS_TO_TICKS(1000));
            wulpus_pro_protocol_discard_prefetched_payload(&link);
            continue;
        }
        if (protocol_thread_submit_session(session) != ESP_OK) {
            wulpus_pro_session_release(session);
            continue;
        }
        while (wulpus_pro_session_is_current(session))
            vTaskDelay(pdMS_TO_TICKS(20));
    }
}

esp_err_t usb_thread_start(void)
{
    return xTaskCreate(usb_task, "usb_link", CONFIG_WP_LINK_STACK_SIZE, NULL,
                       CONFIG_WP_LINK_PRIORITY, NULL) == pdPASS
               ? ESP_OK
               : ESP_ERR_NO_MEM;
}
