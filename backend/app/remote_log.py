from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SAFE_ID = re.compile(r"[^A-Za-z0-9._-]+")


def safe_node_id(node_id: str) -> str:
    cleaned = SAFE_ID.sub("_", (node_id or "node").strip())
    cleaned = cleaned.strip("._-")[:64]
    return cleaned or "node"


def row_from_report(report: dict[str, Any], recv_t: float) -> dict[str, Any]:
    link = report.get("link") or {}
    motion = report.get("motion") or {}
    return {
        "timestamp": float(report.get("t") or recv_t),
        "recv_t": float(recv_t),
        "node_id": report.get("id"),
        "ssid": link.get("ssid"),
        "bssid": link.get("bssid"),
        "channel": link.get("channel"),
        "band": link.get("band"),
        "rssi": link.get("rssi") if link.get("rssi") is not None else motion.get("rssi"),
        "rolling_mean": motion.get("rolling_mean"),
        "rolling_std": motion.get("rolling_std"),
        "residual": motion.get("residual"),
        "z_score": motion.get("z_score"),
        "motion_score": motion.get("score"),
        "state": motion.get("state"),
        "aps": report.get("aps") or [],
        "position": report.get("position"),
    }


class RemoteNodeLog:
    """Append-only JSONL of remote node snapshots, one file per node per UTC day."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.samples: dict[str, int] = {}
        self.paths: dict[str, str] = {}
        self._lock = threading.Lock()

    def status(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "directory": str(self.directory),
            "nodes": [
                {"id": node_id, "samples": self.samples.get(node_id, 0), "path": self.paths.get(node_id)}
                for node_id in sorted(self.samples)
            ],
        }

    def append(self, report: dict[str, Any], recv_t: float) -> Path:
        node_id = safe_node_id(str(report.get("id") or "node"))
        day = datetime.fromtimestamp(recv_t, tz=timezone.utc).strftime("%Y%m%d")
        folder = self.directory / node_id
        path = folder / f"{node_id}_{day}.jsonl"
        payload = row_from_report(report, recv_t)
        line = json.dumps(payload, separators=(",", ":")) + "\n"
        with self._lock:
            folder.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
            self.samples[node_id] = self.samples.get(node_id, 0) + 1
            self.paths[node_id] = str(path)
        return path
