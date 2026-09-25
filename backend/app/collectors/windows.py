from __future__ import annotations

import ctypes
import struct
from ctypes import wintypes
from typing import Any

from ..models import AccessPoint, LinkSample, WlanInterface
from ..rf import decode_ssid, format_mac, freq_khz_to_channel, normalize_rssi
from .base import RadioCollector

ERROR_SUCCESS = 0
WLAN_CLIENT_VERSION = 2
WLAN_INTF_OPCODE_CURRENT_CONNECTION = 7
WLAN_INTF_OPCODE_RSSI = 0x10000102
WLAN_INTERFACE_STATE_CONNECTED = 1
DOT11_BSS_TYPE_ANY = 3
BSS_LIST_HEADER = 8
BSS_ENTRY_SIZE = 360

wlanapi = ctypes.WinDLL("wlanapi.dll")


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    ]

    def as_str(self) -> str:
        return (
            f"{{{self.Data1:08x}-{self.Data2:04x}-{self.Data3:04x}-"
            f"{self.Data4[0]:02x}{self.Data4[1]:02x}-"
            f"{''.join(f'{b:02x}' for b in self.Data4[2:])}}}"
        )


class WLAN_INTERFACE_INFO(ctypes.Structure):
    _fields_ = [
        ("InterfaceGuid", GUID),
        ("strInterfaceDescription", wintypes.WCHAR * 256),
        ("isState", wintypes.DWORD),
    ]


class DOT11_SSID(ctypes.Structure):
    _fields_ = [
        ("uSSIDLength", wintypes.ULONG),
        ("ucSSID", ctypes.c_ubyte * 32),
    ]


class WLAN_ASSOCIATION_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("dot11Ssid", DOT11_SSID),
        ("dot11BssType", wintypes.DWORD),
        ("dot11Bssid", ctypes.c_ubyte * 6),
        ("dot11PhyType", wintypes.DWORD),
        ("uDot11PhyIndex", wintypes.ULONG),
        ("uChCenterFrequency", wintypes.ULONG),
        ("ulRxRate", wintypes.ULONG),
        ("ulTxRate", wintypes.ULONG),
    ]


class WLAN_SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("bSecurityEnabled", wintypes.BOOL),
        ("bOneXEnabled", wintypes.BOOL),
        ("dot11AuthAlgorithm", wintypes.DWORD),
        ("dot11CipherAlgorithm", wintypes.DWORD),
    ]


class WLAN_CONNECTION_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("isState", wintypes.DWORD),
        ("wlanConnectionMode", wintypes.DWORD),
        ("strProfileName", wintypes.WCHAR * 256),
        ("wlanAssociationAttributes", WLAN_ASSOCIATION_ATTRIBUTES),
        ("wlanSecurityAttributes", WLAN_SECURITY_ATTRIBUTES),
    ]


wlanapi.WlanOpenHandle.argtypes = [
    wintypes.DWORD,
    wintypes.LPVOID,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.HANDLE),
]
wlanapi.WlanOpenHandle.restype = wintypes.DWORD

wlanapi.WlanCloseHandle.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
wlanapi.WlanCloseHandle.restype = wintypes.DWORD

wlanapi.WlanEnumInterfaces.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    ctypes.POINTER(ctypes.c_void_p),
]
wlanapi.WlanEnumInterfaces.restype = wintypes.DWORD

wlanapi.WlanScan.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(GUID),
    wintypes.LPVOID,
    wintypes.LPVOID,
    wintypes.LPVOID,
]
wlanapi.WlanScan.restype = wintypes.DWORD

wlanapi.WlanGetNetworkBssList.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(GUID),
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.BOOL,
    wintypes.LPVOID,
    ctypes.POINTER(ctypes.c_void_p),
]
wlanapi.WlanGetNetworkBssList.restype = wintypes.DWORD

wlanapi.WlanQueryInterface.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(GUID),
    wintypes.DWORD,
    wintypes.LPVOID,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(ctypes.c_void_p),
    ctypes.POINTER(wintypes.DWORD),
]
wlanapi.WlanQueryInterface.restype = wintypes.DWORD

wlanapi.WlanFreeMemory.argtypes = [wintypes.LPVOID]
wlanapi.WlanFreeMemory.restype = None


def _sanitize_mhz(raw: int | float) -> float | None:
    value = float(raw)
    if value > 20_000:
        value = value / 1000.0
    if 2400 <= value <= 7200:
        return value
    return None


def _guid_from_string(value: str) -> GUID:
    cleaned = value.strip().strip("{}")
    parts = cleaned.split("-")
    guid = GUID()
    guid.Data1 = int(parts[0], 16)
    guid.Data2 = int(parts[1], 16)
    guid.Data3 = int(parts[2], 16)
    rest = parts[3] + parts[4]
    for i in range(8):
        guid.Data4[i] = int(rest[i * 2 : i * 2 + 2], 16)
    return guid


