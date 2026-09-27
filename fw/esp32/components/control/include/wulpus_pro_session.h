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
 * @file wulpus_pro_session.h
 * @brief Active transport session ownership and generation tracking.
 */

#pragma once
#include <stdint.h>
#include "esp_err.h"
#include "link.h"
typedef struct {
    link_t* link;
    uint32_t generation;
    link_kind_t kind;
} wulpus_pro_session_ref_t;
/**
 * @brief Create the mutex protecting the active session.
 */
esp_err_t wulpus_pro_session_init(void);
/**
 * @brief Claim an idle session and assign a new nonzero generation.
 *
 * @param link Link to claim; must remain valid until session release.
 * @param session Receives the claimed reference only on success.
 * @return true if claimed; false if a session is already active.
 */
bool wulpus_pro_session_try_claim(link_t* link, wulpus_pro_session_ref_t* session);
/**
 * @brief Release the active session only when its link and generation match.
 */
void wulpus_pro_session_release(wulpus_pro_session_ref_t session);
/**
 * @brief Return a mutex-protected copy of the current session reference.
 */
wulpus_pro_session_ref_t wulpus_pro_session_current(void);
/**
 * @brief Compare a reference's link and generation with the current session.
 */
bool wulpus_pro_session_is_current(wulpus_pro_session_ref_t session);
