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
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from src.infrastructure.storage.workspace_storage import WorkspaceStorage, WorkspaceStorageError
from src.managers.workspace_manager import WorkspaceManager, WorkspaceManagerError
from src.ui.main_window import MainWindow


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


class MainWindowInferencePromptGuardTest(unittest.TestCase):
    """
    Mission 083: InferencePage.confirm_context_change(), the 5th guard,
    appended after Settings — same real-Workspace/mocked-modal-dialogs
    idiom as MainWindowConfirmContextChangeTest above, applied to
    InferencePage.prompt instead of PromptsPage.text_edit.
    """

    def setUp(self):
        self.window = MainWindow()
        self.addCleanup(self.window.close)

        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.old_folder = Path(self.tmp_dir) / "OldProject"
        self.new_folder = Path(self.tmp_dir) / "NewProject"

    def _make_dirty_inference_prompt(self):
        self.window.workspace_manager.create(self.old_folder)
        character = self.window.character_manager.principal_character
        self.window.inference_page.prompt.setPlainText("a red fox, not saved")
        self.assertTrue(self.window.inference_page._dirty)
        return character

    def _read_old_project_prompts(self, character_id):
        with open(self.old_folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        character = next(c for c in on_disk["characters"] if c["character_id"] == character_id)
        return character["prompts"]

    @staticmethod
    def _mock_new_project_dialog(target_path):
        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Accepted
        dialog.target_path = target_path
        return dialog

    # ------------------------------------------------------------
    # new_project()
    # ------------------------------------------------------------

    def test_new_project_dirty_inference_prompt_save_persists_then_switches(self):
        character = self._make_dirty_inference_prompt()
        dialog = self._mock_new_project_dialog(self.new_folder)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.inference_page, "_confirm_discard_before_switch",
                    return_value=QMessageBox.Save,
                ), patch(
                    "src.ui.pages.inference_page.QInputDialog.getText",
                    return_value=("From Inference", True),
                ):
            self.window.new_project()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.new_folder)
        prompts = self._read_old_project_prompts(character.character_id)
        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0]["name"], "From Inference")
        self.assertEqual(prompts[0]["text"], "a red fox, not saved")
        # Mission 083: reset_for_context_change() must leave the new
        # Workspace's own InferencePage prompt empty — the old project's
        # text (even once safely saved elsewhere) must never carry over.
        self.assertEqual(self.window.inference_page.prompt.toPlainText(), "")
        self.assertFalse(self.window.inference_page._dirty)

    def test_new_project_dirty_inference_prompt_discard_switches_without_creating(self):
        character = self._make_dirty_inference_prompt()
        dialog = self._mock_new_project_dialog(self.new_folder)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.inference_page, "_confirm_discard_before_switch",
                    return_value=QMessageBox.Discard,
                ):
            self.window.new_project()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.new_folder)
        self.assertEqual(self._read_old_project_prompts(character.character_id), [])

    def test_new_project_dirty_inference_prompt_cancel_abandons_new_project_entirely(self):
        self._make_dirty_inference_prompt()
        dialog = self._mock_new_project_dialog(self.new_folder)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.inference_page, "_confirm_discard_before_switch",
                    return_value=QMessageBox.Cancel,
                ), patch.object(self.window.workspace_manager, "create") as create_mock:
            self.window.new_project()

            create_mock.assert_not_called()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.old_folder)
        self.assertTrue(self.window.inference_page._dirty)
        self.assertEqual(self.window.inference_page.prompt.toPlainText(), "a red fox, not saved")

        # Same reason as MainWindowConfirmContextChangeTest's own Cancel
        # tests above — neutralizes only the teardown close(), registered
        # after setUp()'s so it runs first (LIFO).
        self.addCleanup(setattr, self.window.inference_page, "_dirty", False)

    def test_new_project_inference_guard_false_never_calls_workspace_manager_create(self):
        dialog = self._mock_new_project_dialog(self.new_folder)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.inference_page, "confirm_context_change", return_value=False
                ), \
                patch.object(self.window.workspace_manager, "create") as create_mock:
            self.window.new_project()

            create_mock.assert_not_called()

    def test_new_project_guard_order_includes_inference_fifth(self):
        dialog = self._mock_new_project_dialog(self.new_folder)
        order = []

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.prompts_page, "confirm_context_change",
                    side_effect=lambda: order.append("prompts") or True,
                ), patch.object(
                    self.window.characters_page, "confirm_context_change",
                    side_effect=lambda: order.append("characters") or True,
                ), patch.object(
                    self.window.lora_page, "confirm_context_change",
                    side_effect=lambda: order.append("lora") or True,
                ), patch.object(
                    self.window.settings_page, "confirm_context_change",
                    side_effect=lambda: order.append("settings") or True,
                ), patch.object(
                    self.window.inference_page, "confirm_context_change",
                    side_effect=lambda: order.append("inference") or True,
                ), patch.object(
                    self.window.workspace_manager, "create",
                    side_effect=lambda *a, **k: order.append("create"),
                ):
            self.window.new_project()

        self.assertEqual(order, ["prompts", "characters", "lora", "settings", "inference", "create"])

    # ------------------------------------------------------------
    # open_project()
    # ------------------------------------------------------------

    def _precreate_new_folder_project(self):
        # Same reasoning as MainWindowConfirmContextChangeTest's own
        # helper above: a standalone, unwired WorkspaceManager avoids
        # publishing WORKSPACE_CREATED (which would wipe the dirty draft
        # via reset_for_context_change() before open_project() even
        # runs) — only produces a real project.json for
        # self.window.workspace_manager.open() to load.
        WorkspaceManager().create(self.new_folder)

    def test_open_project_dirty_inference_prompt_save_persists_then_switches(self):
        self._precreate_new_folder_project()
        character = self._make_dirty_inference_prompt()

        with patch(
            "src.ui.main_window.QFileDialog.getExistingDirectory",
            return_value=str(self.new_folder),
        ), patch.object(
            self.window.inference_page, "_confirm_discard_before_switch",
            return_value=QMessageBox.Save,
        ), patch(
            "src.ui.pages.inference_page.QInputDialog.getText",
            return_value=("From Inference", True),
        ):
            self.window.open_project()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.new_folder)
        prompts = self._read_old_project_prompts(character.character_id)
        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0]["text"], "a red fox, not saved")

    def test_open_project_dirty_inference_prompt_discard_switches_without_creating(self):
        self._precreate_new_folder_project()
        character = self._make_dirty_inference_prompt()

        with patch(
            "src.ui.main_window.QFileDialog.getExistingDirectory",
            return_value=str(self.new_folder),
        ), patch.object(
            self.window.inference_page, "_confirm_discard_before_switch",
            return_value=QMessageBox.Discard,
        ):
            self.window.open_project()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.new_folder)
        self.assertEqual(self._read_old_project_prompts(character.character_id), [])

    def test_open_project_dirty_inference_prompt_cancel_abandons_open_project_entirely(self):
        self._precreate_new_folder_project()
        self._make_dirty_inference_prompt()

        with patch(
            "src.ui.main_window.QFileDialog.getExistingDirectory",
            return_value=str(self.new_folder),
        ), patch.object(
            self.window.inference_page, "_confirm_discard_before_switch",
            return_value=QMessageBox.Cancel,
        ), patch.object(self.window.workspace_manager, "open") as open_mock:
            self.window.open_project()

            open_mock.assert_not_called()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.old_folder)
        self.assertTrue(self.window.inference_page._dirty)

        self.addCleanup(setattr, self.window.inference_page, "_dirty", False)


