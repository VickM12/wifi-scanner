from __future__ import annotations

import json
from pathlib import Path
from typing import Any


LOCAL_PATH = Path(__file__).resolve().parents[1] / "radar.local.json"
LOCAL_KEYS = ("node_id", "hub_url", "share_token", "push_to_hub")


def load_local() -> dict[str, Any]:
    if not LOCAL_PATH.is_file():
        return {}
    try:
        data = json.loads(LOCAL_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {key: data[key] for key in LOCAL_KEYS if key in data}


def save_local(settings: Any) -> None:
    payload = {
        "node_id": getattr(settings, "node_id", "") or "",
        "hub_url": getattr(settings, "hub_url", None),
        "share_token": getattr(settings, "share_token", "") or "",
        "push_to_hub": bool(getattr(settings, "push_to_hub", False)),
    }
    LOCAL_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
