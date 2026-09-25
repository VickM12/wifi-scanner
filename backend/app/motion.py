from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .models import MotionResult
from .stats import motion_score, residual, rolling_mean, rolling_std, z_score


@dataclass
class RssiSample:
    t: float
    rssi: float


@dataclass
class Baseline:
    bssid: str
    mean: float
    sigma: float
    samples: int


@dataclass
class MotionConfig:
    sample_interval: float = 0.15
    baseline_window: float = 12.0
    motion_window: float = 1.5
    noise_floor: float = 0.4
    threshold: float = 0.35
    hold_s: float = 0.45


@dataclass
class MotionDetector:
    """Explainable RSSI motion detector: rolling mean/std, residual, z-score."""

    config: MotionConfig = field(default_factory=MotionConfig)
    samples: deque[RssiSample] = field(default_factory=deque)
    state: str = "STILL"
    state_changed_at: float = 0.0
    calibrating: bool = False
    calibrate_bssid: str | None = None
    calibrate_buffer: list[float] = field(default_factory=list)
    baselines: dict[str, Baseline] = field(default_factory=dict)

    def reset(self) -> None:
        self.samples.clear()
        self.state = "STILL"
        self.state_changed_at = 0.0
        self.calibrating = False
        self.calibrate_bssid = None
        self.calibrate_buffer.clear()

    def start_calibration(self, bssid: str) -> None:
        self.calibrating = True
        self.calibrate_bssid = bssid
        self.calibrate_buffer.clear()

    def stop_calibration(self) -> Baseline | None:
        self.calibrating = False
        bssid = self.calibrate_bssid
        buf = list(self.calibrate_buffer)
        self.calibrate_bssid = None
        self.calibrate_buffer.clear()
        if not bssid or len(buf) < 4:
            return None
        stored = Baseline(
            bssid=bssid,
            mean=rolling_mean(buf),
            sigma=max(rolling_std(buf), self.config.noise_floor),
            samples=len(buf),
        )
        self.baselines[bssid] = stored
        return stored

    def reset_baseline(self, bssid: str | None = None) -> None:
        if bssid:
            self.baselines.pop(bssid, None)
        else:
            self.baselines.clear()
        if self.calibrating and (bssid is None or bssid == self.calibrate_bssid):
            self.calibrating = False
            self.calibrate_bssid = None
            self.calibrate_buffer.clear()

    def baseline_for(self, bssid: str | None) -> Baseline | None:
        if not bssid:
            return None
        return self.baselines.get(bssid)

    def calibration_status(self, bssid: str | None) -> dict:
        stored = self.baseline_for(bssid)
        if self.calibrating:
            state = "calibrating"
            samples = len(self.calibrate_buffer)
            mean = rolling_mean(self.calibrate_buffer) if self.calibrate_buffer else None
            sigma = rolling_std(self.calibrate_buffer) if len(self.calibrate_buffer) >= 2 else None
        elif stored:
            state = "ready"
            samples = stored.samples
            mean = stored.mean
            sigma = stored.sigma
        else:
            state = "idle"
            samples = 0
            mean = None
            sigma = None
        return {
            "state": state,
            "bssid": self.calibrate_bssid if self.calibrating else (stored.bssid if stored else bssid),
            "baseline_rssi": mean,
            "noise_sigma": sigma,
            "samples": samples,
        }

    def push_rssi(self, t: float, rssi: float, bssid: str | None = None) -> MotionResult:
        self.samples.append(RssiSample(t, rssi))
        keep = max(self.config.baseline_window, self.config.motion_window) + 2.0
        while self.samples and t - self.samples[0].t > keep:
            self.samples.popleft()
        if self.calibrating and bssid and bssid == self.calibrate_bssid:
            self.calibrate_buffer.append(rssi)
        return self.evaluate(t, rssi, bssid)

    def evaluate(self, now: float, rssi: float, bssid: str | None = None) -> MotionResult:
        cfg = self.config
        baseline_vals = [s.rssi for s in self.samples if now - s.t <= cfg.baseline_window]
        motion_vals = [s.rssi for s in self.samples if now - s.t <= cfg.motion_window]
        mean = rolling_mean(baseline_vals) if baseline_vals else rssi
        std = rolling_std(baseline_vals)
        resid = residual(rssi, mean)
        stored = self.baseline_for(bssid)
        sigma = max(std, cfg.noise_floor)
        if stored:
            sigma = max(sigma, stored.sigma)
        z = z_score(resid, std, cfg.noise_floor)
        short_std = rolling_std(motion_vals)
        score = motion_score(abs(z), short_std, sigma, cfg.noise_floor)
        state = self._debounce(now, score, cfg.threshold)
        return MotionResult(
            score=score,
            rssi_score=score,
            csi_score=0.0,
            active=state == "MOTION",
            residual=resid,
            sample_count=len(baseline_vals),
            rssi=rssi,
            rolling_mean=mean,
            rolling_std=std,
            z_score=z,
            short_variance=short_std ** 2,
            state=state,
            baseline_rssi=stored.mean if stored else mean,
            noise_sigma=stored.sigma if stored else sigma,
        )

    def _debounce(self, now: float, score: float, threshold: float) -> str:
        desired = "STILL"
        if score >= threshold:
            desired = "MOTION"
        elif score >= threshold * 0.55:
            desired = "DISTURBANCE"

        current = self.state
        if current == "MOTION" and score >= threshold * 0.75:
            desired = "MOTION"
        elif current == "DISTURBANCE" and threshold * 0.35 <= score < threshold:
            desired = "DISTURBANCE"

        if desired != current:
            if self.state_changed_at == 0.0 or (now - self.state_changed_at) >= self.config.hold_s:
                self.state = desired
                self.state_changed_at = now
        elif self.state_changed_at == 0.0:
            self.state_changed_at = now
        return self.state
