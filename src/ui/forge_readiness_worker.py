"""
Mission 119: polls a transient ForgeEngine's check_connection() off the
Qt main thread until Forge's HTTP API actually answers, a bounded total
budget elapses, or the owning ForgeLifecycleManager cancels it. Same
QObject-with-run()-moved-to-a-QThread idiom already established by
ComfyUIReadinessWorker (Mission 114) -- reused here unchanged since the
polling concept itself does not depend on how Forge was launched, only
on which engine/exception type it polls against.
"""
import http.client
import logging
import time
from threading import Event

from PySide6.QtCore import QObject, Signal

from src.engines.forge_engine import ForgeEngineError

logger = logging.getLogger(__name__)

# Mission 170: the only transport-level errors a polling attempt tolerates
# besides the engine's own error -- a truncated or garbled response from a
# server Toolkit itself just launched and that may still be booting. The
# list is closed on purpose (never a bare http.client.HTTPException):
# CannotSendRequest and its family describe the HTTP client's own state
# machine, not an unavailable server, so retrying them until the budget
# ran out would hide a programming error behind a false "timeout".
_TRANSIENT_HTTP_ERRORS = (http.client.IncompleteRead, http.client.BadStatusLine)

_MAX_DETAIL_CHARS = 300


def describe_unexpected_exception(exc) -> str:
    """
    Mission 170: a short, user-presentable description of an ordinary
    exception -- "TypeName: message", truncated to _MAX_DETAIL_CHARS. Never
    raises for an ordinary exception: if str(exc) itself fails the type
    name alone is used, so formatting can never cost the terminal signal.
    Imported by the lifecycle manager of the same engine (pre-start check).
    """
    try:
        text = "%s: %s" % (type(exc).__name__, exc)
    except Exception:
        try:
            text = type(exc).__name__
        except Exception:
            text = "unexpected exception"
    if len(text) > _MAX_DETAIL_CHARS:
        text = text[: _MAX_DETAIL_CHARS - 3] + "..."
    return text


class ForgeReadinessWorker(QObject):

    # Exactly one of these four fires per run() for an ordinary exception
    # path, never more than one. failed (Mission 170) carries a short
    # diagnostic and is only emitted for an unexpected exception raised by
    # the connection check itself.
    ready = Signal()
    timed_out = Signal()
    cancelled = Signal()
    failed = Signal(str)

    def __init__(
        self,
        forge_engine,
        budget_seconds: float,
        poll_interval_seconds: float,
        attempt_timeout_seconds: float,
    ):
        super().__init__()
        self._forge_engine = forge_engine
        self._budget_seconds = budget_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._attempt_timeout_seconds = attempt_timeout_seconds
        self._cancel_event = Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        deadline = time.monotonic() + self._budget_seconds

        while True:
            if self._cancel_event.is_set():
                self.cancelled.emit()
                return

            try:
                self._forge_engine.check_connection(timeout=self._attempt_timeout_seconds)
            except (ForgeEngineError, *_TRANSIENT_HTTP_ERRORS):
                pass
            except Exception as exc:  # never BaseException
                # Mission 170: the diagnostic is computed first (it cannot
                # raise), then the cancellation flag is consulted ONCE, at this
                # point -- not at the instant the exception was raised. A
                # cancellation already requested by then wins; one requested
                # later is harmlessly ignored by the lifecycle manager (its
                # state has already left STARTING). This is not a general
                # priority of cancelled over the other outcomes.
                detail = describe_unexpected_exception(exc)
                if self._cancel_event.is_set():
                    self.cancelled.emit()
                else:
                    self.failed.emit(detail)
                # Logged after the terminal signal: logging is never a
                # condition of it, and the user-facing diagnostic travels in
                # the signal itself.
                logger.exception("Forge readiness check raised an unexpected exception")
                return
            else:
                self.ready.emit()
                return

            if time.monotonic() >= deadline:
                self.timed_out.emit()
                return

            if self._cancel_event.wait(self._poll_interval_seconds):
                self.cancelled.emit()
                return
