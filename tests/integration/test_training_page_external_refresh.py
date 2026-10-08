"""
Mission 175: TrainingPage's job rows and Start button depend on state that
lives outside the Workspace -- a Central LoRA Library entry (deleted or
renamed) and ApplicationSettings.onetrainer_path -- and used to be
refreshed only by unrelated Workspace/Training events. These tests drive
the REAL wiring: a real MainWindow, its real EventBus, real Managers and
the real TrainingPage computation. Nothing is refreshed by hand after a
trigger: each test changes the external state through the real Manager
(LoRALibraryManager.delete()/update(), ApplicationSettingsManager.update())
and then reads what the page displays.

Isolation. A real MainWindow reads and writes the machine-local
ApplicationSettings and Central LoRA Library locations. setUp therefore
points LOCALAPPDATA, USERPROFILE and HOME at a private temporary tree
before the window is built and fails the test outright if any of those
locations does not resolve under it. A tripwire makes any Python-level
socket connection fail. No engine, process or training is started.

Declared substitutions (none of them replaces the EventBus, a subscription
or the computation under study):
  * QMessageBox's static dialogs and QMessageBox.exec() are replaced by
    recorders returning a harmless button;
  * QInputDialog.getText() of the training_page module returns a fixed name
    for the import flow (as the existing tests do);
  * Dataset.images is assigned directly and the OneTrainer "installation"
    is a pair of empty placeholder files that are only ever checked for
    existence (never executed);
  * "active job" tests install a MagicMock as the page's runner; no
    process is created.

Cleanup. Every test builds a real MainWindow, so every test must also dispose of it, whether its assertions pass or
fail. The cleanup runs after the test's own assertions (a draft or a fake runner is never neutralised before the
assertion that protects it). It then abandons the test doubles and the unsaved drafts WITHOUT saving them (the fake
runner and job markers, the parameter draft flag, and the rename draft by restoring the loaded name so that no focus loss
can commit it), requires that close() is accepted and that no dialog was opened by the production close guards, requests
the deferred deletion, delivers the deferred-delete events explicitly and requires that the window and its page are
really destroyed. The isolated environment and the declared replacements stay active until then (cleanups run in
reverse order of registration). The outcome of every disposal is also written to the standard error stream at the end of
the module, so that a run shows the verification, not only the absence of failure.

Spies and the EventBus. The EventBus keeps the bound methods captured at
subscription time, so replacing an attribute on the page afterwards would
not observe the callbacks the bus really invokes. The bus-level spy below
wraps each stored callback in place (same callable underneath) and records
the owner and name of every callback actually invoked.
"""

import os
import shutil
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QMessageBox
from shiboken6 import isValid

from src.domain.image import Image
from src.infrastructure.storage.application_settings_storage import ApplicationSettingsStorage
from src.infrastructure.storage.lora_library_storage import LoRALibraryStorage
from src.managers.application_settings_manager import APPLICATION_SETTINGS_UPDATED
from src.managers.lora_library_manager import (
    LORA_LIBRARY_DELETED,
    LORA_LIBRARY_IMPORTED,
    LORA_LIBRARY_UPDATED,
)
from src.managers.training_manager import (
    TRAINING_ARCHITECTURE_SD15,
    TRAINING_JOB_STATE_SUCCEEDED,
)
from src.managers.workspace_lifecycle import create_workspace_with_default_character
from src.managers.workspace_manager import WorkspaceManagerError
from src.ui.main_window import MainWindow

_app = QApplication.instance() or QApplication([])

# One entry per disposed MainWindow: (test id, close accepted, dialogs opened by the close guards, window destroyed,
# page destroyed). Printed by tearDownModule().
_DISPOSAL_LOG = []

CONFIGURE_HINT = "Configurez OneTrainer"
RUNNING_LABEL = "Entraînement en cours"
CANCELLING_LABEL = "Annulation en cours"
DEFERRED_LABEL = "Résultat d'entraînement non enregistré"

EXTERNAL_EVENTS = (LORA_LIBRARY_DELETED, LORA_LIBRARY_UPDATED, APPLICATION_SETTINGS_UPDATED)


