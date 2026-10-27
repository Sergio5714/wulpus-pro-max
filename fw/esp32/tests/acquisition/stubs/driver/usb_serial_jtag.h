#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
typedef struct { size_t rx_buffer_size, tx_buffer_size; } usb_serial_jtag_driver_config_t;
int usb_serial_jtag_read_bytes(void* buffer, size_t length, uint32_t timeout);
int usb_serial_jtag_write_bytes(const void* buffer, size_t length, uint32_t timeout);
bool usb_serial_jtag_is_connected(void);
esp_err_t usb_serial_jtag_driver_install(usb_serial_jtag_driver_config_t* config);
