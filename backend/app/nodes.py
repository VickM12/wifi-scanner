from __future__ import annotations

import socket
import time
from dataclasses import dataclass, field
from typing import Any


NODE_TTL_S = 4.0
MAX_APS = 24


def lan_addresses() -> list[str]:
    found: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                found.add(ip)
    except OSError:
        pass
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("1.1.1.1", 80))
        found.add(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass
    return sorted(found)


def default_node_id() -> str:
    return socket.gethostname() or "node"


def compact_aps(aps: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ap in aps or []:
        out.append(
            {
                "ssid": ap.get("ssid"),
                "bssid": ap.get("bssid"),
                "rssi": ap.get("rssi"),
                "channel": ap.get("channel"),
                "band": ap.get("band"),
                "linked": bool(ap.get("linked")),
            }
        )
        if len(out) >= MAX_APS:
            break
    return out


def build_node_report(
    *,
    node_id: str,
    t: float,
    link: dict[str, Any] | None,
    motion: dict[str, Any] | None,
    aps: list[dict[str, Any]] | None,
    position: dict[str, Any] | None = None,
    local: bool = False,
) -> dict[str, Any]:
    """Shared observation for the hub. Position is reserved for later triangulation."""
    return {
        "id": node_id,
        "t": t,
        "local": local,
        "link": link,
        "motion": {
            "rssi": (motion or {}).get("rssi") if motion else None,
            "score": (motion or {}).get("score") if motion else None,
            "state": (motion or {}).get("state") if motion else "STILL",
            "z_score": (motion or {}).get("z_score") if motion else None,
            "residual": (motion or {}).get("residual") if motion else None,
            "rolling_mean": (motion or {}).get("rolling_mean") if motion else None,
            "rolling_std": (motion or {}).get("rolling_std") if motion else None,
        },
        "aps": compact_aps(aps),
        "position": position,
    }


@dataclass
class NodeRegistry:
    ttl_s: float = NODE_TTL_S
    _nodes: dict[str, dict[str, Any]] = field(default_factory=dict)

    def ingest(self, report: dict[str, Any], now: float | None = None) -> dict[str, Any]:
        node_id = str(report.get("id") or "").strip()
        if not node_id:
            raise ValueError("node id required")
        stamp = float(now if now is not None else time.time())
        stored = {
            "id": node_id,
            "t": float(report.get("t") or stamp),
            "recv_t": stamp,
            "local": False,
            "link": report.get("link"),
            "motion": report.get("motion") or {},
            "aps": compact_aps(report.get("aps")),
            "position": report.get("position"),
        }
        self._nodes[node_id] = stored
        return stored

    def expire(self, now: float | None = None) -> None:
        stamp = now if now is not None else time.time()
        dead = [key for key, node in self._nodes.items() if stamp - float(node.get("recv_t", 0)) > self.ttl_s]
        for key in dead:
            self._nodes.pop(key, None)

    def remote_list(self, now: float | None = None) -> list[dict[str, Any]]:
        self.expire(now)
        return [dict(node) for node in self._nodes.values()]
