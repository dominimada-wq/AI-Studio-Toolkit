"""
Mission 091: shared safety net against unexpected, unmocked real
QMessageBox dialogs blocking a test run.

Verified empirically (this mission's own mini-audit demonstration) that
patching QMessageBox.exec at the Python class level does NOT intercept
QMessageBox.warning()/.critical()/.information()/.question(): those are
Shiboken wrappers around Qt's native C++ static functions, which
construct their own C++-native QMessageBox and call .exec() on it via a
direct C++ vtable call, never through Python attribute lookup — so a
Python-level monkeypatch of QMessageBox.exec has no effect on them.

The only mechanism that works uniformly regardless of who constructed
the dialog is a QApplication-wide watcher that reacts to any real
QMessageBox actually becoming visible. QDialog.exec() calls show()
before it creates and assigns its internal QEventLoop, so closing the
dialog synchronously from a QEvent.Show filter would just hide it while
the (not-yet-armed) event loop still starts and blocks forever right
after — an invisible hang, worse than the original bug. The close is
therefore deferred by one event-loop tick (QTimer.singleShot(0, ...)),
which reliably lands once that internal event loop is already running.
A fast repeating scan timer backs this up unconditionally, so a dialog
can never be left waiting for a human click even if the show-event path
is ever missed.
"""

import contextlib

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox


class UnexpectedDialogError(AssertionError):
    """A real QMessageBox appeared during a test and was never mocked."""


def _describe(box):
    try:
        title = box.windowTitle()
    except Exception:
        title = "<unavailable>"
    try:
        text = box.text()
    except Exception:
        text = "<unavailable>"
    try:
        buttons = [button.text() for button in box.buttons()]
    except Exception:
        buttons = []
    return title, text, buttons


class _DialogGuard(QObject):

    def __init__(self):
        super().__init__()
        self.captured = []
        self._closed_ids = set()
        self._app = QApplication.instance()
        self._timer = QTimer(self)
        self._timer.setInterval(15)
        self._timer.timeout.connect(self._scan)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Show and isinstance(watched, QMessageBox):
            # Deferred on purpose — see module docstring: closing
            # synchronously here races QDialog.exec()'s internal event
            # loop, which is not yet assigned at Show-event time.
            QTimer.singleShot(0, lambda box=watched: self._close_if_visible(box))
        return False

    def _scan(self):
        for widget in self._app.topLevelWidgets():
            if isinstance(widget, QMessageBox):
                self._close_if_visible(widget)

    def _close_if_visible(self, box):
        if not box.isVisible() or id(box) in self._closed_ids:
            return
        self._closed_ids.add(id(box))
        self.captured.append(_describe(box))
        try:
            box.done(int(QMessageBox.StandardButton.Cancel))
        except Exception:
            pass
        box.hide()

    def start(self):
        self._app.installEventFilter(self)
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self._app.removeEventFilter(self)
        if self.captured:
            captured, self.captured = self.captured, []
            details = "; ".join(
                f"title={title!r} text={text!r} buttons={buttons!r}"
                for title, text, buttons in captured
            )
            raise UnexpectedDialogError(
                f"{len(captured)} unexpected real QMessageBox dialog(s) "
                f"appeared during this test and would have blocked "
                f"waiting for a human click: {details}"
            )


@contextlib.contextmanager
def guard_against_unexpected_dialogs():
    guard = _DialogGuard()
    guard.start()
    try:
        yield guard
    finally:
        guard.stop()


def start_dialog_guard():
    guard = _DialogGuard()
    guard.start()
    return guard


def stop_dialog_guard(guard):
    guard.stop()
