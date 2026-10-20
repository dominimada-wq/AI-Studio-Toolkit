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
from PySide6.QtWidgets import QApplication, QDialog, QListWidget

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

    def test_default_window_title_and_info_text_match_dataset_contract(self):
        dialog = self._make_dialog([self.path_a])

        self.assertEqual(dialog.windowTitle(), "Ajouter depuis Images")

    def test_selection_mode_title_and_info_text_are_configurable(self):
        dialog = SelectImagesDialog(
            [self.path_a],
            selection_mode=QListWidget.SingleSelection,
            title="Choisir une image de référence",
            info_text="Sélectionnez une image de la galerie à utiliser comme référence :",
        )
        self.addCleanup(dialog.close)

        self.assertEqual(dialog.list_widget.selectionMode(), QListWidget.SingleSelection)
        self.assertEqual(dialog.windowTitle(), "Choisir une image de référence")

    def test_single_selection_mode_allows_only_one_item_selected_at_once(self):
        dialog = SelectImagesDialog(
            [self.path_a, self.path_b],
            selection_mode=QListWidget.SingleSelection,
        )
        self.addCleanup(dialog.close)

        dialog.list_widget.item(0).setSelected(True)
        dialog.list_widget.item(1).setSelected(True)

        self.assertEqual(len(dialog.selected_paths()), 1)


