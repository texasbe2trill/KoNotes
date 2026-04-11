"""Model representing a connected Kobo device."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class KoboDevice(BaseModel):
    mount_point: Path
    db_path: Path
    device_name: str | None = None
    serial: str | None = None

    @property
    def label(self) -> str:
        return self.device_name or str(self.mount_point.name)
