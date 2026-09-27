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
 * @file threads.c
 * @brief Startup of the firmware runtime tasks.
 */

#include "threads.h"
#include "thread_internal.h"
#include "esp_check.h"

esp_err_t threads_start(bool reset_provisioning)
{
    ESP_RETURN_ON_ERROR(packet_tx_thread_start(), "threads", "packet TX thread failed");
    ESP_RETURN_ON_ERROR(acquisition_thread_start(), "threads", "acquisition thread failed");
    ESP_RETURN_ON_ERROR(protocol_thread_start(), "threads", "protocol thread failed");
    ESP_RETURN_ON_ERROR(usb_thread_start(), "threads", "USB thread failed");
    ESP_RETURN_ON_ERROR(tcp_thread_start(), "threads", "TCP thread failed");
    ESP_RETURN_ON_ERROR(provisioning_thread_start(reset_provisioning), "threads",
                        "provisioning thread failed");
    return ESP_OK;
}
