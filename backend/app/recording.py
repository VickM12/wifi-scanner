from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO


RECORD_FIELDS = [
    "timestamp",
    "ssid",
    "bssid",
    "channel",
    "band",
    "rssi",
    "rolling_mean",
    "rolling_std",
    "residual",
    "z_score",
    "motion_score",
    "label",
]

SUGGESTED_LABELS = [
    "empty_room",
    "walking",
    "walking_across_rf_path",
    "person_enters",
    "person_leaves",
    "sitting",
    "standing",
    "door_open",
    "door_close",
    "laptop_moved",
    "custom",
]


def serialize_record(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in RECORD_FIELDS:
        value = row.get(key)
        if key == "timestamp" and value is not None:
            out[key] = float(value)
        else:
            out[key] = value
    return out


class ExperimentRecorder:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.active = False
        self.label = "empty_room"
        self.fmt = "csv"
        self.path: Path | None = None
        self.samples = 0
        self.started_at: float | None = None
        self._fh: TextIO | None = None
        self._writer: csv.DictWriter | None = None

    def status(self, now: float) -> dict[str, Any]:
        elapsed = 0.0
        if self.active and self.started_at is not None:
            elapsed = max(0.0, now - self.started_at)
        return {
            "active": self.active,
            "label": self.label,
            "elapsed": elapsed,
            "samples": self.samples,
            "path": str(self.path) if self.path else None,
            "format": self.fmt,
            "labels": SUGGESTED_LABELS,
        }

    def start(self, label: str, fmt: str, now: float) -> Path:
        self.stop()
        clean = (label or "empty_room").strip() or "empty_room"
        self.label = clean
        self.fmt = "jsonl" if fmt == "jsonl" else "csv"
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in clean)[:48]
        self.path = self.directory / f"exp_{stamp}_{safe}.{self.fmt}"
        self._fh = self.path.open("w", encoding="utf-8", newline="")
        if self.fmt == "csv":
            self._writer = csv.DictWriter(self._fh, fieldnames=RECORD_FIELDS)
            self._writer.writeheader()
        self.active = True
        self.samples = 0
        self.started_at = now
        return self.path

    def append(self, row: dict[str, Any]) -> None:
        if not self.active or self._fh is None:
            return
        payload = serialize_record(row)
        payload["label"] = self.label
        if self.fmt == "csv" and self._writer is not None:
            self._writer.writerow(payload)
        else:
            self._fh.write(json.dumps(payload, separators=(",", ":")) + "\n")
        self._fh.flush()
        self.samples += 1

    def stop(self) -> Path | None:
        path = self.path if self.active else None
        if self._fh is not None:
            self._fh.close()
        self._fh = None
        self._writer = None
        self.active = False
        self.started_at = None
        return path
