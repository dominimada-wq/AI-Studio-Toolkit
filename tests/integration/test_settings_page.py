"""
First dedicated Qt coverage for SettingsPage (Mission 025). Focused on
the checkpoint discovery/selection feature: the editable QComboBox
replacing the former free-text checkpoint field, the "Rafraîchir les
checkpoints" button querying a real ComfyUIEngine.list_checkpoints()
(entirely mocked here — no network access, no real ComfyUI instance),
and the manual-entry fallback that must always remain available. The
rest of SettingsPage's lifecycle (Workspace section, other Application
fields) is already covered by test_settings_roundtrip.py/
test_application_settings_roundtrip.py and is only touched here to
confirm refresh_checkpoints() never disturbs it.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QComboBox

from src.core.event_bus import EventBus
from src.engines.ai_backend import AIBackendError, AIModelInfo
from src.engines.comfyui_engine import ComfyUIEngineError
from src.infrastructure.storage.application_settings_storage import (
    ApplicationSettingsStorage,
    ApplicationSettingsStorageError,
)
from src.infrastructure.storage.workspace_storage import (
    WorkspaceStorage,
    WorkspaceStorageError,
)
from src.managers.application_settings_manager import ApplicationSettingsManager
from src.managers.settings_manager import SettingsManager
from src.managers.workspace_manager import (
    WorkspaceManager,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_SAVED,
    WORKSPACE_CLOSED,
)
from src.ui.pages.settings_page import (
    CHECKPOINT_DISCOVERY_TIMEOUT,
    LORA_DISCOVERY_TIMEOUT,
    OLLAMA_DISCOVERY_TIMEOUT,
    SettingsPage,
)

_app = QApplication.instance() or QApplication([])


class SettingsPageCheckpointDiscoveryTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        self.settings_manager = SettingsManager(workspace_manager)
        self.application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "AppSettings", event_bus=event_bus
        )
        self.page = SettingsPage(self.settings_manager, self.application_settings_manager)

    def _combo_items(self):
        combo = self.page.comfyui_checkpoint_name_edit
        return [combo.itemText(index) for index in range(combo.count())]

    def test_checkpoint_field_is_an_editable_combo_box(self):
        combo = self.page.comfyui_checkpoint_name_edit
        self.assertIsInstance(combo, QComboBox)
        self.assertTrue(combo.isEditable())

    def test_persisted_checkpoint_value_restored_on_load(self):
        # ApplicationSettings' own literal default (Mission 018),
        # displayed without requiring any discovery.
        self.assertEqual(
            self.page.comfyui_checkpoint_name_edit.currentText(),
            "v1-5-pruned-emaonly-fp16.safetensors",
        )

    @patch("src.ui.pages.settings_page.ComfyUIEngine")
    def test_refresh_populates_combo_box_with_discovered_checkpoints(self, mock_engine_class):
        mock_engine_class.return_value.list_checkpoints.return_value = [
            "Juggernaut-XL_v9.safetensors",
            "v1-5-pruned-emaonly-fp16.safetensors",
        ]

        self.page.refresh_checkpoints_button.click()

        self.assertEqual(
            self._combo_items(),
            ["Juggernaut-XL_v9.safetensors", "v1-5-pruned-emaonly-fp16.safetensors"],
        )

    @patch("src.ui.pages.settings_page.ComfyUIEngine")
    def test_refresh_preserves_currently_displayed_value_even_if_absent_from_discovered_list(
        self, mock_engine_class
    ):
        mock_engine_class.return_value.list_checkpoints.return_value = ["other.safetensors"]

        # A value the user already typed/kept, not present on the server.
        self.page.comfyui_checkpoint_name_edit.setCurrentText("my_custom_checkpoint.safetensors")

        self.page.refresh_checkpoints_button.click()

        self.assertEqual(self._combo_items(), ["other.safetensors"])
        self.assertEqual(
            self.page.comfyui_checkpoint_name_edit.currentText(), "my_custom_checkpoint.safetensors"
        )

    @patch("src.ui.pages.settings_page.ComfyUIEngine")
    def test_selecting_a_discovered_checkpoint_then_save_persists_it(self, mock_engine_class):
        mock_engine_class.return_value.list_checkpoints.return_value = [
            "a.safetensors",
            "b.safetensors",
        ]
        self.page.refresh_checkpoints_button.click()

        self.page.comfyui_checkpoint_name_edit.setCurrentIndex(1)
        self.page.save_application_settings()

        self.assertEqual(
            self.application_settings_manager.settings.comfyui_checkpoint_name, "b.safetensors"
        )

    def test_manual_entry_then_save_persists_it(self):
        # No discovery attempted at all — pure free-text fallback, the
        # only option available for a remote/cloud ComfyUI instance.
        self.page.comfyui_checkpoint_name_edit.setCurrentText("manually_typed.safetensors")

        self.page.save_application_settings()

        self.assertEqual(
            self.application_settings_manager.settings.comfyui_checkpoint_name,
            "manually_typed.safetensors",
        )

    def test_reload_after_save_restores_persisted_value(self):
        self.page.comfyui_checkpoint_name_edit.setCurrentText("restored.safetensors")
        self.page.save_application_settings()

        self.page.update_application_settings()

        self.assertEqual(
            self.page.comfyui_checkpoint_name_edit.currentText(), "restored.safetensors"
        )

    @patch("src.ui.pages.settings_page.ComfyUIEngine")
    def test_refresh_uses_the_currently_typed_url_not_necessarily_saved(self, mock_engine_class):
        mock_engine_class.return_value.list_checkpoints.return_value = []

        # Testing an address before ever saving it (Mission 025, section 7).
        self.page.comfyui_url_edit.setText("http://192.168.1.99:8188")

        self.page.refresh_checkpoints_button.click()

        mock_engine_class.assert_called_once_with(
            base_url="http://192.168.1.99:8188", timeout=CHECKPOINT_DISCOVERY_TIMEOUT
        )

    @patch("src.ui.pages.settings_page.ComfyUIEngine")
    def test_refresh_uses_a_short_dedicated_timeout_not_the_generation_timeout(self, mock_engine_class):
        mock_engine_class.return_value.list_checkpoints.return_value = []

        self.page.refresh_checkpoints_button.click()

        used_timeout = mock_engine_class.call_args.kwargs["timeout"]
        self.assertEqual(used_timeout, CHECKPOINT_DISCOVERY_TIMEOUT)
        self.assertLess(used_timeout, 120.0)

    @patch("src.ui.pages.settings_page.ComfyUIEngine")
    def test_refresh_with_unreachable_server_does_not_raise_and_settings_stays_usable(
        self, mock_engine_class
    ):
        mock_engine_class.return_value.list_checkpoints.side_effect = ComfyUIEngineError(
            "ComfyUI server unreachable"
        )

        # Must not raise/crash SettingsPage.
        self.page.refresh_checkpoints_button.click()

        self.assertIn("impossible", self.page.checkpoint_discovery_status_label.text().lower())

        # Manual entry and save remain fully available afterward.
        self.page.comfyui_checkpoint_name_edit.setCurrentText("fallback.safetensors")
        self.page.save_application_settings()
        self.assertEqual(
            self.application_settings_manager.settings.comfyui_checkpoint_name, "fallback.safetensors"
        )

    @patch("src.ui.pages.settings_page.ComfyUIEngine")
    def test_refresh_with_zero_checkpoints_reports_status_without_error(self, mock_engine_class):
        mock_engine_class.return_value.list_checkpoints.return_value = []

        self.page.refresh_checkpoints_button.click()

        self.assertEqual(self._combo_items(), [])
        self.assertIn("aucun", self.page.checkpoint_discovery_status_label.text().lower())

    def test_refresh_checkpoints_button_exists(self):
        self.assertTrue(hasattr(self.page, "refresh_checkpoints_button"))
        self.assertEqual(self.page.refresh_checkpoints_button.text(), "Rafraîchir les checkpoints")

    @patch("src.ui.pages.settings_page.ComfyUIEngine")
    def test_refresh_does_not_change_other_application_fields(self, mock_engine_class):
        mock_engine_class.return_value.list_checkpoints.return_value = ["a.safetensors"]

        self.page.python_path_edit.setText("C:/Python/python.exe")
        self.page.comfyui_path_edit.setText("C:/ComfyUI")
        self.page.onetrainer_path_edit.setText("C:/OneTrainer")
        url_before = self.page.comfyui_url_edit.text()

        self.page.refresh_checkpoints_button.click()

        self.assertEqual(self.page.python_path_edit.text(), "C:/Python/python.exe")
        self.assertEqual(self.page.comfyui_path_edit.text(), "C:/ComfyUI")
        self.assertEqual(self.page.onetrainer_path_edit.text(), "C:/OneTrainer")
        self.assertEqual(self.page.comfyui_url_edit.text(), url_before)

    def test_no_discovery_attempted_automatically_on_load(self):
        # Section 7 of MISSION_025.md: discovery only happens on an
        # explicit "Rafraîchir" click, never at SettingsPage construction.
        with patch("src.ui.pages.settings_page.ComfyUIEngine") as mock_engine_class:
            SettingsPage(self.settings_manager, self.application_settings_manager)
            mock_engine_class.assert_not_called()


class SettingsPageLoraDiscoveryTest(unittest.TestCase):
    """
    Mission 059: same discovery/selection pattern as
    SettingsPageCheckpointDiscoveryTest above, reproduced for the LoRA
    field — the editable QComboBox, the "Rafraîchir les LoRA" button
    querying a mocked ComfyUIEngine.list_loras(), and the manual-entry
    fallback that must always remain available. A configured value that
    becomes absent from a fresh discovery is never silently replaced —
    the whole point of this discovery mechanism (see
    test_refresh_preserves_currently_displayed_value_even_if_absent_
    from_discovered_list below).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        self.settings_manager = SettingsManager(workspace_manager)
        self.application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "AppSettings", event_bus=event_bus
        )
        self.page = SettingsPage(self.settings_manager, self.application_settings_manager)

    def _combo_items(self):
        combo = self.page.comfyui_lora_name_edit
        return [combo.itemText(index) for index in range(combo.count())]

    def test_lora_field_is_an_editable_combo_box(self):
        combo = self.page.comfyui_lora_name_edit
        self.assertIsInstance(combo, QComboBox)
        self.assertTrue(combo.isEditable())

    def test_persisted_lora_value_restored_on_load(self):
        # ApplicationSettings' own literal default (Mission 059) — ""
        # honestly means "no LoRA configured", unlike the checkpoint's
        # own non-empty default.
        self.assertEqual(self.page.comfyui_lora_name_edit.currentText(), "")
        self.assertEqual(self.page.comfyui_lora_strength_edit.value(), 1.0)

    @patch("src.ui.pages.settings_page.ComfyUIEngine")
    def test_refresh_populates_combo_box_with_discovered_loras(self, mock_engine_class):
        mock_engine_class.return_value.list_loras.return_value = [
            "style_a.safetensors",
            "style_b.safetensors",
        ]

        self.page.refresh_loras_button.click()

        self.assertEqual(self._combo_items(), ["style_a.safetensors", "style_b.safetensors"])

    @patch("src.ui.pages.settings_page.ComfyUIEngine")
    def test_refresh_preserves_currently_displayed_value_even_if_absent_from_discovered_list(
        self, mock_engine_class
    ):
        mock_engine_class.return_value.list_loras.return_value = ["other.safetensors"]

        # A value the user already configured/saved, no longer present
        # on the server (deleted/moved/renamed) — must never be silently
        # replaced by whatever the fresh discovery returns.
        self.page.comfyui_lora_name_edit.setCurrentText("my_missing_lora.safetensors")

        self.page.refresh_loras_button.click()

        self.assertEqual(self._combo_items(), ["other.safetensors"])
        self.assertEqual(
            self.page.comfyui_lora_name_edit.currentText(), "my_missing_lora.safetensors"
        )

    @patch("src.ui.pages.settings_page.ComfyUIEngine")
    def test_selecting_a_discovered_lora_then_save_persists_it(self, mock_engine_class):
        mock_engine_class.return_value.list_loras.return_value = ["a.safetensors", "b.safetensors"]
        self.page.refresh_loras_button.click()

        self.page.comfyui_lora_name_edit.setCurrentIndex(1)
        self.page.comfyui_lora_strength_edit.setValue(0.5)
        self.page.save_application_settings()

        self.assertEqual(
            self.application_settings_manager.settings.comfyui_lora_name, "b.safetensors"
        )
        self.assertEqual(self.application_settings_manager.settings.comfyui_lora_strength, 0.5)

    def test_manual_entry_then_save_persists_it(self):
        self.page.comfyui_lora_name_edit.setCurrentText("manually_typed.safetensors")

        self.page.save_application_settings()

        self.assertEqual(
            self.application_settings_manager.settings.comfyui_lora_name,
            "manually_typed.safetensors",
        )

    def test_reload_after_save_restores_persisted_value(self):
        self.page.comfyui_lora_name_edit.setCurrentText("restored.safetensors")
        self.page.comfyui_lora_strength_edit.setValue(0.8)
        self.page.save_application_settings()

        self.page.update_application_settings()

        self.assertEqual(
            self.page.comfyui_lora_name_edit.currentText(), "restored.safetensors"
        )
        self.assertEqual(self.page.comfyui_lora_strength_edit.value(), 0.8)

    @patch("src.ui.pages.settings_page.ComfyUIEngine")
    def test_refresh_uses_the_currently_typed_url_not_necessarily_saved(self, mock_engine_class):
        mock_engine_class.return_value.list_loras.return_value = []

        self.page.comfyui_url_edit.setText("http://192.168.1.99:8188")

        self.page.refresh_loras_button.click()

        mock_engine_class.assert_called_once_with(
            base_url="http://192.168.1.99:8188", timeout=LORA_DISCOVERY_TIMEOUT
        )

    @patch("src.ui.pages.settings_page.ComfyUIEngine")
    def test_refresh_uses_a_short_dedicated_timeout_not_the_generation_timeout(self, mock_engine_class):
        mock_engine_class.return_value.list_loras.return_value = []

        self.page.refresh_loras_button.click()

        used_timeout = mock_engine_class.call_args.kwargs["timeout"]
        self.assertEqual(used_timeout, LORA_DISCOVERY_TIMEOUT)
        self.assertLess(used_timeout, 120.0)

    @patch("src.ui.pages.settings_page.ComfyUIEngine")
    def test_refresh_with_unreachable_server_does_not_raise_and_settings_stays_usable(
        self, mock_engine_class
    ):
        mock_engine_class.return_value.list_loras.side_effect = ComfyUIEngineError(
            "ComfyUI server unreachable"
        )

        # Must not raise/crash SettingsPage.
        self.page.refresh_loras_button.click()

        self.assertIn("impossible", self.page.lora_discovery_status_label.text().lower())

        # Manual entry and save remain fully available afterward — the
        # previously configured value is never silently swapped for
        # anything else.
        self.page.comfyui_lora_name_edit.setCurrentText("fallback.safetensors")
        self.page.save_application_settings()
        self.assertEqual(
            self.application_settings_manager.settings.comfyui_lora_name, "fallback.safetensors"
        )

    @patch("src.ui.pages.settings_page.ComfyUIEngine")
    def test_refresh_with_zero_loras_reports_status_without_error(self, mock_engine_class):
        mock_engine_class.return_value.list_loras.return_value = []

        self.page.refresh_loras_button.click()

        self.assertEqual(self._combo_items(), [])
        self.assertIn("aucun", self.page.lora_discovery_status_label.text().lower())

    def test_refresh_loras_button_exists(self):
        self.assertTrue(hasattr(self.page, "refresh_loras_button"))
        self.assertEqual(self.page.refresh_loras_button.text(), "Rafraîchir les LoRA")

    @patch("src.ui.pages.settings_page.ComfyUIEngine")
    def test_refresh_does_not_change_other_application_fields(self, mock_engine_class):
        mock_engine_class.return_value.list_loras.return_value = ["a.safetensors"]

        self.page.python_path_edit.setText("C:/Python/python.exe")
        self.page.comfyui_checkpoint_name_edit.setCurrentText("some_checkpoint.safetensors")
        checkpoint_before = self.page.comfyui_checkpoint_name_edit.currentText()

        self.page.refresh_loras_button.click()

        self.assertEqual(self.page.python_path_edit.text(), "C:/Python/python.exe")
        self.assertEqual(
            self.page.comfyui_checkpoint_name_edit.currentText(), checkpoint_before
        )

    def test_no_discovery_attempted_automatically_on_load(self):
        # Same discipline as checkpoint/Ollama discovery: only an
        # explicit "Rafraîchir" click ever constructs an engine.
        with patch("src.ui.pages.settings_page.ComfyUIEngine") as mock_engine_class:
            SettingsPage(self.settings_manager, self.application_settings_manager)
            mock_engine_class.assert_not_called()


