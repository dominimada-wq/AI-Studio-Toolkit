"""
Mission 091: deliberate, voluntary demonstration that the shared safety
net (tests/integration/_qt_dialog_safety_net.py) actually does what it
claims — an unmocked real QMessageBox is intercepted before it renders,
never blocks, and turns into a clean, descriptive test failure instead
of a hung suite waiting for a human click.
"""

import time
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

from tests.integration._qt_dialog_safety_net import (
    UnexpectedDialogError,
    guard_against_unexpected_dialogs,
)

_app = QApplication.instance() or QApplication([])


class QtDialogSafetyNetTest(unittest.TestCase):

    def test_unexpected_warning_dialog_is_caught_not_blocked(self):
        started = time.monotonic()

        with self.assertRaises(UnexpectedDialogError) as ctx:
            with guard_against_unexpected_dialogs():
                QMessageBox.warning(None, "Test Title", "Test Text")

        elapsed = time.monotonic() - started
        self.assertLess(
            elapsed, 1.0,
            "the guarded dialog call took over a second — it may have "
            "actually rendered/blocked instead of being intercepted",
        )
        self.assertIn("Test Title", str(ctx.exception))
        self.assertIn("Test Text", str(ctx.exception))

    def test_unexpected_critical_dialog_is_caught_not_blocked(self):
        started = time.monotonic()

        with self.assertRaises(UnexpectedDialogError) as ctx:
            with guard_against_unexpected_dialogs():
                QMessageBox.critical(None, "Critical Title", "Critical Text")

        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 1.0)
        self.assertIn("Critical Title", str(ctx.exception))
        self.assertIn("Critical Text", str(ctx.exception))

    def test_no_dialog_means_no_error(self):
        with guard_against_unexpected_dialogs():
            pass

    def test_guard_cleans_up_timer_and_event_filter_after_use(self):
        with guard_against_unexpected_dialogs() as guard:
            self.assertTrue(guard._timer.isActive())

        self.assertFalse(guard._timer.isActive())

    def test_a_mocked_dialog_inside_the_guard_is_not_flagged(self):
        with guard_against_unexpected_dialogs():
            with patch("PySide6.QtWidgets.QMessageBox.warning"):
                QMessageBox.warning(None, "Mocked Title", "Mocked Text")


if __name__ == "__main__":
    unittest.main()
