"""
Integration coverage for Application Settings — a machine-local
persistence tier entirely independent of any Workspace. Exercises
ApplicationSettings (Domain), ApplicationSettingsStorage
(Infrastructure, atomic writes on a real temp directory) and
ApplicationSettingsManager together, plus the Application section of
the real SettingsPage widget — the same wiring MainWindow uses. No
test ever reads or writes the real %LOCALAPPDATA%; every storage
interaction is routed through an injected temporary directory.
"""

import json
import logging
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from src.core.event_bus import EventBus
from src.domain.application_settings import ApplicationSettings
from src.infrastructure.storage.application_settings_storage import (
    ApplicationSettingsStorage,
    ApplicationSettingsStorageError,
)
from src.managers.workspace_manager import (
    WorkspaceManager,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_SAVED,
    WORKSPACE_CLOSED,
)
from src.managers.settings_manager import SettingsManager
from src.managers.application_settings_manager import (
    ApplicationSettingsManager,
    APPLICATION_SETTINGS_UPDATED,
)
from src.ui.pages.settings_page import SettingsPage

WORKSPACE_EVENTS = (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_SAVED, WORKSPACE_CLOSED)

_app = QApplication.instance() or QApplication([])


class ApplicationSettingsRoundTripTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def _wire(self, storage_directory=None):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        settings_manager = SettingsManager(workspace_manager)
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=storage_directory or (Path(self.tmp_dir) / "AppSettings"),
            event_bus=event_bus,
        )

        settings_page = SettingsPage(settings_manager, application_settings_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, settings_page.update_settings)
        event_bus.subscribe(
            APPLICATION_SETTINGS_UPDATED, settings_page.update_application_settings
        )

        return (
            event_bus, workspace_manager, settings_manager,
            application_settings_manager, settings_page,
        )

    # ------------------------------------------------------------------
    # 1. Domain
    # ------------------------------------------------------------------
    def test_application_settings_domain_object_roundtrip_and_defaults(self):

        settings = ApplicationSettings()
        self.assertEqual(settings.python_path, "")
        self.assertEqual(settings.comfyui_path, "")
        self.assertEqual(settings.onetrainer_path, "")
        # Mission 018: unlike the three fields above, these two already
        # have a real, currently active behavior (a specific ComfyUI
        # server/checkpoint the app actually talks to) — their defaults
        # are the literal values that were hardcoded in main_window.py
        # before this mission, not "".
        self.assertEqual(settings.comfyui_url, "http://127.0.0.1:8000")
        self.assertEqual(
            settings.comfyui_checkpoint_name, "v1-5-pruned-emaonly-fp16.safetensors"
        )
        # Mission 030: ollama_url has a real literal default (Ollama's
        # own documented local port), same convention as comfyui_url —
        # ollama_path/ollama_model_name default to "" like
        # python_path/onetrainer_path, since there is no prior
        # hardcoded Ollama behavior to preserve.
        self.assertEqual(settings.ollama_url, "http://127.0.0.1:11434")
        self.assertEqual(settings.ollama_path, "")
        self.assertEqual(settings.ollama_model_name, "")
        self.assertEqual(
            settings.to_dict(),
            {
                "python_path": "",
                "comfyui_path": "",
                "onetrainer_path": "",
                "comfyui_url": "http://127.0.0.1:8000",
                "comfyui_checkpoint_name": "v1-5-pruned-emaonly-fp16.safetensors",
                "ollama_url": "http://127.0.0.1:11434",
                "ollama_path": "",
                "ollama_model_name": "",
            },
        )

        original = ApplicationSettings(
            python_path="C:/Python/python.exe",
            comfyui_path="C:/ComfyUI",
            onetrainer_path="C:/OneTrainer",
            comfyui_url="http://192.168.1.50:8188",
            comfyui_checkpoint_name="sdxl_base.safetensors",
            ollama_url="http://192.168.1.50:11434",
            ollama_path="C:/Ollama",
            ollama_model_name="llama3.2:latest",
        )
        restored = ApplicationSettings.from_dict(original.to_dict())
        self.assertEqual(original, restored)

        self.assertEqual(ApplicationSettings.from_dict({}), ApplicationSettings())

        self.assertEqual(
            ApplicationSettings.from_dict({"python_path": "C:/Python"}),
            ApplicationSettings(python_path="C:/Python"),
        )

        self.assertEqual(
            ApplicationSettings.from_dict({"python_path": "C:/Python", "unknown": "ignored"}),
            ApplicationSettings(python_path="C:/Python"),
        )

        self.assertEqual(ApplicationSettings.from_dict({"python_path": ""}).python_path, "")

        # A dict missing comfyui_url/comfyui_checkpoint_name entirely
        # (the exact shape of a pre-Mission-018 file) falls back to the
        # same literal defaults as ApplicationSettings() itself, not "".
        legacy = ApplicationSettings.from_dict({"python_path": "C:/Python"})
        self.assertEqual(legacy.comfyui_url, "http://127.0.0.1:8000")
        self.assertEqual(
            legacy.comfyui_checkpoint_name, "v1-5-pruned-emaonly-fp16.safetensors"
        )
        # Mission 030: same fallback discipline for a dict missing the
        # Ollama fields entirely (the exact shape of a pre-Mission-030
        # file).
        self.assertEqual(legacy.ollama_url, "http://127.0.0.1:11434")
        self.assertEqual(legacy.ollama_path, "")
        self.assertEqual(legacy.ollama_model_name, "")

        # An explicit empty string is still a real, distinct value — not
        # silently replaced by the default.
        self.assertEqual(
            ApplicationSettings.from_dict({"comfyui_url": ""}).comfyui_url, ""
        )
        self.assertEqual(
            ApplicationSettings.from_dict({"ollama_url": ""}).ollama_url, ""
        )

    # ------------------------------------------------------------------
    # 2. default_directory() — LOCALAPPDATA simulated + fallback
    # ------------------------------------------------------------------
    def test_default_directory_resolution(self):

        with patch.dict(os.environ, {"LOCALAPPDATA": r"C:\Users\FakeUser\AppData\Local"}):
            result = ApplicationSettingsStorage.default_directory()
        self.assertEqual(
            result, Path(r"C:\Users\FakeUser\AppData\Local") / "AIStudioToolkit"
        )

        env_without_localappdata = {k: v for k, v in os.environ.items() if k != "LOCALAPPDATA"}
        with patch.dict(os.environ, env_without_localappdata, clear=True):
            result = ApplicationSettingsStorage.default_directory()
        self.assertEqual(
            result, Path.home() / "AppData" / "Local" / "AIStudioToolkit"
        )

    # ------------------------------------------------------------------
    # 3. load() compatibility matrix
    # ------------------------------------------------------------------
    def test_storage_load_compatibility_matrix(self):

        log_records = []

        class ListHandler(logging.Handler):
            def emit(self, record):
                log_records.append(record.getMessage())

        logger = logging.getLogger(
            "src.infrastructure.storage.application_settings_storage"
        )
        handler = ListHandler()
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        logger.setLevel(logging.WARNING)

        root = Path(self.tmp_dir) / "LoadMatrix"

        # Absent file: None, no warning, no directory created.
        absent_dir = root / "absent"
        result = ApplicationSettingsStorage.load(absent_dir)
        self.assertIsNone(result)
        self.assertEqual(log_records, [])
        self.assertFalse(absent_dir.exists())

        # Malformed cases: each -> None + exactly one warning.
        malformed_cases = {
            "empty": "",
            "invalid_json": "{not valid",
            "root_is_list": "[1, 2, 3]",
            "root_is_str": '"just a string"',
            "root_is_int": "42",
        }
        for label, payload in malformed_cases.items():
            case_dir = root / label
            case_dir.mkdir(parents=True)
            (case_dir / "application_settings.json").write_text(payload, encoding="utf-8")
            log_records.clear()
            result = ApplicationSettingsStorage.load(case_dir)
            self.assertIsNone(result, label)
            self.assertEqual(len(log_records), 1, label)

        # OSError while reading -> None + warning.
        oserror_dir = root / "oserror"
        oserror_dir.mkdir(parents=True)
        (oserror_dir / "application_settings.json").write_text("{}", encoding="utf-8")
        log_records.clear()
        with patch("builtins.open", side_effect=OSError("simulated read failure")):
            result = ApplicationSettingsStorage.load(oserror_dir)
        self.assertIsNone(result)
        self.assertEqual(len(log_records), 1)

        # Valid partial dict returned raw — Storage does not fill defaults.
        partial_dir = root / "partial"
        partial_dir.mkdir(parents=True)
        (partial_dir / "application_settings.json").write_text(
            json.dumps({"comfyui_path": "C:/ComfyUI"}), encoding="utf-8"
        )
        result = ApplicationSettingsStorage.load(partial_dir)
        self.assertEqual(result, {"comfyui_path": "C:/ComfyUI"})

        # Unknown keys preserved raw — filtering is the Domain's job, not Storage's.
        unknown_dir = root / "unknown"
        unknown_dir.mkdir(parents=True)
        (unknown_dir / "application_settings.json").write_text(
            json.dumps({"python_path": "C:/Python", "future_field": "kept"}),
            encoding="utf-8",
        )
        result = ApplicationSettingsStorage.load(unknown_dir)
        self.assertEqual(result, {"python_path": "C:/Python", "future_field": "kept"})

    # ------------------------------------------------------------------
    # 4. Real round-trip with Unicode paths
    # ------------------------------------------------------------------
    def test_storage_round_trip_with_unicode_paths(self):

        directory = Path(self.tmp_dir) / "Unicode"
        payload = {
            "python_path": "C:/Utilisateurs/Éléonore Müller/Python/python.exe",
            "comfyui_path": "D:/Outils été 2026/ComfyUI",
            "onetrainer_path": "",
        }
        ApplicationSettingsStorage.save(directory, payload)
        restored = ApplicationSettingsStorage.load(directory)
        self.assertEqual(restored, payload)

        raw_bytes = (directory / "application_settings.json").read_bytes()
        self.assertIn("Éléonore".encode("utf-8"), raw_bytes)

    # ------------------------------------------------------------------
    # 5. Atomic write: success + failure preserves the last valid file
    # ------------------------------------------------------------------
    def test_storage_atomic_write_preserves_last_valid_file_on_failure(self):

        directory = Path(self.tmp_dir) / "Atomic"

        # Successful replacement of an existing file leaves no temp residue.
        ApplicationSettingsStorage.save(directory, {"python_path": "old"})
        ApplicationSettingsStorage.save(directory, {"python_path": "new"})
        self.assertEqual(
            ApplicationSettingsStorage.load(directory), {"python_path": "new"}
        )
        self.assertEqual(len(list(directory.iterdir())), 1)

        # Failure before os.replace(): exception raised, old file untouched,
        # temp file cleaned up.
        original_content = (directory / "application_settings.json").read_text(
            encoding="utf-8"
        )

        with patch("os.replace", side_effect=OSError("simulated replace failure")):
            with self.assertRaises(ApplicationSettingsStorageError):
                ApplicationSettingsStorage.save(directory, {"python_path": "should_not_persist"})

        current_content = (directory / "application_settings.json").read_text(encoding="utf-8")
        self.assertEqual(current_content, original_content)

        leftovers = [f for f in directory.iterdir() if f.name != "application_settings.json"]
        self.assertEqual(leftovers, [])

    # ------------------------------------------------------------------
    # 6. Manager: defaults and loading
    # ------------------------------------------------------------------
    def test_application_settings_manager_defaults_and_loading(self):

        empty_dir = Path(self.tmp_dir) / "ManagerEmpty"
        manager = ApplicationSettingsManager(storage_directory=empty_dir)
        self.assertEqual(manager.settings, ApplicationSettings())

        preloaded_dir = Path(self.tmp_dir) / "ManagerPreloaded"
        ApplicationSettingsStorage.save(preloaded_dir, {"python_path": "C:/Python/python.exe"})
        manager_2 = ApplicationSettingsManager(storage_directory=preloaded_dir)
        self.assertEqual(
            manager_2.settings, ApplicationSettings(python_path="C:/Python/python.exe")
        )

    # ------------------------------------------------------------------
    # 7. Manager: idempotence, atomicity, unknown kwarg
    # ------------------------------------------------------------------
    def test_application_settings_manager_update_is_idempotent_and_atomic(self):

        event_bus = EventBus()
        manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "ManagerUpdate", event_bus=event_bus,
        )
        events_seen = []
        event_bus.subscribe(
            APPLICATION_SETTINGS_UPDATED, lambda payload: events_seen.append(dict(payload))
        )

        # update() with no arguments: no-op.
        with patch.object(ApplicationSettingsStorage, "save") as save_spy:
            self.assertFalse(manager.update())
            save_spy.assert_not_called()
        self.assertEqual(events_seen, [])

        # A single field.
        with patch.object(
            ApplicationSettingsStorage, "save", wraps=ApplicationSettingsStorage.save
        ) as save_spy:
            self.assertTrue(manager.update(python_path="C:/Python/python.exe"))
            save_spy.assert_called_once()
        self.assertEqual(manager.settings.python_path, "C:/Python/python.exe")
        self.assertEqual(len(events_seen), 1)
        self.assertEqual(
            events_seen[-1],
            {
                "python_path": "C:/Python/python.exe",
                "comfyui_path": "",
                "onetrainer_path": "",
                "comfyui_url": "http://127.0.0.1:8000",
                "comfyui_checkpoint_name": "v1-5-pruned-emaonly-fp16.safetensors",
                "ollama_url": "http://127.0.0.1:11434",
                "ollama_path": "",
                "ollama_model_name": "",
            },
        )

        # Multiple fields simultaneously: exactly 1 save(), 1 event.
        events_seen.clear()
        with patch.object(
            ApplicationSettingsStorage, "save", wraps=ApplicationSettingsStorage.save
        ) as save_spy:
            self.assertTrue(
                manager.update(comfyui_path="C:/ComfyUI", onetrainer_path="C:/OneTrainer")
            )
            save_spy.assert_called_once()
        self.assertEqual(manager.settings.comfyui_path, "C:/ComfyUI")
        self.assertEqual(manager.settings.onetrainer_path, "C:/OneTrainer")
        self.assertEqual(len(events_seen), 1)

        # Identical values: no-op, 0 save, 0 event.
        events_seen.clear()
        with patch.object(ApplicationSettingsStorage, "save") as save_spy:
            self.assertFalse(
                manager.update(comfyui_path="C:/ComfyUI", onetrainer_path="C:/OneTrainer")
            )
            save_spy.assert_not_called()
        self.assertEqual(events_seen, [])

        # Mission 018: comfyui_url/comfyui_checkpoint_name follow the
        # exact same update() contract — multiple fields, exactly 1
        # save(), 1 event, then idempotent no-op on identical values.
        events_seen.clear()
        with patch.object(
            ApplicationSettingsStorage, "save", wraps=ApplicationSettingsStorage.save
        ) as save_spy:
            self.assertTrue(
                manager.update(
                    comfyui_url="http://192.168.1.50:8188",
                    comfyui_checkpoint_name="sdxl_base.safetensors",
                )
            )
            save_spy.assert_called_once()
        self.assertEqual(manager.settings.comfyui_url, "http://192.168.1.50:8188")
        self.assertEqual(manager.settings.comfyui_checkpoint_name, "sdxl_base.safetensors")
        self.assertEqual(len(events_seen), 1)

        events_seen.clear()
        with patch.object(ApplicationSettingsStorage, "save") as save_spy:
            self.assertFalse(
                manager.update(
                    comfyui_url="http://192.168.1.50:8188",
                    comfyui_checkpoint_name="sdxl_base.safetensors",
                )
            )
            save_spy.assert_not_called()
        self.assertEqual(events_seen, [])

        # Mission 030: ollama_url/ollama_path/ollama_model_name follow
        # the exact same update() contract — multiple fields, exactly 1
        # save(), 1 event, then idempotent no-op on identical values.
        events_seen.clear()
        with patch.object(
            ApplicationSettingsStorage, "save", wraps=ApplicationSettingsStorage.save
        ) as save_spy:
            self.assertTrue(
                manager.update(
                    ollama_url="http://192.168.1.50:11434",
                    ollama_path="C:/Ollama",
                    ollama_model_name="llama3.2:latest",
                )
            )
            save_spy.assert_called_once()
        self.assertEqual(manager.settings.ollama_url, "http://192.168.1.50:11434")
        self.assertEqual(manager.settings.ollama_path, "C:/Ollama")
        self.assertEqual(manager.settings.ollama_model_name, "llama3.2:latest")
        self.assertEqual(len(events_seen), 1)

        events_seen.clear()
        with patch.object(ApplicationSettingsStorage, "save") as save_spy:
            self.assertFalse(
                manager.update(
                    ollama_url="http://192.168.1.50:11434",
                    ollama_path="C:/Ollama",
                    ollama_model_name="llama3.2:latest",
                )
            )
            save_spy.assert_not_called()
        self.assertEqual(events_seen, [])

        # "" is a real, distinct value.
        events_seen.clear()
        with patch.object(
            ApplicationSettingsStorage, "save", wraps=ApplicationSettingsStorage.save
        ) as save_spy:
            self.assertTrue(manager.update(python_path=""))
            save_spy.assert_called_once()
        self.assertEqual(manager.settings.python_path, "")
        self.assertEqual(len(events_seen), 1)

        # Unknown kwarg: native TypeError, no mutation, no save, no event.
        before = manager.settings
        events_seen.clear()
        with patch.object(ApplicationSettingsStorage, "save") as save_spy:
            with self.assertRaises(TypeError):
                manager.update(unknown="x")
            save_spy.assert_not_called()
        self.assertIs(manager.settings, before)
        self.assertEqual(events_seen, [])

    # ------------------------------------------------------------------
    # 8. Manager: failed save leaves memory unchanged, no event
    # ------------------------------------------------------------------
    def test_application_settings_manager_failed_save_preserves_state(self):

        event_bus = EventBus()
        manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "ManagerFail", event_bus=event_bus,
        )
        events_seen = []
        event_bus.subscribe(
            APPLICATION_SETTINGS_UPDATED, lambda payload: events_seen.append(dict(payload))
        )

        before = manager.settings

        with patch.object(
            ApplicationSettingsStorage, "save",
            side_effect=ApplicationSettingsStorageError("simulated failure"),
        ):
            with self.assertRaises(ApplicationSettingsStorageError):
                manager.update(python_path="SHOULD_NOT_PERSIST")

        self.assertIs(manager.settings, before)
        self.assertNotEqual(manager.settings.python_path, "SHOULD_NOT_PERSIST")
        self.assertEqual(events_seen, [])

    # ------------------------------------------------------------------
    # 9. Persistence across manager instances
    # ------------------------------------------------------------------
    def test_application_settings_persist_across_manager_instances(self):

        directory = Path(self.tmp_dir) / "Persist"

        manager_a = ApplicationSettingsManager(storage_directory=directory)
        manager_a.update(
            python_path="C:/Python",
            comfyui_path="C:/ComfyUI",
            onetrainer_path="C:/OneTrainer",
            comfyui_url="http://192.168.1.50:8188",
            comfyui_checkpoint_name="sdxl_base.safetensors",
            ollama_url="http://192.168.1.50:11434",
            ollama_path="C:/Ollama",
            ollama_model_name="llama3.2:latest",
        )

        manager_b = ApplicationSettingsManager(storage_directory=directory)
        self.assertEqual(
            manager_b.settings,
            ApplicationSettings(
                python_path="C:/Python",
                comfyui_path="C:/ComfyUI",
                onetrainer_path="C:/OneTrainer",
                comfyui_url="http://192.168.1.50:8188",
                comfyui_checkpoint_name="sdxl_base.safetensors",
                ollama_url="http://192.168.1.50:11434",
                ollama_path="C:/Ollama",
                ollama_model_name="llama3.2:latest",
            ),
        )

    # ------------------------------------------------------------------
    # 10. Independence from Workspace
    # ------------------------------------------------------------------
    def test_application_settings_manager_independent_of_workspace(self):

        import inspect

        signature = inspect.signature(ApplicationSettingsManager.__init__)
        self.assertNotIn("workspace_manager", signature.parameters)

        # No WorkspaceManager anywhere in scope, no Workspace ever opened:
        # the Manager still constructs and updates correctly.
        directory = Path(self.tmp_dir) / "NoWorkspace"
        manager = ApplicationSettingsManager(storage_directory=directory)
        self.assertEqual(manager.settings, ApplicationSettings())
        self.assertTrue(manager.update(python_path="C:/Python"))
        self.assertEqual(manager.settings.python_path, "C:/Python")

    # ------------------------------------------------------------------
    # 11. SettingsPage — Application section lifecycle
    # ------------------------------------------------------------------
    def test_settings_page_application_section_lifecycle(self):

        (event_bus, workspace_manager, settings_manager,
         application_settings_manager, settings_page) = self._wire()

        # Available and enabled with no Workspace at all.
        self.assertTrue(settings_page.python_path_edit.isEnabled())
        self.assertTrue(settings_page.comfyui_path_edit.isEnabled())
        self.assertTrue(settings_page.onetrainer_path_edit.isEnabled())
        self.assertTrue(settings_page.comfyui_url_edit.isEnabled())
        self.assertTrue(settings_page.comfyui_checkpoint_name_edit.isEnabled())
        self.assertTrue(settings_page.ollama_url_edit.isEnabled())
        self.assertTrue(settings_page.ollama_path_edit.isEnabled())
        self.assertTrue(settings_page.ollama_model_name_edit.isEnabled())
        self.assertTrue(settings_page.application_save_button.isEnabled())
        self.assertEqual(settings_page.python_path_edit.text(), "")
        # Mission 018: the two fields show the real default already in
        # effect (ApplicationSettings' own literal defaults), not an
        # empty field hiding an implicit value used elsewhere.
        self.assertEqual(settings_page.comfyui_url_edit.text(), "http://127.0.0.1:8000")
        self.assertEqual(
            settings_page.comfyui_checkpoint_name_edit.currentText(),
            "v1-5-pruned-emaonly-fp16.safetensors",
        )
        # Mission 030: same convention — ollama_url shows its own real
        # default, ollama_path/ollama_model_name show "" (nothing
        # hardcoded to preserve for a brand new integration).
        self.assertEqual(settings_page.ollama_url_edit.text(), "http://127.0.0.1:11434")
        self.assertEqual(settings_page.ollama_path_edit.text(), "")
        self.assertEqual(settings_page.ollama_model_name_edit.currentText(), "")

        # Real save persists and refreshes the section.
        settings_page.python_path_edit.setText("C:/Python/python.exe")
        settings_page.comfyui_path_edit.setText("C:/ComfyUI")
        settings_page.onetrainer_path_edit.setText("C:/OneTrainer")
        settings_page.comfyui_url_edit.setText("http://192.168.1.50:8188")
        settings_page.comfyui_checkpoint_name_edit.setCurrentText("sdxl_base.safetensors")
        settings_page.ollama_url_edit.setText("http://192.168.1.50:11434")
        settings_page.ollama_path_edit.setText("C:/Ollama")
        settings_page.ollama_model_name_edit.setCurrentText("llama3.2:latest")
        with patch.object(
            ApplicationSettingsStorage, "save", wraps=ApplicationSettingsStorage.save
        ) as save_spy:
            settings_page.save_application_settings()
            save_spy.assert_called_once()
        self.assertEqual(application_settings_manager.settings.python_path, "C:/Python/python.exe")
        self.assertEqual(
            application_settings_manager.settings.comfyui_url, "http://192.168.1.50:8188"
        )
        self.assertEqual(
            application_settings_manager.settings.comfyui_checkpoint_name, "sdxl_base.safetensors"
        )
        self.assertEqual(
            application_settings_manager.settings.ollama_url, "http://192.168.1.50:11434"
        )
        self.assertEqual(application_settings_manager.settings.ollama_path, "C:/Ollama")
        self.assertEqual(
            application_settings_manager.settings.ollama_model_name, "llama3.2:latest"
        )

        # Idempotent save: no extra write.
        with patch.object(ApplicationSettingsStorage, "save") as save_spy:
            settings_page.save_application_settings()
            save_spy.assert_not_called()

        # Unsaved draft preserved through every WORKSPACE_* event.
        settings_page.python_path_edit.setText("UNSAVED_DRAFT")

        workspace_manager.create(Path(self.tmp_dir) / "WS")
        self.assertEqual(settings_page.python_path_edit.text(), "UNSAVED_DRAFT")

        workspace_manager.save()
        self.assertEqual(settings_page.python_path_edit.text(), "UNSAVED_DRAFT")

        workspace_manager.close()
        self.assertEqual(settings_page.python_path_edit.text(), "UNSAVED_DRAFT")

        workspace_manager.open(Path(self.tmp_dir) / "WS")
        self.assertEqual(settings_page.python_path_edit.text(), "UNSAVED_DRAFT")

    # ------------------------------------------------------------------
    # 12. Cross-section independence (bidirectional)
    # ------------------------------------------------------------------
    def test_settings_page_sections_refresh_independently(self):

        (event_bus, workspace_manager, settings_manager,
         application_settings_manager, settings_page) = self._wire()

        workspace_manager.create(Path(self.tmp_dir) / "WS2")

        # An Application event must never touch an unsaved Workspace draft.
        settings_page.theme_edit.setText("UNSAVED_WORKSPACE_DRAFT")
        settings_page.comfyui_path_edit.setText("D:/NewComfyUI")
        settings_page.save_application_settings()
        self.assertEqual(settings_page.theme_edit.text(), "UNSAVED_WORKSPACE_DRAFT")

        # A Workspace event must never touch an unsaved Application draft.
        settings_page.python_path_edit.setText("UNSAVED_APPLICATION_DRAFT")
        settings_page.language_edit.setText("fr")
        settings_page.save_settings()
        self.assertEqual(settings_page.python_path_edit.text(), "UNSAVED_APPLICATION_DRAFT")

    # ------------------------------------------------------------------
    # 13. No duplicate subscriptions
    # ------------------------------------------------------------------
    def test_no_duplicate_subscriptions_between_wire_calls(self):

        wired_1 = self._wire()
        wired_2 = self._wire()

        for obj_1, obj_2 in zip(wired_1, wired_2):
            self.assertIsNot(obj_1, obj_2)

        event_bus_1, event_bus_2 = wired_1[0], wired_2[0]
        settings_page_1 = wired_1[4]

        count = sum(
            1 for cb in event_bus_1._subscribers[APPLICATION_SETTINGS_UPDATED]
            if cb == settings_page_1.update_application_settings
        )
        self.assertEqual(count, 1)

        self.assertTrue(
            set(event_bus_1._subscribers[APPLICATION_SETTINGS_UPDATED]).isdisjoint(
                event_bus_2._subscribers[APPLICATION_SETTINGS_UPDATED]
            )
        )

    # ------------------------------------------------------------------
    # 14. Mission 018 — legacy file predating comfyui_url/checkpoint_name
    # ------------------------------------------------------------------
    def test_manager_loads_legacy_settings_file_without_comfyui_url_or_checkpoint_fields(self):

        directory = Path(self.tmp_dir) / "LegacyFile"
        # Exact shape of a pre-Mission-018 application_settings.json —
        # only the three fields that existed before this mission.
        ApplicationSettingsStorage.save(
            directory,
            {
                "python_path": "C:/Python/python.exe",
                "comfyui_path": "C:/ComfyUI",
                "onetrainer_path": "",
            },
        )

        manager = ApplicationSettingsManager(storage_directory=directory)

        self.assertEqual(manager.settings.python_path, "C:/Python/python.exe")
        self.assertEqual(manager.settings.comfyui_path, "C:/ComfyUI")
        # The whole point of this mission's chosen default strategy:
        # a legacy file loads the exact same values the application
        # already used before Mission 018 existed — not empty strings.
        self.assertEqual(manager.settings.comfyui_url, "http://127.0.0.1:8000")
        self.assertEqual(
            manager.settings.comfyui_checkpoint_name, "v1-5-pruned-emaonly-fp16.safetensors"
        )

    # ------------------------------------------------------------------
    # 15. Mission 030 — legacy file predating ollama_url/path/model_name
    # ------------------------------------------------------------------
    def test_manager_loads_legacy_settings_file_without_ollama_fields(self):

        directory = Path(self.tmp_dir) / "LegacyFileNoOllama"
        # Exact shape of a pre-Mission-030 application_settings.json —
        # only the fields that existed before this mission (including
        # Mission 018's comfyui_url/comfyui_checkpoint_name).
        ApplicationSettingsStorage.save(
            directory,
            {
                "python_path": "C:/Python/python.exe",
                "comfyui_path": "C:/ComfyUI",
                "onetrainer_path": "",
                "comfyui_url": "http://192.168.1.50:8188",
                "comfyui_checkpoint_name": "sdxl_base.safetensors",
            },
        )

        manager = ApplicationSettingsManager(storage_directory=directory)

        self.assertEqual(manager.settings.python_path, "C:/Python/python.exe")
        self.assertEqual(manager.settings.comfyui_url, "http://192.168.1.50:8188")
        # The whole point of this mission's chosen default strategy: a
        # legacy file loads the same literal Ollama defaults
        # ApplicationSettings() itself uses, not empty strings hiding a
        # missing value.
        self.assertEqual(manager.settings.ollama_url, "http://127.0.0.1:11434")
        self.assertEqual(manager.settings.ollama_path, "")
        self.assertEqual(manager.settings.ollama_model_name, "")


if __name__ == "__main__":
    unittest.main()
