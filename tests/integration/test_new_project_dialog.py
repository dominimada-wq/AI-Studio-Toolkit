"""
Real-widget coverage for NewProjectDialog (Mission 016): validates
that the dialog only builds and validates a target_path — it never
creates anything on disk — and that "Créer" is enabled/disabled
exactly according to spec (parent chosen, name valid, no collision),
including a collision that appears between the last _revalidate() and
the moment "Créer" is actually clicked.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog

from src.ui.dialogs.new_project_dialog import NewProjectDialog

_app = QApplication.instance() or QApplication([])


class NewProjectDialogTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        self.dialog = NewProjectDialog()
        self.addCleanup(self.dialog.close)

    def _choose_parent(self, folder):
        with patch(
            "src.ui.dialogs.new_project_dialog.QFileDialog.getExistingDirectory",
            return_value=folder,
        ):
            self.dialog.browse_button.click()

    def _entries(self):
        return sorted(Path(self.tmp_dir).iterdir())

    # --- Initial state ---

    def test_initial_state_create_button_disabled_and_no_parent_selected(self):
        self.assertFalse(self.dialog.create_button.isEnabled())
        self.assertEqual(self.dialog.parent_line_edit.text(), "")

    # --- Parent alone ---

    def test_create_button_disabled_with_parent_but_no_name(self):
        self._choose_parent(self.tmp_dir)

        self.assertEqual(self.dialog.parent_line_edit.text(), self.tmp_dir)
        self.assertFalse(self.dialog.create_button.isEnabled())

    # --- Valid combination ---

    def test_create_button_enabled_with_valid_parent_and_valid_name(self):
        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("MyProject")

        self.assertTrue(self.dialog.create_button.isEnabled())
        self.assertEqual(
            self.dialog.preview_label.text(), str(Path(self.tmp_dir) / "MyProject")
        )

    def test_name_with_internal_dot_is_valid(self):
        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("MyProject.v2")

        self.assertTrue(self.dialog.create_button.isEnabled())

    def test_name_with_internal_spaces_is_valid_and_path_preserved_exactly(self):
        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("My Project")

        self.assertTrue(self.dialog.create_button.isEnabled())

        self.dialog._on_accept_clicked()

        self.assertEqual(self.dialog.target_path, Path(self.tmp_dir) / "My Project")

    # --- Name validation ---

    def test_empty_name_is_rejected(self):
        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("")

        self.assertFalse(self.dialog.create_button.isEnabled())

    def test_whitespace_only_name_is_rejected(self):
        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("   ")

        self.assertFalse(self.dialog.create_button.isEnabled())

    def test_dot_name_is_rejected(self):
        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText(".")

        self.assertFalse(self.dialog.create_button.isEnabled())

    def test_dotdot_name_is_rejected(self):
        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("..")

        self.assertFalse(self.dialog.create_button.isEnabled())

    def test_forbidden_windows_characters_are_rejected(self):
        self._choose_parent(self.tmp_dir)

        for character in '<>:"|?*':
            with self.subTest(character=character):
                self.dialog.name_line_edit.setText(f"My{character}Project")
                self.assertFalse(self.dialog.create_button.isEnabled())

    def test_forward_and_back_slash_are_rejected(self):
        self._choose_parent(self.tmp_dir)

        for separator in ("/", "\\"):
            with self.subTest(separator=separator):
                self.dialog.name_line_edit.setText(f"My{separator}Project")
                self.assertFalse(self.dialog.create_button.isEnabled())

    def test_reserved_windows_names_are_rejected(self):
        self._choose_parent(self.tmp_dir)

        reserved_names = ["CON", "PRN", "AUX", "NUL", "con", "Con", "CoN"]
        reserved_names += [f"COM{i}" for i in range(1, 10)]
        reserved_names += [f"LPT{i}" for i in range(1, 10)]

        for reserved in reserved_names:
            with self.subTest(reserved=reserved):
                self.dialog.name_line_edit.setText(reserved)
                self.assertFalse(self.dialog.create_button.isEnabled())

    def test_reserved_windows_name_with_extension_is_rejected(self):
        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("CON.txt")

        self.assertFalse(self.dialog.create_button.isEnabled())

    def test_names_close_to_reserved_but_valid_are_accepted(self):
        self._choose_parent(self.tmp_dir)

        for name in ("CONSOLE", "COM10", "LPT10", "AUXILIARY"):
            with self.subTest(name=name):
                self.dialog.name_line_edit.setText(name)
                self.assertTrue(self.dialog.create_button.isEnabled())

    def test_trailing_space_is_rejected(self):
        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("MyProject ")

        self.assertFalse(self.dialog.create_button.isEnabled())

    def test_trailing_dot_is_rejected(self):
        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("MyProject.")

        self.assertFalse(self.dialog.create_button.isEnabled())

    # --- Parent directory edge cases ---

    def test_browse_cancelled_leaves_no_parent_selected(self):
        with patch(
            "src.ui.dialogs.new_project_dialog.QFileDialog.getExistingDirectory",
            return_value="",
        ):
            self.dialog.browse_button.click()

        self.assertEqual(self.dialog.parent_line_edit.text(), "")
        self.assertFalse(self.dialog.create_button.isEnabled())

    def test_browse_cancelled_after_a_parent_was_already_selected_keeps_it(self):
        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("MyProject")
        self.assertTrue(self.dialog.create_button.isEnabled())

        with patch(
            "src.ui.dialogs.new_project_dialog.QFileDialog.getExistingDirectory",
            return_value="",
        ):
            self.dialog.browse_button.click()

        self.assertEqual(self.dialog.parent_line_edit.text(), self.tmp_dir)
        self.assertTrue(self.dialog.create_button.isEnabled())

    def test_parent_removed_externally_after_selection_disables_create(self):
        removable_parent = tempfile.mkdtemp(dir=self.tmp_dir)
        self._choose_parent(removable_parent)

        shutil.rmtree(removable_parent)

        self.dialog.name_line_edit.setText("MyProject")

        self.assertFalse(self.dialog.create_button.isEnabled())
        self.assertEqual(self.dialog.preview_label.text(), "Choisissez un dossier parent.")

    def test_parent_pointing_to_a_file_disables_create(self):
        file_path = Path(self.tmp_dir) / "not_a_folder.txt"
        file_path.write_text("data")

        # Not reachable via the real Browse button (getExistingDirectory
        # only ever returns directories) — exercised directly as a
        # defensive check of _compute_target_path()'s own guard.
        self.dialog._parent_directory = str(file_path)
        self.dialog.name_line_edit.setText("MyProject")

        self.assertFalse(self.dialog.create_button.isEnabled())
        self.assertEqual(self.dialog.preview_label.text(), "Choisissez un dossier parent.")

    # --- Collision with an existing target ---

    def test_existing_target_folder_blocks_create_button(self):
        (Path(self.tmp_dir) / "AlreadyThere").mkdir()

        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("AlreadyThere")

        self.assertFalse(self.dialog.create_button.isEnabled())
        self.assertIn("existe déjà", self.dialog.preview_label.text())

    def test_existing_target_file_blocks_create_button(self):
        (Path(self.tmp_dir) / "AlreadyThere.txt").write_text("data")

        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("AlreadyThere.txt")

        self.assertFalse(self.dialog.create_button.isEnabled())
        self.assertIn("existe déjà", self.dialog.preview_label.text())

    def test_target_becomes_valid_again_once_name_changed_away_from_collision(self):
        (Path(self.tmp_dir) / "Taken").mkdir()

        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("Taken")
        self.assertFalse(self.dialog.create_button.isEnabled())

        self.dialog.name_line_edit.setText("Free")

        self.assertTrue(self.dialog.create_button.isEnabled())
        self.assertEqual(self.dialog.target_path, None)  # still not set before Accept
        self.assertEqual(
            self.dialog.preview_label.text(), str(Path(self.tmp_dir) / "Free")
        )

    def test_target_becomes_valid_again_after_colliding_folder_removed_and_revalidated(self):
        colliding = Path(self.tmp_dir) / "Taken"
        colliding.mkdir()

        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("Taken")
        self.assertFalse(self.dialog.create_button.isEnabled())

        shutil.rmtree(colliding)

        # No filesystem polling by design (see spec) — the dialog only
        # re-checks on an actual field change. Two real textChanged
        # signals (append then remove a character) simulate the user
        # continuing to interact with the field, ending on the exact
        # same name, which must now be accepted since the collision is
        # gone.
        self.dialog.name_line_edit.setText("Taken2")
        self.dialog.name_line_edit.setText("Taken")

        self.assertTrue(self.dialog.create_button.isEnabled())

    # --- Exact path construction ---

    def test_target_path_matches_parent_joined_with_name_exactly(self):
        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("MyProject")

        self.dialog._on_accept_clicked()

        self.assertEqual(self.dialog.target_path, Path(self.tmp_dir) / "MyProject")

    # --- Cancel ---

    def test_cancel_rejects_dialog_and_exposes_no_target_path(self):
        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("MyProject")

        self.dialog.reject()

        self.assertIsNone(self.dialog.target_path)
        self.assertEqual(self.dialog.result(), QDialog.Rejected)

    def test_closing_via_window_x_behaves_like_cancel(self):
        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("MyProject")

        self.dialog.close()

        self.assertIsNone(self.dialog.target_path)
        self.assertEqual(self.dialog.result(), QDialog.Rejected)
        self.assertFalse((Path(self.tmp_dir) / "MyProject").exists())

    # --- Accept ---

    def test_accept_returns_accepted_and_exposes_correct_target_path(self):
        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("MyProject")

        self.dialog._on_accept_clicked()

        self.assertEqual(self.dialog.result(), QDialog.Accepted)
        self.assertEqual(self.dialog.target_path, Path(self.tmp_dir) / "MyProject")

    def test_accept_never_creates_anything_on_disk(self):
        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("MyProject")

        before = self._entries()
        self.dialog._on_accept_clicked()
        after = self._entries()

        self.assertEqual(before, after)
        self.assertFalse((Path(self.tmp_dir) / "MyProject").exists())

    # --- Collision re-checked exactly at accept time ---

    def test_collision_appearing_after_revalidate_blocks_accept(self):
        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("RaceProject")
        self.assertTrue(self.dialog.create_button.isEnabled())

        # Simulate the target appearing on disk between the last
        # _revalidate() (triggered by textChanged above) and the
        # user's click on "Créer" — accept() must re-check, not trust
        # the stale state.
        (Path(self.tmp_dir) / "RaceProject").mkdir()

        self.dialog._on_accept_clicked()

        self.assertIsNone(self.dialog.target_path)
        self.assertNotEqual(self.dialog.result(), QDialog.Accepted)
        self.assertFalse(self.dialog.create_button.isEnabled())
        self.assertIn("existe déjà", self.dialog.preview_label.text())

    # --- Double-trigger / idempotency ---

    def test_calling_on_accept_clicked_twice_is_idempotent(self):
        self._choose_parent(self.tmp_dir)
        self.dialog.name_line_edit.setText("MyProject")

        self.dialog._on_accept_clicked()
        first_target = self.dialog.target_path

        self.dialog._on_accept_clicked()
        second_target = self.dialog.target_path

        self.assertEqual(first_target, second_target)
        self.assertEqual(self.dialog.result(), QDialog.Accepted)
        self.assertFalse((Path(self.tmp_dir) / "MyProject").exists())


if __name__ == "__main__":
    unittest.main()
