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

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QListWidget, QMessageBox

from src.core.event_bus import EventBus
from src.domain.image import Image
from src.infrastructure.storage.workspace_storage import WorkspaceStorage, WorkspaceStorageError
from src.managers.workspace_manager import (
    WorkspaceManager,
    WorkspaceManagerError,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_SAVED,
    WORKSPACE_CLOSED,
    WORKSPACE_RENAMED,
)
from src.managers.character_manager import (
    CharacterManager,
    CHARACTER_CREATED,
    CHARACTER_SELECTED,
    CHARACTER_DELETED,
)
from src.managers.dataset_manager import (
    DatasetManager,
    DATASET_CREATED,
    DATASET_SELECTED,
    DATASET_DELETED,
)
from src.managers.workspace_lifecycle import create_workspace_with_default_character
from src.ui.pages.datasets_page import DatasetsPage
from tests.integration._qt_dialog_safety_net import start_dialog_guard, stop_dialog_guard

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
        create_workspace_with_default_character(self.workspace_manager, self.character_manager, self.folder)

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

    def test_reimporting_into_the_same_dataset_preserves_previous_selection(self):
        # Mission 082: a same-Dataset refresh (here, importing another
        # image into the SAME active Dataset) must preserve a selection
        # whose underlying item still exists — this used to be silently
        # wiped by every rebuild, even one unrelated to the selected
        # item itself. Superseded the previous (opposite) assertion this
        # test made pre-Mission-082.
        self.page.images_list.setCurrentRow(0)
        self.assertTrue(self.page.enlarge_button.isEnabled())

        second_path = str(Path(self.tmp_dir) / "second_refresh.png")
        _make_png(second_path)
        self.dataset_manager.add_images([second_path])

        self.assertIsNotNone(self.page.images_list.currentItem())
        self.assertEqual(self.page.images_list.currentItem().data(Qt.UserRole), self.internal_image_path)
        self.assertTrue(self.page.enlarge_button.isEnabled())
        # The newly added image must never be selected artificially.
        self.assertEqual(len(self.page.images_list.selectedItems()), 1)

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


