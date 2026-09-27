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
 * @file tcp_thread.c
 * @brief TCP connection acceptance and session handoff.
 */

#include "thread_internal.h"

#include "freertos/task.h"
#include "provisioner.h"
#include "tcp_link.h"
#include "wulpus_pro_protocol.h"
#include "wulpus_pro_session.h"

/**
 * @brief Accept TCP clients, synchronize headers, and submit claimed sessions for processing.
 */
static void tcp_task(void* argument)
{
    (void)argument;
    tcp_link_server_t server;
    bool initialized = false;
    while (true) {
        ESP_ERROR_CHECK(provisioner_wait_connected());
        if (!initialized) {
            ESP_ERROR_CHECK(tcp_link_server_init(&server, CONFIG_WP_SOCKET_PORT));
            initialized = true;
        }
        link_t link;
        if (tcp_link_accept(&server, &link) != ESP_OK)
            continue;
        if (wulpus_pro_protocol_wait_for_header(&link) != ESP_OK) {
            link_close(&link);
            continue;
        }
        wulpus_pro_session_ref_t session;
        if (!wulpus_pro_session_try_claim(&link, &session)) {
            packet_tx_submit_to_link(&link, WULPUS_PRO_BUSY, NULL, 0, pdMS_TO_TICKS(1000));
            wulpus_pro_protocol_discard_prefetched_payload(&link);
            link_close(&link);
            continue;
        }
        if (protocol_thread_submit_session(session) != ESP_OK) {
            wulpus_pro_session_release(session);
            link_close(&link);
            continue;
        }
        while (wulpus_pro_session_is_current(session))
            vTaskDelay(pdMS_TO_TICKS(20));
    }
}

esp_err_t tcp_thread_start(void)
{
    return xTaskCreate(tcp_task, "tcp_link", CONFIG_WP_LINK_STACK_SIZE, NULL,
                       CONFIG_WP_LINK_PRIORITY, NULL) == pdPASS
               ? ESP_OK
               : ESP_ERR_NO_MEM;
}
