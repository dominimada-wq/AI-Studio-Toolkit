"""
Integration coverage for Mission 087 — the central LoRA library
foundation. Exercises LoRALibraryStorage (Infrastructure, atomic writes
on a real temp directory), LoRALibraryManager (Domain LoRA objects,
transactional import/delete with real files on disk) and the
lora_library_path lock enforced by ApplicationSettingsManager.update().
No test ever reads or writes the real %LOCALAPPDATA%; every storage
interaction is routed through an injected temporary directory.

Deliberately independent of Character/Workspace/project.json/LoRAPage —
this library is Application-level, entirely unconnected to any of them
in Mission 087.
"""

import json
import logging
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.event_bus import EventBus
from src.domain.lora import LoRA
from src.infrastructure.storage.lora_library_storage import (
    LoRALibraryStorage,
    LoRALibraryStorageError,
)
from src.infrastructure.storage.workspace_storage import (
    WorkspaceStorage,
    WorkspaceStorageError,
)
from src.managers.application_settings_manager import (
    ApplicationSettingsManager,
    LoRAExposureRootLockedError,
    LoRALibraryPathLockedError,
)
from src.managers.lora_library_manager import (
    LoRAComfyUIExposureResult,
    LoRAExposureRootInspectionError,
    LoRALibraryDeletionResult,
    LoRALibraryError,
    LoRALibraryManager,
    LoRALibraryThumbnailResult,
    LORA_LIBRARY_DELETED,
    LORA_LIBRARY_IMPORTED,
    LORA_LIBRARY_UPDATED,
)


class LoRALibraryStorageTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def test_absent_file_returns_none(self):
        directory = Path(self.tmp_dir) / "Absent"
        self.assertIsNone(LoRALibraryStorage.load(directory))
        self.assertFalse(directory.exists())

    def test_invalid_json_raises_storage_error_with_error_log(self):
        # Mission 144: a present-but-corrupt registry must never be
        # treated the same as a missing one — it now raises instead of
        # silently returning None.
        directory = Path(self.tmp_dir) / "Invalid"
        directory.mkdir(parents=True)
        (directory / LoRALibraryStorage.FILE_NAME).write_text("{not valid", encoding="utf-8")

        log_records = []

        class ListHandler(logging.Handler):
            def emit(self, record):
                log_records.append(record.getMessage())

        logger = logging.getLogger("src.infrastructure.storage.lora_library_storage")
        handler = ListHandler()
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        logger.setLevel(logging.WARNING)

        with self.assertRaises(LoRALibraryStorageError) as ctx:
            LoRALibraryStorage.load(directory)

        self.assertEqual(len(log_records), 1)
        self.assertIsInstance(ctx.exception.__cause__, json.JSONDecodeError)

    def test_non_dict_root_raises_storage_error(self):
        # Mission 144: syntactically valid JSON that is not an object
        # is structurally unusable — same treatment as invalid JSON.
        for label, payload in {
            "list": "[1, 2, 3]",
            "str": '"just a string"',
            "int": "42",
            "null": "null",
        }.items():
            directory = Path(self.tmp_dir) / f"NonDict_{label}"
            directory.mkdir(parents=True)
            (directory / LoRALibraryStorage.FILE_NAME).write_text(payload, encoding="utf-8")
            with self.assertRaises(LoRALibraryStorageError, msg=label):
                LoRALibraryStorage.load(directory)

    def test_non_list_loras_value_raises_storage_error(self):
        # Mission 144: the "loras" key, when present, must be a list —
        # a present-but-wrong-typed value is a structural corruption,
        # not tolerable the way a malformed individual entry is.
        for label, payload in {
            "string": '{"loras": "foo"}',
            "dict": '{"loras": {}}',
            "int": '{"loras": 42}',
            "null": '{"loras": null}',
        }.items():
            directory = Path(self.tmp_dir) / f"NonListLoras_{label}"
            directory.mkdir(parents=True)
            (directory / LoRALibraryStorage.FILE_NAME).write_text(payload, encoding="utf-8")
            with self.assertRaises(LoRALibraryStorageError, msg=label):
                LoRALibraryStorage.load(directory)

    def test_missing_loras_key_still_tolerated_as_empty_catalog(self):
        # Mission 144: an absent "loras" key ("{}") remains a legitimate
        # permissive case, distinct from a present-but-wrong-typed one —
        # unchanged behavior, not raised.
        directory = Path(self.tmp_dir) / "EmptyObject"
        directory.mkdir(parents=True)
        (directory / LoRALibraryStorage.FILE_NAME).write_text("{}", encoding="utf-8")
        self.assertEqual(LoRALibraryStorage.load(directory), {})

    def test_read_oserror_raises_storage_error_with_cause_preserved(self):
        directory = Path(self.tmp_dir) / "OSErrorRead"
        directory.mkdir(parents=True)
        (directory / LoRALibraryStorage.FILE_NAME).write_text("{}", encoding="utf-8")

        original_oserror = OSError("simulated read failure")
        with patch("builtins.open", side_effect=original_oserror):
            with self.assertRaises(LoRALibraryStorageError) as ctx:
                LoRALibraryStorage.load(directory)

        self.assertIs(ctx.exception.__cause__, original_oserror)

    def test_load_failure_never_modifies_the_corrupt_file(self):
        # Mission 144's essential business invariant: load() must never
        # be the thing that destroys data.
        directory = Path(self.tmp_dir) / "Untouched"
        directory.mkdir(parents=True)
        file = directory / LoRALibraryStorage.FILE_NAME
        file.write_bytes(b"{not valid json at all")
        before = file.read_bytes()

        with self.assertRaises(LoRALibraryStorageError):
            LoRALibraryStorage.load(directory)

        after = file.read_bytes()
        self.assertEqual(before, after)

    def test_default_directory_delegates_to_application_settings_storage(self):
        from src.infrastructure.storage.application_settings_storage import (
            ApplicationSettingsStorage,
        )
        self.assertEqual(
            LoRALibraryStorage.default_directory(), ApplicationSettingsStorage.default_directory()
        )

    def test_atomic_round_trip(self):
        directory = Path(self.tmp_dir) / "RoundTrip"
        payload = {"loras": [{"lora_id": "abc", "name": "Style"}]}
        LoRALibraryStorage.save(directory, payload)
        self.assertEqual(LoRALibraryStorage.load(directory), payload)
        self.assertEqual(len(list(directory.iterdir())), 1)

    def test_atomic_write_failure_preserves_last_valid_file(self):
        directory = Path(self.tmp_dir) / "Atomic"
        LoRALibraryStorage.save(directory, {"loras": []})
        original_content = (directory / LoRALibraryStorage.FILE_NAME).read_text(encoding="utf-8")

        with patch("os.replace", side_effect=OSError("simulated replace failure")):
            with self.assertRaises(LoRALibraryStorageError):
                LoRALibraryStorage.save(directory, {"loras": [{"lora_id": "x"}]})

        current_content = (directory / LoRALibraryStorage.FILE_NAME).read_text(encoding="utf-8")
        self.assertEqual(current_content, original_content)
        leftovers = [f for f in directory.iterdir() if f.name != LoRALibraryStorage.FILE_NAME]
        self.assertEqual(leftovers, [])


class LoRALibraryManagerImportTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.registry_dir = Path(self.tmp_dir) / "Registry"
        self.library_root = Path(self.tmp_dir) / "Library"
        self.source_dir = Path(self.tmp_dir) / "External"
        self.source_dir.mkdir()

        self.event_bus = EventBus()
        self.manager = LoRALibraryManager(
            storage_directory=self.registry_dir, event_bus=self.event_bus
        )

    def _source(self, name: str, content: bytes = b"weights") -> Path:
        path = self.source_dir / name
        path.write_bytes(content)
        return path

    def test_registry_starts_empty(self):
        self.assertEqual(self.manager.list_loras(), [])

    def test_import_transmits_the_four_metadata_fields(self):
        # Mission 088: engine/architecture/trigger_word/version are
        # transmitted as-is to the created LoRA, never validated.
        source = self._source("style.safetensors")

        lora = self.manager.import_lora(
            "Style Meta",
            [str(source)],
            self.library_root,
            engine="ComfyUI",
            architecture="SDXL",
            trigger_word="mystyle",
            version="v2",
        )

        self.assertEqual(lora.engine, "ComfyUI")
        self.assertEqual(lora.architecture, "SDXL")
        self.assertEqual(lora.trigger_word, "mystyle")
        self.assertEqual(lora.version, "v2")

        reloaded = LoRALibraryManager(storage_directory=self.registry_dir)
        self.assertEqual(reloaded.get(lora.lora_id).engine, "ComfyUI")
        self.assertEqual(reloaded.get(lora.lora_id).architecture, "SDXL")
        self.assertEqual(reloaded.get(lora.lora_id).trigger_word, "mystyle")
        self.assertEqual(reloaded.get(lora.lora_id).version, "v2")

    def test_import_without_metadata_kwargs_keeps_pre_mission_088_defaults(self):
        # Every pre-Mission-088 call site never passes these kwargs —
        # their behavior must stay byte-for-byte unchanged.
        source = self._source("style.safetensors")

        lora = self.manager.import_lora("Style Legacy", [str(source)], self.library_root)

        self.assertEqual(lora.engine, "")
        self.assertEqual(lora.architecture, "")
        self.assertEqual(lora.trigger_word, "")
        self.assertEqual(lora.version, "")

    def test_import_single_file(self):
        source = self._source("style.safetensors")
        events = []
        self.event_bus.subscribe(LORA_LIBRARY_IMPORTED, lambda payload: events.append(dict(payload)))

        lora = self.manager.import_lora("Style A", [str(source)], self.library_root)

        self.assertIsInstance(lora, LoRA)
        self.assertEqual(lora.name, "Style A")
        self.assertEqual(len(lora.files), 1)
        owned_path = Path(lora.files[0])
        self.assertTrue(owned_path.exists())
        self.assertEqual(owned_path.read_bytes(), b"weights")
        self.assertEqual(owned_path.parent, self.library_root / lora.lora_id)
        self.assertEqual(lora.thumbnail, "")
        self.assertEqual(self.manager.list_loras(), [lora])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["lora_id"], lora.lora_id)

    def test_import_multiple_files(self):
        source_a = self._source("model.safetensors", b"weights-a")
        source_b = self._source("metadata.json", b'{"rank": 32}')

        lora = self.manager.import_lora("Style B", [str(source_a), str(source_b)], self.library_root)

        self.assertEqual(len(lora.files), 2)
        for owned_path in lora.files:
            self.assertTrue(Path(owned_path).exists())
        contents = {Path(p).read_bytes() for p in lora.files}
        self.assertEqual(contents, {b"weights-a", b'{"rank": 32}'})

    def test_import_with_optional_thumbnail(self):
        source = self._source("style.safetensors")
        thumbnail_source = self._source("preview.png", b"fake png")

        lora = self.manager.import_lora(
            "Style C", [str(source)], self.library_root, thumbnail_path=str(thumbnail_source)
        )

        self.assertNotEqual(lora.thumbnail, "")
        self.assertTrue(Path(lora.thumbnail).exists())
        self.assertEqual(Path(lora.thumbnail).parent, self.library_root / lora.lora_id)

    def test_import_without_thumbnail_leaves_it_empty(self):
        source = self._source("style.safetensors")
        lora = self.manager.import_lora("Style D", [str(source)], self.library_root)
        self.assertEqual(lora.thumbnail, "")

    def test_filename_collision_within_the_same_entry_is_resolved(self):
        # Two distinct source directories, same basename — a real,
        # plausible scenario (e.g. the weights file and an fp16 variant
        # both literally named the same by convention elsewhere).
        other_source_dir = Path(self.tmp_dir) / "OtherExternal"
        other_source_dir.mkdir()
        source_a = self._source("model.safetensors", b"variant-a")
        source_b = other_source_dir / "model.safetensors"
        source_b.write_bytes(b"variant-b")

        lora = self.manager.import_lora("Style E", [str(source_a), str(source_b)], self.library_root)

        self.assertEqual(len(lora.files), 2)
        names = sorted(Path(p).name for p in lora.files)
        self.assertEqual(names, ["model.safetensors", "model_1.safetensors"])
        contents = {Path(p).read_bytes() for p in lora.files}
        self.assertEqual(contents, {b"variant-a", b"variant-b"})

    def test_two_imports_of_the_same_source_produce_two_distinct_entries_and_copies(self):
        source = self._source("shared.safetensors")

        lora_1 = self.manager.import_lora("First", [str(source)], self.library_root)
        lora_2 = self.manager.import_lora("Second", [str(source)], self.library_root)

        self.assertNotEqual(lora_1.lora_id, lora_2.lora_id)
        self.assertNotEqual(Path(lora_1.files[0]).parent, Path(lora_2.files[0]).parent)
        self.assertTrue(Path(lora_1.files[0]).exists())
        self.assertTrue(Path(lora_2.files[0]).exists())
        self.assertNotEqual(lora_1.files[0], lora_2.files[0])
        # No hash-based deduplication in Mission 087 — genuinely two
        # independent physical copies of identical bytes.
        self.assertEqual(
            Path(lora_1.files[0]).read_bytes(), Path(lora_2.files[0]).read_bytes()
        )

    def test_source_files_are_never_modified_or_deleted(self):
        source = self._source("style.safetensors", b"original weights")
        original_mtime = source.stat().st_mtime

        lora = self.manager.import_lora("Style F", [str(source)], self.library_root)
        self.manager.delete(lora.lora_id, self.library_root)

        self.assertTrue(source.exists())
        self.assertEqual(source.read_bytes(), b"original weights")
        self.assertEqual(source.stat().st_mtime, original_mtime)

    def test_partial_copy_failure_leaves_no_entry_and_no_orphaned_folder(self):
        source_ok = self._source("first.safetensors")
        missing_source = self.source_dir / "does_not_exist.safetensors"

        with self.assertRaises(LoRALibraryError):
            self.manager.import_lora(
                "Broken", [str(source_ok), str(missing_source)], self.library_root
            )

        self.assertEqual(self.manager.list_loras(), [])
        # No lora_id is known outside the failed call, but the library
        # root itself must contain no leftover entry folder at all.
        if self.library_root.exists():
            self.assertEqual(list(self.library_root.iterdir()), [])

    def test_partial_copy_failure_cleanup_itself_failing_is_reported_in_the_message(self):
        source_ok = self._source("first.safetensors")
        missing_source = self.source_dir / "does_not_exist.safetensors"

        with patch.object(
            WorkspaceStorage, "delete_folder", side_effect=WorkspaceStorageError("locked")
        ):
            with self.assertRaises(LoRALibraryError) as ctx:
                self.manager.import_lora(
                    "Broken", [str(source_ok), str(missing_source)], self.library_root
                )

        self.assertIn("orphaned", str(ctx.exception))
        self.assertEqual(self.manager.list_loras(), [])

    def test_persistence_failure_after_copy_rolls_back_memory_and_cleans_up_disk(self):
        source = self._source("style.safetensors")

        with patch.object(
            LoRALibraryStorage, "save", side_effect=LoRALibraryStorageError("disk full")
        ):
            with self.assertRaises(LoRALibraryError):
                self.manager.import_lora("Style G", [str(source)], self.library_root)

        self.assertEqual(self.manager.list_loras(), [])
        # The entry folder was created by the (successful) copy step,
        # then removed again by the rollback triggered by save() failing.
        self.assertEqual(list(self.library_root.iterdir()), [])

    def test_persistence_failure_cleanup_itself_failing_is_reported_in_the_message(self):
        source = self._source("style.safetensors")

        with patch.object(
            LoRALibraryStorage, "save", side_effect=LoRALibraryStorageError("disk full")
        ), patch.object(
            WorkspaceStorage, "delete_folder", side_effect=WorkspaceStorageError("locked")
        ):
            with self.assertRaises(LoRALibraryError) as ctx:
                self.manager.import_lora("Style H", [str(source)], self.library_root)

        self.assertIn("orphaned", str(ctx.exception))
        self.assertEqual(self.manager.list_loras(), [])

    def test_import_never_raises_for_empty_file_paths(self):
        # No business-content validation in the Manager (CLAUDE.md
        # convention) — a name-only entry with zero files is a valid,
        # legal state, mirroring LoRAManager.create() before add_files().
        lora = self.manager.import_lora("Empty", [], self.library_root)
        self.assertEqual(lora.files, [])
        self.assertFalse((self.library_root / lora.lora_id).exists())


class LoRALibraryManagerDeleteTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.registry_dir = Path(self.tmp_dir) / "Registry"
        self.library_root = Path(self.tmp_dir) / "Library"
        self.source_dir = Path(self.tmp_dir) / "External"
        self.source_dir.mkdir()

        self.event_bus = EventBus()
        self.manager = LoRALibraryManager(
            storage_directory=self.registry_dir, event_bus=self.event_bus
        )

        source = self.source_dir / "style.safetensors"
        source.write_bytes(b"weights")
        self.lora = self.manager.import_lora("Style", [str(source)], self.library_root)

    def _lora_folder(self) -> Path:
        return self.library_root / self.lora.lora_id

    def test_delete_unknown_id_is_a_no_op(self):
        result = self.manager.delete("unknown-id", self.library_root)
        self.assertEqual(result, LoRALibraryDeletionResult(False, False, None))

    def test_delete_succeeds_and_removes_the_folder(self):
        events = []
        self.event_bus.subscribe(LORA_LIBRARY_DELETED, lambda payload: events.append(dict(payload)))
        folder = self._lora_folder()
        self.assertTrue(folder.exists())

        result = self.manager.delete(self.lora.lora_id, self.library_root)

        self.assertTrue(result.deleted)
        self.assertFalse(result.cleanup_failed)
        self.assertFalse(folder.exists())
        self.assertEqual(self.manager.list_loras(), [])
        self.assertEqual(len(events), 1)

    def test_delete_move_failure_aborts_before_any_mutation(self):
        folder = self._lora_folder()

        with patch.object(
            WorkspaceStorage, "rename_folder",
            side_effect=WorkspaceStorageError("locked by another process"),
        ):
            with self.assertRaises(LoRALibraryError):
                self.manager.delete(self.lora.lora_id, self.library_root)

        self.assertTrue(folder.exists())
        self.assertEqual(self.manager.list_loras(), [self.lora])

    def test_delete_persistence_failure_restores_folder_and_domain(self):
        folder = self._lora_folder()
        original_contents = [p.name for p in folder.iterdir()]

        with patch.object(
            LoRALibraryStorage, "save", side_effect=LoRALibraryStorageError("disk full")
        ):
            with self.assertRaises(LoRALibraryError):
                self.manager.delete(self.lora.lora_id, self.library_root)

        self.assertTrue(folder.exists())
        self.assertEqual([p.name for p in folder.iterdir()], original_contents)
        self.assertEqual(self.manager.list_loras(), [self.lora])
        trash_root = self.library_root / ".trash"
        self.assertTrue(not trash_root.exists() or list(trash_root.iterdir()) == [])

    def test_delete_double_failure_restores_domain_and_reports_manual_recovery(self):
        folder = self._lora_folder()
        original_contents = [p.name for p in folder.iterdir()]

        original_rename_folder = WorkspaceStorage.rename_folder
        call_count = {"n": 0}

        def flaky_rename_folder(old_root, new_root):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return original_rename_folder(old_root, new_root)
            raise WorkspaceStorageError("still locked")

        with patch.object(WorkspaceStorage, "rename_folder", side_effect=flaky_rename_folder), \
                patch.object(
                    LoRALibraryStorage, "save", side_effect=LoRALibraryStorageError("disk full")
                ):
            with self.assertRaises(LoRALibraryError) as ctx:
                self.manager.delete(self.lora.lora_id, self.library_root)

        self.assertEqual(self.manager.list_loras(), [self.lora])
        self.assertFalse(folder.exists())
        trash_root = self.library_root / ".trash"
        residual = list(trash_root.iterdir())
        self.assertEqual(len(residual), 1)
        self.assertEqual([p.name for p in residual[0].iterdir()], original_contents)
        message = str(ctx.exception)
        self.assertIn("restored", message)

    def test_delete_permanent_cleanup_failure_never_rolls_back_the_persisted_deletion(self):
        with patch.object(WorkspaceStorage, "delete_folder", side_effect=WorkspaceStorageError("locked")):
            result = self.manager.delete(self.lora.lora_id, self.library_root)

        self.assertTrue(result.deleted)
        self.assertTrue(result.cleanup_failed)
        self.assertIsNotNone(result.residual_path)
        self.assertEqual(self.manager.list_loras(), [])
        self.assertTrue(Path(result.residual_path).exists())

    def test_delete_only_ever_touches_its_own_entry_folder(self):
        other_source = self.source_dir / "other.safetensors"
        other_source.write_bytes(b"other weights")
        other = self.manager.import_lora("Other", [str(other_source)], self.library_root)
        other_folder = self.library_root / other.lora_id

        self.manager.delete(self.lora.lora_id, self.library_root)

        self.assertTrue(other_folder.exists())
        self.assertEqual(self.manager.list_loras(), [other])


