from __future__ import annotations

import time
from typing import Protocol

from .collectors.esp32_csi import CsiCollector
from .models import CsiFrame, CsiSample


class CsiSource(Protocol):
    source_id: str

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def latest(self) -> CsiSample | None: ...
    def connected(self) -> bool: ...


class LaptopWifiScanner:
    """Laptop radios do not expose CSI. Present so the UI can name the gap."""

    source_id = "LaptopWifiScanner"

    def start(self) -> None:
        return

    def stop(self) -> None:
        return

    def latest(self) -> CsiSample | None:
        return None

    def connected(self) -> bool:
        return False


class Esp32CsiSource:
    """UDP CSI listener. Real frames only — never synthesizes amplitudes."""

    source_id = "Esp32CsiSource"

    def __init__(self, port: int = 5500) -> None:
        self.transport = CsiCollector(port=port)
        self._cached: CsiSample | None = None
        self._cached_seq: int | None = None

    def start(self) -> None:
        self.transport.start()

    def stop(self) -> None:
        self.transport.stop()

    def set_port(self, port: int) -> None:
        self.transport.set_port(port)

    def latest(self) -> CsiSample | None:
        frame = self.transport.latest
        if frame is None:
            return None
        if self._cached is None or frame.seq != self._cached_seq:
            self._cached = frame_to_sample(frame, self.source_id)
            self._cached_seq = frame.seq
        return self._cached

    def connected(self) -> bool:
        return self.transport.packets > 0 and self.transport.latest is not None

    @property
    def packets(self) -> int:
        return self.transport.packets

    @property
    def last_error(self) -> str | None:
        return self.transport.last_error


class RecordedDatasetSource:
    """Placeholder for replaying captured CSI files. Not wired yet."""

    source_id = "RecordedDatasetSource"

    def start(self) -> None:
        return

    def stop(self) -> None:
        return

    def latest(self) -> CsiSample | None:
        return None

    def connected(self) -> bool:
        return False


def frame_to_sample(frame: CsiFrame, source_id: str, timestamp: float | None = None) -> CsiSample:
    amps = list(frame.amps)
    return CsiSample(
        timestamp=time.time() if timestamp is None else timestamp,
        source_id=source_id,
        bssid=frame.mac,
        channel=None,
        rssi=frame.rssi,
        subcarrier_indices=list(range(len(amps))),
        amplitudes=amps,
        phases=None,
        seq=frame.seq,
    )


class CsiSourceHub:
    def __init__(self, esp32: Esp32CsiSource) -> None:
        self.laptop = LaptopWifiScanner()
        self.esp32 = esp32
        self.recorded = RecordedDatasetSource()
        self.sources: list[CsiSource] = [self.laptop, self.esp32, self.recorded]

    def start(self) -> None:
        for src in self.sources:
            src.start()

    def stop(self) -> None:
        for src in self.sources:
            src.stop()

    def pick(self) -> tuple[CsiSample | None, str]:
        for src in self.sources:
            sample = src.latest()
            if sample is not None and src.connected():
                return sample, src.source_id
        return None, "CSI source not connected"
