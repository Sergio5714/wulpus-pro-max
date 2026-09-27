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
 * @file usb_link.c
 * @brief USB Serial/JTAG adapter for the common link interface.
 */

#include "usb_link.h"
#include "driver/usb_serial_jtag.h"
#include "esp_check.h"
#include "freertos/task.h"

#define USB_DISCONNECT_CONFIRM pdMS_TO_TICKS(100)
static portMUX_TYPE connection_lock = portMUX_INITIALIZER_UNLOCKED;
static bool host_connected;
static bool disconnect_pending;
static TickType_t disconnect_started;

/**
 * @brief Read bytes through the USB driver using the supplied tick timeout.
 */
static int read_bytes(void* context, void* buffer, size_t length, TickType_t timeout)
{
    (void)context;
    return usb_serial_jtag_read_bytes(buffer, length, timeout);
}
/**
 * @brief Write bytes through the USB driver using the supplied tick timeout.
 */
static int write_bytes(void* context, const void* buffer, size_t length, TickType_t timeout)
{
    (void)context;
    return usb_serial_jtag_write_bytes(buffer, length, timeout);
}
/**
 * @brief Return success without uninstalling the shared USB driver.
 */
static esp_err_t close_link(void* context)
{
    (void)context;
    return ESP_OK;
}
/**
 * @brief Return the USB driver connection state.
 */
static bool connected(void* context)
{
    (void)context;
    bool observed = usb_serial_jtag_is_connected();
    TickType_t now = xTaskGetTickCount();
    portENTER_CRITICAL(&connection_lock);
    if (observed) {
        host_connected = true;
        disconnect_pending = false;
    } else if (host_connected) {
        /* The driver's SOF monitor can briefly report false during traffic.
         * Do not end the acquisition session on a single false sample. */
        if (!disconnect_pending) {
            disconnect_pending = true;
            disconnect_started = now;
        } else if (now - disconnect_started >= USB_DISCONNECT_CONFIRM) {
            host_connected = false;
        }
    }
    bool result = host_connected;
    portEXIT_CRITICAL(&connection_lock);
    return result;
}

esp_err_t usb_link_create(link_t* link)
{
    usb_serial_jtag_driver_config_t config = {.rx_buffer_size = 2048, .tx_buffer_size = 2048};
    ESP_RETURN_ON_ERROR(usb_serial_jtag_driver_install(&config), "usb_link",
                        "driver install failed");
    *link = (link_t){.kind = LINK_USB,
                     .read = read_bytes,
                     .write = write_bytes,
                     .close = close_link,
                     .connected = connected};
    return link_init(link);
}
