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
 * @file wulpus_pro_commands.h
 * @brief Wire command identifiers and printable command names.
 */

#pragma once
#include <stdint.h>
/* Command IDs must remain contiguous between the exclusive bounds below.
 * The bounds are sentinels, not commands, and must never be transmitted.
 */
typedef enum {
    WULPUS_PRO_CMD_ID_BEGIN = 0x56,
    WULPUS_PRO_SET_ACQ_CONFIG = 0x57,
    WULPUS_PRO_GET_DATA = 0x58,
    WULPUS_PRO_PING = 0x59,
    WULPUS_PRO_PONG = 0x5A,
    WULPUS_PRO_RESET = 0x5B,
    WULPUS_PRO_CLOSE = 0x5C,
    WULPUS_PRO_START_RX = 0x5D,
    WULPUS_PRO_STOP_RX = 0x5E,
    WULPUS_PRO_BUSY = 0x5F,
    WULPUS_PRO_GET_STATUS = 0x60,
    WULPUS_PRO_STATUS = 0x61,
    WULPUS_PRO_CLEAR_STATUS = 0x62,
    WULPUS_PRO_RESET_MSP = 0x63,
    WULPUS_PRO_GET_DEVICE_CONFIG = 0x64,
    WULPUS_PRO_DEVICE_CONFIG = 0x65,
    WULPUS_PRO_SET_DEVICE_CONFIG = 0x66,
    WULPUS_PRO_GET_WIFI_STATUS = 0x67,
    WULPUS_PRO_WIFI_STATUS = 0x68,
    WULPUS_PRO_SET_WIFI_CREDENTIALS = 0x69,
    WULPUS_PRO_CLEAR_WIFI_CREDENTIALS = 0x6A,
    WULPUS_PRO_ERROR = 0x6B,
    WULPUS_PRO_MSP_UPDATE_BEGIN = 0x6C,
    WULPUS_PRO_MSP_UPDATE_DATA = 0x6D,
    WULPUS_PRO_MSP_UPDATE_COMMIT = 0x6E,
    WULPUS_PRO_MSP_UPDATE_ABORT = 0x6F,
    WULPUS_PRO_MSP_UPDATE_GET_STATUS = 0x70,
    WULPUS_PRO_MSP_UPDATE_STATUS = 0x71,
    WULPUS_PRO_MSP_UPDATE_GET_DIAGNOSTICS = 0x72,
    WULPUS_PRO_MSP_UPDATE_DIAGNOSTICS = 0x73,
    WULPUS_PRO_GET_FIRMWARE_INFO = 0x74,
    WULPUS_PRO_FIRMWARE_INFO = 0x75,
    WULPUS_PRO_CMD_ID_END,
} wulpus_pro_command_t;

typedef struct __attribute__((packed)) {
    uint8_t version;
    uint8_t flags;
    uint16_t reserved;
    uint32_t image_size;
    uint32_t image_crc32;
} wulpus_pro_msp_update_begin_t;

typedef struct __attribute__((packed)) {
    uint32_t offset;
    uint16_t sequence;
    uint16_t data_length;
    uint32_t data_crc32;
} wulpus_pro_msp_update_data_t;

typedef struct __attribute__((packed)) {
    uint32_t next_offset;
    uint16_t accepted_sequence;
    uint16_t reserved;
} wulpus_pro_msp_update_data_response_t;

typedef struct __attribute__((packed)) {
    uint8_t version;
    uint8_t ssid_length;
    uint8_t password_length;
    uint8_t reserved;
} wulpus_pro_wifi_credentials_header_t;

typedef struct __attribute__((packed)) {
    uint8_t command;
    int32_t error;
} wulpus_pro_error_response_t;
/**
 * @brief Return a static command name, or UNKNOWN for an unrecognized value.
 */
const char* wulpus_pro_command_name(wulpus_pro_command_t command);
