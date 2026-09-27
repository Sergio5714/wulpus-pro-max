/*
 * Copyright (C) 2026 Sergei Vostrikov
 * SPDX-License-Identifier: Apache-2.0
 *
 * ESP32-C6 4-wire GPIO port of TI SLAU320AJ's MSP430Xv2 FRAM Replicator.
 * Included TI code and RAM funclets retain their BSD-3-Clause notices.
 */

/**
 * @file msp430_jtag.c
 * @brief ESP32 GPIO implementation of MSP430 four-wire JTAG programming.
 */

#include "msp430_jtag.h"
#include <string.h>
#include "board.h"
#include "driver/gpio.h"
#include "esp_rom_sys.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"
#include "ti/LowLevelFunc430Xv2.h"

#define MSP430FR5043_DEVICE_ID 0x8317U
#define MSP430FR5043_DEVICE_ID_ADDRESS 0x1A04U

static portMUX_TYPE jtag_mux = portMUX_INITIALIZER_UNLOCKED;
static bool pins_driven;
static int tdi_level = 1;
/**
 * @brief Set the output level of a GPIO pin.
 */
static inline void pin(gpio_num_t number, int level)
{
    gpio_set_level(number, level);
}
/**
 * @brief Set the JTAG TMS output level.
 */
void msp_ll_set_tms(int level)
{
    pin(CONFIG_WP_GPIO_MSP_TMS, level);
}
/**
 * @brief Set and remember the TDI level, then wait one microsecond for setup.
 */
void msp_ll_set_tdi(int level)
{
    tdi_level = !!level;
    pin(CONFIG_WP_GPIO_MSP_TDI, tdi_level);
    esp_rom_delay_us(1); /* TDI/TMS-to-TCK setup margin. */
}
/**
 * @brief Set the JTAG clock level and wait two microseconds.
 */
void msp_ll_set_tck(int level)
{
    pin(CONFIG_WP_GPIO_MSP_TCK, level);
    esp_rom_delay_us(2); /* Explicit high and low phase duration. */
}
/**
 * @brief Drive TCLK on the TDI pin and wait two microseconds.
 */
void msp_ll_set_tclk(int level)
{
    tdi_level = !!level;
    pin(CONFIG_WP_GPIO_MSP_TDI, tdi_level);
    esp_rom_delay_us(2); /* TCLK is carried on TDI in four-wire JTAG. */
}
/**
 * @brief Restore the saved TCLK level on TDI and wait one microsecond.
 */
void msp_ll_restore_tclk(int level)
{
    tdi_level = !!level;
    pin(CONFIG_WP_GPIO_MSP_TDI, tdi_level);
    esp_rom_delay_us(1);
}
/**
 * @brief Set the MSP430 TEST output level.
 */
void msp_ll_set_test(int level)
{
    pin(CONFIG_WP_GPIO_MSP_TEST, level);
}
/**
 * @brief Set the physical level of the active-low MSP430 reset pin.
 */
void msp_ll_set_reset(int level)
{
    pin(CONFIG_WP_GPIO_MSP_RST_N, level);
}
/**
 * @brief Return the current JTAG TDO input level.
 */
int msp_ll_get_tdo(void)
{
    return gpio_get_level(CONFIG_WP_GPIO_MSP_TDO);
}
/**
 * @brief Return the last level recorded for the shared TDI/TCLK output.
 */
int msp_ll_tdi_level(void)
{
    return tdi_level;
}

/**
 * @brief Configure TDO as input and TEST, TDI, TMS, and TCK as driven outputs.
 */
void msp_ll_drive(void)
{
    gpio_config_t input = {.pin_bit_mask = 1ULL << CONFIG_WP_GPIO_MSP_TDO,
                           .mode = GPIO_MODE_INPUT,
                           .intr_type = GPIO_INTR_DISABLE};
    gpio_config(&input);
    msp_ll_set_tdi(1);
    msp_ll_set_tms(1);
    msp_ll_set_tck(1);
    msp_ll_set_test(0);
    msp_ll_set_reset(1);
    gpio_config_t output = {
        .pin_bit_mask = (1ULL << CONFIG_WP_GPIO_MSP_TEST) | (1ULL << CONFIG_WP_GPIO_MSP_TDI) |
                        (1ULL << CONFIG_WP_GPIO_MSP_TMS) | (1ULL << CONFIG_WP_GPIO_MSP_TCK),
        .mode = GPIO_MODE_OUTPUT,
        .intr_type = GPIO_INTR_DISABLE};
    gpio_config(&output);
    pins_driven = true;
}