class LoRALibraryManagerUpdateTest(unittest.TestCase):
    """
    Mission 090: LoRALibraryManager.update() — a single combined
    mutation for name/engine/architecture/trigger_word/version, mirroring
    CharacterManager.update() (Mission 074) rather than LoRAManager's
    split update()/update_name() (an artifact of two separate missions,
    not a contract to reproduce here).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.registry_dir = Path(self.tmp_dir) / "Registry"
        self.library_root = Path(self.tmp_dir) / "Library"
        self.source_dir = Path(self.tmp_dir) / "External"
        self.source_dir.mkdir()

        self.event_bus = EventBus()
        self.manager = LoRALibraryManager(
            storage_directory=self.registry_dir, event_bus=self.event_bus
        )

        source = self.source_dir / "style.safetensors"
        source.write_bytes(b"weights")
        self.lora = self.manager.import_lora(
            "Style", [str(source)], self.library_root,
            engine="ComfyUI", architecture="SDXL", trigger_word="mytrigger", version="1.0",
        )

    def _lora_folder(self) -> Path:
        return self.library_root / self.lora.lora_id

    def test_update_unknown_id_returns_false(self):
        result = self.manager.update("unknown-id", name="New")
        self.assertFalse(result)

    def test_update_no_fields_provided_is_a_no_op(self):
        events = []
        self.event_bus.subscribe(LORA_LIBRARY_UPDATED, lambda payload: events.append(payload))

        result = self.manager.update(self.lora.lora_id)

        self.assertFalse(result)
        self.assertEqual(events, [])

    def test_update_identical_values_is_idempotent(self):
        events = []
        self.event_bus.subscribe(LORA_LIBRARY_UPDATED, lambda payload: events.append(payload))

        result = self.manager.update(
            self.lora.lora_id,
            name="Style", engine="ComfyUI", architecture="SDXL",
            trigger_word="mytrigger", version="1.0",
        )

        self.assertFalse(result)
        self.assertEqual(events, [])

    def test_update_name_only_leaves_other_fields_untouched(self):
        result = self.manager.update(self.lora.lora_id, name="Renamed")

        self.assertTrue(result)
        stored = self.manager.get(self.lora.lora_id)
        self.assertEqual(stored.name, "Renamed")
        self.assertEqual(stored.engine, "ComfyUI")
        self.assertEqual(stored.architecture, "SDXL")
        self.assertEqual(stored.trigger_word, "mytrigger")
        self.assertEqual(stored.version, "1.0")

    def test_update_all_five_fields_single_save_and_single_event(self):
        events = []
        self.event_bus.subscribe(LORA_LIBRARY_UPDATED, lambda payload: events.append(dict(payload)))

        result = self.manager.update(
            self.lora.lora_id,
            name="Renamed", engine="Kohya", architecture="Flux",
            trigger_word="newtrigger", version="2.0",
        )

        self.assertTrue(result)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["name"], "Renamed")
        self.assertEqual(events[0]["engine"], "Kohya")
        self.assertEqual(events[0]["architecture"], "Flux")
        self.assertEqual(events[0]["trigger_word"], "newtrigger")
        self.assertEqual(events[0]["version"], "2.0")

        # Persisted for real — a fresh Manager instance reading the same
        # registry file must see the exact same 5 values.
        reloaded = LoRALibraryManager(storage_directory=self.registry_dir)
        stored = reloaded.get(self.lora.lora_id)
        self.assertEqual(stored.name, "Renamed")
        self.assertEqual(stored.engine, "Kohya")
        self.assertEqual(stored.architecture, "Flux")
        self.assertEqual(stored.trigger_word, "newtrigger")
        self.assertEqual(stored.version, "2.0")

    def test_update_empty_string_is_a_legitimate_distinct_value(self):
        result = self.manager.update(self.lora.lora_id, trigger_word="")

        self.assertTrue(result)
        self.assertEqual(self.manager.get(self.lora.lora_id).trigger_word, "")

    def test_update_revert_to_original_values_is_idempotent_again(self):
        self.manager.update(self.lora.lora_id, name="Temporary")

        events = []
        self.event_bus.subscribe(LORA_LIBRARY_UPDATED, lambda payload: events.append(payload))
        result = self.manager.update(self.lora.lora_id, name="Style")

        self.assertTrue(result)
        self.assertEqual(len(events), 1)

        events.clear()
        # Reverted back to the value already on disk — the second call is
        # a true no-op, not just "same as the last call made".
        result_again = self.manager.update(self.lora.lora_id, name="Style")
        self.assertFalse(result_again)
        self.assertEqual(events, [])

    def test_update_never_touches_lora_id_or_files(self):
        original_id = self.lora.lora_id
        original_files = list(self.lora.files)

        self.manager.update(self.lora.lora_id, name="Renamed", engine="Kohya")

        stored = self.manager.get(original_id)
        self.assertEqual(stored.lora_id, original_id)
        self.assertEqual(stored.files, original_files)

    def test_update_never_touches_the_filesystem(self):
        folder = self._lora_folder()
        original_contents = sorted(p.name for p in folder.iterdir())

        self.manager.update(self.lora.lora_id, name="Completely Renamed")

        # Still keyed by lora_id, never by name — no folder rename/move.
        self.assertTrue(folder.exists())
        self.assertEqual(sorted(p.name for p in folder.iterdir()), original_contents)

    def test_update_persistence_failure_rolls_back_all_five_fields(self):
        events = []
        self.event_bus.subscribe(LORA_LIBRARY_UPDATED, lambda payload: events.append(payload))

        with patch.object(
            LoRALibraryStorage, "save", side_effect=LoRALibraryStorageError("disk full")
        ):
            with self.assertRaises(LoRALibraryError):
                self.manager.update(
                    self.lora.lora_id,
                    name="Renamed", engine="Kohya", architecture="Flux",
                    trigger_word="newtrigger", version="2.0",
                )

        self.assertEqual(events, [])
        stored = self.manager.get(self.lora.lora_id)
        self.assertEqual(stored.name, "Style")
        self.assertEqual(stored.engine, "ComfyUI")
        self.assertEqual(stored.architecture, "SDXL")
        self.assertEqual(stored.trigger_word, "mytrigger")
        self.assertEqual(stored.version, "1.0")

        # The registry file on disk was never touched by the failed save
        # either — a fresh Manager instance confirms the same values.
        reloaded = LoRALibraryManager(storage_directory=self.registry_dir)
        reloaded_stored = reloaded.get(self.lora.lora_id)
        self.assertEqual(reloaded_stored.name, "Style")


class LoRALibraryManagerSetThumbnailTest(unittest.TestCase):
    """
    Mission 093: LoRALibraryManager.set_thumbnail() — mirrors
    LoRAManager.set_thumbnail()'s transactional contract (Missions
    047/067/080), adapted to this Manager's own conventions: a real
    failure (copy or persistence) always raises LoRALibraryError, never
    a bare None (unlike LoRAManager.set_thumbnail(), which collapses
    "unknown lora" and "failed copy" into the same None) — only an
    unknown lora_id returns None, matching get()/update()/delete().
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.registry_dir = Path(self.tmp_dir) / "Registry"
        self.library_root = Path(self.tmp_dir) / "Library"
        self.source_dir = Path(self.tmp_dir) / "External"
        self.source_dir.mkdir()

        self.event_bus = EventBus()
        self.manager = LoRALibraryManager(
            storage_directory=self.registry_dir, event_bus=self.event_bus
        )

        source = self.source_dir / "style.safetensors"
        source.write_bytes(b"weights")
        self.lora = self.manager.import_lora("Style", [str(source)], self.library_root)

    def _lora_folder(self) -> Path:
        return self.library_root / self.lora.lora_id

    def _thumbnail_source(self, name: str, content: bytes = b"png-bytes") -> Path:
        path = self.source_dir / name
        path.write_bytes(content)
        return path

    def test_set_thumbnail_unknown_lora_returns_none(self):
        source = self._thumbnail_source("thumb.png")
        self.assertIsNone(
            self.manager.set_thumbnail("unknown-id", str(source), self.library_root)
        )

    def test_set_thumbnail_first_thumbnail_copies_file_and_persists(self):
        events = []
        self.event_bus.subscribe(LORA_LIBRARY_UPDATED, lambda payload: events.append(payload))
        source = self._thumbnail_source("thumb.png")

        result = self.manager.set_thumbnail(self.lora.lora_id, str(source), self.library_root)

        self.assertIsInstance(result, LoRALibraryThumbnailResult)
        self.assertFalse(result.cleanup_failed)
        self.assertIsNone(result.residual_path)
        self.assertTrue(Path(result.thumbnail).exists())
        self.assertTrue(WorkspaceStorage.is_inside(result.thumbnail, self._lora_folder()))
        self.assertEqual(source.read_bytes(), Path(result.thumbnail).read_bytes())
        # Source stays intact — never moved, only copied.
        self.assertTrue(source.exists())
        self.assertEqual(len(events), 1)

        stored = self.manager.get(self.lora.lora_id)
        self.assertEqual(stored.thumbnail, result.thumbnail)

        reloaded = LoRALibraryManager(storage_directory=self.registry_dir)
        self.assertEqual(reloaded.get(self.lora.lora_id).thumbnail, result.thumbnail)

    def test_set_thumbnail_first_thumbnail_leaves_no_temp_or_orphan_file(self):
        source = self._thumbnail_source("thumb.png")
        result = self.manager.set_thumbnail(self.lora.lora_id, str(source), self.library_root)

        folder_contents = sorted(p.name for p in self._lora_folder().iterdir())
        # Exactly the original imported file plus the one new thumbnail —
        # no partial/temp artifact left behind.
        self.assertEqual(len(folder_contents), 2)
        self.assertIn(Path(result.thumbnail).name, folder_contents)

    def test_set_thumbnail_replacement_deletes_previous_owned_file(self):
        first = self._thumbnail_source("first.png")
        first_result = self.manager.set_thumbnail(self.lora.lora_id, str(first), self.library_root)
        old_thumbnail_path = Path(first_result.thumbnail)
        self.assertTrue(old_thumbnail_path.exists())

        second = self._thumbnail_source("second.png", content=b"different-bytes")
        second_result = self.manager.set_thumbnail(
            self.lora.lora_id, str(second), self.library_root
        )

        self.assertFalse(second_result.cleanup_failed)
        self.assertNotEqual(second_result.thumbnail, first_result.thumbnail)
        self.assertFalse(old_thumbnail_path.exists())
        self.assertTrue(Path(second_result.thumbnail).exists())
        self.assertEqual(
            Path(second_result.thumbnail).read_bytes(), second.read_bytes()
        )

    def test_set_thumbnail_never_deletes_an_external_passthrough_thumbnail(self):
        # Constructed defensively: today no write path can ever leave
        # lora.thumbnail pointing outside this entry's own folder, but
        # the is_inside() ownership guard must still refuse to delete
        # anything external if it somehow did.
        external = self._thumbnail_source("external.png")
        self.lora.thumbnail = str(external)

        second = self._thumbnail_source("second.png", content=b"different-bytes")
        result = self.manager.set_thumbnail(self.lora.lora_id, str(second), self.library_root)

        self.assertFalse(result.cleanup_failed)
        self.assertTrue(external.exists())

    def test_set_thumbnail_invalid_source_raises_and_does_not_mutate(self):
        missing = self.source_dir / "does-not-exist.png"

        with self.assertRaises(LoRALibraryError):
            self.manager.set_thumbnail(self.lora.lora_id, str(missing), self.library_root)

        stored = self.manager.get(self.lora.lora_id)
        self.assertEqual(stored.thumbnail, "")
        reloaded = LoRALibraryManager(storage_directory=self.registry_dir)
        self.assertEqual(reloaded.get(self.lora.lora_id).thumbnail, "")

    def test_set_thumbnail_copy_failure_publishes_no_event(self):
        events = []
        self.event_bus.subscribe(LORA_LIBRARY_UPDATED, lambda payload: events.append(payload))
        missing = self.source_dir / "does-not-exist.png"

        with self.assertRaises(LoRALibraryError):
            self.manager.set_thumbnail(self.lora.lora_id, str(missing), self.library_root)

        self.assertEqual(events, [])

    def test_set_thumbnail_persistence_failure_rolls_back_and_cleans_up_new_copy(self):
        events = []
        self.event_bus.subscribe(LORA_LIBRARY_UPDATED, lambda payload: events.append(payload))
        source = self._thumbnail_source("thumb.png")

        with patch.object(
            LoRALibraryStorage, "save", side_effect=LoRALibraryStorageError("disk full")
        ):
            with self.assertRaises(LoRALibraryError):
                self.manager.set_thumbnail(self.lora.lora_id, str(source), self.library_root)

        self.assertEqual(events, [])
        stored = self.manager.get(self.lora.lora_id)
        self.assertEqual(stored.thumbnail, "")

        # The newly copied thumbnail file was cleaned up — only the
        # original imported file remains in the entry's folder.
        folder_contents = [p.name for p in self._lora_folder().iterdir()]
        self.assertEqual(folder_contents, ["style.safetensors"])

        reloaded = LoRALibraryManager(storage_directory=self.registry_dir)
        self.assertEqual(reloaded.get(self.lora.lora_id).thumbnail, "")

    def test_set_thumbnail_persistence_failure_after_replacement_restores_previous_value(self):
        first = self._thumbnail_source("first.png")
        first_result = self.manager.set_thumbnail(self.lora.lora_id, str(first), self.library_root)

        second = self._thumbnail_source("second.png", content=b"different-bytes")
        with patch.object(
            LoRALibraryStorage, "save", side_effect=LoRALibraryStorageError("disk full")
        ):
            with self.assertRaises(LoRALibraryError):
                self.manager.set_thumbnail(self.lora.lora_id, str(second), self.library_root)

        stored = self.manager.get(self.lora.lora_id)
        self.assertEqual(stored.thumbnail, first_result.thumbnail)
        self.assertTrue(Path(first_result.thumbnail).exists())


class LoRALibraryManagerListGetTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.manager = LoRALibraryManager(storage_directory=Path(self.tmp_dir) / "Registry")
        self.source_dir = Path(self.tmp_dir) / "External"
        self.source_dir.mkdir()
        self.library_root = Path(self.tmp_dir) / "Library"

        source = self.source_dir / "style.safetensors"
        source.write_bytes(b"weights")
        self.lora = self.manager.import_lora("Style", [str(source)], self.library_root)

    def test_list_loras_returns_lora_objects_not_dicts(self):
        result = self.manager.list_loras()
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], LoRA)
        self.assertNotIsInstance(result[0], dict)

    def test_list_loras_returns_a_fresh_list_each_time(self):
        first = self.manager.list_loras()
        first.clear()
        self.assertEqual(len(self.manager.list_loras()), 1)

    def test_get_known_id_returns_the_lora(self):
        result = self.manager.get(self.lora.lora_id)
        self.assertIsInstance(result, LoRA)
        self.assertEqual(result.lora_id, self.lora.lora_id)

    def test_get_unknown_id_returns_none(self):
        self.assertIsNone(self.manager.get("unknown-id"))


class LoRALibraryPersistenceRoundTripTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.registry_dir = Path(self.tmp_dir) / "Registry"
        self.library_root = Path(self.tmp_dir) / "Library"
        self.source_dir = Path(self.tmp_dir) / "External"
        self.source_dir.mkdir()

    def test_registry_persists_across_manager_instances(self):
        manager_a = LoRALibraryManager(storage_directory=self.registry_dir)
        source = self.source_dir / "style.safetensors"
        source.write_bytes(b"weights")
        lora = manager_a.import_lora("Style", [str(source)], self.library_root)

        manager_b = LoRALibraryManager(storage_directory=self.registry_dir)
        loaded = manager_b.list_loras()

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0], lora)

        # The registry file itself only ever holds LoRA.to_dict() shape.
        raw = json.loads((self.registry_dir / LoRALibraryStorage.FILE_NAME).read_text(encoding="utf-8"))
        self.assertEqual(list(raw.keys()), ["loras"])
        self.assertEqual(raw["loras"][0]["lora_id"], lora.lora_id)

    def test_corrupted_registry_entries_are_kept_as_is_never_silently_dropped(self):
        # A hand-edited registry with two entries sharing a lora_id — a
        # pathological but tolerated case, same defensive philosophy as
        # the rest of the codebase toward a hand-edited project.json.
        LoRALibraryStorage.save(
            self.registry_dir,
            {
                "loras": [
                    LoRA(lora_id="dup", name="First").to_dict(),
                    LoRA(lora_id="dup", name="Second").to_dict(),
                ]
            },
        )

        manager = LoRALibraryManager(storage_directory=self.registry_dir)

        self.assertEqual(len(manager.list_loras()), 2)
        # get() returns the first match, never crashes.
        self.assertEqual(manager.get("dup").name, "First")

    def test_non_dict_entries_in_registry_are_ignored_defensively(self):
        LoRALibraryStorage.save(
            self.registry_dir,
            {"loras": [LoRA(lora_id="ok", name="Kept").to_dict(), "garbage", 42, None]},
        )

        manager = LoRALibraryManager(storage_directory=self.registry_dir)

        self.assertEqual(len(manager.list_loras()), 1)
        self.assertEqual(manager.list_loras()[0].name, "Kept")


