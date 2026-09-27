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
 * @file board.h
 * @brief Board GPIO, SPI, and USB light-sleep control.
 */

#pragma once

#include <stdbool.h>
#include <stddef.h>

#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_err.h"

/**
 * @brief Initialize the BSP, reset/data-ready GPIOs, SPI bus, and power management.
 *
 * @note Leaves MSP reset asserted. Call once before using the board services.
 * @return ESP_OK on success, or the first initialization error.
 */
esp_err_t board_init(void);
/**
 * @brief Assert or release the active-low MSP430 reset signal.
 *
 * @param asserted true to hold the MSP430 in reset; false to release it.
 * @pre The reset GPIO has been configured by board_init().
 * @return The result of gpio_set_level().
 */
esp_err_t board_msp_reset(bool asserted);
/**
 * @brief Read whether the MSP430 DATA_READY input is high.
 *
 * @return true when DATA_READY is high; false when it is low.
 */
bool board_data_ready(void);
/**
 * @brief Register a callback for rising edges on DATA_READY.
 *
 * @param handler Callback invoked in GPIO interrupt context.
 * @param argument User argument passed to the callback.
 * @pre board_init() has configured DATA_READY for rising-edge interrupts.
 * @return ESP_OK on success, or a GPIO ISR service/registration error.
 */
esp_err_t board_data_ready_set_isr(gpio_isr_t handler, void* argument);

/**
 * @brief Receive bytes from the MSP430 using the DMA-enabled SPI bus.
 *
 * @param buffer Writable receive storage.
 * @param length Transfer length in bytes.
 * @pre board_init() has completed successfully; storage must remain valid until return.
 * @note Waits up to one second for the SPI mutex, then waits for transaction completion.
 * @return ESP_OK on success, ESP_ERR_TIMEOUT for mutex contention, or a SPI driver error.
 */
esp_err_t board_spi_receive_dma(void* buffer, size_t length);
/**
 * @brief Transmit bytes to the MSP430 and wait for completion.
 *
 * @param buffer Bytes to transmit.
 * @param length Transfer length in bytes.
 * @pre board_init() has completed successfully; storage must remain valid until return.
 * @note Waits up to one second for the SPI mutex, then waits for transaction completion.
 * @return ESP_OK on success, ESP_ERR_TIMEOUT for mutex contention, or a SPI driver error.
 */
esp_err_t board_spi_transmit(const void* buffer, size_t length);
/**
 * @brief Simultaneously transmit to and receive from the MSP430.
 *
 * @param tx_buffer Bytes
 * to transmit.
 * @param rx_buffer Writable receive storage.
 * @param length Transfer length in
 * bytes for both buffers.
 * @return ESP_OK on success, ESP_ERR_TIMEOUT for mutex contention, or a
 * SPI driver error.
 */
esp_err_t board_spi_transceive(const void* tx_buffer, void* rx_buffer, size_t length);

/**
 * @brief Hold the USB light-sleep and CPU-frequency locks if not already held.
 *
 * @note Calls do not nest. With CONFIG_WP_ENABLE_PM disabled, this is a no-op.
 * @return ESP_OK if no change is needed or the operation succeeds; otherwise a PM error.
 */
esp_err_t board_usb_no_sleep_acquire(void);
/**
 * @brief Release the USB light-sleep and CPU-frequency locks if held.
 *
 * @note Calls do not nest. With CONFIG_WP_ENABLE_PM disabled, this is a no-op.
 * @return ESP_OK if no change is needed or the operation succeeds; otherwise a PM error.
 */
esp_err_t board_usb_no_sleep_release(void);
