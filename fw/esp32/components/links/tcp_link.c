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
 * @file tcp_link.c
 * @brief TCP server adapter for the common link interface.
 */

#include "tcp_link.h"

/**
 * @brief Receive socket bytes; the callback timeout argument is unused.
 */
static int read_bytes(void* context, void* buffer, size_t length, TickType_t timeout)
{
    (void)timeout;
    size_t received = length;
    return sock_recv(context, buffer, &received) == ESP_OK ? (int)received : -1;
}
/**
 * @brief Send all socket bytes; the callback timeout argument is unused.
 */
static int write_bytes(void* context, const void* buffer, size_t length, TickType_t timeout)
{
    (void)timeout;
    return sock_send(context, buffer, length) == ESP_OK ? (int)length : -1;
}
/**
 * @brief Close the socket backing the link.
 */
static esp_err_t close_link(void* context)
{
    return sock_close(context);
}
/**
 * @brief Return whether the client socket descriptor is nonnegative.
 */
static bool connected(void* context)
{
    return ((socket_instance_t*)context)->fd >= 0;
}

esp_err_t tcp_link_server_init(tcp_link_server_t* server, uint16_t port)
{
    server->listener = sock_create();
    server->client = sock_create();
    if (server->listener.mutex == NULL || server->client.mutex == NULL)
        return ESP_ERR_NO_MEM;
    esp_err_t result = sock_init(&server->listener);
    if (result == ESP_OK)
        result = sock_listen(&server->listener, INADDR_ANY, port);
    return result;
}

esp_err_t tcp_link_accept(tcp_link_server_t* server, link_t* link)
{
    esp_err_t result = sock_accept(&server->listener, &server->client);
    if (result != ESP_OK)
        return result;
    *link = (link_t){.kind = LINK_TCP,
                     .context = &server->client,
                     .read = read_bytes,
                     .write = write_bytes,
                     .close = close_link,
                     .connected = connected};
    return link_init(link);
}
