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
 * @file link.c
 * @brief Transport-independent byte transfers and header prefetch state.
 */

#include "link.h"

esp_err_t link_init(link_t* link)
{
    if (link == NULL || link->read == NULL || link->write == NULL || link->connected == NULL)
        return ESP_ERR_INVALID_ARG;
    link->timeout = pdMS_TO_TICKS(5000);
    link_reset_prefetch(link);
    return ESP_OK;
}

void link_reset_prefetch(link_t* link)
{
    link->prefetch_length = 0;
    link->prefetch_offset = 0;
}

esp_err_t link_read_exact(link_t* link, void* buffer, size_t length)
{
    uint8_t* destination = buffer;
    size_t received = 0;
    while (received < length && link->prefetch_offset < link->prefetch_length) {
        destination[received++] = link->prefetch[link->prefetch_offset++];
    }
    if (link->prefetch_offset == link->prefetch_length)
        link_reset_prefetch(link);
    while (received < length) {
        int result =
            link->read(link->context, destination + received, length - received, link->timeout);
        if (result == 0 && link_is_connected(link))
            continue;
        if (result <= 0)
            return ESP_FAIL;
        received += result;
    }
    return ESP_OK;
}

esp_err_t link_write_all(link_t* link, const void* buffer, size_t length)
{
    const uint8_t* source = buffer;
    size_t written = 0;
    while (written < length) {
        int result = link->write(link->context, source + written, length - written, link->timeout);
        if (result <= 0)
            return result == 0 ? ESP_ERR_TIMEOUT : ESP_FAIL;
        written += result;
    }
    return ESP_OK;
}

bool link_is_connected(link_t* link)
{
    return link != NULL && link->connected(link->context);
}
esp_err_t link_close(link_t* link)
{
    link_reset_prefetch(link);
    return link != NULL && link->close ? link->close(link->context) : ESP_OK;
}