class _IsolatedWindowCase(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.root = Path(self.tmp_dir)

        env = {
            "LOCALAPPDATA": str(self.root / "localappdata"),
            "USERPROFILE": str(self.root / "home"),
            "HOME": str(self.root / "home"),
        }
        env_patcher = patch.dict(os.environ, env)
        env_patcher.start()
        self.addCleanup(env_patcher.stop)
        (self.root / "localappdata").mkdir()
        (self.root / "home").mkdir()

        from src.domain.application_settings import ApplicationSettings

        for label, location in (
            ("application settings", ApplicationSettingsStorage.default_directory()),
            ("LoRA library registry", LoRALibraryStorage.default_directory()),
            ("default LoRA library path", ApplicationSettings().lora_library_path),
            ("home", Path.home()),
        ):
            self.assertTrue(
                os.path.normcase(str(location)).startswith(os.path.normcase(str(self.root))),
                f"isolation failed: {label} resolves outside the private tree: {location}",
            )

        self.dialogs = []
        for name, result in (
            ("information", QMessageBox.Ok),
            ("warning", QMessageBox.Ok),
            ("critical", QMessageBox.Ok),
            ("question", QMessageBox.No),
        ):
            patcher = patch.object(QMessageBox, name, side_effect=self._recorder(name, result))
            patcher.start()
            self.addCleanup(patcher.stop)

        def _fake_exec(box, *args, **kwargs):
            self.dialogs.append(("exec", [box.text()]))
            return QMessageBox.Cancel

        exec_patcher = patch.object(QMessageBox, "exec", _fake_exec)
        exec_patcher.start()
        self.addCleanup(exec_patcher.stop)

        network_patcher = patch.object(
            socket.socket, "connect", side_effect=AssertionError("network access is forbidden in this test")
        )
        network_patcher.start()
        self.addCleanup(network_patcher.stop)

        self.library_root = self.root / "lora_library_root"
        self.library_root.mkdir()

        self.window = MainWindow()
        self.addCleanup(self._close_window)
        self.page = self.window.training_page

    def _recorder(self, name, result):
        def _fake(*args, **kwargs):
            self.dialogs.append((name, [a for a in args if isinstance(a, str)]))
            return result

        return _fake

    def _close_window(self):
        window, page = self.window, self.page
        destroyed = []
        window.destroyed.connect(lambda *_args: destroyed.append(True))

        # The test's assertions have all run: abandon the test doubles and the drafts, without saving anything.
        # The rename draft is abandoned by restoring the loaded name, so that a focus loss during the close can
        # never commit it through editingFinished.
        page._active_runner = None
        page._active_job_id = None
        page._cancel_in_flight = False
        page._deferred_job_id = None
        page._dirty = False
        page.name_edit.setText(page._name_editor_loaded_value)

        dialogs_before_close = len(self.dialogs)
        closed = False
        try:
            closed = window.close()
        finally:
            dialogs_opened_by_close = len(self.dialogs) - dialogs_before_close
            window.deleteLater()
            # Deferred deletions are only delivered from an event loop; deliver them explicitly.
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            _app.processEvents()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            window_destroyed = bool(destroyed) and not isValid(window)
            page_destroyed = not isValid(page)
            _DISPOSAL_LOG.append((self.id(), closed, dialogs_opened_by_close, window_destroyed, page_destroyed))

        self.assertTrue(closed, "MainWindow.close() was refused by a production close guard")
        self.assertEqual(dialogs_opened_by_close, 0, "a close guard opened a dialog")
        self.assertTrue(window_destroyed, "the MainWindow was not destroyed after deleteLater()")
        self.assertTrue(page_destroyed, "the TrainingPage was not destroyed with its window")

    # -- scenario builders -------------------------------------------------------------------------------------

    def make_onetrainer_dir(self, name, valid):
        folder = self.root / name
        folder.mkdir()
        if valid:
            (folder / "venv" / "Scripts").mkdir(parents=True)
            (folder / "scripts").mkdir()
            (folder / "venv" / "Scripts" / "python.exe").write_bytes(b"")
            (folder / "scripts" / "train_remote.py").write_bytes(b"")
        return folder

    def make_workspace_with_training(self, jobs=0, onetrainer_path=None):
        w = self.window
        w.application_settings_manager.update(lora_library_path=str(self.library_root))
        if onetrainer_path is not None:
            w.application_settings_manager.update(onetrainer_path=str(onetrainer_path))

        create_workspace_with_default_character(
            w.workspace_manager, w.character_manager, self.root / "project"
        )
        dataset = w.dataset_manager.create("Portraits")
        image_path = self.root / "a.png"
        image_path.write_bytes(b"fake-png-bytes")
        dataset.images = [Image(image_id=str(image_path), file_path=str(image_path))]

        training = w.training_manager.create("Session 1", dataset.dataset_id)
        w.training_manager.select(training.training_id)
        w.training_manager.update(
            base_model_source="models/v1-5-pruned.safetensors",
            architecture=TRAINING_ARCHITECTURE_SD15,
            resolution=512,
        )

        job_ids = []
        if jobs:
            w.training_manager.prepare_onetrainer_config(training.training_id)
            for _ in range(jobs):
                job = w.training_manager.create_job(training.training_id)
                output = Path(job.expected_output_path)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"fake-lora-bytes")
                w.training_manager.update_job_state(
                    job.job_id, TRAINING_JOB_STATE_SUCCEEDED, final_output_path=str(output)
                )
                job_ids.append(job.job_id)

        _app.processEvents()
        w.sidebar.select_page("training")
        _app.processEvents()
        return training, job_ids

    # -- page readers / actions --------------------------------------------------------------------------------

    def rows(self):
        return {
            self.page.jobs_list.item(i).data(Qt.UserRole): self.page.jobs_list.item(i).text()
            for i in range(self.page.jobs_list.count())
        }

    def current_job_id(self):
        item = self.page.jobs_list.currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    def select_job(self, job_id):
        for i in range(self.page.jobs_list.count()):
            item = self.page.jobs_list.item(i)
            if item.data(Qt.UserRole) == job_id:
                self.page.jobs_list.setCurrentItem(item)
                return
        self.fail(f"no job row for {job_id!r}")

    def import_selected_job(self, name="Imported LoRA"):
        with patch("src.ui.pages.training_page.QInputDialog.getText", return_value=(name, True)):
            self.page.import_lora_button.click()
        _app.processEvents()

    def imported_lora_id(self):
        return self.window.lora_library_manager.list_loras()[0].lora_id

    def page_callbacks(self, event_name):
        """Names of the callbacks of TrainingPage currently stored for `event_name` on the real bus."""
        return sorted(
            getattr(callback, "__name__", repr(callback))
            for callback in self.window.event_bus._subscribers[event_name]
            if getattr(callback, "__self__", None) is self.page
        )

    def spy_on_bus(self):
        """Wrap every stored callback in place; returns the list that records (event, owner, name) of each invocation."""
        calls = []
        for event_name, callbacks in self.window.event_bus._subscribers.items():
            wrapped = []
            for callback in callbacks:
                def make(callback=callback, event_name=event_name):
                    def spy(payload):
                        calls.append((event_name, getattr(callback, "__self__", None), getattr(callback, "__name__", repr(callback))))
                        return callback(payload)

                    return spy

                wrapped.append(make())
            callbacks[:] = wrapped
        return calls

    def page_calls(self, calls, event_name):
        return [name for (event, owner, name) in calls if event == event_name and owner is self.page]


