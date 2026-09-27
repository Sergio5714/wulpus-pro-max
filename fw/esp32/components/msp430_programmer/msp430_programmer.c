/* Copyright (C) 2026 Sergei Vostrikov, SPDX-License-Identifier: Apache-2.0 */

/**
 * @file msp430_programmer.c
 * @brief Staged MSP430 firmware reception, persistent update state, and boot programming.
 */

#include "msp430_programmer.h"
#include <stddef.h>
#include <string.h>
#include "board.h"
#include "esp_partition.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "nvs.h"
#include "sdkconfig.h"
#include "msp430_image.h"
#include "msp430_jtag.h"
#include "wulpus_pro_state.h"

static SemaphoreHandle_t lock;
static TaskHandle_t worker;
static const esp_partition_t* partition;
static msp430_update_status_t status;
static msp430_diagnostics_t diagnostics;
static uint32_t expected_crc;
static bool cancel_requested;
static bool persisted_verifying;

#define MSP_NVS_NAMESPACE "wulpus_pro"
#define MSP_NVS_KEY "msp_update"
#define MSP_DIAG_NVS_KEY "msp_diag"
#define MSP_PERSIST_MAGIC 0x3155504dU /* MPU1 */
#define MSP_PERSIST_VERSION 1

typedef struct __attribute__((packed)) {
    uint32_t magic;
    uint16_t version;
    uint16_t size;
    msp430_update_status_t status;
    uint32_t image_crc32;
    uint32_t record_crc32;
} msp430_persistent_record_t;

/**
 * @brief Calculate the persistent update record CRC, excluding its CRC field.
 */
static uint32_t record_crc(const msp430_persistent_record_t* record)
{
    return msp430_crc32(0, record, offsetof(msp430_persistent_record_t, record_crc32));
}

/**
 * @brief Commit update status and expected image CRC to NVS with a record CRC.
 */
static esp_err_t persist_status(void)
{
    msp430_persistent_record_t record = {
        .magic = MSP_PERSIST_MAGIC,
        .version = MSP_PERSIST_VERSION,
        .size = sizeof(record),
        .status = status,
        .image_crc32 = expected_crc,
    };
    record.record_crc32 = record_crc(&record);
    nvs_handle_t handle = 0;
    esp_err_t result = nvs_open(MSP_NVS_NAMESPACE, NVS_READWRITE, &handle);
    if (result == ESP_OK)
        result = nvs_set_blob(handle, MSP_NVS_KEY, &record, sizeof(record));
    if (result == ESP_OK)
        result = nvs_commit(handle);
    if (handle)
        nvs_close(handle);
    return result;
}

/**
 * @brief Restore update status and expected CRC from a valid NVS record.
 */
static bool load_status(void)
{
    msp430_persistent_record_t record;
    size_t size = sizeof(record);
    nvs_handle_t handle = 0;
    esp_err_t result = nvs_open(MSP_NVS_NAMESPACE, NVS_READONLY, &handle);
    if (result == ESP_OK)
        result = nvs_get_blob(handle, MSP_NVS_KEY, &record, &size);
    if (handle)
        nvs_close(handle);
    if (result != ESP_OK || size != sizeof(record) || record.magic != MSP_PERSIST_MAGIC ||
        record.version != MSP_PERSIST_VERSION || record.size != sizeof(record) ||
        record.record_crc32 != record_crc(&record))
        return false;
    status = record.status;
    expected_crc = record.image_crc32;
    return true;
}

/**
 * @brief Commit the current MSP430 diagnostics to NVS.
 */
static esp_err_t persist_diagnostics(void)
{
    nvs_handle_t handle = 0;
    esp_err_t result = nvs_open(MSP_NVS_NAMESPACE, NVS_READWRITE, &handle);
    if (result == ESP_OK)
        result = nvs_set_blob(handle, MSP_DIAG_NVS_KEY, &diagnostics, sizeof(diagnostics));
    if (result == ESP_OK)
        result = nvs_commit(handle);
    if (handle)
        nvs_close(handle);
    return result;
}

/**
 * @brief Load diagnostics from NVS or initialize an empty versioned record.
 */
static void load_diagnostics(void)
{
    size_t size = sizeof(diagnostics);
    nvs_handle_t handle = 0;
    esp_err_t result = nvs_open(MSP_NVS_NAMESPACE, NVS_READONLY, &handle);
    if (result == ESP_OK)
        result = nvs_get_blob(handle, MSP_DIAG_NVS_KEY, &diagnostics, &size);
    if (handle)
        nvs_close(handle);
    if (result != ESP_OK || size != sizeof(diagnostics) ||
        diagnostics.version != MSP430_DIAGNOSTICS_VERSION) {
        memset(&diagnostics, 0, sizeof(diagnostics));
        diagnostics.version = MSP430_DIAGNOSTICS_VERSION;
    }
}