/**
 * @brief Return the TEST, TDO, TDI, TMS, and TCK pins to input mode.
 */
void msp_ll_release(void)
{
    gpio_config_t released = {
        .pin_bit_mask = (1ULL << CONFIG_WP_GPIO_MSP_TEST) | (1ULL << CONFIG_WP_GPIO_MSP_TDO) |
                        (1ULL << CONFIG_WP_GPIO_MSP_TDI) | (1ULL << CONFIG_WP_GPIO_MSP_TMS) |
                        (1ULL << CONFIG_WP_GPIO_MSP_TCK),
        .mode = GPIO_MODE_INPUT,
        .intr_type = GPIO_INTR_DISABLE};
    gpio_config(&released);
    pins_driven = false;
}

/**
 * @brief Delay the calling task for the supplied millisecond duration converted to ticks.
 */
void MsDelay(word milliseconds)
{
    vTaskDelay(pdMS_TO_TICKS(milliseconds));
}
/**
 * @brief Busy-wait for the supplied number of microseconds.
 */
void usDelay(word microseconds)
{
    esp_rom_delay_us(microseconds);
}

/**
 * @brief Shift JTAG data most-significant bit first and return sampled TDO bits.
 */
unsigned long AllShifts(word format, unsigned long data)
{
    uint32_t msb;
    switch (format) {
    case F_BYTE:
        msb = 0x80;
        break;
    case F_WORD:
        msb = 0x8000;
        break;
    case F_ADDR:
        msb = 0x80000;
        break;
    case F_LONG:
        msb = 0x80000000;
        break;
    default:
        return 0;
    }
    int saved_tclk = tdi_level;
    uint32_t out = 0;
    portENTER_CRITICAL(&jtag_mux);
    for (word remaining = format; remaining; --remaining) {
        msp_ll_set_tdi((data & msb) != 0);
        data <<= 1;
        if (remaining == 1)
            msp_ll_set_tms(1);
        msp_ll_set_tck(0);
        msp_ll_set_tck(1);
        /* TI's four-wire reference samples TDO after the rising TCK edge. */
        out = (out << 1) | (uint32_t)msp_ll_get_tdo();
    }
    msp_ll_set_tdi(saved_tclk);
    msp_ll_set_tck(0);
    msp_ll_set_tck(1);
    msp_ll_set_tms(0);
    msp_ll_set_tck(0);
    msp_ll_set_tck(1);
    portEXIT_CRITICAL(&jtag_mux);
    /* TI applies the 20-bit TDO de-scrambling rotation only to Spy-Bi-Wire.
     * Standard four-wire JTAG returns the address bits in their natural order. */
    return out;
}

#include "ti/JTAGfunc430FR.c"