class TrainingPageLibraryRefreshTest(_IsolatedWindowCase):
    """Library deletions and renames reach the job rows through the real bus (no manual refresh)."""

    def _imported_single_job(self):
        _training, job_ids = self.make_workspace_with_training(jobs=1)
        job_id = job_ids[0]
        self.select_job(job_id)
        self.assertIn("importable", self.rows()[job_id])
        self.import_selected_job()
        self.assertIn("importé : Imported LoRA", self.rows()[job_id])
        self.assertFalse(self.page.import_lora_button.isEnabled())
        self.assertTrue(self.page.use_lora_in_inference_button.isEnabled())
        return job_id

    def test_deleting_the_imported_lora_updates_the_row_and_the_buttons(self):
        job_id = self._imported_single_job()
        lora_id = self.imported_lora_id()

        self.window.sidebar.select_page("lora")
        result = self.window.lora_library_manager.delete(lora_id, str(self.library_root))
        self.assertTrue(result.deleted)
        self.window.sidebar.select_page("training")
        _app.processEvents()

        self.assertIsNone(self.window.lora_library_manager.get(lora_id))
        self.assertIn("LoRA supprimé, réimport possible", self.rows()[job_id])
        self.assertTrue(self.page.import_lora_button.isEnabled())
        self.assertFalse(self.page.use_lora_in_inference_button.isEnabled())
        self.assertEqual(self.current_job_id(), job_id)

    def test_renaming_the_imported_lora_updates_the_row(self):
        job_id = self._imported_single_job()
        lora_id = self.imported_lora_id()

        changed = self.window.lora_library_manager.update(lora_id, name="Renamed LoRA")
        _app.processEvents()

        self.assertTrue(changed)
        self.assertIn("importé : Renamed LoRA", self.rows()[job_id])
        self.assertNotIn("Imported LoRA", self.rows()[job_id])
        self.assertFalse(self.page.import_lora_button.isEnabled())
        self.assertTrue(self.page.use_lora_in_inference_button.isEnabled())
        self.assertEqual(self.current_job_id(), job_id)

    def test_the_selected_job_survives_among_several_jobs(self):
        _training, job_ids = self.make_workspace_with_training(jobs=2)
        job_a, job_b = job_ids
        self.select_job(job_b)
        self.import_selected_job()
        self.assertIn("importé", self.rows()[job_b])
        self.assertIn("importable", self.rows()[job_a])
        lora_id = self.imported_lora_id()

        self.window.lora_library_manager.delete(lora_id, str(self.library_root))
        _app.processEvents()

        self.assertEqual(self.current_job_id(), job_b)
        self.assertIn("LoRA supprimé, réimport possible", self.rows()[job_b])
        self.assertIn("importable", self.rows()[job_a])
        self.assertEqual(self.page.jobs_list.count(), 2)

    def test_the_page_never_trusts_the_event_payload_as_state(self):
        job_id = self._imported_single_job()
        lora_id = self.imported_lora_id()

        with self.assertNoLogs("src.core.event_bus", level="ERROR"):
            # An event that claims a deletion which did not happen: the Managers still hold the entry.
            self.window.event_bus.publish(LORA_LIBRARY_DELETED, {"lora_id": lora_id})
            self.window.event_bus.publish(LORA_LIBRARY_UPDATED, {"lora_id": lora_id, "name": "Not the real name"})
            self.window.event_bus.publish(LORA_LIBRARY_UPDATED, None)
            self.window.event_bus.publish(
                APPLICATION_SETTINGS_UPDATED, {"onetrainer_path": str(self.make_onetrainer_dir("claimed", True))}
            )
        _app.processEvents()

        self.assertIn("importé : Imported LoRA", self.rows()[job_id])
        self.assertTrue(self.page.use_lora_in_inference_button.isEnabled())
        self.assertFalse(self.page.start_training_button.isEnabled())
        self.assertIn(CONFIGURE_HINT, self.page.job_state_label.text())


