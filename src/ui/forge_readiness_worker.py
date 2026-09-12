"""
Mission 119: polls a transient ForgeEngine's check_connection() off the
Qt main thread until Forge's HTTP API actually answers, a bounded total
budget elapses, or the owning ForgeLifecycleManager cancels it. Same
QObject-with-run()-moved-to-a-QThread idiom already established by
ComfyUIReadinessWorker (Mission 114) -- reused here unchanged since the
polling concept itself does not depend on how Forge was launched, only
on which engine/exception type it polls against.
"""
import time
from threading import Event

from PySide6.QtCore import QObject, Signal

from src.engines.forge_engine import ForgeEngineError


class ForgeReadinessWorker(QObject):

    # Exactly one of these three fires per run(), always exactly once.
    ready = Signal()
    timed_out = Signal()
    cancelled = Signal()

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
            except ForgeEngineError:
                pass
            else:
                self.ready.emit()
                return

            if time.monotonic() >= deadline:
                self.timed_out.emit()
                return

            if self._cancel_event.wait(self._poll_interval_seconds):
                self.cancelled.emit()
                return
