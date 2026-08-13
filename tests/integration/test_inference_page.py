"""
Real-widget coverage for the Mission 013 vertical: InferencePage's
Generate button, the worker/thread it starts, and the resulting
registration into Workspace.images via WorkspaceManager.add_images()
(reusing the same wiring ImagesPage/WORKSPACE_SAVED already use).
GenerationManager is mocked here — this test exercises the real Qt
widgets, the real QThread/GenerationWorker, and the real
WorkspaceManager/EventBus/ImagesPage wiring, never a real ComfyUI
instance.
"""

import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtWidgets import QApplication

from src.core.event_bus import EventBus
from src.managers.generation_manager import GenerationError
from src.managers.workspace_manager import (
    WorkspaceManager,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_SAVED,
    WORKSPACE_CLOSED,
)
from src.ui.pages.images_page import ImagesPage
from src.ui.pages.inference_page import InferencePage

_app = QApplication.instance() or QApplication([])


def _pump(seconds: float) -> None:
    """
    Test-only: pumps the main thread's event loop so queued
    worker->InferencePage signal deliveries actually happen. The real
    application never needs this — MainWindow's QApplication.exec()
    already runs continuously.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)


class InferencePageTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "InferenceProject"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.workspace_manager.create(self.folder)

        self.generated_path = str(Path(self.folder) / "outputs" / "generated.png")
        (Path(self.folder) / "outputs").mkdir(parents=True, exist_ok=True)
        Path(self.generated_path).write_bytes(b"fake-png-bytes")

        self.generation_manager = MagicMock()
        self.generation_manager.generate.return_value = self.generated_path

        self.images_page = ImagesPage(self.workspace_manager)
        self.page = InferencePage(self.generation_manager, self.workspace_manager)

        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_SAVED, WORKSPACE_CLOSED):
            self.event_bus.subscribe(event_name, self.images_page.update_images)

    def tearDown(self):
        self.page.shutdown()

    @patch("src.ui.pages.inference_page.QMessageBox.warning")
    def test_empty_prompt_is_refused_without_starting_a_generation(self, mock_warning):
        self.page.prompt.setPlainText("   ")

        self.page.generate_button.click()

        mock_warning.assert_called_once()
        self.generation_manager.generate.assert_not_called()
        self.assertTrue(self.page.generate_button.isEnabled())

    @patch("src.ui.pages.inference_page.QMessageBox.information")
    def test_click_disables_button_immediately_and_ui_is_not_blocked(self, mock_information):
        self.page.prompt.setPlainText("a red fox")

        def slow_generate(prompt_text, output_directory):
            time.sleep(0.3)
            return self.generated_path

        self.generation_manager.generate.side_effect = slow_generate

        self.page.generate_button.click()

        # The click handler returns immediately — the button is
        # already disabled right after click(), well before the
        # (deliberately slow) generation running on the worker thread
        # has had any chance to complete. If generation ran
        # synchronously on the main thread instead, this assertion
        # would still pass but the whole test would then hang on the
        # _pump() below for 0.3s while nothing else could run —
        # exactly what threading is meant to avoid.
        self.assertFalse(self.page.generate_button.isEnabled())

        _pump(2.0)

        self.assertTrue(self.page.generate_button.isEnabled())
        mock_information.assert_called_once()

    @patch("src.ui.pages.inference_page.QMessageBox.information")
    def test_successful_generation_registers_image_and_refreshes_images_page(self, mock_information):
        self.page.prompt.setPlainText("a red fox")

        self.page.generate_button.click()
        _pump(2.0)

        self.generation_manager.generate.assert_called_once_with(
            "a red fox", str(Path(self.folder) / "outputs")
        )

        image_paths = [image.file_path for image in self.workspace_manager.current_workspace.images]
        self.assertIn(self.generated_path, image_paths)

        items = [
            self.images_page.list_widget.item(i).text()
            for i in range(self.images_page.list_widget.count())
        ]
        self.assertIn(self.generated_path, items)

    @patch("src.ui.pages.inference_page.QMessageBox.critical")
    def test_generation_error_shows_message_reenables_button_and_registers_nothing(self, mock_critical):
        self.generation_manager.generate.side_effect = GenerationError("ComfyUI unreachable")
        self.page.prompt.setPlainText("a red fox")

        self.page.generate_button.click()
        _pump(2.0)

        self.assertTrue(self.page.generate_button.isEnabled())
        mock_critical.assert_called_once()
        self.assertEqual(self.workspace_manager.current_workspace.images, [])

    @patch("src.ui.pages.inference_page.QMessageBox.information")
    def test_second_generation_after_first_fully_completes_runs_a_fresh_full_qthread_cycle(
        self, mock_information
    ):
        # Mission 013 final review: not just that GenerationManager.
        # generate() can be called twice (already covered in
        # test_generation_manager.py without any Qt involved) — this
        # proves the *InferencePage-level* QThread/worker bookkeeping
        # (creation, started->run, finished->quit,
        # thread.finished->cleanup, reference reset) is torn down and
        # rebuilt correctly across two full, real cycles, driven only
        # by real widget clicks.
        second_path = str(Path(self.folder) / "outputs" / "generated_2.png")
        Path(second_path).write_bytes(b"fake-png-bytes-2")
        self.generation_manager.generate.side_effect = [self.generated_path, second_path]

        self.page.prompt.setPlainText("first fox")
        self.page.generate_button.click()
        _pump(2.0)

        # The first cycle's thread/worker must be fully torn down
        # (thread.finished -> _cleanup_thread already ran) before the
        # second click — this is what "after first fully completes"
        # means, and what distinguishes this test from merely clicking
        # twice in quick succession.
        self.assertIsNone(self.page._thread)
        self.assertIsNone(self.page._worker)
        self.assertTrue(self.page.generate_button.isEnabled())

        self.page.prompt.setPlainText("second fox")
        self.page.generate_button.click()
        _pump(2.0)

        self.assertIsNone(self.page._thread)
        self.assertIsNone(self.page._worker)
        self.assertTrue(self.page.generate_button.isEnabled())
        self.assertEqual(self.generation_manager.generate.call_count, 2)

        image_paths = [image.file_path for image in self.workspace_manager.current_workspace.images]
        self.assertEqual(image_paths, [self.generated_path, second_path])

        items = [
            self.images_page.list_widget.item(i).text()
            for i in range(self.images_page.list_widget.count())
        ]
        self.assertEqual(items, [self.generated_path, second_path])

    # --- Race-condition regression coverage (final review, section 2) ---
    #
    # worker.finished/failed re-enables the button (queued to the main
    # thread) strictly before thread.finished -> _cleanup_thread fires
    # (quit() must be delivered and the OS thread must actually exit
    # first). If a second generation starts in that window, the OLD
    # cycle's deferred cleanup must never touch the NEW cycle's
    # worker/thread — neither by deleting the wrong objects nor by
    # resetting self._worker/self._thread out from under it.

    def test_cleanup_of_an_old_cycle_never_touches_a_newer_cycles_references(self):
        # Direct, deterministic proof of the guard itself: simulate a
        # newer cycle already being in place (self._worker/self._thread
        # replaced) when an OLDER cycle's deferred cleanup finally runs.
        old_worker = MagicMock()
        old_thread = MagicMock()
        new_worker = MagicMock()
        new_thread = MagicMock()

        self.page._worker = new_worker
        self.page._thread = new_thread

        self.page._cleanup_thread(old_worker, old_thread)

        old_worker.deleteLater.assert_called_once()
        old_thread.deleteLater.assert_called_once()
        new_worker.deleteLater.assert_not_called()
        new_thread.deleteLater.assert_not_called()
        self.assertIs(self.page._worker, new_worker)
        self.assertIs(self.page._thread, new_thread)

    def test_cleanup_resets_references_only_when_they_still_belong_to_this_cycle(self):
        worker = MagicMock()
        thread = MagicMock()
        self.page._worker = worker
        self.page._thread = thread

        self.page._cleanup_thread(worker, thread)

        worker.deleteLater.assert_called_once()
        thread.deleteLater.assert_called_once()
        self.assertIsNone(self.page._worker)
        self.assertIsNone(self.page._thread)

    def _assert_rapid_reclick_is_safe(self, first_side_effect):
        # End-to-end proof, with real QThread objects: click, poll for
        # the button to become re-enabled (the moment worker.finished/
        # failed's first queued slot has run), and click again
        # *immediately* — maximizing the chance the old cycle's
        # thread.finished -> _cleanup_thread has not fired yet. No
        # exception may escape, no Qt "destroyed while running" warning
        # may be logged, and the second generation must complete
        # normally once fully pumped.
        captured_messages = []
        qInstallMessageHandler(lambda mode, context, message: captured_messages.append(message))
        try:
            second_path = str(Path(self.folder) / "outputs" / "generated_race.png")
            Path(second_path).write_bytes(b"fake-png-bytes-race")
            self.generation_manager.generate.side_effect = [first_side_effect, second_path]

            self.page.prompt.setPlainText("first")
            self.page.generate_button.click()

            deadline = time.monotonic() + 5.0
            while not self.page.generate_button.isEnabled() and time.monotonic() < deadline:
                QApplication.processEvents()
                time.sleep(0.001)

            self.assertTrue(self.page.generate_button.isEnabled(), "first generation never completed")

            # Immediate re-click, no further pumping first — this is the
            # narrow race window.
            self.page.prompt.setPlainText("second")
            self.page.generate_button.click()

            _pump(3.0)

            self.assertTrue(self.page.generate_button.isEnabled())
            self.assertEqual(self.generation_manager.generate.call_count, 2)

            image_paths = [
                image.file_path for image in self.workspace_manager.current_workspace.images
            ]
            self.assertIn(second_path, image_paths)

            offending = [m for m in captured_messages if "destroyed while" in m.lower()]
            self.assertEqual(offending, [], f"Qt logged: {offending}")
        finally:
            qInstallMessageHandler(None)

    @patch("src.ui.pages.inference_page.QMessageBox.information")
    @patch("src.ui.pages.inference_page.QMessageBox.critical")
    def test_rapid_second_click_after_success_is_safe(self, mock_critical, mock_information):
        self._assert_rapid_reclick_is_safe(self.generated_path)

    @patch("src.ui.pages.inference_page.QMessageBox.information")
    @patch("src.ui.pages.inference_page.QMessageBox.critical")
    def test_rapid_second_click_after_error_is_safe(self, mock_critical, mock_information):
        self._assert_rapid_reclick_is_safe(GenerationError("boom"))


if __name__ == "__main__":
    unittest.main()
