"""
Real-widget coverage for Mission 013's threading foundation and Mission
014's post-generation validation state machine: InferencePage's Generate
button, the pending-result preview it produces, and Accept/Reject/
Regenerate deciding whether that result ever reaches Workspace.images.
GenerationManager is mocked throughout — these tests exercise the real
Qt widgets, the real QThread/GenerationWorker, and the real
WorkspaceManager/EventBus/ImagesPage wiring, never a real ComfyUI
instance.
"""

import json
import time
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt, qInstallMessageHandler
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from src.core.event_bus import EventBus
from src.domain.character import Character
from src.infrastructure.storage.workspace_storage import WorkspaceStorage, WorkspaceStorageError
from src.managers.generation_manager import (
    REFERENCE_ROLE_POSE_COMPOSITION,
    GenerationError,
    Reference,
)
from src.managers.workspace_manager import (
    WorkspaceManager,
    WorkspaceManagerError,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_SAVED,
    WORKSPACE_CLOSED,
    WORKSPACE_RENAMED,
)
from src.ui.pages.images_page import ImagesPage
from src.ui.pages.inference_page import InferencePage
from src.ui.dialogs.image_preview_dialog import ImagePreviewDialog

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


def _wait_until(predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        QApplication.processEvents()
        time.sleep(0.001)
    return predicate()


class InferencePageTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "InferenceProject"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.workspace_manager.create(self.folder)

        self.outputs_dir = Path(self.folder) / "outputs"
        self.outputs_dir.mkdir(parents=True, exist_ok=True)

        self.generated_path = str(self.outputs_dir / "generated.png")
        Path(self.generated_path).write_bytes(b"fake-png-bytes")

        self.generation_manager = MagicMock()
        self.generation_manager.generate.return_value = self.generated_path

        self.prompt_manager = MagicMock()
        self.prompt_assistant_manager = MagicMock()
        self.character_manager = MagicMock()
        self.character_manager.principal_character = None

        self.images_page = ImagesPage(self.workspace_manager)
        self.page = InferencePage(
            self.generation_manager,
            self.workspace_manager,
            self.prompt_manager,
            self.prompt_assistant_manager,
            self.character_manager,
        )

        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_SAVED, WORKSPACE_CLOSED):
            self.event_bus.subscribe(event_name, self.images_page.update_images)

        # Mirrors MainWindow's real wiring (Mission 014 final review,
        # extended by Mission 027 with WORKSPACE_RENAMED): WORKSPACE_SAVED
        # is deliberately excluded — see
        # InferencePage.reset_for_workspace_change's own docstring.
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED, WORKSPACE_RENAMED):
            self.event_bus.subscribe(event_name, self.page.reset_for_workspace_change)

    def tearDown(self):
        self.page.shutdown()

    def _generate(self, prompt_text="a red fox"):
        self.page.prompt.setPlainText(prompt_text)
        self.page.generate_button.click()
        _pump(2.0)

    def _images_page_paths(self):
        return [
            self.images_page.list_widget.item(i).data(Qt.UserRole)
            for i in range(self.images_page.list_widget.count())
        ]

    # --- Initial state ---

    def test_initial_state_has_no_pending_and_validation_buttons_disabled(self):
        self.assertIsNone(self.page._pending_path)
        self.assertTrue(self.page.generate_button.isEnabled())
        self.assertFalse(self.page.accept_button.isEnabled())
        self.assertFalse(self.page.reject_button.isEnabled())
        self.assertFalse(self.page.regenerate_button.isEnabled())
        self.assertFalse(self.page.preview_enlarge_button.isEnabled())

    def test_empty_prompt_is_refused_without_starting_a_generation(self):
        self.page.prompt.setPlainText("   ")

        with patch("src.ui.pages.inference_page.QMessageBox.warning") as mock_warning:
            self.page.generate_button.click()
            mock_warning.assert_called_once()

        self.generation_manager.generate.assert_not_called()
        self.assertTrue(self.page.generate_button.isEnabled())

    # --- 1. Success -> preview, no persistence ---

    def test_successful_generation_shows_pending_result_without_persisting(self):
        self._generate()

        self.generation_manager.generate.assert_called_once_with(
            "a red fox", str(self.outputs_dir), reference_images=[], reference_strength=0.75
        )
        self.assertEqual(self.page._pending_path, self.generated_path)
        self.assertEqual(self.workspace_manager.current_workspace.images, [])
        self.assertEqual(self._images_page_paths(), [])

        self.assertFalse(self.page.generate_button.isEnabled())
        self.assertTrue(self.page.accept_button.isEnabled())
        self.assertTrue(self.page.reject_button.isEnabled())
        self.assertTrue(self.page.regenerate_button.isEnabled())
        self.assertTrue(self.page.preview_enlarge_button.isEnabled())

    def test_preview_shows_pixmap_for_a_valid_image_file(self):
        valid_path = str(self.outputs_dir / "valid.png")
        pixmap = QPixmap(4, 3)
        pixmap.fill()
        self.assertTrue(pixmap.save(valid_path, "PNG"))

        self.generation_manager.generate.return_value = valid_path
        self._generate()

        self.assertIsNotNone(self.page._pending_pixmap)
        self.assertFalse(self.page.preview_label.pixmap().isNull())

    def test_preview_is_cleared_for_an_unreadable_image_file(self):
        # generated_path holds non-image bytes (b"fake-png-bytes") in
        # every test — QPixmap load fails, and this must not crash: the
        # pending state is still tracked (Accept/Reject/Regenerate stay
        # usable), only the visual preview itself is absent.
        self._generate()

        self.assertIsNone(self.page._pending_pixmap)
        self.assertTrue(self.page.preview_label.pixmap() is None or self.page.preview_label.pixmap().isNull())
        self.assertTrue(self.page.accept_button.isEnabled())

    # --- 2. Accept -> add_images exactly once ---

    def test_accept_persists_pending_image_exactly_once(self):
        self._generate()

        # Mission 028 non-regression (MISSION_028.md section 6.3):
        # self.generated_path already sits under <root>/outputs/, so
        # add_images() must recognize it as already-internal and reuse
        # it as-is — never copy it a second time into images/, which
        # would silently duplicate every accepted generation on disk.
        with patch.object(
            self.workspace_manager, "add_images", wraps=self.workspace_manager.add_images
        ) as spy, patch(
            "src.infrastructure.storage.workspace_storage.shutil.copy2"
        ) as copy2_mock:
            self.page.accept_button.click()
            spy.assert_called_once_with([self.generated_path])
            copy2_mock.assert_not_called()

        image_paths = [image.file_path for image in self.workspace_manager.current_workspace.images]
        self.assertEqual(image_paths, [self.generated_path])
        self.assertTrue(Path(self.generated_path).exists())
        # images/ is pre-created empty by WorkspaceStorage.create_directories()
        # (Mission 011) — must stay empty, never receive a duplicate copy.
        self.assertEqual(
            list((self.workspace_manager.current_workspace.root / "images").iterdir()), []
        )
        self.assertIn(self.generated_path, self._images_page_paths())

        self.assertIsNone(self.page._pending_path)
        self.assertTrue(self.page.generate_button.isEnabled())
        self.assertFalse(self.page.accept_button.isEnabled())
        self.assertFalse(self.page.reject_button.isEnabled())
        self.assertFalse(self.page.regenerate_button.isEnabled())

    def test_accept_with_no_pending_result_is_a_no_op(self):
        self.page._on_accept_clicked()

        self.generation_manager.generate.assert_not_called()
        self.assertEqual(self.workspace_manager.current_workspace.images, [])

    # --- 2bis. Mission 067: Accept + save() failure ---

    def test_accept_save_failure_keeps_pending_state_and_shows_error(self):
        self._generate()

        # add_images() now rollbacks Workspace.images before re-raising
        # on a save() failure — generated_path is a passthrough already
        # under outputs/, so no physical copy is ever created for it.
        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ), patch("src.ui.pages.inference_page.QMessageBox.critical") as mock_critical:
            self.page.accept_button.click()

        mock_critical.assert_called_once()
        self.assertEqual(self.workspace_manager.current_workspace.images, [])
        self.assertTrue(Path(self.generated_path).exists())

        # The page stays in exactly the pre-Accept "pending" state —
        # not reverted to "no pending result at all".
        self.assertEqual(self.page._pending_path, self.generated_path)
        self.assertTrue(self.page.accept_button.isEnabled())
        self.assertTrue(self.page.reject_button.isEnabled())
        self.assertTrue(self.page.regenerate_button.isEnabled())
        self.assertFalse(self.page.generate_button.isEnabled())

    def test_retry_accept_after_save_failure_actually_persists(self):
        self._generate()

        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ), patch("src.ui.pages.inference_page.QMessageBox.critical"):
            self.page.accept_button.click()

        # Second click: save() is no longer mocked to fail — a genuine
        # new attempt, not a silent no-op, since add_images() rolled
        # the failed attempt's Domain entry back.
        self.page.accept_button.click()

        image_paths = [image.file_path for image in self.workspace_manager.current_workspace.images]
        self.assertEqual(image_paths, [self.generated_path])
        self.assertIsNone(self.page._pending_path)
        self.assertTrue(self.page.generate_button.isEnabled())
        self.assertFalse(self.page.accept_button.isEnabled())

    def test_reject_after_failed_accept_leaves_no_phantom_reference(self):
        self._generate()

        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ), patch("src.ui.pages.inference_page.QMessageBox.critical"):
            self.page.accept_button.click()

        self.page.reject_button.click()

        self.assertFalse(Path(self.generated_path).exists())
        self.assertEqual(self.workspace_manager.current_workspace.images, [])
        self.assertIsNone(self.page._pending_path)

        # A later, unrelated successful save() must never resurrect a
        # phantom reference to the now-deleted pending file — this is
        # the exact scenario the pre-Mission 067 mini-audit demonstrated
        # as a real risk.
        self.workspace_manager.save()
        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertEqual(on_disk["images"], [])

    # --- 3. Reject -> file deleted, no persistence ---

    def test_reject_deletes_pending_file_without_persisting(self):
        self._generate()
        self.assertTrue(Path(self.generated_path).exists())

        self.page.reject_button.click()

        self.assertFalse(Path(self.generated_path).exists())
        self.assertEqual(self.workspace_manager.current_workspace.images, [])
        self.assertIsNone(self.page._pending_path)
        self.assertTrue(self.page.generate_button.isEnabled())
        self.assertFalse(self.page.accept_button.isEnabled())
        self.assertEqual(self._images_page_paths(), [])

    # --- 4. Regenerate -> old file deleted, prompt kept, new real cycle ---

    def test_regenerate_deletes_old_pending_keeps_prompt_and_starts_new_cycle(self):
        second_path = str(self.outputs_dir / "generated_2.png")
        prompts_seen = []

        def generate_side_effect(prompt_text, output_directory, reference_images=None, reference_strength=None):
            prompts_seen.append(prompt_text)
            if len(prompts_seen) == 1:
                return self.generated_path
            Path(second_path).write_bytes(b"fake-png-bytes-2")
            return second_path

        self.generation_manager.generate.side_effect = generate_side_effect

        self._generate(prompt_text="first fox")
        self.assertEqual(self.page._pending_path, self.generated_path)
        self.assertTrue(Path(self.generated_path).exists())

        self.page.regenerate_button.click()
        _pump(2.0)

        self.assertFalse(Path(self.generated_path).exists())
        self.assertEqual(self.page._pending_path, second_path)
        self.assertEqual(prompts_seen, ["first fox", "first fox"])
        self.assertEqual(self.workspace_manager.current_workspace.images, [])

        self.assertFalse(self.page.generate_button.isEnabled())
        self.assertTrue(self.page.accept_button.isEnabled())

    def test_regenerate_with_no_pending_result_is_a_no_op(self):
        self.page._on_regenerate_clicked()
        self.generation_manager.generate.assert_not_called()

    # --- 5. Close with pending -> cleanup without persistence ---

    def test_shutdown_with_pending_result_deletes_file_without_persisting(self):
        self._generate()
        self.assertTrue(Path(self.generated_path).exists())

        self.page.shutdown()

        self.assertFalse(Path(self.generated_path).exists())
        self.assertIsNone(self.page._pending_path)
        self.assertEqual(self.workspace_manager.current_workspace.images, [])

    def test_shutdown_without_pending_result_does_nothing_special(self):
        self.page.shutdown()  # no thread, no pending — must not raise
        self.assertIsNone(self.page._pending_path)

    # --- 6. Pending file already missing -> no crash ---

    def test_reject_when_pending_file_already_missing_does_not_crash(self):
        self._generate()
        Path(self.generated_path).unlink()

        self.page.reject_button.click()

        self.assertIsNone(self.page._pending_path)
        self.assertTrue(self.page.generate_button.isEnabled())

    # --- 7. Deletion error -> controlled behavior ---

    @patch("src.ui.pages.inference_page.Path.unlink", side_effect=OSError("permission denied"))
    def test_deletion_error_is_handled_without_crashing(self, mock_unlink):
        self._generate()

        with patch("src.ui.pages.inference_page.QMessageBox.warning") as mock_warning:
            self.page.reject_button.click()
            mock_warning.assert_called_once()

        mock_unlink.assert_called_once()
        self.assertIsNone(self.page._pending_path)
        self.assertTrue(self.page.generate_button.isEnabled())
        self.assertFalse(self.page.accept_button.isEnabled())
        self.assertEqual(self.workspace_manager.current_workspace.images, [])

    @patch("src.ui.pages.inference_page.Path.unlink", side_effect=OSError("permission denied"))
    def test_regenerate_deletion_error_still_starts_a_new_generation(self, mock_unlink):
        # Mission 014 final review policy: unlike Reject, a failed
        # deletion of the OLD pending file must not block Regenerate —
        # no Domain/Workspace consistency is at risk (the old file was
        # never persisted either way) — but the user must still be
        # informed that an orphan file may remain on disk.
        second_path = str(self.outputs_dir / "generated_2.png")
        prompts_seen = []

        def generate_side_effect(prompt_text, output_directory, reference_images=None, reference_strength=None):
            prompts_seen.append(prompt_text)
            if len(prompts_seen) == 1:
                return self.generated_path
            Path(second_path).write_bytes(b"fake-png-bytes-2")
            return second_path

        self.generation_manager.generate.side_effect = generate_side_effect

        self._generate(prompt_text="first fox")

        with patch("src.ui.pages.inference_page.QMessageBox.warning") as mock_warning:
            self.page.regenerate_button.click()
            _pump(2.0)
            mock_warning.assert_called_once()

        mock_unlink.assert_called_once()
        self.assertEqual(self.page._pending_path, second_path)
        self.assertEqual(prompts_seen, ["first fox", "first fox"])
        self.assertTrue(self.page.accept_button.isEnabled())

    # --- 8. Generation error -> restored initial state ---

    @patch("src.ui.pages.inference_page.QMessageBox.critical")
    def test_generation_error_restores_initial_state_without_pending(self, mock_critical):
        self.generation_manager.generate.side_effect = GenerationError("ComfyUI unreachable")

        self._generate()

        mock_critical.assert_called_once()
        self.assertIsNone(self.page._pending_path)
        self.assertTrue(self.page.generate_button.isEnabled())
        self.assertFalse(self.page.accept_button.isEnabled())
        self.assertFalse(self.page.reject_button.isEnabled())
        self.assertFalse(self.page.regenerate_button.isEnabled())
        self.assertEqual(self.workspace_manager.current_workspace.images, [])

    # --- 9. Rapid double action -> no double persistence ---

    def test_double_click_accept_does_not_persist_twice(self):
        # Qt itself refuses click() on an already-disabled QPushButton,
        # so this proves the UI-level guarantee (button state alone
        # already prevents a second Accept).
        self._generate()

        with patch.object(
            self.workspace_manager, "add_images", wraps=self.workspace_manager.add_images
        ) as spy:
            self.page.accept_button.click()
            self.page.accept_button.click()
            spy.assert_called_once()

    def test_direct_double_call_accept_does_not_persist_twice(self):
        # Same guarantee, bypassing the button's enabled state entirely
        # — proves the handler itself is defensive, not just the widget.
        self._generate()

        with patch.object(
            self.workspace_manager, "add_images", wraps=self.workspace_manager.add_images
        ) as spy:
            self.page._on_accept_clicked()
            self.page._on_accept_clicked()
            spy.assert_called_once()

    def test_rapid_regenerate_after_success_is_safe(self):
        # Mission 013's original race was: worker.finished re-enables
        # Generate before thread.finished -> _cleanup_thread runs, so a
        # fast second generation could let a stale cleanup tear down the
        # new cycle. Mission 014 replaces the "click Generate again"
        # trigger with "click Regenerate" (Generate itself stays
        # disabled after success) — this proves the same guarantee holds
        # through that new path, with real QThread objects.
        captured_messages = []
        qInstallMessageHandler(lambda mode, context, message: captured_messages.append(message))
        try:
            second_path = str(self.outputs_dir / "generated_race.png")
            prompts_seen = []

            def generate_side_effect(prompt_text, output_directory, reference_images=None, reference_strength=None):
                prompts_seen.append(prompt_text)
                if len(prompts_seen) == 1:
                    return self.generated_path
                Path(second_path).write_bytes(b"fake-png-bytes-race")
                return second_path

            self.generation_manager.generate.side_effect = generate_side_effect

            self.page.prompt.setPlainText("first")
            self.page.generate_button.click()

            self.assertTrue(
                _wait_until(lambda: self.page.regenerate_button.isEnabled()),
                "first generation never completed",
            )

            # Immediate re-click, no further pumping first — this is the
            # narrow race window (thread.finished -> _cleanup_thread for
            # cycle 1 may not have run yet).
            self.page.regenerate_button.click()

            _pump(3.0)

            self.assertEqual(prompts_seen, ["first", "first"])
            self.assertEqual(self.page._pending_path, second_path)
            self.assertTrue(self.page.accept_button.isEnabled())
            self.assertEqual(self.workspace_manager.current_workspace.images, [])

            offending = [m for m in captured_messages if "destroyed while" in m.lower()]
            self.assertEqual(offending, [], f"Qt logged: {offending}")
        finally:
            qInstallMessageHandler(None)

    @patch("src.ui.pages.inference_page.QMessageBox.critical")
    def test_rapid_second_click_after_error_is_safe(self, mock_critical):
        captured_messages = []
        qInstallMessageHandler(lambda mode, context, message: captured_messages.append(message))
        try:
            second_path = str(self.outputs_dir / "generated_race_error.png")
            self.generation_manager.generate.side_effect = [
                GenerationError("boom"),
                second_path,
            ]

            self.page.prompt.setPlainText("first")
            self.page.generate_button.click()

            self.assertTrue(
                _wait_until(lambda: self.page.generate_button.isEnabled()),
                "first (failing) generation never completed",
            )

            self.page.prompt.setPlainText("second")
            self.page.generate_button.click()

            _pump(3.0)

            self.assertEqual(self.generation_manager.generate.call_count, 2)
            self.assertEqual(self.page._pending_path, second_path)

            offending = [m for m in captured_messages if "destroyed while" in m.lower()]
            self.assertEqual(offending, [], f"Qt logged: {offending}")
        finally:
            qInstallMessageHandler(None)

    # --- 10. Mission 013 race-condition guard tests, unchanged ---

    def test_cleanup_of_an_old_cycle_never_touches_a_newer_cycles_references(self):
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

    # --- Sequential full cycles (Generate -> Accept, twice) ---

    def test_second_full_cycle_after_accept_runs_a_fresh_qthread_cycle(self):
        second_path = str(self.outputs_dir / "generated_2.png")
        prompts_seen = []

        def generate_side_effect(prompt_text, output_directory, reference_images=None, reference_strength=None):
            prompts_seen.append(prompt_text)
            if len(prompts_seen) == 1:
                return self.generated_path
            Path(second_path).write_bytes(b"fake-png-bytes-2")
            return second_path

        self.generation_manager.generate.side_effect = generate_side_effect

        self._generate(prompt_text="first fox")
        self.page.accept_button.click()

        self.assertIsNone(self.page._thread)
        self.assertIsNone(self.page._worker)
        self.assertTrue(self.page.generate_button.isEnabled())

        self._generate(prompt_text="second fox")
        self.page.accept_button.click()

        self.assertIsNone(self.page._thread)
        self.assertIsNone(self.page._worker)
        self.assertTrue(self.page.generate_button.isEnabled())
        self.assertEqual(prompts_seen, ["first fox", "second fox"])

        image_paths = [image.file_path for image in self.workspace_manager.current_workspace.images]
        self.assertEqual(image_paths, [self.generated_path, second_path])
        self.assertEqual(self._images_page_paths(), [self.generated_path, second_path])

    # --- UI not blocked during generation (Mission 013 guarantee, unchanged) ---

    def test_click_disables_button_immediately_and_ui_is_not_blocked(self):
        def slow_generate(prompt_text, output_directory, reference_images=None, reference_strength=None):
            time.sleep(0.3)
            return self.generated_path

        self.generation_manager.generate.side_effect = slow_generate

        self.page.prompt.setPlainText("a red fox")
        self.page.generate_button.click()

        # The click handler returns immediately — Generate is already
        # disabled right after click(), well before the (deliberately
        # slow) generation running on the worker thread has had any
        # chance to complete.
        self.assertFalse(self.page.generate_button.isEnabled())
        self.assertFalse(self.page.accept_button.isEnabled())

        _pump(2.0)

        self.assertTrue(self.page.accept_button.isEnabled())
        self.assertFalse(self.page.generate_button.isEnabled())


    # --- Mission 014 final review: pending result <-> Workspace binding ---

    def test_workspace_switch_before_accept_never_persists_into_new_workspace(self):
        self._generate()
        self.assertEqual(self.page._pending_path, self.generated_path)

        folder_b = Path(self.tmp_dir) / "WorkspaceB"
        self.workspace_manager.create(folder_b)  # WORKSPACE_CREATED -> reset_for_workspace_change

        self.assertIsNone(self.page._pending_path)
        self.assertFalse(Path(self.generated_path).exists())
        self.assertTrue(self.page.generate_button.isEnabled())
        self.assertFalse(self.page.accept_button.isEnabled())
        self.assertFalse(self.page.preview_enlarge_button.isEnabled())
        self.assertEqual(self.workspace_manager.current_workspace.images, [])

        # Defense in depth: even a stray Accept call after the fact must
        # still be a strict no-op (see InferencePage._on_accept_clicked's
        # own workspace-mismatch guard).
        with patch.object(
            self.workspace_manager, "add_images", wraps=self.workspace_manager.add_images
        ) as spy:
            self.page._on_accept_clicked()
            spy.assert_not_called()

    def test_workspace_open_invalidates_pending_and_resets_ui(self):
        self._generate()

        other_folder = Path(self.tmp_dir) / "OtherProject"
        WorkspaceManager(event_bus=EventBus()).create(other_folder)
        self.workspace_manager.open(other_folder)  # WORKSPACE_OPENED

        self.assertIsNone(self.page._pending_path)
        self.assertFalse(Path(self.generated_path).exists())
        self.assertTrue(self.page.generate_button.isEnabled())
        self.assertFalse(self.page.accept_button.isEnabled())
        self.assertFalse(self.page.reject_button.isEnabled())
        self.assertFalse(self.page.regenerate_button.isEnabled())
        self.assertFalse(self.page.preview_enlarge_button.isEnabled())

    def test_workspace_close_invalidates_pending(self):
        self._generate()

        self.workspace_manager.close()  # WORKSPACE_CLOSED

        self.assertIsNone(self.page._pending_path)
        self.assertFalse(Path(self.generated_path).exists())
        self.assertTrue(self.page.generate_button.isEnabled())
        self.assertFalse(self.page.preview_enlarge_button.isEnabled())

    def test_workspace_rename_invalidates_pending_and_resets_ui(self):
        """
        Mission 027: a real rename() physically moves the workspace
        folder (and the pending file inside it) — the old path string
        captured before the rename must no longer resolve to anything,
        exactly like a workspace switch/close already invalidates a
        pending result computed for the previous root.
        """
        self._generate()

        self.workspace_manager.rename("RenamedInferenceProject")  # WORKSPACE_RENAMED

        self.assertIsNone(self.page._pending_path)
        self.assertFalse(Path(self.generated_path).exists())
        self.assertTrue(self.page.generate_button.isEnabled())
        self.assertFalse(self.page.accept_button.isEnabled())
        self.assertFalse(self.page.reject_button.isEnabled())
        self.assertFalse(self.page.regenerate_button.isEnabled())
        self.assertFalse(self.page.preview_enlarge_button.isEnabled())

    def test_workspace_switch_during_in_flight_generation_is_never_persisted(self):
        def slow_generate(prompt_text, output_directory, reference_images=None, reference_strength=None):
            time.sleep(0.3)
            return self.generated_path

        self.generation_manager.generate.side_effect = slow_generate

        self.page.prompt.setPlainText("a red fox")
        self.page.generate_button.click()

        # Thread already running against Workspace A's output_directory
        # (fixed at _start_generation() time). Switch the active
        # workspace before the worker completes.
        folder_b = Path(self.tmp_dir) / "WorkspaceB"
        self.workspace_manager.create(folder_b)

        _pump(2.0)

        # The file was still written correctly under A/outputs (and is
        # then discarded) — it must never surface as pending, and must
        # never reach Workspace B's images.
        self.assertIsNone(self.page._pending_path)
        self.assertFalse(Path(self.generated_path).exists())
        self.assertEqual(self.workspace_manager.current_workspace.images, [])
        self.assertTrue(self.page.generate_button.isEnabled())
        self.assertFalse(self.page.accept_button.isEnabled())
        self.assertFalse(self.page.preview_enlarge_button.isEnabled())

    def test_accept_with_pending_file_missing_persists_nothing(self):
        self._generate()
        Path(self.generated_path).unlink()

        with patch("src.ui.pages.inference_page.QMessageBox.warning") as mock_warning:
            self.page.accept_button.click()
            mock_warning.assert_called_once()

        self.assertEqual(self.workspace_manager.current_workspace.images, [])
        self.assertIsNone(self.page._pending_path)
        self.assertTrue(self.page.generate_button.isEnabled())

    def test_generation_in_new_workspace_after_switch_works_normally(self):
        self._generate()

        folder_b = Path(self.tmp_dir) / "WorkspaceB"
        self.workspace_manager.create(folder_b)  # invalidates A's pending

        outputs_b = str(Path(folder_b) / "outputs")
        path_b = str(Path(outputs_b) / "generated_b.png")
        Path(path_b).write_bytes(b"fake-png-bytes-b")
        self.generation_manager.generate.side_effect = None
        self.generation_manager.generate.return_value = path_b

        self.page.prompt.setPlainText("a blue sphere")
        self.page.generate_button.click()
        _pump(2.0)

        self.generation_manager.generate.assert_called_with(
            "a blue sphere", outputs_b, reference_images=[], reference_strength=0.75
        )
        self.assertEqual(self.page._pending_path, path_b)

        self.page.accept_button.click()

        image_paths = [image.file_path for image in self.workspace_manager.current_workspace.images]
        self.assertEqual(image_paths, [path_b])


    # --- Mission 015: enlarged preview button ---

    def test_preview_enlarge_button_disabled_outside_pending(self):
        self.assertFalse(self.page.preview_enlarge_button.isEnabled())

        with patch("src.ui.pages.inference_page.QMessageBox.critical"):
            self.generation_manager.generate.side_effect = GenerationError("boom")
            self._generate()

        self.assertFalse(self.page.preview_enlarge_button.isEnabled())

    def test_preview_enlarge_button_enabled_only_while_pending(self):
        self._generate()
        self.assertTrue(self.page.preview_enlarge_button.isEnabled())

        self.page.accept_button.click()
        self.assertFalse(self.page.preview_enlarge_button.isEnabled())

    def test_preview_enlarge_button_with_no_pending_result_is_a_no_op(self):
        with patch("src.ui.pages.inference_page.ImagePreviewDialog") as mock_dialog_cls:
            self.page._on_enlarge_clicked()

        mock_dialog_cls.assert_not_called()

    def test_preview_enlarge_button_opens_dialog_with_pending_path(self):
        self._generate()

        with patch("src.ui.pages.inference_page.ImagePreviewDialog") as mock_dialog_cls:
            self.page.preview_enlarge_button.click()

        mock_dialog_cls.assert_called_once_with(self.generated_path, parent=self.page)
        mock_dialog_cls.return_value.exec.assert_called_once()

    def test_opening_enlarged_preview_leaves_pending_state_strictly_unchanged(self):
        self._generate()

        pending_path_before = self.page._pending_path
        pending_pixmap_before = self.page._pending_pixmap
        workspace_root_before = self.page._generation_workspace_root
        accept_enabled_before = self.page.accept_button.isEnabled()
        reject_enabled_before = self.page.reject_button.isEnabled()
        regenerate_enabled_before = self.page.regenerate_button.isEnabled()
        generate_enabled_before = self.page.generate_button.isEnabled()

        with patch("src.ui.pages.inference_page.ImagePreviewDialog") as mock_dialog_cls:
            self.page.preview_enlarge_button.click()

        mock_dialog_cls.return_value.exec.assert_called_once()

        self.assertEqual(self.page._pending_path, pending_path_before)
        self.assertIs(self.page._pending_pixmap, pending_pixmap_before)
        self.assertEqual(self.page._generation_workspace_root, workspace_root_before)
        self.assertEqual(self.page.accept_button.isEnabled(), accept_enabled_before)
        self.assertEqual(self.page.reject_button.isEnabled(), reject_enabled_before)
        self.assertEqual(self.page.regenerate_button.isEnabled(), regenerate_enabled_before)
        self.assertEqual(self.page.generate_button.isEnabled(), generate_enabled_before)
        self.assertTrue(Path(self.generated_path).exists())
        self.assertEqual(self.workspace_manager.current_workspace.images, [])

    def test_preview_enlarge_button_opened_twice_in_a_row_still_reflects_pending(self):
        self._generate()

        with patch("src.ui.pages.inference_page.ImagePreviewDialog") as mock_dialog_cls:
            self.page.preview_enlarge_button.click()
            self.page.preview_enlarge_button.click()

        self.assertEqual(mock_dialog_cls.call_count, 2)
        mock_dialog_cls.assert_called_with(self.generated_path, parent=self.page)
        self.assertEqual(mock_dialog_cls.return_value.exec.call_count, 2)
        self.assertEqual(self.page._pending_path, self.generated_path)
        self.assertEqual(self.workspace_manager.current_workspace.images, [])

    def test_opening_enlarged_preview_never_persists_deletes_or_saves(self):
        self._generate()

        with patch.object(
            self.workspace_manager, "add_images", wraps=self.workspace_manager.add_images
        ) as add_images_spy, patch.object(
            self.workspace_manager, "save", wraps=self.workspace_manager.save
        ) as save_spy, patch("src.ui.pages.inference_page.ImagePreviewDialog"):
            self.page.preview_enlarge_button.click()

            add_images_spy.assert_not_called()
            save_spy.assert_not_called()

        self.assertTrue(Path(self.generated_path).exists())

    # --- Mission 022: reference image selection and propagation ---

    def _select_reference(self, file_path):
        with patch(
            "src.ui.pages.inference_page.QFileDialog.getOpenFileName",
            return_value=(file_path, ""),
        ):
            self.page.select_reference_button.click()

    def test_reference_initial_state_is_empty(self):
        self.assertIsNone(self.page._reference_image_path)
        self.assertEqual(self.page.reference_label.text(), "Aucune référence sélectionnée")
        self.assertFalse(self.page.remove_reference_button.isEnabled())

    def test_selecting_a_reference_updates_state_label_and_remove_button(self):
        reference_path = str(Path(self.tmp_dir) / "portrait.png")

        self._select_reference(reference_path)

        self.assertEqual(self.page._reference_image_path, reference_path)
        self.assertEqual(self.page.reference_label.text(), "portrait.png — Pose / composition")
        self.assertTrue(self.page.remove_reference_button.isEnabled())

    def test_selecting_reference_cancelled_leaves_state_unchanged(self):
        self._select_reference("")

        self.assertIsNone(self.page._reference_image_path)
        self.assertEqual(self.page.reference_label.text(), "Aucune référence sélectionnée")
        self.assertFalse(self.page.remove_reference_button.isEnabled())

    def test_selecting_a_new_reference_replaces_the_previous_one(self):
        first_path = str(Path(self.tmp_dir) / "first.png")
        second_path = str(Path(self.tmp_dir) / "second.png")

        self._select_reference(first_path)
        self._select_reference(second_path)

        self.assertEqual(self.page._reference_image_path, second_path)
        self.assertEqual(self.page.reference_label.text(), "second.png — Pose / composition")

    def test_removing_reference_clears_state(self):
        reference_path = str(Path(self.tmp_dir) / "portrait.png")
        self._select_reference(reference_path)

        self.page.remove_reference_button.click()

        self.assertIsNone(self.page._reference_image_path)
        self.assertEqual(self.page.reference_label.text(), "Aucune référence sélectionnée")
        self.assertFalse(self.page.remove_reference_button.isEnabled())

    def test_generate_without_reference_sends_empty_list(self):
        self._generate()

        self.generation_manager.generate.assert_called_once_with(
            "a red fox", str(self.outputs_dir), reference_images=[], reference_strength=0.75
        )

    def test_generate_with_reference_sends_it_as_a_single_element_list(self):
        reference_path = str(Path(self.tmp_dir) / "portrait.png")
        self._select_reference(reference_path)

        self._generate()

        self.generation_manager.generate.assert_called_once_with(
            "a red fox",
            str(self.outputs_dir),
            reference_images=[Reference(reference_path, REFERENCE_ROLE_POSE_COMPOSITION)],
            reference_strength=0.75,
        )

    def test_changing_selection_after_launch_does_not_affect_the_in_flight_snapshot(self):
        # The property explicitly required by the architect: a
        # selection change made after Generate was clicked (while the
        # worker/thread are already running) must never be able to
        # alter the job that was already launched, since
        # GenerationWorker only ever holds a snapshot copied before
        # thread.start().
        first_reference = str(Path(self.tmp_dir) / "first.png")
        self._select_reference(first_reference)

        # Slow down generate() just enough to change the selection
        # while the worker thread is still running.
        def slow_generate(prompt_text, output_directory, reference_images=None, reference_strength=None):
            time.sleep(0.2)
            return self.generated_path

        self.generation_manager.generate.side_effect = slow_generate

        self.page.prompt.setPlainText("a red fox")
        self.page.generate_button.click()

        # Mutate the UI selection while the generation above is still
        # in flight on its own thread.
        second_reference = str(Path(self.tmp_dir) / "second.png")
        self._select_reference(second_reference)

        _pump(2.0)

        self.generation_manager.generate.assert_called_once_with(
            "a red fox",
            str(self.outputs_dir),
            reference_images=[Reference(first_reference, REFERENCE_ROLE_POSE_COMPOSITION)],
            reference_strength=0.75,
        )

    def test_reference_reset_on_workspace_switch(self):
        reference_path = str(Path(self.tmp_dir) / "portrait.png")
        self._select_reference(reference_path)

        folder_b = Path(self.tmp_dir) / "WorkspaceB"
        self.workspace_manager.create(folder_b)  # publishes WORKSPACE_CREATED

        self.assertIsNone(self.page._reference_image_path)
        self.assertEqual(self.page.reference_label.text(), "Aucune référence sélectionnée")
        self.assertFalse(self.page.remove_reference_button.isEnabled())

    def test_reference_never_persisted_into_workspace_images(self):
        reference_path = str(Path(self.tmp_dir) / "portrait.png")
        self._select_reference(reference_path)

        self._generate()
        self.page.accept_button.click()

        image_paths = [image.file_path for image in self.workspace_manager.current_workspace.images]
        self.assertEqual(image_paths, [self.generated_path])
        self.assertNotIn(reference_path, image_paths)

    def test_reference_controls_disabled_during_generation_and_still_disabled_while_pending(self):
        # Reference controls follow generate_button's own enabled state
        # exactly: both stay disabled for the entire pending window
        # (Accept/Reject/Regenerate is the only way forward from
        # there), and both only re-enable together once that decision
        # is made.
        reference_path = str(Path(self.tmp_dir) / "portrait.png")
        self._select_reference(reference_path)

        def slow_generate(prompt_text, output_directory, reference_images=None, reference_strength=None):
            time.sleep(0.2)
            return self.generated_path

        self.generation_manager.generate.side_effect = slow_generate

        self.page.prompt.setPlainText("a red fox")
        self.page.generate_button.click()

        self.assertFalse(self.page.select_reference_button.isEnabled())
        self.assertFalse(self.page.remove_reference_button.isEnabled())

        _pump(2.0)

        self.assertFalse(self.page.generate_button.isEnabled())
        self.assertFalse(self.page.select_reference_button.isEnabled())
        self.assertFalse(self.page.remove_reference_button.isEnabled())

        self.page.reject_button.click()

        self.assertTrue(self.page.select_reference_button.isEnabled())
        # The reference selection itself is untouched by Reject — only
        # WORKSPACE_CREATED/OPENED/CLOSED clears it (Mission 022 spec,
        # section 6) — so remove_reference_button reflects that a
        # reference is still selected.
        self.assertTrue(self.page.remove_reference_button.isEnabled())
        self.assertEqual(self.page._reference_image_path, reference_path)

    # --- Mission 024: reference strength slider ---

    def test_reference_strength_label_text(self):
        self.assertEqual(self.page.reference_strength_label.text(), "Force de transformation :")

    def test_reference_strength_slider_initial_state(self):
        self.assertEqual(self.page.reference_strength_slider.minimum(), 0)
        self.assertEqual(self.page.reference_strength_slider.maximum(), 100)
        self.assertEqual(self.page.reference_strength_slider.value(), 75)
        self.assertFalse(self.page.reference_strength_slider.isEnabled())
        self.assertEqual(self.page.reference_strength_value_label.text(), "0.75")

    def test_reference_strength_slider_enabled_when_reference_selected(self):
        reference_path = str(Path(self.tmp_dir) / "portrait.png")
        self._select_reference(reference_path)

        self.assertTrue(self.page.reference_strength_slider.isEnabled())

    def test_reference_strength_value_label_updates_immediately_on_slider_change(self):
        self.page.reference_strength_slider.setValue(10)
        self.assertEqual(self.page.reference_strength_value_label.text(), "0.10")

        self.page.reference_strength_slider.setValue(95)
        self.assertEqual(self.page.reference_strength_value_label.text(), "0.95")

    def test_generate_without_reference_forwards_default_reference_strength(self):
        # Sans référence, la valeur est tout de même transmise (0.75 par
        # défaut) mais GenerationManager ne l'utilise jamais — le chemin
        # txt2img reste inchangé (voir GenerationManagerReferenceStrengthTest).
        self._generate()

        _, kwargs = self.generation_manager.generate.call_args
        self.assertEqual(kwargs["reference_strength"], 0.75)
        self.assertEqual(kwargs["reference_images"], [])

    def test_generate_with_default_strength_forwards_0_75(self):
        reference_path = str(Path(self.tmp_dir) / "portrait.png")
        self._select_reference(reference_path)

        self._generate()

        self.generation_manager.generate.assert_called_once_with(
            "a red fox",
            str(self.outputs_dir),
            reference_images=[Reference(reference_path, REFERENCE_ROLE_POSE_COMPOSITION)],
            reference_strength=0.75,
        )

    def test_generate_with_custom_strength_forwards_converted_value(self):
        reference_path = str(Path(self.tmp_dir) / "portrait.png")
        self._select_reference(reference_path)
        self.page.reference_strength_slider.setValue(30)

        self._generate()

        self.generation_manager.generate.assert_called_once_with(
            "a red fox",
            str(self.outputs_dir),
            reference_images=[Reference(reference_path, REFERENCE_ROLE_POSE_COMPOSITION)],
            reference_strength=0.3,
        )

    def test_reference_strength_reset_after_removing_reference(self):
        reference_path = str(Path(self.tmp_dir) / "portrait.png")
        self._select_reference(reference_path)
        self.page.reference_strength_slider.setValue(20)

        self.page.remove_reference_button.click()

        self.assertEqual(self.page.reference_strength_slider.value(), 75)
        self.assertFalse(self.page.reference_strength_slider.isEnabled())
        self.assertEqual(self.page.reference_strength_value_label.text(), "0.75")

    def test_reference_strength_reset_after_workspace_switch(self):
        reference_path = str(Path(self.tmp_dir) / "portrait.png")
        self._select_reference(reference_path)
        self.page.reference_strength_slider.setValue(20)

        folder_b = Path(self.tmp_dir) / "WorkspaceB"
        self.workspace_manager.create(folder_b)  # publishes WORKSPACE_CREATED

        self.assertEqual(self.page.reference_strength_slider.value(), 75)
        self.assertFalse(self.page.reference_strength_slider.isEnabled())
        self.assertEqual(self.page.reference_strength_value_label.text(), "0.75")

    def test_reference_strength_slider_disabled_during_generation_and_reenabled_only_if_reference_kept(self):
        reference_path = str(Path(self.tmp_dir) / "portrait.png")
        self._select_reference(reference_path)

        def slow_generate(prompt_text, output_directory, reference_images=None, reference_strength=None):
            time.sleep(0.2)
            return self.generated_path

        self.generation_manager.generate.side_effect = slow_generate

        self.page.prompt.setPlainText("a red fox")
        self.page.generate_button.click()

        self.assertFalse(self.page.reference_strength_slider.isEnabled())

        _pump(2.0)
        self.page.reject_button.click()

        self.assertTrue(self.page.reference_strength_slider.isEnabled())

    def test_inference_page_module_never_references_the_comfyui_denoise_term(self):
        # Mission 024 architectural constraint: InferencePage manipulates
        # a generic "reference strength" concept only — the ComfyUI-
        # native name for this concept must stay confined to
        # ComfyUIEngine/comfyui_workflows.
        import inspect

        from src.ui.pages import inference_page

        source = Path(inspect.getfile(inference_page)).read_text(encoding="utf-8").lower()
        self.assertNotIn("denoise", source)

    def test_inference_page_and_prompts_page_never_import_ollamaengine_or_urllib(self):
        # Mission 031 architectural constraint: no UI page ever talks to
        # OllamaEngine/urllib directly — only PromptAssistantManager
        # (UI -> Manager -> AIBackend -> provider). Covers PromptsPage
        # too, its second real consumer since Mission 032, sharing the
        # same Manager instance unchanged.
        import inspect

        from src.ui.pages import inference_page, prompts_page

        for module in (inference_page, prompts_page):
            source = Path(inspect.getfile(module)).read_text(encoding="utf-8")
            self.assertNotIn("OllamaEngine", source)
            self.assertNotIn("urllib", source)


