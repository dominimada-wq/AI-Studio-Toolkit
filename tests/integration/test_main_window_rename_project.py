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
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QDialog

from src.managers.workspace_manager import (
    WorkspaceManagerError,
    WorkspaceRenamePermissionError,
)
from src.ui.main_window import MainWindow

from tests.integration._qt_dialog_safety_net import start_dialog_guard, stop_dialog_guard

_app = QApplication.instance() or QApplication([])


def _wait_until(predicate, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        QApplication.processEvents()
        time.sleep(0.01)
    return predicate()


def _controlled_generate(output_path, started_evt, release_evt, timeout: float = 30.0):
    """
    Mission 085: a GenerationManager.generate() replacement whose start
    and completion are known with certainty (threading.Event), so the
    genuinely-active-generation scenarios below never depend on a
    fragile sleep() — same methodology as the mini-audit.
    """
    def _generate(prompt_text, output_directory, reference_images=None, reference_strength=None):
        started_evt.set()
        if not release_evt.wait(timeout=timeout):
            raise RuntimeError("release_evt never set - test harness bug")
        Path(output_path).write_bytes(b"controlled-generated-bytes")
        return str(output_path)
    return _generate


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


class MainWindowRenameGenerationActiveGuardTest(unittest.TestCase):
    """
    Mission 085: InferencePage.confirm_no_active_generation() as the
    FIRST check in rename_project() — before RenameProjectDialog is even
    shown, so a genuinely active generation is reported without asking
    the user for a new project name only to refuse the operation
    afterward. Deliberately independent from
    MainWindowRenamePendingResultGuardTest above: that class covers a
    generation that has already finished (a pending result); this one
    covers a generation that is still genuinely producing work — the
    mini-audit demonstrated these are structurally mutually exclusive
    states (generate_button stays disabled while a pending exists), so
    the two guard classes never need to interact.
    """

    def setUp(self):
        self.dialog_guard = start_dialog_guard()
        self.addCleanup(stop_dialog_guard, self.dialog_guard)

        self.window = MainWindow()
        self.addCleanup(self.window.close)

        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"
        self.window.workspace_manager.create(self.folder)

    def _start_controlled_generation(self, output_filename="controlled.png"):
        outputs_dir = self.folder / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        output_path = outputs_dir / output_filename
        started = threading.Event()
        release = threading.Event()
        self.window.generation_manager.generate = MagicMock(
            side_effect=_controlled_generate(output_path, started, release)
        )
        self.window.inference_page.prompt.blockSignals(True)
        self.window.inference_page.prompt.setPlainText("a test prompt")
        self.window.inference_page.prompt.blockSignals(False)
        self.window.inference_page._dirty = False
        self.window.inference_page.generate_button.click()
        self.assertTrue(started.wait(timeout=15.0), "worker never reached the controlled mock")
        self.assertTrue(
            self.window.inference_page.is_generation_active(),
            "worker reached the mock but is_generation_active() already reports False",
        )
        return output_path, release

    def test_rename_refused_before_dialog_while_generation_genuinely_active(self):
        output_path, release = self._start_controlled_generation()

        with patch("src.ui.main_window.RenameProjectDialog") as dialog_class, \
                patch("src.ui.pages.inference_page.QMessageBox"):
            self.window.rename_project()

            dialog_class.assert_not_called()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.folder)
        self.assertTrue(self.folder.exists())

        release.set()
        _wait_until(lambda: output_path.exists(), timeout=30.0)
        # Mission 091: let the worker's deferred finished/thread.finished
        # signals actually settle before addCleanup's real window.close()
        # runs — otherwise it can still observe is_generation_active()
        # True for a brief window and show the real "generation active"
        # guard dialog on close.
        _wait_until(lambda: self.window.inference_page._thread is None, timeout=30.0)
        self.window.inference_page._pending_path = None

    def test_workspace_physically_unchanged_after_refused_rename(self):
        output_path, release = self._start_controlled_generation()

        with patch("src.ui.pages.inference_page.QMessageBox"):
            self.window.rename_project()

        self.assertTrue(self.folder.exists())
        self.assertEqual(self.window.workspace_manager.current_workspace.name, "Project")

        release.set()
        _wait_until(lambda: output_path.exists(), timeout=30.0)
        # Mission 091: see the identical comment in
        # test_rename_refused_before_dialog_while_generation_genuinely_active.
        _wait_until(lambda: self.window.inference_page._thread is None, timeout=30.0)
        self.window.inference_page._pending_path = None

    def test_generation_continues_and_finishes_in_the_unchanged_workspace(self):
        output_path, release = self._start_controlled_generation()

        with patch("src.ui.pages.inference_page.QMessageBox"):
            self.window.rename_project()

        release.set()
        self.assertTrue(_wait_until(lambda: output_path.exists(), timeout=30.0))
        self.assertTrue(
            _wait_until(lambda: self.window.inference_page._pending_path is not None, timeout=30.0)
        )
        self.assertEqual(self.window.inference_page._pending_path, str(output_path))
        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.folder)

        self.window.inference_page._pending_path = None

    def test_second_rename_after_generation_finishes_hits_m084_pending_guard(self):
        output_path, release = self._start_controlled_generation()

        with patch("src.ui.pages.inference_page.QMessageBox"):
            self.window.rename_project()

        release.set()
        self.assertTrue(
            _wait_until(lambda: self.window.inference_page._pending_path is not None, timeout=30.0)
        )

        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Accepted
        dialog.new_name = "RenamedProject"

        with patch("src.ui.main_window.RenameProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.inference_page, "_confirm_pending_before_switch",
                    return_value="reject",
                ):
            self.window.rename_project()

        self.assertFalse(output_path.exists())
        self.assertIsNone(self.window.inference_page._pending_path)
        self.assertEqual(self.window.workspace_manager.current_workspace.name, "RenamedProject")

    def test_no_active_generation_rename_unchanged(self):
        # Non-regression: without any generation running,
        # confirm_no_active_generation() must return True and the
        # dialog must still be shown normally.
        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Accepted
        dialog.new_name = "RenamedProject"

        with patch("src.ui.main_window.RenameProjectDialog", return_value=dialog) as dialog_class:
            self.window.rename_project()

            dialog_class.assert_called_once()

        self.assertEqual(self.window.workspace_manager.current_workspace.name, "RenamedProject")


if __name__ == "__main__":
    unittest.main()
