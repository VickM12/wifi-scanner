from __future__ import annotations

import math
from typing import Any

from .rf import format_mac, rssi_to_meters


N_INNER = 3.6
N_OUTER = 2.4
N_MID = 3.0
DB_PAD = 6.0
FLOOR_PRIOR_DB = 6.0
SCAN_CLIP_DBM = -50.0
REF_1M_5 = -35.0
REF_1M_24 = -30.0


def default_house() -> dict[str, Any]:
    return {
        "footprint": {"w": 12.0, "d": 10.0},
        "floors": [
            {"id": "1", "name": "1", "z": 0.0, "w": 12.0, "d": 10.0},
            {"id": "2", "name": "2", "z": 3.0, "w": 12.0, "d": 10.0},
            {"id": "3", "name": "3", "z": 6.0, "w": 12.0, "d": 10.0},
        ],
        "rooms": [
            {"id": "living", "name": "living", "floor": "1", "z": 0.0, "x": 0.0, "y": 0.0, "w": 6.0, "d": 10.0},
            {"id": "bedroom", "name": "bedroom", "floor": "2", "z": 3.0, "x": 0.0, "y": 1.5, "w": 6.0, "d": 7.0},
            {"id": "office", "name": "office", "floor": "3", "z": 6.0, "x": 0.0, "y": 0.0, "w": 4.5, "d": 5.0},
        ],
        "anchors": [
            {"id": "deco-a", "label": "bedroom Deco", "floor": "2", "x": 4.2, "y": 4.0, "bssids": []},
            {"id": "deco-b", "label": "living Deco", "floor": "1", "x": 2.4, "y": 7.5, "bssids": []},
        ],
    }


def normalize_house(raw: Any) -> dict[str, Any]:
    base = default_house()
    if not isinstance(raw, dict):
        return base
    floors = []
    for item in raw.get("floors") or base["floors"]:
        if not isinstance(item, dict):
            continue
        floors.append(
            {
                "id": str(item.get("id") or len(floors) + 1),
                "name": str(item.get("name") or f"floor-{len(floors) + 1}"),
                "z": float(item.get("z") or 0.0),
                "w": max(2.0, float(item.get("w") or 12.0)),
                "d": max(2.0, float(item.get("d") or 8.0)),
            }
        )
    if not floors:
        floors = base["floors"]
    floor_ids = {f["id"] for f in floors}
    anchors = []
    for item in raw.get("anchors") or []:
        if not isinstance(item, dict):
            continue
        floor_id = str(item.get("floor") or floors[0]["id"])
        if floor_id not in floor_ids:
            floor_id = floors[0]["id"]
        bssids = []
        for mac in item.get("bssids") or []:
            cleaned = format_mac(str(mac))
            if cleaned and cleaned not in bssids:
                bssids.append(cleaned)
        anchors.append(
            {
                "id": str(item.get("id") or f"anchor-{len(anchors) + 1}"),
                "label": str(item.get("label") or f"Anchor {len(anchors) + 1}"),
                "floor": floor_id,
                "x": float(item.get("x") or 0.0),
                "y": float(item.get("y") or 0.0),
                "bssids": bssids,
            }
        )
    if not anchors:
        anchors = base["anchors"]
    rooms = []
    for item in raw.get("rooms") or []:
        if not isinstance(item, dict):
            continue
        floor_id = str(item.get("floor") or floors[0]["id"])
        if floor_id not in floor_ids:
            floor_id = floors[0]["id"]
        z = next((float(f["z"]) for f in floors if f["id"] == floor_id), float(item.get("z") or 0.0))
        rooms.append(
            {
                "id": str(item.get("id") or f"room-{len(rooms) + 1}"),
                "name": str(item.get("name") or f"room {len(rooms) + 1}"),
                "floor": floor_id,
                "z": z,
                "x": float(item.get("x") or 0.0),
                "y": float(item.get("y") or 0.0),
                "w": max(1.0, float(item.get("w") or 4.0)),
                "d": max(1.0, float(item.get("d") or 4.0)),
            }
        )
    if not rooms:
        if raw.get("floors"):
            rooms = [
                {
                    "id": floor["name"] or floor["id"],
                    "name": floor["name"] or floor["id"],
                    "floor": floor["id"],
                    "z": float(floor["z"]),
                    "x": 0.0,
                    "y": 0.0,
                    "w": float(floor["w"]),
                    "d": float(floor["d"]),
                }
                for floor in floors
            ]
        else:
            rooms = base["rooms"]
    foot = raw.get("footprint") if isinstance(raw.get("footprint"), dict) else {}
    fw = max(float(foot.get("w") or 0.0), max((f["w"] for f in floors), default=12.0), max((r["x"] + r["w"] for r in rooms), default=12.0))
    fd = max(float(foot.get("d") or 0.0), max((f["d"] for f in floors), default=10.0), max((r["y"] + r["d"] for r in rooms), default=10.0))
    for floor in floors:
        floor["w"] = fw
        floor["d"] = fd
    return {"footprint": {"w": fw, "d": fd}, "floors": floors, "rooms": rooms, "anchors": anchors}


