from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import AccessPoint, LinkSample, WlanInterface


class RadioCollector(ABC):
    last_error: str | None = None
    status: str = ""

    @abstractmethod
    def list_interfaces(self) -> list[WlanInterface]:
        raise NotImplementedError

    @abstractmethod
    def scan_aps(self) -> list[AccessPoint]:
        raise NotImplementedError

    @abstractmethod
    def poll_link(self) -> LinkSample | None:
        raise NotImplementedError

    def close(self) -> None:
        return
