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
    _DialogGuard,
    _HANG_DETECTION_CEILING_SECONDS,
    UnexpectedDialogError,
    assert_dialog_guard_intercepts_promptly,
    guard_against_unexpected_dialogs,
    start_dialog_guard,
    stop_dialog_guard,
)

_app = QApplication.instance() or QApplication([])


class QtDialogSafetyNetTest(unittest.TestCase):

    def test_unexpected_warning_dialog_is_caught_not_blocked(self):
        def trigger():
            with guard_against_unexpected_dialogs():
                QMessageBox.warning(None, "Test Title", "Test Text")

        exception = assert_dialog_guard_intercepts_promptly(self, trigger)
        self.assertIn("Test Title", str(exception))
        self.assertIn("Test Text", str(exception))

    def test_unexpected_critical_dialog_is_caught_not_blocked(self):
        def trigger():
            with guard_against_unexpected_dialogs():
                QMessageBox.critical(None, "Critical Title", "Critical Text")

        exception = assert_dialog_guard_intercepts_promptly(self, trigger)
        self.assertIn("Critical Title", str(exception))
        self.assertIn("Critical Text", str(exception))

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


class DialogGuardCeilingHelperTest(unittest.TestCase):
    """
    Mission 133: proves assert_dialog_guard_intercepts_promptly()'s
    ceiling is not vacuous — it must reject a round-trip deliberately
    slowed past _HANG_DETECTION_CEILING_SECONDS, and accept one
    comfortably below it. Both simulated delays are finite, small and
    fully deterministic (a plain time.sleep() inside the guard's own
    close step) — never an attempt to reproduce a real infinite hang,
    which this assertion could never detect in the first place (see
    _HANG_DETECTION_CEILING_SECONDS's own comment in
    _qt_dialog_safety_net.py).
    """

    def test_ceiling_rejects_a_bounded_round_trip_slower_than_the_ceiling(self):
        exaggerated_delay = _HANG_DETECTION_CEILING_SECONDS + 0.5
        original_close = _DialogGuard._close_if_visible

        def slow_close(self, box):
            time.sleep(exaggerated_delay)
            original_close(self, box)

        def trigger():
            with guard_against_unexpected_dialogs():
                QMessageBox.warning(None, "Slow Title", "Slow Text")

        with patch.object(_DialogGuard, "_close_if_visible", slow_close):
            with self.assertRaises(AssertionError) as ctx:
                assert_dialog_guard_intercepts_promptly(self, trigger)

        self.assertIn("last-resort dysfunction ceiling", str(ctx.exception))

    def test_ceiling_accepts_a_bounded_round_trip_faster_than_the_ceiling(self):
        mild_delay = 0.5
        self.assertLess(mild_delay, _HANG_DETECTION_CEILING_SECONDS)
        original_close = _DialogGuard._close_if_visible

        def mildly_slow_close(self, box):
            time.sleep(mild_delay)
            original_close(self, box)

        def trigger():
            with guard_against_unexpected_dialogs():
                QMessageBox.warning(None, "Mild Title", "Mild Text")

        with patch.object(_DialogGuard, "_close_if_visible", mildly_slow_close):
            exception = assert_dialog_guard_intercepts_promptly(self, trigger)

        self.assertIn("Mild Title", str(exception))


if __name__ == "__main__":
    unittest.main()
