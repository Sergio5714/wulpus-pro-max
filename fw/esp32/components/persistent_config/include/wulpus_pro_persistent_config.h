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
 * @file wulpus_pro_persistent_config.h
 * @brief Versioned device policy defaults, validation, and NVS persistence.
 */

#pragma once

#include <stdint.h>
#include "esp_err.h"

#define WULPUS_PRO_DEVICE_CONFIG_VERSION 1

typedef enum {
    WULPUS_PRO_WIFI_PS_NONE = 0,
    WULPUS_PRO_WIFI_PS_MIN_MODEM = 1,
    WULPUS_PRO_WIFI_PS_MAX_MODEM = 2,
} wulpus_pro_wifi_power_save_t;

typedef struct __attribute__((packed)) {
    uint8_t version;
    uint8_t size;
    uint8_t wifi_enabled_at_boot;
    uint8_t auto_provision;
    uint8_t wifi_power_save_mode;
    uint8_t twt_enabled;
    uint8_t reserved[10];
} wulpus_pro_device_config_t;

/**
 * @brief Fill a device configuration with the firmware's default policy.
 */
void wulpus_pro_device_config_defaults(wulpus_pro_device_config_t* config);
/**
 * @brief Validate configuration version, size, flags, power-save mode, and reserved bytes.
 */
esp_err_t wulpus_pro_device_config_validate(const wulpus_pro_device_config_t* config);
/**
 * @brief Load configuration from NVS, falling back to defaults for missing or invalid records.
 */
esp_err_t wulpus_pro_device_config_load(wulpus_pro_device_config_t* config);
/**
 * @brief Validate the device configuration and commit it to NVS.
 */
esp_err_t wulpus_pro_device_config_save(const wulpus_pro_device_config_t* config);
