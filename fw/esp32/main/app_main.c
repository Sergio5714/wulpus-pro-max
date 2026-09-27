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

#include "board.h"
#include "double_reset.h"
#include "esp_log.h"
#include "provisioner.h"
#include "threads.h"
#include "wulpus_pro_frame_pool.h"
#include "wulpus_pro_session.h"
#include "wulpus_pro_state.h"
#include "wulpus_pro_status.h"
#include "msp430_programmer.h"

static const char* TAG = "main";

void app_main(void)
{
    bool reset_provisioning = false;
    ESP_ERROR_CHECK(board_init());
    ESP_ERROR_CHECK(msp430_programmer_init());
    if (msp430_programmer_boot_update_pending()) {
        ESP_LOGI(TAG, "Running pending MSP430 update before normal startup");
        esp_err_t update_result = msp430_programmer_run_boot_update();
        if (update_result == ESP_OK)
            ESP_LOGI(TAG, "MSP430 update completed");
        else
            ESP_LOGE(TAG, "MSP430 update failed: %s", esp_err_to_name(update_result));
    }
#if CONFIG_WP_DOUBLE_RESET
    ESP_ERROR_CHECK(double_reset_start(&reset_provisioning, CONFIG_WP_DOUBLE_RESET_TIMEOUT));
    if (reset_provisioning) {
        ESP_LOGI(TAG, "Double reset detected; provisioning will be reset");
    }
#endif
    ESP_ERROR_CHECK(provisioner_init());
    ESP_ERROR_CHECK(wulpus_pro_frame_pool_init(CONFIG_WP_DATA_RX_LENGTH));
    ESP_ERROR_CHECK(wulpus_pro_status_init());
    ESP_ERROR_CHECK(wulpus_pro_state_init());
    ESP_ERROR_CHECK(wulpus_pro_session_init());
    ESP_ERROR_CHECK(threads_start(reset_provisioning));
    ESP_LOGI(TAG, "WULPUS Pro Max runtime started");
}
