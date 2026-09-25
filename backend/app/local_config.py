from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .geometry import default_house, normalize_house


LOCAL_PATH = Path(__file__).resolve().parents[1] / "radar.local.json"
LOCAL_KEYS = ("node_id", "hub_url", "share_token", "push_to_hub", "house")


def load_local() -> dict[str, Any]:
    if not LOCAL_PATH.is_file():
        return {}
    try:
        data = json.loads(LOCAL_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out = {key: data[key] for key in LOCAL_KEYS if key in data}
    if "house" in out:
        out["house"] = normalize_house(out["house"])
    return out


def save_local(settings: Any, house: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {}
    if LOCAL_PATH.is_file():
        try:
            existing = json.loads(LOCAL_PATH.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                payload.update(existing)
        except (OSError, json.JSONDecodeError):
            payload = {}
    payload.update(
        {
            "node_id": getattr(settings, "node_id", "") or "",
            "hub_url": getattr(settings, "hub_url", None),
            "share_token": getattr(settings, "share_token", "") or "",
            "push_to_hub": bool(getattr(settings, "push_to_hub", False)),
        }
    )
    if house is not None:
        payload["house"] = normalize_house(house)
    elif "house" not in payload:
        payload["house"] = default_house()
    LOCAL_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
