idf_component_register(SRCS "provisioner.c"
                       INCLUDE_DIRS "."
                       REQUIRES esp_event esp_wifi network_provisioning persistent_config)
