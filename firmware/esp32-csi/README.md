# ESP32 CSI node

The laptop radio cannot expose Channel State Information. This firmware turns an ESP32 into a CSI sensor that UDP-sends amplitude vectors to the radar app.

## Protocol

One JSON object per UDP datagram, default port **5500**:

```json
{
  "v": 1,
  "seq": 42,
  "rssi": -51,
  "mac": "aa:bb:cc:dd:ee:ff",
  "noise": -91,
  "amps": [9.1, 8.4, 10.2]
}
```

- `amps` is per-subcarrier amplitude (`sqrt(I^2 + Q^2)`), typically 52–64 bins after skipping the invalid first word.
- The backend also accepts the same JSON from `backend/scripts/demo_csi_sender.py` so the heatmap can be tested without a board.

## What the firmware does

1. Joins your home AP (`WIFI_SSID` / `WIFI_PASS`).
2. Enables `esp_wifi_set_csi`.
3. Pings the default gateway so the router sends packets the ESP32 can harvest CSI from (same idea as Espressif `csi_recv_router`).
4. For each CSI callback, packs amplitudes and `sendto()` the laptop IP.

## Build (when you have a board)

Edit [`main/csi_udp.c`](main/csi_udp.c):

- `WIFI_SSID` / `WIFI_PASS` — home network
- `CSI_HOST` — laptop IPv4 on that LAN
- `CSI_PORT` — `5500` unless you changed it in the UI

Then, with [ESP-IDF](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/) 5.x:

```bat
idf.py set-target esp32
idf.py build
idf.py -p COMx flash monitor
```

Works on ESP32 / C3 / S3 / C6 with CSI support. Classic ESP32 is the most documented path.

## Laptop side

Keep the radar app running. In the UI, CSI heatmap should switch from “waiting” to live columns as soon as packets arrive. Point `CSI_HOST` at the machine running FastAPI, not `127.0.0.1` on the ESP32.
