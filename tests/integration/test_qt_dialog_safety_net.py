"""
Mission 091: deliberate, voluntary demonstration that the shared safety
net (tests/integration/_qt_dialog_safety_net.py) actually does what it
claims — an unmocked real QMessageBox is intercepted before it renders,
never blocks, and turns into a clean, descriptive test failure instead
of a hung suite waiting for a human click.

Mission 097: the guard's contract changed — it no longer runs a
periodic scan timer (see _qt_dialog_safety_net.py's own docstring for
why), only the QEvent.Show eventFilter + deferred QTimer.singleShot(0,
...) close. These tests exercise that contract directly: no assertion
depends on an internal timer, and detection/closing is verified via
observable behavior only (no hang, UnexpectedDialogError raised,
eventFilter removed at teardown).
"""

import time
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

from tests.integration._qt_dialog_safety_net import (
    UnexpectedDialogError,
    guard_against_unexpected_dialogs,
    start_dialog_guard,
    stop_dialog_guard,
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

    def test_a_mocked_dialog_inside_the_guard_is_not_flagged(self):
        with guard_against_unexpected_dialogs():
            with patch("PySide6.QtWidgets.QMessageBox.warning"):
                QMessageBox.warning(None, "Mocked Title", "Mocked Text")

    def test_guard_removes_its_event_filter_after_use(self):
        # Mission 097: no _timer to assert on anymore — teardown is
        # verified by observable behavior instead: a dialog shown after
        # the guard has stopped must never reach its (removed) event
        # filter, so guard.captured stays empty.
        with guard_against_unexpected_dialogs() as guard:
            pass

        box = QMessageBox(None)
        box.setWindowTitle("After Teardown")
        box.setText("Should not be intercepted by the stopped guard")
        try:
            box.show()
            _app.processEvents()
            self.assertEqual(guard.captured, [])
        finally:
            box.hide()
            box.deleteLater()

    def test_start_stop_dialog_guard_pair_raises_on_a_real_dialog(self):
        # Mission 097: the raw start_dialog_guard()/stop_dialog_guard()
        # pair (used directly by setUp()/tearDown() in several test
        # files) must keep the exact same detection/raise contract as
        # the guard_against_unexpected_dialogs() context manager.
        guard = start_dialog_guard()
        QMessageBox.warning(None, "Paired Title", "Paired Text")

        with self.assertRaises(UnexpectedDialogError) as ctx:
            stop_dialog_guard(guard)

        self.assertIn("Paired Title", str(ctx.exception))

    def test_start_stop_dialog_guard_pair_is_silent_with_no_dialog(self):
        guard = start_dialog_guard()
        stop_dialog_guard(guard)


if __name__ == "__main__":
    unittest.main()
