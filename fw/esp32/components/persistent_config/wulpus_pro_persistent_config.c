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

SPDX-License-Identifier: Apache-2.0
*/

/**
 * @file wulpus_pro_persistent_config.c
 * @brief Versioned device policy defaults, validation, and NVS persistence.
 */

#include "wulpus_pro_persistent_config.h"

#include <stdbool.h>
#include <string.h>
#include "nvs.h"

#define WP_NVS_NAMESPACE "wulpus_pro"
#define WP_NVS_DEVICE_CONFIG_KEY "device_cfg"

void wulpus_pro_device_config_defaults(wulpus_pro_device_config_t* config)
{
    *config = (wulpus_pro_device_config_t){
        .version = WULPUS_PRO_DEVICE_CONFIG_VERSION,
        .size = sizeof(*config),
        .wifi_enabled_at_boot = true,
        .auto_provision = true,
        .wifi_power_save_mode = WULPUS_PRO_WIFI_PS_MAX_MODEM,
        .twt_enabled = false,
    };
}

esp_err_t wulpus_pro_device_config_validate(const wulpus_pro_device_config_t* config)
{
    if (config == NULL || config->version != WULPUS_PRO_DEVICE_CONFIG_VERSION ||
        config->size != sizeof(*config) || config->wifi_enabled_at_boot > 1 ||
        config->auto_provision > 1 || config->twt_enabled > 1 ||
        config->wifi_power_save_mode > WULPUS_PRO_WIFI_PS_MAX_MODEM)
        return ESP_ERR_INVALID_ARG;
    for (size_t i = 0; i < sizeof(config->reserved); ++i) {
        if (config->reserved[i] != 0)
            return ESP_ERR_INVALID_ARG;
    }
    return ESP_OK;
}

esp_err_t wulpus_pro_device_config_load(wulpus_pro_device_config_t* config)
{
    if (config == NULL)
        return ESP_ERR_INVALID_ARG;
    nvs_handle_t handle;
    esp_err_t result = nvs_open(WP_NVS_NAMESPACE, NVS_READONLY, &handle);
    if (result == ESP_ERR_NVS_NOT_FOUND) {
        wulpus_pro_device_config_defaults(config);
        return ESP_OK;
    }
    if (result != ESP_OK)
        return result;
    size_t size = sizeof(*config);
    result = nvs_get_blob(handle, WP_NVS_DEVICE_CONFIG_KEY, config, &size);
    nvs_close(handle);
    if (result != ESP_OK && result != ESP_ERR_NVS_NOT_FOUND)
        return result;
    if (result == ESP_ERR_NVS_NOT_FOUND || size != sizeof(*config) ||
        wulpus_pro_device_config_validate(config) != ESP_OK) {
        wulpus_pro_device_config_defaults(config);
        return ESP_OK;
    }
    return result;
}

esp_err_t wulpus_pro_device_config_save(const wulpus_pro_device_config_t* config)
{
    esp_err_t result = wulpus_pro_device_config_validate(config);
    if (result != ESP_OK)
        return result;
    nvs_handle_t handle = 0;
    result = nvs_open(WP_NVS_NAMESPACE, NVS_READWRITE, &handle);
    if (result == ESP_OK)
        result = nvs_set_blob(handle, WP_NVS_DEVICE_CONFIG_KEY, config, sizeof(*config));
    if (result == ESP_OK)
        result = nvs_commit(handle);
    if (handle)
        nvs_close(handle);
    return result;
}
