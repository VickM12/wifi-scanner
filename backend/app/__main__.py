from __future__ import annotations

import argparse
import asyncio
import os

import uvicorn

from .certs import ensure_tls
from .hub import hub
from .nodes import default_node_id, lan_addresses


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
    hub.listen_https_port = args.port + 1
    if args.name:
        hub.settings.node_id = args.name
    if args.token:
        hub.settings.share_token = args.token
    if args.hub:
        hub.settings.hub_url = args.hub.rstrip("/")
        hub.settings.push_to_hub = True
    hub.persist_local()

    tls = ensure_tls(lan_addresses()) if args.host in ("0.0.0.0", "::") else None
    if tls:
        hub.https_ready = True
        asyncio.run(_serve(args.host, args.port, args.port + 1, tls[0], tls[1]))
        return
    hub.https_ready = False
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=False)


async def _serve(host: str, port: int, https_port: int, cert, key) -> None:
    from app.main import app

    http = uvicorn.Server(uvicorn.Config(app, host=host, port=port, lifespan="on", log_level="info"))
    https = uvicorn.Server(
        uvicorn.Config(
            app,
            host=host,
            port=https_port,
            lifespan="off",
            ssl_certfile=str(cert),
            ssl_keyfile=str(key),
            log_level="info",
        )
    )
    await asyncio.gather(http.serve(), https.serve())


if __name__ == "__main__":
    main()
