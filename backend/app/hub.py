from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from copy import deepcopy
from pathlib import Path

from fastapi import WebSocket

from .collectors import create_collector
from .collectors.base import RadioCollector
from .csi_sources import CsiSourceHub, Esp32CsiSource
from .models import AccessPoint, AppSettings, LinkSample, MotionResult, Snapshot
from .motion import MotionConfig, MotionDetector
from .local_config import load_local, save_local
from .nodes import NodeRegistry, build_node_report, default_node_id, lan_addresses
from .recording import ExperimentRecorder
from .rf import freq_mhz_to_channel


RECORDINGS_DIR = Path(__file__).resolve().parents[2] / "recordings"
AP_HOLD_S = 20.0
SMOOTH_ALPHA = 0.35


class RadarHub:
    def __init__(self) -> None:
        self.settings = AppSettings()
        self.motion = MotionDetector(config=self._motion_config())
        self.csi_hub = CsiSourceHub(Esp32CsiSource(port=self.settings.csi_port))
        self.recorder = ExperimentRecorder(RECORDINGS_DIR)
        self.collector: RadioCollector = create_collector(demo=False)
        self.aps: list[AccessPoint] = []
        self.interfaces = []
        self._ap_cache: dict[str, AccessPoint] = {}
        self._rssi_hist: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=8))
        self._smoothed: dict[str, float] = {}
        self._prev_rssi: dict[str, float] = {}
        self._link: LinkSample | None = None
        self._last_motion: MotionResult | None = None
        self.clients: set[WebSocket] = set()
        self.registry = NodeRegistry()
        self.listen_host = "127.0.0.1"
        self.listen_port = 8765
        self.push_error: str | None = None
        self.settings.node_id = default_node_id()
        self._apply_local(load_local())
        self._lock = asyncio.Lock()
        self._tasks: list[asyncio.Task] = []
        self._started = False

    def _motion_config(self) -> MotionConfig:
        s = self.settings
        return MotionConfig(
            sample_interval=s.sample_interval,
            baseline_window=s.baseline_window,
            motion_window=s.motion_window,
            noise_floor=s.noise_floor,
            threshold=s.threshold,
        )

    def _sync_motion_config(self) -> None:
        self.motion.config = self._motion_config()

    def _apply_local(self, data: dict) -> None:
        if data.get("node_id"):
            self.settings.node_id = str(data["node_id"])
        if "hub_url" in data:
            url = (data.get("hub_url") or "").strip().rstrip("/")
            self.settings.hub_url = url or None
        if "share_token" in data and data["share_token"] is not None:
            self.settings.share_token = str(data["share_token"])
        if "push_to_hub" in data and data["push_to_hub"] is not None:
            self.settings.push_to_hub = bool(data["push_to_hub"])

    def persist_local(self) -> None:
        save_local(self.settings)

    async def start(self) -> None:
        if self._started:
            return
        self.csi_hub.start()
        self._tasks = [
            asyncio.create_task(self._link_loop(), name="link-loop"),
            asyncio.create_task(self._scan_loop(), name="scan-loop"),
            asyncio.create_task(self._broadcast_loop(), name="ws-loop"),
            asyncio.create_task(self._push_loop(), name="node-push"),
        ]
        self._started = True

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        self.recorder.stop()
        self.csi_hub.stop()
        self.collector.close()
        self._started = False

    async def apply_settings(self, **changes) -> AppSettings:
        async with self._lock:
            rebuild = False
            if "running" in changes and changes["running"] is not None:
                self.settings.running = bool(changes["running"])
            if "demo" in changes and changes["demo"] is not None:
                demo = bool(changes["demo"])
                if demo != self.settings.demo:
                    self.settings.demo = demo
                    rebuild = True
            if "threshold" in changes and changes["threshold"] is not None:
                self.settings.threshold = float(changes["threshold"])
            if "sample_interval" in changes and changes["sample_interval"] is not None:
                self.settings.sample_interval = float(changes["sample_interval"])
            if "baseline_window" in changes and changes["baseline_window"] is not None:
                self.settings.baseline_window = float(changes["baseline_window"])
            if "motion_window" in changes and changes["motion_window"] is not None:
                self.settings.motion_window = float(changes["motion_window"])
            if "noise_floor" in changes and changes["noise_floor"] is not None:
                self.settings.noise_floor = float(changes["noise_floor"])
            if "iface" in changes:
                iface = changes["iface"] or None
                if iface != self.settings.iface:
                    self.settings.iface = iface
                    rebuild = True
            if "csi_port" in changes and changes["csi_port"] is not None:
                port = int(changes["csi_port"])
                if port != self.settings.csi_port:
                    self.settings.csi_port = port
                    self.csi_hub.esp32.set_port(port)
            if "node_id" in changes and changes["node_id"] is not None:
                name = str(changes["node_id"]).strip()
                if name:
                    self.settings.node_id = name
            if "hub_url" in changes:
                url = (changes["hub_url"] or "").strip().rstrip("/")
                self.settings.hub_url = url or None
            if "share_token" in changes and changes["share_token"] is not None:
                self.settings.share_token = str(changes["share_token"])
            if "push_to_hub" in changes and changes["push_to_hub"] is not None:
                self.settings.push_to_hub = bool(changes["push_to_hub"])
            self._sync_motion_config()
            self.persist_local()
            if rebuild:
                self.collector.close()
                self.collector = create_collector(
                    demo=self.settings.demo, iface=self.settings.iface
                )
                self.motion.reset()
                self.aps = []
                self._ap_cache.clear()
                self._rssi_hist.clear()
                self._prev_rssi.clear()
                self._smoothed.clear()
        return self.settings

    async def calibrate(self, action: str) -> dict:
        bssid = self._link.bssid if self._link else None
        async with self._lock:
            if action == "start":
                if not bssid:
                    return self.motion.calibration_status(None)
                self.motion.start_calibration(bssid)
            elif action == "stop":
                self.motion.stop_calibration()
            elif action == "reset":
                self.motion.reset_baseline(bssid)
        return self.motion.calibration_status(bssid)

    async def record(self, action: str, label: str = "empty_room", fmt: str = "csv") -> dict:
        now = time.time()
        async with self._lock:
            if action == "start":
                self.recorder.start(label, fmt, now)
            elif action == "stop":
                self.recorder.stop()
        return self.recorder.status(now)

    def settings_dict(self) -> dict:
        s = self.settings
        return {
            "running": s.running,
            "demo": s.demo,
            "threshold": s.threshold,
            "iface": s.iface,
            "csi_port": s.csi_port,
            "sample_interval": s.sample_interval,
            "baseline_window": s.baseline_window,
            "motion_window": s.motion_window,
            "noise_floor": s.noise_floor,
            "node_id": s.node_id,
            "hub_url": s.hub_url,
            "share_token": s.share_token,
            "push_to_hub": s.push_to_hub,
        }

    def token_ok(self, token: str | None) -> bool:
        expected = self.settings.share_token
        if not expected:
            return True
        return (token or "") == expected

    def ingest_node(self, report: dict, token: str | None = None) -> dict:
        if not self.token_ok(token):
            raise PermissionError("share token mismatch")
        return self.registry.ingest(report)

    def local_report(self, now: float | None = None) -> dict:
        stamp = now if now is not None else time.time()
        motion = self._last_motion.to_dict() if self._last_motion else None
        return build_node_report(
            node_id=self.settings.node_id or default_node_id(),
            t=stamp,
            link=self._link.to_dict() if self._link else None,
            motion=motion,
            aps=[ap.to_dict() for ap in self.aps],
            position=None,
            local=True,
        )

    def snapshot(self) -> Snapshot:
        now = time.time()
        csi, csi_status = self.csi_hub.pick()
        if csi is None:
            csi_status = "CSI source not connected"
        motion = self._last_motion
        if motion is None:
            motion = MotionResult(score=0.0, rssi_score=0.0, csi_score=0.0, active=False)
        status = self.collector.status
        error = self.collector.last_error or self.csi_hub.esp32.last_error or self.push_error
        if not self.settings.running:
            status = "paused"
        bssid = self._link.bssid if self._link else None
        local = self.local_report(now)
        remotes = [node for node in self.registry.remote_list(now) if node.get("id") != local["id"]]
        return Snapshot(
            t=now,
            link=self._link,
            aps=list(self.aps),
            motion=motion,
            csi=csi,
            interfaces=list(self.interfaces),
            settings=self.settings_dict(),
            status=status,
            error=error,
            calibration=self.motion.calibration_status(bssid),
            recording=self.recorder.status(now),
            csi_status=csi_status,
            nodes=[local, *remotes],
            network={
                "listen_host": self.listen_host,
                "listen_port": self.listen_port,
                "lan_ips": lan_addresses(),
                "lan_open": self.listen_host in ("0.0.0.0", "::"),
            },
        )

    async def register(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)

    def unregister(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def _link_loop(self) -> None:
        while True:
            try:
                interval = max(0.05, self.settings.sample_interval)
                if self.settings.running:
                    link = await asyncio.to_thread(self.collector.poll_link)
                    now = time.time()
                    async with self._lock:
                        if link is not None:
                            link = self._enrich_link(link)
                            self._link = link
                            result = self.motion.push_rssi(now, link.rssi, link.bssid)
                            self._last_motion = result
                            if self.recorder.active:
                                self.recorder.append(
                                    {
                                        "timestamp": now,
                                        "ssid": link.ssid,
                                        "bssid": link.bssid,
                                        "channel": link.channel,
                                        "band": link.band,
                                        "rssi": link.rssi,
                                        "rolling_mean": result.rolling_mean,
                                        "rolling_std": result.rolling_std,
                                        "residual": result.residual,
                                        "z_score": result.z_score,
                                        "motion_score": result.score,
                                        "label": self.recorder.label,
                                    }
                                )
                        else:
                            self._link = None
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(0.5)

    async def _scan_loop(self) -> None:
        while True:
            try:
                if self.settings.running:
                    aps = await asyncio.to_thread(self.collector.scan_aps)
                    ifaces = await asyncio.to_thread(self.collector.list_interfaces)
                    async with self._lock:
                        self.aps = self._annotate(aps, time.time())
                        self.interfaces = ifaces
                await asyncio.sleep(2.5)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(2.0)

    async def _broadcast_loop(self) -> None:
        while True:
            try:
                payload = self.snapshot().to_dict()
                dead: list[WebSocket] = []
                for ws in list(self.clients):
                    try:
                        await ws.send_json(payload)
                    except Exception:
                        dead.append(ws)
                for ws in dead:
                    self.unregister(ws)
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(0.25)

    async def _push_loop(self) -> None:
        while True:
            try:
                should = (
                    self.settings.push_to_hub
                    and self.settings.hub_url
                    and self.settings.running
                )
                if should:
                    report = self.local_report()
                    url = f"{self.settings.hub_url.rstrip('/')}/api/nodes/ingest"
                    await asyncio.to_thread(self._post_report, url, report)
                await asyncio.sleep(max(0.3, self.settings.sample_interval))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.push_error = f"hub push failed: {exc}"
                await asyncio.sleep(1.0)

    def _post_report(self, url: str, report: dict) -> None:
        import json
        from urllib.error import HTTPError, URLError
        from urllib.request import Request, urlopen

        payload = {"token": self.settings.share_token, "node": {**report, "local": False}}
        req = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=2.0) as resp:
                resp.read()
            self.push_error = None
        except HTTPError as exc:
            self.push_error = f"hub push HTTP {exc.code}"
        except URLError as exc:
            self.push_error = f"hub push failed: {exc.reason}"

    def _enrich_link(self, link: LinkSample) -> LinkSample:
        match = next((ap for ap in self.aps if ap.bssid == link.bssid), None)
        if match:
            if not link.channel:
                link.channel = match.channel
            if not link.band:
                link.band = match.band
            if not link.frequency_mhz:
                link.frequency_mhz = match.frequency_mhz
        elif link.frequency_mhz:
            ch, band = freq_mhz_to_channel(link.frequency_mhz)
            link.channel = link.channel or ch
            link.band = link.band or band
        return link

    def _annotate(self, aps: list[AccessPoint], now: float) -> list[AccessPoint]:
        linked = self._link.bssid if self._link else None
        seen: set[str] = set()
        for ap in aps:
            item = deepcopy(ap)
            if linked and item.bssid == linked:
                item.linked = True
            prev = self._prev_rssi.get(item.bssid)
            item.delta_rssi = None if prev is None else round(item.rssi - prev, 2)
            self._prev_rssi[item.bssid] = item.rssi
            hist = self._rssi_hist[item.bssid]
            hist.append(item.rssi)
            if len(hist) >= 3:
                mean = sum(hist) / len(hist)
                item.variance = sum((x - mean) ** 2 for x in hist) / (len(hist) - 1)
            prev_s = self._smoothed.get(item.bssid, item.rssi)
            smoothed = SMOOTH_ALPHA * item.rssi + (1.0 - SMOOTH_ALPHA) * prev_s
            self._smoothed[item.bssid] = smoothed
            item.smoothed_rssi = round(smoothed, 2)
            item.last_seen = now
            self._ap_cache[item.bssid] = item
            seen.add(item.bssid)

        expired = [
            bssid
            for bssid, ap in self._ap_cache.items()
            if now - (ap.last_seen or 0) > AP_HOLD_S
        ]
        for bssid in expired:
            self._ap_cache.pop(bssid, None)

        annotated = list(self._ap_cache.values())
        for item in annotated:
            if linked and item.bssid == linked:
                item.linked = True
        annotated.sort(key=lambda a: (a.linked, a.rssi), reverse=True)
        return annotated


hub = RadarHub()