class ApplicationSettingsLoraLibraryLockTest(unittest.TestCase):
    """
    The path-change lock contract (decision validated by the architect):
    registre vide -> changement autorisé ; registre non vide -> refusé
    (LoRALibraryPathLockedError, aucune mutation) ; même valeur -> no-op
    autorisé même registre non vide ; suppression de la dernière entrée
    -> de nouveau autorisé ; aucun déplacement/copie/suppression
    automatique lors d'un changement ou d'un refus.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.source_dir = Path(self.tmp_dir) / "External"
        self.source_dir.mkdir()
        self.library_root = Path(self.tmp_dir) / "Library"

        self.lora_library_manager = LoRALibraryManager(
            storage_directory=Path(self.tmp_dir) / "Registry"
        )
        self.application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "AppSettings",
            lora_library_manager=self.lora_library_manager,
        )

    def _import_one(self) -> LoRA:
        source = self.source_dir / "style.safetensors"
        source.write_bytes(b"weights")
        return self.lora_library_manager.import_lora(
            "Style", [str(source)], self.library_root
        )

    def test_empty_registry_change_is_allowed_and_persisted(self):
        self.assertTrue(
            self.application_settings_manager.update(lora_library_path="D:/New Library")
        )
        self.assertEqual(
            self.application_settings_manager.settings.lora_library_path, "D:/New Library"
        )

    def test_non_empty_registry_change_is_refused(self):
        self._import_one()
        previous = self.application_settings_manager.settings.lora_library_path

        with self.assertRaises(LoRALibraryPathLockedError):
            self.application_settings_manager.update(lora_library_path="D:/New Library")

        self.assertEqual(
            self.application_settings_manager.settings.lora_library_path, previous
        )

    def test_no_mutation_or_persistence_on_refusal(self):
        lora = self._import_one()
        entries_before = list((self.library_root / lora.lora_id).iterdir())

        with patch("src.managers.application_settings_manager.ApplicationSettingsStorage.save") as save_spy:
            with self.assertRaises(LoRALibraryPathLockedError):
                self.application_settings_manager.update(lora_library_path="D:/New Library")
            save_spy.assert_not_called()

        # Nothing was moved/copied/deleted on disk — the entry's own
        # folder still contains exactly what it did before the refusal,
        # and no new "D:/New Library" folder was ever created.
        self.assertEqual(list((self.library_root / lora.lora_id).iterdir()), entries_before)

    def test_same_path_as_current_is_a_no_op_even_with_non_empty_registry(self):
        self._import_one()
        current = self.application_settings_manager.settings.lora_library_path

        with patch("src.managers.application_settings_manager.ApplicationSettingsStorage.save") as save_spy:
            result = self.application_settings_manager.update(lora_library_path=current)
            save_spy.assert_not_called()

        self.assertFalse(result)
        self.assertEqual(self.application_settings_manager.settings.lora_library_path, current)

    def test_change_allowed_again_after_deleting_the_last_entry(self):
        lora = self._import_one()

        with self.assertRaises(LoRALibraryPathLockedError):
            self.application_settings_manager.update(lora_library_path="D:/New Library")

        self.lora_library_manager.delete(lora.lora_id, self.library_root)

        self.assertTrue(
            self.application_settings_manager.update(lora_library_path="D:/New Library")
        )
        self.assertEqual(
            self.application_settings_manager.settings.lora_library_path, "D:/New Library"
        )

    def test_manager_without_lora_library_manager_never_locks(self):
        # Optional dependency (None) — the lock structurally never fires.
        standalone = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "Standalone"
        )
        self.assertTrue(standalone.update(lora_library_path="D:/Anything"))


class ApplicationSettingsExposureRootLockTest(unittest.TestCase):
    """
    Mission 149: the forge_lora_expose_path/comfyui_lora_expose_path
    lock contract — same shape and rationale as
    ApplicationSettingsLoraLibraryLockTest above, adapted to a per-
    provider exposure (LoRALibraryManager.has_any_exposure()) rather
    than a non-empty registry: a real exposure in the currently
    configured root refuses the change (LoRAExposureRootLockedError, no
    mutation) ; the same value is always a no-op even while exposed ;
    the two providers are independent ; the change is allowed again
    once unexposed. Reuses a real LoRALibraryManager with an actually
    exposed hardlink, exactly like the sibling class above reuses a
    real imported entry.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.source_dir = Path(self.tmp_dir) / "External"
        self.source_dir.mkdir()
        self.library_root = Path(self.tmp_dir) / "Library"
        self.forge_root_a = Path(self.tmp_dir) / "ForgeA"
        self.forge_root_b = Path(self.tmp_dir) / "ForgeB"
        self.comfyui_root_a = Path(self.tmp_dir) / "ComfyUIA"
        self.comfyui_root_b = Path(self.tmp_dir) / "ComfyUIB"
        for root in (self.forge_root_a, self.forge_root_b, self.comfyui_root_a, self.comfyui_root_b):
            root.mkdir()

        self.lora_library_manager = LoRALibraryManager(
            storage_directory=Path(self.tmp_dir) / "Registry"
        )
        self.application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "AppSettings",
            lora_library_manager=self.lora_library_manager,
        )

        source = self.source_dir / "style.safetensors"
        source.write_bytes(b"weights")
        self.lora = self.lora_library_manager.import_lora(
            "Style", [str(source)], self.library_root
        )

    # --- Forge ---

    def test_forge_change_is_refused_while_exposed_in_current_root(self):
        self.lora_library_manager.expose_to_forge(self.lora, self.forge_root_a)
        self.application_settings_manager.update(forge_lora_expose_path=str(self.forge_root_a))

        with self.assertRaises(LoRAExposureRootLockedError):
            self.application_settings_manager.update(
                forge_lora_expose_path=str(self.forge_root_b)
            )

        self.assertEqual(
            self.application_settings_manager.settings.forge_lora_expose_path,
            str(self.forge_root_a),
        )

    def test_forge_same_value_is_a_no_op_even_while_exposed(self):
        self.lora_library_manager.expose_to_forge(self.lora, self.forge_root_a)
        self.application_settings_manager.update(forge_lora_expose_path=str(self.forge_root_a))

        with patch("src.managers.application_settings_manager.ApplicationSettingsStorage.save") as save_spy:
            result = self.application_settings_manager.update(
                forge_lora_expose_path=str(self.forge_root_a)
            )
            save_spy.assert_not_called()

        self.assertFalse(result)

    def test_forge_change_allowed_again_after_unexpose(self):
        self.lora_library_manager.expose_to_forge(self.lora, self.forge_root_a)
        self.application_settings_manager.update(forge_lora_expose_path=str(self.forge_root_a))

        self.lora_library_manager.unexpose_from_forge(self.lora, self.forge_root_a)

        self.assertTrue(
            self.application_settings_manager.update(
                forge_lora_expose_path=str(self.forge_root_b)
            )
        )
        self.assertEqual(
            self.application_settings_manager.settings.forge_lora_expose_path,
            str(self.forge_root_b),
        )

    # --- ComfyUI (same contract, independent field) ---

    def test_comfyui_change_is_refused_while_exposed_in_current_root(self):
        self.lora_library_manager.expose_to_comfyui(self.lora, self.comfyui_root_a)
        self.application_settings_manager.update(
            comfyui_lora_expose_path=str(self.comfyui_root_a)
        )

        with self.assertRaises(LoRAExposureRootLockedError):
            self.application_settings_manager.update(
                comfyui_lora_expose_path=str(self.comfyui_root_b)
            )

        self.assertEqual(
            self.application_settings_manager.settings.comfyui_lora_expose_path,
            str(self.comfyui_root_a),
        )

    def test_comfyui_same_value_is_a_no_op_even_while_exposed(self):
        self.lora_library_manager.expose_to_comfyui(self.lora, self.comfyui_root_a)
        self.application_settings_manager.update(
            comfyui_lora_expose_path=str(self.comfyui_root_a)
        )

        with patch("src.managers.application_settings_manager.ApplicationSettingsStorage.save") as save_spy:
            result = self.application_settings_manager.update(
                comfyui_lora_expose_path=str(self.comfyui_root_a)
            )
            save_spy.assert_not_called()

        self.assertFalse(result)

    def test_comfyui_change_allowed_again_after_unexpose(self):
        self.lora_library_manager.expose_to_comfyui(self.lora, self.comfyui_root_a)
        self.application_settings_manager.update(
            comfyui_lora_expose_path=str(self.comfyui_root_a)
        )

        self.lora_library_manager.unexpose_from_comfyui(self.lora, self.comfyui_root_a)

        self.assertTrue(
            self.application_settings_manager.update(
                comfyui_lora_expose_path=str(self.comfyui_root_b)
            )
        )

    # --- Independence between the two providers ---

    def test_forge_lock_does_not_affect_comfyui(self):
        self.lora_library_manager.expose_to_forge(self.lora, self.forge_root_a)
        self.application_settings_manager.update(forge_lora_expose_path=str(self.forge_root_a))

        # ComfyUI has no exposure anywhere — its own field stays freely
        # changeable regardless of Forge's active lock.
        self.assertTrue(
            self.application_settings_manager.update(
                comfyui_lora_expose_path=str(self.comfyui_root_a)
            )
        )

    def test_comfyui_lock_does_not_affect_forge(self):
        self.lora_library_manager.expose_to_comfyui(self.lora, self.comfyui_root_a)
        self.application_settings_manager.update(
            comfyui_lora_expose_path=str(self.comfyui_root_a)
        )

        self.assertTrue(
            self.application_settings_manager.update(forge_lora_expose_path=str(self.forge_root_a))
        )

    def test_both_providers_exposed_are_locked_independently(self):
        self.lora_library_manager.expose_to_forge(self.lora, self.forge_root_a)
        self.lora_library_manager.expose_to_comfyui(self.lora, self.comfyui_root_a)
        self.application_settings_manager.update(
            forge_lora_expose_path=str(self.forge_root_a),
            comfyui_lora_expose_path=str(self.comfyui_root_a),
        )

        with self.assertRaises(LoRAExposureRootLockedError):
            self.application_settings_manager.update(
                forge_lora_expose_path=str(self.forge_root_b)
            )
        with self.assertRaises(LoRAExposureRootLockedError):
            self.application_settings_manager.update(
                comfyui_lora_expose_path=str(self.comfyui_root_b)
            )

        # Unexposing Forge only unlocks Forge — ComfyUI, still exposed,
        # remains independently locked.
        self.lora_library_manager.unexpose_from_forge(self.lora, self.forge_root_a)
        self.assertTrue(
            self.application_settings_manager.update(
                forge_lora_expose_path=str(self.forge_root_b)
            )
        )
        with self.assertRaises(LoRAExposureRootLockedError):
            self.application_settings_manager.update(
                comfyui_lora_expose_path=str(self.comfyui_root_b)
            )

    # --- Atomicity of a combined update() call ---

    def test_refused_exposure_change_does_not_persist_other_fields_in_the_same_call(self):
        self.lora_library_manager.expose_to_forge(self.lora, self.forge_root_a)
        self.application_settings_manager.update(forge_lora_expose_path=str(self.forge_root_a))
        previous_ollama_url = self.application_settings_manager.settings.ollama_url

        with patch("src.managers.application_settings_manager.ApplicationSettingsStorage.save") as save_spy:
            with self.assertRaises(LoRAExposureRootLockedError):
                self.application_settings_manager.update(
                    forge_lora_expose_path=str(self.forge_root_b),
                    ollama_url="http://newhost:11434",
                )
            save_spy.assert_not_called()

        self.assertEqual(
            self.application_settings_manager.settings.forge_lora_expose_path,
            str(self.forge_root_a),
        )
        self.assertEqual(self.application_settings_manager.settings.ollama_url, previous_ollama_url)

    def test_manager_without_lora_library_manager_never_locks_exposure(self):
        standalone = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "Standalone"
        )
        self.assertTrue(standalone.update(forge_lora_expose_path=str(self.forge_root_a)))
        self.assertTrue(standalone.update(comfyui_lora_expose_path=str(self.comfyui_root_a)))

    # --- Mission 152: inspection non concluante (fail-closed) ---
    #
    # has_any_exposure() is always called with the CURRENT root (never
    # the proposed new one) — so each test below first establishes a
    # real, non-empty current root via an ordinary successful update()
    # (no mock active, no exposure yet, so it succeeds normally), then
    # only activates the os.scandir mock for the guarded second call.
    # An empty current root would short-circuit has_any_exposure() via
    # its own `if not expose_root: return False` before ever reaching
    # the filesystem, which would never exercise this guard at all.

    def test_forge_inspection_error_is_propagated_without_mutation(self):
        self.application_settings_manager.update(forge_lora_expose_path=str(self.forge_root_a))

        with patch("os.scandir", side_effect=PermissionError("simulated access denied")):
            with patch(
                "src.managers.application_settings_manager.ApplicationSettingsStorage.save"
            ) as save_spy:
                with self.assertRaises(LoRAExposureRootInspectionError):
                    self.application_settings_manager.update(
                        forge_lora_expose_path=str(self.forge_root_b)
                    )
                save_spy.assert_not_called()

        self.assertEqual(
            self.application_settings_manager.settings.forge_lora_expose_path,
            str(self.forge_root_a),
        )

    def test_comfyui_inspection_error_is_propagated_without_mutation(self):
        self.application_settings_manager.update(
            comfyui_lora_expose_path=str(self.comfyui_root_a)
        )

        with patch("os.scandir", side_effect=OSError("simulated network failure")):
            with patch(
                "src.managers.application_settings_manager.ApplicationSettingsStorage.save"
            ) as save_spy:
                with self.assertRaises(LoRAExposureRootInspectionError):
                    self.application_settings_manager.update(
                        comfyui_lora_expose_path=str(self.comfyui_root_b)
                    )
                save_spy.assert_not_called()

        self.assertEqual(
            self.application_settings_manager.settings.comfyui_lora_expose_path,
            str(self.comfyui_root_a),
        )

    def test_forge_inspection_error_does_not_affect_comfyui(self):
        self.application_settings_manager.update(forge_lora_expose_path=str(self.forge_root_a))

        with patch("os.scandir", side_effect=PermissionError("simulated access denied")):
            with self.assertRaises(LoRAExposureRootInspectionError):
                self.application_settings_manager.update(
                    forge_lora_expose_path=str(self.forge_root_b)
                )

            # ComfyUI has never been configured — its own field is
            # still "" and therefore reaches has_any_exposure("") only
            # via the falsy-root short-circuit, never os.scandir() —
            # so it succeeds even while the Forge mock is still active.
            self.assertTrue(
                self.application_settings_manager.update(
                    comfyui_lora_expose_path=str(self.comfyui_root_a)
                )
            )

    def test_same_value_resubmission_is_still_a_no_op_even_if_inspection_would_fail(self):
        self.lora_library_manager.expose_to_forge(self.lora, self.forge_root_a)
        self.application_settings_manager.update(forge_lora_expose_path=str(self.forge_root_a))

        # forge_lora_expose_path_changed is False for this call — the
        # inspection primitive must never even be reached.
        with patch("os.scandir", side_effect=PermissionError("simulated access denied")):
            result = self.application_settings_manager.update(
                forge_lora_expose_path=str(self.forge_root_a)
            )

        self.assertFalse(result)

    def test_refused_inspection_error_does_not_persist_other_fields_in_the_same_call(self):
        self.application_settings_manager.update(forge_lora_expose_path=str(self.forge_root_a))
        previous_ollama_url = self.application_settings_manager.settings.ollama_url

        with patch("os.scandir", side_effect=PermissionError("simulated access denied")):
            with patch(
                "src.managers.application_settings_manager.ApplicationSettingsStorage.save"
            ) as save_spy:
                with self.assertRaises(LoRAExposureRootInspectionError):
                    self.application_settings_manager.update(
                        forge_lora_expose_path=str(self.forge_root_b),
                        ollama_url="http://newhost:11434",
                    )
                save_spy.assert_not_called()

        self.assertEqual(
            self.application_settings_manager.settings.forge_lora_expose_path,
            str(self.forge_root_a),
        )
        self.assertEqual(self.application_settings_manager.settings.ollama_url, previous_ollama_url)


