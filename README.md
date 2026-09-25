# WiFi Radar

Proof-of-concept scanner that draws nearby access points as a radar map and scores **movement from RSSI flicker** on the path between this computer and the router you are joined to. Channel State Information (CSI) is accepted over UDP so an ESP32 can be plugged in later.

Stock Windows and Linux adapters do **not** expose CSI. This laptop can do RSSI. CSI comes from the ESP32 node (or the demo sender).

## What you will see

- **AP radar** — this machine at the origin. Distance is a path-loss guess from RSSI. Angle is a stable hash of the BSSID, not a compass heading or a floor plan.
- **RSSI waveform** — connected-AP signal at ~5–10 Hz. Walking or waving in the Fresnel zone raises the motion score.
- **CSI heatmap** — time × subcarrier once UDP frames arrive.
- **Demo mode** — synthetic house APs + CSI so the UI works without radio permission.

RSSI flicker on one laptop ↔ one router is **path motion**, not a room occupancy map. Imaging walls would need several sensors at known positions.

## Requirements

- Python 3.11+
- Windows 10/11 **or** Linux with `nmcli` and/or `iw`
- Node.js 20+ only if you want to rebuild the Vite UI (a prebuilt `frontend/dist` is already included)

### Windows

1. Connect to Wi-Fi.
2. Settings → Privacy & security → Location → **On**.
3. Allow desktop apps to use location (Wi-Fi scans are gated on this).

Connected RSSI (the motion waveform) often still works if scans are blocked. The radar list will be empty until Location is enabled.

### Linux

- Interface is auto-detected from `/sys/class/net` (`wlan0`, `wlp…`). Pick another in the UI.
- Scans prefer `nmcli dev wifi` (usually no sudo). Fallback is `iw dev <iface> scan` (often needs `cap_net_admin`).
- Link RSSI uses `iw dev <iface> link` or `/proc/net/wireless`.

## Run

Backend (from repo root):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app
```

On Linux, activate with `source .venv/bin/activate` then `python -m app`.

The API and UI listen on [http://127.0.0.1:8765](http://127.0.0.1:8765).

Optional Vite rebuild (hot reload — proxy to the API). If `npm install` fails with `UNABLE_TO_VERIFY_LEAF_SIGNATURE`, a corporate TLS intercept is blocking the registry; the prebuilt UI is enough:

```powershell
cd frontend
npm install
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173).

Or build once and use only the backend:

```powershell
cd frontend
npm install
npm run build
```

Then refresh `http://127.0.0.1:8765`.

### Try motion

Stay associated to your home AP. Watch the RSSI strip and walk through the room (or wave near the laptop). Raise **Motion threshold** if the badge chatters; lower it if it never trips.

Turn on **Demo** if you are not on Wi-Fi or Location is off.

### Try CSI without a board

With the backend running:

```powershell
cd backend
python scripts\demo_csi_sender.py
```

The heatmap should start painting. On Linux: `python scripts/demo_csi_sender.py`.

## ESP32 later

See [firmware/esp32-csi/README.md](firmware/esp32-csi/README.md). The node joins your AP, pings the gateway, and UDP-sends:

```json
{"v":1,"seq":1,"rssi":-51,"mac":"aa:bb:cc:dd:ee:ff","noise":-91,"amps":[9.1,8.4]}
```

to the laptop IP on port **5500** (changeable in the UI).

## API

| Path | Role |
| --- | --- |
| `GET /api/health` | status, settings, CSI packet count |
| `GET /api/aps` | latest snapshot |
| `GET /api/interfaces` | WLAN adapters |
| `POST /api/control` | `{ running, demo, threshold, iface, csi_port }` |
| `WS /ws/live` | ~10 Hz snapshots |

Default bind is `127.0.0.1`. CSI UDP binds `0.0.0.0:5500` so a board on the LAN can reach it.

## Two machines on one LAN

On the hub (stays on):

```powershell
python -m app --host 0.0.0.0
```

On another computer:

```powershell
python -m app --hub http://HUB_LAN_IP:8765
```

Set the same share token on both (UI **Token** field, or `WIFI_RADAR_TOKEN`). It is stored in gitignored `backend/radar.local.json`. Copy `backend/radar.local.json.example` — do not commit the real file. Allow TCP 8765 on the hub firewall.
