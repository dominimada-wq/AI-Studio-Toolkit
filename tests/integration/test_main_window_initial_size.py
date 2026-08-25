"""
Mission 060 — MainWindow.__init__() no longer hard-codes resize(1700, 950)
unconditionally: the default is now bounded to the real screen's
availableGeometry() (the actually usable area, excluding the taskbar/
reserved zones — deliberately distinct from geometry() in every test
below, to prove the bound comes from the right one), falls back to
QApplication.primaryScreen() when screen() is None, and falls back to
the historical 1700x950 default when neither is available. Real
MainWindow instances are constructed, with
ApplicationSettingsStorage.default_directory() redirected to a
temporary directory so the real %LOCALAPPDATA% is never touched (same
pattern as test_main_window_comfyui_settings.py), and
QMainWindow.screen()/QApplication.primaryScreen() patched so the test
never depends on the resolution of the machine actually running it.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QMainWindow

from src.infrastructure.storage.application_settings_storage import (
    ApplicationSettingsStorage,
)
from src.ui.main_window import MainWindow

_app = QApplication.instance() or QApplication([])


def _fake_screen(available_width, available_height, geometry_width, geometry_height):
    # geometry() is deliberately different from availableGeometry() in
    # every helper call below, so a test that accidentally bounded the
    # window to geometry() instead of availableGeometry() would fail.
    screen = MagicMock()
    screen.availableGeometry.return_value = QRect(0, 0, available_width, available_height)
    screen.geometry.return_value = QRect(0, 0, geometry_width, geometry_height)
    return screen


class MainWindowInitialSizeTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.settings_dir = Path(self.tmp_dir) / "NoSettingsFile"
        self.settings_patcher = patch.object(
            ApplicationSettingsStorage, "default_directory", return_value=self.settings_dir
        )
        self.settings_patcher.start()
        self.addCleanup(self.settings_patcher.stop)

    def test_smaller_available_screen_bounds_width_and_height_to_available_geometry(self):
        screen = _fake_screen(
            available_width=1280, available_height=720,
            geometry_width=1280, geometry_height=800,
        )
        with patch.object(QMainWindow, "screen", return_value=screen):
            window = MainWindow()
            self.addCleanup(window.close)

        self.assertEqual(window.width(), 1280)
        self.assertEqual(window.height(), 720)

    def test_larger_available_screen_keeps_the_historical_default_size(self):
        screen = _fake_screen(
            available_width=1920, available_height=1080,
            geometry_width=1920, geometry_height=1200,
        )
        with patch.object(QMainWindow, "screen", return_value=screen):
            window = MainWindow()
            self.addCleanup(window.close)

        self.assertEqual(window.width(), 1700)
        self.assertEqual(window.height(), 950)

    def test_falls_back_to_primary_screen_when_screen_is_none(self):
        screen = _fake_screen(
            available_width=1366, available_height=768,
            geometry_width=1366, geometry_height=850,
        )
        with patch.object(QMainWindow, "screen", return_value=None), \
                patch.object(QApplication, "primaryScreen", return_value=screen):
            window = MainWindow()
            self.addCleanup(window.close)

        self.assertEqual(window.width(), 1366)
        self.assertEqual(window.height(), 768)

    def test_falls_back_to_historical_default_when_no_screen_is_available_at_all(self):
        with patch.object(QMainWindow, "screen", return_value=None), \
                patch.object(QApplication, "primaryScreen", return_value=None):
            # Must not raise despite neither screen() nor
            # primaryScreen() ever returning a usable QScreen.
            window = MainWindow()
            self.addCleanup(window.close)

        self.assertEqual(window.width(), 1700)
        self.assertEqual(window.height(), 950)

    def test_window_stays_freely_resizable_after_the_bounded_initial_size(self):
        screen = _fake_screen(
            available_width=1280, available_height=720,
            geometry_width=1280, geometry_height=800,
        )
        with patch.object(QMainWindow, "screen", return_value=screen):
            window = MainWindow()
            self.addCleanup(window.close)

        window.resize(640, 480)

        self.assertEqual(window.width(), 640)
        self.assertEqual(window.height(), 480)


if __name__ == "__main__":
    unittest.main()
