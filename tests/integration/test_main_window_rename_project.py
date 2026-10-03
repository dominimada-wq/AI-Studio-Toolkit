"""
Narrow coverage for MainWindow.rename_project()'s wiring to
RenameProjectDialog/WorkspaceManager.rename() (Mission 027), and for the
WORKSPACE_RENAMED addition to InferencePage's pending-result invalidation
wiring — mirrors test_main_window_new_project.py exactly:
RenameProjectDialog is always patched (a real exec() would block the
test process), this file validates the wiring, not the dialog itself
(see test_rename_project_dialog.py for that).
"""

import json
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from src.managers.training_manager import (
    TRAINING_ARCHITECTURE_SD15,
    TRAINING_JOB_STATE_SUCCEEDED,
)
from src.managers.workspace_lifecycle import create_workspace_with_default_character
from src.managers.workspace_manager import (
    WORKSPACE_RENAMED,
    WorkspaceManagerError,
    WorkspaceRenamePermissionError,
)
from src.ui.main_window import MainWindow

from tests.integration._qt_dialog_safety_net import (
    UnexpectedDialogError,
    assert_dialog_guard_intercepts_promptly,
    start_dialog_guard,
    stop_dialog_guard,
)

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
    def _generate(prompt_text, output_directory, reference_images=None, reference_strength=None, **kwargs):
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
        self.dialog_guard = start_dialog_guard()
        self.addCleanup(stop_dialog_guard, self.dialog_guard)

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

        # Mission 094: the assertion above already verified the guard's
        # real behavior (Cancel preserves the pending result) — this
        # test-only cleanup, registered after setUp()'s own
        # addCleanup(self.window.close), runs before it (LIFO) so the
        # real closeEvent() reached by that close() never finds a
        # pending result to protect. See MISSION_094.md.
        self.addCleanup(setattr, self.window.inference_page, "_pending_path", None)

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

        # Mission 094: see the identical comment above in
        # test_pending_cancel_refuses_rename_entirely.
        self.addCleanup(setattr, self.window.inference_page, "_pending_path", None)

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

    # ------------------------------------------------------------
    # Mission 094: dedicated proof of the lifetime-gap fix itself
    # ------------------------------------------------------------

    def test_pending_cleanup_prevents_real_dialog_reaching_close(self):
        """
        Mission 094: dedicated proof that the addCleanup(setattr, ...,
        "_pending_path", None) fix added to the 2 Cancel/persistence-
        failure tests above genuinely neutralizes the real guard before
        window.close() runs — not merely that those tests happen to
        stay green, which could also occur for an unrelated reason.
        Reproduces the exact failing sequence documented in
        MISSION_093.md/MISSION_094.md: a Cancel scenario leaves
        _pending_path set, the mock's scope exits for real, then the
        real teardown cleanup chain (doCleanups()) runs with
        QMessageBox itself patched, so any real dialog construction
        attempt is directly observable rather than silently swallowed
        or left blocking.
        """
        generated_path = self._make_pending_result()
        dialog = self._mock_dialog(accepted=True, new_name="RenamedProject")

        with patch("src.ui.main_window.RenameProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.inference_page, "_confirm_pending_before_switch",
                    return_value="cancel",
                ), patch.object(self.window.workspace_manager, "rename"):
            self.window.rename_project()

        # Functional behavior verified here, exactly like the Cancel
        # test above — the guard genuinely preserved the pending
        # result while still inside the mock's scope.
        self.assertEqual(self.window.inference_page._pending_path, str(generated_path))

        self.addCleanup(setattr, self.window.inference_page, "_pending_path", None)

        # The mock's scope has already exited above. Run the exact
        # cleanup chain unittest will run at teardown right now, with
        # QMessageBox patched so a real dialog construction attempt is
        # directly observable — this proves _confirm_pending_before_
        # switch() (and therefore QMessageBox) is never reached, not
        # just that no visible dialog happened to appear.
        with patch("src.ui.pages.inference_page.QMessageBox") as mock_box:
            self.doCleanups()
            mock_box.assert_not_called()

    def test_dialog_guard_converts_a_genuinely_unexpected_dialog_into_a_clean_failure(self):
        """
        Mission 094: positive proof that the safety net armed on this
        class in setUp() (defense in depth, independent of the
        _pending_path cleanup fix above) is genuinely effective in
        this class's own context — mirrors QtDialogSafetyNetTest's own
        demonstration (test_qt_dialog_safety_net.py) but exercises
        this class's actual armed guard instance, proving a real
        unmocked dialog reached here would be converted into a clean,
        descriptive UnexpectedDialogError rather than left blocking
        for a human click.
        """
        def trigger():
            QMessageBox.warning(self.window, "Mission 094 Test Title", "Mission 094 Test Text")
            stop_dialog_guard(self.dialog_guard)

        exception = assert_dialog_guard_intercepts_promptly(self, trigger)
        self.assertIn("Mission 094 Test Title", str(exception))


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
        # Mission 115: this class is about Rename Project's pre-existing
        # close/rename guards, not ComfyUI Local's own lifecycle — see
        # the identical fix/comment in MainWindowCloseEventRealStateTest.
        # _start_controlled_generation() (test_main_window_close_event.py)
        # for the full rationale.
        from src.ui.comfyui_lifecycle_manager import RUNNING_OWNED, STOPPED
        self.window.comfyui_lifecycle_manager._state = RUNNING_OWNED
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
        self.window.comfyui_lifecycle_manager._state = STOPPED
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


