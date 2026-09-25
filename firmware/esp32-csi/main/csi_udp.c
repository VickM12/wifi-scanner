#include <math.h>
#include <stdio.h>
#include <string.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "lwip/inet.h"
#include "lwip/sockets.h"
#include "nvs_flash.h"
#include "ping/ping_sock.h"

/* Edit these before flashing. */
#define WIFI_SSID "YOUR_SSID"
#define WIFI_PASS "YOUR_PASS"
#define CSI_HOST "192.168.1.50"
#define CSI_PORT 5500

static const char *TAG = "csi_udp";
static EventGroupHandle_t s_wifi_event;
static const int GOT_IP_BIT = BIT0;
static int s_sock = -1;
static struct sockaddr_in s_dest;
static uint32_t s_seq;
static uint8_t s_ap_mac[6];

static void on_wifi(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        xEventGroupSetBits(s_wifi_event, GOT_IP_BIT);
    }
}

static void send_frame(int rssi, int8_t noise, const int8_t *buf, int len, bool skip_first)
{
    if (s_sock < 0 || buf == NULL || len < 4) {
        return;
    }

    int start = skip_first ? 4 : 0;
    int pairs = (len - start) / 2;
    if (pairs <= 0) {
        return;
    }
    if (pairs > 128) {
        pairs = 128;
    }

    char payload[2048];
    int n = snprintf(
        payload,
        sizeof(payload),
        "{\"v\":1,\"seq\":%lu,\"rssi\":%d,\"mac\":\"%02x:%02x:%02x:%02x:%02x:%02x\",\"noise\":%d,\"amps\":[",
        (unsigned long)s_seq++,
        rssi,
        s_ap_mac[0],
        s_ap_mac[1],
        s_ap_mac[2],
        s_ap_mac[3],
        s_ap_mac[4],
        s_ap_mac[5],
        (int)noise);

    for (int i = 0; i < pairs && n < (int)sizeof(payload) - 24; i++) {
        float iv = (float)buf[start + i * 2];
        float qv = (float)buf[start + i * 2 + 1];
        float amp = sqrtf(iv * iv + qv * qv);
        n += snprintf(payload + n, sizeof(payload) - n, "%s%.2f", i ? "," : "", amp);
    }
    if (n < (int)sizeof(payload) - 3) {
        memcpy(payload + n, "]}", 3);
        n += 2;
        sendto(s_sock, payload, n, 0, (struct sockaddr *)&s_dest, sizeof(s_dest));
    }
}

static void csi_cb(void *ctx, wifi_csi_info_t *info)
{
    (void)ctx;
    if (info == NULL || info->buf == NULL) {
        return;
    }
    send_frame(info->rx_ctrl.rssi, info->rx_ctrl.noise_floor, (const int8_t *)info->buf, info->len, info->first_word_invalid);
}

static void ping_on_success(esp_ping_handle_t handle, void *args)
{
    (void)handle;
    (void)args;
}

static void start_ping(void)
{
    esp_netif_ip_info_t ip;
    esp_netif_t *netif = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
    if (netif == NULL || esp_netif_get_ip_info(netif, &ip) != ESP_OK) {
        ESP_LOGW(TAG, "no STA netif / gateway yet");
        return;
    }

    esp_ping_config_t config = ESP_PING_DEFAULT_CONFIG();
    config.count = ESP_PING_COUNT_INFINITE;
    config.interval_ms = 50;
    config.target_addr.u_addr.ip4.addr = ip.gw.addr;
    config.target_addr.type = ESP_IPADDR_TYPE_V4;

    esp_ping_callbacks_t cbs = {
        .on_ping_success = ping_on_success,
        .on_ping_timeout = NULL,
        .on_ping_end = NULL,
        .cb_args = NULL,
    };
    esp_ping_handle_t ping;
    if (esp_ping_new_session(&config, &cbs, &ping) == ESP_OK) {
        esp_ping_start(ping);
        ESP_LOGI(TAG, "pinging gateway to solicit CSI");
    }
}

void app_main(void)
{
    ESP_ERROR_CHECK(nvs_flash_init());
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    s_wifi_event = xEventGroupCreate();
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &on_wifi, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &on_wifi, NULL));

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    wifi_config_t wifi_config = {0};
    strncpy((char *)wifi_config.sta.ssid, WIFI_SSID, sizeof(wifi_config.sta.ssid));
    strncpy((char *)wifi_config.sta.password, WIFI_PASS, sizeof(wifi_config.sta.password));
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));

    EventBits_t bits = xEventGroupWaitBits(s_wifi_event, GOT_IP_BIT, pdFALSE, pdTRUE, pdMS_TO_TICKS(30000));
    if (!(bits & GOT_IP_BIT)) {
        ESP_LOGE(TAG, "failed to join %s", WIFI_SSID);
        return;
    }
    ESP_ERROR_CHECK(esp_wifi_get_mac(WIFI_IF_STA, s_ap_mac));
    wifi_ap_record_t ap;
    if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) {
        memcpy(s_ap_mac, ap.bssid, 6);
    }

    s_sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    memset(&s_dest, 0, sizeof(s_dest));
    s_dest.sin_family = AF_INET;
    s_dest.sin_port = htons(CSI_PORT);
    s_dest.sin_addr.s_addr = inet_addr(CSI_HOST);

    wifi_csi_config_t csi_config = {
        .lltf_en = true,
        .htltf_en = true,
        .stbc_htltf2_en = true,
        .ltf_merge_en = true,
        .channel_filter_en = false,
        .manu_scale = false,
        .shift = 0,
    };
    ESP_ERROR_CHECK(esp_wifi_set_csi_config(&csi_config));
    ESP_ERROR_CHECK(esp_wifi_set_csi_rx_cb(csi_cb, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_csi(true));

    start_ping();
    ESP_LOGI(TAG, "CSI UDP -> %s:%d", CSI_HOST, CSI_PORT);
}
