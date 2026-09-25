from __future__ import annotations

import argparse
import os

import uvicorn

from .hub import hub
from .nodes import default_node_id


def main() -> None:
    parser = argparse.ArgumentParser(description="WiFi Radar")
    parser.add_argument(
        "--host",
        default=os.environ.get("WIFI_RADAR_HOST", "127.0.0.1"),
        help="Bind address. Use 0.0.0.0 so other devices on the LAN can push snapshots.",
    )
    parser.add_argument("--port", type=int, default=int(os.environ.get("WIFI_RADAR_PORT", "8765")))
    parser.add_argument("--name", default=os.environ.get("WIFI_RADAR_NAME", default_node_id()))
    parser.add_argument("--hub", default=os.environ.get("WIFI_RADAR_HUB", ""), help="Hub base URL, e.g. http://192.168.1.20:8765")
    parser.add_argument("--token", default=os.environ.get("WIFI_RADAR_TOKEN", ""))
    args = parser.parse_args()

    hub.listen_host = args.host
    hub.listen_port = args.port
    if args.name:
        hub.settings.node_id = args.name
    if args.token:
        hub.settings.share_token = args.token
    if args.hub:
        hub.settings.hub_url = args.hub.rstrip("/")
        hub.settings.push_to_hub = True
    hub.persist_local()

    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
