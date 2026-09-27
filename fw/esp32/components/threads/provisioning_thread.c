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
 * @file provisioning_thread.c
 * @brief Wi-Fi provisioning, mDNS advertisement, and TWT setup task.
 */

#include "thread_internal.h"

#include "freertos/task.h"
#include "esp_log.h"
#include "mdns_manager.h"
#include "provisioner.h"

/**
 * @brief Run provisioning, advertise mDNS after connection, and configure TWT on reconnect.
 */
static void provisioning_task(void* argument)
{
    bool reset = (bool)(uintptr_t)argument;
    bool mdns_started = false;
    ESP_ERROR_CHECK(provisioner_start(reset));
    while (true) {
        ESP_ERROR_CHECK(provisioner_wait_connected());
        if (!mdns_started) {
            ESP_ERROR_CHECK(mdns_manager_init("wulpus_pro"));
            ESP_ERROR_CHECK(mdns_manager_add("wulpus_pro", MDNS_PROTO_TCP, CONFIG_WP_SOCKET_PORT));
            mdns_started = true;
        }
        esp_err_t result = provisioner_twt_setup();
        if (result != ESP_OK && result != ESP_ERR_NOT_SUPPORTED) {
            ESP_LOGW("wifi_manager", "TWT setup failed: %s", esp_err_to_name(result));
        }
        ESP_ERROR_CHECK(provisioner_wait_disconnected());
    }
}

esp_err_t provisioning_thread_start(bool reset)
{
    return xTaskCreate(provisioning_task, "provisioning", CONFIG_WP_PROVISIONING_STACK_SIZE,
                       (void*)(uintptr_t)reset, CONFIG_WP_PROVISIONING_PRIORITY, NULL) == pdPASS
               ? ESP_OK
               : ESP_ERR_NO_MEM;
}
