"""
Mission 079: MainWindow.closeEvent() gains the same dirty-draft guard
already established by Missions 069/078 for new_project()/open_project()
— PromptsPage/CharactersPage/LoRAPage/SettingsPage.confirm_context_change(),
same order, same early-return-on-False contract. Before this mission,
closing the whole application (OS-level window close) never consulted
any of the four guards, silently discarding any unsaved draft.

Same narrow-scope pattern as test_main_window_new_project.py: a real
MainWindow() with only the modal QMessageBox dialogs and, where noted,
the four confirm_context_change() methods themselves mocked to control
orchestration without blocking the test process.
"""

import json
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from src.ui.main_window import MainWindow

from tests.integration._qt_dialog_safety_net import start_dialog_guard, stop_dialog_guard

_app = QApplication.instance() or QApplication([])


def _pump(seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)


def _wait_until(predicate, timeout: float = 5.0) -> bool:
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


class MainWindowCloseEventOrchestrationTest(unittest.TestCase):
    """
    Orchestration/ordering coverage using mocked guards — no real
    Workspace/dirty-state involved, matching
    MainWindowNewProjectTest's own mocked-guard tests.
    """

    def setUp(self):
        self.window = MainWindow()

    def tearDown(self):
        # Guards are patched per-test above the real implementation;
        # nothing is left dirty here, so a real close() is always safe.
        self.window.close()

    def _patch_guards(self, prompts=True, characters=True, lora=True, settings=True):
        return (
            patch.object(self.window.prompts_page, "confirm_context_change", return_value=prompts),
            patch.object(self.window.characters_page, "confirm_context_change", return_value=characters),
            patch.object(self.window.lora_page, "confirm_context_change", return_value=lora),
            patch.object(self.window.settings_page, "confirm_context_change", return_value=settings),
        )

    def test_all_guards_true_accepts_close_and_shuts_down_inference(self):
        patchers = self._patch_guards()
        with patchers[0], patchers[1], patchers[2], patchers[3], \
                patch.object(self.window.inference_page, "shutdown") as shutdown_mock:
            event = QCloseEvent()
            self.window.closeEvent(event)

            self.assertTrue(event.isAccepted())
            shutdown_mock.assert_called_once()

    def test_prompts_guard_false_ignores_close_and_stops_the_chain(self):
        with patch.object(self.window.prompts_page, "confirm_context_change", return_value=False), \
                patch.object(self.window.characters_page, "confirm_context_change") as characters_mock, \
                patch.object(self.window.lora_page, "confirm_context_change") as lora_mock, \
                patch.object(self.window.settings_page, "confirm_context_change") as settings_mock, \
                patch.object(self.window.inference_page, "shutdown") as shutdown_mock:
            event = QCloseEvent()
            self.window.closeEvent(event)

            self.assertFalse(event.isAccepted())
            characters_mock.assert_not_called()
            lora_mock.assert_not_called()
            settings_mock.assert_not_called()
            shutdown_mock.assert_not_called()

    def test_characters_guard_false_ignores_close_and_stops_the_chain(self):
        with patch.object(self.window.prompts_page, "confirm_context_change", return_value=True), \
                patch.object(self.window.characters_page, "confirm_context_change", return_value=False), \
                patch.object(self.window.lora_page, "confirm_context_change") as lora_mock, \
                patch.object(self.window.settings_page, "confirm_context_change") as settings_mock, \
                patch.object(self.window.inference_page, "shutdown") as shutdown_mock:
            event = QCloseEvent()
            self.window.closeEvent(event)

            self.assertFalse(event.isAccepted())
            lora_mock.assert_not_called()
            settings_mock.assert_not_called()
            shutdown_mock.assert_not_called()

    def test_lora_guard_false_ignores_close_and_stops_the_chain(self):
        with patch.object(self.window.prompts_page, "confirm_context_change", return_value=True), \
                patch.object(self.window.characters_page, "confirm_context_change", return_value=True), \
                patch.object(self.window.lora_page, "confirm_context_change", return_value=False), \
                patch.object(self.window.settings_page, "confirm_context_change") as settings_mock, \
                patch.object(self.window.inference_page, "shutdown") as shutdown_mock:
            event = QCloseEvent()
            self.window.closeEvent(event)

            self.assertFalse(event.isAccepted())
            settings_mock.assert_not_called()
            shutdown_mock.assert_not_called()

    def test_settings_guard_false_ignores_close(self):
        with patch.object(self.window.prompts_page, "confirm_context_change", return_value=True), \
                patch.object(self.window.characters_page, "confirm_context_change", return_value=True), \
                patch.object(self.window.lora_page, "confirm_context_change", return_value=True), \
                patch.object(self.window.settings_page, "confirm_context_change", return_value=False), \
                patch.object(self.window.inference_page, "shutdown") as shutdown_mock:
            event = QCloseEvent()
            self.window.closeEvent(event)

            self.assertFalse(event.isAccepted())
            shutdown_mock.assert_not_called()

    def test_inference_guard_false_ignores_close_and_stops_the_chain(self):
        # Mission 083: InferencePage.confirm_context_change() appended as
        # the 5th guard, after Settings — same early-return contract as
        # the 4 existing guards.
        with patch.object(self.window.prompts_page, "confirm_context_change", return_value=True), \
                patch.object(self.window.characters_page, "confirm_context_change", return_value=True), \
                patch.object(self.window.lora_page, "confirm_context_change", return_value=True), \
                patch.object(self.window.settings_page, "confirm_context_change", return_value=True), \
                patch.object(self.window.inference_page, "confirm_context_change", return_value=False), \
                patch.object(self.window.inference_page, "shutdown") as shutdown_mock:
            event = QCloseEvent()
            self.window.closeEvent(event)

            self.assertFalse(event.isAccepted())
            shutdown_mock.assert_not_called()

    def test_pending_guard_false_ignores_close_and_stops_the_chain(self):
        # Mission 084: InferencePage.confirm_pending_result_change()
        # appended as the 6th and last guard, after the Inference prompt
        # guard — same early-return contract, deliberately a separate
        # method/dialog from confirm_context_change() (see that method's
        # own docstring).
        with patch.object(self.window.prompts_page, "confirm_context_change", return_value=True), \
                patch.object(self.window.characters_page, "confirm_context_change", return_value=True), \
                patch.object(self.window.lora_page, "confirm_context_change", return_value=True), \
                patch.object(self.window.settings_page, "confirm_context_change", return_value=True), \
                patch.object(self.window.inference_page, "confirm_context_change", return_value=True), \
                patch.object(self.window.inference_page, "confirm_pending_result_change", return_value=False), \
                patch.object(self.window.inference_page, "shutdown") as shutdown_mock:
            event = QCloseEvent()
            self.window.closeEvent(event)

            self.assertFalse(event.isAccepted())
            shutdown_mock.assert_not_called()

    def test_generation_active_guard_false_ignores_close_and_stops_the_chain(self):
        # Mission 085: InferencePage.confirm_no_active_generation()
        # appended as the very first guard, before all 6 existing ones —
        # a genuinely active generation has produced no dirty draft and
        # no pending result yet, so none of the other guards have
        # anything to protect, and InferencePage.shutdown() must never
        # run (its blocking wait()-then-cleanup sequence is exactly what
        # silently destroyed the freshly generated file — see
        # MISSION_085.md).
        with patch.object(self.window.inference_page, "confirm_no_active_generation", return_value=False) as guard_mock, \
                patch.object(self.window.prompts_page, "confirm_context_change") as prompts_mock, \
                patch.object(self.window.characters_page, "confirm_context_change") as characters_mock, \
                patch.object(self.window.lora_page, "confirm_context_change") as lora_mock, \
                patch.object(self.window.settings_page, "confirm_context_change") as settings_mock, \
                patch.object(self.window.inference_page, "confirm_context_change") as inference_prompt_mock, \
                patch.object(self.window.inference_page, "confirm_pending_result_change") as pending_mock, \
                patch.object(self.window.inference_page, "shutdown") as shutdown_mock:
            event = QCloseEvent()
            self.window.closeEvent(event)

            self.assertFalse(event.isAccepted())
            guard_mock.assert_called_once()
            prompts_mock.assert_not_called()
            characters_mock.assert_not_called()
            lora_mock.assert_not_called()
            settings_mock.assert_not_called()
            inference_prompt_mock.assert_not_called()
            pending_mock.assert_not_called()
            shutdown_mock.assert_not_called()

    def test_guard_order_including_generation_active_matches_seven_guard_contract(self):
        order = []
        patchers = [
            patch.object(
                self.window.inference_page, "confirm_no_active_generation",
                side_effect=lambda message: order.append("generation_active") or True,
            ),
            patch.object(
                self.window.prompts_page, "confirm_context_change",
                side_effect=lambda: order.append("prompts") or True,
            ),
            patch.object(
                self.window.characters_page, "confirm_context_change",
                side_effect=lambda: order.append("characters") or True,
            ),
            patch.object(
                self.window.lora_page, "confirm_context_change",
                side_effect=lambda: order.append("lora") or True,
            ),
            patch.object(
                self.window.settings_page, "confirm_context_change",
                side_effect=lambda: order.append("settings") or True,
            ),
            patch.object(
                self.window.inference_page, "confirm_context_change",
                side_effect=lambda: order.append("inference_prompt") or True,
            ),
            patch.object(
                self.window.inference_page, "confirm_pending_result_change",
                side_effect=lambda: order.append("inference_pending") or True,
            ),
        ]
        with patchers[0], patchers[1], patchers[2], patchers[3], patchers[4], patchers[5], patchers[6], \
                patch.object(
                    self.window.inference_page, "shutdown",
                    side_effect=lambda: order.append("shutdown"),
                ):
            event = QCloseEvent()
            self.window.closeEvent(event)

        self.assertEqual(
            order,
            [
                "generation_active", "prompts", "characters", "lora", "settings",
                "inference_prompt", "inference_pending", "shutdown",
            ],
        )

    def test_guard_order_including_pending_matches_six_guard_contract(self):
        order = []
        patchers = [
            patch.object(
                self.window.prompts_page, "confirm_context_change",
                side_effect=lambda: order.append("prompts") or True,
            ),
            patch.object(
                self.window.characters_page, "confirm_context_change",
                side_effect=lambda: order.append("characters") or True,
            ),
            patch.object(
                self.window.lora_page, "confirm_context_change",
                side_effect=lambda: order.append("lora") or True,
            ),
            patch.object(
                self.window.settings_page, "confirm_context_change",
                side_effect=lambda: order.append("settings") or True,
            ),
            patch.object(
                self.window.inference_page, "confirm_context_change",
                side_effect=lambda: order.append("inference_prompt") or True,
            ),
            patch.object(
                self.window.inference_page, "confirm_pending_result_change",
                side_effect=lambda: order.append("inference_pending") or True,
            ),
        ]
        with patchers[0], patchers[1], patchers[2], patchers[3], patchers[4], patchers[5], \
                patch.object(
                    self.window.inference_page, "shutdown",
                    side_effect=lambda: order.append("shutdown"),
                ):
            event = QCloseEvent()
            self.window.closeEvent(event)

        self.assertEqual(
            order,
            ["prompts", "characters", "lora", "settings", "inference_prompt", "inference_pending", "shutdown"],
        )

    def test_guard_order_including_inference_matches_five_guard_contract(self):
        # Mission 083: proves Inference runs 5th, after Settings and
        # before shutdown() — appended without reordering the 4 existing
        # guards (see test_guard_order_matches_new_project_and_open_project
        # below for the original 4-guard-only coverage, left unchanged).
        order = []
        patchers = [
            patch.object(
                self.window.prompts_page, "confirm_context_change",
                side_effect=lambda: order.append("prompts") or True,
            ),
            patch.object(
                self.window.characters_page, "confirm_context_change",
                side_effect=lambda: order.append("characters") or True,
            ),
            patch.object(
                self.window.lora_page, "confirm_context_change",
                side_effect=lambda: order.append("lora") or True,
            ),
            patch.object(
                self.window.settings_page, "confirm_context_change",
                side_effect=lambda: order.append("settings") or True,
            ),
            patch.object(
                self.window.inference_page, "confirm_context_change",
                side_effect=lambda: order.append("inference") or True,
            ),
        ]
        with patchers[0], patchers[1], patchers[2], patchers[3], patchers[4], \
                patch.object(
                    self.window.inference_page, "shutdown",
                    side_effect=lambda: order.append("shutdown"),
                ):
            event = QCloseEvent()
            self.window.closeEvent(event)

        self.assertEqual(order, ["prompts", "characters", "lora", "settings", "inference", "shutdown"])

    def test_guard_order_matches_new_project_and_open_project(self):
        order = []
        patchers = [
            patch.object(
                self.window.prompts_page, "confirm_context_change",
                side_effect=lambda: order.append("prompts") or True,
            ),
            patch.object(
                self.window.characters_page, "confirm_context_change",
                side_effect=lambda: order.append("characters") or True,
            ),
            patch.object(
                self.window.lora_page, "confirm_context_change",
                side_effect=lambda: order.append("lora") or True,
            ),
            patch.object(
                self.window.settings_page, "confirm_context_change",
                side_effect=lambda: order.append("settings") or True,
            ),
        ]
        with patchers[0], patchers[1], patchers[2], patchers[3], \
                patch.object(self.window.inference_page, "shutdown"):
            event = QCloseEvent()
            self.window.closeEvent(event)

        self.assertEqual(order, ["prompts", "characters", "lora", "settings"])

    def test_shutdown_runs_only_after_all_four_guards_resolved(self):
        order = []
        patchers = [
            patch.object(
                self.window.prompts_page, "confirm_context_change",
                side_effect=lambda: order.append("prompts") or True,
            ),
            patch.object(
                self.window.characters_page, "confirm_context_change",
                side_effect=lambda: order.append("characters") or True,
            ),
            patch.object(
                self.window.lora_page, "confirm_context_change",
                side_effect=lambda: order.append("lora") or True,
            ),
            patch.object(
                self.window.settings_page, "confirm_context_change",
                side_effect=lambda: order.append("settings") or True,
            ),
        ]
        with patchers[0], patchers[1], patchers[2], patchers[3], \
                patch.object(
                    self.window.inference_page, "shutdown",
                    side_effect=lambda: order.append("shutdown"),
                ):
            event = QCloseEvent()
            self.window.closeEvent(event)

        self.assertEqual(order, ["prompts", "characters", "lora", "settings", "shutdown"])


