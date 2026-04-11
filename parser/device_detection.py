"""Detect connected Kobo devices by scanning mounted volumes.

Looks for the signature ``.kobo/KoboReader.sqlite`` file that Kobo devices
expose when connected via USB. Supports macOS (``/Volumes``), Linux
(``/media``, ``/mnt``, ``/run/media``), and Windows drive letters.
"""
from __future__ import annotations

import platform
import string
from pathlib import Path

from models.device import KoboDevice

_KOBO_DB_REL = Path(".kobo") / "KoboReader.sqlite"

# Mount-point roots to scan per platform
_MOUNT_ROOTS: dict[str, list[Path]] = {
    "Darwin": [Path("/Volumes")],
    "Linux": [Path("/media"), Path("/mnt"), Path("/run/media")],
}


def detect_devices() -> list[KoboDevice]:
    """Return a list of Kobo devices currently connected via USB."""
    system = platform.system()
    candidates: list[Path] = []

    if system == "Windows":
        for letter in string.ascii_uppercase:
            candidates.append(Path(f"{letter}:\\"))
    else:
        for root in _MOUNT_ROOTS.get(system, []):
            if root.is_dir():
                # Scan one level for direct mounts (/Volumes/KOBOeReader)
                try:
                    candidates.extend(p for p in root.iterdir() if p.is_dir())
                except PermissionError:
                    continue
                # Linux: /run/media/<user>/<mount>
                for child in root.iterdir():
                    if child.is_dir():
                        try:
                            candidates.extend(
                                p for p in child.iterdir() if p.is_dir()
                            )
                        except PermissionError:
                            continue

    devices: list[KoboDevice] = []
    seen: set[Path] = set()
    for mount in candidates:
        db_path = mount / _KOBO_DB_REL
        if db_path.is_file() and db_path not in seen:
            seen.add(db_path)
            devices.append(
                KoboDevice(
                    mount_point=mount,
                    db_path=db_path,
                    device_name=mount.name,
                )
            )

    return devices
