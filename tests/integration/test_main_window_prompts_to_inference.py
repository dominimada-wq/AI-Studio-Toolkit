"""
Mission 033: "Envoyer vers Inference" orchestration in MainWindow —
PromptsPage.send_to_inference_requested -> MainWindow -> InferencePage
-> navigation (Option A, see docs/missions/MISSION_033.md section 4.1).
Same narrow-scope pattern as test_main_window_new_project.py: a real
MainWindow() with only the external boundary (QMessageBox) mocked. The
confirmation dialog itself is always fully mocked — a real exec()
would block the test process (same lesson as Mission 014/015's modal
dialogs).
"""

import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow

_app = QApplication.instance() or QApplication([])


class MainWindowPromptsToInferenceTest(unittest.TestCase):

    def setUp(self):
        self.window = MainWindow()
        self.addCleanup(self.window.close)

    def test_inference_empty_transfers_immediately_without_confirmation(self):
        self.window.inference_page.set_prompt_text("")
        self.window.prompts_page.text_edit.setPlainText("a red fox")

        with patch("src.ui.main_window.QMessageBox") as mock_box_class:
            self.window.prompts_page.send_to_inference_button.click()
            mock_box_class.assert_not_called()

        self.assertEqual(self.window.inference_page.prompt_text(), "a red fox")
        self.assertIs(self.window.stack.currentWidget(), self.window.inference_page)

    def test_inference_whitespace_only_transfers_immediately(self):
        self.window.inference_page.set_prompt_text("   \n  ")
        self.window.prompts_page.text_edit.setPlainText("a red fox")

        with patch("src.ui.main_window.QMessageBox") as mock_box_class:
            self.window.prompts_page.send_to_inference_button.click()
            mock_box_class.assert_not_called()

        self.assertEqual(self.window.inference_page.prompt_text(), "a red fox")
        self.assertIs(self.window.stack.currentWidget(), self.window.inference_page)

    def test_inference_identical_text_no_confirmation_and_navigates(self):
        self.window.inference_page.set_prompt_text("a red fox")
        self.window.prompts_page.text_edit.setPlainText("a red fox")

        with patch("src.ui.main_window.QMessageBox") as mock_box_class:
            self.window.prompts_page.send_to_inference_button.click()
            mock_box_class.assert_not_called()

        self.assertEqual(self.window.inference_page.prompt_text(), "a red fox")
        self.assertIs(self.window.stack.currentWidget(), self.window.inference_page)

    def test_inference_text_differing_only_by_whitespace_still_prompts_confirmation(self):
        # Exact string comparison required — no normalization.
        self.window.inference_page.set_prompt_text("a red fox")
        self.window.prompts_page.text_edit.setPlainText("a red fox ")

        replace_button = MagicMock(name="replace_button")
        cancel_button = MagicMock(name="cancel_button")

        with patch("src.ui.main_window.QMessageBox") as mock_box_class:
            mock_box = mock_box_class.return_value
            mock_box.addButton.side_effect = [replace_button, cancel_button]
            mock_box.clickedButton.return_value = cancel_button

            self.window.prompts_page.send_to_inference_button.click()

            mock_box_class.assert_called_once()
            mock_box.exec.assert_called_once()

        self.assertEqual(self.window.inference_page.prompt_text(), "a red fox")

    def test_inference_different_text_confirmed_replaces_and_navigates(self):
        self.window.inference_page.set_prompt_text("an old prompt")
        self.window.prompts_page.text_edit.setPlainText("a new prompt")

        replace_button = MagicMock(name="replace_button")
        cancel_button = MagicMock(name="cancel_button")

        with patch("src.ui.main_window.QMessageBox") as mock_box_class:
            mock_box = mock_box_class.return_value
            mock_box.addButton.side_effect = [replace_button, cancel_button]
            mock_box.clickedButton.return_value = replace_button

            self.window.prompts_page.send_to_inference_button.click()

        self.assertEqual(self.window.inference_page.prompt_text(), "a new prompt")
        self.assertIs(self.window.stack.currentWidget(), self.window.inference_page)

    def test_inference_different_text_cancelled_changes_nothing_and_does_not_navigate(self):
        self.window.inference_page.set_prompt_text("an old prompt")
        self.window.prompts_page.text_edit.setPlainText("a new prompt")

        replace_button = MagicMock(name="replace_button")
        cancel_button = MagicMock(name="cancel_button")

        with patch("src.ui.main_window.QMessageBox") as mock_box_class:
            mock_box = mock_box_class.return_value
            mock_box.addButton.side_effect = [replace_button, cancel_button]
            mock_box.clickedButton.return_value = cancel_button

            self.window.prompts_page.send_to_inference_button.click()

        self.assertEqual(self.window.inference_page.prompt_text(), "an old prompt")
        self.assertEqual(self.window.prompts_page.text_edit.toPlainText(), "a new prompt")
        self.assertIsNot(self.window.stack.currentWidget(), self.window.inference_page)
        self.assertIs(self.window.stack.currentWidget(), self.window.dashboard_page)

    def test_transfer_never_calls_prompt_manager_update_text_or_create(self):
        self.window.inference_page.set_prompt_text("")
        self.window.prompts_page.text_edit.setPlainText("a red fox")

        with patch.object(self.window.prompt_manager, "update_text") as mock_update, \
                patch.object(self.window.prompt_manager, "create") as mock_create:
            self.window.prompts_page.send_to_inference_button.click()

            mock_update.assert_not_called()
            mock_create.assert_not_called()

    def test_transfer_never_calls_workspace_manager_save(self):
        self.window.inference_page.set_prompt_text("")
        self.window.prompts_page.text_edit.setPlainText("a red fox")

        with patch.object(self.window.workspace_manager, "save") as mock_save:
            self.window.prompts_page.send_to_inference_button.click()

            mock_save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