class MainWindowRenameTrainingJobPathsTest(unittest.TestCase):
    """
    Mission 166: through a real MainWindow, a succeeded TrainingJob must be
    reachable again after rename_project() — with the page refreshed by the
    real WORKSPACE_RENAMED subscription, never by a manual call.

    Scope and limits: the Job is created by TrainingManager.create_job() and
    completed by update_job_state(), the production mechanisms, but the
    output is a stand-in file — no OneTrainer training runs, and the actual
    import into the Central LoRA Library is not executed. What is verified
    is the "importable" state of the Job row, the enabled import button and
    the paths/files, not a real training or a real import.
    """

    def setUp(self):
        # Armed first, stopped last: a genuinely unexpected real dialog is
        # turned into a clean failure instead of waiting for a human click.
        self.dialog_guard = start_dialog_guard()
        self.addCleanup(stop_dialog_guard, self.dialog_guard)

        # Registered before the window: cleanups run in reverse order, so
        # the window is closed before the Workspace folder is deleted.
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.window = MainWindow()
        self.addCleanup(self.window.close)

    @staticmethod
    def _mock_dialog(new_name):
        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Accepted
        dialog.new_name = new_name
        return dialog

    def _find_job(self, job_id):
        workspace = self.window.workspace_manager.current_workspace
        for character in workspace.characters:
            for training in character.trainings:
                for job in training.jobs:
                    if job.job_id == job_id:
                        return job
        self.fail(f"No Job {job_id!r} in the current Workspace")

    def _job_row(self, job_id):
        jobs_list = self.window.training_page.jobs_list
        for index in range(jobs_list.count()):
            item = jobs_list.item(index)
            if item.data(Qt.UserRole) == job_id:
                return item
        self.fail(f"No jobs_list row for job {job_id!r}")

    def _build_succeeded_job(self):
        window = self.window
        create_workspace_with_default_character(
            window.workspace_manager, window.character_manager, self.folder
        )

        image = QImage(16, 16, QImage.Format_RGB32)
        image.fill(QColor("red"))
        source_image = Path(self.tmp_dir) / "source.png"
        self.assertTrue(image.save(str(source_image)))

        dataset = window.dataset_manager.create("Dataset")
        window.dataset_manager.select(dataset.dataset_id)
        window.dataset_manager.add_images([str(source_image)])

        training_manager = window.training_manager
        training = training_manager.create("Session", dataset.dataset_id)
        training_manager.select(training.training_id)
        training_manager.update(
            base_model_source="models/v1-5-pruned.safetensors",
            architecture=TRAINING_ARCHITECTURE_SD15,
            resolution=512,
        )
        training_manager.prepare_onetrainer_config(training.training_id)

        job = training_manager.create_job(training.training_id)
        output = Path(job.expected_output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"fake-lora-bytes")
        training_manager.update_job_state(
            job.job_id, TRAINING_JOB_STATE_SUCCEEDED, final_output_path=str(output)
        )
        return job

    def test_succeeded_job_is_importable_again_through_the_real_workspace_renamed_event(self):
        window = self.window
        page = window.training_page
        job = self._build_succeeded_job()
        old_root = window.workspace_manager.current_workspace.root
        old_paths = {
            "config_snapshot_path": job.config_snapshot_path,
            "expected_output_path": job.expected_output_path,
            "final_output_path": job.final_output_path,
        }

        # Precondition: importable before the rename (the Job row exists
        # because the real events from create_job()/update_job_state()
        # already refreshed the page).
        page.jobs_list.setCurrentItem(self._job_row(job.job_id))
        self.assertTrue(self._job_row(job.job_id).text().endswith("importable"))
        self.assertTrue(page.import_lora_button.isEnabled())
        job_before_rename = self._find_job(job.job_id)

        # Observe the real WORKSPACE_RENAMED -> TrainingPage.update_trainings
        # subscription without replacing what it does.
        subscribers = window.event_bus._subscribers[WORKSPACE_RENAMED]
        recorded = []
        wrapped = 0
        for index, callback in enumerate(subscribers):
            if getattr(callback, "__self__", None) is page and callback.__name__ == "update_trainings":
                def recording(payload, _callback=callback):
                    recorded.append(payload)
                    return _callback(payload)
                subscribers[index] = recording
                wrapped += 1
        self.assertEqual(
            wrapped, 1,
            "TrainingPage.update_trainings must be subscribed to WORKSPACE_RENAMED exactly once",
        )

        dialog = self._mock_dialog("RenamedProject")
        with patch("src.ui.main_window.RenameProjectDialog", return_value=dialog):
            window.rename_project()
        # No manual update_trainings() here: everything below depends on
        # the real event alone.

        new_root = Path(self.tmp_dir) / "RenamedProject"
        self.assertEqual(window.workspace_manager.current_workspace.root, new_root)
        self.assertEqual(len(recorded), 1)

        # The Job is fetched from the rebuilt Workspace, not from a Python
        # reference kept from before Workspace.from_dict().
        job_after = self._find_job(job.job_id)
        self.assertIsNot(job_after, job_before_rename)
        for key, old_value in old_paths.items():
            expected = str(new_root / Path(old_value).relative_to(old_root))
            self.assertEqual(getattr(job_after, key), expected, key)
        self.assertTrue(Path(job_after.config_snapshot_path).is_file())
        self.assertEqual(Path(job_after.final_output_path).read_bytes(), b"fake-lora-bytes")
        self.assertTrue(Path(job_after.expected_output_path).is_file())
        self.assertFalse(old_root.exists())

        row_text = self._job_row(job.job_id).text()
        self.assertTrue(row_text.endswith("importable"), row_text)
        self.assertNotIn("fichier introuvable", row_text)
        self.assertTrue(page.import_lora_button.isEnabled())
        self.assertIsNotNone(page._importable_job())
        self.assertEqual(page._importable_job().job_id, job.job_id)


