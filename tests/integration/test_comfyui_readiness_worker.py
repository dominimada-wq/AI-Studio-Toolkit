"""
Mission 170: ComfyUIReadinessWorker -- terminal-signal contract of run(),
verified on a real QThread driven by a real QEventLoop against a simulated
engine (never a real ComfyUI, never a server, never real network traffic).

Three families, kept apart on purpose:
- ComfyUIReadinessWorkerInvariantTest: historical behavior that must hold
  before and after Mission 170 (expected engine errors, success, timeout,
  cancellation, blocking attempts).
- ComfyUIReadinessWorkerRegressionTest: behavior-only proofs of the defect
  (an exception outside the engine's own error used to kill run() without any
  terminal signal and leave the QThread running). They read the signals only
  through getattr(), so they fail on the previous implementation by assertion,
  never by a missing symbol.
- ComfyUIReadinessWorkerContractTest: the new contract (failed, its
  diagnostic, truncation, logging, the cancellation crossing). Not a proof of
  the defect.

Cleanup contract (valid even when run() died silently): every worker/thread
pair is registered before it starts; the fake engine's controlled waits are
released, cancel() is requested, quit() is requested, and wait() is checked
with a bounded delay. A thread still active afterward is a cleanup failure,
is kept referenced (never destroyed while active) and is never terminate()d.
"""
import http.client
import logging
import threading
import time
import unittest

from PySide6.QtCore import QEventLoop, QObject, QThread, QTimer
from PySide6.QtWidgets import QApplication

from src.engines.comfyui_engine import ComfyUIEngineError
from src.ui import comfyui_readiness_worker as worker_module
from src.ui.comfyui_readiness_worker import ComfyUIReadinessWorker

_app = QApplication.instance() or QApplication([])

TERMINAL = ("ready", "timed_out", "cancelled", "failed")
WATCHDOG_SECONDS = 2.0
GRACE_SECONDS = 0.3

# Threads that could not be stopped by the cooperative cleanup: kept alive so a
# running QThread is never destroyed, never terminate()d.
_GRAVEYARD = []


def _ok():
    return ("ok",)


def _raise(exc):
    return ("raise", exc)


def _wait(seconds, then):
    return ("wait", seconds, then)


