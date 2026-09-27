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

#ifndef PROVISIONER_H
#define PROVISIONER_H

#include <stdbool.h>
#include <stddef.h>

#include "esp_err.h"
#include "wulpus_pro_persistent_config.h"

typedef enum {
    WULPUS_PRO_WIFI_DISABLED = 0,
    WULPUS_PRO_WIFI_PROVISIONING = 1,
    WULPUS_PRO_WIFI_CONNECTING = 2,
    WULPUS_PRO_WIFI_CONNECTED = 3,
    WULPUS_PRO_WIFI_DISCONNECTED = 4,
    WULPUS_PRO_WIFI_ERROR = 5,
} wulpus_pro_wifi_state_t;

typedef struct __attribute__((packed)) {
    uint8_t version;
    uint8_t size;
    uint8_t state;
    uint8_t credentials_present;
    int8_t rssi;
    uint8_t reserved[3];
    uint8_t ipv4[4];
} wulpus_pro_wifi_status_t;

esp_err_t provisioner_init(void);
esp_err_t provisioner_reset(void);

esp_err_t provisioner_start(bool reset);
esp_err_t provisioner_stop(void);

esp_err_t provisioner_wait(void);

esp_err_t provisioner_twt_setup(void);
esp_err_t provisioner_twt_suspend(int time);
esp_err_t provisioner_wait_connected(void);
esp_err_t provisioner_wait_disconnected(void);
esp_err_t provisioner_get_status(wulpus_pro_wifi_status_t* status);
esp_err_t provisioner_set_credentials(const uint8_t* ssid, size_t ssid_length,
                                      const uint8_t* password, size_t password_length);
esp_err_t provisioner_clear_credentials(void);

#endif
