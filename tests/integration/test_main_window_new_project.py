"""
Narrow coverage for MainWindow.new_project()'s wiring to
NewProjectDialog (Mission 016) — the first test file touching
MainWindow directly, deliberately scoped to this one method only (no
general MainWindow test suite is introduced here). NewProjectDialog
itself is always patched: a real exec() would block the test process
(same lesson as Mission 014/015's modal dialogs) — this file validates
the wiring, not the dialog (see test_new_project_dialog.py for that).

Mission 069 extends this file with MainWindowConfirmContextChangeTest,
covering the new PromptsPage.confirm_context_change() guard wired into
both new_project() and open_project() — real Workspace/Character/Prompt
state on the real MainWindow, only the modal dialogs mocked.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from src.managers.workspace_manager import WorkspaceManager, WorkspaceManagerError
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


class MainWindowConfirmContextChangeTest(unittest.TestCase):
    """
    Mission 069: the PromptsPage.confirm_context_change() guard wired
    into MainWindow.new_project() and open_project() — must run after
    the picker is accepted but before workspace_manager.create()/open()
    replaces current_workspace. Real Workspace/Character/Prompt state on
    the real window; only the modal dialogs (NewProjectDialog,
    QFileDialog.getExistingDirectory, and PromptsPage's own internal
    Save/Discard/Cancel QMessageBox) are mocked to avoid blocking.
    """

    def setUp(self):
        self.window = MainWindow()
        self.addCleanup(self.window.close)

        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.old_folder = Path(self.tmp_dir) / "OldProject"
        self.new_folder = Path(self.tmp_dir) / "NewProject"

    def _make_dirty_prompt(self):
        self.window.workspace_manager.create(self.old_folder)
        character = self.window.character_manager.create("Aria")
        self.window.character_manager.select(character.character_id)
        prompt = self.window.prompt_manager.create("Master", text="original")
        self.window.prompt_manager.select(prompt.prompt_id)
        self.window.prompts_page.text_edit.setPlainText("edited draft, not saved")
        self.assertTrue(self.window.prompts_page._dirty)
        return prompt

    def _read_old_project_prompt_text(self):
        with open(self.old_folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        return aria["prompts"][0]["text"]

    @staticmethod
    def _mock_new_project_dialog(target_path):
        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Accepted
        dialog.target_path = target_path
        return dialog

    # ------------------------------------------------------------
    # new_project()
    # ------------------------------------------------------------

    def test_new_project_dirty_save_persists_into_old_workspace_then_switches(self):
        self._make_dirty_prompt()
        dialog = self._mock_new_project_dialog(self.new_folder)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.prompts_page, "_confirm_discard_before_switch",
                    return_value=QMessageBox.Save,
                ):
            self.window.new_project()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.new_folder)
        self.assertEqual(self._read_old_project_prompt_text(), "edited draft, not saved")

    def test_new_project_dirty_discard_switches_without_persisting(self):
        self._make_dirty_prompt()
        dialog = self._mock_new_project_dialog(self.new_folder)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.prompts_page, "_confirm_discard_before_switch",
                    return_value=QMessageBox.Discard,
                ):
            self.window.new_project()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.new_folder)
        self.assertEqual(self._read_old_project_prompt_text(), "original")

    def test_new_project_dirty_cancel_abandons_new_project_entirely(self):
        prompt = self._make_dirty_prompt()
        dialog = self._mock_new_project_dialog(self.new_folder)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.prompts_page, "_confirm_discard_before_switch",
                    return_value=QMessageBox.Cancel,
                ), patch.object(self.window.workspace_manager, "create") as create_mock:
            self.window.new_project()

            create_mock.assert_not_called()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.old_folder)
        self.assertTrue(self.window.prompts_page._dirty)
        self.assertEqual(self.window.prompts_page.text_edit.toPlainText(), "edited draft, not saved")
        self.assertEqual(self.window.prompt_manager.active_prompt_id, prompt.prompt_id)
        self.assertEqual(self._read_old_project_prompt_text(), "original")

        # Mission 079: closeEvent() now also consults confirm_context_change()
        # — this test's whole point is a real dirty draft surviving until
        # here, so leave that state untouched and only neutralize the
        # teardown close() itself (registered after setUp()'s, so it runs
        # first in LIFO order, before window.close() would otherwise show
        # a real, unmocked confirmation dialog).
        self.addCleanup(setattr, self.window.prompts_page, "_dirty", False)

    def test_new_project_guard_false_never_calls_workspace_manager_create(self):
        dialog = self._mock_new_project_dialog(self.new_folder)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.prompts_page, "confirm_context_change", return_value=False
                ), \
                patch.object(self.window.workspace_manager, "create") as create_mock:
            self.window.new_project()

            create_mock.assert_not_called()

    def test_new_project_picker_cancelled_never_calls_guard(self):
        dialog = self._mock_new_project_dialog(self.new_folder)
        dialog.exec.return_value = QDialog.Rejected

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(self.window.prompts_page, "confirm_context_change") as guard_mock:
            self.window.new_project()

            guard_mock.assert_not_called()

    def test_new_project_guard_runs_before_workspace_manager_create(self):
        dialog = self._mock_new_project_dialog(self.new_folder)
        order = []

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.prompts_page, "confirm_context_change",
                    side_effect=lambda: order.append("guard") or True,
                ), \
                patch.object(
                    self.window.workspace_manager, "create",
                    side_effect=lambda *a, **k: order.append("create"),
                ):
            self.window.new_project()

        self.assertEqual(order, ["guard", "create"])

    # ------------------------------------------------------------
    # open_project()
    # ------------------------------------------------------------

    def _precreate_new_folder_project(self):
        # A standalone, unwired WorkspaceManager — creating it via
        # self.window.workspace_manager would publish WORKSPACE_CREATED
        # and wipe the dirty draft through PromptsPage's own
        # reset_for_context_change() before open_project() is even
        # called. This only produces a valid project.json on disk for
        # self.window.workspace_manager.open() to load for real.
        WorkspaceManager().create(self.new_folder)

    def test_open_project_dirty_save_persists_into_old_workspace_then_switches(self):
        self._precreate_new_folder_project()
        self._make_dirty_prompt()

        with patch(
            "src.ui.main_window.QFileDialog.getExistingDirectory",
            return_value=str(self.new_folder),
        ), patch.object(
            self.window.prompts_page, "_confirm_discard_before_switch",
            return_value=QMessageBox.Save,
        ):
            self.window.open_project()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.new_folder)
        self.assertEqual(self._read_old_project_prompt_text(), "edited draft, not saved")

    def test_open_project_dirty_discard_switches_without_persisting(self):
        self._precreate_new_folder_project()
        self._make_dirty_prompt()

        with patch(
            "src.ui.main_window.QFileDialog.getExistingDirectory",
            return_value=str(self.new_folder),
        ), patch.object(
            self.window.prompts_page, "_confirm_discard_before_switch",
            return_value=QMessageBox.Discard,
        ):
            self.window.open_project()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.new_folder)
        self.assertEqual(self._read_old_project_prompt_text(), "original")

    def test_open_project_dirty_cancel_abandons_open_project_entirely(self):
        self._precreate_new_folder_project()
        prompt = self._make_dirty_prompt()

        with patch(
            "src.ui.main_window.QFileDialog.getExistingDirectory",
            return_value=str(self.new_folder),
        ), patch.object(
            self.window.prompts_page, "_confirm_discard_before_switch",
            return_value=QMessageBox.Cancel,
        ), patch.object(self.window.workspace_manager, "open") as open_mock:
            self.window.open_project()

            open_mock.assert_not_called()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.old_folder)
        self.assertTrue(self.window.prompts_page._dirty)
        self.assertEqual(self.window.prompts_page.text_edit.toPlainText(), "edited draft, not saved")
        self.assertEqual(self.window.prompt_manager.active_prompt_id, prompt.prompt_id)
        self.assertEqual(self._read_old_project_prompt_text(), "original")

        # Mission 079: same teardown neutralization as the new_project()
        # Cancel test above — see its comment for the full rationale.
        self.addCleanup(setattr, self.window.prompts_page, "_dirty", False)

    def test_open_project_guard_false_never_calls_workspace_manager_open(self):
        with patch(
            "src.ui.main_window.QFileDialog.getExistingDirectory",
            return_value=str(self.new_folder),
        ), patch.object(
            self.window.prompts_page, "confirm_context_change", return_value=False
        ), patch.object(self.window.workspace_manager, "open") as open_mock:
            self.window.open_project()

            open_mock.assert_not_called()

    def test_open_project_picker_cancelled_never_calls_guard(self):
        with patch(
            "src.ui.main_window.QFileDialog.getExistingDirectory",
            return_value="",
        ), patch.object(self.window.prompts_page, "confirm_context_change") as guard_mock:
            self.window.open_project()

            guard_mock.assert_not_called()

    def test_open_project_guard_runs_before_workspace_manager_open(self):
        order = []

        with patch(
            "src.ui.main_window.QFileDialog.getExistingDirectory",
            return_value=str(self.new_folder),
        ), patch.object(
            self.window.prompts_page, "confirm_context_change",
            side_effect=lambda: order.append("guard") or True,
        ), patch.object(
            self.window.workspace_manager, "open",
            side_effect=lambda *a, **k: order.append("open"),
        ):
            self.window.open_project()

        self.assertEqual(order, ["guard", "open"])


if __name__ == "__main__":
    unittest.main()