def room_at(house: dict[str, Any], floor_id: str, x: float, y: float) -> dict[str, Any] | None:
    for room in house.get("rooms") or []:
        if room.get("floor") != floor_id:
            continue
        if room["x"] <= x <= room["x"] + room["w"] and room["y"] <= y <= room["y"] + room["d"]:
            return room
    return None


def house_configured(house: dict[str, Any] | None) -> bool:
    if not house:
        return False
    return any(anchor.get("bssids") for anchor in house.get("anchors") or [])


def _ref_rssi(band: str | None) -> float:
    return REF_1M_24 if band == "2.4" else REF_1M_5


def _annulus(rssi: float, band: str | None, clipped: bool) -> tuple[float, float, float]:
    ref = _ref_rssi(band)
    inner = rssi_to_meters(rssi + DB_PAD, tx_power_dbm=ref, path_loss_n=N_INNER)
    mid = rssi_to_meters(rssi, tx_power_dbm=ref, path_loss_n=N_MID)
    outer = rssi_to_meters(rssi - DB_PAD, tx_power_dbm=ref, path_loss_n=N_OUTER)
    if clipped:
        inner = min(inner, 0.4)
    inner = max(0.15, inner)
    outer = max(outer, inner + 0.4)
    mid = min(max(mid, inner), outer)
    return inner, mid, outer


def _horizontal(radius: float, dz: float) -> float | None:
    if radius <= abs(dz):
        return None
    return math.sqrt(radius * radius - dz * dz)


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def circle_intersections(
    c1: tuple[float, float],
    r1: float,
    c2: tuple[float, float],
    r2: float,
) -> list[tuple[float, float]]:
    d = _dist(c1, c2)
    if d < 1e-6 or r1 <= 0 or r2 <= 0:
        return []
    if d > r1 + r2 or d < abs(r1 - r2):
        return []
    along = (r1 * r1 - r2 * r2 + d * d) / (2.0 * d)
    h2 = r1 * r1 - along * along
    if h2 < -1e-6:
        return []
    h = math.sqrt(max(0.0, h2))
    mx = c1[0] + along * (c2[0] - c1[0]) / d
    my = c1[1] + along * (c2[1] - c1[1]) / d
    if h < 1e-6:
        return [(mx, my)]
    rx = -(c2[1] - c1[1]) * (h / d)
    ry = (c2[0] - c1[0]) * (h / d)
    return [(mx + rx, my + ry), (mx - rx, my - ry)]


def _clamp(point: tuple[float, float], floor: dict[str, Any]) -> tuple[float, float]:
    return (
        min(max(point[0], 0.0), float(floor["w"])),
        min(max(point[1], 0.0), float(floor["d"])),
    )


def _pick_observation(
    anchor: dict[str, Any],
    aps: list[dict[str, Any]],
    link: dict[str, Any] | None,
) -> dict[str, Any] | None:
    wanted = {format_mac(mac) for mac in anchor.get("bssids") or []}
    if not wanted:
        return None
    link_bssid = format_mac(str(link.get("bssid"))) if link and link.get("bssid") else ""
    link_rssi = link.get("rssi") if link else None
    matches: list[dict[str, Any]] = []
    for ap in aps or []:
        bssid = format_mac(str(ap.get("bssid") or ""))
        if bssid not in wanted or ap.get("rssi") is None:
            continue
        matches.append(
            {
                "bssid": bssid,
                "rssi": float(ap["rssi"]),
                "band": str(ap.get("band") or ""),
                "linked": bool(ap.get("linked")) or bssid == link_bssid,
            }
        )
    if link_bssid in wanted and link_rssi is not None:
        band = str((link or {}).get("band") or "")
        existing = next((m for m in matches if m["bssid"] == link_bssid), None)
        if existing:
            existing["rssi"] = float(link_rssi)
            existing["linked"] = True
            if band:
                existing["band"] = band
        else:
            matches.append({"bssid": link_bssid, "rssi": float(link_rssi), "band": band, "linked": True})
    if not matches:
        return None
    linked = [m for m in matches if m["linked"]]
    pool = linked or matches
    pool.sort(key=lambda m: (0 if m.get("band") == "5" else 1, -m["rssi"]))
    best = dict(pool[0])
    scan_twin = next((m for m in matches if m["bssid"] == best["bssid"] and not m["linked"]), None)
    clipped = (not best["linked"]) and best["rssi"] >= SCAN_CLIP_DBM - 0.6
    if clipped and scan_twin is None:
        best["clipped"] = True
    else:
        best["clipped"] = clipped
    return best