/**
 * @brief Mark the firmware update as failed and store its error under the update mutex.
 */
static void fail(esp_err_t error)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    status.state = MSP430_UPDATE_FAILED;
    status.error = error;
    xSemaphoreGive(lock);
}

/**
 * @brief Update programming progress, persist the first verification transition, and check
 * cancellation.
 */
static esp_err_t progress(uint32_t address, uint32_t done, bool verifying, void* arg)
{
    (void)arg;
    xSemaphoreTake(lock, portMAX_DELAY);
    status.current_address = address;
    status.processed_bytes = done;
    status.state = verifying ? MSP430_UPDATE_VERIFYING : MSP430_UPDATE_PROGRAMMING;
    bool cancel = cancel_requested;
    xSemaphoreGive(lock);
    if (verifying && !persisted_verifying) {
        persisted_verifying = true;
        esp_err_t result = persist_status();
        if (result != ESP_OK)
            return result;
    }
    /* Keep the USB/TCP protocol responsive during the CPU-heavy bit-bang. */
    vTaskDelay(1);
    return cancel ? ESP_ERR_INVALID_STATE : ESP_OK;
}

/**
 * @brief Verify the staged file CRC and open its validated image structure.
 */
static esp_err_t validate(msp430_image_t* image)
{
    uint8_t buffer[512];
    uint32_t crc = 0;
    for (uint32_t offset = 0; offset < status.total_bytes;) {
        size_t count = status.total_bytes - offset;
        if (count > sizeof(buffer))
            count = sizeof(buffer);
        esp_err_t err = esp_partition_read(partition, offset, buffer, count);
        if (err != ESP_OK)
            return err;
        crc = msp430_crc32(crc, buffer, count);
        offset += count;
    }
    if (crc != expected_crc)
        return ESP_ERR_INVALID_CRC;
    return msp430_image_open(partition, status.total_bytes, image);
}

/**
 * @brief Wait 250 milliseconds for the commit acknowledgement, then restart the ESP32.
 */
static void reboot_task(void* arg)
{
    (void)arg;
    /* Let the COMMIT acknowledgement leave the USB/TCP TX queue first. */
    vTaskDelay(pdMS_TO_TICKS(250));
    esp_restart();
}

esp_err_t msp430_programmer_init(void)
{
    lock = xSemaphoreCreateMutex();
    partition = esp_partition_find_first(ESP_PARTITION_TYPE_DATA, 0x40, "msp_image");
    memset(&status, 0, sizeof(status));
    status.version = MSP430_UPDATE_STATUS_VERSION;
    load_diagnostics();
    if (!lock || !partition)
        return ESP_ERR_NOT_FOUND;
    if (load_status() && !(status.flags & MSP430_UPDATE_FLAG_BOOT_PENDING) &&
        status.state >= MSP430_UPDATE_VALIDATING &&
        status.state <= MSP430_UPDATE_WAITING_FOR_BOOT) {
        status.state = MSP430_UPDATE_FAILED;
        status.error = ESP_ERR_INVALID_STATE;
        (void)persist_status();
    }
    return ESP_OK;
}

bool msp430_programmer_boot_update_pending(void)
{
    return (status.flags & MSP430_UPDATE_FLAG_BOOT_PENDING) != 0;
}

esp_err_t msp430_programmer_run_boot_update(void)
{
    if (!msp430_programmer_boot_update_pending())
        return ESP_ERR_INVALID_STATE;
    /* Keep the target inactive while the staged image is being validated. */
    esp_err_t reset_result = board_msp_reset(true);
    status.flags &= ~MSP430_UPDATE_FLAG_BOOT_PENDING;
    status.state = MSP430_UPDATE_VALIDATING;
    status.processed_bytes = 0;
    status.current_address = 0;
    status.target_device_id = 0;
    status.error = ESP_OK;
    memset(&diagnostics, 0, sizeof(diagnostics));
    diagnostics.version = MSP430_DIAGNOSTICS_VERSION;
    esp_err_t result = reset_result == ESP_OK ? persist_status() : reset_result;
    msp430_image_t image;
    if (result == ESP_OK)
        result = validate(&image);
    if (result == ESP_OK) {
        status.state = MSP430_UPDATE_PROGRAMMING;
        result = persist_status();
    }
    uint32_t device_id = 0;
    persisted_verifying = false;
    if (result == ESP_OK)
        result = msp430_jtag_program(&image, progress, NULL, &device_id, &diagnostics);
    msp430_jtag_release();
    (void)board_msp_reset(false);
    status.target_device_id = device_id;
    status.state = result == ESP_OK ? MSP430_UPDATE_COMPLETE : MSP430_UPDATE_FAILED;
    status.error = result;
    esp_err_t persist_result = persist_status();
    (void)persist_diagnostics();
    return result != ESP_OK ? result : persist_result;
}

