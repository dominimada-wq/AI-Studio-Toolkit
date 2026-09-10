"""
Mission 109: "Training Result -> Inference Handoff" orchestration in
MainWindow -- TrainingPage.use_lora_in_inference_requested -> MainWindow
-> InferencePage.refresh_lora_selector(target_lora_id=...) -> navigation
(same Option A mediator pattern as Prompts -> Inference, Mission 033).

Isolation (established after Mission 103): a real MainWindow() always
uses real storage locations for LoRALibraryManager/ApplicationSettings
(no override, see main_window.py). These tests never call any real
LoRALibraryManager-mutating method on window.lora_library_manager --
list_loras() (the only method refresh_lora_selector() calls) is patched
to return controlled fake LoRA entries, so no real Central LoRA Library
registry or file on disk is ever touched.
"""

import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from src.domain.lora import LoRA
from src.ui.main_window import MainWindow

_app = QApplication.instance() or QApplication([])


class MainWindowTrainingToInferenceTest(unittest.TestCase):

    def setUp(self):
        self.window = MainWindow()
        self.addCleanup(self.window.close)

        self.lora_a = LoRA(lora_id="lora-a", name="Zaraya Koyah SDX")
        self.lora_b = LoRA(lora_id="lora-b", name="Other LoRA")
        self._list_loras_patcher = patch.object(
            self.window.lora_library_manager,
            "list_loras",
            return_value=[self.lora_a, self.lora_b],
        )
        self._list_loras_patcher.start()
        self.addCleanup(self._list_loras_patcher.stop)

    def test_signal_selects_the_target_lora_and_navigates_to_inference(self):
        self.window.inference_page.set_prompt_text("a red fox")

        self.window.training_page.use_lora_in_inference_requested.emit("lora-a")

        self.assertEqual(self.window.inference_page._selected_lora_choice, "lora-a")
        self.assertEqual(self.window.inference_page.lora_combo.currentText(), "Zaraya Koyah SDX")
        self.assertIs(self.window.stack.currentWidget(), self.window.inference_page)

    def test_signal_never_modifies_the_inference_prompt(self):
        self.window.inference_page.set_prompt_text("a red fox, unchanged")

        self.window.training_page.use_lora_in_inference_requested.emit("lora-a")

        self.assertEqual(self.window.inference_page.prompt_text(), "a red fox, unchanged")

    def test_signal_navigates_even_from_a_different_starting_page(self):
        self.window.sidebar.select_page("characters")
        self.assertIsNot(self.window.stack.currentWidget(), self.window.inference_page)

        self.window.training_page.use_lora_in_inference_requested.emit("lora-b")

        self.assertIs(self.window.stack.currentWidget(), self.window.inference_page)
        self.assertEqual(self.window.inference_page._selected_lora_choice, "lora-b")

    def test_target_lora_id_overrides_a_previously_selected_lora(self):
        self.window.inference_page.refresh_lora_selector(target_lora_id="lora-b")
        self.assertEqual(self.window.inference_page._selected_lora_choice, "lora-b")

        self.window.training_page.use_lora_in_inference_requested.emit("lora-a")

        self.assertEqual(self.window.inference_page._selected_lora_choice, "lora-a")

    def test_training_page_never_calls_workspace_manager_save(self):
        with patch.object(self.window.workspace_manager, "save") as mock_save:
            self.window.training_page.use_lora_in_inference_requested.emit("lora-a")

            mock_save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
