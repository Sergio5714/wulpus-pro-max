idf_component_register(SRCS "app_main.c"
                       INCLUDE_DIRS "."
                       REQUIRES board frames control threads provisioner
                                mdns_manager double_reset msp430_programmer)
