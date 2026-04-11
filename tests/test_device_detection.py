"""Tests for device detection module."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from models.device import KoboDevice
from parser.device_detection import detect_devices


class TestKoboDevice:
    def test_label_uses_device_name(self):
        dev = KoboDevice(
            mount_point=Path("/Volumes/KOBOeReader"),
            db_path=Path("/Volumes/KOBOeReader/.kobo/KoboReader.sqlite"),
            device_name="KOBOeReader",
        )
        assert dev.label == "KOBOeReader"

    def test_label_fallback_to_mount_name(self):
        dev = KoboDevice(
            mount_point=Path("/Volumes/MyKobo"),
            db_path=Path("/Volumes/MyKobo/.kobo/KoboReader.sqlite"),
        )
        assert dev.label == "MyKobo"


class TestDetectDevices:
    def test_returns_list(self):
        # On a dev machine without a Kobo, should still return a list
        devices = detect_devices()
        assert isinstance(devices, list)

    def test_finds_mock_device(self, tmp_path):
        # Create a fake Kobo device mount
        kobo_dir = tmp_path / "KOBOeReader" / ".kobo"
        kobo_dir.mkdir(parents=True)
        db_file = kobo_dir / "KoboReader.sqlite"
        db_file.write_text("fake")

        mount_root = tmp_path
        with patch("parser.device_detection._MOUNT_ROOTS", {"Darwin": [mount_root]}):
            with patch("parser.device_detection.platform.system", return_value="Darwin"):
                devices = detect_devices()
                assert len(devices) == 1
                assert devices[0].device_name == "KOBOeReader"
                assert devices[0].db_path == db_file