esp_err_t msp430_jtag_program(const msp430_image_t* image, msp430_jtag_progress_fn progress,
                              void* context, uint32_t* device_id, msp430_diagnostics_t* diagnostics)
{
    if (!image)
        return ESP_ERR_INVALID_ARG;
    esp_err_t result = board_usb_no_sleep_acquire();
    if (result != ESP_OK)
        return result;
    bool connected = false;
    uint16_t words[128];
    if (diagnostics) {
        memset(diagnostics, 0, sizeof(*diagnostics));
        diagnostics->version = MSP430_DIAGNOSTICS_VERSION;
        diagnostics->stage = MSP430_DIAG_JTAG_ENTRY;
    }
    msp_ll_drive();
    word access = GetDevice_430Xv2();
    if (access == STATUS_FUSEBLOWN) {
        result = ESP_ERR_NOT_ALLOWED;
        goto done;
    }
    if (access != STATUS_OK) {
        result = ESP_ERR_NOT_FOUND;
        goto done;
    }
    connected = true;
    if (diagnostics) {
        diagnostics->jtag_id = IR_Shift(IR_CNTRL_SIG_CAPTURE);
        diagnostics->control_signal = DR_Shift16(0);
        diagnostics->core_id = CoreId;
        diagnostics->descriptor_pointer = DeviceIdPointer;
        diagnostics->quick_device_id = DeviceId;
        diagnostics->stage = MSP430_DIAG_DEVICE_MEMORY_READ;
    }
    /* The diagnostic capture above changes the selected JTAG register. Restore
     * the same synchronized full-emulation state before the independent read. */
    if (SyncJtag_AssertPor() != STATUS_OK) {
        result = ESP_ERR_INVALID_STATE;
        goto done;
    }
    /* This product has one fixed target. Read its documented descriptor word
     * directly instead of trusting the 20-bit pointer returned by IR_DEVICE_ID;
     * that pointer remains useful to generic gang programmers but adds another
     * failure mode to a fixed-device application. */
    word fixed_device_id = 0;
    ReadMemQuick_430Xv2(MSP430FR5043_DEVICE_ID_ADDRESS, 1, &fixed_device_id);
    word direct_device_id = ReadMem_430Xv2(F_WORD, MSP430FR5043_DEVICE_ID_ADDRESS);
    DeviceId = fixed_device_id;
    if (diagnostics) {
        diagnostics->quick_device_id = fixed_device_id;
        diagnostics->direct_device_id = direct_device_id;
    }
    if (device_id)
        *device_id = DeviceId;
    if (DeviceId != MSP430FR5043_DEVICE_ID) {
        /* On identification failure expose TI's raw 20-bit descriptor pointer
         * through current_address without writing any target memory. */
        if (progress)
            (void)progress(DeviceIdPointer, 0, false, context);
        result = ESP_ERR_NOT_SUPPORTED;
        goto done;
    }
    if (diagnostics)
        diagnostics->stage = MSP430_DIAG_DEVICE_VALIDATED;
    if (DisableMpu_430Xv2() != STATUS_OK || DisableFramWprod_430Xv2() != STATUS_OK) {
        result = ESP_ERR_INVALID_STATE;
        goto done;
    }
    uint32_t processed = 0;
    for (unsigned section = 0; section < image->header.section_count; ++section) {
        const msp430_image_section_t* s = &image->sections[section];
        for (uint32_t offset = 0; offset < s->length;) {
            size_t bytes = s->length - offset;
            if (bytes > sizeof(words))
                bytes = sizeof(words);
            result = msp430_image_read(image, section, offset, words, bytes);
            if (result != ESP_OK)
                goto done;
            WriteMemQuick_430Xv2(s->address + offset, bytes / 2, words);
            offset += bytes;
            processed += bytes;
            if (progress &&
                (result = progress(s->address + offset, processed, false, context)) != ESP_OK)
                goto done;
        }
    }
    if (progress && (result = progress(0, 0, true, context)) != ESP_OK)
        goto done;
    processed = 0;
    for (unsigned section = 0; section < image->header.section_count; ++section) {
        const msp430_image_section_t* s = &image->sections[section];
        for (uint32_t offset = 0; offset < s->length;) {
            size_t bytes = s->length - offset;
            if (bytes > sizeof(words))
                bytes = sizeof(words);
            result = msp430_image_read(image, section, offset, words, bytes);
            if (result != ESP_OK)
                goto done;
            if (VerifyMem_430Xv2(s->address + offset, bytes / 2, words) != STATUS_OK) {
                result = ESP_ERR_INVALID_RESPONSE;
                goto done;
            }
            offset += bytes;
            processed += bytes;
            if (progress &&
                (result = progress(s->address + offset, processed, true, context)) != ESP_OK)
                goto done;
        }
    }
    result = ESP_OK;
done:
    if (connected)
        ReleaseDevice_430Xv2(V_RESET);
    msp_ll_release();
    board_usb_no_sleep_release();
    return result;
}

void msp430_jtag_release(void)
{
    if (pins_driven)
        msp_ll_release();
}
