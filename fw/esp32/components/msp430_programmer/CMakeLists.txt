idf_component_register(SRCS "msp430_programmer.c" "msp430_image.c" "msp430_jtag.c"
                       INCLUDE_DIRS "include"
                       REQUIRES esp_partition esp_driver_gpio freertos nvs_flash
                                esp_system board control)