class _FakeEngine:
    """script: one action per call, the last one repeats. Controlled waits are releasable."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0
        self.release = threading.Event()
        self.hook = None
        self.first_call_at = None

    def check_connection(self, timeout=None):
        index = self.calls
        self.calls += 1
        if self.first_call_at is None:
            self.first_call_at = time.monotonic()
        if self.hook is not None:
            self.hook()
        action = self.script[min(index, len(self.script) - 1)]
        while action[0] == "wait":
            self.release.wait(action[1])
            action = action[2]
        if action[0] == "raise":
            raise action[1]
        return True


class _Collector(QObject):
    """Lives on the main thread, so every worker signal reaches it through a queued connection."""

    def __init__(self):
        super().__init__()
        self.events = []
        self.t0 = time.monotonic()
        self.thread_finished = False
        self.loop = None

    def _log(self, name, payload=None):
        self.events.append((round(time.monotonic() - self.t0, 3), name, payload))

    def on_ready(self):
        self._log("ready")

    def on_timed_out(self):
        self._log("timed_out")

    def on_cancelled(self):
        self._log("cancelled")

    def on_failed(self, detail):
        self._log("failed", detail)

    def on_thread_finished(self):
        self.thread_finished = True
        if self.loop is not None:
            QTimer.singleShot(int(GRACE_SECONDS * 1000), self.loop.quit)


class _Run:
    def __init__(self, test, script, budget=2.0, poll=0.02, attempt=0.05):
        self.engine = _FakeEngine(script)
        self.collector = _Collector()
        self.thread = QThread()
        self.worker = ComfyUIReadinessWorker(self.engine, budget, poll, attempt)
        self.worker.moveToThread(self.thread)
        test._runs.append(self)  # registered before anything can start
        self.watchdog_fired = False
        self.thread_finished_by_itself = False

        self.thread.started.connect(self.worker.run)
        self.worker.ready.connect(self.collector.on_ready)
        self.worker.timed_out.connect(self.collector.on_timed_out)
        self.worker.cancelled.connect(self.collector.on_cancelled)
        failed = getattr(self.worker, "failed", None)  # absent on the previous implementation
        if failed is not None:
            failed.connect(self.collector.on_failed)
        # Same wiring as the lifecycle managers: every terminal signal quits the thread.
        for signal in (self.worker.ready, self.worker.timed_out, self.worker.cancelled, failed):
            if signal is not None:
                signal.connect(self.thread.quit)
        self.thread.finished.connect(self.collector.on_thread_finished)

    def go(self, cancel_at=None, watchdog=WATCHDOG_SECONDS):
        loop = QEventLoop()
        self.collector.loop = loop
        timers = []

        watchdog_timer = QTimer()
        watchdog_timer.setSingleShot(True)

        def _expired():
            self.watchdog_fired = True
            loop.quit()

        watchdog_timer.timeout.connect(_expired)
        watchdog_timer.start(int(watchdog * 1000))
        timers.append(watchdog_timer)

        if cancel_at is not None:
            # cancel() runs on the main thread as a plain call, exactly as the lifecycle
            # managers do -- never QTimer.singleShot(ms, worker.cancel), which would queue
            # the call onto the (busy) worker thread. It is requested `cancel_at` seconds
            # after the FIRST attempt has started, never at a wall-clock offset from the
            # thread start: the worker thread's startup latency is not under the test's
            # control, and a cancellation seen before run() entered its loop would
            # legitimately change the outcome being tested.
            armed = {"at": None}
            cancel_timer = QTimer()

            def _maybe_cancel():
                now = time.monotonic()
                if armed["at"] is None and self.engine.calls >= 1:
                    armed["at"] = now
                if armed["at"] is not None and now - armed["at"] >= cancel_at:
                    cancel_timer.stop()
                    self.worker.cancel()

            cancel_timer.timeout.connect(_maybe_cancel)
            cancel_timer.start(5)
            timers.append(cancel_timer)

        self.thread.start()
        loop.exec()
        for timer in timers:
            timer.stop()
        self.thread_finished_by_itself = self.collector.thread_finished
        return self

    @property
    def terminal(self):
        return [name for _, name, _ in self.collector.events if name in TERMINAL]

    def event(self, name):
        for when, event_name, payload in self.collector.events:
            if event_name == name:
                return when, payload
        return None


class _ReadinessWorkerTestCase(unittest.TestCase):
    quiet_logs = True

    def setUp(self):
        self._runs = []
        self.addCleanup(self._release_everything)
        if self.quiet_logs:
            module_logger = logging.getLogger(worker_module.__name__)
            previous = module_logger.disabled
            module_logger.disabled = True
            self.addCleanup(setattr, module_logger, "disabled", previous)

    def _release_everything(self):
        stuck = []
        for run in self._runs:
            run.engine.release.set()  # frees any controlled wait
            run.worker.cancel()
            run.thread.quit()
            if not run.thread.wait(3000):
                _GRAVEYARD.append(run)  # never destroyed while active, never terminate()d
                stuck.append(run)
        if stuck:
            raise AssertionError("%d worker thread(s) still active after the cooperative cleanup" % len(stuck))

    def run_scenario(self, script, cancel_at=None, **kwargs):
        return _Run(self, script, **kwargs).go(cancel_at=cancel_at)

    def assert_single_terminal_and_thread_end(self, run):
        self.assertFalse(run.watchdog_fired, "no terminal signal before the watchdog: %r" % run.terminal)
        self.assertEqual(len(run.terminal), 1, "exactly one terminal signal expected, got %r" % run.terminal)
        self.assertTrue(run.thread_finished_by_itself, "the QThread must end by itself, before any forced cleanup")


class ComfyUIReadinessWorkerInvariantTest(_ReadinessWorkerTestCase):

    def test_expected_engine_errors_then_success_emit_exactly_one_ready(self):
        run = self.run_scenario([
            _raise(ComfyUIEngineError("not yet")), _raise(ComfyUIEngineError("not yet")), _ok(),
        ])

        self.assertEqual(run.terminal, ["ready"])
        self.assertEqual(run.engine.calls, 3)
        self.assertTrue(run.thread_finished_by_itself)

    def test_expected_engine_errors_until_the_budget_emit_exactly_one_timed_out(self):
        run = self.run_scenario([_raise(ComfyUIEngineError("never ready"))], budget=0.15)

        self.assertEqual(run.terminal, ["timed_out"])
        self.assertTrue(run.thread_finished_by_itself)

    def test_cancel_after_a_failed_attempt_emits_exactly_one_cancelled_quickly(self):
        run = self.run_scenario([_raise(ComfyUIEngineError("not yet"))], cancel_at=0.15, budget=5.0, poll=1.0)

        self.assertEqual(run.terminal, ["cancelled"])
        self.assertEqual(run.engine.calls, 1)
        elapsed = run.collector.t0 + run.event("cancelled")[0] - run.engine.first_call_at
        self.assertLess(elapsed, 0.6, "the interruptible wait must not sit out the 1s interval")
        self.assertTrue(run.thread_finished_by_itself)

    def test_cancel_during_a_blocking_attempt_that_then_succeeds_still_emits_ready(self):
        # Historical contract, deliberately unchanged: a success is never turned
        # into cancelled. The lifecycle manager ignores it once its state moved on.
        run = self.run_scenario([_wait(0.3, _ok())], cancel_at=0.05, budget=5.0)

        self.assertEqual(run.terminal, ["ready"])
        self.assertTrue(run.thread_finished_by_itself)

    def test_a_blocking_attempt_longer_than_the_budget_ends_with_timed_out_after_it(self):
        # The deadline is only checked between attempts: the total delay is the
        # budget plus the attempt in flight -- no promise about a call that never returns.
        run = self.run_scenario([_wait(0.3, _raise(ComfyUIEngineError("not yet")))], budget=0.1)

        self.assertEqual(run.terminal, ["timed_out"])
        self.assertGreaterEqual(run.event("timed_out")[0], 0.25)
        self.assertEqual(run.engine.calls, 1)

    def test_cancel_then_an_engine_error_after_the_deadline_is_timed_out_not_cancelled(self):
        # Historical order kept: the deadline check precedes the interruptible wait.
        run = self.run_scenario([_wait(0.3, _raise(ComfyUIEngineError("not yet")))], cancel_at=0.05, budget=0.1)

        self.assertEqual(run.terminal, ["timed_out"])

class ComfyUIReadinessWorkerRegressionTest(_ReadinessWorkerTestCase):
    """Behavior-only proofs of the defect: fail by assertion on the previous implementation."""

    def test_an_exception_outside_the_engine_error_yields_exactly_one_terminal_signal(self):
        cases = [
            ("AttributeError", AttributeError("'list' object has no attribute 'get'")),
            ("TypeError", TypeError("bad")),
            ("RuntimeError", RuntimeError("boom")),
            ("RecursionError", RecursionError("maximum recursion depth exceeded")),
            ("UnicodeDecodeError", UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")),
            ("raw OSError", OSError("not translated by the engine")),
        ]
        for label, exc in cases:
            with self.subTest(label):
                run = self.run_scenario([_raise(exc)])

                self.assert_single_terminal_and_thread_end(run)

    def test_an_unexpected_exception_after_an_expected_error_yields_exactly_one_terminal_signal(self):
        run = self.run_scenario([_raise(ComfyUIEngineError("not yet")), _raise(RuntimeError("boom"))])

        self.assert_single_terminal_and_thread_end(run)

    def test_cancel_then_an_unexpected_exception_yields_exactly_one_terminal_signal(self):
        run = self.run_scenario([_wait(0.3, _raise(RuntimeError("late boom")))], cancel_at=0.05, budget=5.0)

        self.assert_single_terminal_and_thread_end(run)

    def test_transient_http_errors_followed_by_success_emit_ready(self):
        cases = [
            ("IncompleteRead", http.client.IncompleteRead(b"ab", 10)),
            ("BadStatusLine", http.client.BadStatusLine("garbage")),
        ]
        for label, exc in cases:
            with self.subTest(label):
                run = self.run_scenario([_raise(ComfyUIEngineError("not yet")), _raise(exc), _ok()])

                self.assertFalse(run.watchdog_fired, "no terminal signal before the watchdog: %r" % run.terminal)
                self.assertEqual(run.terminal, ["ready"])
                self.assertEqual(run.engine.calls, 3)

    def test_transient_http_errors_until_the_budget_emit_timed_out(self):
        cases = [
            ("IncompleteRead", http.client.IncompleteRead(b"ab", 10)),
            ("BadStatusLine", http.client.BadStatusLine("garbage")),
        ]
        for label, exc in cases:
            with self.subTest(label):
                run = self.run_scenario([_raise(exc)], budget=0.15)

                self.assertFalse(run.watchdog_fired, "no terminal signal before the watchdog: %r" % run.terminal)
                self.assertEqual(run.terminal, ["timed_out"])

    def test_http_client_state_errors_are_not_retried_and_yield_one_terminal_signal(self):
        cases = [
            ("CannotSendRequest", http.client.CannotSendRequest("Request-sent")),
            ("ResponseNotReady", http.client.ResponseNotReady("Idle")),
            ("bare HTTPException", http.client.HTTPException("x")),
        ]
        for label, exc in cases:
            with self.subTest(label):
                run = self.run_scenario([_raise(exc)], budget=5.0)

                self.assert_single_terminal_and_thread_end(run)
                self.assertEqual(run.engine.calls, 1, "a client state error must not be retried until the budget")


class ComfyUIReadinessWorkerContractTest(_ReadinessWorkerTestCase):
    """The new contract (failed and its diagnostic). Not a proof of the defect."""

    quiet_logs = False

    def test_an_unexpected_exception_emits_failed_with_its_diagnostic_and_never_timed_out(self):
        with self.assertLogs(worker_module.logger, "ERROR"):
            run = self.run_scenario([_raise(AttributeError("'list' object has no attribute 'get'"))])

        self.assertEqual(run.terminal, ["failed"])
        self.assertEqual(run.event("failed")[1], "AttributeError: 'list' object has no attribute 'get'")
        self.assertTrue(run.thread_finished_by_itself)

    def test_http_client_state_errors_emit_failed(self):
        cases = [
            ("CannotSendRequest", http.client.CannotSendRequest("Request-sent")),
            ("ResponseNotReady", http.client.ResponseNotReady("Idle")),
            ("bare HTTPException", http.client.HTTPException("x")),
        ]
        for label, exc in cases:
            with self.subTest(label), self.assertLogs(worker_module.logger, "ERROR"):
                run = self.run_scenario([_raise(exc)], budget=5.0)

                self.assertEqual(run.terminal, ["failed"])
                self.assertTrue(run.event("failed")[1].startswith(type(exc).__name__ + ":"))

    def test_describe_unexpected_exception_is_short_and_never_raises(self):
        class _BadStr(Exception):
            def __str__(self):
                raise RuntimeError("str() failed")

        self.assertEqual(worker_module.describe_unexpected_exception(RuntimeError("boom")), "RuntimeError: boom")
        self.assertEqual(worker_module.describe_unexpected_exception(_BadStr()), "_BadStr")

    def test_the_diagnostic_is_truncated_to_300_characters(self):
        with self.assertLogs(worker_module.logger, "ERROR"):
            run = self.run_scenario([_raise(RuntimeError("x" * 1000))])

        detail = run.event("failed")[1]
        self.assertEqual(len(detail), 300)
        self.assertTrue(detail.startswith("RuntimeError: xxx"))
        self.assertTrue(detail.endswith("..."))

    def test_an_exception_whose_str_fails_still_emits_failed_with_its_type_name(self):
        class _BadStr(Exception):
            def __str__(self):
                raise RuntimeError("str() failed")

        with self.assertLogs(worker_module.logger, "ERROR"):
            run = self.run_scenario([_raise(_BadStr())])

        self.assertEqual(run.terminal, ["failed"])
        self.assertEqual(run.event("failed")[1], "_BadStr")

    def test_a_cancellation_already_requested_when_the_exception_is_handled_emits_cancelled(self):
        # Decided when the cancellation flag is consulted (after the diagnostic is
        # formatted), not at the instant the exception was raised -- and only for
        # this new path. No universal priority of cancelled is claimed.
        run = _Run(self, [_raise(RuntimeError("boom"))])
        run.engine.hook = lambda: run.worker.cancel()  # set before the exception is handled
        with self.assertLogs(worker_module.logger, "ERROR"):
            run.go()

        self.assertEqual(run.terminal, ["cancelled"])
        self.assertTrue(run.thread_finished_by_itself)

    def test_without_a_cancellation_the_same_exception_emits_failed(self):
        with self.assertLogs(worker_module.logger, "ERROR"):
            run = self.run_scenario([_raise(RuntimeError("boom"))])

        self.assertEqual(run.terminal, ["failed"])

    def test_an_unexpected_exception_is_logged_exactly_once_after_the_signal(self):
        with self.assertLogs(worker_module.logger, "ERROR") as captured:
            run = self.run_scenario([_raise(RuntimeError("boom"))])

        self.assertEqual(len(captured.records), 1)
        self.assertIsNotNone(captured.records[0].exc_info)
        self.assertEqual(run.terminal, ["failed"])

    def test_nothing_is_logged_for_success_expected_errors_or_transient_http_errors(self):
        scripts = [
            [_ok()],
            [_raise(ComfyUIEngineError("not yet")), _ok()],
            [_raise(http.client.IncompleteRead(b"ab", 10)), _raise(http.client.BadStatusLine("x")), _ok()],
        ]
        for index, script in enumerate(scripts):
            with self.subTest(index), self.assertNoLogs(worker_module.logger, "ERROR"):
                run = self.run_scenario(script)

                self.assertEqual(run.terminal, ["ready"])

    def test_the_user_diagnostic_does_not_depend_on_logging(self):
        module_logger = logging.getLogger(worker_module.__name__)
        previous = module_logger.disabled
        module_logger.disabled = True
        self.addCleanup(setattr, module_logger, "disabled", previous)

        run = self.run_scenario([_raise(RuntimeError("boom"))])

        self.assertEqual(run.terminal, ["failed"])
        self.assertEqual(run.event("failed")[1], "RuntimeError: boom")

    def test_a_base_exception_is_not_captured_and_emits_no_terminal_signal(self):
        # Called synchronously on the test thread: no KeyboardInterrupt/SystemExit is ever
        # injected into a Qt thread, and the dedicated subclass cannot reach the test runner.
        class _Fatal(BaseException):
            pass

        engine = _FakeEngine([_raise(_Fatal())])
        worker = ComfyUIReadinessWorker(engine, 1.0, 0.02, 0.05)
        seen = []
        worker.ready.connect(lambda: seen.append("ready"))
        worker.timed_out.connect(lambda: seen.append("timed_out"))
        worker.cancelled.connect(lambda: seen.append("cancelled"))
        worker.failed.connect(lambda detail: seen.append("failed"))

        with self.assertRaises(_Fatal):
            worker.run()

        self.assertEqual(seen, [])


if __name__ == "__main__":
    unittest.main()
