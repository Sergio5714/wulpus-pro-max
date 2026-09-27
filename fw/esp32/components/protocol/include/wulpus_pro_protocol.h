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
 * @file wulpus_pro_protocol.h
 * @brief Packet headers, stream synchronization, and payload reception.
 */

#pragma once
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
#include "link.h"
#include "wulpus_pro_commands.h"

#define WULPUS_PRO_HEADER_SIZE 9
#define WULPUS_PRO_MAGIC "wulpus"

typedef struct __attribute__((packed)) {
    char magic[6];
    uint8_t command;
    uint16_t data_length;
} wulpus_pro_header_t;

typedef struct __attribute__((packed)) {
    uint32_t error_mask;
    uint8_t clear_counters;
} wulpus_pro_clear_status_t;

/**
 * @brief Fill the magic bytes, command ID, and payload byte count of a header.
 *
 * @param header Destination header.
 * @param command Wire command ID.
 * @param length Payload size in bytes.
 */
void wulpus_pro_protocol_make_header(wulpus_pro_header_t* header, wulpus_pro_command_t command,
                                     uint16_t length);
/**
 * @brief Check the header pointer, magic bytes, and command ID bounds.
 *
 * @param header Header to inspect; may be NULL.
 * @return true for matching magic and a command inside the enum bounds.
 * @note Does not validate payload length or command-specific payload contents.
 */
bool wulpus_pro_protocol_header_valid(const wulpus_pro_header_t* header);
/**
 * @brief Scan a connected link for a valid header and retain it in the prefetch buffer.
 */
esp_err_t wulpus_pro_protocol_wait_for_header(link_t* link);
/**
 * @brief Read and validate a header, then read its payload within the supplied capacity.
 *
 * @param link Initialized input link.
 * @param header Receives the packet header.
 * @param payload Destination for the payload.
 * @param capacity Payload buffer capacity in bytes.
 * @return ESP_OK, ESP_ERR_INVALID_SIZE for an invalid header/oversized payload, or a read error.
 */
esp_err_t wulpus_pro_protocol_receive(link_t* link, wulpus_pro_header_t* header, void* payload,
                                      size_t capacity);
/**
 * @brief Clear a prefetched header and drain its payload while the link remains connected.
 */
esp_err_t wulpus_pro_protocol_discard_prefetched_payload(link_t* link);
