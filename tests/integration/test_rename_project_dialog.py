"""
Real-widget coverage for RenameProjectDialog (Mission 027). Only the
dialog's own wiring is tested here — pre-fill from the current folder
name, live validation, collision/identical-name handling, exposing
new_name after acceptance. validate_project_name()'s own rules are
already exhaustively covered by test_new_project_dialog.py and are not
duplicated here, since RenameProjectDialog reuses that exact function
rather than reimplementing it.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication, QDialog

from src.ui.dialogs.rename_project_dialog import RenameProjectDialog

_app = QApplication.instance() or QApplication([])


class RenameProjectDialogTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.current_root = Path(self.tmp_dir) / "CurrentName"
        self.current_root.mkdir()

        self.dialog = RenameProjectDialog(self.current_root)
        self.addCleanup(self.dialog.close)

    # --- Initial state ---

    def test_initial_state_prefilled_with_current_folder_name(self):
        self.assertEqual(self.dialog.name_line_edit.text(), "CurrentName")

    def test_initial_state_rename_button_disabled_on_unchanged_name(self):
        self.assertFalse(self.dialog.rename_button.isEnabled())
        self.assertIn("actuel", self.dialog.preview_label.text())

    # --- Valid new name ---

    def test_rename_button_enabled_with_a_new_valid_name(self):
        self.dialog.name_line_edit.setText("NewName")

        self.assertTrue(self.dialog.rename_button.isEnabled())
        self.assertEqual(
            self.dialog.preview_label.text(),
            str(self.current_root.parent / "NewName"),
        )

    # --- Name validation reused, spot-checked (not duplicated) ---

    def test_empty_name_is_rejected(self):
        self.dialog.name_line_edit.setText("")

        self.assertFalse(self.dialog.rename_button.isEnabled())

    def test_forbidden_windows_character_is_rejected(self):
        self.dialog.name_line_edit.setText("New:Name")

        self.assertFalse(self.dialog.rename_button.isEnabled())

    # --- Identical name ---

    def test_identical_name_disables_rename_button(self):
        self.dialog.name_line_edit.setText("NewName")
        self.assertTrue(self.dialog.rename_button.isEnabled())

        self.dialog.name_line_edit.setText("CurrentName")

        self.assertFalse(self.dialog.rename_button.isEnabled())

    # --- Collision with an existing target ---

    def test_existing_target_folder_blocks_rename_button(self):
        (self.current_root.parent / "AlreadyThere").mkdir()

        self.dialog.name_line_edit.setText("AlreadyThere")

        self.assertFalse(self.dialog.rename_button.isEnabled())
        self.assertIn("existe déjà", self.dialog.preview_label.text())

    def test_collision_appearing_after_revalidate_blocks_accept(self):
        self.dialog.name_line_edit.setText("RaceProject")
        self.assertTrue(self.dialog.rename_button.isEnabled())

        (self.current_root.parent / "RaceProject").mkdir()

        self.dialog._on_accept_clicked()

        self.assertIsNone(self.dialog.new_name)
        self.assertNotEqual(self.dialog.result(), QDialog.Accepted)
        self.assertFalse(self.dialog.rename_button.isEnabled())

    # --- Accept / cancel ---

    def test_accept_exposes_new_name_and_never_touches_the_filesystem(self):
        self.dialog.name_line_edit.setText("NewName")

        self.dialog._on_accept_clicked()

        self.assertEqual(self.dialog.result(), QDialog.Accepted)
        self.assertEqual(self.dialog.new_name, "NewName")
        self.assertTrue(self.current_root.exists())
        self.assertFalse((self.current_root.parent / "NewName").exists())

    def test_cancel_exposes_no_new_name(self):
        self.dialog.name_line_edit.setText("NewName")

        self.dialog.reject()

        self.assertIsNone(self.dialog.new_name)
        self.assertEqual(self.dialog.result(), QDialog.Rejected)


if __name__ == "__main__":
    unittest.main()
