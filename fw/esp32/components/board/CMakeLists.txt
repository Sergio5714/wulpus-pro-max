idf_component_register(SRCS "board.c"
                       INCLUDE_DIRS "include"
                       REQUIRES bsp esp_driver_gpio esp_driver_spi esp_pm)
