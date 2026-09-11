"""
Mission 114: polls a transient ComfyUIEngine's check_connection() off
the Qt main thread until ComfyUI's HTTP API actually answers, a bounded
total budget elapses, or the owning ComfyUILifecycleManager cancels it.
Same QObject-with-run()-moved-to-a-QThread idiom already established by
GenerationWorker (Mission 013) for a single blocking call -- reused here
for a repeating one so no polling ever blocks the UI thread. This is not
a generic polling framework: the loop, its three terminal signals, and
the cancellation mechanism are the whole of this class.

Cancellation uses threading.Event rather than a plain bool: cancel() is
always called from the Qt main thread while run() executes on this
worker's own thread, and Event.wait()/.set()/.is_set() are the
thread-safe primitives for exactly that handoff -- wait() also lets a
cancel interrupt the between-attempts sleep immediately instead of
waiting out the full poll interval.
"""
import time
from threading import Event

from PySide6.QtCore import QObject, Signal

from src.engines.comfyui_engine import ComfyUIEngineError


class ComfyUIReadinessWorker(QObject):

    # Exactly one of these three fires per run(), always exactly once.
    ready = Signal()
    timed_out = Signal()
    cancelled = Signal()

    def __init__(
        self,
        comfyui_engine,
        budget_seconds: float,
        poll_interval_seconds: float,
        attempt_timeout_seconds: float,
    ):
        super().__init__()
        self._comfyui_engine = comfyui_engine
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
                self._comfyui_engine.check_connection(timeout=self._attempt_timeout_seconds)
            except ComfyUIEngineError:
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
