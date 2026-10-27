#pragma once
#include <stdbool.h>
#include <stddef.h>
#include "esp_err.h"
bool board_data_ready(void);
esp_err_t board_msp_reset(bool asserted);
esp_err_t board_data_ready_set_isr(void (*handler)(void*), void* arg);
esp_err_t board_spi_transceive(const void* tx_buffer, void* rx_buffer, size_t length);
esp_err_t board_spi_transmit(const void* data, size_t length);
esp_err_t board_spi_receive_dma(void* data, size_t length);
