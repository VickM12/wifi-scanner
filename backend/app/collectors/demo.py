from __future__ import annotations

import math
import time

from ..models import AccessPoint, LinkSample, WlanInterface
from .base import RadioCollector


class DemoCollector(RadioCollector):
    """Synthetic house + neighbor APs so the UI can run without radio access."""

    def __init__(self) -> None:
        self.status = "demo generator"

    def list_interfaces(self) -> list[WlanInterface]:
        return [WlanInterface(id="demo0", name="Demo radio", connected=True)]

    def scan_aps(self) -> list[AccessPoint]:
        t = time.time()
        living = -42 + 2.2 * math.sin(t / 2.4) + 1.4 * math.sin(t * 3.1)
        specs = [
            ("Living Room", "aa:11:22:33:44:01", living, 6, 2437, "2.4", True),
            ("Bedroom", "aa:11:22:33:44:02", -58 + 1.1 * math.sin(t / 5.0), 36, 5180, "5", False),
            ("Kitchen", "aa:11:22:33:44:03", -61 + 0.8 * math.sin(t / 3.7), 44, 5220, "5", False),
            ("Office", "aa:11:22:33:44:04", -70 + 0.6 * math.sin(t / 6.2), 149, 5745, "5", False),
            ("Neighbor-5G", "bb:22:33:44:55:10", -76, 11, 2462, "2.4", False),
            ("CafeGuest", "cc:33:44:55:66:20", -84, 1, 2412, "2.4", False),
            ("IoT-Hub", "aa:11:22:33:44:05", -67 + 0.4 * math.sin(t / 8.0), 5, 2432, "2.4", False),
        ]
        return [
            AccessPoint(
                ssid=ssid,
                bssid=bssid,
                rssi=round(rssi, 2),
                channel=ch,
                frequency_mhz=freq,
                band=band,
                linked=linked,
            )
            for ssid, bssid, rssi, ch, freq, band, linked in specs
        ]

    def poll_link(self) -> LinkSample | None:
        t = time.time()
        # Slow fade plus a faster "someone walking" flicker.
        rssi = -42 + 1.6 * math.sin(t / 3.0) + 2.8 * math.sin(t * 4.4)
        return LinkSample(
            bssid="aa:11:22:33:44:01",
            ssid="Living Room",
            rssi=round(rssi, 2),
            frequency_mhz=2437,
            raw_rssi=rssi,
        )