class SettingsPageOllamaDiscoveryTest(unittest.TestCase):
    """
    Mission 030: same discovery/selection pattern as
    SettingsPageCheckpointDiscoveryTest above, reproduced for the
    Ollama model field — the editable QComboBox, the "Rafraîchir les
    modèles" button querying a mocked OllamaEngine.list_models(), and
    the manual-entry fallback that must always remain available.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        self.settings_manager = SettingsManager(workspace_manager)
        self.application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "AppSettings", event_bus=event_bus
        )
        self.page = SettingsPage(self.settings_manager, self.application_settings_manager)

    def _combo_items(self):
        combo = self.page.ollama_model_name_edit
        return [combo.itemText(index) for index in range(combo.count())]

    def test_ollama_model_field_is_an_editable_combo_box(self):
        combo = self.page.ollama_model_name_edit
        self.assertIsInstance(combo, QComboBox)
        self.assertTrue(combo.isEditable())

    def test_persisted_ollama_fields_restored_on_load(self):
        # ApplicationSettings' own literal default (Mission 030),
        # displayed without requiring any discovery.
        self.assertEqual(self.page.ollama_url_edit.text(), "http://127.0.0.1:11434")
        self.assertEqual(self.page.ollama_path_edit.text(), "")
        self.assertEqual(self.page.ollama_model_name_edit.currentText(), "")

    @patch("src.ui.pages.settings_page.OllamaEngine")
    def test_refresh_populates_combo_box_with_discovered_models(self, mock_engine_class):
        mock_engine_class.return_value.list_models.return_value = [
            AIModelInfo(name="llama3.2:latest"),
            AIModelInfo(name="mistral:latest"),
        ]

        self.page.refresh_ollama_models_button.click()

        self.assertEqual(self._combo_items(), ["llama3.2:latest", "mistral:latest"])

    @patch("src.ui.pages.settings_page.OllamaEngine")
    def test_refresh_preserves_currently_displayed_value_even_if_absent_from_discovered_list(
        self, mock_engine_class
    ):
        mock_engine_class.return_value.list_models.return_value = [AIModelInfo(name="other:latest")]

        # A value the user already typed/kept, not present on the server.
        self.page.ollama_model_name_edit.setCurrentText("my_custom_model:latest")

        self.page.refresh_ollama_models_button.click()

        self.assertEqual(self._combo_items(), ["other:latest"])
        self.assertEqual(
            self.page.ollama_model_name_edit.currentText(), "my_custom_model:latest"
        )

    @patch("src.ui.pages.settings_page.OllamaEngine")
    def test_selecting_a_discovered_model_then_save_persists_it(self, mock_engine_class):
        mock_engine_class.return_value.list_models.return_value = [
            AIModelInfo(name="a:latest"),
            AIModelInfo(name="b:latest"),
        ]
        self.page.refresh_ollama_models_button.click()

        self.page.ollama_model_name_edit.setCurrentIndex(1)
        self.page.save_application_settings()

        self.assertEqual(
            self.application_settings_manager.settings.ollama_model_name, "b:latest"
        )

    def test_manual_entry_then_save_persists_it(self):
        # No discovery attempted at all — pure free-text fallback, the
        # only option available for a remote/network Ollama instance.
        self.page.ollama_model_name_edit.setCurrentText("manually_typed:latest")

        self.page.save_application_settings()

        self.assertEqual(
            self.application_settings_manager.settings.ollama_model_name,
            "manually_typed:latest",
        )

    def test_reload_after_save_restores_persisted_value(self):
        self.page.ollama_url_edit.setText("http://192.168.1.50:11434")
        self.page.ollama_path_edit.setText("C:/Ollama")
        self.page.ollama_model_name_edit.setCurrentText("restored:latest")
        self.page.save_application_settings()

        self.page.update_application_settings()

        self.assertEqual(self.page.ollama_url_edit.text(), "http://192.168.1.50:11434")
        self.assertEqual(self.page.ollama_path_edit.text(), "C:/Ollama")
        self.assertEqual(self.page.ollama_model_name_edit.currentText(), "restored:latest")

    @patch("src.ui.pages.settings_page.OllamaEngine")
    def test_refresh_uses_the_currently_typed_url_not_necessarily_saved(self, mock_engine_class):
        mock_engine_class.return_value.list_models.return_value = []

        # Testing an address before ever saving it (mirrors Mission 025).
        self.page.ollama_url_edit.setText("http://192.168.1.99:11434")

        self.page.refresh_ollama_models_button.click()

        mock_engine_class.assert_called_once_with(
            base_url="http://192.168.1.99:11434", timeout=OLLAMA_DISCOVERY_TIMEOUT
        )

    @patch("src.ui.pages.settings_page.OllamaEngine")
    def test_refresh_uses_a_short_dedicated_timeout_not_the_generation_timeout(self, mock_engine_class):
        mock_engine_class.return_value.list_models.return_value = []

        self.page.refresh_ollama_models_button.click()

        used_timeout = mock_engine_class.call_args.kwargs["timeout"]
        self.assertEqual(used_timeout, OLLAMA_DISCOVERY_TIMEOUT)
        self.assertLess(used_timeout, 120.0)

    @patch("src.ui.pages.settings_page.OllamaEngine")
    def test_refresh_with_unreachable_server_does_not_raise_and_settings_stays_usable(
        self, mock_engine_class
    ):
        mock_engine_class.return_value.list_models.side_effect = AIBackendError(
            "Ollama server unreachable"
        )

        # Must not raise/crash SettingsPage.
        self.page.refresh_ollama_models_button.click()

        self.assertIn("impossible", self.page.ollama_discovery_status_label.text().lower())

        # Manual entry and save remain fully available afterward.
        self.page.ollama_model_name_edit.setCurrentText("fallback:latest")
        self.page.save_application_settings()
        self.assertEqual(
            self.application_settings_manager.settings.ollama_model_name, "fallback:latest"
        )

    @patch("src.ui.pages.settings_page.OllamaEngine")
    def test_refresh_with_zero_models_reports_status_without_error(self, mock_engine_class):
        mock_engine_class.return_value.list_models.return_value = []

        self.page.refresh_ollama_models_button.click()

        self.assertEqual(self._combo_items(), [])
        self.assertIn("aucun", self.page.ollama_discovery_status_label.text().lower())

    def test_refresh_ollama_models_button_exists(self):
        self.assertTrue(hasattr(self.page, "refresh_ollama_models_button"))
        self.assertEqual(self.page.refresh_ollama_models_button.text(), "Rafraîchir les modèles")

    @patch("src.ui.pages.settings_page.OllamaEngine")
    def test_refresh_does_not_change_other_application_fields(self, mock_engine_class):
        mock_engine_class.return_value.list_models.return_value = [AIModelInfo(name="a:latest")]

        self.page.python_path_edit.setText("C:/Python/python.exe")
        self.page.comfyui_path_edit.setText("C:/ComfyUI")
        self.page.comfyui_url_edit.setText("http://127.0.0.1:8000")
        ollama_url_before = self.page.ollama_url_edit.text()
        ollama_path_before = self.page.ollama_path_edit.text()

        self.page.refresh_ollama_models_button.click()

        self.assertEqual(self.page.python_path_edit.text(), "C:/Python/python.exe")
        self.assertEqual(self.page.comfyui_path_edit.text(), "C:/ComfyUI")
        self.assertEqual(self.page.comfyui_url_edit.text(), "http://127.0.0.1:8000")
        self.assertEqual(self.page.ollama_url_edit.text(), ollama_url_before)
        self.assertEqual(self.page.ollama_path_edit.text(), ollama_path_before)

    def test_no_discovery_attempted_automatically_on_load(self):
        # Same discipline as ComfyUI checkpoint discovery: only an
        # explicit "Rafraîchir" click ever constructs an engine.
        with patch("src.ui.pages.settings_page.OllamaEngine") as mock_engine_class:
            SettingsPage(self.settings_manager, self.application_settings_manager)
            mock_engine_class.assert_not_called()


class SettingsPageSizeHintRegressionTest(unittest.TestCase):
    """
    Mission 059: SettingsPage.sizeHint() must never balloon past a
    normal desktop screen width — QStackedWidget aggregates the max
    sizeHint()/minimumSizeHint() across every page (visible or not),
    so an oversized SettingsPage silently inflates MainWindow's own
    minimumSizeHint() even while Dashboard is the page actually shown
    at launch. Measured regression before the fix: SettingsPage's
    unwrapped application_hint QLabel grew from 974px to 1982px wide
    once M059 appended its LoRA-compatibility sentence, taking
    SettingsPage.sizeHint() from (996, 596) to (2004, 704) and
    MainWindow.minimumSizeHint() from (2225, 769) to a size exceeding
    even a 1920px-wide screen. Fixed by application_hint.setWordWrap(True).
    900px is a generous bound — comfortably above the pre-M059 width
    (996 total page width, ~974 of it the label) and comfortably below
    any common screen width, so this only fails on a real regression,
    not on ordinary UI growth.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        settings_manager = SettingsManager(workspace_manager)
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "AppSettings", event_bus=event_bus
        )
        self.page = SettingsPage(settings_manager, application_settings_manager)

    def test_settings_page_size_hint_width_stays_within_a_normal_screen(self):
        self.assertLess(self.page.sizeHint().width(), 900)
        self.assertLess(self.page.minimumSizeHint().width(), 900)


