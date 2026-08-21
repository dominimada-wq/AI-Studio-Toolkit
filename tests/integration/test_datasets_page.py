"""
Mission 042: real-widget coverage for DatasetsPage's thumbnail gallery
(images_list) — icon-mode grid, short filename label, full-path
tooltip/Qt.UserRole, fallback icon for a missing/invalid file, and the
enlarged-preview wiring (double-click and "Voir en grand", both opening
the same ImagePreviewDialog), all mirroring the equivalent coverage
already established for ImagesPage in Mission 019/028
(test_images_page.py). ImagePreviewDialog.exec() is patched throughout
— a real modal exec() would block the test process (same lesson as
every other dialog in this project).

Dataset-specific plumbing (unlike ImagesPage's WorkspaceManager alone):
a real Character is required — WorkspaceManager.create() triggers
CharacterManager's own WORKSPACE_CREATED subscription, which
auto-creates and auto-selects a principal Character (Mission 026) —
DatasetManager.create()/add_images() operate on that principal
Character's own Dataset pool. DatasetManager.add_images() itself
publishes no dedicated event; it only calls WorkspaceManager.save()
(WORKSPACE_SAVED) — DatasetsPage.update_datasets() is wired to that
event plus DATASET_SELECTED, exactly like the real MainWindow wiring
in test_dataset_roundtrip.py.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QListWidget

from src.core.event_bus import EventBus
from src.managers.workspace_manager import WorkspaceManager, WORKSPACE_CREATED, WORKSPACE_SAVED
from src.managers.character_manager import CharacterManager
from src.managers.dataset_manager import DatasetManager, DATASET_SELECTED
from src.ui.pages.datasets_page import DatasetsPage

_app = QApplication.instance() or QApplication([])


def _make_png(path: str, width: int = 4, height: int = 4) -> None:
    pixmap = QPixmap(width, height)
    pixmap.fill()
    assert pixmap.save(path, "PNG")


class DatasetsPageGalleryTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "DatasetsGalleryProject"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.page = DatasetsPage(self.dataset_manager, self.workspace_manager)

        for event_name in (WORKSPACE_CREATED, WORKSPACE_SAVED, DATASET_SELECTED):
            self.event_bus.subscribe(event_name, self.page.update_datasets)

        # WORKSPACE_CREATED auto-creates and auto-selects a principal
        # Character (Mission 026) — DatasetManager.create() depends on it.
        self.workspace_manager.create(self.folder)

        self.dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(self.dataset.dataset_id)

        # self.image_path is the external source handed to add_images();
        # self.internal_image_path is the internal copy the app actually
        # renders afterward (Mission 028) — the two are deliberately
        # different paths on disk.
        self.image_path = str(Path(self.tmp_dir) / "existing.png")
        _make_png(self.image_path)
        self.dataset_manager.add_images([self.image_path])
        self.internal_image_path = self.dataset_manager.active_dataset.images[0].file_path

    # --- Gallery configuration ---

    def test_images_list_uses_icon_mode(self):
        self.assertEqual(self.page.images_list.viewMode(), QListWidget.IconMode)

    # --- Valid image ---

    def test_valid_image_item_has_icon_short_label_tooltip_and_user_role(self):
        item = self.page.images_list.item(0)

        self.assertFalse(item.icon().isNull())
        self.assertEqual(item.text(), "existing.png")
        self.assertEqual(item.toolTip(), self.internal_image_path)
        self.assertEqual(item.data(Qt.UserRole), self.internal_image_path)

    # --- Missing file (present at import time, gone afterward) ---

    def test_missing_file_item_still_shown_with_fallback_icon_and_correct_metadata(self):
        Path(self.internal_image_path).unlink()

        # Deleting the file on disk changes nothing in Domain/persistence
        # — a real refresh (e.g. reopening the page) is what re-reads it
        # and discovers the file is now unreadable.
        self.page.update_datasets()

        item = self.page.images_list.item(0)

        self.assertFalse(item.icon().isNull())
        self.assertEqual(item.text(), "existing.png")
        self.assertEqual(item.toolTip(), self.internal_image_path)
        self.assertEqual(item.data(Qt.UserRole), self.internal_image_path)

    # --- Invalid / non-decodable file ---

    def test_invalid_non_image_file_item_still_created_with_fallback_icon(self):
        invalid_path = str(Path(self.tmp_dir) / "invalid.png")
        Path(invalid_path).write_bytes(b"this is definitely not a png")

        self.dataset_manager.add_images([invalid_path])
        internal_invalid_path = self.dataset_manager.active_dataset.images[-1].file_path

        item = self.page.images_list.item(self.page.images_list.count() - 1)

        self.assertIsNotNone(item)
        self.assertFalse(item.icon().isNull())
        self.assertEqual(item.data(Qt.UserRole), internal_invalid_path)

    # --- Multiple images ---

    def test_multiple_images_each_item_has_its_own_user_role(self):
        second_path = str(Path(self.tmp_dir) / "second.png")
        third_path = str(Path(self.tmp_dir) / "third.png")
        _make_png(second_path)
        _make_png(third_path)

        self.dataset_manager.add_images([second_path, third_path])

        internal_paths = {
            image.file_path for image in self.dataset_manager.active_dataset.images
        }
        roles = {
            self.page.images_list.item(i).data(Qt.UserRole)
            for i in range(self.page.images_list.count())
        }

        self.assertEqual(roles, internal_paths)
        self.assertEqual(len(roles), 3)

    # --- Selection -> "Voir en grand" state ---

    def test_enlarge_button_disabled_without_selection(self):
        self.assertIsNone(self.page.images_list.currentItem())
        self.assertFalse(self.page.enlarge_button.isEnabled())

    def test_enlarge_button_enabled_once_an_item_is_selected(self):
        self.page.images_list.setCurrentRow(0)

        self.assertTrue(self.page.enlarge_button.isEnabled())

    # --- Button / double-click both open the same preview ---

    @patch("src.ui.pages.datasets_page.ImagePreviewDialog")
    def test_enlarge_button_opens_the_selected_file_path(self, mock_dialog_cls):
        self.page.images_list.setCurrentRow(0)

        self.page.enlarge_button.click()

        mock_dialog_cls.assert_called_once_with(self.internal_image_path, parent=self.page)
        mock_dialog_cls.return_value.exec.assert_called_once()

    @patch("src.ui.pages.datasets_page.ImagePreviewDialog")
    def test_double_click_opens_the_same_file_path(self, mock_dialog_cls):
        item = self.page.images_list.item(0)

        self.page._on_image_item_double_clicked(item)

        mock_dialog_cls.assert_called_once_with(self.internal_image_path, parent=self.page)
        mock_dialog_cls.return_value.exec.assert_called_once()

    @patch("src.ui.pages.datasets_page.ImagePreviewDialog")
    def test_enlarge_button_with_no_selection_is_a_no_op(self, mock_dialog_cls):
        self.page.enlarge_button.click()

        mock_dialog_cls.assert_not_called()

    # --- Refresh / dataset switch resets selection ---

    def test_switching_active_dataset_clears_previous_selection_and_disables_button(self):
        self.page.images_list.setCurrentRow(0)
        self.assertTrue(self.page.enlarge_button.isEnabled())

        other_dataset = self.dataset_manager.create("Other")
        self.dataset_manager.select(other_dataset.dataset_id)

        self.assertIsNone(self.page.images_list.currentItem())
        self.assertFalse(self.page.enlarge_button.isEnabled())
        self.assertEqual(self.page.images_list.count(), 0)

    def test_reimporting_into_the_same_dataset_clears_previous_selection(self):
        self.page.images_list.setCurrentRow(0)
        self.assertTrue(self.page.enlarge_button.isEnabled())

        second_path = str(Path(self.tmp_dir) / "second_refresh.png")
        _make_png(second_path)
        self.dataset_manager.add_images([second_path])

        self.assertIsNone(self.page.images_list.currentItem())
        self.assertFalse(self.page.enlarge_button.isEnabled())

    # --- Mission 044: "Ajouter depuis Images" ---

    def _add_to_workspace_gallery(self, name="gallery.png"):
        source = str(Path(self.tmp_dir) / name)
        _make_png(source)
        self.workspace_manager.add_images([source])
        return self.workspace_manager.current_workspace.images[-1].file_path

    @patch("src.ui.pages.datasets_page.QMessageBox")
    def test_add_from_gallery_without_active_dataset_shows_warning_and_no_dialog(self, mock_box):
        # Fresh wiring with no Dataset ever created/selected — same
        # "no active dataset" state already exercised by
        # test_enlarge_button_disabled_without_selection-style tests
        # elsewhere in this file, here for a Manager with zero Datasets
        # at all rather than an unselected one.
        other_workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        other_character_manager = CharacterManager(other_workspace_manager, event_bus=self.event_bus)
        other_dataset_manager = DatasetManager(
            other_character_manager, other_workspace_manager, event_bus=self.event_bus
        )
        other_folder = Path(self.tmp_dir) / "OtherProject"
        other_workspace_manager.create(other_folder)
        other_page = DatasetsPage(other_dataset_manager, other_workspace_manager)
        self.addCleanup(other_page.close)

        with patch("src.ui.pages.datasets_page.SelectImagesDialog") as mock_dialog_cls:
            other_page.add_images_from_gallery()

        mock_box.warning.assert_called_once()
        mock_dialog_cls.assert_not_called()

    @patch("src.ui.pages.datasets_page.QMessageBox")
    def test_add_from_gallery_with_empty_workspace_gallery_shows_info_and_no_dialog(self, mock_box):
        with patch("src.ui.pages.datasets_page.SelectImagesDialog") as mock_dialog_cls:
            self.page.add_images_from_gallery()

        mock_box.information.assert_called_once()
        mock_dialog_cls.assert_not_called()

    def test_add_from_gallery_dialog_is_populated_with_workspace_images(self):
        internal_gallery_path = self._add_to_workspace_gallery()

        with patch("src.ui.pages.datasets_page.SelectImagesDialog") as mock_dialog_cls:
            mock_dialog_cls.return_value.exec.return_value = QDialog.Rejected
            self.page.add_images_from_gallery()

            mock_dialog_cls.assert_called_once_with([internal_gallery_path], parent=self.page)

    def test_add_from_gallery_cancelled_dialog_adds_nothing(self):
        self._add_to_workspace_gallery()
        count_before = self.page.images_list.count()

        with patch("src.ui.pages.datasets_page.SelectImagesDialog") as mock_dialog_cls:
            mock_dialog_cls.return_value.exec.return_value = QDialog.Rejected
            self.page.add_images_from_gallery()

        self.assertEqual(self.page.images_list.count(), count_before)

    @patch("src.ui.pages.datasets_page.QMessageBox")
    def test_add_from_gallery_adds_a_single_selected_image_without_new_file_on_disk(self, _mock_box):
        internal_gallery_path = self._add_to_workspace_gallery()
        datasets_dir = Path(self.tmp_dir) / "DatasetsGalleryProject" / "datasets" / self.dataset.dataset_id
        files_before = set(datasets_dir.iterdir()) if datasets_dir.exists() else set()

        with patch("src.ui.pages.datasets_page.SelectImagesDialog") as mock_dialog_cls:
            mock_dialog_cls.return_value.exec.return_value = QDialog.Accepted
            mock_dialog_cls.return_value.selected_paths.return_value = [internal_gallery_path]
            self.page.add_images_from_gallery()

        internal_paths = {image.file_path for image in self.dataset_manager.active_dataset.images}
        self.assertIn(internal_gallery_path, internal_paths)

        # No new physical file was written under the dataset's own
        # folder — the gallery source is reused as-is (WorkspaceStorage.
        # copy_into_workspace(), Mission 028), never copied a second time.
        files_after = set(datasets_dir.iterdir()) if datasets_dir.exists() else set()
        self.assertEqual(files_after, files_before)

    @patch("src.ui.pages.datasets_page.QMessageBox")
    def test_add_from_gallery_adds_multiple_selected_images_in_one_operation(self, _mock_box):
        path_a = self._add_to_workspace_gallery("gallery_a.png")
        path_b = self._add_to_workspace_gallery("gallery_b.png")

        with patch("src.ui.pages.datasets_page.SelectImagesDialog") as mock_dialog_cls:
            mock_dialog_cls.return_value.exec.return_value = QDialog.Accepted
            mock_dialog_cls.return_value.selected_paths.return_value = [path_a, path_b]
            self.page.add_images_from_gallery()

        internal_paths = {image.file_path for image in self.dataset_manager.active_dataset.images}
        self.assertIn(path_a, internal_paths)
        self.assertIn(path_b, internal_paths)

    @patch("src.ui.pages.datasets_page.QMessageBox")
    def test_add_from_gallery_ignores_an_image_already_in_the_active_dataset(self, _mock_box):
        # self.internal_image_path (from setUp) is already in the
        # active dataset — re-selecting it via the gallery dialog must
        # be silently skipped, never duplicated.
        with patch("src.ui.pages.datasets_page.SelectImagesDialog") as mock_dialog_cls:
            mock_dialog_cls.return_value.exec.return_value = QDialog.Accepted
            mock_dialog_cls.return_value.selected_paths.return_value = [self.internal_image_path]
            self.page.add_images_from_gallery()

        internal_paths = [image.file_path for image in self.dataset_manager.active_dataset.images]
        self.assertEqual(internal_paths.count(self.internal_image_path), 1)

    @patch("src.ui.pages.datasets_page.QMessageBox")
    def test_add_from_gallery_refreshes_images_list_via_existing_workspace_saved_wiring(self, _mock_box):
        internal_gallery_path = self._add_to_workspace_gallery()
        count_before = self.page.images_list.count()

        with patch("src.ui.pages.datasets_page.SelectImagesDialog") as mock_dialog_cls:
            mock_dialog_cls.return_value.exec.return_value = QDialog.Accepted
            mock_dialog_cls.return_value.selected_paths.return_value = [internal_gallery_path]
            self.page.add_images_from_gallery()

        # No manual update_datasets() call here: the refresh must come
        # solely from the pre-existing WORKSPACE_SAVED subscription.
        self.assertEqual(self.page.images_list.count(), count_before + 1)
        internal_paths = {
            self.page.images_list.item(i).data(Qt.UserRole)
            for i in range(self.page.images_list.count())
        }
        self.assertIn(internal_gallery_path, internal_paths)

    # --- Mission 045: "Retirer du dataset" ---

    def test_images_list_uses_extended_selection(self):
        self.assertEqual(self.page.images_list.selectionMode(), QListWidget.ExtendedSelection)

    def test_remove_button_disabled_without_selection(self):
        self.assertFalse(self.page.remove_from_dataset_button.isEnabled())

    def test_remove_button_enabled_with_single_selection(self):
        self.page.images_list.item(0).setSelected(True)

        self.assertTrue(self.page.remove_from_dataset_button.isEnabled())

    def test_remove_button_enabled_with_multiple_selection(self):
        second_path = str(Path(self.tmp_dir) / "second.png")
        _make_png(second_path)
        self.dataset_manager.add_images([second_path])

        self.page.images_list.item(0).setSelected(True)
        self.page.images_list.item(1).setSelected(True)

        self.assertTrue(self.page.remove_from_dataset_button.isEnabled())

    def test_remove_selected_image_removes_it_from_the_active_dataset_only(self):
        self.page.images_list.item(0).setSelected(True)

        self.page.remove_selected_images_from_dataset()

        self.assertEqual(self.page.images_list.count(), 0)
        self.assertEqual(self.dataset_manager.active_dataset.images, [])

        # The physical file itself is never touched by this mission.
        self.assertTrue(Path(self.internal_image_path).exists())

    def test_remove_multiple_selected_images_in_one_operation(self):
        second_path = str(Path(self.tmp_dir) / "second.png")
        third_path = str(Path(self.tmp_dir) / "third.png")
        _make_png(second_path)
        _make_png(third_path)
        self.dataset_manager.add_images([second_path, third_path])
        self.assertEqual(self.page.images_list.count(), 3)

        self.page.images_list.item(0).setSelected(True)
        self.page.images_list.item(1).setSelected(True)

        self.page.remove_selected_images_from_dataset()

        self.assertEqual(self.page.images_list.count(), 1)

    def test_remove_with_no_selection_is_a_no_op(self):
        self.page.remove_selected_images_from_dataset()

        self.assertEqual(self.page.images_list.count(), 1)
        self.assertEqual(len(self.dataset_manager.active_dataset.images), 1)

    def test_remove_last_image_leaves_empty_gallery_and_disables_buttons(self):
        self.page.images_list.item(0).setSelected(True)

        self.page.remove_selected_images_from_dataset()

        self.assertEqual(self.page.images_list.count(), 0)
        self.assertFalse(self.page.enlarge_button.isEnabled())
        self.assertFalse(self.page.remove_from_dataset_button.isEnabled())

    def test_remove_refreshes_images_list_via_existing_workspace_saved_wiring(self):
        self.page.images_list.item(0).setSelected(True)

        # No manual update_datasets() call here: the refresh must come
        # solely from the pre-existing WORKSPACE_SAVED subscription,
        # exactly like add_images_from_gallery() above.
        self.page.remove_selected_images_from_dataset()

        self.assertEqual(self.page.images_list.count(), 0)

    def test_enlarge_button_still_works_with_a_multiple_selection(self):
        second_path = str(Path(self.tmp_dir) / "second.png")
        _make_png(second_path)
        self.dataset_manager.add_images([second_path])
        internal_second_path = self.dataset_manager.active_dataset.images[-1].file_path

        self.page.images_list.item(0).setSelected(True)
        self.page.images_list.setCurrentRow(1)
        self.page.images_list.item(1).setSelected(True)

        # Qt's own notion of "current" (last row explicitly focused via
        # setCurrentRow) is what the preview acts on, deterministic and
        # unchanged regardless of how many items are also selected.
        with patch("src.ui.pages.datasets_page.ImagePreviewDialog") as mock_dialog_cls:
            self.page.enlarge_button.click()

        mock_dialog_cls.assert_called_once_with(internal_second_path, parent=self.page)


if __name__ == "__main__":
    unittest.main()
