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
 * @file wulpus_pro_firmware_info.c
 * @brief ESP32 application metadata and runtime MSP430 version cache.
 */

#include "wulpus_pro_firmware_info.h"

#include <stdbool.h>
#include <string.h>

#include "esp_app_desc.h"
#include "freertos/FreeRTOS.h"

static portMUX_TYPE firmware_info_lock = portMUX_INITIALIZER_UNLOCKED;
static bool msp_valid;
static uint8_t msp_major;
static uint8_t msp_minor;
static uint8_t msp_patch;

void wulpus_pro_firmware_info_clear_msp(void)
{
    portENTER_CRITICAL(&firmware_info_lock);
    msp_valid = false;
    portEXIT_CRITICAL(&firmware_info_lock);
}

void wulpus_pro_firmware_info_set_msp(const void* data, size_t length)
{
    static const uint8_t magic[4] = {'W', 'V', 'E', 'R'};
    if (data == NULL || length < sizeof(wulpus_pro_msp_firmware_hello_t))
        return;
    wulpus_pro_msp_firmware_hello_t hello;
    memcpy(&hello, data, sizeof(hello));
    if (memcmp(hello.magic, magic, sizeof(magic)) != 0 ||
        hello.version != WULPUS_PRO_MSP_FIRMWARE_HELLO_VERSION)
        return;
    portENTER_CRITICAL(&firmware_info_lock);
    msp_major = hello.major;
    msp_minor = hello.minor;
    msp_patch = hello.patch;
    msp_valid = true;
    portEXIT_CRITICAL(&firmware_info_lock);
}

void wulpus_pro_firmware_info_get(wulpus_pro_firmware_info_t* info)
{
    memset(info, 0, sizeof(*info));
    info->version = WULPUS_PRO_FIRMWARE_INFO_VERSION;
    info->size = sizeof(*info);
    const esp_app_desc_t* app = esp_app_get_description();
    strlcpy(info->esp_version, app->version, sizeof(info->esp_version));
    portENTER_CRITICAL(&firmware_info_lock);
    if (msp_valid) {
        info->flags |= WULPUS_PRO_FIRMWARE_INFO_MSP_VALID;
        info->msp_major = msp_major;
        info->msp_minor = msp_minor;
        info->msp_patch = msp_patch;
    }
    portEXIT_CRITICAL(&firmware_info_lock);
}
