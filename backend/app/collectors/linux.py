from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from ..models import AccessPoint, LinkSample, WlanInterface
from ..rf import format_mac, freq_mhz_to_channel, normalize_rssi, quality_to_dbm
from .base import RadioCollector


def _run(args: list[str], timeout: float = 8.0) -> str:
    result = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0 and not result.stdout:
        raise RuntimeError((result.stderr or result.stdout or "command failed").strip())
    return result.stdout


class LinuxCollector(RadioCollector):
    def __init__(self, iface: str | None = None) -> None:
        self.iface = iface

    def list_interfaces(self) -> list[WlanInterface]:
        names = self._iface_names()
        linked = None
        try:
            sample = self.poll_link()
            linked = self.iface if sample else None
        except Exception:
            linked = None
        return [
            WlanInterface(id=name, name=name, connected=name == linked or (not linked and i == 0))
            for i, name in enumerate(names)
        ]

    def _iface_names(self) -> list[str]:
        found: list[str] = []
        sys_net = Path("/sys/class/net")
        if sys_net.is_dir():
            for entry in sorted(sys_net.iterdir()):
                if (entry / "wireless").exists() or (entry / "phy80211").exists():
                    found.append(entry.name)
        if found:
            return found
        if shutil.which("iw"):
            try:
                text = _run(["iw", "dev"])
            except (RuntimeError, FileNotFoundError, subprocess.TimeoutExpired):
                text = ""
            found = re.findall(r"Interface\s+(\S+)", text)
        return found

    def _pick_iface(self) -> str | None:
        names = self._iface_names()
        if self.iface and self.iface in names:
            return self.iface
        if self.iface:
            return self.iface
        return names[0] if names else None

    def poll_link(self) -> LinkSample | None:
        iface = self._pick_iface()
        if iface and shutil.which("iw"):
            try:
                text = _run(["iw", "dev", iface, "link"], timeout=2.0)
            except (RuntimeError, subprocess.TimeoutExpired):
                text = ""
            sample = _parse_iw_link(text, iface)
            if sample:
                self.status = f"linked {sample.ssid or sample.bssid}"
                self.last_error = None
                return sample
        sample = _parse_proc_wireless(iface)
        if sample:
            self.status = f"linked {sample.ssid or iface or 'wifi'}"
            self.last_error = None
            return sample
        self.status = "Wi-Fi not associated"
        return None

    def scan_aps(self) -> list[AccessPoint]:
        iface = self._pick_iface()
        linked = None
        try:
            link = self.poll_link()
            linked = link.bssid if link else None
        except Exception:
            linked = None

        if shutil.which("nmcli"):
            try:
                if iface:
                    try:
                        _run(["nmcli", "dev", "wifi", "rescan", "ifname", iface], timeout=4.0)
                    except (RuntimeError, subprocess.TimeoutExpired):
                        pass
                args = [
                    "nmcli",
                    "-t",
                    "-f",
                    "SSID,BSSID,CHAN,FREQ,SIGNAL,IN-USE,SECURITY",
                    "dev",
                    "wifi",
                    "list",
                ]
                if iface:
                    args.extend(["ifname", iface])
                text = _run(args, timeout=8.0)
                aps = _parse_nmcli(text, linked)
                if aps:
                    self.last_error = None
                    self.status = f"{len(aps)} BSS (nmcli)"
                    return aps
            except (RuntimeError, subprocess.TimeoutExpired) as exc:
                self.last_error = f"nmcli: {exc}"

        if iface and shutil.which("iw"):
            try:
                text = _run(["iw", "dev", iface, "scan"], timeout=12.0)
                aps = _parse_iw_scan(text, linked)
                if aps:
                    self.last_error = None
                    self.status = f"{len(aps)} BSS (iw)"
                    return aps
            except (RuntimeError, subprocess.TimeoutExpired) as exc:
                self.last_error = (
                    f"iw scan failed ({exc}). Try: sudo setcap cap_net_admin+ep $(command -v iw)"
                )
        if not self.last_error:
            self.last_error = "No nmcli/iw scan results. Install NetworkManager or iw."
        return []