class SelectImagesDialogOrderTest(unittest.TestCase):
    """
    Mission 182: reversed_display only changes how the rows are presented;
    selected_paths() always follows the order of the list given to the
    dialog, whatever the presentation, the order of the clicks or the order
    selectedItems() returns. Nothing here asserts anything about the latter:
    every case selects rows itself, in an order it chooses.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        self.paths = []
        for name in ("a.png", "b.png", "c.png", "d.png"):
            path = str(Path(self.tmp_dir) / name)
            _make_png(path)
            self.paths.append(path)

    def _make_dialog(self, paths, **kwargs):
        dialog = SelectImagesDialog(paths, **kwargs)
        self.addCleanup(dialog.close)
        return dialog

    @staticmethod
    def _row_paths(dialog):
        return [
            dialog.list_widget.item(i).data(Qt.UserRole)
            for i in range(dialog.list_widget.count())
        ]

    @staticmethod
    def _select_in_order(dialog, paths):
        # Selects the rows of the given paths one after the other, in the
        # order given, whatever the order of the rows is.
        for path in paths:
            for i in range(dialog.list_widget.count()):
                item = dialog.list_widget.item(i)
                if item.data(Qt.UserRole) == path:
                    item.setSelected(True)

    def test_default_presents_the_given_order(self):
        dialog = self._make_dialog(self.paths)

        self.assertEqual(self._row_paths(dialog), self.paths)

    def test_explicit_false_presents_the_given_order_like_the_default(self):
        dialog = self._make_dialog(self.paths, reversed_display=False)

        self.assertEqual(self._row_paths(dialog), self.paths)

    def test_reversed_display_presents_the_given_list_in_reverse(self):
        dialog = self._make_dialog(self.paths, reversed_display=True)

        self.assertEqual(self._row_paths(dialog), list(reversed(self.paths)))

    def test_reversed_display_keeps_text_tooltip_icon_and_path_of_every_row(self):
        dialog = self._make_dialog(self.paths, reversed_display=True)

        for i in range(dialog.list_widget.count()):
            item = dialog.list_widget.item(i)
            path = item.data(Qt.UserRole)
            self.assertEqual(item.text(), Path(path).name)
            self.assertEqual(item.toolTip(), path)
            self.assertFalse(item.icon().isNull())
        self.assertEqual(sorted(self._row_paths(dialog)), sorted(self.paths))

    def test_the_given_list_is_not_modified_for_both_values(self):
        for reversed_display in (False, True):
            given = list(self.paths)
            dialog = self._make_dialog(given, reversed_display=reversed_display)
            self._select_in_order(dialog, [self.paths[3], self.paths[0]])

            dialog.selected_paths()

            self.assertEqual(given, self.paths)

    def test_selected_paths_follow_the_given_order_whatever_the_order_of_the_selection(self):
        a, b, c, d = self.paths
        # (paths selected, in this order) -> expected result, in the given order
        cases = [
            ([a], [a]),
            ([b, c], [b, c]),
            ([d, b], [b, d]),
            ([c, a, b], [a, b, c]),
            ([d, c, b, a], [a, b, c, d]),
        ]

        for reversed_display in (False, True):
            for selected, expected in cases:
                dialog = self._make_dialog(self.paths, reversed_display=reversed_display)
                self._select_in_order(dialog, selected)

                self.assertEqual(
                    dialog.selected_paths(),
                    expected,
                    f"reversed_display={reversed_display}, selected={selected}",
                )

    def test_the_given_order_is_followed_even_when_it_is_not_the_alphabetical_one(self):
        a, b, c, d = self.paths
        given = [c, a, d, b]

        for reversed_display in (False, True):
            dialog = self._make_dialog(given, reversed_display=reversed_display)
            self._select_in_order(dialog, [b, c, d])

            self.assertEqual(dialog.selected_paths(), [c, d, b])

    def test_single_selection_mode_returns_the_chosen_path_for_both_values(self):
        for reversed_display in (False, True):
            dialog = self._make_dialog(
                self.paths,
                selection_mode=QListWidget.SingleSelection,
                reversed_display=reversed_display,
            )
            self._select_in_order(dialog, [self.paths[2]])

            self.assertEqual(dialog.selected_paths(), [self.paths[2]])

    def test_no_selection_and_empty_list_return_an_empty_list_for_both_values(self):
        for reversed_display in (False, True):
            dialog = self._make_dialog(self.paths, reversed_display=reversed_display)
            empty = self._make_dialog([], reversed_display=reversed_display)

            self.assertEqual(dialog.selected_paths(), [])
            self.assertEqual(empty.list_widget.count(), 0)
            self.assertEqual(empty.selected_paths(), [])

    def test_equal_paths_stay_separate_items_and_are_not_deduplicated(self):
        # Existing contract kept: the dialog never removes anything. Equal
        # paths are shown and returned as many times as they are selected;
        # removing duplicates stays the job of DatasetManager.add_images().
        a, b = self.paths[0], self.paths[1]
        given = [a, b, a]

        for reversed_display in (False, True):
            everything = self._make_dialog(given, reversed_display=reversed_display)
            self.assertEqual(everything.list_widget.count(), 3)
            for i in range(everything.list_widget.count()):
                everything.list_widget.item(i).setSelected(True)
            self.assertEqual(everything.selected_paths(), [a, b, a])

            one_row = self._make_dialog(given, reversed_display=reversed_display)
            one_row.list_widget.item(0).setSelected(True)
            self.assertEqual(one_row.selected_paths(), [a])

    def test_opening_selecting_and_reading_the_selection_write_nothing(self):
        def snapshot():
            return {p.name: p.read_bytes() for p in Path(self.tmp_dir).iterdir()}

        before = snapshot()
        for reversed_display in (False, True):
            dialog = self._make_dialog(self.paths, reversed_display=reversed_display)
            self._select_in_order(dialog, self.paths[:2])
            dialog.selected_paths()

        self.assertEqual(snapshot(), before)

    def test_rejecting_the_dialog_keeps_the_given_list_and_the_presentation(self):
        for reversed_display in (False, True):
            given = list(self.paths)
            dialog = self._make_dialog(given, reversed_display=reversed_display)
            rows_before = self._row_paths(dialog)
            self._select_in_order(dialog, [self.paths[1]])

            dialog.reject()

            self.assertNotEqual(dialog.result(), QDialog.Accepted)
            self.assertEqual(given, self.paths)
            self.assertEqual(self._row_paths(dialog), rows_before)


if __name__ == "__main__":
    unittest.main()