def estimate_fix(
    house: dict[str, Any] | None,
    aps: list[dict[str, Any]] | None,
    link: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not house_configured(house):
        return None
    assert house is not None
    floors = {f["id"]: f for f in house["floors"]}
    observed: list[dict[str, Any]] = []
    rings: list[dict[str, Any]] = []
    for anchor in house["anchors"]:
        obs = _pick_observation(anchor, aps or [], link)
        if obs is None:
            continue
        inner, mid, outer = _annulus(obs["rssi"], obs.get("band"), bool(obs.get("clipped")))
        anchor_floor = floors.get(anchor["floor"])
        az = float(anchor_floor["z"]) if anchor_floor else 0.0
        observed.append({**obs, "anchor": anchor, "inner": inner, "mid": mid, "outer": outer, "az": az})
        for floor in house["floors"]:
            dz = float(floor["z"]) - az
            hi = _horizontal(outer, dz)
            if hi is None:
                continue
            lo = _horizontal(inner, dz) or 0.15
            rings.append(
                {
                    "anchor_id": anchor["id"],
                    "label": anchor["label"],
                    "floor": floor["id"],
                    "x": float(anchor["x"]),
                    "y": float(anchor["y"]),
                    "r_inner": lo,
                    "r_outer": hi,
                    "rssi": obs["rssi"],
                    "band": obs.get("band"),
                    "linked": obs["linked"],
                }
            )
    if not observed:
        return None

    strong = max(observed, key=lambda o: o["rssi"])
    second = max((o["rssi"] for o in observed if o is not strong), default=None)
    prior_floor = None
    if second is None or strong["rssi"] - second >= FLOOR_PRIOR_DB:
        prior_floor = strong["anchor"]["floor"]

    candidates: list[dict[str, Any]] = []
    if len(observed) >= 2:
        a, b = observed[0], observed[1]
        for floor in house["floors"]:
            dz_a = float(floor["z"]) - a["az"]
            dz_b = float(floor["z"]) - b["az"]
            r_a = _horizontal(a["mid"], dz_a)
            r_b = _horizontal(b["mid"], dz_b)
            if r_a is None or r_b is None:
                continue
            c1 = (float(a["anchor"]["x"]), float(a["anchor"]["y"]))
            c2 = (float(b["anchor"]["x"]), float(b["anchor"]["y"]))
            points = circle_intersections(c1, r_a, c2, r_b)
            if not points:
                gap = _dist(c1, c2)
                if gap < 1e-6:
                    continue
                # Compromise on the line between anchors when mid-circles miss.
                pull = r_a / (r_a + r_b)
                points = [(c1[0] + (c2[0] - c1[0]) * pull, c1[1] + (c2[1] - c1[1]) * pull)]
            width = 0.5 * (
                abs((_horizontal(a["outer"], dz_a) or r_a) - (_horizontal(a["inner"], dz_a) or r_a))
                + abs((_horizontal(b["outer"], dz_b) or r_b) - (_horizontal(b["inner"], dz_b) or r_b))
            )
            for raw in points:
                x, y = _clamp(raw, floor)
                fit = abs(_dist((x, y), c1) - r_a) + abs(_dist((x, y), c2) - r_b)
                prior = 0.0 if prior_floor in (None, floor["id"]) else 4.0
                inside = room_at(house, floor["id"], x, y)
                if inside is None:
                    prior += 1.5
                candidates.append(
                    {
                        "x": round(x, 3),
                        "y": round(y, 3),
                        "z": float(floor["z"]),
                        "floor": floor["id"],
                        "room": (inside or {}).get("name") or floor["name"],
                        "uncertainty": round(max(0.6, width), 3),
                        "score": round(fit + prior, 3),
                    }
                )
    candidates.sort(key=lambda c: c["score"])
    best = candidates[0] if candidates else None
    return {
        "x": best["x"] if best else None,
        "y": best["y"] if best else None,
        "z": best["z"] if best else None,
        "room": best["room"] if best else None,
        "floor": best["floor"] if best else None,
        "uncertainty": best["uncertainty"] if best else None,
        "score": best["score"] if best else None,
        "candidates": candidates[:4],
        "rings": rings,
        "anchors": [
            {
                "id": o["anchor"]["id"],
                "rssi": o["rssi"],
                "band": o.get("band"),
                "linked": o["linked"],
            }
            for o in observed
        ],
    }
