"""
Real-widget coverage for PromptAssistantDialog (Mission 031) — mode
selection ("Créer"/"Améliorer"), the explicit existing-prompt preview
before an "Améliorer" call, the non-blocking assist call (real QThread/
PromptAssistantWorker), and result handoff via result_text.
PromptAssistantManager is mocked throughout: no real Ollama instance.
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from src.managers.prompt_assistant_manager import CharacterContext, PromptAssistantError
from src.ui.dialogs.prompt_assistant_dialog import PromptAssistantDialog

_app = QApplication.instance() or QApplication([])


class PromptAssistantDialogLayoutTest(unittest.TestCase):
    """
    Mission 031 smoke test follow-up: the dialog was too small to read/
    work with generated prompts comfortably — a larger starting size,
    resizability, and expanding text areas were added. No size/position
    persistence is introduced.
    """

    def test_initial_size_is_at_least_800_by_700(self):
        dialog = PromptAssistantDialog(MagicMock(), existing_prompt="")
        self.addCleanup(dialog.close)

        self.assertGreaterEqual(dialog.size().width(), 800)
        self.assertGreaterEqual(dialog.size().height(), 700)

    def test_dialog_is_resizable(self):
        # QDialog is resizable unless setFixedSize()/a fixed size policy
        # is used — confirmed here by actually resizing larger than the
        # default starting size and checking it took effect.
        dialog = PromptAssistantDialog(MagicMock(), existing_prompt="")
        self.addCleanup(dialog.close)

        dialog.resize(1100, 900)

        self.assertEqual(dialog.size().width(), 1100)
        self.assertEqual(dialog.size().height(), 900)

    def test_result_area_gets_a_larger_share_of_extra_space_than_request_area(self):
        dialog = PromptAssistantDialog(MagicMock(), existing_prompt="")
        self.addCleanup(dialog.close)
        layout = dialog.layout()

        request_index = layout.indexOf(dialog.request_edit)
        result_index = layout.indexOf(dialog.result_edit)

        self.assertGreater(layout.stretch(result_index), layout.stretch(request_index))


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
        time.sleep(0.001)
    return predicate()


class PromptAssistantDialogModeTest(unittest.TestCase):

    def test_only_create_mode_offered_when_no_existing_prompt(self):
        dialog = PromptAssistantDialog(MagicMock(), existing_prompt="")
        self.addCleanup(dialog.close)

        self.assertIsNone(dialog.improve_mode_button)
        self.assertFalse(dialog.existing_prompt_preview.isVisible())

    def test_both_modes_offered_when_an_existing_prompt_is_present(self):
        dialog = PromptAssistantDialog(MagicMock(), existing_prompt="a fox in a forest")
        self.addCleanup(dialog.close)

        self.assertIsNotNone(dialog.improve_mode_button)

    def test_existing_prompt_preview_shown_only_in_improve_mode(self):
        # isVisibleTo(dialog) reflects the widget's own show/hide state
        # relative to its parent, without requiring the dialog itself to
        # be shown on screen — unlike isVisible(), which is always False
        # for a top-level never actually shown (headless-safe here).
        dialog = PromptAssistantDialog(MagicMock(), existing_prompt="a fox in a forest")
        self.addCleanup(dialog.close)

        self.assertFalse(dialog.existing_prompt_preview.isVisibleTo(dialog))

        dialog.improve_mode_button.click()
        self.assertTrue(dialog.existing_prompt_preview.isVisibleTo(dialog))
        self.assertEqual(dialog.existing_prompt_preview.toPlainText(), "a fox in a forest")

        dialog.create_mode_button.click()
        self.assertFalse(dialog.existing_prompt_preview.isVisibleTo(dialog))


class PromptAssistantDialogGenerateTest(unittest.TestCase):

    @patch("src.ui.dialogs.prompt_assistant_dialog.QMessageBox.warning")
    def test_empty_request_is_rejected_without_calling_the_manager(self, mock_warning):
        manager = MagicMock()
        dialog = PromptAssistantDialog(manager, existing_prompt="")
        self.addCleanup(dialog.close)

        dialog.request_edit.setPlainText("   ")
        dialog.generate_button.click()

        manager.assist.assert_not_called()
        mock_warning.assert_called_once()

    def test_create_mode_calls_assist_without_existing_prompt(self):
        manager = MagicMock()
        manager.assist.return_value = "a fox in a forest"

        dialog = PromptAssistantDialog(manager, existing_prompt="")
        self.addCleanup(dialog.close)

        dialog.request_edit.setPlainText("a fox in a forest")
        dialog.generate_button.click()

        self.assertTrue(_wait_until(lambda: dialog.use_result_button.isEnabled()))

        manager.assist.assert_called_once_with(
            "a fox in a forest", existing_prompt="", character_context=None
        )
        self.assertEqual(dialog.result_edit.toPlainText(), "a fox in a forest")

    def test_improve_mode_calls_assist_with_the_existing_prompt(self):
        manager = MagicMock()
        manager.assist.return_value = "a fox in a forest, golden hour"

        dialog = PromptAssistantDialog(manager, existing_prompt="a fox in a forest")
        self.addCleanup(dialog.close)

        dialog.improve_mode_button.click()
        dialog.request_edit.setPlainText("make it more cinematic")
        dialog.generate_button.click()

        self.assertTrue(_wait_until(lambda: dialog.use_result_button.isEnabled()))

        manager.assist.assert_called_once_with(
            "make it more cinematic", existing_prompt="a fox in a forest", character_context=None
        )

    def test_controls_disabled_while_generation_is_in_progress(self):
        manager = MagicMock()
        manager.assist.return_value = "result"

        dialog = PromptAssistantDialog(manager, existing_prompt="")
        self.addCleanup(dialog.close)

        dialog.request_edit.setPlainText("a fox")
        dialog.generate_button.click()

        self.assertFalse(dialog.generate_button.isEnabled())
        self.assertFalse(dialog.cancel_button.isEnabled())

        self.assertTrue(_wait_until(lambda: dialog.use_result_button.isEnabled()))

        self.assertTrue(dialog.generate_button.isEnabled())
        self.assertTrue(dialog.cancel_button.isEnabled())

    @patch("src.ui.dialogs.prompt_assistant_dialog.QMessageBox.critical")
    def test_prompt_assistant_error_does_not_crash_and_re_enables_controls(self, mock_critical):
        manager = MagicMock()
        manager.assist.side_effect = PromptAssistantError("Ollama server unreachable")

        dialog = PromptAssistantDialog(manager, existing_prompt="")
        self.addCleanup(dialog.close)

        dialog.request_edit.setPlainText("a fox")
        dialog.generate_button.click()

        self.assertTrue(_wait_until(lambda: mock_critical.called))
        self.assertFalse(dialog.use_result_button.isEnabled())
        self.assertEqual(dialog.result_edit.toPlainText(), "")
        self.assertIn("Ollama server unreachable", mock_critical.call_args[0][2])
        self.assertTrue(dialog.generate_button.isEnabled())

    @patch("src.ui.dialogs.prompt_assistant_dialog.QMessageBox.critical")
    def test_use_result_button_stays_enabled_after_a_failed_follow_up_generation(self, mock_critical):
        """
        Mission 040: a successful result already displayed must remain
        usable after a later generation fails — result_edit already
        preserved it correctly (Mission 039's fallback discipline is
        unrelated here), the defect was use_result_button never
        tracking that content back on failure.
        """

        manager = MagicMock()
        manager.assist.side_effect = ["a fox in a forest", PromptAssistantError("Ollama server unreachable")]

        dialog = PromptAssistantDialog(manager, existing_prompt="")
        self.addCleanup(dialog.close)

        dialog.request_edit.setPlainText("a fox in a forest")
        dialog.generate_button.click()

        self.assertTrue(_wait_until(lambda: dialog.use_result_button.isEnabled()))
        self.assertEqual(dialog.result_edit.toPlainText(), "a fox in a forest")

        dialog.request_edit.setPlainText("make it more cinematic")
        dialog.generate_button.click()

        self.assertTrue(_wait_until(lambda: mock_critical.called))
        self.assertEqual(dialog.result_edit.toPlainText(), "a fox in a forest")
        self.assertTrue(dialog.use_result_button.isEnabled())


class PromptAssistantDialogIdentityCheckboxTest(unittest.TestCase):
    """
    Mission 034: the dialog receives an already-resolved
    CharacterContext | None — it never knows Character or
    CharacterManager, it only decides whether to forward the object it
    was given.
    """

    def test_checkbox_absent_when_no_context_is_given(self):
        dialog = PromptAssistantDialog(MagicMock(), existing_prompt="")
        self.addCleanup(dialog.close)

        self.assertIsNone(dialog.use_identity_checkbox)

    def test_checkbox_present_when_a_context_is_given(self):
        context = CharacterContext(character_lock="lock")

        dialog = PromptAssistantDialog(MagicMock(), existing_prompt="", character_context=context)
        self.addCleanup(dialog.close)

        self.assertIsNotNone(dialog.use_identity_checkbox)
        self.assertTrue(dialog.use_identity_checkbox.isVisibleTo(dialog))

    def test_checkbox_unchecked_by_default(self):
        context = CharacterContext(character_lock="lock")

        dialog = PromptAssistantDialog(MagicMock(), existing_prompt="", character_context=context)
        self.addCleanup(dialog.close)

        self.assertFalse(dialog.use_identity_checkbox.isChecked())

    def test_unchecked_checkbox_sends_none_context(self):
        manager = MagicMock()
        manager.assist.return_value = "result"
        context = CharacterContext(character_lock="lock")

        dialog = PromptAssistantDialog(manager, existing_prompt="", character_context=context)
        self.addCleanup(dialog.close)

        dialog.request_edit.setPlainText("a fox")
        dialog.generate_button.click()

        self.assertTrue(_wait_until(lambda: dialog.use_result_button.isEnabled()))
        manager.assist.assert_called_once_with("a fox", existing_prompt="", character_context=None)

    def test_checked_checkbox_sends_the_context_through(self):
        manager = MagicMock()
        manager.assist.return_value = "result"
        context = CharacterContext(character_lock="lock")

        dialog = PromptAssistantDialog(manager, existing_prompt="", character_context=context)
        self.addCleanup(dialog.close)

        dialog.use_identity_checkbox.setChecked(True)
        dialog.request_edit.setPlainText("a fox")
        dialog.generate_button.click()

        self.assertTrue(_wait_until(lambda: dialog.use_result_button.isEnabled()))
        manager.assist.assert_called_once_with("a fox", existing_prompt="", character_context=context)

    def test_create_mode_still_works_with_a_context_present(self):
        manager = MagicMock()
        manager.assist.return_value = "result"
        context = CharacterContext(character_lock="lock")

        dialog = PromptAssistantDialog(manager, existing_prompt="", character_context=context)
        self.addCleanup(dialog.close)

        dialog.request_edit.setPlainText("a fox")
        dialog.generate_button.click()

        self.assertTrue(_wait_until(lambda: dialog.use_result_button.isEnabled()))
        self.assertEqual(dialog.result_edit.toPlainText(), "result")

    def test_improve_mode_still_works_with_a_context_present(self):
        manager = MagicMock()
        manager.assist.return_value = "improved"
        context = CharacterContext(character_lock="lock")

        dialog = PromptAssistantDialog(
            manager, existing_prompt="a fox in a forest", character_context=context
        )
        self.addCleanup(dialog.close)

        dialog.improve_mode_button.click()
        dialog.request_edit.setPlainText("make it more cinematic")
        dialog.use_identity_checkbox.setChecked(True)
        dialog.generate_button.click()

        self.assertTrue(_wait_until(lambda: dialog.use_result_button.isEnabled()))
        manager.assist.assert_called_once_with(
            "make it more cinematic", existing_prompt="a fox in a forest", character_context=context
        )

    @patch("src.ui.dialogs.prompt_assistant_dialog.QMessageBox.critical")
    def test_backend_error_still_handled_without_a_real_messagebox_when_context_present(self, mock_critical):
        manager = MagicMock()
        manager.assist.side_effect = PromptAssistantError("Ollama server unreachable")
        context = CharacterContext(character_lock="lock")

        dialog = PromptAssistantDialog(manager, existing_prompt="", character_context=context)
        self.addCleanup(dialog.close)

        dialog.use_identity_checkbox.setChecked(True)
        dialog.request_edit.setPlainText("a fox")
        dialog.generate_button.click()

        self.assertTrue(_wait_until(lambda: mock_critical.called))
        self.assertFalse(dialog.use_result_button.isEnabled())


class PromptAssistantDialogResultHandoffTest(unittest.TestCase):

    def test_use_result_sets_result_text_and_accepts(self):
        manager = MagicMock()
        manager.assist.return_value = "a fox in a forest"

        dialog = PromptAssistantDialog(manager, existing_prompt="")
        self.addCleanup(dialog.close)

        dialog.request_edit.setPlainText("a fox")
        dialog.generate_button.click()
        self.assertTrue(_wait_until(lambda: dialog.use_result_button.isEnabled()))

        dialog.use_result_button.click()

        self.assertEqual(dialog.result_text, "a fox in a forest")

    def test_result_text_stays_none_if_dialog_is_cancelled(self):
        dialog = PromptAssistantDialog(MagicMock(), existing_prompt="")
        self.addCleanup(dialog.close)

        dialog.cancel_button.click()

        self.assertIsNone(dialog.result_text)


if __name__ == "__main__":
    unittest.main()