class DatasetsPageGallerySortTest(unittest.TestCase):
    """
    Mission 048: images_list is now sorted by Path(file_path).name,
    case-insensitively, always on — purely a Presentation-layer display
    order, Dataset.images itself is never reordered. Mirrors
    ImagesPageGallerySortTest (test_images_page.py) exactly.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "DatasetsGallerySortProject"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.page = DatasetsPage(self.dataset_manager, self.workspace_manager)

        for event_name in (WORKSPACE_CREATED, WORKSPACE_SAVED, DATASET_SELECTED):
            self.event_bus.subscribe(event_name, self.page.update_datasets)

        create_workspace_with_default_character(self.workspace_manager, self.character_manager, self.folder)
        self.dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(self.dataset.dataset_id)

    def _add(self, name: str, content: bytes = b"fake-png-bytes") -> str:
        path = str(Path(self.tmp_dir) / name)
        Path(path).write_bytes(content)
        self.dataset_manager.add_images([path])
        return self.dataset_manager.active_dataset.images[-1].file_path

    def test_gallery_sorted_alphabetically_by_filename(self):
        self._add("zebra.png")
        self._add("apple.png")
        self._add("mango.png")

        texts = [self.page.images_list.item(i).text() for i in range(self.page.images_list.count())]

        self.assertEqual(texts, ["apple.png", "mango.png", "zebra.png"])

    def test_sort_is_case_insensitive(self):
        self._add("Banana.png")
        self._add("apple.png")
        self._add("Cherry.png")

        texts = [self.page.images_list.item(i).text() for i in range(self.page.images_list.count())]

        self.assertEqual(texts, ["apple.png", "Banana.png", "Cherry.png"])

    def test_sort_is_stable_for_equal_keys_after_case_normalization(self):
        first = str(Path(self.tmp_dir) / "dirA" / "shot.png")
        second = str(Path(self.tmp_dir) / "dirB" / "shot.png")
        Path(first).parent.mkdir(parents=True, exist_ok=True)
        Path(second).parent.mkdir(parents=True, exist_ok=True)
        Path(first).write_bytes(b"first")
        Path(second).write_bytes(b"second")

        self.dataset_manager.add_images([first])
        internal_first = self.dataset_manager.active_dataset.images[-1].file_path
        self.dataset_manager.add_images([second])
        internal_second = self.dataset_manager.active_dataset.images[-1].file_path

        roles = [self.page.images_list.item(i).data(Qt.UserRole) for i in range(self.page.images_list.count())]

        self.assertEqual(roles, [internal_first, internal_second])

    def test_domain_order_unchanged_after_display_sort(self):
        self._add("zebra.png")
        self._add("apple.png")

        domain_names = [
            Path(image.file_path).name
            for image in self.dataset_manager.active_dataset.images
        ]
        self.assertEqual(domain_names, ["zebra.png", "apple.png"])

        displayed_names = [self.page.images_list.item(i).text() for i in range(self.page.images_list.count())]
        self.assertEqual(displayed_names, ["apple.png", "zebra.png"])

    def test_gallery_resorts_after_workspace_saved_refresh(self):
        self._add("zebra.png")

        texts_before = [self.page.images_list.item(i).text() for i in range(self.page.images_list.count())]
        self.assertEqual(texts_before, ["zebra.png"])

        self._add("apple.png")

        texts_after = [self.page.images_list.item(i).text() for i in range(self.page.images_list.count())]
        self.assertEqual(texts_after, ["apple.png", "zebra.png"])

    def test_selection_and_preview_still_work_after_reordering(self):
        self._add("existing.png")
        internal_first_alpha = self._add("aardvark.png")

        texts = [self.page.images_list.item(i).text() for i in range(self.page.images_list.count())]
        self.assertEqual(texts, ["aardvark.png", "existing.png"])

        self.page.images_list.setCurrentRow(0)
        with patch("src.ui.pages.datasets_page.ImagePreviewDialog") as mock_dialog_cls:
            self.page.enlarge_button.click()

        mock_dialog_cls.assert_called_once_with(internal_first_alpha, parent=self.page)

    # --- Mission 049: "Date du fichier (plus récent d'abord)" ---

    def _set_mtime(self, path: str, timestamp: float) -> None:
        os.utime(path, (timestamp, timestamp))

    def test_date_sort_orders_by_mtime_descending(self):
        old_path = self._add("old.png")
        self._set_mtime(old_path, 1000)
        new_path = self._add("new.png")
        self._set_mtime(new_path, 2000)

        self.page.sort_combo.setCurrentIndex(1)

        texts = [self.page.images_list.item(i).text() for i in range(self.page.images_list.count())]
        self.assertEqual(texts, ["new.png", "old.png"])

    def test_date_sort_works_for_external_file(self):
        internal_path = self._add("internal.png")
        self._set_mtime(internal_path, 1000)

        external_path = str(Path(self.tmp_dir) / "external.png")
        _make_png(external_path)
        self._set_mtime(external_path, 2000)
        self.dataset_manager.active_dataset.images.append(
            Image(image_id="ext-1", file_path=external_path)
        )
        self.workspace_manager.save()

        self.page.sort_combo.setCurrentIndex(1)

        texts = [self.page.images_list.item(i).text() for i in range(self.page.images_list.count())]
        self.assertEqual(texts, ["external.png", "internal.png"])

    def test_missing_file_sorts_last_in_date_mode(self):
        present_path = self._add("present.png")
        self._set_mtime(present_path, 1000)

        missing_path = str(Path(self.tmp_dir) / "missing.png")
        self.dataset_manager.active_dataset.images.append(
            Image(image_id="missing-1", file_path=missing_path)
        )
        self.workspace_manager.save()

        self.page.sort_combo.setCurrentIndex(1)

        texts = [self.page.images_list.item(i).text() for i in range(self.page.images_list.count())]
        self.assertEqual(texts, ["present.png", "missing.png"])

    def test_multiple_missing_files_preserve_relative_order_in_date_mode(self):
        missing_a = str(Path(self.tmp_dir) / "missing_a.png")
        missing_b = str(Path(self.tmp_dir) / "missing_b.png")
        self.dataset_manager.active_dataset.images.append(
            Image(image_id="ma", file_path=missing_a)
        )
        self.dataset_manager.active_dataset.images.append(
            Image(image_id="mb", file_path=missing_b)
        )
        self.workspace_manager.save()

        self.page.sort_combo.setCurrentIndex(1)

        texts = [self.page.images_list.item(i).text() for i in range(self.page.images_list.count())]
        self.assertEqual(texts, ["missing_a.png", "missing_b.png"])

    def test_equal_mtime_files_preserve_relative_order_in_date_mode(self):
        first = self._add("first.png")
        second = self._add("second.png")
        self._set_mtime(first, 5000)
        self._set_mtime(second, 5000)

        self.page.sort_combo.setCurrentIndex(1)

        texts = [self.page.images_list.item(i).text() for i in range(self.page.images_list.count())]
        self.assertEqual(texts, ["first.png", "second.png"])

    def test_switching_criterion_back_to_name_restores_name_order(self):
        self._add("zebra.png")
        self._add("apple.png")

        self.page.sort_combo.setCurrentIndex(1)
        self.page.sort_combo.setCurrentIndex(0)

        texts = [self.page.images_list.item(i).text() for i in range(self.page.images_list.count())]
        self.assertEqual(texts, ["apple.png", "zebra.png"])

    def test_sort_criterion_survives_workspace_saved_refresh(self):
        old_path = self._add("old.png")
        self._set_mtime(old_path, 1000)

        self.page.sort_combo.setCurrentIndex(1)

        new_path = self._add("new.png")
        self._set_mtime(new_path, 2000)

        self.assertEqual(self.page.sort_combo.currentData(), "date")
        texts = [self.page.images_list.item(i).text() for i in range(self.page.images_list.count())]
        self.assertEqual(texts, ["new.png", "old.png"])

    def test_switching_active_dataset_keeps_deterministic_sort_criterion(self):
        self._add("zebra.png")
        self.page.sort_combo.setCurrentIndex(1)

        second_dataset = self.dataset_manager.create("Landscapes")
        second_path = str(Path(self.tmp_dir) / "mountain.png")
        _make_png(second_path)
        self.dataset_manager.select(second_dataset.dataset_id)
        self.dataset_manager.add_images([second_path])

        # Switching the active Dataset must never silently reset the
        # combo back to "Nom" — the criterion lives on the Page, not on
        # any particular Dataset.
        self.assertEqual(self.page.sort_combo.currentData(), "date")
        texts = [self.page.images_list.item(i).text() for i in range(self.page.images_list.count())]
        self.assertEqual(texts, ["mountain.png"])

    def test_domain_order_unchanged_in_date_mode(self):
        self._add("zebra.png")
        self._add("apple.png")

        self.page.sort_combo.setCurrentIndex(1)

        domain_names = [
            Path(image.file_path).name
            for image in self.dataset_manager.active_dataset.images
        ]
        self.assertEqual(domain_names, ["zebra.png", "apple.png"])


if __name__ == "__main__":
    unittest.main()


class DatasetsPageImagesSelectionPreservationTest(unittest.TestCase):
    """
    Mission 082: images_list.selectedItems()/currentItem() must survive
    a same-Dataset rebuild (e.g. an unrelated WORKSPACE_SAVED, or a real
    DATASET_SELECTED that happens to reselect the very same Dataset —
    not exercised as a distinct event here, plain workspace_manager.
    save() already covers "same Dataset, unrelated refresh"). A genuine
    switch to a DIFFERENT Dataset (DATASET_SELECTED) must never carry
    the selection over, even when the two Datasets happen to reference
    the exact same file_path (a real, supported scenario — "Ajouter
    depuis Images…" references the same Workspace image, no copy) —
    guarded by DatasetsPage._displayed_dataset_id.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "DatasetsSelectionProject"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.page = DatasetsPage(self.dataset_manager, self.workspace_manager)

        for event_name in (WORKSPACE_CREATED, WORKSPACE_SAVED, DATASET_SELECTED):
            self.event_bus.subscribe(event_name, self.page.update_datasets)

        create_workspace_with_default_character(self.workspace_manager, self.character_manager, self.folder)

        self.dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(self.dataset.dataset_id)

        self.paths = []
        for name in ("a.png", "b.png", "c.png"):
            path = str(Path(self.tmp_dir) / name)
            _make_png(path)
            self.dataset_manager.add_images([path])
            self.paths.append(self.dataset_manager.active_dataset.images[-1].file_path)

    def _select(self, *paths, current=None):
        for i in range(self.page.images_list.count()):
            item = self.page.images_list.item(i)
            if item.data(Qt.UserRole) in paths:
                item.setSelected(True)
            if current is not None and item.data(Qt.UserRole) == current:
                self.page.images_list.setCurrentItem(item)

    def _selected_paths(self):
        return {item.data(Qt.UserRole) for item in self.page.images_list.selectedItems()}

    def test_refresh_without_content_change_preserves_full_selection(self):
        self._select(self.paths[0], self.paths[1], current=self.paths[0])

        self.workspace_manager.save()  # unrelated refresh, same active Dataset

        self.assertEqual(self._selected_paths(), {self.paths[0], self.paths[1]})

    def test_restoring_current_item_does_not_disturb_the_restored_selection(self):
        # Mission 082: the exact regression QItemSelectionModel.NoUpdate
        # is meant to prevent — a plain setCurrentItem() call would
        # otherwise collapse the just-restored multi-selection.
        self._select(self.paths[0], self.paths[1], self.paths[2], current=self.paths[0])

        self.workspace_manager.save()

        self.assertEqual(self._selected_paths(), {self.paths[0], self.paths[1], self.paths[2]})
        self.assertIsNotNone(self.page.images_list.currentItem())
        self.assertEqual(self.page.images_list.currentItem().data(Qt.UserRole), self.paths[0])

    def test_current_item_restored_when_it_still_exists(self):
        self._select(self.paths[0], current=self.paths[0])

        self.workspace_manager.save()

        self.assertIsNotNone(self.page.images_list.currentItem())
        self.assertEqual(self.page.images_list.currentItem().data(Qt.UserRole), self.paths[0])
        self.assertTrue(self.page.enlarge_button.isEnabled())

    def test_adding_a_new_image_preserves_previous_selection_without_selecting_the_new_one(self):
        self._select(self.paths[0], self.paths[1])

        new_path = str(Path(self.tmp_dir) / "d.png")
        _make_png(new_path)
        self.dataset_manager.add_images([new_path])
        internal_new_path = self.dataset_manager.active_dataset.images[-1].file_path

        self.assertEqual(self._selected_paths(), {self.paths[0], self.paths[1]})
        self.assertNotIn(internal_new_path, self._selected_paths())

    def test_removing_one_selected_image_keeps_the_surviving_selection(self):
        self._select(self.paths[0], self.paths[1], self.paths[2], current=self.paths[0])

        self.dataset_manager.remove_images([self.paths[0]])

        self.assertEqual(self._selected_paths(), {self.paths[1], self.paths[2]})

    def test_removing_the_current_item_leaves_current_item_none_without_arbitrary_replacement(self):
        self._select(self.paths[0], current=self.paths[0])

        self.dataset_manager.remove_images([self.paths[0]])

        self.assertIsNone(self.page.images_list.currentItem())
        self.assertFalse(self.page.enlarge_button.isEnabled())

    def test_removing_all_selected_images_empties_selection_and_disables_buttons(self):
        self._select(self.paths[0], self.paths[1], self.paths[2], current=self.paths[0])

        self.dataset_manager.remove_images(list(self.paths))

        self.assertEqual(self._selected_paths(), set())
        self.assertIsNone(self.page.images_list.currentItem())
        self.assertFalse(self.page.remove_from_dataset_button.isEnabled())
        self.assertFalse(self.page.enlarge_button.isEnabled())

    def test_switching_to_a_different_dataset_never_transfers_selection_even_with_a_shared_image(self):
        # Mission 082 critical regression: DatasetManager.add_images()
        # passthrough reuses the exact same file_path when the source is
        # already an internal Workspace image (e.g. "Ajouter depuis
        # Images…") — two different Datasets can legitimately share one.
        # A naive identity-only restoration would incorrectly cross-
        # select this image in Dataset B just because it was selected
        # in Dataset A.
        gallery_source = str(Path(self.tmp_dir) / "shared.png")
        _make_png(gallery_source)
        self.workspace_manager.add_images([gallery_source])
        shared_path = self.workspace_manager.current_workspace.images[-1].file_path

        # The shared image is referenced (passthrough, no copy) by BOTH
        # Datasets, added while each is the active one in turn.
        self.dataset_manager.add_images([shared_path])  # into "Portraits" (currently active)

        other_dataset = self.dataset_manager.create("Other")
        self.dataset_manager.select(other_dataset.dataset_id)
        self.dataset_manager.add_images([shared_path])  # into "Other" too

        self.dataset_manager.select(self.dataset.dataset_id)  # back to "Portraits"
        for i in range(self.page.images_list.count()):
            item = self.page.images_list.item(i)
            if item.data(Qt.UserRole) == shared_path:
                item.setSelected(True)
        self.assertIn(shared_path, self._selected_paths())

        self.dataset_manager.select(other_dataset.dataset_id)  # the genuine A -> B switch under test

        self.assertEqual(self._selected_paths(), set())


class DatasetsPageCaptionPanelTest(unittest.TestCase):
    """
    Mission 098: caption_edit/save_caption_button — mirrors LoRAPage's
    metadata dirty-state contract (Save/Discard/Cancel on selection
    switch), scoped to images_list's current item. See MISSION_098.md
    section 4.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "CaptionProject"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.page = DatasetsPage(self.dataset_manager, self.workspace_manager)

        for event_name in (WORKSPACE_CREATED, WORKSPACE_SAVED, DATASET_SELECTED):
            self.event_bus.subscribe(event_name, self.page.update_datasets)

        create_workspace_with_default_character(self.workspace_manager, self.character_manager, self.folder)
        self.dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(self.dataset.dataset_id)

        self.image_path = str(Path(self.tmp_dir) / "first.png")
        _make_png(self.image_path)
        self.dataset_manager.add_images([self.image_path])
        self.image_id = self.dataset_manager.active_dataset.images[0].image_id

    def _item_for(self, image_id):
        for i in range(self.page.images_list.count()):
            item = self.page.images_list.item(i)
            if item.data(Qt.UserRole + 1) == image_id:
                return item
        return None

    def _dataset_item_for(self, dataset_id):
        for i in range(self.page.dataset_list.count()):
            item = self.page.dataset_list.item(i)
            if item.data(Qt.UserRole) == dataset_id:
                return item
        return None

    # --- Display / editing ---

    def test_caption_editor_disabled_without_any_selection(self):
        self.page.images_list.setCurrentItem(None)

        self.assertFalse(self.page.caption_edit.isEnabled())
        self.assertFalse(self.page.save_caption_button.isEnabled())

    def test_selecting_an_image_with_no_caption_shows_an_empty_editor(self):
        self.page.images_list.setCurrentItem(self._item_for(self.image_id))

        self.assertTrue(self.page.caption_edit.isEnabled())
        self.assertEqual(self.page.caption_edit.toPlainText(), "")
        self.assertFalse(self.page.save_caption_button.isEnabled())

    def test_selecting_an_image_with_an_existing_caption_loads_it(self):
        self.dataset_manager.set_caption(self.image_id, "a girl smiling")

        self.page.images_list.setCurrentItem(self._item_for(self.image_id))

        self.assertEqual(self.page.caption_edit.toPlainText(), "a girl smiling")
        self.assertFalse(self.page.save_caption_button.isEnabled())

    def test_editing_the_caption_marks_dirty_and_enables_save(self):
        self.page.images_list.setCurrentItem(self._item_for(self.image_id))

        self.page.caption_edit.setPlainText("a new caption")

        self.assertTrue(self.page._caption_dirty)
        self.assertTrue(self.page.save_caption_button.isEnabled())

    def test_save_caption_persists_and_clears_dirty(self):
        self.page.images_list.setCurrentItem(self._item_for(self.image_id))
        self.page.caption_edit.setPlainText("a red car")

        self.page.save_caption()

        self.assertFalse(self.page._caption_dirty)
        self.assertFalse(self.page.save_caption_button.isEnabled())
        self.assertEqual(self.dataset.entries[self.image_id].caption, "a red car")

    def test_save_caption_with_explicit_empty_text_is_persisted_as_present(self):
        self.dataset_manager.set_caption(self.image_id, "will be cleared")
        self.page.images_list.setCurrentItem(self._item_for(self.image_id))
        self.page.caption_edit.setPlainText("")

        self.page.save_caption()

        self.assertIn(self.image_id, self.dataset.entries)
        self.assertEqual(self.dataset.entries[self.image_id].caption, "")

    # --- Visual indicator ---

    def test_thumbnail_has_no_indicator_without_a_caption(self):
        item = self._item_for(self.image_id)
        self.assertEqual(item.text(), "first.png")

    def test_thumbnail_shows_indicator_once_a_caption_entry_exists(self):
        self.dataset_manager.set_caption(self.image_id, "anything")

        self.page.update_datasets()

        item = self._item_for(self.image_id)
        self.assertIn("first.png", item.text())
        self.assertNotEqual(item.text(), "first.png")

    def test_thumbnail_shows_indicator_even_for_an_explicitly_empty_caption(self):
        self.dataset_manager.set_caption(self.image_id, "")

        self.page.update_datasets()

        item = self._item_for(self.image_id)
        self.assertNotEqual(item.text(), "first.png")

    # --- Switching selection while dirty ---

    def test_switching_selection_while_dirty_cancel_keeps_draft_and_selection(self):
        second_path = str(Path(self.tmp_dir) / "second.png")
        _make_png(second_path)
        self.dataset_manager.add_images([second_path])
        second_id = self.dataset_manager.active_dataset.images[-1].image_id

        self.page.images_list.setCurrentItem(self._item_for(self.image_id))
        self.page.caption_edit.setPlainText("unsaved draft")

        with patch("src.ui.pages.datasets_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Cancel
            self.page.images_list.setCurrentItem(self._item_for(second_id))

        self.assertTrue(self.page._caption_dirty)
        self.assertEqual(self.page.caption_edit.toPlainText(), "unsaved draft")
        self.assertEqual(self.page._caption_loaded_image_id, self.image_id)
        self.assertEqual(self.page.images_list.currentItem().data(Qt.UserRole + 1), self.image_id)
        self.assertNotIn(self.image_id, self.dataset.entries)

    def test_switching_selection_while_dirty_discard_loads_the_new_image(self):
        second_path = str(Path(self.tmp_dir) / "second.png")
        _make_png(second_path)
        self.dataset_manager.add_images([second_path])
        second_id = self.dataset_manager.active_dataset.images[-1].image_id

        self.page.images_list.setCurrentItem(self._item_for(self.image_id))
        self.page.caption_edit.setPlainText("unsaved draft")

        with patch("src.ui.pages.datasets_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Discard
            self.page.images_list.setCurrentItem(self._item_for(second_id))

        self.assertFalse(self.page._caption_dirty)
        self.assertEqual(self.page._caption_loaded_image_id, second_id)
        self.assertEqual(self.page.caption_edit.toPlainText(), "")
        self.assertNotIn(self.image_id, self.dataset.entries)

    def test_switching_selection_while_dirty_save_persists_then_loads_the_new_image(self):
        second_path = str(Path(self.tmp_dir) / "second.png")
        _make_png(second_path)
        self.dataset_manager.add_images([second_path])
        second_id = self.dataset_manager.active_dataset.images[-1].image_id

        self.page.images_list.setCurrentItem(self._item_for(self.image_id))
        self.page.caption_edit.setPlainText("saved via switch")

        with patch("src.ui.pages.datasets_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Save
            self.page.images_list.setCurrentItem(self._item_for(second_id))

        self.assertFalse(self.page._caption_dirty)
        self.assertEqual(self.page._caption_loaded_image_id, second_id)
        self.assertEqual(self.dataset.entries[self.image_id].caption, "saved via switch")

    def test_switching_selection_without_dirty_never_prompts(self):
        second_path = str(Path(self.tmp_dir) / "second.png")
        _make_png(second_path)
        self.dataset_manager.add_images([second_path])
        second_id = self.dataset_manager.active_dataset.images[-1].image_id

        self.page.images_list.setCurrentItem(self._item_for(self.image_id))

        with patch("src.ui.pages.datasets_page.QMessageBox") as mock_message_box:
            self.page.images_list.setCurrentItem(self._item_for(second_id))
            mock_message_box.assert_not_called()

        self.assertEqual(self.page._caption_loaded_image_id, second_id)

    def test_unrelated_refresh_never_discards_a_dirty_draft(self):
        # A WORKSPACE_SAVED unrelated to the caption panel (e.g. renaming
        # the dataset) must never wipe an in-progress caption draft.
        self.page.images_list.setCurrentItem(self._item_for(self.image_id))
        self.page.caption_edit.setPlainText("still typing")

        self.dataset_manager.update_name("Renamed")

        self.assertTrue(self.page._caption_dirty)
        self.assertEqual(self.page.caption_edit.toPlainText(), "still typing")

    # --- Switching Dataset while dirty (Mission 158) ---

    def _create_second_dataset_visible_in_list(self, name="Landscapes"):
        second_dataset = self.dataset_manager.create(name)
        # DATASET_CREATED is not wired to update_datasets() in this
        # fixture (mirrors the real MainWindow wiring, where it never
        # needs to be — see main_window.py) — a plain, non-gating
        # refresh is enough to make the new item selectable in
        # dataset_list for this test's own setup, exactly like adding a
        # second image via add_images() (WORKSPACE_SAVED, already
        # subscribed) does for images_list above.
        self.page.update_datasets()
        return second_dataset

    def test_switching_dataset_while_dirty_cancel_keeps_draft_and_dataset(self):
        second_dataset = self._create_second_dataset_visible_in_list()

        self.page.images_list.setCurrentItem(self._item_for(self.image_id))
        self.page.caption_edit.setPlainText("unsaved draft")

        with patch("src.ui.pages.datasets_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Cancel
            self.page.dataset_list.setCurrentItem(self._dataset_item_for(second_dataset.dataset_id))

        self.assertTrue(self.page._caption_dirty)
        self.assertEqual(self.page.caption_edit.toPlainText(), "unsaved draft")
        self.assertEqual(self.dataset_manager.active_dataset_id, self.dataset.dataset_id)
        self.assertEqual(
            self.page.dataset_list.currentItem().data(Qt.UserRole), self.dataset.dataset_id
        )
        self.assertNotIn(self.image_id, self.dataset.entries)

    def test_switching_dataset_while_dirty_discard_loads_the_target_dataset(self):
        second_dataset = self._create_second_dataset_visible_in_list()

        self.page.images_list.setCurrentItem(self._item_for(self.image_id))
        self.page.caption_edit.setPlainText("unsaved draft")

        with patch("src.ui.pages.datasets_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Discard
            self.page.dataset_list.setCurrentItem(self._dataset_item_for(second_dataset.dataset_id))

        self.assertFalse(self.page._caption_dirty)
        self.assertEqual(self.dataset_manager.active_dataset_id, second_dataset.dataset_id)
        self.assertNotIn(self.image_id, self.dataset.entries)

    def test_switching_dataset_while_dirty_save_persists_then_loads_the_target_dataset(self):
        second_dataset = self._create_second_dataset_visible_in_list()

        self.page.images_list.setCurrentItem(self._item_for(self.image_id))
        self.page.caption_edit.setPlainText("saved via dataset switch")

        with patch("src.ui.pages.datasets_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Save
            self.page.dataset_list.setCurrentItem(self._dataset_item_for(second_dataset.dataset_id))

        self.assertFalse(self.page._caption_dirty)
        self.assertEqual(self.dataset_manager.active_dataset_id, second_dataset.dataset_id)
        self.assertEqual(self.dataset.entries[self.image_id].caption, "saved via dataset switch")

    def test_switching_dataset_without_dirty_never_prompts(self):
        second_dataset = self._create_second_dataset_visible_in_list()

        self.page.images_list.setCurrentItem(self._item_for(self.image_id))

        with patch("src.ui.pages.datasets_page.QMessageBox") as mock_message_box:
            self.page.dataset_list.setCurrentItem(self._dataset_item_for(second_dataset.dataset_id))
            mock_message_box.assert_not_called()

        self.assertEqual(self.dataset_manager.active_dataset_id, second_dataset.dataset_id)

    def test_switching_dataset_while_dirty_save_failure_keeps_draft_and_dataset(self):
        # Mission 158: the branch that matters most — DatasetManager.
        # select() must never be called once Save has failed, or the
        # Page would silently move to the target Dataset despite the
        # draft never having actually been persisted.
        second_dataset = self._create_second_dataset_visible_in_list()

        self.page.images_list.setCurrentItem(self._item_for(self.image_id))
        self.page.caption_edit.setPlainText("unsaved draft, save will fail")

        with patch("src.ui.pages.datasets_page.QMessageBox") as mock_message_box, patch.object(
            self.dataset_manager, "set_caption", side_effect=WorkspaceManagerError("disk full")
        ):
            mock_message_box.return_value.exec.return_value = mock_message_box.Save
            self.page.dataset_list.setCurrentItem(self._dataset_item_for(second_dataset.dataset_id))

        self.assertTrue(self.page._caption_dirty)
        self.assertEqual(self.page.caption_edit.toPlainText(), "unsaved draft, save will fail")
        self.assertEqual(self.dataset_manager.active_dataset_id, self.dataset.dataset_id)
        self.assertEqual(
            self.page.dataset_list.currentItem().data(Qt.UserRole), self.dataset.dataset_id
        )
        self.assertNotIn(self.image_id, self.dataset.entries)

    # --- Removing images while dirty (Mission 159) ---

    def _confirm_removal(self, accept: bool):
        # Same technique as test_dataset_roundtrip.py's own
        # _confirm_delete() — _confirm_discard_caption_before_removal()
        # decides via addButton()/clickedButton() identity, not via
        # exec()'s return value like _confirm_discard_caption_before_
        # switch() above, so it needs its own distinct mocking shape.
        patcher = patch("src.ui.pages.datasets_page.QMessageBox")
        mock_cls = patcher.start()
        self.addCleanup(patcher.stop)

        remove_sentinel = object()
        cancel_sentinel = object()
        box_instance = mock_cls.return_value
        box_instance.addButton.side_effect = [remove_sentinel, cancel_sentinel]
        box_instance.clickedButton.return_value = (
            remove_sentinel if accept else cancel_sentinel
        )

        return mock_cls

    def test_removing_the_dirty_image_cancel_keeps_draft_and_image(self):
        item = self._item_for(self.image_id)
        self.page.images_list.setCurrentItem(item)
        item.setSelected(True)
        self.page.caption_edit.setPlainText("unsaved draft")

        self._confirm_removal(accept=False)
        self.page.remove_selected_images_from_dataset()

        self.assertTrue(self.page._caption_dirty)
        self.assertEqual(self.page.caption_edit.toPlainText(), "unsaved draft")
        self.assertEqual(self.page.images_list.count(), 1)
        self.assertEqual(len(self.dataset_manager.active_dataset.images), 1)

    def test_removing_a_selection_including_the_dirty_image_cancel_keeps_draft_and_all_images(self):
        second_path = str(Path(self.tmp_dir) / "second.png")
        _make_png(second_path)
        self.dataset_manager.add_images([second_path])
        second_id = self.dataset_manager.active_dataset.images[-1].image_id

        self.page.images_list.setCurrentItem(self._item_for(self.image_id))
        self.page.caption_edit.setPlainText("unsaved draft")
        self._item_for(self.image_id).setSelected(True)
        self._item_for(second_id).setSelected(True)

        self._confirm_removal(accept=False)
        self.page.remove_selected_images_from_dataset()

        self.assertTrue(self.page._caption_dirty)
        self.assertEqual(self.page.caption_edit.toPlainText(), "unsaved draft")
        self.assertEqual(self.page.images_list.count(), 2)

    def test_removing_the_dirty_image_discard_removes_it_and_clears_the_draft(self):
        item = self._item_for(self.image_id)
        self.page.images_list.setCurrentItem(item)
        item.setSelected(True)
        self.page.caption_edit.setPlainText("unsaved draft")

        self._confirm_removal(accept=True)
        self.page.remove_selected_images_from_dataset()

        self.assertFalse(self.page._caption_dirty)
        self.assertEqual(self.page.images_list.count(), 0)
        self.assertNotIn(self.image_id, self.dataset.entries)

    def test_removing_other_images_while_a_different_image_is_dirty_never_prompts_and_preserves_draft(self):
        # Mission 159 design proof (Case C): the dirty image is
        # excluded from the removed batch — the pre-existing identity
        # short-circuit in _refresh_caption_panel_for_current_selection()
        # (Mission 082/098) already preserves it, no new dialogue
        # needed.
        second_path = str(Path(self.tmp_dir) / "second.png")
        _make_png(second_path)
        self.dataset_manager.add_images([second_path])
        second_id = self.dataset_manager.active_dataset.images[-1].image_id

        self.page.images_list.setCurrentItem(self._item_for(self.image_id))
        self.page.caption_edit.setPlainText("unsaved draft")
        self._item_for(self.image_id).setSelected(False)
        self._item_for(second_id).setSelected(True)

        with patch("src.ui.pages.datasets_page.QMessageBox") as mock_message_box:
            self.page.remove_selected_images_from_dataset()
            mock_message_box.assert_not_called()

        self.assertTrue(self.page._caption_dirty)
        self.assertEqual(self.page.caption_edit.toPlainText(), "unsaved draft")
        self.assertEqual(self.page.images_list.count(), 1)
        self.assertEqual(self.page._caption_loaded_image_id, self.image_id)
        self.assertEqual(self.page.images_list.currentItem().data(Qt.UserRole + 1), self.image_id)

    def test_removing_images_without_any_dirty_draft_never_prompts(self):
        item = self._item_for(self.image_id)
        self.page.images_list.setCurrentItem(item)
        item.setSelected(True)

        with patch("src.ui.pages.datasets_page.QMessageBox") as mock_message_box:
            self.page.remove_selected_images_from_dataset()
            mock_message_box.assert_not_called()

        self.assertEqual(self.page.images_list.count(), 0)

    def test_removing_the_dirty_image_remove_failure_after_discard_shows_error_and_preserves_original_caption(self):
        self.dataset_manager.set_caption(self.image_id, "original caption")
        item = self._item_for(self.image_id)
        self.page.images_list.setCurrentItem(item)
        item.setSelected(True)
        self.page.caption_edit.setPlainText("edited but will be abandoned")

        mock_message_box = self._confirm_removal(accept=True)
        with patch.object(
            self.dataset_manager, "remove_images", side_effect=WorkspaceManagerError("disk full")
        ):
            self.page.remove_selected_images_from_dataset()

        mock_message_box.critical.assert_called_once()
        self.assertEqual(self.page.images_list.count(), 1)
        self.assertEqual(self.dataset.entries[self.image_id].caption, "original caption")
        # Mission 159: the draft was explicitly abandoned by the user's
        # own "Retirer quand même" choice before the failed attempt —
        # never resurrected. But a _caption_dirty == False state must
        # always correspond to what's actually persisted: the explicit
        # reload in remove_selected_images_from_dataset()'s except
        # branch replaces the abandoned text with the real, restored
        # original caption — never leaves the editor showing a value
        # that no longer matches the Domain.
        self.assertEqual(self.page.caption_edit.toPlainText(), "original caption")
        self.assertFalse(self.page._caption_dirty)
        self.assertFalse(self.page.save_caption_button.isEnabled())

    # --- Deleting the Dataset while its caption is dirty (Mission 160) ---

    def _confirm_delete_dataset(self, accept: bool):
        # Same technique as _confirm_removal() above (mirroring
        # test_dataset_roundtrip.py's own _confirm_delete()) —
        # delete_dataset()'s pre-existing confirmation decides via
        # addButton()/clickedButton() identity, not exec()'s return
        # value.
        patcher = patch("src.ui.pages.datasets_page.QMessageBox")
        mock_cls = patcher.start()
        self.addCleanup(patcher.stop)

        delete_sentinel = object()
        cancel_sentinel = object()
        box_instance = mock_cls.return_value
        box_instance.addButton.side_effect = [delete_sentinel, cancel_sentinel]
        box_instance.clickedButton.return_value = (
            delete_sentinel if accept else cancel_sentinel
        )

        return mock_cls

    def test_deleting_the_dataset_with_a_dirty_caption_cancel_keeps_dataset_and_draft(self):
        self.page.images_list.setCurrentItem(self._item_for(self.image_id))
        self.page.caption_edit.setPlainText("unsaved draft")

        self._confirm_delete_dataset(accept=False)
        with patch.object(self.dataset_manager, "delete") as delete_mock:
            self.page.delete_dataset()
            delete_mock.assert_not_called()

        self.assertEqual(self.dataset_manager.datasets, [self.dataset])
        self.assertEqual(self.page.caption_edit.toPlainText(), "unsaved draft")
        self.assertTrue(self.page._caption_dirty)
        self.assertTrue(self.page.save_caption_button.isEnabled())

    def test_deleting_the_dataset_with_a_dirty_caption_confirm_deletes_and_clears_the_draft(self):
        self.page.images_list.setCurrentItem(self._item_for(self.image_id))
        self.page.caption_edit.setPlainText("unsaved draft")

        self._confirm_delete_dataset(accept=True)
        self.page.delete_dataset()

        self.assertEqual(self.dataset_manager.datasets, [])
        self.assertIsNone(self.dataset_manager.active_dataset_id)
        # Mission 160: none of this is set explicitly by delete_dataset()
        # itself — WorkspaceManager.save()'s synchronous WORKSPACE_SAVED
        # (published from inside DatasetManager.delete(), before it even
        # returns here) already drives update_datasets() ->
        # _refresh_caption_panel_for_current_selection() -> a genuine
        # identity change (the Dataset and its images are gone) ->
        # _load_caption_into_editor(None), which alone produces every
        # assertion below.
        self.assertFalse(self.page._caption_dirty)
        self.assertFalse(self.page.save_caption_button.isEnabled())
        self.assertEqual(self.page.caption_edit.toPlainText(), "")
        self.assertFalse(self.page.caption_edit.isEnabled())

    def test_deleting_the_dataset_without_a_dirty_caption_shows_the_historical_confirmation_text(self):
        expected_label = self._dataset_item_for(self.dataset.dataset_id).text()
        mock_cls = self._confirm_delete_dataset(accept=False)

        self.page.delete_dataset()

        text = mock_cls.return_value.setText.call_args[0][0]
        self.assertEqual(
            text,
            f"Supprimer le dataset « {expected_label} » ? Cette action est "
            "irréversible. Les images provenant de la galerie Images y "
            "resteront ; les images importées directement dans ce dataset "
            "seront supprimées avec lui."
        )

    def test_deleting_the_dataset_with_a_dirty_caption_confirmation_text_mentions_the_lost_draft(self):
        self.page.images_list.setCurrentItem(self._item_for(self.image_id))
        self.page.caption_edit.setPlainText("unsaved draft")

        mock_cls = self._confirm_delete_dataset(accept=False)
        self.page.delete_dataset()

        text = mock_cls.return_value.setText.call_args[0][0]
        self.assertIn("modifications de caption non enregistrées", text)
        self.assertIn("perdues", text)

    def test_deleting_the_dataset_with_a_dirty_caption_manager_failure_preserves_the_draft(self):
        self.dataset_manager.set_caption(self.image_id, "original caption")
        item = self._item_for(self.image_id)
        self.page.images_list.setCurrentItem(item)
        self.page.caption_edit.setPlainText("edited but not saved")

        mock_message_box = self._confirm_delete_dataset(accept=True)
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            self.page.delete_dataset()

        mock_message_box.critical.assert_called_once()
        self.assertEqual(self.dataset_manager.datasets, [self.dataset])
        self.assertEqual(self.dataset_manager.active_dataset_id, self.dataset.dataset_id)
        # Mission 160: nothing refreshes on this path (WORKSPACE_SAVED is
        # only ever published after a successful WorkspaceStorage.save()
        # — never reached here), so images_list keeps the exact same
        # QListWidgetItem, never rebuilt.
        self.assertIs(self.page.images_list.currentItem(), item)
        self.assertEqual(self.page.caption_edit.toPlainText(), "edited but not saved")
        self.assertTrue(self.page._caption_dirty)
        self.assertTrue(self.page.save_caption_button.isEnabled())
        # The draft was never abandoned/saved — the Domain still holds
        # exactly the caption that was persisted before this test's own
        # edit, never the unsaved draft text.
        self.assertEqual(self.dataset.entries[self.image_id].caption, "original caption")


class DatasetsPageConfirmContextChangeTest(unittest.TestCase):
    """
    Mission 158: DatasetsPage.confirm_context_change()/
    reset_for_context_change() — the guard MainWindow calls before a
    Workspace/Character context change (new_project()/open_project()/
    closeEvent()), mirroring LoRAPageConfirmContextChangeTest's exact
    shape (test_lora_roundtrip.py).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "ContextChangeProject"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.page = DatasetsPage(self.dataset_manager, self.workspace_manager)

        for event_name in (WORKSPACE_CREATED, WORKSPACE_SAVED, DATASET_SELECTED):
            self.event_bus.subscribe(event_name, self.page.update_datasets)

        create_workspace_with_default_character(self.workspace_manager, self.character_manager, self.folder)
        self.dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(self.dataset.dataset_id)

        self.image_path = str(Path(self.tmp_dir) / "first.png")
        _make_png(self.image_path)
        self.dataset_manager.add_images([self.image_path])
        self.image_id = self.dataset_manager.active_dataset.images[0].image_id

    def _item_for(self, image_id):
        for i in range(self.page.images_list.count()):
            item = self.page.images_list.item(i)
            if item.data(Qt.UserRole + 1) == image_id:
                return item
        return None

    def _make_dirty_caption(self, text="unsaved draft"):
        self.page.images_list.setCurrentItem(self._item_for(self.image_id))
        self.page.caption_edit.setPlainText(text)
        self.assertTrue(self.page._caption_dirty)

    def test_confirm_context_change_without_dirty_draft_returns_true_no_dialog(self):
        with patch("src.ui.pages.datasets_page.QMessageBox") as mock_message_box:
            result = self.page.confirm_context_change()
            mock_message_box.assert_not_called()

        self.assertTrue(result)

    def test_confirm_context_change_cancel_returns_false_and_keeps_draft(self):
        self._make_dirty_caption()

        with patch("src.ui.pages.datasets_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Cancel
            result = self.page.confirm_context_change()

        self.assertFalse(result)
        self.assertTrue(self.page._caption_dirty)
        self.assertEqual(self.page.caption_edit.toPlainText(), "unsaved draft")
        self.assertNotIn(self.image_id, self.dataset.entries)

    def test_confirm_context_change_save_choice_persists_and_returns_true(self):
        self._make_dirty_caption("persist me")

        with patch("src.ui.pages.datasets_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Save
            result = self.page.confirm_context_change()

        self.assertTrue(result)
        self.assertFalse(self.page._caption_dirty)
        self.assertEqual(self.dataset.entries[self.image_id].caption, "persist me")

    def test_confirm_context_change_save_failure_returns_false_and_keeps_draft(self):
        self._make_dirty_caption("will fail to save")

        with patch("src.ui.pages.datasets_page.QMessageBox") as mock_message_box, patch.object(
            self.dataset_manager, "set_caption", side_effect=WorkspaceManagerError("disk full")
        ):
            mock_message_box.return_value.exec.return_value = mock_message_box.Save
            result = self.page.confirm_context_change()

        self.assertFalse(result)
        self.assertTrue(self.page._caption_dirty)
        self.assertEqual(self.page.caption_edit.toPlainText(), "will fail to save")
        self.assertNotIn(self.image_id, self.dataset.entries)

    def test_reset_for_context_change_clears_a_stale_draft_and_resyncs_from_domain(self):
        self._make_dirty_caption("about to be reset")

        # DatasetManager._on_context_changed() — subscribed to the same
        # 5 events as this method, always registered first (the Manager
        # is constructed before the Page's own EventBus wiring) — always
        # resets active_dataset_id to None before reset_for_context_change()
        # ever runs in production; reproduced explicitly here since this
        # test calls it directly, out of that real event sequence.
        self.dataset_manager.active_dataset_id = None

        self.page.reset_for_context_change()

        self.assertFalse(self.page._caption_dirty)
        self.assertFalse(self.page.save_caption_button.isEnabled())
        self.assertIsNone(self.page._caption_loaded_image_id)
        self.assertEqual(self.page.caption_edit.toPlainText(), "")


class DatasetsPageNameAndCaptionDraftTest(unittest.TestCase):
    """
    Mission 165: a name draft (name_edit, commit-on-blur) and a caption
    draft (caption_edit, explicit Save, Mission 098) are two independent
    states that must never overwrite, discard or commit one another.
    _wire() reproduces the exact subscriptions main_window.py registers
    for DatasetsPage (including WORKSPACE_RENAMED and the 5 context-reset
    events routed to reset_for_context_change()). The name-only contract
    lives in test_dataset_roundtrip.py (DatasetsPageNameDraftProtectionTest).
    """

    def setUp(self):
        # Armed first, hence stopped last: an unexpected real QMessageBox
        # becomes a clean UnexpectedDialogError, never a human-click wait.
        self.dialog_guard = start_dialog_guard()
        self.addCleanup(stop_dialog_guard, self.dialog_guard)

        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "NameAndCaptionProject"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.page = DatasetsPage(self.dataset_manager, self.workspace_manager)

        for event_name in (
            WORKSPACE_SAVED, WORKSPACE_RENAMED, CHARACTER_CREATED,
            DATASET_CREATED, DATASET_SELECTED, DATASET_DELETED,
        ):
            self.event_bus.subscribe(event_name, self.page.update_datasets)
        for event_name in (
            WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED,
            CHARACTER_SELECTED, CHARACTER_DELETED,
        ):
            self.event_bus.subscribe(event_name, self.page.reset_for_context_change)

        create_workspace_with_default_character(self.workspace_manager, self.character_manager, self.folder)
        self.alpha = self.dataset_manager.create("Alpha")
        self.beta = self.dataset_manager.create("Beta")
        self.dataset_manager.select(self.alpha.dataset_id)

        self.image_path = str(Path(self.tmp_dir) / "first.png")
        _make_png(self.image_path)
        self.dataset_manager.add_images([self.image_path])
        self.image_id = self.dataset_manager.active_dataset.images[0].image_id

        self.page.resize(500, 700)
        self.page.show()
        self.addCleanup(self.page.close)
        QTest.qWaitForWindowExposed(self.page)

    def _item_for(self, image_id):
        for i in range(self.page.images_list.count()):
            item = self.page.images_list.item(i)
            if item.data(Qt.UserRole + 1) == image_id:
                return item
        return None

    def _dataset_item_for(self, dataset_id):
        for i in range(self.page.dataset_list.count()):
            item = self.page.dataset_list.item(i)
            if item.data(Qt.UserRole) == dataset_id:
                return item
        return None

    def _make_both_drafts(self, caption="caption draft", name_suffix=" EDIT"):
        self.page.images_list.setCurrentItem(self._item_for(self.image_id))
        self.page.caption_edit.setPlainText(caption)
        self.assertTrue(self.page._caption_dirty)

        self.page.name_edit.setFocus()
        QTest.qWait(10)
        QTest.keyClicks(self.page.name_edit, name_suffix)
        self.assertEqual(self.page.name_edit.text(), "Alpha" + name_suffix)

    def _assert_caption_draft_intact(self, caption="caption draft"):
        self.assertEqual(self.page.caption_edit.toPlainText(), caption)
        self.assertTrue(self.page._caption_dirty)
        self.assertTrue(self.page.save_caption_button.isEnabled())
        self.assertEqual(self.page._caption_loaded_image_id, self.image_id)
        # Never persisted by any name-related path.
        self.assertNotIn(self.image_id, self.alpha.entries)

    def test_unrelated_events_preserve_both_the_name_draft_and_the_caption_draft(self):

        self._make_both_drafts()

        self.workspace_manager.save()
        self.assertEqual(self.page.name_edit.text(), "Alpha EDIT")
        self._assert_caption_draft_intact()
        self.assertEqual(self.alpha.name, "Alpha")

        # WORKSPACE_RENAMED: only the name draft is asserted here. A
        # project rename remaps every internal image path, and
        # update_datasets()'s images_list selection restoration is keyed
        # by file_path (Mission 082) — a pre-existing, separate
        # interaction with the caption draft (MainWindow.rename_project()
        # deliberately runs no dirty-draft guard), outside this
        # mission's scope and deliberately not asserted either way.
        self.workspace_manager.rename("RenamedProject")
        self.assertEqual(self.page.name_edit.text(), "Alpha EDIT")
        self.assertEqual(self.alpha.name, "Alpha")

    def test_successful_rename_keeps_the_caption_draft_untouched(self):

        self._make_both_drafts()

        QTest.keyClick(self.page.name_edit, Qt.Key_Return)

        self.assertEqual(self.alpha.name, "Alpha EDIT")
        self.assertEqual(self.page.name_edit.text(), "Alpha EDIT")
        self.assertIn("Alpha EDIT", self.page.dataset_list.currentItem().text())
        self._assert_caption_draft_intact()

    def test_failed_rename_restores_the_name_and_keeps_the_caption_draft(self):

        self._make_both_drafts(name_suffix=" WILL_FAIL")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.datasets_page.QMessageBox.critical") as critical_mock:
            QTest.keyClick(self.page.name_edit, Qt.Key_Return)

        self.assertEqual(critical_mock.call_count, 1)
        self.assertEqual(self.alpha.name, "Alpha")
        self.assertEqual(self.page.name_edit.text(), "Alpha")
        self._assert_caption_draft_intact()

    def test_saving_the_caption_never_commits_or_discards_the_name_draft(self):

        self._make_both_drafts()

        # Called directly (a real click on the button would first move
        # the focus, which commits the name through editingFinished).
        self.page.save_caption()

        self.assertEqual(self.alpha.entries[self.image_id].caption, "caption draft")
        self.assertFalse(self.page._caption_dirty)
        # The caption Save went through WorkspaceManager.save() — the
        # resulting WORKSPACE_SAVED refresh preserved the name draft and
        # never committed it.
        self.assertEqual(self.page.name_edit.text(), "Alpha EDIT")
        self.assertEqual(self.alpha.name, "Alpha")

    def test_cancelled_dataset_switch_with_a_dirty_caption_never_loses_the_name(self):
        """
        A real click on another Dataset first moves the focus, so
        editingFinished may commit the name BEFORE the caption dialog is
        even shown — the contract is therefore "no loss of the name text,
        whether still a draft or already correctly persisted by the
        existing commit-on-blur behavior", not "the name stays
        unsaved". The caption draft, the selection/context restoration
        and the absence of any write on the wrong Dataset are asserted
        exactly.
        """

        self._make_both_drafts()

        rect = self.page.dataset_list.visualItemRect(self._dataset_item_for(self.beta.dataset_id))

        with patch.object(
            self.page, "_confirm_discard_caption_before_switch", return_value=QMessageBox.Cancel
        ) as dialog_mock:
            QTest.mouseClick(self.page.dataset_list.viewport(), Qt.LeftButton, pos=rect.center())
            QTest.qWait(20)

        self.assertEqual(dialog_mock.call_count, 1)

        # Selection/context restored by the existing guard.
        self.assertEqual(self.dataset_manager.active_dataset_id, self.alpha.dataset_id)
        self.assertEqual(
            self.page.dataset_list.currentItem().data(Qt.UserRole), self.alpha.dataset_id
        )
        self.assertEqual(self.page._name_editor_owner_id, self.alpha.dataset_id)

        # The name text is never lost: still the typed text, whether it
        # remained a draft or was already persisted by the blur.
        self.assertEqual(self.page.name_edit.text(), "Alpha EDIT")
        self.assertIn(self.alpha.name, ("Alpha", "Alpha EDIT"))

        # No write on the wrong Dataset.
        self.assertEqual(self.beta.name, "Beta")

        # The caption draft survived untouched.
        self._assert_caption_draft_intact()

    def test_dataset_switch_with_discard_choice_commits_the_name_on_the_right_dataset_only(self):

        self._make_both_drafts()

        rect = self.page.dataset_list.visualItemRect(self._dataset_item_for(self.beta.dataset_id))

        with patch.object(
            self.page, "_confirm_discard_caption_before_switch", return_value=QMessageBox.Discard
        ):
            QTest.mouseClick(self.page.dataset_list.viewport(), Qt.LeftButton, pos=rect.center())
            QTest.qWait(20)

        # The Dataset that was active at focus loss received its draft;
        # the one switched to was never written.
        self.assertEqual(self.alpha.name, "Alpha EDIT")
        self.assertEqual(self.beta.name, "Beta")
        self.assertEqual(self.dataset_manager.active_dataset_id, self.beta.dataset_id)
        self.assertEqual(self.page.name_edit.text(), "Beta")
        self.assertFalse(self.page._caption_dirty)
