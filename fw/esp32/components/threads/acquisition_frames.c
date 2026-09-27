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

/** @file acquisition_frames.c
 * @brief Acquisition frame reception, ownership, cleanup, and publication. */

#include "acquisition_internal.h"
#include "board.h"
#include "esp_timer.h"
#include "wulpus_pro_state.h"
#include "wulpus_pro_status.h"

wulpus_pro_frame_slot_t* acquisition_pending_frame;

/** @brief Releases the unpublished pending frame, if one exists. */
static void acquisition_discard_pending(void)
{
    if (acquisition_pending_frame != NULL) {
        wulpus_pro_status_increment_discarded();
        wulpus_pro_frame_pool_release(acquisition_pending_frame);
        acquisition_pending_frame = NULL;
    }
}

/** @brief Stops publication and discards all pending and ready frames. */
void acquisition_quiesce(void)
{
    acquisition_state = ACQ_STATE_QUIESCENT;
    wulpus_pro_state_set_acquiring(false);
    ulTaskNotifyTake(pdTRUE, 0);
    acquisition_discard_pending();
    wulpus_pro_frame_pool_discard_ready();
}

/** @brief Publishes the frame retained before acquisition was enabled. */
void acquisition_publish_pending(void)
{
    if (acquisition_pending_frame != NULL) {
        wulpus_pro_frame_pool_mark_ready(acquisition_pending_frame);
        acquisition_pending_frame = NULL;
        packet_tx_notify_frame_ready();
    }
}

/** @brief Receives, validates, and either publishes or retains one SPI frame. */
void acquisition_receive_frame(void)
{
    if (!wulpus_pro_session_is_current(acquisition_owner) ||
        !link_is_connected(acquisition_owner.link)) {
        acquisition_quiesce();
        return;
    }
    wulpus_pro_frame_slot_t* slot = wulpus_pro_frame_pool_acquire_for_spi(ACQUISITION_BUFFER_WAIT);
    if (slot == NULL) {
        wulpus_pro_status_set_error(WULPUS_PRO_ERROR_ACQ_BUFFER_OVERFLOW);
        wulpus_pro_status_increment_overflow();
        acquisition_quiesce();
        return;
    }
    slot->session_generation = acquisition_owner.generation;
    slot->data_ready_time_us = esp_timer_get_time();
    acquisition_consume_assertion();
    esp_err_t result = board_spi_receive_dma(slot->payload, slot->length);
    slot->spi_complete_time_us = esp_timer_get_time();
    if (result == ESP_OK)
        result = acquisition_wait_transfer_low(NULL);
    if (result == ESP_OK && slot->payload[0] != 0xFF)
        result = ESP_ERR_INVALID_RESPONSE;
    if (result != ESP_OK) {
        acquisition_report_error(result);
        wulpus_pro_frame_pool_release(slot);
        acquisition_quiesce();
        acquisition_configured = false;
        return;
    }
    wulpus_pro_status_increment_spi_complete();
    if (!wulpus_pro_session_is_current(acquisition_owner) ||
        !link_is_connected(acquisition_owner.link)) {
        wulpus_pro_frame_pool_release(slot);
        wulpus_pro_status_increment_discarded();
        acquisition_quiesce();
        return;
    }
    if (acquisition_state == ACQ_STATE_ACQUIRING && wulpus_pro_state_is_acquiring()) {
        wulpus_pro_frame_pool_mark_ready(slot);
        packet_tx_notify_frame_ready();
    } else {
        acquisition_pending_frame = slot;
    }
}
