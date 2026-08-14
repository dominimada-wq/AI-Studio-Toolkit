"""
Narrow coverage for MainWindow.new_project()'s wiring to
NewProjectDialog (Mission 016) — the first test file touching
MainWindow directly, deliberately scoped to this one method only (no
general MainWindow test suite is introduced here). NewProjectDialog
itself is always patched: a real exec() would block the test process
(same lesson as Mission 014/015's modal dialogs) — this file validates
the wiring, not the dialog (see test_new_project_dialog.py for that).
"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QDialog

from src.managers.workspace_manager import WorkspaceManagerError
from src.ui.main_window import MainWindow

_app = QApplication.instance() or QApplication([])


class MainWindowNewProjectTest(unittest.TestCase):

    def setUp(self):
        self.window = MainWindow()
        self.addCleanup(self.window.close)

    @staticmethod
    def _mock_dialog(accepted, target_path=None):
        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Accepted if accepted else QDialog.Rejected
        dialog.target_path = target_path
        return dialog

    def test_cancel_never_calls_workspace_manager_create(self):
        dialog = self._mock_dialog(accepted=False)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(self.window.workspace_manager, "create") as create_mock:
            self.window.new_project()

            create_mock.assert_not_called()

    def test_accept_calls_create_exactly_once_with_dialog_target_path(self):
        target_path = Path("C:/SomeParent/SomeProject")
        dialog = self._mock_dialog(accepted=True, target_path=target_path)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(self.window.workspace_manager, "create") as create_mock:
            self.window.new_project()

            create_mock.assert_called_once_with(target_path)

    def test_workspace_manager_error_is_shown_via_message_box(self):
        target_path = Path("C:/SomeParent/SomeProject")
        dialog = self._mock_dialog(accepted=True, target_path=target_path)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.workspace_manager,
                    "create",
                    side_effect=WorkspaceManagerError("boom"),
                ), \
                patch("src.ui.main_window.QMessageBox.critical") as critical_mock:
            self.window.new_project()

            critical_mock.assert_called_once()

    def test_open_project_and_save_project_are_unaffected(self):
        with patch(
            "src.ui.main_window.QFileDialog.getExistingDirectory",
            return_value="C:/SomeFolder",
        ), patch.object(self.window.workspace_manager, "open") as open_mock:
            open_mock.return_value = MagicMock()
            self.window.open_project()

            open_mock.assert_called_once_with("C:/SomeFolder")

        self.window.workspace_manager.current_workspace = MagicMock()

        with patch.object(self.window.workspace_manager, "save") as save_mock:
            self.window.save_project()

            save_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
