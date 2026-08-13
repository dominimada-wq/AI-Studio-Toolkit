"""
Coverage for src/ui/generation_worker.py — GenerationWorker actually
runs off the Qt main thread and translates GenerationManager's
result/exception into finished/failed signals. GenerationManager is
mocked (MagicMock), so these tests exercise the real QThread/QObject
machinery without any real generation logic or network access.
"""

import time
import unittest
from unittest.mock import MagicMock

from PySide6.QtCore import QCoreApplication, QThread

from src.managers.generation_manager import GenerationError
from src.ui.generation_worker import GenerationWorker

_app = QCoreApplication.instance() or QCoreApplication([])


def _run_worker(generation_manager, timeout_seconds=5.0):
    """
    Test-only harness. In the real application, MainWindow's QThread
    is quit()/finished as part of the normally-running Qt main loop
    (QApplication.exec()) — nothing special is required there. This
    test process never calls exec(), so the queued worker.finished ->
    thread.quit() call needs the main thread's event loop pumped
    explicitly, or it is never delivered and thread.wait() hangs
    forever. That is what this polling loop does — a test harness
    detail, not a production concern.
    """
    thread = QThread()
    worker = GenerationWorker(generation_manager, "a fox", "/tmp/out")
    worker.moveToThread(thread)

    results = {}

    worker.finished.connect(lambda path: results.__setitem__("path", path))
    worker.failed.connect(lambda message: results.__setitem__("error", message))
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.failed.connect(thread.quit)

    thread.start()

    deadline = time.monotonic() + timeout_seconds
    while thread.isRunning() and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.01)

    if thread.isRunning():
        raise AssertionError("worker thread did not finish within timeout")

    thread.wait(1000)
    QCoreApplication.processEvents()

    worker.deleteLater()
    thread.deleteLater()
    QCoreApplication.processEvents()

    return results


class GenerationWorkerTest(unittest.TestCase):

    def test_success_emits_finished_with_the_generated_path(self):
        manager = MagicMock()
        manager.generate.return_value = "/tmp/out/image.png"

        results = _run_worker(manager)

        self.assertEqual(results.get("path"), "/tmp/out/image.png")
        self.assertNotIn("error", results)
        manager.generate.assert_called_once_with("a fox", "/tmp/out")

    def test_generation_error_emits_failed_with_message(self):
        manager = MagicMock()
        manager.generate.side_effect = GenerationError("prompt is empty")

        results = _run_worker(manager)

        self.assertEqual(results.get("error"), "prompt is empty")
        self.assertNotIn("path", results)

    def test_unexpected_exception_never_crosses_the_thread_boundary_unhandled(self):
        # Safety net: even an exception GenerationManager never
        # documented (not a GenerationError) must still surface as a
        # failed signal, never propagate uncaught out of the thread.
        manager = MagicMock()
        manager.generate.side_effect = RuntimeError("unexpected")

        results = _run_worker(manager)

        self.assertEqual(results.get("error"), "unexpected")
        self.assertNotIn("path", results)

    def test_generation_actually_runs_off_the_main_thread(self):
        main_thread = QThread.currentThread()
        observed = {}

        manager = MagicMock()

        def fake_generate(prompt_text, output_directory):
            observed["thread"] = QThread.currentThread()
            return "/tmp/out/image.png"

        manager.generate.side_effect = fake_generate

        _run_worker(manager)

        self.assertIsNotNone(observed.get("thread"))
        self.assertIsNot(observed["thread"], main_thread)


if __name__ == "__main__":
    unittest.main()
