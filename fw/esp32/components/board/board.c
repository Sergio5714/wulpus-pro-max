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
 * @file board.c
 * @brief Board GPIO, SPI, and USB light-sleep control.
 */

#include "board.h"

#include "bsp.h"
#include "esp_check.h"
#include "esp_pm.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

static spi_device_handle_t spi_device;
static SemaphoreHandle_t spi_mutex;
#if CONFIG_WP_ENABLE_PM
static esp_pm_lock_handle_t usb_sleep_lock;
/* The C6 USB path corrupted command bytes and reported transient disconnects
 * with DFS down to 10 MHz. Keep CPU/APB clocks stable while USB is attached. */
static esp_pm_lock_handle_t usb_frequency_lock;
static bool usb_sleep_lock_held;
#endif

esp_err_t board_msp_reset(bool asserted)
{
    return gpio_set_level(CONFIG_WP_GPIO_MSP_RST_N, asserted ? 0 : 1);
}

bool board_data_ready(void)
{
    return gpio_get_level(CONFIG_WP_GPIO_DATA_READY) != 0;
}

esp_err_t board_data_ready_set_isr(gpio_isr_t handler, void* argument)
{
    esp_err_t result = gpio_install_isr_service(0);
    if (result != ESP_OK && result != ESP_ERR_INVALID_STATE) {
        return result;
    }
    return gpio_isr_handler_add(CONFIG_WP_GPIO_DATA_READY, handler, argument);
}

/**
 * @brief Serialize a SPI transaction and wait for its completion.
 */
static esp_err_t board_spi_transfer(const void* tx, void* rx, size_t length)
{
    if (xSemaphoreTake(spi_mutex, pdMS_TO_TICKS(1000)) != pdTRUE) {
        return ESP_ERR_TIMEOUT;
    }
    spi_transaction_t transaction = {
        .length = length * 8,
        .tx_buffer = tx,
        .rx_buffer = rx,
    };
    esp_err_t result = spi_device_queue_trans(spi_device, &transaction, portMAX_DELAY);
    if (result == ESP_OK) {
        spi_transaction_t* completed = NULL;
        result = spi_device_get_trans_result(spi_device, &completed, portMAX_DELAY);
    }
    xSemaphoreGive(spi_mutex);
    return result;
}

esp_err_t board_spi_receive_dma(void* buffer, size_t length)
{
    return board_spi_transfer(NULL, buffer, length);
}

esp_err_t board_spi_transmit(const void* buffer, size_t length)
{
    return board_spi_transfer(buffer, NULL, length);
}

esp_err_t board_spi_transceive(const void* tx_buffer, void* rx_buffer, size_t length)
{
    return board_spi_transfer(tx_buffer, rx_buffer, length);
}

esp_err_t board_usb_no_sleep_acquire(void)
{
#if CONFIG_WP_ENABLE_PM
    if (!usb_sleep_lock_held) {
        esp_err_t result = esp_pm_lock_acquire(usb_frequency_lock);
        if (result != ESP_OK)
            return result;
        result = esp_pm_lock_acquire(usb_sleep_lock);
        if (result != ESP_OK)
            esp_pm_lock_release(usb_frequency_lock);
        if (result == ESP_OK) {
            usb_sleep_lock_held = true;
        }
        return result;
    }
#endif
    return ESP_OK;
}

esp_err_t board_usb_no_sleep_release(void)
{
#if CONFIG_WP_ENABLE_PM
    if (usb_sleep_lock_held) {
        esp_err_t result = esp_pm_lock_release(usb_sleep_lock);
        if (result == ESP_OK) {
            esp_pm_lock_release(usb_frequency_lock);
            usb_sleep_lock_held = false;
        }
        return result;
    }
#endif
    return ESP_OK;
}

