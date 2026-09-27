idf_component_register(SRCS "wulpus_pro_session.c" "wulpus_pro_status.c" "wulpus_pro_state.c"
                       "wulpus_pro_firmware_info.c"
                       INCLUDE_DIRS "include"
                       REQUIRES links frames esp_app_format)
