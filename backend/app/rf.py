from __future__ import annotations

import math
import re


BSSID_RE = re.compile(r"[0-9A-Fa-f]{2}")


def format_mac(raw: bytes | str) -> str:
    if isinstance(raw, str):
        hex_bytes = BSSID_RE.findall(raw.replace("-", ":"))
        if len(hex_bytes) >= 6:
            return ":".join(b.lower() for b in hex_bytes[:6])
        return raw.strip().lower()
    return ":".join(f"{b:02x}" for b in raw[:6])


def decode_ssid(raw: bytes | str, length: int | None = None) -> str:
    if isinstance(raw, str):
        return raw
    data = raw[:length] if length is not None else raw
    data = data.rstrip(b"\x00")
    return data.decode("utf-8", errors="replace")


def freq_mhz_to_channel(mhz: float) -> tuple[int, str]:
    if 2400 <= mhz <= 2500:
        if abs(mhz - 2484) < 1:
            return 14, "2.4"
        channel = int(round((mhz - 2412) / 5)) + 1
        return max(1, min(14, channel)), "2.4"
    if 4900 <= mhz <= 5895:
        if mhz >= 5000:
            return int(round((mhz - 5000) / 5)), "5"
        return int(round((mhz - 4000) / 5)), "5"
    if 5925 <= mhz <= 7125:
        return int(round((mhz - 5955) / 5)) + 1, "6"
    return 0, "unknown"


def freq_khz_to_channel(khz: int) -> tuple[int, str]:
    if khz <= 0:
        return 0, "unknown"
    mhz = khz / 1000.0 if khz > 20_000 else float(khz)
    return freq_mhz_to_channel(mhz)


def quality_to_dbm(quality: float) -> float:
    return quality / 2.0 - 100.0


def normalize_rssi(raw: float | int | None) -> float | None:
    """Coerce driver-specific RSSI / quality values into approximate dBm."""
    if raw is None:
        return None
    value = float(raw)
    if -120.0 <= value <= 0.0:
        return value
    if 0.0 < value <= 100.0:
        return quality_to_dbm(value)
    if 100.0 < value <= 255.0:
        signed = value - 256.0 if value > 127.0 else value
        if -120.0 <= signed <= 0.0:
            return signed
        return signed - 50.0
    return max(-120.0, min(0.0, value))


def bssid_angle(bssid: str) -> float:
    """Deterministic FNV-1a angle from a normalized BSSID. Not a compass bearing."""
    norm = format_mac(bssid)
    hash_ = 2166136261
    for ch in norm:
        hash_ ^= ord(ch)
        hash_ = (hash_ * 16777619) & 0xFFFFFFFF
    return (hash_ / 0xFFFFFFFF) * math.tau


def rssi_to_meters(rssi: float, tx_power_dbm: float = 20.0, path_loss_n: float = 3.0) -> float:
    return 10 ** ((tx_power_dbm - rssi) / (10.0 * path_loss_n))
