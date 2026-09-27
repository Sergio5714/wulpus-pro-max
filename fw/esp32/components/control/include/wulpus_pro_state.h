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
 * @file wulpus_pro_state.h
 * @brief Mutex-protected acquisition and firmware-update state.
 */

#pragma once
#include <stdbool.h>
#include "esp_err.h"
/**
 * @brief Create the mutex protecting acquisition and update flags.
 */
esp_err_t wulpus_pro_state_init(void);
/**
 * @brief Set the acquisition flag under the state mutex.
 */
void wulpus_pro_state_set_acquiring(bool enabled);
/**
 * @brief Return the acquisition flag under the state mutex.
 */
bool wulpus_pro_state_is_acquiring(void);
/**
 * @brief Set the firmware-update flag under the state mutex.
 */
void wulpus_pro_state_set_updating(bool enabled);
/**
 * @brief Return the firmware-update flag under the state mutex.
 */
bool wulpus_pro_state_is_updating(void);
