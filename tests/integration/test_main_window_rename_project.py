"""
Narrow coverage for MainWindow.rename_project()'s wiring to
RenameProjectDialog/WorkspaceManager.rename() (Mission 027), and for the
WORKSPACE_RENAMED addition to InferencePage's pending-result invalidation
wiring — mirrors test_main_window_new_project.py exactly:
RenameProjectDialog is always patched (a real exec() would block the
test process), this file validates the wiring, not the dialog itself
(see test_rename_project_dialog.py for that).
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QDialog

from src.managers.workspace_manager import (
    WorkspaceManagerError,
    WorkspaceRenamePermissionError,
)
from src.ui.main_window import MainWindow

_app = QApplication.instance() or QApplication([])


class MainWindowRenameProjectTest(unittest.TestCase):

    def setUp(self):
        self.window = MainWindow()
        self.addCleanup(self.window.close)

        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

    @staticmethod
    def _mock_dialog(accepted, new_name=None):
        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Accepted if accepted else QDialog.Rejected
        dialog.new_name = new_name
        return dialog

    def test_no_workspace_open_never_opens_dialog(self):
        with patch("src.ui.main_window.RenameProjectDialog") as dialog_cls:
            self.window.rename_project()

            dialog_cls.assert_not_called()

    def test_cancel_never_calls_workspace_manager_rename(self):
        self.window.workspace_manager.create(self.folder)
        dialog = self._mock_dialog(accepted=False)

        with patch("src.ui.main_window.RenameProjectDialog", return_value=dialog), \
                patch.object(self.window.workspace_manager, "rename") as rename_mock:
            self.window.rename_project()

            rename_mock.assert_not_called()

    def test_accept_calls_rename_exactly_once_with_dialog_new_name(self):
        self.window.workspace_manager.create(self.folder)
        dialog = self._mock_dialog(accepted=True, new_name="RenamedProject")

        with patch("src.ui.main_window.RenameProjectDialog", return_value=dialog), \
                patch.object(self.window.workspace_manager, "rename") as rename_mock:
            self.window.rename_project()

            rename_mock.assert_called_once_with("RenamedProject")

    def test_dialog_is_constructed_with_the_current_workspace_root(self):
        self.window.workspace_manager.create(self.folder)
        dialog = self._mock_dialog(accepted=False)

        with patch(
            "src.ui.main_window.RenameProjectDialog", return_value=dialog
        ) as dialog_cls:
            self.window.rename_project()

            dialog_cls.assert_called_once_with(self.folder, self.window)

    def test_workspace_manager_error_is_shown_via_message_box(self):
        self.window.workspace_manager.create(self.folder)
        dialog = self._mock_dialog(accepted=True, new_name="RenamedProject")

        with patch("src.ui.main_window.RenameProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.workspace_manager,
                    "rename",
                    side_effect=WorkspaceManagerError("boom"),
                ), \
                patch("src.ui.main_window.QMessageBox.critical") as critical_mock:
            self.window.rename_project()

            critical_mock.assert_called_once()

    def test_permission_denied_shows_actionable_french_warning_not_critical(self):
        # Mission 027 real smoke test: confirmed via Process Explorer to
        # be explorer.exe holding handles on the project's subfolders —
        # the UI must show a clear, actionable French message, never the
        # generic technical QMessageBox.critical used for other errors.
        self.window.workspace_manager.create(self.folder)
        dialog = self._mock_dialog(accepted=True, new_name="RenamedProject")

        with patch("src.ui.main_window.RenameProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.workspace_manager,
                    "rename",
                    side_effect=WorkspaceRenamePermissionError("[WinError 5] Access is denied"),
                ), \
                patch("src.ui.main_window.QMessageBox.warning") as warning_mock, \
                patch("src.ui.main_window.QMessageBox.critical") as critical_mock:
            self.window.rename_project()

            warning_mock.assert_called_once()
            critical_mock.assert_not_called()

        message_text = warning_mock.call_args.args[2]
        self.assertIn("Explorateur Windows", message_text)
        self.assertIn("sous-dossier", message_text)

    def test_other_rename_errors_still_use_the_generic_critical_dialog(self):
        # Regression guard: the specific handling above must never widen
        # to swallow unrelated failures under the friendly message.
        self.window.workspace_manager.create(self.folder)
        dialog = self._mock_dialog(accepted=True, new_name="RenamedProject")

        with patch("src.ui.main_window.RenameProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.workspace_manager,
                    "rename",
                    side_effect=WorkspaceManagerError("A folder already exists at ..."),
                ), \
                patch("src.ui.main_window.QMessageBox.warning") as warning_mock, \
                patch("src.ui.main_window.QMessageBox.critical") as critical_mock:
            self.window.rename_project()

            critical_mock.assert_called_once()
            warning_mock.assert_not_called()

    def test_real_rename_updates_status_bar_with_new_name(self):
        self.window.workspace_manager.create(self.folder)
        dialog = self._mock_dialog(accepted=True, new_name="RenamedProject")

        with patch("src.ui.main_window.RenameProjectDialog", return_value=dialog):
            self.window.rename_project()

        self.assertIn("RenamedProject", self.window.statusBar().currentMessage())

    def test_new_project_open_project_save_project_are_unaffected(self):
        with patch(
            "src.ui.main_window.QFileDialog.getExistingDirectory",
            return_value=str(self.folder),
        ), patch.object(self.window.workspace_manager, "open") as open_mock:
            open_mock.return_value = MagicMock()
            self.window.open_project()

            open_mock.assert_called_once_with(str(self.folder))

    # --- WORKSPACE_RENAMED wiring: reset_for_workspace_change() safety net ---

    def test_pending_generation_result_invalidated_after_rename(self):
        # Mission 084 adaptation: before this mission, a rename silently
        # destroyed a pending result via reset_for_workspace_change()'s
        # own WORKSPACE_RENAMED subscription — this test proved exactly
        # that. Mission 084 adds an explicit Accept/Reject/Cancel guard
        # (confirm_pending_result_change()) in front of that destruction,
        # so a real (unmocked) rename_project() call would now block on
        # a real, blocking QMessageBox — this test mocks the guard's own
        # dialog choice ("reject") to reach the same end state via the
        # new, explicit path instead, still proving
        # reset_for_workspace_change()'s WORKSPACE_RENAMED subscription
        # itself remains wired and unmodified as a safety net (see its
        # own updated docstring) — not the destruction path exercised
        # directly, which is now covered by the pending-guard tests below.
        self.window.workspace_manager.create(self.folder)

        self.window.inference_page._pending_path = str(
            self.folder / "outputs" / "generated.png"
        )
        self.window.inference_page._generation_workspace_root = str(self.folder)
        self.window.inference_page._set_validation_buttons_enabled(True)

        dialog = self._mock_dialog(accepted=True, new_name="RenamedProject")
        with patch("src.ui.main_window.RenameProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.inference_page, "_confirm_pending_before_switch",
                    return_value="reject",
                ):
            self.window.rename_project()

        self.assertIsNone(self.window.inference_page._pending_path)
        self.assertFalse(self.window.inference_page.accept_button.isEnabled())


class MainWindowRenamePendingResultGuardTest(unittest.TestCase):
    """
    Mission 084: InferencePage.confirm_pending_result_change() as the
    SOLE guard added to rename_project() — deliberately not the 5 dirty
    -text guards (Mission 083 established that a rename never destroys
    any of those drafts; only reset_for_workspace_change()'s
    WORKSPACE_RENAMED-triggered pending-result destruction needed
    protecting here). Placed after RenameProjectDialog is accepted and
    before any physical WorkspaceManager.rename() call.
    """

    def setUp(self):
        self.window = MainWindow()
        self.addCleanup(self.window.close)

        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

    def _make_pending_result(self):
        self.window.workspace_manager.create(self.folder)
        outputs_dir = self.folder / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        generated_path = outputs_dir / "generated.png"
        generated_path.write_bytes(b"fake-png-bytes")

        self.window.inference_page._generation_workspace_root = str(self.folder)
        self.window.inference_page._set_pending(str(generated_path))
        return generated_path

    @staticmethod
    def _mock_dialog(accepted, new_name=None):
        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Accepted if accepted else QDialog.Rejected
        dialog.new_name = new_name
        return dialog

    def test_no_pending_result_never_shows_a_dialog(self):
        self.window.workspace_manager.create(self.folder)
        dialog = self._mock_dialog(accepted=True, new_name="RenamedProject")

        with patch("src.ui.main_window.RenameProjectDialog", return_value=dialog), \
                patch("src.ui.pages.inference_page.QMessageBox") as inference_box:
            self.window.rename_project()

            inference_box.assert_not_called()

        self.assertEqual(self.window.workspace_manager.current_workspace.name, "RenamedProject")

    def test_pending_cancel_refuses_rename_entirely(self):
        generated_path = self._make_pending_result()
        dialog = self._mock_dialog(accepted=True, new_name="RenamedProject")

        with patch("src.ui.main_window.RenameProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.inference_page, "_confirm_pending_before_switch",
                    return_value="cancel",
                ), patch.object(self.window.workspace_manager, "rename") as rename_mock:
            self.window.rename_project()

            rename_mock.assert_not_called()

        self.assertEqual(self.window.inference_page._pending_path, str(generated_path))
        self.assertTrue(generated_path.exists())
        self.assertEqual(self.window.workspace_manager.current_workspace.name, "Project")

    def test_pending_reject_deletes_then_renames(self):
        generated_path = self._make_pending_result()
        dialog = self._mock_dialog(accepted=True, new_name="RenamedProject")

        with patch("src.ui.main_window.RenameProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.inference_page, "_confirm_pending_before_switch",
                    return_value="reject",
                ):
            self.window.rename_project()

        self.assertFalse(generated_path.exists())
        self.assertIsNone(self.window.inference_page._pending_path)
        self.assertEqual(self.window.workspace_manager.current_workspace.name, "RenamedProject")

    def test_pending_accept_persistence_failure_refuses_rename_and_keeps_file(self):
        from src.infrastructure.storage.workspace_storage import WorkspaceStorage, WorkspaceStorageError

        generated_path = self._make_pending_result()
        dialog = self._mock_dialog(accepted=True, new_name="RenamedProject")

        with patch("src.ui.main_window.RenameProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.inference_page, "_confirm_pending_before_switch",
                    return_value="accept",
                ), patch.object(
                    WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
                ), patch("src.ui.pages.inference_page.QMessageBox.critical") as mock_critical, \
                patch.object(self.window.workspace_manager, "rename") as rename_mock:
            self.window.rename_project()

            rename_mock.assert_not_called()

        mock_critical.assert_called_once()
        self.assertEqual(self.window.inference_page._pending_path, str(generated_path))
        self.assertTrue(generated_path.exists())
        self.assertEqual(self.window.workspace_manager.current_workspace.name, "Project")

    # --- The critical, empirically-verified contract: Accept before a
    # real physical rename produces a valid, correctly remapped path. ---

    def test_pending_accept_then_real_rename_remaps_path_and_moves_file_physically(self):
        generated_path = self._make_pending_result()
        dialog = self._mock_dialog(accepted=True, new_name="RenamedProject")

        with patch("src.ui.main_window.RenameProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.inference_page, "_confirm_pending_before_switch",
                    return_value="accept",
                ):
            self.window.rename_project()

        new_root = self.window.workspace_manager.current_workspace.root
        self.assertEqual(new_root.name, "RenamedProject")
        self.assertNotEqual(new_root, self.folder)
        self.assertFalse(self.folder.exists())
        self.assertTrue(new_root.exists())

        images = self.window.workspace_manager.current_workspace.images
        self.assertEqual(len(images), 1)
        remapped_path = Path(images[0].file_path).resolve()

        # The recorded path was rewritten under the NEW root...
        self.assertTrue(str(remapped_path).startswith(str(new_root.resolve())))
        # ...and the physical file genuinely followed the folder rename
        # (a single atomic directory move, not a copy) to that exact
        # remapped location, with its content intact.
        self.assertTrue(remapped_path.exists())
        self.assertEqual(remapped_path.read_bytes(), b"fake-png-bytes")
        self.assertFalse(generated_path.exists())

        # Reopening the renamed project from disk confirms the remapped
        # reference is genuinely valid, not just correct in memory.
        self.window.close()
        reopened = MainWindow()
        self.addCleanup(reopened.close)
        result = reopened.workspace_manager.open(str(new_root))
        self.assertIsNotNone(result)
        reopened_images = reopened.workspace_manager.current_workspace.images
        self.assertEqual(len(reopened_images), 1)
        self.assertTrue(Path(reopened_images[0].file_path).exists())


if __name__ == "__main__":
    unittest.main()
