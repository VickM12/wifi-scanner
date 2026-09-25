from __future__ import annotations


def read_heading_deg() -> float | None:
    """Best-effort device compass. Most desktops have none."""
    try:
        from winrt.windows.devices.sensors import Compass  # type: ignore
    except Exception:
        return None
    try:
        sensor = Compass.get_default()
        if sensor is None:
            return None
        reading = sensor.get_current_reading()
        if reading is None:
            return None
        heading = getattr(reading, "heading_magnetic_north", None)
        if heading is None:
            heading = getattr(reading, "heading_true_north", None)
        if heading is None:
            return None
        return float(heading) % 360.0
    except Exception:
        return None
