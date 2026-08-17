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
from src.engines.comfyui_engine import ComfyUIEngineError
from src.managers.application_settings_manager import ApplicationSettingsManager
from src.managers.settings_manager import SettingsManager
from src.managers.workspace_manager import WorkspaceManager
from src.ui.pages.settings_page import CHECKPOINT_DISCOVERY_TIMEOUT, SettingsPage

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


if __name__ == "__main__":
    unittest.main()