class MainWindowRenameDatasetCaptionDraftTest(unittest.TestCase):
    """
    Mission 167: through a real MainWindow, a caption draft typed on the
    selected Dataset image must survive rename_project() — the selection
    being restored by image_id, not by file_path (every internal path is
    remapped by a rename) — and a later explicit save must reach the right
    image under the new root.

    Scope and limits: the selection is made with real mouse clicks and the
    draft with real key events; only RenameProjectDialog is simulated. The
    page is refreshed exclusively by the real WORKSPACE_RENAMED
    subscription (observed in place, never replaced) — nothing calls
    update_datasets() by hand — and every object is re-read from the
    rebuilt Workspace. A failed rename is simulated by making
    WorkspaceManager.rename() raise (the real rollback is covered in
    test_workspace_roundtrip.py). Windows-native platform only.
    """

    def setUp(self):
        # Armed first, stopped last: a genuinely unexpected real dialog is
        # turned into a clean failure instead of waiting for a human click.
        self.dialog_guard = start_dialog_guard()
        self.addCleanup(stop_dialog_guard, self.dialog_guard)

        # Registered before the window: cleanups run in reverse order, so
        # the window is closed (and that closure verified) before the
        # Workspace folder is deleted — even if an assertion failed.
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.window = MainWindow()
        self.addCleanup(self._close_window_and_verify)
        self.window.show()
        QTest.qWait(20)
        self.assertTrue(self.window.sidebar.select_page("datasets"))

        self._build_dataset()
        QTest.qWait(20)

    def _close_window_and_verify(self):
        # Cleanup only, after every assertion: a draft a scenario left
        # dirty would make the real closeEvent guard prompt (which the
        # dialog guard cancels), leaving the window open. The draft is
        # neutralized here and nowhere else.
        self.window.datasets_page._caption_dirty = False
        self.window.close()
        QApplication.processEvents()
        self.assertFalse(
            self.window.isVisible(), "the window must be closed before the project is removed"
        )

    def _build_dataset(self):
        window = self.window
        create_workspace_with_default_character(
            window.workspace_manager, window.character_manager, self.folder
        )
        dataset = window.dataset_manager.create("Portraits")
        window.dataset_manager.select(dataset.dataset_id)
        self.dataset_id = dataset.dataset_id

        self.ids = {}
        for key, color in (("a", "red"), ("b", "green"), ("c", "blue")):
            image = QImage(24, 24, QImage.Format_RGB32)
            image.fill(QColor(color))
            source = Path(self.tmp_dir) / f"{key}.png"
            self.assertTrue(image.save(str(source)))
            window.dataset_manager.add_images([str(source)])
            self.ids[key] = window.dataset_manager.active_dataset.images[-1].image_id
        window.dataset_manager.set_caption(self.ids["b"], "persisted-b")
        window.dataset_manager.set_caption(self.ids["c"], "persisted-c")

    # --- helpers -----------------------------------------------------

    def _item_for(self, key):
        images_list = self.window.datasets_page.images_list
        for i in range(images_list.count()):
            item = images_list.item(i)
            if item.data(Qt.UserRole + 1) == self.ids[key]:
                return item
        self.fail(f"No images_list item for image {key!r}")

    def _click(self, key, ctrl=False):
        images_list = self.window.datasets_page.images_list
        rect = images_list.visualItemRect(self._item_for(key))
        self.assertTrue(rect.isValid() and not rect.isEmpty(), "the item must be laid out to be clicked")
        QTest.mouseClick(
            images_list.viewport(),
            Qt.LeftButton,
            Qt.ControlModifier if ctrl else Qt.NoModifier,
            rect.center(),
        )
        QApplication.processEvents()

    def _type_draft(self, text):
        page = self.window.datasets_page
        page.caption_edit.setFocus()
        QApplication.processEvents()
        QTest.keyClicks(page.caption_edit, text)
        QApplication.processEvents()
        self.assertTrue(page._caption_dirty)
        return page.caption_edit.toPlainText()

    def _assert_state(self, *, selected, current, text, dirty):
        page = self.window.datasets_page
        current_item = page.images_list.currentItem()
        expected_current = self.ids[current] if current is not None else None

        self.assertEqual(
            {item.data(Qt.UserRole + 1) for item in page.images_list.selectedItems()},
            {self.ids[key] for key in selected},
        )
        self.assertEqual(
            current_item.data(Qt.UserRole + 1) if current_item is not None else None,
            expected_current,
        )
        self.assertEqual(page._caption_loaded_image_id, expected_current)
        self.assertEqual(page.caption_edit.toPlainText(), text)
        self.assertEqual(page._caption_dirty, dirty)
        self.assertEqual(page.caption_edit.isEnabled(), current is not None)
        self.assertEqual(page.save_caption_button.isEnabled(), dirty)
        self.assertEqual(page.enlarge_button.isEnabled(), current is not None)
        self.assertEqual(page.remove_from_dataset_button.isEnabled(), bool(selected))

    def _captions(self, **by_key):
        return {self.ids[key]: caption for key, caption in by_key.items()}

    def _domain_captions(self):
        dataset = self.window.dataset_manager.active_dataset
        return {image_id: entry.caption for image_id, entry in dataset.entries.items()}

    def _persisted_captions(self, root):
        data = json.loads((Path(root) / "project.json").read_text(encoding="utf-8"))
        for character in data["characters"]:
            for dataset in character["datasets"]:
                if dataset["dataset_id"] == self.dataset_id:
                    return {image_id: entry["caption"] for image_id, entry in dataset["entries"].items()}
        self.fail("the Dataset is absent from project.json")

    @staticmethod
    def _mock_dialog(new_name, accepted=True):
        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Accepted if accepted else QDialog.Rejected
        dialog.new_name = new_name
        return dialog

    def _rename(self, new_name):
        """
        Production path: rename_project() with only the input dialog
        simulated. The page's own WORKSPACE_RENAMED subscription is
        observed in place and restored afterwards. Returns the Dataset
        re-read from the rebuilt Workspace.
        """
        window = self.window
        page = window.datasets_page
        subscribers = window.event_bus._subscribers[WORKSPACE_RENAMED]
        calls = []
        originals = []
        for index, callback in enumerate(subscribers):
            if getattr(callback, "__self__", None) is page and callback.__name__ == "update_datasets":
                def recording(payload, _callback=callback):
                    calls.append(payload)
                    return _callback(payload)
                originals.append((index, callback))
                subscribers[index] = recording
        self.assertEqual(len(originals), 1, "update_datasets must be subscribed to WORKSPACE_RENAMED exactly once")

        old_dataset = window.dataset_manager.active_dataset
        try:
            with patch("src.ui.main_window.RenameProjectDialog", return_value=self._mock_dialog(new_name)):
                window.rename_project()
        finally:
            for index, callback in originals:
                subscribers[index] = callback

        self.assertEqual(len(calls), 1)
        new_dataset = window.dataset_manager.active_dataset
        self.assertIsNot(new_dataset, old_dataset, "the Workspace must have been rebuilt")
        self.assertEqual(new_dataset.dataset_id, old_dataset.dataset_id)
        return new_dataset

    # --- tests ---------------------------------------------------------

    def test_draft_survives_the_real_rename_and_the_explicit_save_reaches_the_right_image(self):
        window = self.window
        page = window.datasets_page

        self._click("b")
        draft = self._type_draft("+draft")
        self.assertNotEqual(draft, "persisted-b")
        self._assert_state(selected=["b"], current="b", text=draft, dirty=True)

        with patch.object(
            window.dataset_manager, "set_caption", wraps=window.dataset_manager.set_caption
        ) as set_caption:
            new_dataset = self._rename("RenamedProject")
        set_caption.assert_not_called()

        new_root = Path(self.tmp_dir) / "RenamedProject"
        self.assertEqual(window.workspace_manager.current_workspace.root, new_root)
        self.assertFalse(self.folder.exists())
        for image in new_dataset.images:
            self.assertTrue(Path(image.file_path).is_relative_to(new_root), image.file_path)

        self._assert_state(selected=["b"], current="b", text=draft, dirty=True)

        # No automatic save: Domain and project.json still hold the
        # persisted captions.
        persisted = self._captions(b="persisted-b", c="persisted-c")
        self.assertEqual(self._domain_captions(), persisted)
        self.assertEqual(self._persisted_captions(new_root), persisted)

        # Explicit save, through the real button.
        QTest.mouseClick(page.save_caption_button, Qt.LeftButton)
        QApplication.processEvents()

        self._assert_state(selected=["b"], current="b", text=draft, dirty=False)
        expected = self._captions(b=draft, c="persisted-c")
        self.assertEqual(self._domain_captions(), expected)
        self.assertEqual(self._persisted_captions(new_root), expected)
        self.assertNotIn(self.ids["a"], self._domain_captions())

    def test_without_draft_the_multi_selection_and_displayed_caption_survive_the_real_rename(self):

        self._click("a")
        self._click("b", ctrl=True)
        self._assert_state(selected=["a", "b"], current="b", text="persisted-b", dirty=False)

        self._rename("RenamedProject")

        self._assert_state(selected=["a", "b"], current="b", text="persisted-b", dirty=False)
        self.assertEqual(self._domain_captions(), self._captions(b="persisted-b", c="persisted-c"))

    def test_cancelled_and_failed_renames_leave_selection_and_draft_untouched(self):
        window = self.window

        self._click("b")
        draft = self._type_draft("+draft")
        old_root = window.workspace_manager.current_workspace.root
        old_dataset = window.dataset_manager.active_dataset

        # Cancelled: the dialog is rejected, WorkspaceManager.rename() is never reached.
        with patch(
            "src.ui.main_window.RenameProjectDialog",
            return_value=self._mock_dialog("RenamedProject", accepted=False),
        ):
            window.rename_project()
        self.assertEqual(window.workspace_manager.current_workspace.root, old_root)
        self.assertIs(window.dataset_manager.active_dataset, old_dataset)
        self._assert_state(selected=["b"], current="b", text=draft, dirty=True)

        # Failed: rename() raises, MainWindow reports it, no WORKSPACE_RENAMED is published.
        with patch(
            "src.ui.main_window.RenameProjectDialog",
            return_value=self._mock_dialog("RenamedProject"),
        ), patch.object(
            type(window.workspace_manager), "rename", side_effect=WorkspaceManagerError("simulated failure")
        ), patch("src.ui.main_window.QMessageBox.critical") as critical:
            window.rename_project()
        critical.assert_called_once()
        self.assertEqual(window.workspace_manager.current_workspace.root, old_root)
        self.assertIs(window.dataset_manager.active_dataset, old_dataset)
        self._assert_state(selected=["b"], current="b", text=draft, dirty=True)
        self.assertEqual(self._domain_captions(), self._captions(b="persisted-b", c="persisted-c"))

    def test_two_successive_real_renames_then_save_persist_under_the_last_root_and_survive_a_reopen(self):
        window = self.window
        page = window.datasets_page

        self._click("b")
        draft = self._type_draft("+draft")

        self._rename("FirstRename")
        self._assert_state(selected=["b"], current="b", text=draft, dirty=True)
        self._rename("SecondRename")
        self._assert_state(selected=["b"], current="b", text=draft, dirty=True)

        last_root = Path(self.tmp_dir) / "SecondRename"
        self.assertEqual(window.workspace_manager.current_workspace.root, last_root)
        self.assertFalse((Path(self.tmp_dir) / "FirstRename").exists())

        QTest.mouseClick(page.save_caption_button, Qt.LeftButton)
        QApplication.processEvents()
        expected = self._captions(b=draft, c="persisted-c")
        self.assertEqual(self._persisted_captions(last_root), expected)

        # Reopening the renamed project (the draft is saved, so nothing is
        # pending; direct Manager calls) shows the persisted caption.
        window.workspace_manager.close()
        window.workspace_manager.open(last_root)
        window.dataset_manager.select(self.dataset_id)
        self.assertEqual(self._domain_captions(), expected)


if __name__ == "__main__":
    unittest.main()
