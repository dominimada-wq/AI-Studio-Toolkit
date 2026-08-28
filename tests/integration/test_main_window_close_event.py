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
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from src.ui.main_window import MainWindow

_app = QApplication.instance() or QApplication([])


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

        self.window = MainWindow()
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.project_dir = Path(self.tmp_dir) / "Project"
        self.window.workspace_manager.create(self.project_dir)

    def tearDown(self):
        # By the time each test ends here, no Page is left dirty (each
        # scenario below resolves Save/Discard/Cancel to completion), so
        # a real close() is always safe.
        self.window.close()

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


if __name__ == "__main__":
    unittest.main()