class TrainingPageOneTrainerSettingRefreshTest(_IsolatedWindowCase):
    """The Start button follows ApplicationSettings.onetrainer_path through the real bus, in both directions."""

    def test_configuring_a_recognized_path_enables_start(self):
        self.make_workspace_with_training()
        self.assertFalse(self.page.start_training_button.isEnabled())
        self.assertIn(CONFIGURE_HINT, self.page.job_state_label.text())

        valid = self.make_onetrainer_dir("onetrainer_valid", True)
        self.assertTrue(self.window.application_settings_manager.update(onetrainer_path=str(valid)))
        self.window.sidebar.select_page("settings")
        self.window.sidebar.select_page("training")
        _app.processEvents()

        self.assertTrue(self.page.start_training_button.isEnabled())
        self.assertEqual(self.page.job_state_label.text(), "")

    def test_invalidating_a_configured_path_disables_start_again(self):
        valid = self.make_onetrainer_dir("onetrainer_valid", True)
        self.make_workspace_with_training(onetrainer_path=valid)
        # Naturally enabled by the existing Workspace/Training events, no refresh of ours involved.
        self.assertTrue(self.page.start_training_button.isEnabled())
        self.assertEqual(self.page.job_state_label.text(), "")

        invalid = self.make_onetrainer_dir("onetrainer_invalid", False)
        self.assertTrue(self.window.application_settings_manager.update(onetrainer_path=str(invalid)))
        self.window.sidebar.select_page("settings")
        self.window.sidebar.select_page("training")
        _app.processEvents()

        self.assertFalse(self.page.start_training_button.isEnabled())
        self.assertIn(CONFIGURE_HINT, self.page.job_state_label.text())


