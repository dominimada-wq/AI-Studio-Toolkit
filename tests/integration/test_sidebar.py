"""
Mission 033: Sidebar.select_page(name) — the reverse lookup of the
already-existing page_name(index), used by MainWindow to navigate to
InferencePage after a successful Prompts -> Inference transfer without
hardcoding a numeric row index.
"""

import unittest

from PySide6.QtWidgets import QApplication

from src.ui.sidebar import Sidebar

_app = QApplication.instance() or QApplication([])


class SidebarSelectPageTest(unittest.TestCase):

    def setUp(self):
        self.sidebar = Sidebar()

    def test_select_page_sets_current_row_to_matching_page(self):
        expected_index = next(
            index for index, (_, name) in enumerate(self.sidebar.pages) if name == "inference"
        )

        result = self.sidebar.select_page("inference")

        self.assertTrue(result)
        self.assertEqual(self.sidebar.currentRow(), expected_index)

    def test_select_page_works_for_first_page(self):
        self.sidebar.setCurrentRow(3)

        result = self.sidebar.select_page("dashboard")

        self.assertTrue(result)
        self.assertEqual(self.sidebar.currentRow(), 0)

    def test_select_page_unknown_name_returns_false_and_does_not_move(self):
        self.sidebar.setCurrentRow(2)

        result = self.sidebar.select_page("does-not-exist")

        self.assertFalse(result)
        self.assertEqual(self.sidebar.currentRow(), 2)


if __name__ == "__main__":
    unittest.main()
