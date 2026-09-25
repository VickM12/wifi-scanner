from __future__ import annotations

from math import sqrt


def rolling_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def rolling_variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = rolling_mean(values)
    return sum((x - mean) ** 2 for x in values) / (len(values) - 1)


def rolling_std(values: list[float]) -> float:
    return sqrt(rolling_variance(values))


def residual(rssi: float, mean: float) -> float:
    return rssi - mean


def z_score(resid: float, sigma: float, noise_floor: float) -> float:
    denom = max(sigma, noise_floor, 1e-6)
    return resid / denom


def motion_score(abs_z: float, short_std: float, sigma: float, noise_floor: float) -> float:
    """Deterministic 0–1 score from |z| and short-window energy."""
    denom = max(sigma, noise_floor, 1e-6)
    z_norm = min(1.0, abs_z / 4.0)
    var_norm = min(1.0, short_std / (2.5 * denom))
    return max(0.0, min(1.0, 0.65 * z_norm + 0.35 * var_norm))
