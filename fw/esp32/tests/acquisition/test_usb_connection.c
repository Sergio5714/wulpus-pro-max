/* Exercise the production USB connection filter with a deterministic clock. */
#include <stdio.h>
#include <stdlib.h>
#include "../../components/links/usb_link.c"
#define CHECK(x)                                                                                   \
    do {                                                                                           \
        if (!(x)) {                                                                                \
            printf("FAIL line %d: %s\n", __LINE__, #x);                                            \
            exit(1);                                                                               \
        }                                                                                          \
    } while (0)
static TickType_t ticks;
static bool physical;
TickType_t xTaskGetTickCount(void)
{
    return ticks;
}
bool usb_serial_jtag_is_connected(void)
{
    return physical;
}
int usb_serial_jtag_read_bytes(void* buffer, size_t length, uint32_t timeout)
{
    (void)buffer;
    (void)length;
    (void)timeout;
    return 0;
}
int usb_serial_jtag_write_bytes(const void* buffer, size_t length, uint32_t timeout)
{
    (void)buffer;
    (void)timeout;
    return (int)length;
}
esp_err_t usb_serial_jtag_driver_install(usb_serial_jtag_driver_config_t* config)
{
    (void)config;
    return ESP_OK;
}
esp_err_t link_init(link_t* link)
{
    (void)link;
    return ESP_OK;
}
int main(void)
{
    CHECK(!connected(NULL));
    physical = true;
    CHECK(connected(NULL));
    physical = false;
    CHECK(connected(NULL));
    ticks = 99;
    CHECK(connected(NULL));
    physical = true;
    CHECK(connected(NULL));
    physical = false;
    ticks = 5000;
    CHECK(connected(NULL)); /* Start timing at first false observation. */
    ticks = 5099;
    CHECK(connected(NULL));
    ticks = 5100;
    CHECK(!connected(NULL));
    CHECK(!connected(NULL));
    physical = true;
    CHECK(connected(NULL));
    ticks = UINT32_MAX - 49;
    physical = false;
    CHECK(connected(NULL));
    ticks = 49;
    CHECK(connected(NULL));
    ticks = 50;
    CHECK(!connected(NULL));
    puts("PASS USB transient disconnect, sustained unplug, reconnect and tick wrap");
    return 0;
}
