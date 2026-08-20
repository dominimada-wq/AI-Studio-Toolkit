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
from PySide6.QtWidgets import QApplication, QListWidget

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


if __name__ == "__main__":
    unittest.main()
