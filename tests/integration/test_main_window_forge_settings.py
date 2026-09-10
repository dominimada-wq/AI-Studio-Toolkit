"""
Narrow coverage for Mission 108 — MainWindow reads Forge's own base_url
exclusively from ApplicationSettings.forge_url, same "sole source of
truth, no fallback constant, read once at startup" contract already
established for ComfyUI (Mission 018) and OneTrainer/Ollama. Real
MainWindow instances are constructed, with
ApplicationSettingsStorage.default_directory() redirected to a
temporary directory so the real %LOCALAPPDATA% is never touched — same
convention as test_main_window_comfyui_settings.py.
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


class MainWindowForgeSettingsTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def test_main_window_uses_default_forge_url_when_none_configured(self):
        empty_dir = Path(self.tmp_dir) / "NoSettingsFile"

        with patch.object(
            ApplicationSettingsStorage, "default_directory", return_value=empty_dir
        ):
            window = MainWindow()
            self.addCleanup(window.close)

        # ApplicationSettings' own literal default (see
        # test_application_settings_domain_object_roundtrip_and_defaults),
        # read straight through — no fallback constant in MainWindow.
        self.assertEqual(window.forge_engine._base_url, "http://127.0.0.1:7860")

    def test_main_window_uses_configured_forge_url_from_application_settings(self):
        configured_dir = Path(self.tmp_dir) / "ConfiguredSettings"
        ApplicationSettingsStorage.save(
            configured_dir,
            {"forge_url": "http://192.168.1.50:7860"},
        )

        with patch.object(
            ApplicationSettingsStorage, "default_directory", return_value=configured_dir
        ):
            window = MainWindow()
            self.addCleanup(window.close)

        self.assertEqual(window.forge_engine._base_url, "http://192.168.1.50:7860")

    def test_main_window_injects_both_engines_into_inference_page(self):
        # Mission 108 section 3.2: two explicit dependencies, the exact
        # same instances MainWindow itself holds — never a second
        # construction, never a dict/registry.
        empty_dir = Path(self.tmp_dir) / "NoSettingsFile2"

        with patch.object(
            ApplicationSettingsStorage, "default_directory", return_value=empty_dir
        ):
            window = MainWindow()
            self.addCleanup(window.close)

        self.assertIs(window.inference_page._comfyui_engine, window.comfyui_engine)
        self.assertIs(window.inference_page._forge_engine, window.forge_engine)


if __name__ == "__main__":
    unittest.main()
