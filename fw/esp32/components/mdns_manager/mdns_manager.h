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

#ifndef MDNS_MANAGER_H
#define MDNS_MANAGER_H

#include "esp_err.h"

/**
 * @brief Protocol type to use for mDNS service
 *
 */
const typedef enum { MDNS_PROTO_TCP, MDNS_PROTO_UDP } mdns_protocol_t;

esp_err_t mdns_manager_init(char* hostname);
esp_err_t mdns_manager_add(const char* name, mdns_protocol_t protocol, uint16_t port);

#endif
