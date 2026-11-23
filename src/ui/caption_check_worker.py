"""
CaptionCheckWorker runs the caption length check off the Qt main thread so the
interface stays responsive while OneTrainer's Python counts the tokens (the
helper process can take about half a minute on a cold start). It is the only
piece of this vertical that knows about threading: the engine module stays
Qt-free.

A plain daemon `threading.Thread` is used on purpose instead of a QThread: a
QThread destroyed while still running aborts the process, and the check must
never keep the application from closing. The result reaches the page through a
signal carrying the analysis serial number, delivered queued to the page's own
thread because the page is a QObject.

Lifetime and context safety:
- the worker is never parented to the page and is kept alive by a module-level
  registry until its thread has finished, so closing the page can never destroy
  an object the thread still uses;
- `cancel()` (called when the page is reset, abandons the analysis or is
  destroyed) kills the helper's whole process tree at once and guarantees that
  nothing is emitted afterwards, so a result can never be applied to another
  project or session;
- emitting towards a receiver that no longer exists is swallowed, never raised;
- no exception crosses the thread boundary: any failure becomes an
  "unverifiable" report, never a reassuring default.
"""

import threading

from PySide6.QtCore import QObject, Signal

from src.engines.caption_length_check import (
    HelperProcessRunner,
    check_caption_lengths,
    fingerprint_caption_inputs,
    unverifiable_report,
)

_LIVE_WORKERS = set()
_LIVE_LOCK = threading.Lock()


class CaptionCheckWorker(QObject):

    finished_with_report = Signal(int, object)  # (analysis serial, CaptionLengthReport)

    def __init__(self, onetrainer_path: str, inputs: dict, serial: int):
        super().__init__(None)
        self._onetrainer_path = onetrainer_path
        self.serial = serial
        # Copied defensively: nothing done to the page's own state afterwards
        # can reach this already launched analysis.
        self._inputs = {
            "training_id": inputs["training_id"],
            "training_name": inputs["training_name"],
            "architecture": inputs["architecture"],
            "dataset_id": inputs.get("dataset_id", ""),
            "items": [dict(item) for item in inputs["items"]],
        }
        self._runner = HelperProcessRunner()
        self._cancelled = threading.Event()
        self._thread = None

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def start(self) -> None:
        with _LIVE_LOCK:
            _LIVE_WORKERS.add(self)
        self._thread = threading.Thread(target=self._run, name="caption-length-check", daemon=True)
        self._thread.start()

    def cancel(self, *_ignored) -> None:
        """Stops the analysis now: kills the helper's process tree and suppresses any result."""
        self._cancelled.set()
        self._runner.cancel()

    def join(self, timeout=None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def _run(self) -> None:
        inputs = self._inputs
        try:
            try:
                report = check_caption_lengths(
                    onetrainer_path=self._onetrainer_path,
                    training_id=inputs["training_id"],
                    training_name=inputs["training_name"],
                    architecture=inputs["architecture"],
                    items=inputs["items"],
                    dataset_id=inputs["dataset_id"],
                    runner=self._runner,
                )
            except Exception as exc:  # noqa: BLE001 — last-resort safety net, never reassuring
                report = unverifiable_report(
                    inputs["training_id"], inputs["training_name"], inputs["architecture"],
                    fingerprint_caption_inputs(
                        inputs["training_id"], inputs["architecture"], inputs["items"],
                        inputs["dataset_id"], self._onetrainer_path,
                    ),
                    inputs["items"], f"unexpected failure: {type(exc).__name__}: {exc}",
                )
            if self._cancelled.is_set():
                return
            try:
                self.finished_with_report.emit(self.serial, report)
            except RuntimeError:
                pass   # the receiving side (or this object) no longer exists
        finally:
            with _LIVE_LOCK:
                _LIVE_WORKERS.discard(self)
