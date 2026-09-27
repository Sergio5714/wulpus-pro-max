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
 * @file wulpus_pro_firmware_info.h
 * @brief Firmware metadata exchanged with the MSP430 and PC clients.
 */

#pragma once

#include <stddef.h>
#include <stdint.h>

#define WULPUS_PRO_FIRMWARE_INFO_VERSION 1
#define WULPUS_PRO_FIRMWARE_INFO_SIZE 72
#define WULPUS_PRO_MSP_FIRMWARE_HELLO_VERSION 1
#define WULPUS_PRO_FIRMWARE_INFO_MSP_VALID (1u << 0)
#define WULPUS_PRO_FIRMWARE_INFO_ESP_DIRTY (1u << 1)
#define WULPUS_PRO_FIRMWARE_INFO_MSP_DIRTY (1u << 2)
#define WULPUS_PRO_ESP_VERSION_LENGTH 32
#define WULPUS_PRO_GIT_HASH_LENGTH 13

/** @brief MSP430 metadata returned during the full-duplex configuration transfer. */
typedef struct __attribute__((packed)) {
    uint8_t magic[4];
    uint8_t version;
    uint8_t major;
    uint8_t minor;
    uint8_t patch;
} wulpus_pro_msp_firmware_hello_t;

/** @brief Versioned firmware metadata returned to a PC protocol client. */
typedef struct __attribute__((packed)) {
    uint8_t version;
    uint8_t size;
    uint8_t flags;
    uint8_t reserved;
    uint8_t msp_major;
    uint8_t msp_minor;
    uint8_t msp_patch;
    uint8_t reserved_2;
    char esp_version[WULPUS_PRO_ESP_VERSION_LENGTH];
    char esp_git_hash[WULPUS_PRO_GIT_HASH_LENGTH];
    char msp_git_hash[WULPUS_PRO_GIT_HASH_LENGTH];
    uint8_t reserved_3[6];
} wulpus_pro_firmware_info_t;

_Static_assert(sizeof(wulpus_pro_firmware_info_t) == WULPUS_PRO_FIRMWARE_INFO_SIZE,
               "firmware information wire size changed");

/** @brief Invalidate cached MSP430 metadata after an MSP430 reset. */
void wulpus_pro_firmware_info_clear_msp(void);
/**
 * @brief Validate and cache an MSP430 hello received during configuration.
 *
 * Unknown or truncated hello formats are ignored for compatibility with older firmware.
 */
void wulpus_pro_firmware_info_set_msp(const void* data, size_t length);
/** @brief Build a PC protocol response from ESP-IDF metadata and cached MSP430 metadata. */
void wulpus_pro_firmware_info_get(wulpus_pro_firmware_info_t* info);
