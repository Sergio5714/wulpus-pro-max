idf_component_register(
    SRCS "threads.c" "acquisition_thread.c"
         "acquisition_handshake.c" "acquisition_frames.c" "packet_tx_thread.c"
         "protocol_thread.c" "usb_thread.c" "tcp_thread.c"
         "provisioning_thread.c"
    INCLUDE_DIRS "include"
    PRIV_INCLUDE_DIRS "."
    REQUIRES board frames control protocol links provisioner persistent_config mdns_manager
             msp430_programmer esp_system)
