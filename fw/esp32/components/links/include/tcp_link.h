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
 * @file tcp_link.h
 * @brief TCP server adapter for the common link interface.
 */

#pragma once
#include "link.h"
#include "sock.h"
typedef struct {
    socket_instance_t listener;
    socket_instance_t client;
} tcp_link_server_t;
/**
 * @brief Create listener/client socket state and listen on all IPv4 interfaces.
 */
esp_err_t tcp_link_server_init(tcp_link_server_t* server, uint16_t port);
/**
 * @brief Accept a client and initialize a link backed by the server's client socket.
 */
esp_err_t tcp_link_accept(tcp_link_server_t* server, link_t* link);