class InferencePagePromptAssistantTest(unittest.TestCase):
    """
    Mission 031: "Assistant IA" and "Enregistrer dans Prompts". A
    lightweight setUp — unlike InferencePageTest above, none of these
    tests exercise the generation cycle itself, so no real
    WorkspaceManager/tempdir is needed, only mocked Managers and the
    real InferencePage widgets.
    """

    def setUp(self):
        self.generation_manager = MagicMock()
        self.workspace_manager = MagicMock()
        self.workspace_manager.opened = True
        self.prompt_manager = MagicMock()
        self.prompt_assistant_manager = MagicMock()
        # Mission 034: no identity by default in this lightweight suite
        # — individual tests below opt into a real Character where the
        # CharacterContext resolution itself is under test.
        self.character_manager = MagicMock()
        self.character_manager.principal_character = None

        self.page = InferencePage(
            self.generation_manager,
            self.workspace_manager,
            self.prompt_manager,
            self.prompt_assistant_manager,
            self.character_manager,
        )
        self.addCleanup(self.page.shutdown)

    def test_save_prompt_button_disabled_when_prompt_is_empty(self):
        self.page.prompt.setPlainText("")
        self.assertFalse(self.page.save_prompt_button.isEnabled())

    def test_save_prompt_button_enabled_once_prompt_has_text(self):
        self.page.prompt.setPlainText("a red fox")
        self.assertTrue(self.page.save_prompt_button.isEnabled())

    def test_save_prompt_button_disabled_again_when_text_cleared(self):
        self.page.prompt.setPlainText("a red fox")
        self.page.prompt.setPlainText("")
        self.assertFalse(self.page.save_prompt_button.isEnabled())

    @patch("src.ui.pages.inference_page.QInputDialog.getText")
    def test_save_prompt_creates_via_prompt_manager_with_current_text_and_never_selects(self, mock_get_text):
        mock_get_text.return_value = ("My Prompt", True)
        self.prompt_manager.create.return_value = MagicMock(prompt_id="new-id")

        self.page.prompt.setPlainText("a red fox, cinematic")
        self.page.save_prompt_button.click()

        self.prompt_manager.create.assert_called_once_with("My Prompt", text="a red fox, cinematic")
        # Mission 031 verification 2: select()/update_text() must never
        # be called from here — active_prompt_id/PromptsPage's current
        # selection must never be silently changed.
        self.prompt_manager.select.assert_not_called()
        self.prompt_manager.update_text.assert_not_called()

    @patch("src.ui.pages.inference_page.QInputDialog.getText")
    def test_save_prompt_cancelled_dialog_does_not_create(self, mock_get_text):
        mock_get_text.return_value = ("", False)

        self.page.prompt.setPlainText("a red fox")
        self.page.save_prompt_button.click()

        self.prompt_manager.create.assert_not_called()

    @patch("src.ui.pages.inference_page.QInputDialog.getText")
    def test_save_prompt_blank_name_does_not_create(self, mock_get_text):
        mock_get_text.return_value = ("   ", True)

        self.page.prompt.setPlainText("a red fox")
        self.page.save_prompt_button.click()

        self.prompt_manager.create.assert_not_called()

    @patch("src.ui.pages.inference_page.QMessageBox.warning")
    @patch("src.ui.pages.inference_page.QInputDialog.getText")
    def test_save_prompt_no_principal_character_shows_warning(self, mock_get_text, mock_warning):
        # Mission 036: Workspace open (self.workspace_manager.opened is
        # True by default in setUp), zero Character — must show "Aucun
        # personnage", not "Aucun projet ouvert" (see the sibling test
        # below for the other cause of the same None).
        mock_get_text.return_value = ("My Prompt", True)
        self.prompt_manager.create.return_value = None

        self.page.prompt.setPlainText("a red fox")
        self.page.save_prompt_button.click()

        mock_warning.assert_called_once_with(
            self.page,
            "Aucun personnage",
            "Ce projet ne possède aucun personnage — créez-en un depuis Characters avant d'enregistrer un prompt."
        )

    @patch("src.ui.pages.inference_page.QMessageBox.warning")
    @patch("src.ui.pages.inference_page.QInputDialog.getText")
    def test_save_prompt_no_open_workspace_shows_no_project_warning(self, mock_get_text, mock_warning):
        # Mission 036: distinguishes "no Workspace open at all" from the
        # sibling test above ("Workspace open, zero Character") — both
        # make PromptManager.create() return None. InferencePage already
        # holds workspace_manager (Mission 013) — no new dependency.
        mock_get_text.return_value = ("My Prompt", True)
        self.prompt_manager.create.return_value = None
        self.workspace_manager.opened = False

        self.page.prompt.setPlainText("a red fox")
        self.page.save_prompt_button.click()

        mock_warning.assert_called_once_with(
            self.page,
            "Aucun projet ouvert",
            "Ouvrez ou créez un projet avant d'enregistrer un prompt."
        )

    @patch("src.ui.pages.inference_page.QMessageBox.critical")
    @patch("src.ui.pages.inference_page.QInputDialog.getText")
    def test_save_prompt_persistence_failure_shows_error_and_does_not_select_or_update(
        self, mock_get_text, mock_critical
    ):
        # Mission 072: PromptManager.create() now raises
        # WorkspaceManagerError on a save() failure instead of silently
        # leaving a phantom Prompt in memory — _on_save_prompt_clicked()
        # must catch it and show an error, same contract as every other
        # create() call site.
        mock_get_text.return_value = ("My Prompt", True)
        self.prompt_manager.create.side_effect = WorkspaceManagerError("disk full")

        self.page.prompt.setPlainText("a red fox")
        self.page.save_prompt_button.click()

        self.assertTrue(mock_critical.called)
        self.prompt_manager.select.assert_not_called()
        self.prompt_manager.update_text.assert_not_called()

    @patch("src.ui.pages.inference_page.PromptAssistantDialog")
    def test_assistant_dialog_receives_current_prompt_text(self, mock_dialog_class):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.Rejected
        mock_dialog_class.return_value = mock_dialog

        self.page.prompt.setPlainText("a red fox")
        self.page.assistant_button.click()

        _, kwargs = mock_dialog_class.call_args
        self.assertEqual(mock_dialog_class.call_args[0][0], self.prompt_assistant_manager)
        self.assertEqual(kwargs["existing_prompt"], "a red fox")

    @patch("src.ui.pages.inference_page.PromptAssistantDialog")
    def test_no_character_dialog_receives_none_context(self, mock_dialog_class):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.Rejected
        mock_dialog_class.return_value = mock_dialog

        self.character_manager.principal_character = None
        self.page.assistant_button.click()

        _, kwargs = mock_dialog_class.call_args
        self.assertIsNone(kwargs["character_context"])

    @patch("src.ui.pages.inference_page.PromptAssistantDialog")
    def test_character_with_identity_dialog_receives_the_resolved_context(self, mock_dialog_class):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.Rejected
        mock_dialog_class.return_value = mock_dialog

        self.character_manager.principal_character = Character(trigger_token="sks_amy")
        self.page.assistant_button.click()

        _, kwargs = mock_dialog_class.call_args
        self.assertEqual(kwargs["character_context"].trigger_token, "sks_amy")

    @patch("src.ui.pages.inference_page.PromptAssistantDialog")
    def test_character_with_no_usable_identity_dialog_receives_none_context(self, mock_dialog_class):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.Rejected
        mock_dialog_class.return_value = mock_dialog

        self.character_manager.principal_character = Character()
        self.page.assistant_button.click()

        _, kwargs = mock_dialog_class.call_args
        self.assertIsNone(kwargs["character_context"])

    @patch("src.ui.pages.inference_page.PromptAssistantDialog")
    def test_assistant_dialog_accepted_result_replaces_prompt_text(self, mock_dialog_class):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.Accepted
        mock_dialog.result_text = "a red fox, golden hour, cinematic"
        mock_dialog_class.return_value = mock_dialog

        self.page.prompt.setPlainText("a red fox")
        self.page.assistant_button.click()

        self.assertEqual(self.page.prompt.toPlainText(), "a red fox, golden hour, cinematic")

    @patch("src.ui.pages.inference_page.PromptAssistantDialog")
    def test_assistant_dialog_rejected_leaves_prompt_text_unchanged(self, mock_dialog_class):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.Rejected
        mock_dialog.result_text = None
        mock_dialog_class.return_value = mock_dialog

        self.page.prompt.setPlainText("a red fox")
        self.page.assistant_button.click()

        self.assertEqual(self.page.prompt.toPlainText(), "a red fox")

    def test_prompt_text_returns_exact_editor_content(self):
        self.page.prompt.setPlainText("a red fox,  cinematic\nnight")
        self.assertEqual(self.page.prompt_text(), "a red fox,  cinematic\nnight")

    def test_set_prompt_text_replaces_editor_content(self):
        self.page.prompt.setPlainText("old content")
        self.page.set_prompt_text("a red fox, golden hour")

        self.assertEqual(self.page.prompt.toPlainText(), "a red fox, golden hour")

    def test_set_prompt_text_does_not_trigger_prompt_manager(self):
        # Mission 033: this is purely a widget write — never a save/
        # persistence side effect (see MISSION_033.md section 9).
        self.page.set_prompt_text("a red fox")

        self.prompt_manager.update_text.assert_not_called()
        self.prompt_manager.create.assert_not_called()


