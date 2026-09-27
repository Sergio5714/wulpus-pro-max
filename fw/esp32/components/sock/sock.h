/*
Copyright (C) 2025 ETH Zurich. All rights reserved.

Author: Cedric Hirschi, ETH Zurich

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

#ifndef SOCK_H
#define SOCK_H

#include <stdint.h>

#include "esp_err.h"

#include "lwip/sockets.h"

typedef struct {
    int fd;

    struct sockaddr_in addr;
    uint16_t addr_len;

    SemaphoreHandle_t mutex;
    TickType_t mutex_timeout;

    bool persist;
} socket_instance_t;

socket_instance_t sock_create(void);

esp_err_t sock_init(socket_instance_t* sock);

esp_err_t sock_listen(socket_instance_t* sock, uint32_t address, uint16_t port);

esp_err_t sock_accept(socket_instance_t* sock, socket_instance_t* client_sock);
esp_err_t sock_close(socket_instance_t* sock);

esp_err_t sock_recv(socket_instance_t* sock, void* buffer, size_t* length);
esp_err_t sock_send(socket_instance_t* sock, const void* buffer, size_t length);

#endif
