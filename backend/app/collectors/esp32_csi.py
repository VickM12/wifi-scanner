from __future__ import annotations

import json
import socket
import threading
from typing import Callable

from ..models import CsiFrame


class CsiCollector:
    """UDP listener for ESP32 (or demo sender) CSI JSON datagrams."""

    def __init__(
        self,
        port: int = 5500,
        host: str = "0.0.0.0",
        on_frame: Callable[[CsiFrame], None] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.on_frame = on_frame
        self.latest: CsiFrame | None = None
        self.last_error: str | None = None
        self.packets = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="csi-udp", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        sock = self._sock
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=1.0)
        self._thread = None
        self._sock = None

    def set_port(self, port: int) -> None:
        if port == self.port and self._thread and self._thread.is_alive():
            return
        self.stop()
        self.port = port
        self.start()

    def _loop(self) -> None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.settimeout(0.5)
            self._sock = sock
            self.last_error = None
        except OSError as exc:
            self.last_error = f"CSI UDP bind {self.host}:{self.port} failed: {exc}"
            return

        while not self._stop.is_set():
            try:
                data, _addr = sock.recvfrom(65535)
            except TimeoutError:
                continue
            except OSError:
                if self._stop.is_set():
                    break
                continue
            frame = parse_csi_datagram(data)
            if frame is None:
                continue
            with self._lock:
                self.latest = frame
                self.packets += 1
            if self.on_frame:
                self.on_frame(frame)

        try:
            sock.close()
        except OSError:
            pass


def parse_csi_datagram(data: bytes) -> CsiFrame | None:
    text = data.decode("utf-8", errors="replace").strip()
    if not text:
        return None
    try:
        payload = json.loads(text.splitlines()[0])
    except json.JSONDecodeError:
        return None
    amps = payload.get("amps")
    if not isinstance(amps, list) or not amps:
        return None
    try:
        values = [float(x) for x in amps]
    except (TypeError, ValueError):
        return None
    rssi = payload.get("rssi")
    noise = payload.get("noise")
    try:
        seq = int(payload.get("seq", 0))
    except (TypeError, ValueError):
        seq = 0
    return CsiFrame(
        seq=seq,
        rssi=float(rssi) if rssi is not None else None,
        mac=str(payload.get("mac", "")),
        noise=float(noise) if noise is not None else None,
        amps=values,
        source=str(payload.get("source", "udp")),
    )
