"""
Real-widget coverage for Mission 020 — MainToolBar Actions Wiring.
MainToolBar's action_open/action_save are exercised by real
QAction.trigger() calls through a real MainWindow, proving the same
observable outcome as calling MainWindow.open_project()/save_project()
directly (see test_main_window_new_project.py) — not merely that a
.connect() line exists. action_run has no handler at all: it stays
visible, disabled, with an explanatory tooltip (same treatment as
DashboardPage.trainingButton, Mission 017). QFileDialog is patched
throughout: a real native picker would block the test process (same
lesson as Missions 014/015/016/017's modal dialogs).
"""

import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow

_app = QApplication.instance() or QApplication([])


class MainToolBarTest(unittest.TestCase):

    def setUp(self):
        self.window = MainWindow()
        self.addCleanup(self.window.close)

    # --- action_open ---

    def test_action_open_selected_folder_calls_workspace_manager_open(self):
        with patch(
            "src.ui.main_window.QFileDialog.getExistingDirectory",
            return_value="C:/SomeFolder",
        ), patch.object(self.window.workspace_manager, "open") as open_mock:
            open_mock.return_value = MagicMock()

            self.window.toolbar.action_open.trigger()

            open_mock.assert_called_once_with("C:/SomeFolder")

    def test_action_open_cancelled_never_calls_open(self):
        with patch(
            "src.ui.main_window.QFileDialog.getExistingDirectory",
            return_value="",
        ), patch.object(self.window.workspace_manager, "open") as open_mock:
            self.window.toolbar.action_open.trigger()

            open_mock.assert_not_called()

    # --- action_save ---

    def test_action_save_with_open_workspace_calls_workspace_manager_save(self):
        self.window.workspace_manager.current_workspace = MagicMock()

        with patch.object(self.window.workspace_manager, "save") as save_mock:
            self.window.toolbar.action_save.trigger()

            save_mock.assert_called_once()

    def test_action_save_without_workspace_shows_existing_status_message(self):
        with patch.object(self.window.workspace_manager, "save") as save_mock:
            self.window.toolbar.action_save.trigger()

            save_mock.assert_not_called()

        self.assertEqual(self.window.statusBar().currentMessage(), "Aucun projet ouvert")

    # --- action_run ---

    def test_action_run_is_disabled(self):
        self.assertFalse(self.window.toolbar.action_run.isEnabled())

    def test_action_run_tooltip_explains_unavailability(self):
        tooltip = self.window.toolbar.action_run.toolTip()

        self.assertIn("pas encore disponible", tooltip.lower())


if __name__ == "__main__":
    unittest.main()
