from __future__ import annotations

import sys

from .base import RadioCollector
from .demo import DemoCollector


def create_collector(demo: bool = False, iface: str | None = None) -> RadioCollector:
    if demo:
        return DemoCollector()
    if sys.platform == "win32":
        from .windows import WindowsCollector

        return WindowsCollector(iface=iface)
    from .linux import LinuxCollector

    return LinuxCollector(iface=iface)