class InferencePagePromptDirtyStateTest(unittest.TestCase):
    """
    Mission 083: InferencePage.prompt's own dirty-draft protection,
    mirroring PromptsPage/CharactersPage/LoRAPage/SettingsPage's
    contract (Missions 038/078) — confirm_context_change(), a local
    _dirty flag, and a dedicated reset_for_context_change() strictly
    separate from reset_for_workspace_change()'s own unrelated
    _pending_path/reference responsibility. Same lightweight
    mocked-Manager setUp as InferencePagePromptAssistantTest above —
    none of these tests exercise the generation cycle itself.
    """

    def setUp(self):
        self.generation_manager = MagicMock()
        self.workspace_manager = MagicMock()
        self.workspace_manager.opened = True
        self.prompt_manager = MagicMock()
        self.prompt_assistant_manager = MagicMock()
        self.character_manager = MagicMock()
        self.character_manager.principal_character = MagicMock()

        self.page = InferencePage(
            self.generation_manager,
            self.workspace_manager,
            self.prompt_manager,
            self.prompt_assistant_manager,
            self.character_manager,
        )
        self.addCleanup(self.page.shutdown)

    def test_manual_typing_marks_dirty(self):
        self.assertFalse(self.page._dirty)

        self.page.prompt.setPlainText("a red fox")

        self.assertTrue(self.page._dirty)

    @patch("src.ui.pages.inference_page.PromptAssistantDialog")
    def test_prompt_assistant_result_marks_dirty(self, mock_dialog_class):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.Accepted
        mock_dialog.result_text = "a red fox, cinematic"
        mock_dialog_class.return_value = mock_dialog

        self.page.assistant_button.click()

        self.assertEqual(self.page.prompt.toPlainText(), "a red fox, cinematic")
        self.assertTrue(self.page._dirty)

    def test_set_prompt_text_is_not_dirty_initially(self):
        self.page.set_prompt_text("from prompts page")

        self.assertEqual(self.page.prompt.toPlainText(), "from prompts page")
        self.assertFalse(self.page._dirty)
        self.assertTrue(self.page.save_prompt_button.isEnabled())

    def test_editing_after_set_prompt_text_marks_dirty(self):
        self.page.set_prompt_text("from prompts page")

        self.page.prompt.setPlainText("from prompts page, edited")

        self.assertTrue(self.page._dirty)

    def test_reset_for_context_change_clears_prompt_and_dirty(self):
        self.page.prompt.setPlainText("a red fox")
        self.assertTrue(self.page._dirty)

        self.page.reset_for_context_change()

        self.assertEqual(self.page.prompt.toPlainText(), "")
        self.assertFalse(self.page._dirty)
        self.assertFalse(self.page.save_prompt_button.isEnabled())

    def test_workspace_rename_preserves_prompt_and_dirty_state(self):
        # Mission 083 mini-audit finding: reset_for_workspace_change()
        # (WORKSPACE_RENAMED included, for _pending_path's own reason)
        # must never clear the prompt — only reset_for_context_change()
        # (CREATED/OPENED/CLOSED only) does that.
        self.page.prompt.setPlainText("a red fox")
        self.assertTrue(self.page._dirty)

        self.page.reset_for_workspace_change()

        self.assertEqual(self.page.prompt.toPlainText(), "a red fox")
        self.assertTrue(self.page._dirty)

    def test_confirm_context_change_returns_true_immediately_when_not_dirty(self):
        self.assertFalse(self.page._dirty)

        with patch.object(self.page, "_confirm_discard_before_switch") as mock_confirm:
            self.assertTrue(self.page.confirm_context_change())

        mock_confirm.assert_not_called()

    def test_confirm_context_change_blank_dirty_text_returns_true_without_dialog(self):
        self.page.prompt.setPlainText("a red fox")
        self.page.prompt.setPlainText("")
        self.assertTrue(self.page._dirty)

        with patch.object(self.page, "_confirm_discard_before_switch") as mock_confirm:
            self.assertTrue(self.page.confirm_context_change())

        mock_confirm.assert_not_called()
        self.assertFalse(self.page._dirty)

    def test_confirm_context_change_cancel_refuses_transition_and_keeps_draft(self):
        self.page.prompt.setPlainText("a red fox")

        with patch.object(self.page, "_confirm_discard_before_switch", return_value=QMessageBox.Cancel):
            self.assertFalse(self.page.confirm_context_change())

        self.assertTrue(self.page._dirty)
        self.assertEqual(self.page.prompt.toPlainText(), "a red fox")
        self.prompt_manager.create.assert_not_called()

    def test_confirm_context_change_discard_authorizes_transition_without_creating(self):
        self.page.prompt.setPlainText("a red fox")

        with patch.object(self.page, "_confirm_discard_before_switch", return_value=QMessageBox.Discard):
            self.assertTrue(self.page.confirm_context_change())

        self.prompt_manager.create.assert_not_called()

    @patch("src.ui.pages.inference_page.QInputDialog.getText")
    def test_confirm_context_change_save_creates_prompt_and_authorizes_transition(self, mock_get_text):
        mock_get_text.return_value = ("My Prompt", True)
        self.prompt_manager.create.return_value = MagicMock(prompt_id="new-id")
        self.page.prompt.setPlainText("a red fox")

        with patch.object(self.page, "_confirm_discard_before_switch", return_value=QMessageBox.Save):
            self.assertTrue(self.page.confirm_context_change())

        self.prompt_manager.create.assert_called_once_with("My Prompt", text="a red fox")
        self.assertFalse(self.page._dirty)

    @patch("src.ui.pages.inference_page.QInputDialog.getText")
    def test_confirm_context_change_save_name_cancelled_refuses_transition(self, mock_get_text):
        mock_get_text.return_value = ("", False)
        self.page.prompt.setPlainText("a red fox")

        with patch.object(self.page, "_confirm_discard_before_switch", return_value=QMessageBox.Save):
            self.assertFalse(self.page.confirm_context_change())

        self.prompt_manager.create.assert_not_called()
        self.assertTrue(self.page._dirty)
        self.assertEqual(self.page.prompt.toPlainText(), "a red fox")

    @patch("src.ui.pages.inference_page.QInputDialog.getText")
    def test_confirm_context_change_save_blank_name_refuses_transition(self, mock_get_text):
        mock_get_text.return_value = ("   ", True)
        self.page.prompt.setPlainText("a red fox")

        with patch.object(self.page, "_confirm_discard_before_switch", return_value=QMessageBox.Save):
            self.assertFalse(self.page.confirm_context_change())

        self.prompt_manager.create.assert_not_called()
        self.assertTrue(self.page._dirty)

    @patch("src.ui.pages.inference_page.QMessageBox.warning")
    @patch("src.ui.pages.inference_page.QInputDialog.getText")
    def test_confirm_context_change_save_no_character_refuses_transition(self, mock_get_text, mock_warning):
        mock_get_text.return_value = ("My Prompt", True)
        self.prompt_manager.create.return_value = None
        self.page.prompt.setPlainText("a red fox")

        with patch.object(self.page, "_confirm_discard_before_switch", return_value=QMessageBox.Save):
            self.assertFalse(self.page.confirm_context_change())

        self.assertTrue(mock_warning.called)
        self.assertTrue(self.page._dirty)
        self.assertEqual(self.page.prompt.toPlainText(), "a red fox")

    @patch("src.ui.pages.inference_page.QMessageBox.critical")
    @patch("src.ui.pages.inference_page.QInputDialog.getText")
    def test_confirm_context_change_save_persistence_failure_refuses_transition(self, mock_get_text, mock_critical):
        mock_get_text.return_value = ("My Prompt", True)
        self.prompt_manager.create.side_effect = WorkspaceManagerError("disk full")
        self.page.prompt.setPlainText("a red fox")

        with patch.object(self.page, "_confirm_discard_before_switch", return_value=QMessageBox.Save):
            self.assertFalse(self.page.confirm_context_change())

        self.assertTrue(mock_critical.called)
        self.assertTrue(self.page._dirty)
        self.assertEqual(self.page.prompt.toPlainText(), "a red fox")

    @patch("src.ui.pages.inference_page.QInputDialog.getText")
    def test_save_prompt_button_click_clears_dirty_on_success(self, mock_get_text):
        mock_get_text.return_value = ("My Prompt", True)
        self.prompt_manager.create.return_value = MagicMock(prompt_id="new-id")
        self.page.prompt.setPlainText("a red fox")
        self.assertTrue(self.page._dirty)

        self.page.save_prompt_button.click()

        self.assertFalse(self.page._dirty)


if __name__ == "__main__":
    unittest.main()
