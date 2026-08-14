"""
Narrow coverage for Mission 018 — MainWindow reads ComfyUI's base_url/
checkpoint_name exclusively from ApplicationSettings (the sole source
of truth as of this mission), never from a fallback constant of its
own (none exists anymore in main_window.py). Real MainWindow instances
are constructed, with ApplicationSettingsStorage.default_directory()
redirected to a temporary directory so the real %LOCALAPPDATA% is
never touched — same lesson as test_application_settings_roundtrip.py.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from src.infrastructure.storage.application_settings_storage import (
    ApplicationSettingsStorage,
)
from src.ui.main_window import MainWindow

_app = QApplication.instance() or QApplication([])


class MainWindowComfyUISettingsTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def test_main_window_uses_default_comfyui_settings_when_none_configured(self):
        empty_dir = Path(self.tmp_dir) / "NoSettingsFile"

        with patch.object(
            ApplicationSettingsStorage, "default_directory", return_value=empty_dir
        ):
            window = MainWindow()
            self.addCleanup(window.close)

        # No fallback constant left in MainWindow — this is
        # ApplicationSettings' own literal default (see
        # test_application_settings_domain_object_roundtrip_and_defaults),
        # read straight through.
        self.assertEqual(window.comfyui_engine._base_url, "http://127.0.0.1:8000")
        self.assertEqual(
            window.generation_manager._checkpoint_name,
            "v1-5-pruned-emaonly-fp16.safetensors",
        )

    def test_main_window_uses_configured_comfyui_url_and_checkpoint_from_application_settings(self):
        configured_dir = Path(self.tmp_dir) / "ConfiguredSettings"
        ApplicationSettingsStorage.save(
            configured_dir,
            {
                "comfyui_url": "http://192.168.1.50:8188",
                "comfyui_checkpoint_name": "sdxl_base.safetensors",
            },
        )

        with patch.object(
            ApplicationSettingsStorage, "default_directory", return_value=configured_dir
        ):
            window = MainWindow()
            self.addCleanup(window.close)

        self.assertEqual(window.comfyui_engine._base_url, "http://192.168.1.50:8188")
        self.assertEqual(
            window.generation_manager._checkpoint_name, "sdxl_base.safetensors"
        )


if __name__ == "__main__":
    unittest.main()
