"""
Real-widget coverage for SelectImagesDialog (Mission 044): a pure
presentation-layer picker over an already-resolved list of image
paths — no Manager, no filesystem I/O, no Dataset/Workspace
reference. DatasetsPage.add_images_from_gallery() is responsible for
resolving those paths (Workspace.images) and applying the result via
DatasetManager.add_images(), unchanged.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QListWidget

from src.ui.dialogs.select_images_dialog import SelectImagesDialog

_app = QApplication.instance() or QApplication([])


def _make_png(path: str, width: int = 4, height: int = 4) -> None:
    pixmap = QPixmap(width, height)
    pixmap.fill()
    assert pixmap.save(path, "PNG")


class SelectImagesDialogTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        self.path_a = str(Path(self.tmp_dir) / "a.png")
        self.path_b = str(Path(self.tmp_dir) / "b.png")
        self.path_c = str(Path(self.tmp_dir) / "c.png")
        _make_png(self.path_a)
        _make_png(self.path_b)
        _make_png(self.path_c)

    def _make_dialog(self, paths):
        dialog = SelectImagesDialog(paths)
        self.addCleanup(dialog.close)
        return dialog

    def test_uses_icon_mode_gallery(self):
        dialog = self._make_dialog([self.path_a])

        self.assertEqual(dialog.list_widget.viewMode(), QListWidget.IconMode)

    def test_allows_multiple_selection(self):
        dialog = self._make_dialog([self.path_a])

        self.assertEqual(dialog.list_widget.selectionMode(), QListWidget.ExtendedSelection)

    def test_each_item_has_icon_short_label_tooltip_and_user_role(self):
        dialog = self._make_dialog([self.path_a, self.path_b])

        item = dialog.list_widget.item(0)
        self.assertFalse(item.icon().isNull())
        self.assertEqual(item.text(), "a.png")
        self.assertEqual(item.toolTip(), self.path_a)
        self.assertEqual(item.data(Qt.UserRole), self.path_a)

    def test_no_selection_returns_empty_list(self):
        dialog = self._make_dialog([self.path_a, self.path_b])

        self.assertEqual(dialog.selected_paths(), [])

    def test_selecting_one_item_returns_its_path(self):
        dialog = self._make_dialog([self.path_a, self.path_b])

        dialog.list_widget.item(0).setSelected(True)

        self.assertEqual(dialog.selected_paths(), [self.path_a])

    def test_selecting_multiple_items_returns_all_their_paths(self):
        dialog = self._make_dialog([self.path_a, self.path_b, self.path_c])

        dialog.list_widget.item(0).setSelected(True)
        dialog.list_widget.item(2).setSelected(True)

        self.assertEqual(set(dialog.selected_paths()), {self.path_a, self.path_c})

    def test_empty_path_list_produces_an_empty_gallery(self):
        dialog = self._make_dialog([])

        self.assertEqual(dialog.list_widget.count(), 0)
        self.assertEqual(dialog.selected_paths(), [])


if __name__ == "__main__":
    unittest.main()