class SettingsPageSaveErrorTest(unittest.TestCase):
    """
    Mission 055: a real write failure (permissions, disk full) must
    surface as a graceful QMessageBox.critical(...), never as an
    unhandled exception reaching the Qt event loop — mirroring the
    WorkspaceManagerError handling already used four times in
    main_window.py. Both save paths (Workspace Settings via
    SettingsManager -> WorkspaceManager.save(), Application Settings
    via ApplicationSettingsManager.update()) are covered.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.settings_manager = SettingsManager(self.workspace_manager)
        self.application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "AppSettings", event_bus=self.event_bus
        )
        self.page = SettingsPage(self.settings_manager, self.application_settings_manager)

        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_SAVED, WORKSPACE_CLOSED):
            self.event_bus.subscribe(event_name, self.page.update_settings)

        self.workspace_manager.create(Path(self.tmp_dir) / "Project")

    @patch("src.ui.pages.settings_page.QMessageBox")
    @patch.object(ApplicationSettingsStorage, "save", side_effect=ApplicationSettingsStorageError("disk full"))
    def test_application_settings_save_failure_shows_error_and_does_not_raise(
        self, mock_save, mock_message_box
    ):
        self.page.comfyui_path_edit.setText("C:/ComfyUI")

        # Must not raise — the exception is caught inside the method.
        self.page.save_application_settings()

        mock_message_box.critical.assert_called_once_with(
            self.page, "Erreur", "disk full"
        )

    @patch("src.ui.pages.settings_page.QMessageBox")
    @patch.object(ApplicationSettingsStorage, "save", side_effect=ApplicationSettingsStorageError("disk full"))
    def test_application_settings_save_failure_leaves_settings_unchanged(
        self, mock_save, mock_message_box
    ):
        before = self.application_settings_manager.settings.comfyui_path

        self.page.comfyui_path_edit.setText("C:/NewComfyUI")
        self.page.save_application_settings()

        # ApplicationSettingsManager.update() only reassigns self._settings
        # after a successful save() — a failed save leaves it untouched.
        self.assertEqual(self.application_settings_manager.settings.comfyui_path, before)

    def test_application_settings_page_reusable_for_real_save_after_failure(self):
        with patch("src.ui.pages.settings_page.QMessageBox"), patch.object(
            ApplicationSettingsStorage, "save", side_effect=ApplicationSettingsStorageError("disk full")
        ):
            self.page.comfyui_path_edit.setText("C:/Failed")
            self.page.save_application_settings()

        # The mocked failure is gone — a real save now succeeds, proving
        # the button/fields stayed fully usable after the earlier error.
        self.page.comfyui_path_edit.setText("C:/Real")
        self.page.save_application_settings()

        self.assertEqual(self.application_settings_manager.settings.comfyui_path, "C:/Real")

    @patch("src.ui.pages.settings_page.QMessageBox")
    @patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full"))
    def test_workspace_settings_save_failure_shows_error_and_does_not_raise(
        self, mock_save, mock_message_box
    ):
        self.page.theme_edit.setText("dark")

        # Must not raise — WorkspaceManager.save() wraps WorkspaceStorageError
        # into WorkspaceManagerError, caught inside save_settings().
        self.page.save_settings()

        self.assertEqual(mock_message_box.critical.call_count, 1)
        args = mock_message_box.critical.call_args.args
        self.assertEqual(args[0], self.page)
        self.assertEqual(args[1], "Erreur")
        self.assertIn("disk full", args[2])

    def test_workspace_settings_page_reusable_for_real_save_after_failure(self):
        with patch("src.ui.pages.settings_page.QMessageBox"), patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ):
            self.page.theme_edit.setText("dark")
            self.page.save_settings()

        # UI stays enabled/reachable after the error (no incoherent state).
        self.assertTrue(self.page.theme_edit.isEnabled())
        self.assertTrue(self.page.save_button.isEnabled())

        # The mocked failure is gone — a real save now succeeds, proving
        # the button/fields stayed fully usable after the earlier error.
        self.page.theme_edit.setText("light")
        self.page.save_settings()

        self.assertEqual(self.settings_manager.settings.theme, "light")


if __name__ == "__main__":
    unittest.main()