class LoRALibraryManagerComfyUIExposureTest(unittest.TestCase):
    """
    Mission 095: expose_to_comfyui()/unexpose_from_comfyui() — every
    hardlink created/removed here is real, on a real temp directory
    (same mechanism validated empirically against the architect's real
    ComfyUI installation, see MISSION_095.md §3.4/§3.6), never mocked
    for the nominal cases. Only os.link()/Path.unlink() failure and
    cross-volume scenarios are simulated (a second real NTFS volume is
    not guaranteed to exist in every environment this suite runs in).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.registry_dir = Path(self.tmp_dir) / "Registry"
        self.library_root = Path(self.tmp_dir) / "Library"
        self.expose_root = Path(self.tmp_dir) / "Expose"
        self.source_dir = Path(self.tmp_dir) / "External"
        self.source_dir.mkdir()
        self.expose_root.mkdir()

        self.manager = LoRALibraryManager(storage_directory=self.registry_dir)

        source = self.source_dir / "style.safetensors"
        source.write_bytes(b"weights")
        self.lora = self.manager.import_lora("My Style", [str(source)], self.library_root)

    def _alias_path(self, result: LoRAComfyUIExposureResult) -> Path:
        return self.expose_root / result.alias_name.replace("\\", "/")

    def test_expose_creates_a_real_hardlink_under_a_dedicated_subfolder(self):
        result = self.manager.expose_to_comfyui(self.lora, self.expose_root)

        self.assertFalse(result.cleanup_failed)
        self.assertIsNone(result.residual_path)
        self.assertTrue(result.alias_name.startswith("AIStudioToolkit\\"))
        self.assertIn(self.lora.lora_id, result.alias_name)

        alias_path = self._alias_path(result)
        self.assertTrue(alias_path.is_file())
        self.assertTrue(os.path.samefile(alias_path, self.lora.files[0]))

    def test_expose_is_idempotent(self):
        first = self.manager.expose_to_comfyui(self.lora, self.expose_root)
        alias_path = self._alias_path(first)
        inode_before = alias_path.stat().st_ino

        second = self.manager.expose_to_comfyui(self.lora, self.expose_root)

        self.assertEqual(first, second)
        self.assertEqual(alias_path.stat().st_ino, inode_before)
        # Exactly one alias on disk — the idempotent path never creates
        # a second link.
        subfolder = self.expose_root / "AIStudioToolkit"
        self.assertEqual(len(list(subfolder.iterdir())), 1)

    def test_expose_after_rename_replaces_the_stale_alias(self):
        first = self.manager.expose_to_comfyui(self.lora, self.expose_root)
        old_alias_path = self._alias_path(first)

        self.manager.update(self.lora.lora_id, name="Renamed Style")

        second = self.manager.expose_to_comfyui(self.lora, self.expose_root)

        self.assertNotEqual(first.alias_name, second.alias_name)
        self.assertFalse(second.cleanup_failed)
        self.assertFalse(old_alias_path.exists())
        new_alias_path = self._alias_path(second)
        self.assertTrue(new_alias_path.is_file())
        self.assertTrue(os.path.samefile(new_alias_path, self.lora.files[0]))
        # Exactly one alias remains — the stale one was actually removed,
        # not merely superseded while still lingering on disk.
        subfolder = self.expose_root / "AIStudioToolkit"
        self.assertEqual(len(list(subfolder.iterdir())), 1)

    def test_expose_after_rename_reports_stale_cleanup_failure_without_losing_the_new_exposure(self):
        first = self.manager.expose_to_comfyui(self.lora, self.expose_root)
        old_alias_path = self._alias_path(first)

        self.manager.update(self.lora.lora_id, name="Renamed Style")

        with patch.object(Path, "unlink", side_effect=OSError("locked by another process")):
            result = self.manager.expose_to_comfyui(self.lora, self.expose_root)

        # The new hardlink is created *first* — a failure to clean up the
        # stale one never rolls back the already-succeeded re-exposure.
        self.assertTrue(result.cleanup_failed)
        self.assertEqual(result.residual_path, str(old_alias_path))
        new_alias_path = self._alias_path(result)
        self.assertTrue(new_alias_path.is_file())
        self.assertTrue(os.path.samefile(new_alias_path, self.lora.files[0]))

    def test_expose_rejects_zero_files(self):
        empty_lora = LoRA(lora_id="no-files", name="Empty", files=[])

        with self.assertRaises(LoRALibraryError) as ctx:
            self.manager.expose_to_comfyui(empty_lora, self.expose_root)

        self.assertIn("0 model file", str(ctx.exception))

    def test_expose_rejects_multiple_files(self):
        second_source = self.source_dir / "extra.safetensors"
        second_source.write_bytes(b"more weights")
        multi_lora = LoRA(
            lora_id="multi-files",
            name="Multi",
            files=[self.lora.files[0], str(second_source)],
        )

        with self.assertRaises(LoRALibraryError) as ctx:
            self.manager.expose_to_comfyui(multi_lora, self.expose_root)

        self.assertIn("2 model file", str(ctx.exception))

    def test_expose_rejects_unconfigured_expose_root(self):
        with self.assertRaises(LoRALibraryError):
            self.manager.expose_to_comfyui(self.lora, "")

    def test_expose_rejects_missing_expose_root_directory(self):
        with self.assertRaises(LoRALibraryError):
            self.manager.expose_to_comfyui(self.lora, self.expose_root / "DoesNotExist")

    def test_expose_rejects_missing_source_file(self):
        Path(self.lora.files[0]).unlink()

        with self.assertRaises(LoRALibraryError):
            self.manager.expose_to_comfyui(self.lora, self.expose_root)

    def test_expose_rejects_incompatible_volumes(self):
        # A second real NTFS volume is not guaranteed to exist in every
        # environment this suite runs in — the same-volume check itself
        # (_same_volume, a plain os.stat().st_dev comparison) is simulated
        # here rather than the filesystem, but the check that consumes it
        # (expose_to_comfyui()) runs exactly as it would in production.
        with patch.object(LoRALibraryManager, "_same_volume", return_value=False):
            with self.assertRaises(LoRALibraryError) as ctx:
                self.manager.expose_to_comfyui(self.lora, self.expose_root)

        self.assertIn("same filesystem volume", str(ctx.exception))
        # Nothing was created — the check runs before any mutation.
        self.assertFalse((self.expose_root / "AIStudioToolkit").exists())

    def test_expose_refuses_to_overwrite_a_collision_at_the_expected_name(self):
        first = self.manager.expose_to_comfyui(self.lora, self.expose_root)
        alias_path = self._alias_path(first)

        # Simulate external tampering: the deterministic alias name now
        # points to a different file than the LoRA's current source.
        alias_path.unlink()
        alias_path.write_bytes(b"not the real file")

        with self.assertRaises(LoRALibraryError) as ctx:
            self.manager.expose_to_comfyui(self.lora, self.expose_root)

        self.assertIn("refusing to overwrite", str(ctx.exception))
        self.assertEqual(alias_path.read_bytes(), b"not the real file")

    def test_expose_refuses_to_overwrite_a_collision_found_under_a_stale_name(self):
        first = self.manager.expose_to_comfyui(self.lora, self.expose_root)
        stale_alias_path = self._alias_path(first)

        self.manager.update(self.lora.lora_id, name="Renamed Style")

        # External tampering on the *stale* alias this time — still found
        # by lora_id, still refused rather than silently deleted/replaced.
        stale_alias_path.unlink()
        stale_alias_path.write_bytes(b"not the real file either")

        with self.assertRaises(LoRALibraryError) as ctx:
            self.manager.expose_to_comfyui(self.lora, self.expose_root)

        self.assertIn("refusing to overwrite", str(ctx.exception))
        self.assertEqual(stale_alias_path.read_bytes(), b"not the real file either")

    def test_expose_raises_a_clear_error_on_link_creation_failure(self):
        with patch("os.link", side_effect=OSError("disk full")):
            with self.assertRaises(LoRALibraryError):
                self.manager.expose_to_comfyui(self.lora, self.expose_root)

    def test_expose_finding_more_than_one_alias_for_the_same_lora_id_raises(self):
        # Structurally unreachable through this Manager's own code paths
        # (see _find_existing_alias()'s docstring) — only reachable via
        # external tampering, reproduced explicitly here.
        subfolder = self.expose_root / "AIStudioToolkit"
        subfolder.mkdir()
        (subfolder / f"first__{self.lora.lora_id}.safetensors").write_bytes(b"a")
        (subfolder / f"second__{self.lora.lora_id}.safetensors").write_bytes(b"b")

        with self.assertRaises(LoRALibraryError) as ctx:
            self.manager.expose_to_comfyui(self.lora, self.expose_root)

        self.assertIn("Multiple ComfyUI exposure aliases", str(ctx.exception))

    def test_unexpose_removes_the_alias(self):
        result = self.manager.expose_to_comfyui(self.lora, self.expose_root)
        alias_path = self._alias_path(result)
        self.assertTrue(alias_path.is_file())

        removed = self.manager.unexpose_from_comfyui(self.lora, self.expose_root)

        self.assertTrue(removed)
        self.assertFalse(alias_path.exists())
        # The canonical library file itself is never touched.
        self.assertTrue(Path(self.lora.files[0]).is_file())

    def test_unexpose_is_idempotent_when_never_exposed(self):
        removed = self.manager.unexpose_from_comfyui(self.lora, self.expose_root)
        self.assertFalse(removed)

    def test_unexpose_is_idempotent_when_called_twice(self):
        self.manager.expose_to_comfyui(self.lora, self.expose_root)

        first = self.manager.unexpose_from_comfyui(self.lora, self.expose_root)
        second = self.manager.unexpose_from_comfyui(self.lora, self.expose_root)

        self.assertTrue(first)
        self.assertFalse(second)

    def test_unexpose_is_a_no_op_when_expose_root_is_not_configured(self):
        self.manager.expose_to_comfyui(self.lora, self.expose_root)

        removed = self.manager.unexpose_from_comfyui(self.lora, "")

        self.assertFalse(removed)

    def test_unexpose_finds_the_alias_after_a_rename(self):
        # The alias is located by lora_id alone — a rename between
        # exposure and unexposure must never leave it unremovable.
        result = self.manager.expose_to_comfyui(self.lora, self.expose_root)
        alias_path = self._alias_path(result)

        self.manager.update(self.lora.lora_id, name="Renamed Before Unexpose")

        removed = self.manager.unexpose_from_comfyui(self.lora, self.expose_root)

        self.assertTrue(removed)
        self.assertFalse(alias_path.exists())

    def test_unexpose_raises_a_clear_error_on_real_removal_failure(self):
        self.manager.expose_to_comfyui(self.lora, self.expose_root)

        with patch.object(Path, "unlink", side_effect=OSError("locked by another process")):
            with self.assertRaises(LoRALibraryError):
                self.manager.unexpose_from_comfyui(self.lora, self.expose_root)

    def test_delete_of_a_never_exposed_entry_is_unaffected(self):
        # Non-regression: an entry that was never exposed deletes exactly
        # as it did before Mission 095 introduced exposure at all.
        result = self.manager.delete(self.lora.lora_id, self.library_root)
        self.assertTrue(result.deleted)
        self.assertEqual(self.manager.list_loras(), [])


class LoRALibraryManagerForgeExposureTest(unittest.TestCase):
    """
    Mission 108: expose_to_forge() — symmetric to expose_to_comfyui()
    above, sharing the exact same private _expose() mechanism. Only the
    representative subset of cases called out by MISSION_108.md §7 is
    duplicated here (unconfigured root, file cardinality, cross-volume,
    idempotence, rename, collision) — the full exhaustive case list
    (structurally-unreachable multiple-alias, real removal failures...)
    is already proven once, against the shared mechanism, by
    LoRALibraryManagerComfyUIExposureTest above.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.registry_dir = Path(self.tmp_dir) / "Registry"
        self.library_root = Path(self.tmp_dir) / "Library"
        self.expose_root = Path(self.tmp_dir) / "ForgeExpose"
        self.source_dir = Path(self.tmp_dir) / "External"
        self.source_dir.mkdir()
        self.expose_root.mkdir()

        self.manager = LoRALibraryManager(storage_directory=self.registry_dir)

        source = self.source_dir / "style.safetensors"
        source.write_bytes(b"weights")
        self.lora = self.manager.import_lora("My Style", [str(source)], self.library_root)

    def _alias_path(self, result: LoRAComfyUIExposureResult) -> Path:
        return self.expose_root / result.alias_name.replace("\\", "/")

    def test_expose_to_forge_creates_a_real_hardlink_under_a_dedicated_subfolder(self):
        result = self.manager.expose_to_forge(self.lora, self.expose_root)

        self.assertFalse(result.cleanup_failed)
        self.assertIsNone(result.residual_path)
        self.assertTrue(result.alias_name.startswith("AIStudioToolkit\\"))
        self.assertIn(self.lora.lora_id, result.alias_name)

        alias_path = self._alias_path(result)
        self.assertTrue(alias_path.is_file())
        self.assertTrue(os.path.samefile(alias_path, self.lora.files[0]))

    def test_expose_to_forge_is_idempotent(self):
        first = self.manager.expose_to_forge(self.lora, self.expose_root)
        alias_path = self._alias_path(first)
        inode_before = alias_path.stat().st_ino

        second = self.manager.expose_to_forge(self.lora, self.expose_root)

        self.assertEqual(first, second)
        self.assertEqual(alias_path.stat().st_ino, inode_before)

    def test_expose_to_forge_after_rename_replaces_the_stale_alias(self):
        first = self.manager.expose_to_forge(self.lora, self.expose_root)
        old_alias_path = self._alias_path(first)

        self.manager.update(self.lora.lora_id, name="Renamed Style")

        second = self.manager.expose_to_forge(self.lora, self.expose_root)

        self.assertNotEqual(first.alias_name, second.alias_name)
        self.assertFalse(old_alias_path.exists())
        new_alias_path = self._alias_path(second)
        self.assertTrue(new_alias_path.is_file())

    def test_expose_to_forge_rejects_zero_files(self):
        empty_lora = LoRA(lora_id="no-files", name="Empty", files=[])

        with self.assertRaises(LoRALibraryError) as ctx:
            self.manager.expose_to_forge(empty_lora, self.expose_root)

        self.assertIn("0 model file", str(ctx.exception))

    def test_expose_to_forge_rejects_unconfigured_expose_root(self):
        with self.assertRaises(LoRALibraryError) as ctx:
            self.manager.expose_to_forge(self.lora, "")

        # The error message names Forge/forge_lora_expose_path, never a
        # leftover ComfyUI-flavored string from the shared mechanism.
        self.assertIn("Forge", str(ctx.exception))
        self.assertIn("forge_lora_expose_path", str(ctx.exception))
        self.assertNotIn("ComfyUI", str(ctx.exception))

    def test_expose_to_forge_rejects_incompatible_volumes(self):
        with patch.object(LoRALibraryManager, "_same_volume", return_value=False):
            with self.assertRaises(LoRALibraryError) as ctx:
                self.manager.expose_to_forge(self.lora, self.expose_root)

        self.assertIn("same filesystem volume", str(ctx.exception))

    def test_expose_to_forge_refuses_to_overwrite_a_collision_at_the_expected_name(self):
        first = self.manager.expose_to_forge(self.lora, self.expose_root)
        alias_path = self._alias_path(first)

        alias_path.unlink()
        alias_path.write_bytes(b"not the real file")

        with self.assertRaises(LoRALibraryError) as ctx:
            self.manager.expose_to_forge(self.lora, self.expose_root)

        self.assertIn("refusing to overwrite", str(ctx.exception))

    def test_expose_to_comfyui_and_expose_to_forge_use_independent_roots(self):
        # The same LoRA can be exposed to both engines simultaneously,
        # each under its own physical root, with no collision and no
        # concurrent lora_name source — the logical LoRA selection stays
        # single, only the exposure call differs.
        comfyui_expose_root = Path(self.tmp_dir) / "ComfyUIExpose"
        comfyui_expose_root.mkdir()

        forge_result = self.manager.expose_to_forge(self.lora, self.expose_root)
        comfyui_result = self.manager.expose_to_comfyui(self.lora, comfyui_expose_root)

        forge_alias = self.expose_root / forge_result.alias_name.replace("\\", "/")
        comfyui_alias = comfyui_expose_root / comfyui_result.alias_name.replace("\\", "/")

        self.assertTrue(forge_alias.is_file())
        self.assertTrue(comfyui_alias.is_file())
        self.assertNotEqual(forge_alias, comfyui_alias)
        self.assertTrue(os.path.samefile(forge_alias, self.lora.files[0]))
        self.assertTrue(os.path.samefile(comfyui_alias, self.lora.files[0]))

    def test_unexpose_from_forge_removes_the_alias(self):
        # Mission 135: unexpose_from_forge() closes the lifecycle gap
        # left open since Mission 108 — the canonical file itself must
        # never be touched, only the managed hardlink alias.
        result = self.manager.expose_to_forge(self.lora, self.expose_root)
        alias_path = self._alias_path(result)
        source_path = Path(self.lora.files[0])

        removed = self.manager.unexpose_from_forge(self.lora, self.expose_root)

        self.assertTrue(removed)
        self.assertFalse(alias_path.exists())
        self.assertTrue(source_path.is_file())

    def test_unexpose_from_forge_is_a_no_op_when_never_exposed(self):
        removed = self.manager.unexpose_from_forge(self.lora, self.expose_root)
        self.assertFalse(removed)

    def test_unexpose_from_forge_is_a_no_op_when_expose_root_is_not_configured(self):
        self.manager.expose_to_forge(self.lora, self.expose_root)
        removed = self.manager.unexpose_from_forge(self.lora, "")
        self.assertFalse(removed)

    def test_unexpose_from_forge_raises_a_clear_error_on_real_removal_failure(self):
        self.manager.expose_to_forge(self.lora, self.expose_root)
        source_path = Path(self.lora.files[0])

        with patch.object(Path, "unlink", side_effect=OSError("locked by another process")):
            with self.assertRaises(LoRALibraryError) as ctx:
                self.manager.unexpose_from_forge(self.lora, self.expose_root)

        self.assertIn("Forge", str(ctx.exception))
        self.assertIn(self.lora.lora_id, str(ctx.exception))
        self.assertTrue(source_path.is_file())


