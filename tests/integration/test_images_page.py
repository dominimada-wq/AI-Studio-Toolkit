"""
Real-widget coverage for ImagesPage: the existing "Importer des
images" flow (Workspace.images, unchanged) plus Mission 015's enlarged
preview wiring (double-click and the "Voir en grand" button, both
opening the same ImagePreviewDialog). ImagePreviewDialog.exec() is
patched throughout — a real modal exec() would block the test process
(same lesson as Mission 014's QMessageBox hang) — these tests validate
the wiring, not the dialog itself (see test_image_preview_dialog.py
for that).

Mission 019 extends this file with the icon-mode gallery: thumbnails,
short filename label, full-path tooltip, and Qt.UserRole as the sole
source of truth for file_path (item.text() is presentation only, never
read by _on_item_double_clicked/_on_enlarge_clicked anymore).
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QListWidget

from src.core.event_bus import EventBus
from src.managers.workspace_manager import WorkspaceManager, WORKSPACE_CREATED, WORKSPACE_SAVED
from src.ui.pages.images_page import ImagesPage

_app = QApplication.instance() or QApplication([])


def _make_png(path: str, width: int = 4, height: int = 4) -> None:
    pixmap = QPixmap(width, height)
    pixmap.fill()
    assert pixmap.save(path, "PNG")


class ImagesPageTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "ImagesProject"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.workspace_manager.create(self.folder)

        self.page = ImagesPage(self.workspace_manager)

        for event_name in (WORKSPACE_CREATED, WORKSPACE_SAVED):
            self.event_bus.subscribe(event_name, self.page.update_images)

        self.image_path = str(Path(self.tmp_dir) / "existing.png")
        Path(self.image_path).write_bytes(b"fake-png-bytes")
        self.workspace_manager.add_images([self.image_path])

    # --- Selection -> button state ---

    def test_enlarge_button_disabled_without_selection(self):
        self.assertIsNone(self.page.list_widget.currentItem())
        self.assertFalse(self.page.enlarge_button.isEnabled())

    def test_enlarge_button_enabled_once_an_item_is_selected(self):
        self.page.list_widget.setCurrentRow(0)

        self.assertTrue(self.page.enlarge_button.isEnabled())

    # --- Button / double-click both open the same dialog ---

    @patch("src.ui.pages.images_page.ImagePreviewDialog")
    def test_enlarge_button_opens_the_selected_file_path(self, mock_dialog_cls):
        self.page.list_widget.setCurrentRow(0)

        self.page.enlarge_button.click()

        mock_dialog_cls.assert_called_once_with(self.image_path, parent=self.page)
        mock_dialog_cls.return_value.exec.assert_called_once()

    @patch("src.ui.pages.images_page.ImagePreviewDialog")
    def test_double_click_opens_the_same_file_path(self, mock_dialog_cls):
        item = self.page.list_widget.item(0)

        self.page._on_item_double_clicked(item)

        mock_dialog_cls.assert_called_once_with(self.image_path, parent=self.page)
        mock_dialog_cls.return_value.exec.assert_called_once()

    @patch("src.ui.pages.images_page.ImagePreviewDialog")
    def test_enlarge_button_with_no_selection_is_a_no_op(self, mock_dialog_cls):
        self.page.enlarge_button.click()

        mock_dialog_cls.assert_not_called()

    # --- Missing file: dialog is still opened, no Domain mutation ---

    @patch("src.ui.pages.images_page.ImagePreviewDialog")
    def test_missing_file_opens_dialog_without_mutating_domain(self, mock_dialog_cls):
        Path(self.image_path).unlink()
        self.page.list_widget.setCurrentRow(0)

        self.page.enlarge_button.click()

        mock_dialog_cls.assert_called_once_with(self.image_path, parent=self.page)
        self.assertEqual(len(self.workspace_manager.current_workspace.images), 1)
        self.assertEqual(
            self.workspace_manager.current_workspace.images[0].file_path, self.image_path
        )

    # --- Consultation is read-only ---

    # --- Refresh (WORKSPACE_SAVED) must not leave a stale selection ---

    def test_refresh_clears_previous_selection_and_disables_button(self):
        self.page.list_widget.setCurrentRow(0)
        self.assertTrue(self.page.enlarge_button.isEnabled())

        # A second WORKSPACE_SAVED (another import) rebuilds the list
        # from scratch — the old QListWidgetItem the selection pointed
        # at no longer exists afterward.
        second_path = str(Path(self.tmp_dir) / "second.png")
        Path(second_path).write_bytes(b"fake-png-bytes-2")
        self.workspace_manager.add_images([second_path])

        self.assertIsNone(self.page.list_widget.currentItem())
        self.assertFalse(self.page.enlarge_button.isEnabled())

    def test_refresh_with_no_prior_selection_leaves_button_disabled(self):
        self.assertFalse(self.page.enlarge_button.isEnabled())

        second_path = str(Path(self.tmp_dir) / "second_b.png")
        Path(second_path).write_bytes(b"fake-png-bytes-2")
        self.workspace_manager.add_images([second_path])

        self.assertIsNone(self.page.list_widget.currentItem())
        self.assertFalse(self.page.enlarge_button.isEnabled())

    def test_selecting_again_after_refresh_re_enables_the_button(self):
        self.page.list_widget.setCurrentRow(0)

        second_path = str(Path(self.tmp_dir) / "second_c.png")
        Path(second_path).write_bytes(b"fake-png-bytes-2")
        self.workspace_manager.add_images([second_path])
        self.assertFalse(self.page.enlarge_button.isEnabled())

        self.page.list_widget.setCurrentRow(0)
        self.assertTrue(self.page.enlarge_button.isEnabled())

    # --- Repeated consultation ---

    @patch("src.ui.pages.images_page.ImagePreviewDialog")
    def test_enlarge_button_opened_twice_in_a_row_opens_dialog_each_time(self, mock_dialog_cls):
        self.page.list_widget.setCurrentRow(0)

        self.page.enlarge_button.click()
        self.page.enlarge_button.click()

        self.assertEqual(mock_dialog_cls.call_count, 2)
        mock_dialog_cls.assert_called_with(self.image_path, parent=self.page)
        self.assertEqual(mock_dialog_cls.return_value.exec.call_count, 2)
        self.assertEqual(len(self.workspace_manager.current_workspace.images), 1)

    @patch("src.ui.pages.images_page.ImagePreviewDialog")
    def test_consultation_never_calls_add_images_or_save(self, mock_dialog_cls):
        with patch.object(
            self.workspace_manager, "add_images", wraps=self.workspace_manager.add_images
        ) as add_images_spy, patch.object(
            self.workspace_manager, "save", wraps=self.workspace_manager.save
        ) as save_spy:
            self.page.list_widget.setCurrentRow(0)
            self.page.enlarge_button.click()

            item = self.page.list_widget.item(0)
            self.page._on_item_double_clicked(item)

            add_images_spy.assert_not_called()
            save_spy.assert_not_called()

        self.assertEqual(len(self.workspace_manager.current_workspace.images), 1)

    # --- Mission 019: icon-mode gallery ---

    def test_list_widget_uses_icon_mode(self):
        self.assertEqual(self.page.list_widget.viewMode(), QListWidget.IconMode)

    def test_valid_image_item_has_icon_short_label_tooltip_and_user_role(self):
        real_image_path = str(Path(self.tmp_dir) / "real.png")
        _make_png(real_image_path)

        self.workspace_manager.add_images([real_image_path])

        item = self.page.list_widget.item(self.page.list_widget.count() - 1)

        self.assertFalse(item.icon().isNull())
        self.assertEqual(item.text(), "real.png")
        self.assertEqual(item.toolTip(), real_image_path)
        self.assertEqual(item.data(Qt.UserRole), real_image_path)

    def test_missing_file_item_still_created_with_fallback_icon_and_user_role(self):
        missing_path = str(Path(self.tmp_dir) / "does_not_exist.png")

        self.workspace_manager.add_images([missing_path])

        item = self.page.list_widget.item(self.page.list_widget.count() - 1)

        self.assertIsNotNone(item)
        self.assertFalse(item.icon().isNull())
        self.assertEqual(item.text(), "does_not_exist.png")
        self.assertEqual(item.toolTip(), missing_path)
        self.assertEqual(item.data(Qt.UserRole), missing_path)

    def test_invalid_non_image_file_item_still_created_with_fallback_icon(self):
        invalid_path = str(Path(self.tmp_dir) / "invalid.png")
        Path(invalid_path).write_bytes(b"this is definitely not a png")

        self.workspace_manager.add_images([invalid_path])

        item = self.page.list_widget.item(self.page.list_widget.count() - 1)

        self.assertIsNotNone(item)
        self.assertFalse(item.icon().isNull())
        self.assertEqual(item.data(Qt.UserRole), invalid_path)

    def test_missing_file_gallery_item_still_opens_preview_and_supports_selection(self):
        missing_path = str(Path(self.tmp_dir) / "gone.png")
        self.workspace_manager.add_images([missing_path])

        last_row = self.page.list_widget.count() - 1
        self.page.list_widget.setCurrentRow(last_row)

        self.assertTrue(self.page.enlarge_button.isEnabled())

        with patch("src.ui.pages.images_page.ImagePreviewDialog") as mock_dialog_cls:
            self.page.enlarge_button.click()
            mock_dialog_cls.assert_called_once_with(missing_path, parent=self.page)

    def test_multiple_images_each_item_has_its_own_user_role(self):
        second_path = str(Path(self.tmp_dir) / "multi_second.png")
        third_path = str(Path(self.tmp_dir) / "multi_third.png")
        _make_png(second_path)
        _make_png(third_path)

        self.workspace_manager.add_images([second_path, third_path])

        roles = {
            self.page.list_widget.item(i).data(Qt.UserRole)
            for i in range(self.page.list_widget.count())
        }

        self.assertEqual(roles, {self.image_path, second_path, third_path})


if __name__ == "__main__":
    unittest.main()