esp_err_t board_init(void)
{
    ESP_RETURN_ON_ERROR(bsp_init(), "board", "BSP initialization failed");

    gpio_config_t gpio = {
        .intr_type = GPIO_INTR_DISABLE,
        .mode = GPIO_MODE_OUTPUT_OD,
        .pin_bit_mask = 1ULL << CONFIG_WP_GPIO_MSP_RST_N,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .pull_up_en = GPIO_PULLUP_DISABLE,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&gpio), "board", "MSP reset GPIO failed");
    ESP_RETURN_ON_ERROR(board_msp_reset(true), "board", "MSP reset failed");
    ESP_RETURN_ON_ERROR(gpio_sleep_sel_dis(CONFIG_WP_GPIO_MSP_RST_N), "board",
                        "MSP sleep GPIO failed");

    gpio = (gpio_config_t){
        .intr_type = GPIO_INTR_POSEDGE,
        .mode = GPIO_MODE_INPUT,
        .pin_bit_mask = 1ULL << CONFIG_WP_GPIO_DATA_READY,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,
        .pull_up_en = GPIO_PULLUP_DISABLE,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&gpio), "board", "DATA_READY GPIO failed");
    ESP_RETURN_ON_ERROR(gpio_sleep_set_direction(CONFIG_WP_GPIO_DATA_READY, GPIO_MODE_INPUT),
                        "board", "DATA_READY sleep direction failed");
    ESP_RETURN_ON_ERROR(gpio_sleep_set_pull_mode(CONFIG_WP_GPIO_DATA_READY, GPIO_PULLDOWN_ONLY),
                        "board", "DATA_READY sleep pull failed");

    spi_bus_config_t bus = {
        .miso_io_num = CONFIG_WP_SPI_MISO,
        .mosi_io_num = CONFIG_WP_SPI_MOSI,
        .sclk_io_num = CONFIG_WP_SPI_CLK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = CONFIG_WP_SPI_MAX_TRANSFER_SIZE,
    };
    spi_device_interface_config_t device = {
        .clock_speed_hz = CONFIG_WP_SPI_CLOCK_SPEED,
        .mode = 1,
        .spics_io_num = CONFIG_WP_SPI_CS,
        .queue_size = 3,
        .cs_ena_pretrans = 16,
        .cs_ena_posttrans = 16,
    };
    ESP_RETURN_ON_ERROR(spi_bus_initialize(CONFIG_WP_SPI_INSTANCE - 1, &bus, SPI_DMA_CH_AUTO),
                        "board", "SPI bus failed");
    ESP_RETURN_ON_ERROR(spi_bus_add_device(CONFIG_WP_SPI_INSTANCE - 1, &device, &spi_device),
                        "board", "SPI device failed");
    spi_mutex = xSemaphoreCreateMutex();
    if (spi_mutex == NULL) {
        return ESP_ERR_NO_MEM;
    }

    ESP_RETURN_ON_ERROR(gpio_sleep_set_direction(CONFIG_WP_SPI_CLK, GPIO_MODE_OUTPUT), "board",
                        "SPI CLK sleep failed");
    ESP_RETURN_ON_ERROR(gpio_sleep_set_pull_mode(CONFIG_WP_SPI_CLK, GPIO_PULLDOWN_ONLY), "board",
                        "SPI CLK pull failed");
    ESP_RETURN_ON_ERROR(gpio_sleep_set_direction(CONFIG_WP_SPI_MOSI, GPIO_MODE_OUTPUT), "board",
                        "SPI MOSI sleep failed");
    ESP_RETURN_ON_ERROR(gpio_sleep_set_pull_mode(CONFIG_WP_SPI_MOSI, GPIO_PULLDOWN_ONLY), "board",
                        "SPI MOSI pull failed");
    ESP_RETURN_ON_ERROR(gpio_sleep_set_direction(CONFIG_WP_SPI_MISO, GPIO_MODE_INPUT), "board",
                        "SPI MISO sleep failed");
    ESP_RETURN_ON_ERROR(gpio_sleep_set_pull_mode(CONFIG_WP_SPI_MISO, GPIO_FLOATING), "board",
                        "SPI MISO pull failed");
    ESP_RETURN_ON_ERROR(gpio_sleep_set_direction(CONFIG_WP_SPI_CS, GPIO_MODE_OUTPUT), "board",
                        "SPI CS sleep failed");
    ESP_RETURN_ON_ERROR(gpio_sleep_set_pull_mode(CONFIG_WP_SPI_CS, GPIO_PULLUP_ONLY), "board",
                        "SPI CS pull failed");

#if CONFIG_WP_ENABLE_PM
    esp_pm_config_t pm = {
        .max_freq_mhz = CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ,
        .min_freq_mhz = CONFIG_WP_PM_MIN_FREQUENCY,
        .light_sleep_enable = true,
    };
    ESP_RETURN_ON_ERROR(esp_pm_configure(&pm), "board", "power management failed");
    ESP_RETURN_ON_ERROR(esp_pm_lock_create(ESP_PM_NO_LIGHT_SLEEP, 0, "usb_host", &usb_sleep_lock),
                        "board", "USB sleep lock failed");
    ESP_RETURN_ON_ERROR(
        esp_pm_lock_create(ESP_PM_CPU_FREQ_MAX, 0, "usb_clock", &usb_frequency_lock), "board",
        "USB frequency lock failed");
    ESP_RETURN_ON_ERROR(board_usb_no_sleep_acquire(), "board", "initial USB sleep lock failed");
#endif
    return ESP_OK;
}
