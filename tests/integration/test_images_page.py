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

Mission 028: WorkspaceManager.add_images() now physically copies each
source into <workspace_root>/images/ instead of merely referencing it
— every fixture below distinguishes the external source it hands to
add_images() from the internal copy path the app actually renders
(read back from Workspace.images after the call), since the two are
no longer the same string. Tests that specifically exercise a
file the widget cannot load (missing/invalid content) now write a
real-but-unloadable file rather than a genuinely non-existent path —
add_images() itself now requires the source to exist (Mission 028
copies it), so a source that was never on disk can no longer become a
persisted Image at all; a real file with unparsable bytes exercises
the exact same QPixmap-load-failure/fallback-icon path.
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

        # self.image_path is the external source handed to add_images();
        # self.internal_image_path is the internal copy the app actually
        # renders afterward (Mission 028) — the two are deliberately
        # different paths on disk.
        self.image_path = str(Path(self.tmp_dir) / "existing.png")
        Path(self.image_path).write_bytes(b"fake-png-bytes")
        self.workspace_manager.add_images([self.image_path])
        self.internal_image_path = self.workspace_manager.current_workspace.images[0].file_path

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

        mock_dialog_cls.assert_called_once_with(self.internal_image_path, parent=self.page)
        mock_dialog_cls.return_value.exec.assert_called_once()

    @patch("src.ui.pages.images_page.ImagePreviewDialog")
    def test_double_click_opens_the_same_file_path(self, mock_dialog_cls):
        item = self.page.list_widget.item(0)

        self.page._on_item_double_clicked(item)

        mock_dialog_cls.assert_called_once_with(self.internal_image_path, parent=self.page)
        mock_dialog_cls.return_value.exec.assert_called_once()

    @patch("src.ui.pages.images_page.ImagePreviewDialog")
    def test_enlarge_button_with_no_selection_is_a_no_op(self, mock_dialog_cls):
        self.page.enlarge_button.click()

        mock_dialog_cls.assert_not_called()

    # --- Missing file: dialog is still opened, no Domain mutation ---

    @patch("src.ui.pages.images_page.ImagePreviewDialog")
    def test_missing_file_opens_dialog_without_mutating_domain(self, mock_dialog_cls):
        # Deletes the internal copy (the file the app actually
        # references after import) — deleting self.image_path (the
        # external source) would no longer be relevant post-Mission-028,
        # since the app never depends on it again once copied.
        Path(self.internal_image_path).unlink()
        self.page.list_widget.setCurrentRow(0)

        self.page.enlarge_button.click()

        mock_dialog_cls.assert_called_once_with(self.internal_image_path, parent=self.page)
        self.assertEqual(len(self.workspace_manager.current_workspace.images), 1)
        self.assertEqual(
            self.workspace_manager.current_workspace.images[0].file_path,
            self.internal_image_path,
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
        mock_dialog_cls.assert_called_with(self.internal_image_path, parent=self.page)
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
        internal_real_path = self.workspace_manager.current_workspace.images[-1].file_path

        item = self.page.list_widget.item(self.page.list_widget.count() - 1)

        self.assertFalse(item.icon().isNull())
        self.assertEqual(item.text(), "real.png")
        self.assertEqual(item.toolTip(), internal_real_path)
        self.assertEqual(item.data(Qt.UserRole), internal_real_path)

    def test_missing_file_item_still_created_with_fallback_icon_and_user_role(self):
        # Mission 028: add_images() now requires the source to exist on
        # disk (it is physically copied) — a genuinely non-existent
        # source can no longer become a persisted Image at all. A real
        # file with unparsable content exercises the exact same
        # QPixmap-load-failure/fallback-icon path a missing file used
        # to, without contradicting the new copy contract.
        broken_source = str(Path(self.tmp_dir) / "does_not_exist.png")
        Path(broken_source).write_bytes(b"not a real png")

        self.workspace_manager.add_images([broken_source])
        internal_path = self.workspace_manager.current_workspace.images[-1].file_path

        item = self.page.list_widget.item(self.page.list_widget.count() - 1)

        self.assertIsNotNone(item)
        self.assertFalse(item.icon().isNull())
        self.assertEqual(item.text(), "does_not_exist.png")
        self.assertEqual(item.toolTip(), internal_path)
        self.assertEqual(item.data(Qt.UserRole), internal_path)

    def test_invalid_non_image_file_item_still_created_with_fallback_icon(self):
        invalid_path = str(Path(self.tmp_dir) / "invalid.png")
        Path(invalid_path).write_bytes(b"this is definitely not a png")

        self.workspace_manager.add_images([invalid_path])
        internal_path = self.workspace_manager.current_workspace.images[-1].file_path

        item = self.page.list_widget.item(self.page.list_widget.count() - 1)

        self.assertIsNotNone(item)
        self.assertFalse(item.icon().isNull())
        self.assertEqual(item.data(Qt.UserRole), internal_path)

    def test_missing_file_gallery_item_still_opens_preview_and_supports_selection(self):
        broken_source = str(Path(self.tmp_dir) / "gone.png")
        Path(broken_source).write_bytes(b"not a real png either")

        self.workspace_manager.add_images([broken_source])
        internal_path = self.workspace_manager.current_workspace.images[-1].file_path

        last_row = self.page.list_widget.count() - 1
        self.page.list_widget.setCurrentRow(last_row)

        self.assertTrue(self.page.enlarge_button.isEnabled())

        with patch("src.ui.pages.images_page.ImagePreviewDialog") as mock_dialog_cls:
            self.page.enlarge_button.click()
            mock_dialog_cls.assert_called_once_with(internal_path, parent=self.page)

    def test_multiple_images_each_item_has_its_own_user_role(self):
        second_path = str(Path(self.tmp_dir) / "multi_second.png")
        third_path = str(Path(self.tmp_dir) / "multi_third.png")
        _make_png(second_path)
        _make_png(third_path)

        self.workspace_manager.add_images([second_path, third_path])
        internal_paths = {
            image.file_path for image in self.workspace_manager.current_workspace.images
        }

        roles = {
            self.page.list_widget.item(i).data(Qt.UserRole)
            for i in range(self.page.list_widget.count())
        }

        self.assertEqual(roles, internal_paths)


class ImagesPageCollisionDialogTest(unittest.TestCase):
    """
    Mission 028 second smoke test: import_images() no longer lets a
    naming collision resolve silently — it must show
    ImportCollisionDialog exactly once per import operation (never
    once per colliding file) whenever
    WorkspaceManager.preview_collisions() finds anything, and never at
    all otherwise. ImportCollisionDialog.exec() is patched throughout
    — a real modal exec() would block the test process (same lesson as
    every other dialog in this project).
    """

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

        self.external_dir = Path(self.tmp_dir) / "External"
        self.external_dir.mkdir()

    def _external(self, name, content=b"fake-bytes"):
        path = self.external_dir / name
        path.write_bytes(content)
        return str(path)

    def _select(self, files):
        return patch(
            "src.ui.pages.images_page.QFileDialog.getOpenFileNames",
            return_value=(files, ""),
        )

    def test_no_dialog_shown_when_nothing_collides(self):
        with self._select([self._external("photo.png")]), \
                patch("src.ui.pages.images_page.ImportCollisionDialog") as dialog_cls, \
                patch("src.ui.pages.images_page.QMessageBox.information"):
            self.page.import_images()

            dialog_cls.assert_not_called()

        self.assertEqual(len(self.workspace_manager.current_workspace.images), 1)

    def test_dialog_shown_exactly_once_for_multiple_collisions(self):
        # Two independent collisions in the same batch must still
        # produce a single dialog, not one per colliding file.
        self.workspace_manager.add_images([self._external("a.png"), self._external("b.png")])
        colliding_a = self._external("a.png", b"different-a")
        colliding_b = self._external("b.png", b"different-b")

        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Rejected
        with self._select([colliding_a, colliding_b]), \
                patch(
                    "src.ui.pages.images_page.ImportCollisionDialog", return_value=dialog
                ) as dialog_cls:
            self.page.import_images()

            dialog_cls.assert_called_once()

    def test_cancelling_the_dialog_aborts_the_whole_import(self):
        self.workspace_manager.add_images([self._external("photo.png")])
        colliding_source = self._external("photo.png", b"different")

        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Rejected
        with self._select([colliding_source]), \
                patch("src.ui.pages.images_page.ImportCollisionDialog", return_value=dialog):
            self.page.import_images()

        self.assertEqual(len(self.workspace_manager.current_workspace.images), 1)

    def test_rename_decision_is_applied_verbatim(self):
        self.workspace_manager.add_images([self._external("photo.png")])
        colliding_source = self._external("photo.png", b"different")

        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Accepted
        dialog.decisions.return_value = {colliding_source: "my_custom_name.png"}
        with self._select([colliding_source]), \
                patch("src.ui.pages.images_page.ImportCollisionDialog", return_value=dialog), \
                patch("src.ui.pages.images_page.QMessageBox.information"):
            self.page.import_images()

        images = self.workspace_manager.current_workspace.images
        self.assertEqual(len(images), 2)
        self.assertEqual(
            images[-1].file_path, str(self.folder / "images" / "my_custom_name.png")
        )

    def test_skip_decision_never_imports_that_file(self):
        self.workspace_manager.add_images([self._external("photo.png")])
        colliding_source = self._external("photo.png", b"different")

        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Accepted
        dialog.decisions.return_value = {colliding_source: None}
        with self._select([colliding_source]), \
                patch("src.ui.pages.images_page.ImportCollisionDialog", return_value=dialog), \
                patch("src.ui.pages.images_page.QMessageBox.information") as info_mock:
            self.page.import_images()

        self.assertEqual(len(self.workspace_manager.current_workspace.images), 1)
        info_mock.assert_called_once()
        message = info_mock.call_args.args[2]
        self.assertIn("Aucune nouvelle image importée", message)

    def test_bypassing_the_ui_still_falls_back_to_the_silent_non_destructive_auto_suffix(self):
        # A caller that bypasses the UI entirely (tests, programmatic
        # use) still gets the original silent auto-suffix from
        # WorkspaceStorage.copy_into_workspace() itself — the
        # architect's explicit instruction was to keep this primitive,
        # only the UI-driven import flow now asks first.
        self.workspace_manager.add_images([self._external("photo.png")])
        self.workspace_manager.add_images([self._external("photo.png", b"other")])

        self.assertTrue((self.folder / "images" / "photo_1.png").exists())


if __name__ == "__main__":
    unittest.main()
