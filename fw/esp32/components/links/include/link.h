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
 * @file link.h
 * @brief Transport-independent byte transfers and header prefetch state.
 */

#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"
#include "freertos/FreeRTOS.h"

typedef enum { LINK_NONE = 0, LINK_TCP, LINK_USB } link_kind_t;
typedef struct link link_t;

/**
 * @brief Read into a buffer using a transport context, byte capacity, and tick timeout.
 * @return Bytes read, zero when no bytes are available, or a negative value on error.
 */
typedef int (*link_read_fn)(void*, void*, size_t, TickType_t);
/**
 * @brief Write bytes using a transport context, source buffer, byte count, and tick timeout.
 * @return Bytes written, zero on timeout, or a negative value on error.
 */
typedef int (*link_write_fn)(void*, const void*, size_t, TickType_t);
/**
 * @brief Close a transport using its context.
 * @return ESP_OK on success, or a transport error.
 */
typedef esp_err_t (*link_close_fn)(void*);
/**
 * @brief Query connectivity using the transport context.
 * @return true when connected; false otherwise.
 */
typedef bool (*link_connected_fn)(void*);

struct link {
    link_kind_t kind;
    void* context;
    link_read_fn read;
    link_write_fn write;
    link_close_fn close;
    link_connected_fn connected;
    TickType_t timeout;
    uint8_t prefetch[9];
    size_t prefetch_length;
    size_t prefetch_offset;
};

/**
 * @brief Validate required callbacks, set a five-second timeout, and clear prefetch state.
 *
 * @param link Link with read, write, and connected callbacks already assigned.
 * @return ESP_OK on success; ESP_ERR_INVALID_ARG for a null link or missing required callback.
 */
esp_err_t link_init(link_t* link);
/**
 * @brief Read the requested byte count, consuming prefetched bytes first.
 *
 * @param link Initialized link.
 * @param buffer Destination for length bytes.
 * @param length Number of bytes to receive.
 * @note A zero-byte read is retried while connected; there is no overall deadline.
 * @return ESP_OK after all bytes are read; ESP_FAIL on transport failure.
 */
esp_err_t link_read_exact(link_t* link, void* buffer, size_t length);
/**
 * @brief Write the requested byte count, retrying partial writes.
 *
 * @param link Initialized link.
 * @param buffer Source bytes.
 * @param length Number of bytes to write.
 * @return ESP_OK on completion, ESP_ERR_TIMEOUT on a zero-byte write, or ESP_FAIL on error.
 */
esp_err_t link_write_all(link_t* link, const void* buffer, size_t length);
/**
 * @brief Query the transport connection state; return false for a null link.
 */
bool link_is_connected(link_t* link);
/**
 * @brief Clear prefetch state and invoke the optional transport close callback.
 *
 * @param link Non-null initialized link.
 * @return The close callback result, or ESP_OK if no close callback is installed.
 */
esp_err_t link_close(link_t* link);
/**
 * @brief Clear the buffered header length and read offset.
 */
void link_reset_prefetch(link_t* link);
