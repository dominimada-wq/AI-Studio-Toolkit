"""
Mission 144: src.core.main.main() is the single interception point for
a present-but-corrupt ApplicationSettings/LoRA Library file —
MainWindow itself is never modified and raises naturally through its
own unmodified construction. QApplication and MainWindow are both
patched here rather than constructed for real: this test suite already
shares one real QApplication instance (see other test files' `_app =
QApplication.instance() or QApplication([])`), and a second real
QApplication([]) call from within main() would raise. QMessageBox is
mocked so no real modal dialog blocks the test run — the underlying
"a real, unparented QMessageBox.critical() works before app.exec()"
claim is verified separately, once, in
tests/integration/test_qt_dialog_safety_net.py's existing coverage of
a real unparented QMessageBox, and was additionally confirmed by hand
against real PySide6 during this mission's design phase.
"""

import unittest
from unittest.mock import MagicMock, patch

import src.core.main as main_module
from src.infrastructure.storage.application_settings_storage import (
    ApplicationSettingsStorageError,
)
from src.infrastructure.storage.lora_library_storage import LoRALibraryStorageError


class MainStartupStorageErrorTest(unittest.TestCase):

    def _run_with_main_window_failure(self, exc):
        with patch.object(main_module, "QApplication") as mock_qapplication_cls, \
                patch.object(main_module, "MainWindow", side_effect=exc), \
                patch.object(main_module, "QMessageBox") as mock_message_box:
            mock_app_instance = MagicMock()
            mock_qapplication_cls.return_value = mock_app_instance

            main_module.main()

        return mock_app_instance, mock_message_box

    def test_application_settings_storage_error_shows_one_fatal_message_and_never_starts(self):
        exc = ApplicationSettingsStorageError(
            "J:/Fake/application_settings.json is not valid JSON"
        )

        app_instance, mock_message_box = self._run_with_main_window_failure(exc)

        mock_message_box.critical.assert_called_once()
        args, kwargs = mock_message_box.critical.call_args
        parent = args[0]
        message_text = args[2] if len(args) > 2 else kwargs.get("text", "")
        self.assertIsNone(parent)
        self.assertIn("Application Settings", message_text)
        self.assertIn(str(exc), message_text)
        app_instance.exec.assert_not_called()

    def test_lora_library_storage_error_shows_one_fatal_message_and_never_starts(self):
        exc = LoRALibraryStorageError("J:/Fake/lora_library.json is not valid JSON")

        app_instance, mock_message_box = self._run_with_main_window_failure(exc)

        mock_message_box.critical.assert_called_once()
        args, kwargs = mock_message_box.critical.call_args
        parent = args[0]
        message_text = args[2] if len(args) > 2 else kwargs.get("text", "")
        self.assertIsNone(parent)
        self.assertIn("LoRA Library", message_text)
        self.assertIn(str(exc), message_text)
        app_instance.exec.assert_not_called()

    def test_the_two_failure_messages_are_distinguishable_from_each_other(self):
        settings_exc = ApplicationSettingsStorageError("settings corrupt")
        _, settings_box = self._run_with_main_window_failure(settings_exc)
        settings_text = settings_box.critical.call_args[0][2]

        library_exc = LoRALibraryStorageError("library corrupt")
        _, library_box = self._run_with_main_window_failure(library_exc)
        library_text = library_box.critical.call_args[0][2]

        self.assertNotEqual(settings_text, library_text)
        self.assertNotIn("LoRA Library", settings_text)
        self.assertNotIn("Application Settings", library_text)

    def test_successful_startup_shows_no_fatal_message_and_starts_normally(self):
        with patch.object(main_module, "QApplication") as mock_qapplication_cls, \
                patch.object(main_module, "MainWindow") as mock_main_window_cls, \
                patch.object(main_module, "QMessageBox") as mock_message_box:
            mock_app_instance = MagicMock()
            mock_qapplication_cls.return_value = mock_app_instance
            mock_window_instance = MagicMock()
            mock_main_window_cls.return_value = mock_window_instance

            main_module.main()

        mock_message_box.critical.assert_not_called()
        mock_window_instance.show.assert_called_once()
        mock_app_instance.exec.assert_called_once()


if __name__ == "__main__":
    unittest.main()