class LoRALibraryManagerHasAnyExposureTest(unittest.TestCase):
    """
    Mission 149: has_any_exposure() — the read-only primitive used
    exclusively by ApplicationSettingsManager.update() to guard a
    Forge/ComfyUI exposure-root Settings change. Provider-agnostic by
    construction (expose_to_forge()/expose_to_comfyui() share the exact
    same underlying alias mechanism) — exercised here via
    expose_to_comfyui()/unexpose_from_comfyui() only, since the
    mechanism this method inspects is identical regardless of which
    engine created the alias.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.registry_dir = Path(self.tmp_dir) / "Registry"
        self.library_root = Path(self.tmp_dir) / "Library"
        self.expose_root = Path(self.tmp_dir) / "Expose"
        self.source_dir = Path(self.tmp_dir) / "External"
        self.source_dir.mkdir()
        self.expose_root.mkdir()

        self.manager = LoRALibraryManager(storage_directory=self.registry_dir)

        source = self.source_dir / "style.safetensors"
        source.write_bytes(b"weights")
        self.lora = self.manager.import_lora("My Style", [str(source)], self.library_root)

    def test_empty_library_has_no_exposure(self):
        empty_manager = LoRALibraryManager(storage_directory=Path(self.tmp_dir) / "EmptyRegistry")
        self.assertFalse(empty_manager.has_any_exposure(self.expose_root))

    def test_unconfigured_root_has_no_exposure(self):
        self.manager.expose_to_comfyui(self.lora, self.expose_root)
        self.assertFalse(self.manager.has_any_exposure(""))

    def test_nonexistent_root_has_no_exposure(self):
        self.assertFalse(self.manager.has_any_exposure(self.expose_root / "DoesNotExist"))

    def test_root_without_toolkit_subfolder_has_no_exposure(self):
        self.assertFalse((self.expose_root / "AIStudioToolkit").exists())
        self.assertFalse(self.manager.has_any_exposure(self.expose_root))

    def test_known_exposure_is_detected(self):
        self.manager.expose_to_comfyui(self.lora, self.expose_root)
        self.assertTrue(self.manager.has_any_exposure(self.expose_root))

    def test_no_longer_exposed_after_unexpose(self):
        self.manager.expose_to_comfyui(self.lora, self.expose_root)
        self.manager.unexpose_from_comfyui(self.lora, self.expose_root)
        self.assertFalse(self.manager.has_any_exposure(self.expose_root))

    def test_unrelated_foreign_file_never_locks(self):
        subfolder = self.expose_root / "AIStudioToolkit"
        subfolder.mkdir()
        (subfolder / "leftover_from_something_else.txt").write_text("not a LoRA alias")

        self.assertFalse(self.manager.has_any_exposure(self.expose_root))

    def test_alias_belonging_to_an_unknown_lora_id_never_locks(self):
        subfolder = self.expose_root / "AIStudioToolkit"
        subfolder.mkdir()
        (subfolder / "orphan__not-a-real-lora-id.safetensors").write_bytes(b"stale")

        self.assertFalse(self.manager.has_any_exposure(self.expose_root))

    def test_ambiguous_multiple_aliases_still_raises_instead_of_silently_reporting_true(self):
        # Mirrors the existing ambiguity contract of
        # _find_existing_alias() (Mission 095) — an already-tampered/
        # corrupted exposure state must never be silently collapsed into
        # a bare True/False by this guard-facing method.
        self.manager.expose_to_comfyui(self.lora, self.expose_root)
        subfolder = self.expose_root / "AIStudioToolkit"
        duplicate = subfolder / f"second_alias__{self.lora.lora_id}.safetensors"
        duplicate.write_bytes(b"tampered duplicate")

        with self.assertRaises(LoRALibraryError):
            self.manager.has_any_exposure(self.expose_root)

    def test_empty_registry_never_touches_the_filesystem(self):
        # Mission 152: the empty-registry short-circuit must skip
        # _list_expose_subfolder() entirely — nothing to match against,
        # so no directory listing is even attempted.
        empty_manager = LoRALibraryManager(storage_directory=Path(self.tmp_dir) / "EmptyRegistry2")
        with patch("os.scandir") as scandir_mock:
            self.assertFalse(empty_manager.has_any_exposure(self.expose_root))
        scandir_mock.assert_not_called()

    def test_permission_error_during_inspection_raises_instead_of_false(self):
        # Mission 152: a PermissionError while listing the exposure
        # subfolder must never be silently read as "no exposure found" —
        # Path.glob() itself would have absorbed it into an empty result
        # (verified against the real pathlib source during the M152
        # mini-audit), which is exactly the false negative this mission
        # closes.
        subfolder = self.expose_root / "AIStudioToolkit"
        subfolder.mkdir()

        with patch("os.scandir", side_effect=PermissionError("simulated access denied")):
            with self.assertRaises(LoRAExposureRootInspectionError):
                self.manager.has_any_exposure(self.expose_root)

    def test_generic_oserror_during_inspection_raises_instead_of_false(self):
        # Mission 152: an OSError that is not a PermissionError (e.g. a
        # network share going away mid-listing) is not caught by
        # Path.glob()'s own except clause either — it must still surface
        # as the dedicated inspection error, never as a silent False.
        subfolder = self.expose_root / "AIStudioToolkit"
        subfolder.mkdir()

        with patch("os.scandir", side_effect=OSError("simulated network failure")):
            with self.assertRaises(LoRAExposureRootInspectionError):
                self.manager.has_any_exposure(self.expose_root)

    def test_not_ready_volume_during_inspection_raises_instead_of_false(self):
        # Mission 152: a not-ready/disconnected volume surfaces as an
        # OSError carrying winerror=21 on Windows — simulated
        # deterministically here rather than via a real removable drive.
        # The inspection primitive must not special-case this winerror
        # as an absence (unlike Path.is_dir(), which silently treats it
        # as one) — it is not proof the root holds no exposure.
        subfolder = self.expose_root / "AIStudioToolkit"
        subfolder.mkdir()
        not_ready_error = OSError("simulated device not ready")
        not_ready_error.winerror = 21

        with patch("os.scandir", side_effect=not_ready_error):
            with self.assertRaises(LoRAExposureRootInspectionError):
                self.manager.has_any_exposure(self.expose_root)

    def test_inspection_error_message_never_leaks_a_raw_traceback(self):
        # Mission 152: the exception's own message is what SettingsPage
        # will display verbatim via str(exc) — it must stay a clear
        # sentence, not a dump of the underlying OSError's repr/args
        # tuple or any traceback-shaped text.
        subfolder = self.expose_root / "AIStudioToolkit"
        subfolder.mkdir()

        with patch("os.scandir", side_effect=PermissionError("simulated access denied")):
            with self.assertRaises(LoRAExposureRootInspectionError) as ctx:
                self.manager.has_any_exposure(self.expose_root)

        message = str(ctx.exception)
        self.assertNotIn("Traceback", message)
        self.assertIn(str(self.expose_root), message)


if __name__ == "__main__":
    unittest.main()
