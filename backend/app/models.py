from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AccessPoint:
    ssid: str
    bssid: str
    rssi: float
    channel: int
    frequency_mhz: float
    band: str
    linked: bool = False
    quality: int | None = None
    delta_rssi: float | None = None
    variance: float = 0.0
    smoothed_rssi: float | None = None
    last_seen: float | None = None
    bearing_deg: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LinkSample:
    bssid: str
    ssid: str
    rssi: float
    frequency_mhz: float | None = None
    raw_rssi: float | None = None
    channel: int | None = None
    band: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MotionResult:
    score: float
    rssi_score: float
    csi_score: float
    active: bool
    residual: float = 0.0
    sample_count: int = 0
    rssi: float | None = None
    rolling_mean: float | None = None
    rolling_std: float | None = None
    z_score: float | None = None
    short_variance: float | None = None
    state: str = "STILL"
    baseline_rssi: float | None = None
    noise_sigma: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CsiSample:
    timestamp: float
    source_id: str
    bssid: str
    channel: int | None
    rssi: float | None
    subcarrier_indices: list[int]
    amplitudes: list[float]
    phases: list[float] | None = None
    seq: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Backward-compatible alias used by the UDP parser.
@dataclass
class CsiFrame:
    seq: int
    rssi: float | None
    mac: str
    noise: float | None
    amps: list[float]
    source: str = "udp"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WlanInterface:
    id: str
    name: str
    connected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AppSettings:
    running: bool = True
    demo: bool = False
    threshold: float = 0.35
    iface: str | None = None
    csi_port: int = 5500
    sample_interval: float = 0.15
    baseline_window: float = 12.0
    motion_window: float = 1.5
    noise_floor: float = 0.4
    node_id: str = ""
    hub_url: str | None = None
    share_token: str = ""
    push_to_hub: bool = False


@dataclass
class Snapshot:
    t: float
    link: LinkSample | None
    aps: list[AccessPoint] = field(default_factory=list)
    motion: MotionResult | None = None
    csi: CsiSample | None = None
    interfaces: list[WlanInterface] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)
    status: str = ""
    error: str | None = None
    calibration: dict[str, Any] = field(default_factory=dict)
    recording: dict[str, Any] = field(default_factory=dict)
    csi_status: str = "CSI source not connected"
    nodes: list[dict[str, Any]] = field(default_factory=list)
    network: dict[str, Any] = field(default_factory=dict)
    house: dict[str, Any] = field(default_factory=dict)
    fix: dict[str, Any] | None = None
    heading: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "t": self.t,
            "link": self.link.to_dict() if self.link else None,
            "aps": [ap.to_dict() for ap in self.aps],
            "motion": self.motion.to_dict() if self.motion else None,
            "csi": self.csi.to_dict() if self.csi else None,
            "interfaces": [i.to_dict() for i in self.interfaces],
            "settings": self.settings,
            "status": self.status,
            "error": self.error,
            "calibration": self.calibration,
            "recording": self.recording,
            "csi_status": self.csi_status,
            "nodes": self.nodes,
            "network": self.network,
            "house": self.house,
            "fix": self.fix,
            "heading": self.heading,
        }