class TrainingPageSubscriptionContractTest(_IsolatedWindowCase):
    """What the page registers on the real bus, and what the bus really invokes."""

    def test_the_entry_point_accepts_the_event_payload_or_none(self):
        self.make_workspace_with_training()
        with self.assertNoLogs("src.core.event_bus", level="ERROR"):
            self.page.refresh_job_controls()
            self.page.refresh_job_controls(None)
            self.page.refresh_job_controls({"any": "payload"})

    def test_the_page_is_subscribed_to_exactly_the_external_events_it_needs(self):
        for event_name in EXTERNAL_EVENTS:
            self.assertEqual(self.page_callbacks(event_name), ["refresh_job_controls"], event_name)

    def test_the_page_has_no_callback_on_the_import_event(self):
        # The import flow keeps its own refreshes; LORA_LIBRARY_IMPORTED is published before the job is linked.
        self.assertEqual(self.page_callbacks(LORA_LIBRARY_IMPORTED), [])

    def test_the_bus_invokes_only_the_thin_entry_point_for_the_external_events(self):
        _training, job_ids = self.make_workspace_with_training(jobs=1)
        self.select_job(job_ids[0])
        self.import_selected_job()
        lora_id = self.imported_lora_id()
        valid = self.make_onetrainer_dir("onetrainer_valid", True)

        calls = self.spy_on_bus()
        self.window.lora_library_manager.update(lora_id, name="Renamed LoRA")
        self.window.application_settings_manager.update(onetrainer_path=str(valid))
        self.window.lora_library_manager.delete(lora_id, str(self.library_root))

        self.assertEqual(self.page_calls(calls, LORA_LIBRARY_UPDATED), ["refresh_job_controls"])
        self.assertEqual(self.page_calls(calls, APPLICATION_SETTINGS_UPDATED), ["refresh_job_controls"])
        self.assertEqual(self.page_calls(calls, LORA_LIBRARY_DELETED), ["refresh_job_controls"])
        # None of the general page refreshes was invoked by these events (workspace events are not involved).
        general = [
            name for (_event, owner, name) in calls
            if owner is self.page and name in ("update_trainings", "reset_for_context_change")
        ]
        self.assertEqual(general, [])