class MainWindowCloseEventRealStateTest(unittest.TestCase):
    """
    Real Workspace/Character/LoRA/Settings state on the real window —
    only the modal Save/Discard/Cancel QMessageBox dialogs are mocked
    per-call, matching MainWindowConfirmContextChangeTest's own idiom.
    Proves persistence and dirty-state, not just orchestration.
    """

    def setUp(self):
        import shutil
        import tempfile
        from pathlib import Path

        self.dialog_guard = start_dialog_guard()

        self.window = MainWindow()
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.project_dir = Path(self.tmp_dir) / "Project"
        self.window.workspace_manager.create(self.project_dir)

    def tearDown(self):
        try:
            # By the time each test ends here, no Page is left dirty (each
            # scenario below resolves Save/Discard/Cancel to completion), so
            # a real close() is always safe.
            self.window.close()
        finally:
            stop_dialog_guard(self.dialog_guard)

    def _project_json(self):
        with open(self.project_dir / "project.json", encoding="utf-8") as f:
            return json.load(f)

    def test_no_dirty_page_closes_immediately_without_any_dialog(self):
        with patch("src.ui.pages.prompts_page.QMessageBox") as prompts_box, \
                patch("src.ui.pages.characters_page.QMessageBox") as characters_box, \
                patch("src.ui.pages.lora_page.QMessageBox") as lora_box, \
                patch("src.ui.pages.settings_page.QMessageBox") as settings_box, \
                patch("src.ui.pages.inference_page.QMessageBox") as inference_box:
            event = QCloseEvent()
            self.window.closeEvent(event)

            self.assertTrue(event.isAccepted())
            prompts_box.assert_not_called()
            characters_box.assert_not_called()
            lora_box.assert_not_called()
            settings_box.assert_not_called()
            inference_box.assert_not_called()

    def test_dirty_settings_cancel_refuses_close_and_keeps_draft(self):
        self.window.settings_page.theme_edit.setText("draft-theme")
        self.assertTrue(self.window.settings_page._dirty)

        with patch("src.ui.pages.settings_page.QMessageBox") as mock_box:
            mock_box.Cancel = QMessageBox.Cancel
            mock_box.Save = QMessageBox.Save
            mock_box.Discard = QMessageBox.Discard
            mock_box.return_value.exec.return_value = mock_box.Cancel
            event = QCloseEvent()
            self.window.closeEvent(event)

        self.assertFalse(event.isAccepted())
        self.assertTrue(self.window.settings_page._dirty)
        self.assertEqual(self.window.settings_page.theme_edit.text(), "draft-theme")

        # Mission 091: resolved directly before tearDown()'s own real
        # close() — same reason as the Inference prompt Cancel test
        # below (a real close() would otherwise hit this same,
        # now-unmocked, genuinely blocking dialog again).
        self.window.settings_page._dirty = False

    def test_dirty_settings_save_accepts_close_and_persists(self):
        self.window.settings_page.theme_edit.setText("saved-theme")

        with patch("src.ui.pages.settings_page.QMessageBox") as mock_box:
            mock_box.Cancel = QMessageBox.Cancel
            mock_box.Save = QMessageBox.Save
            mock_box.Discard = QMessageBox.Discard
            mock_box.return_value.exec.return_value = mock_box.Save
            event = QCloseEvent()
            self.window.closeEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertEqual(self._project_json()["settings"]["theme"], "saved-theme")

    def test_dirty_settings_save_failure_refuses_close_and_resyncs_field(self):
        from src.managers.workspace_manager import WorkspaceManagerError

        self.window.settings_page.theme_edit.setText("draft-theme")

        with patch("src.ui.pages.settings_page.QMessageBox") as mock_box, \
                patch.object(
                    self.window.settings_manager, "update",
                    side_effect=WorkspaceManagerError("boom"),
                ):
            mock_box.Cancel = QMessageBox.Cancel
            mock_box.Save = QMessageBox.Save
            mock_box.Discard = QMessageBox.Discard
            mock_box.return_value.exec.return_value = mock_box.Save
            event = QCloseEvent()
            self.window.closeEvent(event)

        self.assertFalse(event.isAccepted())
        # Established Mission 077 contract, unchanged by Mission 079: on a
        # save() failure the field is resynced to the restored Domain
        # value (here, still empty), never left showing the rejected
        # draft — and the close is refused regardless.
        self.assertEqual(self.window.settings_page.theme_edit.text(), "")
        self.assertFalse(self.window.settings_page._dirty)

    def test_two_dirty_pages_save_then_cancel_refuses_close_but_keeps_first_save(self):
        # Sequential semantics, no global transaction: prompts_page saves
        # successfully (first in the guard order), characters_page then
        # cancels — the close is refused, but the already-completed
        # prompts save is never rolled back.
        character = self.window.character_manager.principal_character
        self.window.character_manager.select(character.character_id)
        prompt = self.window.prompt_manager.create("Master", text="original")
        self.window.prompt_manager.select(prompt.prompt_id)
        self.window.prompts_page.text_edit.setPlainText("edited draft")
        self.assertTrue(self.window.prompts_page._dirty)

        self.window.characters_page.bio_edit.setPlainText("dirty bio draft")
        self.assertTrue(self.window.characters_page._dirty)

        with patch.object(
                    self.window.prompts_page, "_confirm_discard_before_switch",
                    return_value=QMessageBox.Save,
                ), \
                patch("src.ui.pages.characters_page.QMessageBox") as characters_box:
            characters_box.Cancel = QMessageBox.Cancel
            characters_box.Save = QMessageBox.Save
            characters_box.Discard = QMessageBox.Discard
            characters_box.return_value.exec.return_value = characters_box.Cancel
            event = QCloseEvent()
            self.window.closeEvent(event)

        self.assertFalse(event.isAccepted())

        # prompts_page's Save already completed and is not rolled back.
        self.assertFalse(self.window.prompts_page._dirty)
        on_disk = self._project_json()
        aria = next(
            c for c in on_disk["characters"] if c["character_id"] == character.character_id
        )
        self.assertEqual(aria["prompts"][0]["text"], "edited draft")

        # characters_page's Cancel correctly left its own draft dirty and
        # intact — resolved here only to allow a safe real teardown close().
        self.assertTrue(self.window.characters_page._dirty)
        self.assertEqual(self.window.characters_page.bio_edit.toPlainText(), "dirty bio draft")
        self.window.characters_page._dirty = False

    def test_dirty_inference_prompt_cancel_refuses_close_and_keeps_draft(self):
        self.window.inference_page.prompt.setPlainText("a red fox")
        self.assertTrue(self.window.inference_page._dirty)

        with patch.object(
            self.window.inference_page, "_confirm_discard_before_switch",
            return_value=QMessageBox.Cancel,
        ):
            event = QCloseEvent()
            self.window.closeEvent(event)

        self.assertFalse(event.isAccepted())
        self.assertTrue(self.window.inference_page._dirty)
        self.assertEqual(self.window.inference_page.prompt.toPlainText(), "a red fox")

        # This test's whole point is a real dirty draft surviving until
        # here — resolved directly (not via addCleanup, which runs after
        # tearDown() in this class, too late) so tearDown()'s own real
        # close() does not hit an unmocked, genuinely blocking dialog.
        self.window.inference_page._dirty = False

    def test_dirty_inference_prompt_discard_accepts_close_without_creating_prompt(self):
        character = self.window.character_manager.principal_character
        self.window.inference_page.prompt.setPlainText("a red fox")

        with patch.object(
            self.window.inference_page, "_confirm_discard_before_switch",
            return_value=QMessageBox.Discard,
        ):
            event = QCloseEvent()
            self.window.closeEvent(event)

        self.assertTrue(event.isAccepted())
        on_disk = self._project_json()
        aria = next(
            c for c in on_disk["characters"] if c["character_id"] == character.character_id
        )
        self.assertEqual(aria["prompts"], [])

        # Mission 091: _confirm_discard_before_switch()'s Discard branch
        # authorizes the transition but — unlike Save — never itself
        # clears _dirty (InferencePage.confirm_context_change(),
        # inference_page.py:783-799, mirrors PromptsPage's own
        # established pattern: normally reset_for_context_change() does
        # that cleanup on the Workspace-switch events that follow a real
        # new_project()/open_project(), but closing the window fires no
        # such event). Resolved directly here, before tearDown()'s own
        # real close() — otherwise it would hit this same, now-unmocked,
        # genuinely blocking dialog again.
        self.window.inference_page._dirty = False

    def test_dirty_inference_prompt_save_accepts_close_and_persists_new_prompt(self):
        character = self.window.character_manager.principal_character
        self.window.inference_page.prompt.setPlainText("a red fox, cinematic")

        with patch.object(
            self.window.inference_page, "_confirm_discard_before_switch",
            return_value=QMessageBox.Save,
        ), patch(
            "src.ui.pages.inference_page.QInputDialog.getText",
            return_value=("From Inference", True),
        ):
            event = QCloseEvent()
            self.window.closeEvent(event)

        self.assertTrue(event.isAccepted())
        on_disk = self._project_json()
        aria = next(
            c for c in on_disk["characters"] if c["character_id"] == character.character_id
        )
        self.assertEqual(len(aria["prompts"]), 1)
        self.assertEqual(aria["prompts"][0]["name"], "From Inference")
        self.assertEqual(aria["prompts"][0]["text"], "a red fox, cinematic")

    def test_dirty_inference_prompt_save_name_cancelled_refuses_close_and_keeps_draft(self):
        self.window.inference_page.prompt.setPlainText("a red fox")

        with patch.object(
            self.window.inference_page, "_confirm_discard_before_switch",
            return_value=QMessageBox.Save,
        ), patch(
            "src.ui.pages.inference_page.QInputDialog.getText",
            return_value=("", False),
        ):
            event = QCloseEvent()
            self.window.closeEvent(event)

        self.assertFalse(event.isAccepted())
        self.assertTrue(self.window.inference_page._dirty)
        self.assertEqual(self.window.inference_page.prompt.toPlainText(), "a red fox")

        # Same reason as the Cancel test above — resolved directly before
        # tearDown()'s own real close().
        self.window.inference_page._dirty = False

    def _make_pending_result(self):
        outputs_dir = self.project_dir / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        generated_path = outputs_dir / "generated.png"
        generated_path.write_bytes(b"fake-png-bytes")
        self.window.inference_page._generation_workspace_root = str(self.project_dir)
        self.window.inference_page._set_pending(str(generated_path))
        return generated_path

    def test_dirty_pending_result_cancel_refuses_close_and_keeps_file(self):
        generated_path = self._make_pending_result()

        with patch.object(
            self.window.inference_page, "_confirm_pending_before_switch",
            return_value="cancel",
        ):
            event = QCloseEvent()
            self.window.closeEvent(event)

        self.assertFalse(event.isAccepted())
        self.assertEqual(self.window.inference_page._pending_path, str(generated_path))
        self.assertTrue(generated_path.exists())
        self.assertTrue(self.window.inference_page.accept_button.isEnabled())

        # Same reason as the prompt-dirty Cancel test above — resolved
        # directly before tearDown()'s own real close() (which would
        # otherwise hit this same, now-unmocked, genuinely blocking
        # dialog again).
        self.window.inference_page._pending_path = None

    def test_dirty_pending_result_reject_accepts_close_and_deletes_file(self):
        generated_path = self._make_pending_result()

        with patch.object(
            self.window.inference_page, "_confirm_pending_before_switch",
            return_value="reject",
        ):
            event = QCloseEvent()
            self.window.closeEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertFalse(generated_path.exists())
        self.assertEqual(self.window.workspace_manager.current_workspace.images, [])

    def test_dirty_pending_result_accept_accepts_close_and_persists_image(self):
        generated_path = self._make_pending_result()

        with patch.object(
            self.window.inference_page, "_confirm_pending_before_switch",
            return_value="accept",
        ):
            event = QCloseEvent()
            self.window.closeEvent(event)

        self.assertTrue(event.isAccepted())
        on_disk = self._project_json()
        self.assertEqual([img["file_path"] for img in on_disk["images"]], [str(generated_path)])
        self.assertTrue(generated_path.exists())

    def test_dirty_pending_result_accept_persistence_failure_refuses_close_and_keeps_file(self):
        from src.infrastructure.storage.workspace_storage import WorkspaceStorage, WorkspaceStorageError

        generated_path = self._make_pending_result()

        with patch.object(
            self.window.inference_page, "_confirm_pending_before_switch",
            return_value="accept",
        ), patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ), patch("src.ui.pages.inference_page.QMessageBox.critical") as mock_critical:
            event = QCloseEvent()
            self.window.closeEvent(event)

        mock_critical.assert_called_once()
        self.assertFalse(event.isAccepted())
        self.assertEqual(self.window.inference_page._pending_path, str(generated_path))
        self.assertTrue(generated_path.exists())

        self.window.inference_page._pending_path = None

    def test_shutdown_never_called_when_pending_guard_refuses_close(self):
        self._make_pending_result()

        with patch.object(
            self.window.inference_page, "_confirm_pending_before_switch",
            return_value="cancel",
        ), patch.object(self.window.inference_page, "shutdown") as shutdown_mock:
            event = QCloseEvent()
            self.window.closeEvent(event)

            shutdown_mock.assert_not_called()

        self.window.inference_page._pending_path = None

    # --- Mission 085: genuinely active generation ---

    def _start_controlled_generation(self, output_filename="controlled.png"):
        outputs_dir = self.project_dir / "outputs"
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

    def test_close_refused_immediately_while_generation_genuinely_active(self):
        output_path, release = self._start_controlled_generation()

        with patch("src.ui.pages.prompts_page.QMessageBox") as prompts_box, \
                patch("src.ui.pages.characters_page.QMessageBox") as characters_box, \
                patch("src.ui.pages.lora_page.QMessageBox") as lora_box, \
                patch("src.ui.pages.settings_page.QMessageBox") as settings_box, \
                patch("src.ui.pages.inference_page.QMessageBox"), \
                patch.object(self.window.inference_page, "shutdown") as shutdown_mock:
            event = QCloseEvent()
            self.window.closeEvent(event)

        self.assertFalse(event.isAccepted())
        # None of the 6 pre-existing guards ever ran — no draft was
        # saved, no dialog was shown, and shutdown() (whose blocking
        # wait()-then-cleanup sequence is the actual bug) was never
        # reached.
        prompts_box.assert_not_called()
        characters_box.assert_not_called()
        lora_box.assert_not_called()
        settings_box.assert_not_called()
        shutdown_mock.assert_not_called()

        release.set()
        self.assertTrue(_wait_until(lambda: output_path.exists(), timeout=30.0))
        _wait_until(lambda: self.window.inference_page._pending_path is not None, timeout=30.0)
        self.window.inference_page._pending_path = None

    def test_generation_continues_and_becomes_pending_after_close_refused(self):
        output_path, release = self._start_controlled_generation()

        with patch("src.ui.pages.inference_page.QMessageBox"):
            event = QCloseEvent()
            self.window.closeEvent(event)
        self.assertFalse(event.isAccepted())

        release.set()
        self.assertTrue(_wait_until(lambda: self.window.inference_page._pending_path is not None, timeout=30.0))

        self.assertEqual(self.window.inference_page._pending_path, str(output_path))
        self.assertTrue(output_path.exists())
        self.assertTrue(self.window.inference_page.accept_button.isEnabled())
        self.window.inference_page._pending_path = None

    def test_second_close_after_generation_finishes_hits_m084_pending_guard(self):
        output_path, release = self._start_controlled_generation()

        with patch("src.ui.pages.inference_page.QMessageBox"):
            first_event = QCloseEvent()
            self.window.closeEvent(first_event)
        self.assertFalse(first_event.isAccepted())

        release.set()
        self.assertTrue(_wait_until(lambda: self.window.inference_page._pending_path is not None, timeout=30.0))
        self.assertEqual(self.window.inference_page._pending_path, str(output_path))

        with patch.object(
            self.window.inference_page, "_confirm_pending_before_switch",
            return_value="reject",
        ):
            second_event = QCloseEvent()
            self.window.closeEvent(second_event)

        self.assertTrue(second_event.isAccepted())
        self.assertFalse(output_path.exists())

    def test_dirty_prompt_is_never_touched_when_generation_active_guard_refuses(self):
        # Mission 085's guard must run BEFORE the Inference prompt dirty
        # guard (and all other dirty guards) so a genuinely active
        # generation is reported immediately, without ever prompting the
        # user to Save/Discard/Cancel an unrelated draft first.
        output_path, release = self._start_controlled_generation()
        self.window.inference_page.prompt.setPlainText("a test prompt - still dirty")
        self.assertTrue(self.window.inference_page._dirty)

        with patch.object(self.window.inference_page, "_confirm_discard_before_switch") as dialog_mock, \
                patch("src.ui.pages.inference_page.QMessageBox"):
            event = QCloseEvent()
            self.window.closeEvent(event)

            dialog_mock.assert_not_called()

        self.assertFalse(event.isAccepted())
        self.assertTrue(self.window.inference_page._dirty)
        self.assertEqual(
            self.window.inference_page.prompt.toPlainText(), "a test prompt - still dirty"
        )

        release.set()
        _wait_until(lambda: self.window.inference_page._pending_path is not None, timeout=30.0)
        self.window.inference_page._pending_path = None
        self.window.inference_page._dirty = False

    def test_no_active_generation_close_unchanged(self):
        # Non-regression: without any generation running,
        # confirm_no_active_generation() must return True with no
        # message and no effect on the rest of the chain.
        with patch("src.ui.pages.inference_page.QMessageBox.warning") as mock_warning:
            event = QCloseEvent()
            self.window.closeEvent(event)

            mock_warning.assert_not_called()

        self.assertTrue(event.isAccepted())


if __name__ == "__main__":
    unittest.main()