def _parse_bss_entry(buf: bytes, offset: int) -> AccessPoint | None:
    if offset + BSS_ENTRY_SIZE > len(buf):
        return None
    ssid_len = struct.unpack_from("<I", buf, offset)[0]
    ssid = decode_ssid(buf[offset + 4 : offset + 4 + min(ssid_len, 32)])
    bssid = format_mac(buf[offset + 40 : offset + 46])
    rssi = struct.unpack_from("<i", buf, offset + 56)[0]
    quality = struct.unpack_from("<I", buf, offset + 60)[0]
    freq_khz = struct.unpack_from("<I", buf, offset + 92)[0]
    channel, band = freq_khz_to_channel(freq_khz)
    mhz = freq_khz / 1000.0 if freq_khz > 20_000 else float(freq_khz)
    dbm = normalize_rssi(rssi)
    if dbm is None:
        return None
    return AccessPoint(
        ssid=ssid or "(hidden)",
        bssid=bssid,
        rssi=dbm,
        channel=channel,
        frequency_mhz=mhz,
        band=band,
        quality=int(quality) if quality <= 100 else None,
    )


class WindowsCollector(RadioCollector):
    def __init__(self, iface: str | None = None) -> None:
        self.iface = iface
        self._handle: wintypes.HANDLE | None = None
        self._scan_hint: str | None = None
        self._last_link_rssi: float | None = None
        self._last_link_freq: float | None = None
        self._open()

    def _open(self) -> None:
        negotiated = wintypes.DWORD()
        handle = wintypes.HANDLE()
        err = wlanapi.WlanOpenHandle(
            WLAN_CLIENT_VERSION, None, ctypes.byref(negotiated), ctypes.byref(handle)
        )
        if err != ERROR_SUCCESS:
            self.last_error = f"WlanOpenHandle failed ({err})"
            return
        self._handle = handle
        self.last_error = None

    def close(self) -> None:
        if self._handle:
            wlanapi.WlanCloseHandle(self._handle, None)
            self._handle = None

    def _require_handle(self) -> wintypes.HANDLE:
        if not self._handle:
            self._open()
        if not self._handle:
            raise RuntimeError(self.last_error or "WLAN handle unavailable")
        return self._handle

    def _enum_raw(self) -> list[tuple[GUID, str, int]]:
        handle = self._require_handle()
        ptr = ctypes.c_void_p()
        err = wlanapi.WlanEnumInterfaces(handle, None, ctypes.byref(ptr))
        if err != ERROR_SUCCESS or not ptr.value:
            self.last_error = f"WlanEnumInterfaces failed ({err})"
            return []
        try:
            count = ctypes.cast(ptr, ctypes.POINTER(wintypes.DWORD))[0]
            header = 8
            info_size = ctypes.sizeof(WLAN_INTERFACE_INFO)
            items: list[tuple[GUID, str, int]] = []
            for i in range(count):
                info = WLAN_INTERFACE_INFO.from_address(ptr.value + header + i * info_size)
                items.append((info.InterfaceGuid, info.strInterfaceDescription, int(info.isState)))
            return items
        finally:
            wlanapi.WlanFreeMemory(ptr)

    def list_interfaces(self) -> list[WlanInterface]:
        try:
            return [
                WlanInterface(
                    id=guid.as_str(),
                    name=name,
                    connected=state == WLAN_INTERFACE_STATE_CONNECTED,
                )
                for guid, name, state in self._enum_raw()
            ]
        except RuntimeError as exc:
            self.last_error = str(exc)
            return []

    def _pick_guid(self) -> GUID | None:
        items = self._enum_raw()
        if not items:
            return None
        if self.iface:
            wanted = self.iface.lower()
            for guid, name, _state in items:
                if guid.as_str().lower() == wanted or name.lower() == wanted:
                    return guid
        connected = [item for item in items if item[2] == WLAN_INTERFACE_STATE_CONNECTED]
        return (connected or items)[0][0]

    def _query(self, guid: GUID, opcode: int) -> tuple[int, ctypes.c_void_p, int]:
        handle = self._require_handle()
        size = wintypes.DWORD()
        data = ctypes.c_void_p()
        err = wlanapi.WlanQueryInterface(
            handle,
            ctypes.byref(guid),
            opcode,
            None,
            ctypes.byref(size),
            ctypes.byref(data),
            None,
        )
        return err, data, int(size.value)

    def _connection(self, guid: GUID) -> dict[str, Any] | None:
        err, data, _size = self._query(guid, WLAN_INTF_OPCODE_CURRENT_CONNECTION)
        if err != ERROR_SUCCESS or not data.value:
            return None
        try:
            attrs = WLAN_CONNECTION_ATTRIBUTES.from_address(data.value)
            assoc = attrs.wlanAssociationAttributes
            ssid = decode_ssid(bytes(assoc.dot11Ssid.ucSSID), int(assoc.dot11Ssid.uSSIDLength))
            return {
                "ssid": ssid,
                "bssid": format_mac(bytes(assoc.dot11Bssid)),
                "freq_khz": int(assoc.uChCenterFrequency),
                "state": int(attrs.isState),
            }
        finally:
            wlanapi.WlanFreeMemory(data)

    def _query_rssi(self, guid: GUID) -> float | None:
        err, data, _size = self._query(guid, WLAN_INTF_OPCODE_RSSI)
        if err != ERROR_SUCCESS or not data.value:
            return None
        try:
            raw = ctypes.cast(data, ctypes.POINTER(ctypes.c_long)).contents.value
            return normalize_rssi(raw)
        finally:
            wlanapi.WlanFreeMemory(data)

    def poll_link(self) -> LinkSample | None:
        try:
            guid = self._pick_guid()
            if guid is None:
                self.status = "no WLAN interface"
                return None
            conn = self._connection(guid)
            if not conn or conn["state"] != WLAN_INTERFACE_STATE_CONNECTED:
                self.status = "Wi-Fi not associated"
                return None
            rssi = self._query_rssi(guid)
            if rssi is None:
                rssi = self._last_link_rssi
            if rssi is None:
                self.status = "RSSI opcode unavailable"
                return None
            mhz = _sanitize_mhz(conn["freq_khz"]) or self._last_link_freq
            self.status = f"linked {conn['ssid'] or conn['bssid']}"
            self.last_error = None
            return LinkSample(
                bssid=conn["bssid"],
                ssid=conn["ssid"] or "(hidden)",
                rssi=rssi,
                frequency_mhz=mhz,
                raw_rssi=rssi,
            )
        except RuntimeError as exc:
            self.last_error = str(exc)
            return None

    def scan_aps(self) -> list[AccessPoint]:
        try:
            guid = self._pick_guid()
            if guid is None:
                return []
            handle = self._require_handle()
            scan_err = wlanapi.WlanScan(handle, ctypes.byref(guid), None, None, None)
            if scan_err not in (ERROR_SUCCESS, 1617):  # 1617 = already scanning-ish on some builds
                if scan_err in (5, 1008, 1168):
                    self.last_error = (
                        "Wi-Fi scan blocked. Enable Settings > Privacy > Location "
                        "and allow desktop apps to use location."
                    )
                    self._scan_hint = self.last_error
                elif not self._scan_hint:
                    self.last_error = f"WlanScan failed ({scan_err})"

            ptr = ctypes.c_void_p()
            err = wlanapi.WlanGetNetworkBssList(
                handle,
                ctypes.byref(guid),
                None,
                DOT11_BSS_TYPE_ANY,
                False,
                None,
                ctypes.byref(ptr),
            )
            if err != ERROR_SUCCESS or not ptr.value:
                if err in (5, 1008):
                    self.last_error = (
                        "Wi-Fi BSS list blocked. Enable Windows Location for desktop apps."
                    )
                elif not self.last_error:
                    self.last_error = f"WlanGetNetworkBssList failed ({err})"
                return []

            try:
                total_size = ctypes.cast(ptr, ctypes.POINTER(wintypes.DWORD))[0]
                count = ctypes.cast(ptr, ctypes.POINTER(wintypes.DWORD))[1]
                buf = ctypes.string_at(ptr.value, total_size)
                conn = self._connection(guid)
                linked = (conn or {}).get("bssid")
                aps: list[AccessPoint] = []
                seen: set[str] = set()
                stride = BSS_ENTRY_SIZE
                if count > 0 and total_size > BSS_LIST_HEADER:
                    guess = (total_size - BSS_LIST_HEADER) // count
                    if 300 <= guess <= 400:
                        stride = guess
                for i in range(count):
                    ap = _parse_bss_entry(buf, BSS_LIST_HEADER + i * stride)
                    if ap is None or ap.bssid in seen:
                        continue
                    ap.linked = bool(linked) and ap.bssid == linked
                    seen.add(ap.bssid)
                    aps.append(ap)
                if aps:
                    self.last_error = None
                    self.status = f"{len(aps)} BSS"
                    linked_ap = next((ap for ap in aps if ap.linked), None)
                    if linked_ap:
                        self._last_link_rssi = linked_ap.rssi
                        self._last_link_freq = linked_ap.frequency_mhz
                return aps
            finally:
                wlanapi.WlanFreeMemory(ptr)
        except RuntimeError as exc:
            self.last_error = str(exc)
            return []
