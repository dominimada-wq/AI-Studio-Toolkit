"""
Narrow coverage for Mission 031's pre-implementation verification 1 —
MainWindow reads Ollama's base_url/model_name exclusively from
ApplicationSettings, once at construction, exactly the same no-hot-reload
contract already established for ComfyUI (Mission 018,
test_main_window_comfyui_settings.py). Real MainWindow instances are
constructed, with ApplicationSettingsStorage.default_directory()
redirected to a temporary directory so the real %LOCALAPPDATA% is never
touched.
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


class MainWindowOllamaSettingsTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def test_main_window_uses_default_ollama_settings_when_none_configured(self):
        empty_dir = Path(self.tmp_dir) / "NoSettingsFile"

        with patch.object(
            ApplicationSettingsStorage, "default_directory", return_value=empty_dir
        ):
            window = MainWindow()
            self.addCleanup(window.close)

        # ApplicationSettings' own literal default (Mission 030), read
        # straight through — no fallback constant in main_window.py.
        self.assertEqual(window.ollama_engine._base_url, "http://127.0.0.1:11434")
        self.assertEqual(window.prompt_assistant_manager._model_name, "")

    def test_main_window_uses_configured_ollama_url_and_model_from_application_settings(self):
        configured_dir = Path(self.tmp_dir) / "ConfiguredSettings"
        ApplicationSettingsStorage.save(
            configured_dir,
            {
                "ollama_url": "http://192.168.1.50:11434",
                "ollama_model_name": "llama3.2:3b",
            },
        )

        with patch.object(
            ApplicationSettingsStorage, "default_directory", return_value=configured_dir
        ):
            window = MainWindow()
            self.addCleanup(window.close)

        self.assertEqual(window.ollama_engine._base_url, "http://192.168.1.50:11434")
        self.assertEqual(window.prompt_assistant_manager._model_name, "llama3.2:3b")

    def test_settings_change_after_construction_does_not_affect_the_already_built_engine(self):
        """
        Confirms the deliberate no-hot-reload contract explicitly
        (mirrors SettingsPage's own application_hint label): saving a
        new ollama_url via ApplicationSettingsManager after MainWindow
        was constructed must never retroactively change
        window.ollama_engine/window.prompt_assistant_manager — a
        restart is required, exactly like ComfyUI.
        """
        configured_dir = Path(self.tmp_dir) / "RuntimeChangeSettings"

        with patch.object(
            ApplicationSettingsStorage, "default_directory", return_value=configured_dir
        ):
            window = MainWindow()
            self.addCleanup(window.close)

            window.application_settings_manager.update(
                ollama_url="http://10.0.0.9:11434", ollama_model_name="mistral:latest"
            )

        self.assertEqual(window.ollama_engine._base_url, "http://127.0.0.1:11434")
        self.assertEqual(window.prompt_assistant_manager._model_name, "")


if __name__ == "__main__":
    unittest.main()