def _parse_iw_link(text: str, iface: str | None) -> LinkSample | None:
    if "Not connected" in text or not text.strip():
        return None
    bssid_match = re.search(r"Connected to\s+([0-9a-fA-F:]{17})", text)
    ssid_match = re.search(r"SSID:\s*(.+)", text)
    signal_match = re.search(r"signal:\s*(-?\d+(?:\.\d+)?)", text)
    freq_match = re.search(r"freq:\s*(\d+(?:\.\d+)?)", text)
    if not (bssid_match and signal_match):
        return None
    rssi = normalize_rssi(float(signal_match.group(1)))
    if rssi is None:
        return None
    freq = float(freq_match.group(1)) if freq_match else None
    return LinkSample(
        bssid=format_mac(bssid_match.group(1)),
        ssid=(ssid_match.group(1).strip() if ssid_match else "") or iface or "(hidden)",
        rssi=rssi,
        frequency_mhz=freq,
        raw_rssi=rssi,
    )


def _parse_proc_wireless(iface: str | None) -> LinkSample | None:
    path = Path("/proc/net/wireless")
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[2:]:
        parts = line.replace(":", " ").split()
        if len(parts) < 4:
            continue
        name = parts[0]
        if iface and name != iface:
            continue
        try:
            level = float(parts[3])
        except ValueError:
            continue
        rssi = normalize_rssi(level)
        if rssi is None:
            continue
        return LinkSample(
            bssid="",
            ssid=name,
            rssi=rssi,
            raw_rssi=level,
        )
    return None


def _unescape_nmcli_field(value: str) -> str:
    return value.replace("\\:", ":").replace("\\\\", "\\")


def _parse_nmcli(text: str, linked: str | None) -> list[AccessPoint]:
    aps: list[AccessPoint] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        # nmcli -t escapes ":" as "\:" so split on unescaped colons.
        fields = re.split(r"(?<!\\):", raw_line)
        if len(fields) < 6:
            continue
        ssid = _unescape_nmcli_field(fields[0]) or "(hidden)"
        bssid = format_mac(_unescape_nmcli_field(fields[1]))
        if not bssid or bssid in seen:
            continue
        try:
            channel = int(float(fields[2] or 0))
        except ValueError:
            channel = 0
        try:
            freq = float(fields[3] or 0)
        except ValueError:
            freq = 0.0
        try:
            quality = float(fields[4] or 0)
        except ValueError:
            quality = 0.0
        in_use = fields[5].strip() == "*"
        if freq <= 0 and channel:
            # nmcli sometimes omits freq; infer a 2.4 default.
            freq = 2412 + (channel - 1) * 5 if channel <= 14 else 5000 + channel * 5
        _ch, band = freq_mhz_to_channel(freq) if freq else (channel, "unknown")
        rssi = quality_to_dbm(quality)
        aps.append(
            AccessPoint(
                ssid=ssid,
                bssid=bssid,
                rssi=rssi,
                channel=channel or _ch,
                frequency_mhz=freq,
                band=band,
                linked=in_use or (linked == bssid),
                quality=int(quality),
            )
        )
        seen.add(bssid)
    return aps


def _parse_iw_scan(text: str, linked: str | None) -> list[AccessPoint]:
    aps: list[AccessPoint] = []
    seen: set[str] = set()
    current: dict[str, str] = {}

    def flush() -> None:
        bssid = current.get("bssid")
        if not bssid or bssid in seen:
            current.clear()
            return
        rssi = normalize_rssi(float(current["rssi"])) if "rssi" in current else None
        if rssi is None:
            current.clear()
            return
        freq = float(current["freq"]) if "freq" in current else 0.0
        channel, band = freq_mhz_to_channel(freq) if freq else (0, "unknown")
        aps.append(
            AccessPoint(
                ssid=current.get("ssid") or "(hidden)",
                bssid=bssid,
                rssi=rssi,
                channel=channel,
                frequency_mhz=freq,
                band=band,
                linked=bssid == linked,
            )
        )
        seen.add(bssid)
        current.clear()

    for line in text.splitlines():
        bss = re.match(r"BSS\s+([0-9a-fA-F:]{17})", line)
        if bss:
            if current:
                flush()
            current["bssid"] = format_mac(bss.group(1))
            continue
        freq = re.search(r"freq:\s*(\d+(?:\.\d+)?)", line)
        if freq:
            current["freq"] = freq.group(1)
            continue
        signal = re.search(r"signal:\s*(-?\d+(?:\.\d+)?)", line)
        if signal:
            current["rssi"] = signal.group(1)
            continue
        ssid = re.search(r"SSID:\s*(.*)", line)
        if ssid and "ssid" not in current:
            current["ssid"] = ssid.group(1).strip()
    if current:
        flush()
    return aps
