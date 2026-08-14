"""
Real-widget coverage for Mission 015's ImagePreviewDialog: a strictly
passive image viewer shared between ImagesPage and InferencePage's
pending preview. exec() is never called here (it would block the test
process, same lesson learned with real QMessageBox modals in Mission
014) — show()/processEvents()/close() is enough to validate the
component itself in isolation.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.ui.dialogs.image_preview_dialog import ImagePreviewDialog, UNAVAILABLE_MESSAGE

_app = QApplication.instance() or QApplication([])


def _make_png(path: str, width: int, height: int) -> None:
    pixmap = QPixmap(width, height)
    pixmap.fill()
    assert pixmap.save(path, "PNG")


class ImagePreviewDialogTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def _show_and_pump(self, dialog):
        dialog.show()
        QApplication.processEvents()

    def test_valid_image_is_loaded_and_displayed(self):
        path = str(Path(self.tmp_dir) / "valid.png")
        _make_png(path, 400, 200)

        dialog = ImagePreviewDialog(path)
        try:
            self._show_and_pump(dialog)

            self.assertIsNotNone(dialog._source_pixmap)
            self.assertFalse(dialog.image_label.pixmap().isNull())
            self.assertEqual(dialog.image_label.text(), "")
        finally:
            dialog.close()

    def test_missing_file_shows_clear_message_without_crashing(self):
        missing_path = str(Path(self.tmp_dir) / "does_not_exist.png")

        dialog = ImagePreviewDialog(missing_path)
        try:
            self._show_and_pump(dialog)

            self.assertIsNone(dialog._source_pixmap)
            self.assertEqual(dialog.image_label.text(), UNAVAILABLE_MESSAGE)
            self.assertTrue(
                dialog.image_label.pixmap() is None or dialog.image_label.pixmap().isNull()
            )
        finally:
            dialog.close()

    def test_invalid_unreadable_file_shows_clear_message_without_crashing(self):
        invalid_path = str(Path(self.tmp_dir) / "not_an_image.png")
        Path(invalid_path).write_bytes(b"this is definitely not a png")

        dialog = ImagePreviewDialog(invalid_path)
        try:
            self._show_and_pump(dialog)

            self.assertIsNone(dialog._source_pixmap)
            self.assertEqual(dialog.image_label.text(), UNAVAILABLE_MESSAGE)
        finally:
            dialog.close()

    def test_resize_rescales_pixmap_preserving_aspect_ratio(self):
        path = str(Path(self.tmp_dir) / "wide.png")
        _make_png(path, 400, 200)  # 2:1 ratio

        dialog = ImagePreviewDialog(path)
        try:
            self._show_and_pump(dialog)

            dialog.resize(900, 700)
            QApplication.processEvents()

            scaled = dialog.image_label.pixmap()
            self.assertFalse(scaled.isNull())

            observed_ratio = scaled.width() / scaled.height()
            self.assertAlmostEqual(observed_ratio, 2.0, delta=0.1)

            # Never larger than the label it's displayed in.
            self.assertLessEqual(scaled.width(), dialog.image_label.width())
            self.assertLessEqual(scaled.height(), dialog.image_label.height())
        finally:
            dialog.close()

    def test_portrait_image_preserves_aspect_ratio(self):
        path = str(Path(self.tmp_dir) / "tall.png")
        _make_png(path, 200, 400)  # 1:2 ratio

        dialog = ImagePreviewDialog(path)
        try:
            self._show_and_pump(dialog)

            dialog.resize(900, 700)
            QApplication.processEvents()

            scaled = dialog.image_label.pixmap()
            self.assertFalse(scaled.isNull())

            observed_ratio = scaled.width() / scaled.height()
            self.assertAlmostEqual(observed_ratio, 0.5, delta=0.05)
            self.assertLessEqual(scaled.width(), dialog.image_label.width())
            self.assertLessEqual(scaled.height(), dialog.image_label.height())
        finally:
            dialog.close()

    def test_window_can_shrink_back_after_displaying_a_large_scaled_image(self):
        # Regression test: QLabel.minimumSizeHint() locks onto the last
        # pixmap it was given via setPixmap() unless an explicit
        # minimum size decouples it — without that, the dialog would
        # get stuck unable to shrink below whatever size it last
        # rendered the image at.
        path = str(Path(self.tmp_dir) / "shrink.png")
        _make_png(path, 400, 200)

        dialog = ImagePreviewDialog(path)
        try:
            self._show_and_pump(dialog)  # renders at the large default size first
            self.assertGreater(dialog.width(), 500)

            dialog.resize(150, 150)
            QApplication.processEvents()

            self.assertLessEqual(dialog.width(), 250)
            self.assertLessEqual(dialog.height(), 250)
        finally:
            dialog.close()

    def test_very_small_window_does_not_crash(self):
        path = str(Path(self.tmp_dir) / "tiny_window.png")
        _make_png(path, 400, 200)

        dialog = ImagePreviewDialog(path)
        try:
            self._show_and_pump(dialog)

            dialog.resize(1, 1)
            QApplication.processEvents()  # must not raise
        finally:
            dialog.close()

    def test_dialog_can_be_opened_and_closed_multiple_times_without_residual_state(self):
        path = str(Path(self.tmp_dir) / "repeat.png")
        _make_png(path, 120, 90)

        for _ in range(3):
            dialog = ImagePreviewDialog(path)
            self._show_and_pump(dialog)
            self.assertFalse(dialog.image_label.pixmap().isNull())
            dialog.close()
            self.assertFalse(dialog.isVisible())

    def test_f11_key_toggles_fullscreen_twice_and_returns_to_normal(self):
        path = str(Path(self.tmp_dir) / "f11.png")
        _make_png(path, 80, 80)

        dialog = ImagePreviewDialog(path)
        try:
            self._show_and_pump(dialog)
            dialog.activateWindow()
            QApplication.processEvents()
            self.assertFalse(dialog.isFullScreen())

            QTest.keyClick(dialog, Qt.Key_F11)
            QApplication.processEvents()
            self.assertTrue(dialog.isFullScreen())

            QTest.keyClick(dialog, Qt.Key_F11)
            QApplication.processEvents()
            self.assertFalse(dialog.isFullScreen())
        finally:
            dialog.close()

    def test_button_and_f11_invoke_the_same_toggle_method(self):
        # Both the button and the F11 shortcut are wired to the exact
        # same bound method — not two independently maintained code
        # paths that could diverge in behavior.
        path = str(Path(self.tmp_dir) / "same_mechanism.png")
        _make_png(path, 80, 80)

        dialog = ImagePreviewDialog(path)
        try:
            self._show_and_pump(dialog)

            with patch.object(dialog, "_toggle_fullscreen") as mock_toggle:
                dialog.fullscreen_button.click()
                self.assertEqual(mock_toggle.call_count, 1)

                dialog._fullscreen_shortcut.activated.emit()
                self.assertEqual(mock_toggle.call_count, 2)
        finally:
            dialog.close()

    def test_closing_while_fullscreen_requires_no_special_restoration(self):
        path = str(Path(self.tmp_dir) / "fullscreen_close.png")
        _make_png(path, 80, 80)

        dialog = ImagePreviewDialog(path)
        try:
            self._show_and_pump(dialog)
            dialog.showFullScreen()
            QApplication.processEvents()
            self.assertTrue(dialog.isFullScreen())

            dialog.close()  # must not raise, no showNormal() needed first

            self.assertFalse(dialog.isVisible())
        finally:
            if dialog.isVisible():
                dialog.close()

    def test_fullscreen_toggle_uses_show_fullscreen_and_show_normal(self):
        path = str(Path(self.tmp_dir) / "valid2.png")
        _make_png(path, 100, 100)

        dialog = ImagePreviewDialog(path)
        try:
            self._show_and_pump(dialog)
            self.assertFalse(dialog.isFullScreen())

            dialog.fullscreen_button.click()
            QApplication.processEvents()
            self.assertTrue(dialog.isFullScreen())

            dialog.fullscreen_button.click()
            QApplication.processEvents()
            self.assertFalse(dialog.isFullScreen())
        finally:
            dialog.close()

    def test_dialog_closes_cleanly(self):
        path = str(Path(self.tmp_dir) / "valid3.png")
        _make_png(path, 50, 50)

        dialog = ImagePreviewDialog(path)
        self._show_and_pump(dialog)

        dialog.close()

        self.assertFalse(dialog.isVisible())


if __name__ == "__main__":
    unittest.main()
