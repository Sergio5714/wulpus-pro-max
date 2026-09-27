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
 * @file wulpus_pro_protocol.c
 * @brief Packet headers, stream synchronization, and payload reception.
 */

#include "wulpus_pro_protocol.h"
#include <string.h>
#include "esp_check.h"

void wulpus_pro_protocol_make_header(wulpus_pro_header_t* header, wulpus_pro_command_t command,
                                     uint16_t length)
{
    memcpy(header->magic, WULPUS_PRO_MAGIC, sizeof(header->magic));
    header->command = command;
    header->data_length = length;
}

bool wulpus_pro_protocol_header_valid(const wulpus_pro_header_t* header)
{
    return header != NULL && memcmp(header->magic, WULPUS_PRO_MAGIC, sizeof(header->magic)) == 0 &&
           header->command > WULPUS_PRO_CMD_ID_BEGIN && header->command < WULPUS_PRO_CMD_ID_END;
}

esp_err_t wulpus_pro_protocol_wait_for_header(link_t* link)
{
    static const uint8_t magic[] = WULPUS_PRO_MAGIC;
    size_t matched = 0;
    link_reset_prefetch(link);
    while (link_is_connected(link)) {
        uint8_t byte;
        int result = link->read(link->context, &byte, 1, pdMS_TO_TICKS(100));
        if (result <= 0)
            continue;
        if (byte == magic[matched]) {
            link->prefetch[matched++] = byte;
        } else {
            matched = byte == magic[0] ? 1 : 0;
            if (matched)
                link->prefetch[0] = byte;
        }
        if (matched == 6) {
            size_t length = 6;
            while (length < WULPUS_PRO_HEADER_SIZE && link_is_connected(link)) {
                result = link->read(link->context, link->prefetch + length,
                                    WULPUS_PRO_HEADER_SIZE - length, pdMS_TO_TICKS(100));
                if (result > 0)
                    length += result;
            }
            if (length != WULPUS_PRO_HEADER_SIZE)
                return ESP_FAIL;
            wulpus_pro_header_t header;
            memcpy(&header, link->prefetch, sizeof(header));
            if (wulpus_pro_protocol_header_valid(&header)) {
                link->prefetch_length = sizeof(header);
                link->prefetch_offset = 0;
                return ESP_OK;
            }
            matched = 0;
            link_reset_prefetch(link);
        }
    }
    return ESP_FAIL;
}

esp_err_t wulpus_pro_protocol_receive(link_t* link, wulpus_pro_header_t* header, void* payload,
                                      size_t capacity)
{
    ESP_RETURN_ON_ERROR(link_read_exact(link, header, sizeof(*header)), "protocol",
                        "header read failed");
    if (!wulpus_pro_protocol_header_valid(header) || header->data_length > capacity)
        return ESP_ERR_INVALID_SIZE;
    if (header->data_length > 0)
        return link_read_exact(link, payload, header->data_length);
    return ESP_OK;
}

esp_err_t wulpus_pro_protocol_discard_prefetched_payload(link_t* link)
{
    wulpus_pro_header_t header;
    memcpy(&header, link->prefetch, sizeof(header));
    link_reset_prefetch(link);
    uint8_t discard[64];
    size_t remaining = header.data_length;
    while (remaining > 0 && link_is_connected(link)) {
        size_t requested = remaining < sizeof(discard) ? remaining : sizeof(discard);
        int result = link->read(link->context, discard, requested, link->timeout);
        if (result <= 0)
            return ESP_FAIL;
        remaining -= result;
    }
    return ESP_OK;
}
