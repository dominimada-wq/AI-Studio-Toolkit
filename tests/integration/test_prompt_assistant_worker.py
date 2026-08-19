"""
Coverage for src/ui/prompt_assistant_worker.py — PromptAssistantWorker
actually runs off the Qt main thread and translates
PromptAssistantManager's result/exception into finished/failed signals.
PromptAssistantManager is mocked (MagicMock), so these tests exercise
the real QThread/QObject machinery without any real assist logic or
network access. Structural mirror of test_generation_worker.py.
"""

import time
import unittest
from unittest.mock import MagicMock

from PySide6.QtCore import QCoreApplication, QThread

from src.managers.prompt_assistant_manager import PromptAssistantError
from src.ui.prompt_assistant_worker import PromptAssistantWorker

_app = QCoreApplication.instance() or QCoreApplication([])


def _run_worker(prompt_assistant_manager, request_text="a fox", existing_prompt="", timeout_seconds=5.0):
    thread = QThread()
    worker = PromptAssistantWorker(prompt_assistant_manager, request_text, existing_prompt)
    worker.moveToThread(thread)

    results = {}

    worker.finished.connect(lambda text: results.__setitem__("text", text))
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


class PromptAssistantWorkerTest(unittest.TestCase):

    def test_success_emits_finished_with_the_proposed_text(self):
        manager = MagicMock()
        manager.assist.return_value = "a fox in a forest"

        results = _run_worker(manager, request_text="a fox")

        self.assertEqual(results.get("text"), "a fox in a forest")
        self.assertNotIn("error", results)
        manager.assist.assert_called_once_with("a fox", existing_prompt="")

    def test_existing_prompt_is_forwarded_to_assist(self):
        manager = MagicMock()
        manager.assist.return_value = "improved"

        _run_worker(manager, request_text="make it better", existing_prompt="a fox")

        manager.assist.assert_called_once_with("make it better", existing_prompt="a fox")

    def test_prompt_assistant_error_emits_failed_with_message(self):
        manager = MagicMock()
        manager.assist.side_effect = PromptAssistantError("Ollama server unreachable")

        results = _run_worker(manager)

        self.assertEqual(results.get("error"), "Ollama server unreachable")
        self.assertNotIn("text", results)

    def test_unexpected_exception_never_crosses_the_thread_boundary_unhandled(self):
        manager = MagicMock()
        manager.assist.side_effect = RuntimeError("unexpected")

        results = _run_worker(manager)

        self.assertEqual(results.get("error"), "unexpected")
        self.assertNotIn("text", results)

    def test_assist_actually_runs_off_the_main_thread(self):
        main_thread = QThread.currentThread()
        observed = {}

        manager = MagicMock()

        def fake_assist(request_text, existing_prompt=""):
            observed["thread"] = QThread.currentThread()
            return "result"

        manager.assist.side_effect = fake_assist

        _run_worker(manager)

        self.assertIsNotNone(observed.get("thread"))
        self.assertIsNot(observed["thread"], main_thread)


if __name__ == "__main__":
    unittest.main()