esp_err_t msp430_programmer_begin(uint32_t size, uint32_t crc)
{
    if (!lock || !partition || !size || size > partition->size || wulpus_pro_state_is_acquiring() ||
        wulpus_pro_state_is_updating())
        return ESP_ERR_INVALID_ARG;
    xSemaphoreTake(lock, portMAX_DELAY);
    if (worker || status.state == MSP430_UPDATE_RECEIVING) {
        xSemaphoreGive(lock);
        return ESP_ERR_INVALID_STATE;
    }
    memset(&status, 0, sizeof(status));
    status.version = MSP430_UPDATE_STATUS_VERSION;
    status.state = MSP430_UPDATE_RECEIVING;
    status.total_bytes = size;
    expected_crc = crc;
    cancel_requested = false;
    xSemaphoreGive(lock);
    esp_err_t err = esp_partition_erase_range(
        partition, 0, (size + partition->erase_size - 1) & ~(partition->erase_size - 1));
    if (err != ESP_OK)
        fail(err);
    return err;
}

esp_err_t msp430_programmer_write(uint32_t offset, const void* data, size_t length)
{
    if (!data || !length)
        return ESP_ERR_INVALID_ARG;
    xSemaphoreTake(lock, portMAX_DELAY);
    bool valid = status.state == MSP430_UPDATE_RECEIVING && offset == status.received_bytes &&
                 offset + length <= status.total_bytes;
    xSemaphoreGive(lock);
    if (!valid)
        return ESP_ERR_INVALID_STATE;
    esp_err_t err = esp_partition_write(partition, offset, data, length);
    xSemaphoreTake(lock, portMAX_DELAY);
    if (err == ESP_OK) {
        status.received_bytes += length;
        if (status.received_bytes == status.total_bytes)
            status.state = MSP430_UPDATE_READY;
    } else {
        status.state = MSP430_UPDATE_FAILED;
        status.error = err;
    }
    xSemaphoreGive(lock);
    return err;
}

esp_err_t msp430_programmer_commit(void)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    if (status.state != MSP430_UPDATE_READY || worker) {
        xSemaphoreGive(lock);
        return ESP_ERR_INVALID_STATE;
    }
    status.flags |= MSP430_UPDATE_FLAG_BOOT_PENDING;
    status.state = MSP430_UPDATE_READY;
    wulpus_pro_state_set_updating(true);
    esp_err_t saved = persist_status();
    if (saved != ESP_OK) {
        status.flags &= ~MSP430_UPDATE_FLAG_BOOT_PENDING;
        status.state = MSP430_UPDATE_FAILED;
        status.error = saved;
        wulpus_pro_state_set_updating(false);
        xSemaphoreGive(lock);
        return saved;
    }
    BaseType_t ok =
        xTaskCreate(reboot_task, "msp430_reboot", 2048, NULL, CONFIG_WP_HANDLER_PRIORITY, &worker);
    if (ok != pdPASS) {
        worker = NULL;
        status.flags &= ~MSP430_UPDATE_FLAG_BOOT_PENDING;
        status.state = MSP430_UPDATE_FAILED;
        status.error = ESP_ERR_NO_MEM;
        (void)persist_status();
        wulpus_pro_state_set_updating(false);
    }
    xSemaphoreGive(lock);
    return ok == pdPASS ? ESP_OK : ESP_ERR_NO_MEM;
}

esp_err_t msp430_programmer_abort(void)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    cancel_requested = true;
    if (!worker)
        status.state = MSP430_UPDATE_ABORTED;
    xSemaphoreGive(lock);
    return ESP_OK;
}

void msp430_programmer_get_status(msp430_update_status_t* out)
{
    if (!out)
        return;
    xSemaphoreTake(lock, portMAX_DELAY);
    *out = status;
    xSemaphoreGive(lock);
}

void msp430_programmer_get_diagnostics(msp430_diagnostics_t* out)
{
    if (!out)
        return;
    xSemaphoreTake(lock, portMAX_DELAY);
    *out = diagnostics;
    xSemaphoreGive(lock);
}
