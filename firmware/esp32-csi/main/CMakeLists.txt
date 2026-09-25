idf_component_register(
    SRCS "csi_udp.c"
    INCLUDE_DIRS "."
    REQUIRES esp_wifi nvs_flash esp_netif esp_event lwip
)