class MainWindowInferencePendingResultGuardTest(unittest.TestCase):
    """
    Mission 084: InferencePage.confirm_pending_result_change(), the 6th
    and last guard, appended after the Inference prompt guard (Mission
    083) — same real-Workspace/mocked-modal-dialog idiom as
    MainWindowInferencePromptGuardTest above, applied to
    self._pending_path (a not-yet-Accept/Reject generation result)
    instead of self.prompt. Deliberately a SEPARATE guard/dialog from
    the prompt one — the two drafts are independent (see
    confirm_pending_result_change()'s own docstring) — so these tests
    never touch self.inference_page.prompt/._dirty at all.
    """

    def setUp(self):
        self.window = MainWindow()
        self.addCleanup(self.window.close)

        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.old_folder = Path(self.tmp_dir) / "OldProject"
        self.new_folder = Path(self.tmp_dir) / "NewProject"

    def _make_pending_result(self):
        self.window.workspace_manager.create(self.old_folder)
        outputs_dir = self.old_folder / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        generated_path = outputs_dir / "generated.png"
        generated_path.write_bytes(b"fake-png-bytes")

        self.window.inference_page._generation_workspace_root = str(self.old_folder)
        self.window.inference_page._set_pending(str(generated_path))
        self.assertIsNotNone(self.window.inference_page._pending_path)
        return generated_path

    @staticmethod
    def _mock_new_project_dialog(target_path):
        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Accepted
        dialog.target_path = target_path
        return dialog

    # ------------------------------------------------------------
    # new_project()
    # ------------------------------------------------------------

    def test_new_project_pending_accept_persists_then_switches(self):
        generated_path = self._make_pending_result()
        dialog = self._mock_new_project_dialog(self.new_folder)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.inference_page, "_confirm_pending_before_switch",
                    return_value="accept",
                ):
            self.window.new_project()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.new_folder)
        # add_images() saved into the OLD workspace's project.json before
        # the switch — read it directly, current_workspace already points
        # to the new (empty) one.
        with open(self.old_folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertEqual([img["file_path"] for img in on_disk["images"]], [str(generated_path)])
        self.assertTrue(generated_path.exists())
        self.assertIsNone(self.window.inference_page._pending_path)

    def test_new_project_pending_reject_switches_without_persisting(self):
        generated_path = self._make_pending_result()
        dialog = self._mock_new_project_dialog(self.new_folder)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.inference_page, "_confirm_pending_before_switch",
                    return_value="reject",
                ):
            self.window.new_project()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.new_folder)
        self.assertFalse(generated_path.exists())
        self.assertIsNone(self.window.inference_page._pending_path)

    def test_new_project_pending_cancel_abandons_new_project_entirely(self):
        generated_path = self._make_pending_result()
        dialog = self._mock_new_project_dialog(self.new_folder)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.inference_page, "_confirm_pending_before_switch",
                    return_value="cancel",
                ), patch.object(self.window.workspace_manager, "create") as create_mock:
            self.window.new_project()

            create_mock.assert_not_called()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.old_folder)
        self.assertEqual(self.window.inference_page._pending_path, str(generated_path))
        self.assertTrue(generated_path.exists())
        self.assertTrue(self.window.inference_page.accept_button.isEnabled())

    def test_new_project_pending_accept_persistence_failure_refuses_transition(self):
        generated_path = self._make_pending_result()
        dialog = self._mock_new_project_dialog(self.new_folder)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.inference_page, "_confirm_pending_before_switch",
                    return_value="accept",
                ), patch.object(
                    WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
                ), patch("src.ui.pages.inference_page.QMessageBox.critical") as mock_critical, \
                patch.object(self.window.workspace_manager, "create") as create_mock:
            self.window.new_project()

            create_mock.assert_not_called()

        mock_critical.assert_called_once()
        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.old_folder)
        # Distinguishes a real persistence failure (state preserved,
        # retry possible) from the stale-context/missing-file cases
        # tested below, which authorize the transition instead.
        self.assertEqual(self.window.inference_page._pending_path, str(generated_path))
        self.assertTrue(generated_path.exists())

    def test_new_project_pending_accept_stale_context_still_authorizes_transition(self):
        # An extremely rare race, not the persistence-failure path above
        # — _accept_pending_result() already destroys the pending result
        # itself in this branch (nothing left to protect), so the guard
        # must let the transition proceed rather than block it for
        # nothing.
        generated_path = self._make_pending_result()
        self.window.inference_page._generation_workspace_root = str(self.tmp_dir) + "/SomeOtherStaleRoot"
        dialog = self._mock_new_project_dialog(self.new_folder)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.inference_page, "_confirm_pending_before_switch",
                    return_value="accept",
                ), patch("src.ui.pages.inference_page.QMessageBox.warning"):
            self.window.new_project()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.new_folder)
        self.assertFalse(generated_path.exists())
        self.assertIsNone(self.window.inference_page._pending_path)

    def test_new_project_pending_accept_missing_file_still_authorizes_transition(self):
        generated_path = self._make_pending_result()
        generated_path.unlink()
        dialog = self._mock_new_project_dialog(self.new_folder)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.inference_page, "_confirm_pending_before_switch",
                    return_value="accept",
                ), patch("src.ui.pages.inference_page.QMessageBox.warning"):
            self.window.new_project()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.new_folder)
        self.assertIsNone(self.window.inference_page._pending_path)

    def test_new_project_pending_reject_physical_deletion_failure_still_authorizes_transition(self):
        generated_path = self._make_pending_result()
        dialog = self._mock_new_project_dialog(self.new_folder)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.inference_page, "_confirm_pending_before_switch",
                    return_value="reject",
                ), patch(
                    "src.ui.pages.inference_page.Path.unlink", side_effect=OSError("permission denied")
                ), patch("src.ui.pages.inference_page.QMessageBox.warning") as mock_warning:
            self.window.new_project()

            mock_warning.assert_called_once()

        # Reject never blocks the transition, even when the best-effort
        # physical cleanup itself fails.
        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.new_folder)
        self.assertIsNone(self.window.inference_page._pending_path)

    def test_new_project_pending_guard_false_never_calls_workspace_manager_create(self):
        dialog = self._mock_new_project_dialog(self.new_folder)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.inference_page, "confirm_pending_result_change", return_value=False
                ), \
                patch.object(self.window.workspace_manager, "create") as create_mock:
            self.window.new_project()

            create_mock.assert_not_called()

    def test_new_project_guard_order_includes_pending_sixth(self):
        dialog = self._mock_new_project_dialog(self.new_folder)
        order = []

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(
                    self.window.prompts_page, "confirm_context_change",
                    side_effect=lambda: order.append("prompts") or True,
                ), patch.object(
                    self.window.characters_page, "confirm_context_change",
                    side_effect=lambda: order.append("characters") or True,
                ), patch.object(
                    self.window.lora_page, "confirm_context_change",
                    side_effect=lambda: order.append("lora") or True,
                ), patch.object(
                    self.window.settings_page, "confirm_context_change",
                    side_effect=lambda: order.append("settings") or True,
                ), patch.object(
                    self.window.inference_page, "confirm_context_change",
                    side_effect=lambda: order.append("inference_prompt") or True,
                ), patch.object(
                    self.window.inference_page, "confirm_pending_result_change",
                    side_effect=lambda: order.append("inference_pending") or True,
                ), patch.object(
                    self.window.workspace_manager, "create",
                    side_effect=lambda *a, **k: order.append("create"),
                ):
            self.window.new_project()

        self.assertEqual(
            order,
            ["prompts", "characters", "lora", "settings", "inference_prompt", "inference_pending", "create"],
        )

    # ------------------------------------------------------------
    # open_project()
    # ------------------------------------------------------------

    def _precreate_new_folder_project(self):
        # Same reasoning as MainWindowInferencePromptGuardTest's own
        # helper above — a standalone, unwired WorkspaceManager avoids
        # publishing WORKSPACE_CREATED (which would invalidate the
        # pending result via reset_for_workspace_change() before
        # open_project() even runs) — only produces a real project.json
        # for self.window.workspace_manager.open() to load.
        WorkspaceManager().create(self.new_folder)

    def test_open_project_pending_accept_persists_then_switches(self):
        self._precreate_new_folder_project()
        generated_path = self._make_pending_result()

        with patch(
            "src.ui.main_window.QFileDialog.getExistingDirectory",
            return_value=str(self.new_folder),
        ), patch.object(
            self.window.inference_page, "_confirm_pending_before_switch",
            return_value="accept",
        ):
            self.window.open_project()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.new_folder)
        with open(self.old_folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertEqual([img["file_path"] for img in on_disk["images"]], [str(generated_path)])
        self.assertTrue(generated_path.exists())

    def test_open_project_pending_reject_switches_without_persisting(self):
        self._precreate_new_folder_project()
        generated_path = self._make_pending_result()

        with patch(
            "src.ui.main_window.QFileDialog.getExistingDirectory",
            return_value=str(self.new_folder),
        ), patch.object(
            self.window.inference_page, "_confirm_pending_before_switch",
            return_value="reject",
        ):
            self.window.open_project()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.new_folder)
        self.assertFalse(generated_path.exists())

    def test_open_project_pending_cancel_abandons_open_project_entirely(self):
        self._precreate_new_folder_project()
        generated_path = self._make_pending_result()

        with patch(
            "src.ui.main_window.QFileDialog.getExistingDirectory",
            return_value=str(self.new_folder),
        ), patch.object(
            self.window.inference_page, "_confirm_pending_before_switch",
            return_value="cancel",
        ), patch.object(self.window.workspace_manager, "open") as open_mock:
            self.window.open_project()

            open_mock.assert_not_called()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.old_folder)
        self.assertEqual(self.window.inference_page._pending_path, str(generated_path))
        self.assertTrue(generated_path.exists())