class TrainingPageDraftsAndStatesTest(_IsolatedWindowCase):
    """Unsaved drafts, the selection and the job-lifecycle states are preserved by the new refreshes."""

    def _dirty_page(self):
        self.page.epochs_spinbox.setValue(self.page.epochs_spinbox.value() + 3)
        self.page.name_edit.setText("Unsaved rename draft")
        self.assertTrue(self.page._dirty)
        return self._snapshot()

    def _snapshot(self):
        return {
            "epochs": self.page.epochs_spinbox.value(),
            "dirty": self.page._dirty,
            "loaded_training_id": self.page._loaded_training_id,
            "name_text": self.page.name_edit.text(),
            "name_loaded": self.page._name_editor_loaded_value,
            "name_owner": self.page._name_editor_owner_id,
        }

    def test_unsaved_drafts_are_untouched_while_the_rows_are_refreshed(self):
        _training, job_ids = self.make_workspace_with_training(jobs=1)
        job_id = job_ids[0]
        self.select_job(job_id)
        self.import_selected_job()
        lora_id = self.imported_lora_id()
        valid = self.make_onetrainer_dir("onetrainer_valid", True)

        before = self._dirty_page()
        with patch.object(self.page, "_load_training_parameters", wraps=self.page._load_training_parameters) as load_parameters, \
                patch.object(self.page, "_reload_name_editor", wraps=self.page._reload_name_editor) as reload_name:
            self.window.lora_library_manager.update(lora_id, name="Renamed LoRA")
            self.assertEqual(self._snapshot(), before)
            self.assertIn("importé : Renamed LoRA", self.rows()[job_id])

            self.window.application_settings_manager.update(onetrainer_path=str(valid))
            self.assertEqual(self._snapshot(), before)

            self.window.lora_library_manager.delete(lora_id, str(self.library_root))
            self.assertEqual(self._snapshot(), before)
            self.assertIn("LoRA supprimé, réimport possible", self.rows()[job_id])

            load_parameters.assert_not_called()
            reload_name.assert_not_called()
        self.assertEqual(self.current_job_id(), job_id)

    def test_no_workspace_no_error_and_nothing_to_enable(self):
        library_file = self.root / "lora.safetensors"
        library_file.write_bytes(b"fake")
        valid = self.make_onetrainer_dir("onetrainer_valid", True)
        w = self.window
        w.application_settings_manager.update(lora_library_path=str(self.library_root))

        with self.assertNoLogs("src.core.event_bus", level="ERROR"):
            lora = w.lora_library_manager.import_lora("Solo", [str(library_file)], library_root=self.library_root)
            w.lora_library_manager.update(lora.lora_id, name="Solo renamed")
            w.application_settings_manager.update(onetrainer_path=str(valid))
            w.lora_library_manager.delete(lora.lora_id, str(self.library_root))
        _app.processEvents()

        self.assertFalse(w.workspace_manager.opened)
        self.assertFalse(self.page.start_training_button.isEnabled())
        self.assertFalse(self.page.cancel_training_button.isEnabled())
        self.assertFalse(self.page.import_lora_button.isEnabled())
        self.assertFalse(self.page.use_lora_in_inference_button.isEnabled())
        self.assertEqual(self.page.jobs_list.count(), 0)

    def test_workspace_without_a_training_no_error_and_start_stays_disabled(self):
        w = self.window
        create_workspace_with_default_character(w.workspace_manager, w.character_manager, self.root / "project")
        valid = self.make_onetrainer_dir("onetrainer_valid", True)

        with self.assertNoLogs("src.core.event_bus", level="ERROR"):
            w.application_settings_manager.update(onetrainer_path=str(valid))
        _app.processEvents()

        self.assertIsNone(w.training_manager.active_training_id)
        self.assertFalse(self.page.start_training_button.isEnabled())
        self.assertEqual(self.page.jobs_list.count(), 0)

    def test_an_active_job_keeps_start_disabled_and_cancel_available(self):
        _training, job_ids = self.make_workspace_with_training(jobs=1)
        self.page._active_runner = MagicMock()
        self.page._active_job_id = job_ids[0]
        valid = self.make_onetrainer_dir("onetrainer_valid", True)

        with self.assertNoLogs("src.core.event_bus", level="ERROR"):
            self.window.application_settings_manager.update(onetrainer_path=str(valid))

        self.assertFalse(self.page.start_training_button.isEnabled())
        self.assertTrue(self.page.cancel_training_button.isEnabled())
        self.assertIn(RUNNING_LABEL, self.page.job_state_label.text())

    def test_a_cancellation_in_flight_keeps_cancel_disabled(self):
        _training, job_ids = self.make_workspace_with_training(jobs=1)
        self.page._active_runner = MagicMock()
        self.page._active_job_id = job_ids[0]
        self.page._cancel_in_flight = True
        valid = self.make_onetrainer_dir("onetrainer_valid", True)

        with self.assertNoLogs("src.core.event_bus", level="ERROR"):
            self.window.application_settings_manager.update(onetrainer_path=str(valid))

        self.assertFalse(self.page.start_training_button.isEnabled())
        self.assertFalse(self.page.cancel_training_button.isEnabled())
        self.assertIn(CANCELLING_LABEL, self.page.job_state_label.text())
        self.assertTrue(self.page._cancel_in_flight)

    def test_an_unrecorded_terminal_result_keeps_start_withheld(self):
        _training, job_ids = self.make_workspace_with_training(jobs=1)
        self.page._deferred_job_id = job_ids[0]
        valid = self.make_onetrainer_dir("onetrainer_valid", True)

        with self.assertNoLogs("src.core.event_bus", level="ERROR"):
            self.window.application_settings_manager.update(onetrainer_path=str(valid))

        self.assertFalse(self.page.start_training_button.isEnabled())
        self.assertFalse(self.page.cancel_training_button.isEnabled())
        self.assertIn(DEFERRED_LABEL, self.page.job_state_label.text())
        self.assertEqual(self.page._deferred_job_id, job_ids[0])


