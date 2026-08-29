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
    LoRALibraryPathLockedError,
)
from src.managers.lora_library_manager import (
    LoRALibraryDeletionResult,
    LoRALibraryError,
    LoRALibraryManager,
    LORA_LIBRARY_DELETED,
    LORA_LIBRARY_IMPORTED,
)


class LoRALibraryStorageTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def test_absent_file_returns_none(self):
        directory = Path(self.tmp_dir) / "Absent"
        self.assertIsNone(LoRALibraryStorage.load(directory))
        self.assertFalse(directory.exists())

    def test_invalid_json_returns_none_with_warning(self):
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

        result = LoRALibraryStorage.load(directory)

        self.assertIsNone(result)
        self.assertEqual(len(log_records), 1)

    def test_non_dict_root_returns_none(self):
        directory = Path(self.tmp_dir) / "NonDict"
        directory.mkdir(parents=True)
        (directory / LoRALibraryStorage.FILE_NAME).write_text("[1, 2, 3]", encoding="utf-8")
        self.assertIsNone(LoRALibraryStorage.load(directory))

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


if __name__ == "__main__":
    unittest.main()
