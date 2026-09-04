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

The mechanism that works regardless of who constructed the dialog is a
QApplication-wide watcher that reacts to any real QMessageBox actually
becoming visible. QDialog.exec() calls show() before it creates and
assigns its internal QEventLoop, so closing the dialog synchronously
from a QEvent.Show filter would just hide it while the (not-yet-armed)
event loop still starts and blocks forever right after — an invisible
hang, worse than the original bug. The close is therefore deferred by
one event-loop tick (QTimer.singleShot(0, ...)), which reliably lands
once that internal event loop is already running.

Mission 097 crash investigation (see docs/missions/MISSION_097.md): an
earlier version of this module additionally backed the eventFilter with
an unconditional, repeating 15ms scan timer that iterated
QApplication.topLevelWidgets() looking for any QMessageBox. Rigorous
differential isolation (baseline vs Training-page-widget-count
variants, prefix-suite reproduction, then this periodic scan disabled
vs enabled) demonstrated that this periodic scan — not the eventFilter,
not TrainingPage's own widgets — correlated with a native
STATUS_HEAP_CORRUPTION crash during full-suite runs once enough
concurrent Qt object construction/destruction pressure was present
elsewhere in the application (the scan was once caught crashing inside
its own frame, mid-scan, during a real MainWindow close/generation
sequence). The eventFilter + deferred singleShot alone proved
sufficient across 3/3 consecutive full-suite runs with the periodic
scan removed — this module keeps only that mechanism.
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

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Show and isinstance(watched, QMessageBox):
            # Deferred on purpose — see module docstring: closing
            # synchronously here races QDialog.exec()'s internal event
            # loop, which is not yet assigned at Show-event time.
            QTimer.singleShot(0, lambda box=watched: self._close_if_visible(box))
        return False

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

    def stop(self):
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
