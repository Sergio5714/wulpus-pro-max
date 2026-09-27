/**
 * @file msp430_jtag.h
 * @brief ESP32 GPIO implementation of MSP430 four-wire JTAG programming.
 */
#pragma once
#include <stdbool.h>
#include "esp_err.h"
#include "msp430_image.h"
#include "msp430_programmer.h"
/**
 * @brief Report address, processed byte count, verification phase, and caller context.
 * @return ESP_OK to continue; any other result stops normal programming/verification.
 */
typedef esp_err_t (*msp430_jtag_progress_fn)(uint32_t, uint32_t, bool, void*);
/**
 * @brief Identify the MSP430FR5043, write image sections, and verify them over four-wire JTAG.
 */
esp_err_t msp430_jtag_program(const msp430_image_t*, msp430_jtag_progress_fn, void*, uint32_t*,
                              msp430_diagnostics_t*);
/**
 * @brief Release the JTAG signal pins if they are currently driven.
 */
void msp430_jtag_release(void);
