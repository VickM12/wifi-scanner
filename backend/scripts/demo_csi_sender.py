#!/usr/bin/env python3
"""Send synthetic CSI JSON datagrams to the radar collector (UDP 5500)."""

from __future__ import annotations

import argparse
import json
import math
import socket
import time


def main() -> None:
    parser = argparse.ArgumentParser(description="Fake ESP32 CSI sender")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5500)
    parser.add_argument("--hz", type=float, default=20.0)
    parser.add_argument("--subs", type=int, default=64)
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    seq = 0
    period = 1.0 / max(args.hz, 1.0)
    print(f"Sending CSI to {args.host}:{args.port} at {args.hz} Hz. Ctrl+C to stop.")
    try:
        while True:
            now = time.time()
            walk = 3.5 * math.sin(now * 3.6)
            amps = [
                9 + 3.5 * math.sin(i / 7.0) + 0.8 * math.sin(now + i / 5.0) + walk * math.sin(i / 4.0)
                for i in range(args.subs)
            ]
            payload = {
                "v": 1,
                "seq": seq,
                "rssi": round(-51 + walk * 0.3, 2),
                "mac": "aa:11:22:33:44:01",
                "noise": -91,
                "amps": [round(a, 3) for a in amps],
                "source": "demo-sender",
            }
            sock.sendto(json.dumps(payload).encode("utf-8"), (args.host, args.port))
            seq += 1
            time.sleep(period)
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    main()