class MainWindowNewOpenGenerationActiveNonRegressionTest(unittest.TestCase):
    """
    Mission 085: New Project and Open Project deliberately gain NO new
    guard for a genuinely active generation. The mini-audit empirically
    confirmed neither transition touches
    InferencePage._generation_workspace_root, so when the generation
    later finishes, _workspace_context_matches() correctly detects the
    real Workspace change and discards the result silently — exactly
    the intentional, tested Mission 014 contract, structurally
    different from Close/Rename (see MISSION_085.md). These tests
    freeze that already-correct behavior as an explicit non-regression
    baseline for this mission.
    """

    def setUp(self):
        self.window = MainWindow()
        self.addCleanup(self.window.close)

        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.old_folder = Path(self.tmp_dir) / "OldProject"
        self.new_folder = Path(self.tmp_dir) / "NewProject"
        self.window.workspace_manager.create(self.old_folder)

    def _start_controlled_generation(self, output_filename="controlled.png"):
        outputs_dir = self.old_folder / "outputs"
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
        self.assertTrue(started.wait(timeout=5.0), "worker never reached the controlled mock")
        self.assertTrue(self.window.inference_page.is_generation_active())
        return output_path, release

    def test_new_project_proceeds_without_blocking_during_active_generation(self):
        output_path, release = self._start_controlled_generation()

        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Accepted
        dialog.target_path = self.new_folder

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog):
            self.window.new_project()

        # Unlike Close/Rename, this must proceed immediately — the
        # active generation keeps running in the background, unaware
        # the Workspace changed underneath it.
        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.new_folder)
        self.assertTrue(self.window.inference_page.is_generation_active())

        release.set()
        self.assertTrue(_wait_until(lambda: output_path.exists(), timeout=10.0))
        _wait_until(lambda: self.window.inference_page._pending_path is None, timeout=10.0)
        # Mission 014: the result was born in the old Workspace, which
        # is no longer current — discarded silently, never surfaced as
        # a pending result the user could Accept into the new project.
        self.assertIsNone(self.window.inference_page._pending_path)

    def test_open_project_proceeds_without_blocking_during_active_generation(self):
        WorkspaceManager().create(self.new_folder)
        output_path, release = self._start_controlled_generation()

        with patch(
            "src.ui.main_window.QFileDialog.getExistingDirectory",
            return_value=str(self.new_folder),
        ):
            self.window.open_project()

        self.assertEqual(self.window.workspace_manager.current_workspace.root, self.new_folder)
        self.assertTrue(self.window.inference_page.is_generation_active())

        release.set()
        self.assertTrue(_wait_until(lambda: output_path.exists(), timeout=10.0))
        _wait_until(lambda: self.window.inference_page._pending_path is None, timeout=10.0)
        self.assertIsNone(self.window.inference_page._pending_path)

    def test_new_project_result_from_old_workspace_never_persisted_anywhere(self):
        output_path, release = self._start_controlled_generation()

        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Accepted
        dialog.target_path = self.new_folder
        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog):
            self.window.new_project()

        release.set()
        self.assertTrue(_wait_until(lambda: output_path.exists(), timeout=10.0))
        _wait_until(lambda: self.window.inference_page._pending_path is None, timeout=10.0)

        # Neither the abandoned old project nor the new one ever
        # references the file — it is a harmless orphan on disk, never
        # a silent data-integrity issue (same accepted shape as any
        # other Reject).
        with open(self.old_folder / "project.json", encoding="utf-8") as f:
            old_on_disk = json.load(f)
        self.assertEqual(old_on_disk["images"], [])
        with open(self.new_folder / "project.json", encoding="utf-8") as f:
            new_on_disk = json.load(f)
        self.assertEqual(new_on_disk["images"], [])

    def test_no_crash_when_generation_finishes_well_after_new_project(self):
        # Non-regression: no exception, no crash, regardless of how long
        # after the switch the deferred signal actually lands.
        output_path, release = self._start_controlled_generation()

        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Accepted
        dialog.target_path = self.new_folder
        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog):
            self.window.new_project()

        _wait_until(lambda: False, timeout=0.5)  # let a little real time pass first
        release.set()
        self.assertTrue(_wait_until(lambda: output_path.exists(), timeout=10.0))
        _wait_until(lambda: self.window.inference_page._thread is None, timeout=10.0)
        self.assertIsNone(self.window.inference_page._thread)


if __name__ == "__main__":
    unittest.main()