class TrainingPageImportFlowUnchangedTest(_IsolatedWindowCase):
    """The import keeps its own refreshes; the new subscriptions add no business behavior to it."""

    def test_a_successful_import_ends_linked_with_the_expected_buttons(self):
        _training, job_ids = self.make_workspace_with_training(jobs=1)
        job_id = job_ids[0]
        self.select_job(job_id)

        with self.assertNoLogs("src.core.event_bus", level="ERROR"):
            self.import_selected_job("Imported LoRA")

        loras = self.window.lora_library_manager.list_loras()
        self.assertEqual([lora.name for lora in loras], ["Imported LoRA"])
        job = next(j for j in self.window.training_manager.active_training.jobs if j.job_id == job_id)
        self.assertEqual(job.imported_lora_id, loras[0].lora_id)
        self.assertIn("importé : Imported LoRA", self.rows()[job_id])
        self.assertFalse(self.page.import_lora_button.isEnabled())
        self.assertTrue(self.page.use_lora_in_inference_button.isEnabled())
        self.assertEqual(self.current_job_id(), job_id)
        self.assertTrue(any(api == "information" for api, _texts in self.dialogs))

    def test_a_failure_of_the_second_step_leaves_the_entry_unlinked_and_importable(self):
        _training, job_ids = self.make_workspace_with_training(jobs=1)
        job_id = job_ids[0]
        self.select_job(job_id)

        with self.assertNoLogs("src.core.event_bus", level="ERROR"):
            # Only the second step (linking the job, which saves the Workspace) fails; the library import itself
            # persists to the registry and does not go through WorkspaceManager.save().
            with patch.object(
                self.window.workspace_manager, "save", side_effect=WorkspaceManagerError("simulated disk full")
            ):
                self.import_selected_job("Imported LoRA")

        loras = self.window.lora_library_manager.list_loras()
        self.assertEqual([lora.name for lora in loras], ["Imported LoRA"])
        job = next(j for j in self.window.training_manager.active_training.jobs if j.job_id == job_id)
        self.assertEqual(job.imported_lora_id, "")
        self.assertIn("importable", self.rows()[job_id])
        self.assertTrue(self.page.import_lora_button.isEnabled())
        self.assertFalse(self.page.use_lora_in_inference_button.isEnabled())
        self.assertEqual(self.current_job_id(), job_id)
        self.assertTrue(any(api == "warning" and "Import partiel" in texts for api, texts in self.dialogs))



def tearDownModule():
    for test_id, closed, dialogs, window_destroyed, page_destroyed in _DISPOSAL_LOG:
        sys.stderr.write(
            f"DISPOSAL {test_id.rsplit('.', 1)[-1]}: closed={closed} dialogs_during_close={dialogs} "
            f"window_destroyed={window_destroyed} page_destroyed={page_destroyed}\n"
        )
    sys.stderr.write(f"DISPOSAL SUMMARY: {len(_DISPOSAL_LOG)} windows disposed\n")
    sys.stderr.flush()


if __name__ == "__main__":
    unittest.main()
