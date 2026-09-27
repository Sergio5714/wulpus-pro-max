idf_component_register(SRCS "link.c" "usb_link.c" "tcp_link.c"
                       INCLUDE_DIRS "include"
                       REQUIRES sock esp_driver_usb_serial_jtag)
