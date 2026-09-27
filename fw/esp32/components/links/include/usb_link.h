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
 * @file usb_link.h
 * @brief USB Serial/JTAG adapter for the common link interface.
 */

#pragma once
#include "link.h"
/**
 * @brief Install the USB Serial/JTAG driver and initialize its link callbacks.
 */
esp_err_t usb_link_create(link_t* link);
