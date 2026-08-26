"""
Integration coverage for the Workspace create/open/save/close cycle,
exercising WorkspaceManager, WorkspaceStorage and EventBus together
with the real DashboardPage/ImagesPage widgets — the same wiring
MainWindow uses (see src/ui/main_window.py).
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from src.core.event_bus import EventBus
from src.domain.character import Character
from src.domain.dataset import Dataset
from src.domain.image import Image
from src.domain.lora import LoRA
from src.domain.model import Model
from src.domain.workflow import Workflow
from src.infrastructure.storage.workspace_storage import (
    WorkspaceStorage,
    WorkspaceStorageError,
    WorkspaceRenamePermissionError as StorageRenamePermissionError,
)
from src.managers.character_manager import CharacterManager
from src.managers.dataset_manager import DatasetManager
from src.managers.workspace_manager import (
    WorkspaceManager,
    WorkspaceManagerError,
    WorkspaceRenamePermissionError,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_SAVED,
    WORKSPACE_CLOSED,
    WORKSPACE_RENAMED,
)
from src.ui.pages.dashboard_page import DashboardPage
from src.ui.pages.images_page import ImagesPage

WORKSPACE_EVENTS = (
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_SAVED,
    WORKSPACE_CLOSED,
)

# A QApplication instance is required before any QWidget can be created.
_app = QApplication.instance() or QApplication([])


class WorkspaceRoundTripTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "RoundTripProject"

    def _wire(self, event_bus, workspace_manager):
        dashboard = DashboardPage()
        images = ImagesPage(workspace_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, dashboard.update_project)
            event_bus.subscribe(event_name, images.update_images)

        return dashboard, images

    def test_full_create_import_save_close_reopen_cycle(self):

        event_bus = EventBus()
        manager = WorkspaceManager(event_bus=event_bus)
        dashboard, images = self._wire(event_bus, manager)

        # 1. Create
        manager.create(self.folder)
        self.assertEqual(dashboard.projectCard.value.text(), self.folder.name)
        self.assertEqual(dashboard.imagesCard.value.text(), "0")

        # 2. Import images — Mission 028: add_images() physically
        # copies each external source into <root>/images/, so real
        # source files (outside the workspace) are required here.
        ref1_source = Path(self.tmp_dir) / "ref1.png"
        ref2_source = Path(self.tmp_dir) / "ref2.png"
        ref1_source.write_bytes(b"fake-png-bytes-1")
        ref2_source.write_bytes(b"fake-png-bytes-2")

        result = manager.add_images([str(ref1_source), str(ref2_source)])
        self.assertEqual(result.added, 2)
        self.assertEqual(result.failed, [])

        expected_internal = [
            str(self.folder / "images" / "ref1.png"),
            str(self.folder / "images" / "ref2.png"),
        ]
        self.assertEqual(
            [images.list_widget.item(i).text() for i in range(images.list_widget.count())],
            ["ref1.png", "ref2.png"],
        )
        self.assertEqual(
            [image.file_path for image in manager.current_workspace.images],
            expected_internal,
        )
        self.assertEqual(dashboard.imagesCard.value.text(), "2")

        # External sources are never touched by the copy.
        self.assertTrue(ref1_source.exists())
        self.assertTrue(ref2_source.exists())

        # 3. Save
        manager.save()

        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertEqual(
            [image["file_path"] for image in on_disk["images"]],
            expected_internal,
        )
        self.assertTrue(all(image["image_id"] for image in on_disk["images"]))

        # 4. Close
        manager.close()
        self.assertIsNone(manager.current_workspace)
        self.assertEqual(dashboard.projectCard.value.text(), "Aucun")
        self.assertEqual(images.list_widget.count(), 0)

        # 5. Reopen — fresh manager/event_bus/pages, simulating a real
        # application restart rather than reusing in-memory state.
        event_bus_2 = EventBus()
        manager_2 = WorkspaceManager(event_bus=event_bus_2)
        dashboard_2, images_2 = self._wire(event_bus_2, manager_2)

        workspace = manager_2.open(self.folder)
        self.assertIsNotNone(workspace)
        self.assertEqual(
            [image.file_path for image in workspace.images],
            expected_internal,
        )

        # 6. Dashboard and ImagesPage reflect the restored data
        self.assertEqual(dashboard_2.projectCard.value.text(), self.folder.name)
        self.assertEqual(dashboard_2.imagesCard.value.text(), "2")
        self.assertEqual(
            [images_2.list_widget.item(i).text() for i in range(images_2.list_widget.count())],
            ["ref1.png", "ref2.png"],
        )

    def test_failed_open_does_not_close_current_workspace(self):
        """
        Business rule: attempting to open an invalid folder must never
        close the workspace that is currently open. Regression test for
        a bug found during manual testing of Commit 6 and fixed in
        Commit 8 (WorkspaceManager.open() used to unconditionally reset
        current_workspace to None whenever the target folder had no
        project.json, even with a valid workspace already open).
        """

        event_bus = EventBus()
        manager = WorkspaceManager(event_bus=event_bus)
        manager.create(self.folder)

        invalid_folder = Path(self.tmp_dir) / "NoProjectJsonHere"
        invalid_folder.mkdir()

        result = manager.open(invalid_folder)

        self.assertIsNone(result)
        self.assertIsNotNone(manager.current_workspace)
        self.assertEqual(manager.current_workspace.name, self.folder.name)


class WorkspaceRenameTest(unittest.TestCase):
    """
    Mission 027: WorkspaceManager.rename() — physical folder rename,
    Workspace.root/name update, internal-path remapping, external-path
    preservation, and the rollback-on-save-failure strategy (see
    MISSION_027.md section 7/8 for the full transactional design this
    class verifies).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "OldName"
        self.external_dir = Path(self.tmp_dir) / "ExternalAssets"
        self.external_dir.mkdir()

        self.event_bus = EventBus()
        self.manager = WorkspaceManager(event_bus=self.event_bus)
        self.manager.create(self.folder)

    def _new_root(self, name="NewName"):
        return self.folder.parent / name

    # --- Simple rename ---

    def test_simple_rename_updates_root_and_name_and_moves_folder(self):
        old_root = self.folder

        result = self.manager.rename("NewName")

        self.assertTrue(result)
        self.assertEqual(self.manager.current_workspace.name, "NewName")
        self.assertEqual(self.manager.current_workspace.root, self._new_root())
        self.assertFalse(old_root.exists())
        self.assertTrue(self._new_root().exists())

    def test_idempotent_no_op_when_name_and_folder_already_match(self):
        published = []
        self.event_bus.subscribe(WORKSPACE_RENAMED, lambda payload: published.append(payload))

        with patch.object(WorkspaceStorage, "save") as save_mock:
            result = self.manager.rename("OldName")

        self.assertFalse(result)
        save_mock.assert_not_called()
        self.assertEqual(published, [])

    def test_repairs_desynced_workspace_name_without_physical_rename(self):
        # Simulates a Workspace.name left stale by a past manual Explorer
        # rename (audit finding) — the folder's real name is already
        # "OldName", only Workspace.name is out of sync.
        self.manager.current_workspace.name = "StaleName"

        result = self.manager.rename("OldName")

        self.assertTrue(result)
        self.assertEqual(self.manager.current_workspace.name, "OldName")
        self.assertEqual(self.manager.current_workspace.root, self.folder)
        self.assertTrue(self.folder.exists())

    # --- Character.name untouched ---

    def test_character_name_is_never_touched(self):
        character = Character(character_id="c1", name="Aria")
        self.manager.current_workspace.characters.append(character)
        self.manager.save()

        self.manager.rename("NewName")

        restored = self.manager.current_workspace.characters[0]
        self.assertEqual(restored.name, "Aria")

    # --- Internal paths remapped ---

    def test_outputs_image_is_remapped_and_survives_physical_move(self):
        outputs_dir = self.folder / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        image_path = outputs_dir / "generated.png"
        image_path.write_bytes(b"fake-png-bytes")

        self.manager.current_workspace.images.append(
            Image(image_id="img1", file_path=str(image_path))
        )
        self.manager.save()

        self.manager.rename("NewName")

        expected = str(self._new_root() / "outputs" / "generated.png")
        restored = self.manager.current_workspace.images[0]
        self.assertEqual(restored.file_path, expected)
        self.assertTrue(Path(expected).exists())

    def test_image_imported_via_add_images_is_remapped_on_rename(self):
        # Mission 028 synergy check (MISSION_028.md section 15): an
        # image copied into <root>/images/ by add_images() is, by
        # construction, a path under Workspace.root — proves the
        # existing Mission 027 remap already covers it without any
        # change to rename()/_remap_path().
        source = self.external_dir / "photo.png"
        source.write_bytes(b"fake-photo-bytes")

        self.manager.add_images([str(source)])
        internal_path = self.manager.current_workspace.images[0].file_path
        self.assertTrue(Path(internal_path).exists())

        self.manager.rename("NewName")

        expected = str(self._new_root() / "images" / "photo.png")
        restored = self.manager.current_workspace.images[0]
        self.assertEqual(restored.file_path, expected)
        self.assertTrue(Path(expected).exists())
        # External source untouched by either the import or the rename.
        self.assertTrue(source.exists())

    def test_character_dataset_image_is_remapped(self):
        image_path = self.folder / "captions" / "img.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(b"data")

        character = Character(character_id="c1", name="Aria")
        dataset = Dataset(dataset_id="d1", name="Main")
        dataset.images.append(Image(image_id="img1", file_path=str(image_path)))
        character.datasets.append(dataset)
        self.manager.current_workspace.characters.append(character)
        self.manager.save()

        self.manager.rename("NewName")

        expected = str(self._new_root() / "captions" / "img.png")
        restored = self.manager.current_workspace.characters[0]
        self.assertEqual(restored.datasets[0].images[0].file_path, expected)

    def test_model_workflow_lora_internal_paths_are_remapped(self):
        model_path = self.folder / "models" / "checkpoints" / "model.safetensors"
        workflow_path = self.folder / "workflow.json"
        lora_file_path = self.folder / "models" / "loras" / "lora.safetensors"
        thumbnail_path = self.folder / "models" / "loras" / "lora_thumb.png"
        for path in (model_path, workflow_path, lora_file_path, thumbnail_path):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"data")

        self.manager.current_workspace.models.append(
            Model(model_id="m1", name="M", file_path=str(model_path))
        )
        self.manager.current_workspace.workflows.append(
            Workflow(workflow_id="w1", name="W", file_path=str(workflow_path))
        )
        character = Character(character_id="c1", name="Aria")
        character.loras.append(
            LoRA(
                lora_id="l1",
                name="L",
                files=[str(lora_file_path)],
                thumbnail=str(thumbnail_path),
            )
        )
        self.manager.current_workspace.characters.append(character)
        self.manager.save()

        self.manager.rename("NewName")

        new_root = self._new_root()
        workspace = self.manager.current_workspace
        self.assertEqual(
            workspace.models[0].file_path,
            str(new_root / "models" / "checkpoints" / "model.safetensors"),
        )
        self.assertEqual(
            workspace.workflows[0].file_path, str(new_root / "workflow.json")
        )
        restored_lora = workspace.characters[0].loras[0]
        self.assertEqual(
            restored_lora.files[0],
            str(new_root / "models" / "loras" / "lora.safetensors"),
        )
        self.assertEqual(
            restored_lora.thumbnail,
            str(new_root / "models" / "loras" / "lora_thumb.png"),
        )

    def test_empty_model_and_workflow_file_path_preserved(self):
        self.manager.current_workspace.models.append(
            Model(model_id="m1", name="M", file_path="")
        )
        self.manager.current_workspace.workflows.append(
            Workflow(workflow_id="w1", name="W", file_path="")
        )
        self.manager.save()

        self.manager.rename("NewName")

        workspace = self.manager.current_workspace
        self.assertEqual(workspace.models[0].file_path, "")
        self.assertEqual(workspace.workflows[0].file_path, "")

    # --- External paths untouched ---

    def test_external_paths_are_strictly_unchanged(self):
        external_image = self.external_dir / "ref.png"
        external_image.write_bytes(b"data")
        external_model = self.external_dir / "checkpoint.safetensors"
        external_model.write_bytes(b"data")

        self.manager.current_workspace.images.append(
            Image(image_id="i1", file_path=str(external_image))
        )
        self.manager.current_workspace.models.append(
            Model(model_id="m1", name="M", file_path=str(external_model))
        )
        self.manager.save()

        self.manager.rename("NewName")

        workspace = self.manager.current_workspace
        self.assertEqual(workspace.images[0].file_path, str(external_image))
        self.assertEqual(workspace.models[0].file_path, str(external_model))

    # --- Persistence across close/reopen ---

    def test_persistence_after_close_and_reopen(self):
        outputs_dir = self.folder / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        image_path = outputs_dir / "generated.png"
        image_path.write_bytes(b"data")
        self.manager.current_workspace.images.append(
            Image(image_id="i1", file_path=str(image_path))
        )
        self.manager.save()

        self.manager.rename("NewName")
        new_root = self._new_root()

        self.manager.close()

        reopened_manager = WorkspaceManager(event_bus=EventBus())
        workspace = reopened_manager.open(new_root)

        self.assertEqual(workspace.name, "NewName")
        self.assertEqual(
            workspace.images[0].file_path, str(new_root / "outputs" / "generated.png")
        )

    # --- Active selection preserved (no reset on rename) ---

    def test_active_character_and_dataset_selection_preserved_after_rename(self):
        character_manager = CharacterManager(self.manager, event_bus=self.event_bus)
        dataset_manager = DatasetManager(
            character_manager, self.manager, event_bus=self.event_bus
        )

        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Main")
        dataset_manager.select(dataset.dataset_id)

        self.manager.rename("NewName")

        self.assertEqual(character_manager.active_character_id, character.character_id)
        self.assertEqual(dataset_manager.active_dataset_id, dataset.dataset_id)
        self.assertEqual(character_manager.active_character.name, "Aria")

    # --- Failure scenarios ---

    def test_target_folder_already_existing_raises_and_leaves_source_untouched(self):
        colliding = self._new_root()
        colliding.mkdir()

        with self.assertRaises(WorkspaceManagerError):
            self.manager.rename("NewName")

        self.assertTrue(self.folder.exists())
        self.assertEqual(self.manager.current_workspace.root, self.folder)
        self.assertEqual(self.manager.current_workspace.name, "OldName")

    def test_filesystem_rename_failure_leaves_domain_state_untouched(self):
        original_workspace = self.manager.current_workspace

        with patch.object(
            WorkspaceStorage, "rename_folder", side_effect=WorkspaceStorageError("boom")
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.manager.rename("NewName")

        self.assertIs(self.manager.current_workspace, original_workspace)
        self.assertEqual(self.manager.current_workspace.root, self.folder)
        self.assertEqual(self.manager.current_workspace.name, "OldName")
        self.assertTrue(self.folder.exists())

    def test_save_failure_after_successful_rename_rolls_back_filesystem_and_domain(self):
        original_workspace = self.manager.current_workspace

        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.manager.rename("NewName")

        # Filesystem rollback: old folder restored, new folder gone.
        self.assertTrue(self.folder.exists())
        self.assertFalse(self._new_root().exists())

        # The restored project.json is exactly what was there before —
        # never touched by the failed save (mocked out entirely here;
        # WorkspaceStorageAtomicSaveTest below proves this holds even
        # for a real mid-write failure, not just a fully-mocked save()).
        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertEqual(on_disk["name"], "OldName")

        # Domain state was never mutated.
        self.assertIs(self.manager.current_workspace, original_workspace)
        self.assertEqual(self.manager.current_workspace.root, self.folder)
        self.assertEqual(self.manager.current_workspace.name, "OldName")

    def test_rollback_failure_raises_explicit_actionable_error_never_a_silent_false(self):
        real_rename_folder = WorkspaceStorage.rename_folder
        call_count = {"n": 0}

        def flaky_rename_folder(old_root, new_root):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # The forward rename (old -> new) is allowed to succeed
                # for real; only the rollback attempt (new -> old) fails.
                return real_rename_folder(old_root, new_root)
            raise WorkspaceStorageError("rollback also failed")

        original_workspace = self.manager.current_workspace

        with patch.object(
            WorkspaceStorage, "rename_folder", side_effect=flaky_rename_folder
        ), patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ):
            with self.assertRaises(WorkspaceManagerError) as ctx:
                self.manager.rename("NewName")

        message = str(ctx.exception)
        self.assertIn(str(self._new_root()), message)
        self.assertIn("OldName", message)
        self.assertIn(str(self.folder), message)

        # Physically still renamed (the rollback itself failed).
        self.assertTrue(self._new_root().exists())
        self.assertFalse(self.folder.exists())

        # Domain state was never mutated — it still (harmlessly)
        # disagrees with the disk, exactly as documented (MISSION_027.md
        # section 8): this mismatch is why the error message must be
        # actionable rather than a bare failure.
        self.assertIs(self.manager.current_workspace, original_workspace)
        self.assertEqual(self.manager.current_workspace.root, self.folder)

    # --- Permission-denied (WinError 5) UX handling (Mission 027 real
    # smoke test: confirmed via Process Explorer to be explorer.exe
    # holding handles on the project's subfolders, not an application
    # resource leak — see MISSION_027.md section 20) ---

    def test_permission_denied_on_rename_raises_the_specific_permission_error_type(self):
        original_workspace = self.manager.current_workspace

        with patch.object(
            WorkspaceStorage,
            "rename_folder",
            side_effect=StorageRenamePermissionError("[WinError 5] Access is denied"),
        ):
            with self.assertRaises(WorkspaceRenamePermissionError):
                self.manager.rename("NewName")

        # current_workspace strictly untouched — same guarantee as any
        # other failure of the initial rename step.
        self.assertIs(self.manager.current_workspace, original_workspace)
        self.assertEqual(self.manager.current_workspace.root, self.folder)
        self.assertTrue(self.folder.exists())

    def test_other_rename_failures_are_never_misclassified_as_permission_denied(self):
        # A different OSError (not access-denied) must keep raising the
        # plain WorkspaceManagerError — the specific handling must never
        # swallow unrelated failures under the friendly message.
        with patch.object(
            WorkspaceStorage,
            "rename_folder",
            side_effect=WorkspaceStorageError("A folder already exists at ..."),
        ):
            with self.assertRaises(WorkspaceManagerError) as ctx:
                self.manager.rename("NewName")

        self.assertNotIsInstance(ctx.exception, WorkspaceRenamePermissionError)

    def test_no_workspace_renamed_event_published_on_permission_denied(self):
        published = []
        self.event_bus.subscribe(WORKSPACE_RENAMED, lambda payload: published.append(payload))

        with patch.object(
            WorkspaceStorage,
            "rename_folder",
            side_effect=StorageRenamePermissionError("[WinError 5] Access is denied"),
        ):
            with self.assertRaises(WorkspaceRenamePermissionError):
                self.manager.rename("NewName")

        self.assertEqual(published, [])

    def test_rollback_failure_due_to_permission_denied_includes_actionable_hint(self):
        real_rename_folder = WorkspaceStorage.rename_folder
        call_count = {"n": 0}

        def flaky_rename_folder(old_root, new_root):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return real_rename_folder(old_root, new_root)
            raise StorageRenamePermissionError("[WinError 5] Access is denied")

        with patch.object(
            WorkspaceStorage, "rename_folder", side_effect=flaky_rename_folder
        ), patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ):
            with self.assertRaises(WorkspaceManagerError) as ctx:
                self.manager.rename("NewName")

        # Still the generic (richly detailed) rollback-failure error, not
        # the simple permission type — the manual-recovery details must
        # never be replaced by the friendly message in this more severe
        # combined-failure case, only enriched with an extra hint.
        self.assertNotIsInstance(ctx.exception, WorkspaceRenamePermissionError)
        self.assertIn("access-denied", str(ctx.exception))

    def test_no_workspace_renamed_event_on_any_failure_path(self):
        published = []
        self.event_bus.subscribe(WORKSPACE_RENAMED, lambda payload: published.append(payload))

        # 1. Target folder already exists.
        (self._new_root("Collision")).mkdir()
        with self.assertRaises(WorkspaceManagerError):
            self.manager.rename("Collision")

        # 2. Filesystem rename failure.
        with patch.object(
            WorkspaceStorage, "rename_folder", side_effect=WorkspaceStorageError("boom")
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.manager.rename("AnotherName")

        # 3. Save failure, rollback succeeds.
        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("boom")
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.manager.rename("YetAnotherName")

        # 4. Save failure, rollback also fails.
        real_rename_folder = WorkspaceStorage.rename_folder
        call_count = {"n": 0}

        def flaky_rename_folder(old_root, new_root):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return real_rename_folder(old_root, new_root)
            raise WorkspaceStorageError("rollback failed too")

        with patch.object(
            WorkspaceStorage, "rename_folder", side_effect=flaky_rename_folder
        ), patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("boom")
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.manager.rename("FinalName")

        self.assertEqual(published, [])

    def test_workspace_renamed_published_exactly_once_on_success(self):
        received = []
        self.event_bus.subscribe(WORKSPACE_RENAMED, lambda payload: received.append(payload))

        result = self.manager.rename("NewName")

        self.assertTrue(result)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["name"], "NewName")

    # --- Two consecutive renames in the same session (Mission 027 smoke
    # test regression: A -> B succeeded, B -> C failed with WinError 5
    # in real Windows usage — see MISSION_027.md section 16 for the full
    # diagnostic; these tests pass in this environment, which does NOT
    # mean the reported bug is resolved, only that it was not reproduced
    # through this application's own code paths in isolation) ---

    def test_two_consecutive_renames_in_the_same_session(self):
        outputs_dir = self.folder / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        image_path = outputs_dir / "generated.png"
        image_path.write_bytes(b"fake-png-bytes")
        self.manager.current_workspace.images.append(
            Image(image_id="img1", file_path=str(image_path))
        )
        external_image = self.external_dir / "ref.png"
        external_image.write_bytes(b"data")
        self.manager.current_workspace.images.append(
            Image(image_id="img2", file_path=str(external_image))
        )
        self.manager.save()

        received = []
        self.event_bus.subscribe(WORKSPACE_RENAMED, lambda payload: received.append(payload))

        # A -> B
        result_ab = self.manager.rename("MiddleName")
        root_b = self.folder.parent / "MiddleName"

        self.assertTrue(result_ab)
        self.assertEqual(self.manager.current_workspace.root, root_b)
        self.assertEqual(self.manager.current_workspace.name, "MiddleName")
        self.assertFalse(self.folder.exists())
        self.assertTrue(root_b.exists())

        # B -> C (the second rename that failed with WinError 5 in the
        # architect's real Windows session)
        result_bc = self.manager.rename("FinalName")
        root_c = self.folder.parent / "FinalName"

        self.assertTrue(result_bc)
        self.assertEqual(self.manager.current_workspace.root, root_c)
        self.assertEqual(self.manager.current_workspace.name, "FinalName")
        self.assertFalse(root_b.exists())
        self.assertTrue(root_c.exists())

        # Internal path remapped twice (A -> B -> C), external unchanged.
        workspace = self.manager.current_workspace
        internal_image = next(i for i in workspace.images if i.image_id == "img1")
        external_image_restored = next(i for i in workspace.images if i.image_id == "img2")
        self.assertEqual(
            internal_image.file_path, str(root_c / "outputs" / "generated.png")
        )
        self.assertEqual(external_image_restored.file_path, str(external_image))

        # project.json on disk reflects the final state.
        with open(root_c / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertEqual(on_disk["name"], "FinalName")

        # WORKSPACE_RENAMED published exactly once per successful rename.
        self.assertEqual(len(received), 2)

    def test_rename_still_works_after_a_close_and_reopen_cycle(self):
        # Mirrors the architect's real sequence: rename, close the
        # project, reopen it, then rename again — closing/reopening
        # must never be a prerequisite for a second rename to work, and
        # must never itself break a subsequent rename.
        first = self.manager.rename("SecondName")
        root_2 = self.folder.parent / "SecondName"
        self.assertTrue(first)

        self.manager.close()
        self.assertIsNone(self.manager.current_workspace)

        reopened_manager = WorkspaceManager(event_bus=EventBus())
        workspace = reopened_manager.open(root_2)
        self.assertIsNotNone(workspace)
        self.assertEqual(workspace.name, "SecondName")

        second = reopened_manager.rename("ThirdName")
        root_3 = self.folder.parent / "ThirdName"

        self.assertTrue(second)
        self.assertEqual(reopened_manager.current_workspace.root, root_3)
        self.assertEqual(reopened_manager.current_workspace.name, "ThirdName")
        self.assertFalse(root_2.exists())
        self.assertTrue(root_3.exists())


class WorkspaceStorageAtomicSaveTest(unittest.TestCase):
    """
    Mission 027: WorkspaceStorage.save()'s atomic-write hardening
    (temp file + os.replace()) — the dependency the rollback strategy in
    WorkspaceRenameTest relies on. Verifies the pre-existing project.json
    survives a real mid-write failure untouched, with no stray temp file
    left behind, and that a successful save still behaves exactly as
    before.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "AtomicSaveProject"
        self.folder.mkdir()
        WorkspaceStorage.save(self.folder, {"name": "Original", "version": "0.4"})

    def test_failure_before_replace_leaves_existing_project_json_intact(self):
        original_bytes = (self.folder / "project.json").read_bytes()

        with patch(
            "src.infrastructure.storage.workspace_storage.json.dump",
            side_effect=OSError("disk full"),
        ):
            with self.assertRaises(WorkspaceStorageError):
                WorkspaceStorage.save(self.folder, {"name": "New", "version": "0.4"})

        self.assertEqual((self.folder / "project.json").read_bytes(), original_bytes)

    def test_failure_before_replace_does_not_leave_a_stray_temp_file(self):
        with patch(
            "src.infrastructure.storage.workspace_storage.json.dump",
            side_effect=OSError("disk full"),
        ):
            with self.assertRaises(WorkspaceStorageError):
                WorkspaceStorage.save(self.folder, {"name": "New", "version": "0.4"})

        leftover = [p for p in self.folder.iterdir() if p.name != "project.json"]
        self.assertEqual(leftover, [])

    def test_successful_save_still_produces_correct_content(self):
        WorkspaceStorage.save(self.folder, {"name": "Renamed", "version": "0.4"})

        with open(self.folder / "project.json", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["name"], "Renamed")


class WorkspaceStorageRenameFolderErrorTest(unittest.TestCase):
    """
    Mission 027 real smoke test follow-up: WorkspaceStorage.rename_folder()
    must raise the distinct WorkspaceRenamePermissionError only for a real
    PermissionError (WinError 5 on Windows) — any other OSError keeps
    raising the plain WorkspaceStorageError, unchanged.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.old_root = Path(self.tmp_dir) / "Source"
        self.old_root.mkdir()
        self.new_root = Path(self.tmp_dir) / "Target"

    def test_permission_error_raises_the_specific_subclass(self):
        with patch.object(Path, "rename", side_effect=PermissionError("Access is denied")):
            with self.assertRaises(StorageRenamePermissionError):
                WorkspaceStorage.rename_folder(self.old_root, self.new_root)

    def test_other_os_error_raises_the_plain_base_class_only(self):
        with patch.object(Path, "rename", side_effect=OSError("some other failure")):
            with self.assertRaises(WorkspaceStorageError) as ctx:
                WorkspaceStorage.rename_folder(self.old_root, self.new_root)

        self.assertNotIsInstance(ctx.exception, StorageRenamePermissionError)

    def test_successful_rename_is_unaffected(self):
        WorkspaceStorage.rename_folder(self.old_root, self.new_root)

        self.assertFalse(self.old_root.exists())
        self.assertTrue(self.new_root.exists())


class WorkspaceStorageCopyIntoWorkspaceTest(unittest.TestCase):
    """
    Mission 028: WorkspaceStorage.is_inside()/copy_into_workspace() —
    the collision-safe copy primitive add_images() is built on, and
    the "already interior" short-circuit that keeps a source already
    under Workspace.root (e.g. an Inference Accept output, or a file
    re-selected directly from images/) from ever being copied onto
    itself. See MISSION_028.md sections 4/6.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.root = Path(self.tmp_dir) / "Workspace"
        self.root.mkdir()
        self.destination = self.root / "images"
        self.external_dir = Path(self.tmp_dir) / "External"
        self.external_dir.mkdir()

    # --- is_inside() ---

    def test_is_inside_true_for_direct_child(self):
        self.assertTrue(WorkspaceStorage.is_inside(self.root / "images" / "a.png", self.root))

    def test_is_inside_true_for_deeply_nested_path(self):
        self.assertTrue(
            WorkspaceStorage.is_inside(
                self.root / "datasets" / "d1" / "a.png", self.root
            )
        )

    def test_is_inside_true_for_root_itself(self):
        self.assertTrue(WorkspaceStorage.is_inside(self.root, self.root))

    def test_is_inside_false_for_a_sibling_folder(self):
        self.assertFalse(WorkspaceStorage.is_inside(self.external_dir / "a.png", self.root))

    def test_is_inside_case_insensitive_on_windows(self):
        upper_root = Path(str(self.root).upper())
        self.assertTrue(WorkspaceStorage.is_inside(self.root / "images" / "a.png", upper_root))

    def test_is_inside_works_for_a_path_that_no_longer_exists(self):
        missing = self.root / "images" / "deleted.png"
        self.assertTrue(WorkspaceStorage.is_inside(missing, self.root))

    # --- copy_into_workspace(): external source ---

    def test_external_source_is_copied_and_source_kept_intact(self):
        source = self.external_dir / "photo.png"
        source.write_bytes(b"fake-bytes")

        result = WorkspaceStorage.copy_into_workspace(source, self.destination, self.root)

        self.assertEqual(result, self.destination / "photo.png")
        self.assertEqual(result.read_bytes(), b"fake-bytes")
        self.assertTrue(source.exists())
        self.assertEqual(source.read_bytes(), b"fake-bytes")

    def test_destination_folder_created_defensively(self):
        source = self.external_dir / "photo.png"
        source.write_bytes(b"fake-bytes")
        nested_destination = self.root / "datasets" / "brand-new-dataset-id"
        self.assertFalse(nested_destination.exists())

        WorkspaceStorage.copy_into_workspace(source, nested_destination, self.root)

        self.assertTrue(nested_destination.exists())

    def test_collision_resolved_with_numeric_suffix_never_overwriting(self):
        (self.destination).mkdir(parents=True)
        (self.destination / "photo.png").write_bytes(b"original-content")

        source = self.external_dir / "photo.png"
        source.write_bytes(b"new-content")

        result = WorkspaceStorage.copy_into_workspace(source, self.destination, self.root)

        self.assertEqual(result, self.destination / "photo_1.png")
        self.assertEqual((self.destination / "photo.png").read_bytes(), b"original-content")
        self.assertEqual(result.read_bytes(), b"new-content")

    def test_second_collision_uses_next_numeric_suffix(self):
        self.destination.mkdir(parents=True)
        (self.destination / "photo.png").write_bytes(b"a")
        (self.destination / "photo_1.png").write_bytes(b"b")

        source = self.external_dir / "photo.png"
        source.write_bytes(b"c")

        result = WorkspaceStorage.copy_into_workspace(source, self.destination, self.root)

        self.assertEqual(result, self.destination / "photo_2.png")

    def test_missing_source_raises_workspace_storage_error(self):
        missing_source = self.external_dir / "does_not_exist.png"

        with self.assertRaises(WorkspaceStorageError):
            WorkspaceStorage.copy_into_workspace(missing_source, self.destination, self.root)

    def test_copy_failure_cleans_up_partial_destination_file(self):
        source = self.external_dir / "photo.png"
        source.write_bytes(b"fake-bytes")

        with patch(
            "src.infrastructure.storage.workspace_storage.shutil.copy2",
            side_effect=OSError("disk full"),
        ):
            with self.assertRaises(WorkspaceStorageError):
                WorkspaceStorage.copy_into_workspace(source, self.destination, self.root)

        self.assertEqual(list(self.destination.iterdir()), [])

    # --- copy_into_workspace(): already-internal source ---

    def test_source_already_at_destination_is_reused_without_copy(self):
        self.destination.mkdir(parents=True)
        already_there = self.destination / "photo.png"
        already_there.write_bytes(b"already-here")

        with patch(
            "src.infrastructure.storage.workspace_storage.shutil.copy2"
        ) as copy2_mock:
            result = WorkspaceStorage.copy_into_workspace(
                already_there, self.destination, self.root
            )

        copy2_mock.assert_not_called()
        self.assertEqual(result, already_there.resolve())

    def test_source_internal_but_in_a_different_subfolder_is_still_reused_without_copy(self):
        # e.g. a generated image already under <root>/outputs/, being
        # "imported" into images/ — Mission 028 section 6.1's broad
        # "anywhere under root" rule, not just an exact-folder match.
        outputs_dir = self.root / "outputs"
        outputs_dir.mkdir(parents=True)
        generated = outputs_dir / "generated.png"
        generated.write_bytes(b"generated-bytes")

        with patch(
            "src.infrastructure.storage.workspace_storage.shutil.copy2"
        ) as copy2_mock:
            result = WorkspaceStorage.copy_into_workspace(
                generated, self.destination, self.root
            )

        copy2_mock.assert_not_called()
        self.assertEqual(result, generated.resolve())
        # Never moved/duplicated into images/ either.
        self.assertFalse((self.destination / "generated.png").exists())


class WorkspaceManagerAddImagesCopyTest(unittest.TestCase):
    """
    Mission 028: WorkspaceManager.add_images() — real physical copy
    into <workspace_root>/images/, best-effort partial-failure
    handling, the added/failed/skipped ImportResult contract, and the
    "already interior" reuse path. See MISSION_028.md sections 9/10.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"
        self.external_dir = Path(self.tmp_dir) / "External"
        self.external_dir.mkdir()

        self.event_bus = EventBus()
        self.manager = WorkspaceManager(event_bus=self.event_bus)
        self.manager.create(self.folder)

    def _external(self, name, content=b"fake-bytes"):
        path = self.external_dir / name
        path.write_bytes(content)
        return str(path)

    def test_no_current_workspace_returns_empty_result(self):
        manager = WorkspaceManager()
        result = manager.add_images([self._external("a.png")])
        self.assertEqual(result, (0, [], []))

    def test_import_result_reports_added_count_and_persisted_path(self):
        result = self.manager.add_images([self._external("photo.png")])

        self.assertEqual(result.added, 1)
        self.assertEqual(result.failed, [])
        self.assertEqual(result.skipped, [])
        self.assertEqual(
            self.manager.current_workspace.images[0].file_path,
            str(self.folder / "images" / "photo.png"),
        )

    def test_source_stays_intact_after_import(self):
        source = self._external("photo.png")
        self.manager.add_images([source])

        self.assertTrue(Path(source).exists())
        self.assertEqual(Path(source).read_bytes(), b"fake-bytes")

    def test_two_different_sources_same_name_never_overwrite_each_other(self):
        first = self.external_dir / "photo.png"
        first.write_bytes(b"first-content")

        second_dir = Path(self.tmp_dir) / "External2"
        second_dir.mkdir()
        second = second_dir / "photo.png"
        second.write_bytes(b"second-content")

        result = self.manager.add_images([str(first), str(second)])

        self.assertEqual(result.added, 2)
        images = self.manager.current_workspace.images
        self.assertEqual(
            {img.file_path for img in images},
            {
                str(self.folder / "images" / "photo.png"),
                str(self.folder / "images" / "photo_1.png"),
            },
        )
        contents = {Path(img.file_path).read_bytes() for img in images}
        self.assertEqual(contents, {b"first-content", b"second-content"})

    def test_duplicate_source_within_the_same_batch_is_skipped_not_failed(self):
        source = self._external("photo.png")

        result = self.manager.add_images([source, source])

        self.assertEqual(result.added, 1)
        self.assertEqual(result.failed, [])
        self.assertEqual(result.skipped, [source])
        self.assertEqual(len(self.manager.current_workspace.images), 1)

    def test_partial_failure_does_not_block_the_rest_of_the_batch(self):
        good = self._external("good.png")
        missing = str(self.external_dir / "missing.png")

        result = self.manager.add_images([good, missing])

        self.assertEqual(result.added, 1)
        self.assertEqual(result.failed, [missing])
        self.assertEqual(
            self.manager.current_workspace.images[0].file_path,
            str(self.folder / "images" / "good.png"),
        )

    def test_no_image_persisted_for_a_failed_copy(self):
        missing = str(self.external_dir / "missing.png")

        self.manager.add_images([missing])

        self.assertEqual(self.manager.current_workspace.images, [])
        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertEqual(on_disk["images"], [])

    def test_copy_failure_is_wrapped_and_reported_as_failed_not_raised(self):
        source = self._external("photo.png")

        with patch(
            "src.infrastructure.storage.workspace_storage.shutil.copy2",
            side_effect=OSError("disk full"),
        ):
            result = self.manager.add_images([source])

        self.assertEqual(result.added, 0)
        self.assertEqual(result.failed, [source])

    def test_already_internal_source_is_reused_without_a_new_copy(self):
        source = self._external("photo.png")
        self.manager.add_images([source])
        internal_path = self.manager.current_workspace.images[0].file_path

        with patch(
            "src.infrastructure.storage.workspace_storage.shutil.copy2"
        ) as copy2_mock:
            result = self.manager.add_images([internal_path])

        copy2_mock.assert_not_called()
        self.assertEqual(result.added, 0)
        self.assertEqual(result.skipped, [internal_path])
        self.assertEqual(len(self.manager.current_workspace.images), 1)

    # --- Mission 067: rollback + compensation on a save() failure ---

    def test_save_failure_rolls_back_domain_and_deletes_the_new_copy(self):
        source = self._external("photo.png")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.manager.add_images([source])

        self.assertEqual(self.manager.current_workspace.images, [])
        self.assertFalse((self.folder / "images" / "photo.png").exists())
        self.assertTrue(Path(source).exists())
        self.assertEqual(Path(source).read_bytes(), b"fake-bytes")
        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertEqual(on_disk["images"], [])

    def test_save_failure_with_a_passthrough_source_never_deletes_it(self):
        # Mirrors InferencePage's Accept flow: a file already located
        # under workspace_root (e.g. outputs/) but not yet registered
        # in Workspace.images — copy_into_workspace() recognizes it and
        # returns it unchanged, so this call never creates a new copy
        # at all; only the Domain entry may ever be rolled back.
        outputs_dir = self.folder / "outputs"
        outputs_dir.mkdir(exist_ok=True)
        pending = outputs_dir / "generated.png"
        pending.write_bytes(b"generated-bytes")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.manager.add_images([str(pending)])

        self.assertEqual(self.manager.current_workspace.images, [])
        self.assertTrue(pending.exists())
        self.assertEqual(pending.read_bytes(), b"generated-bytes")

    def test_retry_after_save_failure_is_a_genuine_new_attempt(self):
        source = self._external("photo.png")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.manager.add_images([source])

        # The failed copy was cleaned up by the rollback above, so this
        # retry finds no leftover file at the natural name — never a
        # "_1" suffix caused by an orphan from the first attempt.
        result = self.manager.add_images([source])

        self.assertEqual(result.added, 1)
        self.assertEqual(
            self.manager.current_workspace.images[0].file_path,
            str(self.folder / "images" / "photo.png"),
        )
        self.assertFalse((self.folder / "images" / "photo_1.png").exists())

    def test_cleanup_failure_preserves_the_original_persistence_error(self):
        source = self._external("photo.png")

        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ), patch.object(Path, "unlink", side_effect=PermissionError("locked")):
            with self.assertRaises(WorkspaceManagerError) as ctx:
                self.manager.add_images([source])

        message = str(ctx.exception)
        self.assertIn("disk full", message)
        self.assertIn("orphaned", message)
        # The Domain rollback still happens even though the physical
        # cleanup itself failed — the two are independent guarantees.
        self.assertEqual(self.manager.current_workspace.images, [])
        self.assertTrue(Path(source).exists())

    def test_multi_file_save_failure_never_touches_preexisting_images(self):
        existing_source = self._external("existing.png", b"existing-bytes")
        self.manager.add_images([existing_source])
        preexisting_images = list(self.manager.current_workspace.images)

        new_source_1 = self._external("new1.png")
        new_source_2 = self._external("new2.png")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.manager.add_images([new_source_1, new_source_2])

        self.assertEqual(self.manager.current_workspace.images, preexisting_images)
        self.assertIs(self.manager.current_workspace.images[0], preexisting_images[0])
        self.assertFalse((self.folder / "images" / "new1.png").exists())
        self.assertFalse((self.folder / "images" / "new2.png").exists())
        self.assertTrue((self.folder / "images" / "existing.png").exists())

    def test_reopening_after_close_preserves_the_copied_image(self):
        source = self._external("photo.png")
        self.manager.add_images([source])
        expected_path = str(self.folder / "images" / "photo.png")

        self.manager.close()

        reopened = WorkspaceManager(event_bus=EventBus())
        reopened.open(self.folder)

        self.assertEqual(reopened.current_workspace.images[0].file_path, expected_path)
        self.assertTrue(Path(expected_path).exists())

    def test_legacy_project_json_with_external_reference_still_loads_unchanged(self):
        # Mission 028 introduces no retroactive migration — a
        # pre-existing external Image.file_path is read back exactly
        # as stored, no copy attempted at load time.
        legacy_external_path = str(self.external_dir / "legacy.png")
        Path(legacy_external_path).write_bytes(b"legacy-bytes")

        data = self.manager.current_workspace.to_dict()
        data["images"] = [{"image_id": "legacy-1", "file_path": legacy_external_path}]
        WorkspaceStorage.save(self.folder, data)

        reopened = WorkspaceManager(event_bus=EventBus())
        workspace = reopened.open(self.folder)

        self.assertEqual(workspace.images[0].file_path, legacy_external_path)

    # --- Mission 028 second smoke test: preview_collisions()/renames ---

    def test_preview_collisions_empty_when_nothing_collides(self):
        self.assertEqual(self.manager.preview_collisions([self._external("photo.png")]), [])

    def test_preview_collisions_reports_suggested_name_for_a_real_collision(self):
        # Distinct case 1 (architect's smoke test report): the exact
        # same external source re-imported a second time — Mission 028
        # deliberately never dedups this by content, so it is reported
        # as a genuine name collision, not silently skipped.
        source = self._external("photo.png")
        self.manager.add_images([source])

        collisions = self.manager.preview_collisions([source])

        self.assertEqual(len(collisions), 1)
        self.assertEqual(collisions[0].source, source)
        self.assertEqual(collisions[0].suggested_name, "photo_1.png")

    def test_preview_collisions_reports_two_different_files_sharing_a_name(self):
        # Distinct case 2: two genuinely different external files that
        # merely happen to share a filename.
        first = self._external("shared.png", b"first")
        second_dir = Path(self.tmp_dir) / "External2"
        second_dir.mkdir()
        second = second_dir / "shared.png"
        second.write_bytes(b"second")

        self.manager.add_images([first])
        collisions = self.manager.preview_collisions([str(second)])

        self.assertEqual(len(collisions), 1)
        self.assertEqual(collisions[0].source, str(second))
        self.assertEqual(collisions[0].suggested_name, "shared_1.png")

    def test_preview_collisions_empty_for_a_source_already_exactly_in_images(self):
        # Distinct case 3: a source already sitting exactly inside
        # Workspace/images/ is never a naming collision (it is not
        # given a new name at all — see is_inside()/section 6) —
        # confirms it never reaches the collision dialog either.
        source = self._external("photo.png")
        self.manager.add_images([source])
        internal_path = self.manager.current_workspace.images[0].file_path

        self.assertEqual(self.manager.preview_collisions([internal_path]), [])

    def test_preview_collisions_within_a_single_batch_accounts_for_earlier_entries(self):
        # Two brand-new external files sharing a name, submitted in the
        # very same call — neither is on disk yet at preview time, so
        # the second must still be predicted as colliding with the
        # first's own (not-yet-written) claim.
        first = self._external("new.png", b"a")
        second_dir = Path(self.tmp_dir) / "External2"
        second_dir.mkdir()
        second = second_dir / "new.png"
        second.write_bytes(b"b")

        collisions = self.manager.preview_collisions([first, str(second)])

        self.assertEqual(len(collisions), 1)
        self.assertEqual(collisions[0].source, str(second))
        self.assertEqual(collisions[0].suggested_name, "new_1.png")

    def test_preview_collisions_ignores_a_duplicate_source_within_the_batch(self):
        source = self._external("photo.png")
        self.assertEqual(self.manager.preview_collisions([source, source]), [])

    def test_add_images_uses_the_requested_rename_instead_of_auto_suffix(self):
        existing = self._external("photo.png")
        self.manager.add_images([existing])

        new_source = self._external("also_photo.png", b"different")
        result = self.manager.add_images(
            [new_source], renames={new_source: "custom_name.png"}
        )

        self.assertEqual(result.added, 1)
        expected = self.folder / "images" / "custom_name.png"
        self.assertTrue(expected.exists())
        self.assertFalse((self.folder / "images" / "photo_1.png").exists())
        self.assertEqual(
            self.manager.current_workspace.images[-1].file_path, str(expected)
        )

    def test_add_images_requested_name_already_taken_is_reported_as_failed(self):
        self.manager.add_images([self._external("taken.png")])

        new_source = self._external("other.png")
        result = self.manager.add_images(
            [new_source], renames={new_source: "taken.png"}
        )

        self.assertEqual(result.added, 0)
        self.assertEqual(result.failed, [new_source])

    def test_add_images_without_renames_still_falls_back_to_silent_auto_suffix(self):
        # The underlying primitive's default behavior is deliberately
        # preserved (architect's explicit instruction: "ne supprime pas
        # la primitive collision-safe côté Infrastructure") — only the
        # UI-driven import flow now asks first via preview_collisions().
        self.manager.add_images([self._external("photo.png")])
        result = self.manager.add_images([self._external("photo.png", b"other")])

        self.assertEqual(result.added, 1)
        self.assertTrue((self.folder / "images" / "photo_1.png").exists())


class WorkspaceManagerRemoveImagesTest(unittest.TestCase):
    """
    Mission 046: WorkspaceManager.images_referenced_by_datasets()/
    preview_image_removal()/remove_images() — real physical deletion
    only for a file both inside workspace_root and still present on
    disk, atomic blocking if any requested path is still referenced by
    a Dataset (any Character — cardinality is technically unconstrained,
    Missions 026/036), and the safety guarantee that a path external to
    the Workspace (or missing) is never unlinked. A path's mere
    presence in Workspace.images is never treated as a guarantee of
    physical ownership — see WorkspaceManagerAddImagesCopyTest's own
    external-path tests above for the pre-existing precedent this
    mission builds on.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"
        self.external_dir = Path(self.tmp_dir) / "External"
        self.external_dir.mkdir()

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.workspace_manager.create(self.folder)

    def _internal_image(self, name="photo.png"):
        source = self.external_dir / name
        source.write_bytes(b"fake-bytes")
        self.workspace_manager.add_images([str(source)])
        return self.workspace_manager.current_workspace.images[-1].file_path

    def _external_image(self, name="outside.png"):
        path = str(self.external_dir / name)
        Path(path).write_bytes(b"external-bytes")
        self.workspace_manager.current_workspace.images.append(
            Image(image_id=f"ext-{name}", file_path=path)
        )
        return path

    # --- preview_image_removal() ---

    def test_preview_classifies_internal_present_file_as_deletable(self):
        internal_path = self._internal_image()

        preview = self.workspace_manager.preview_image_removal([internal_path])

        self.assertEqual(preview.deletable, [internal_path])
        self.assertEqual(preview.reference_only, [])

    def test_preview_classifies_external_file_as_reference_only(self):
        external_path = self._external_image()

        preview = self.workspace_manager.preview_image_removal([external_path])

        self.assertEqual(preview.deletable, [])
        self.assertEqual(preview.reference_only, [external_path])

    def test_preview_classifies_missing_internal_path_as_reference_only(self):
        internal_path = self._internal_image()
        Path(internal_path).unlink()

        preview = self.workspace_manager.preview_image_removal([internal_path])

        self.assertEqual(preview.deletable, [])
        self.assertEqual(preview.reference_only, [internal_path])

    # --- images_referenced_by_datasets() ---

    def test_referenced_by_datasets_empty_when_no_dataset_uses_the_path(self):
        internal_path = self._internal_image()

        self.assertEqual(self.workspace_manager.images_referenced_by_datasets([internal_path]), {})

    def test_referenced_by_datasets_detects_a_single_dataset(self):
        internal_path = self._internal_image()
        dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(dataset.dataset_id)
        self.dataset_manager.add_images([internal_path])

        referenced = self.workspace_manager.images_referenced_by_datasets([internal_path])

        self.assertEqual(referenced, {"Portraits": [internal_path]})

    def test_referenced_by_datasets_detects_multiple_datasets_sharing_the_same_file(self):
        internal_path = self._internal_image()
        dataset_a = self.dataset_manager.create("A")
        self.dataset_manager.select(dataset_a.dataset_id)
        self.dataset_manager.add_images([internal_path])
        dataset_b = self.dataset_manager.create("B")
        self.dataset_manager.select(dataset_b.dataset_id)
        self.dataset_manager.add_images([internal_path])

        referenced = self.workspace_manager.images_referenced_by_datasets([internal_path])

        self.assertEqual(set(referenced.keys()), {"A", "B"})

    def test_referenced_by_datasets_detects_reference_from_a_non_principal_character(self):
        # Cardinality is technically unconstrained (Missions 026/036) —
        # a Dataset belonging to a second, non-principal Character must
        # still be detected, not only principal_character's own.
        internal_path = self._internal_image()
        second_character = self.character_manager.create("Second")
        self.character_manager.select(second_character.character_id)
        dataset = self.dataset_manager.create("Other")
        self.dataset_manager.select(dataset.dataset_id)
        self.dataset_manager.add_images([internal_path])

        referenced = self.workspace_manager.images_referenced_by_datasets([internal_path])

        self.assertEqual(referenced, {"Other": [internal_path]})

    # --- remove_images(): real deletion / reference-only / atomic blocking ---

    def test_remove_images_deletes_internal_present_file_and_removes_reference(self):
        internal_path = self._internal_image()

        result = self.workspace_manager.remove_images([internal_path])

        self.assertEqual(result.deleted, [internal_path])
        self.assertEqual(result.reference_only, [])
        self.assertEqual(result.blocked_by, {})
        self.assertEqual(result.deletion_failed, [])
        self.assertFalse(Path(internal_path).exists())
        self.assertEqual(self.workspace_manager.current_workspace.images, [])

    def test_remove_images_never_deletes_an_external_file(self):
        external_path = self._external_image()

        result = self.workspace_manager.remove_images([external_path])

        self.assertEqual(result.deleted, [])
        self.assertEqual(result.reference_only, [external_path])
        self.assertTrue(Path(external_path).exists())
        self.assertEqual(self.workspace_manager.current_workspace.images, [])

    def test_remove_images_removes_reference_for_an_already_missing_internal_file_without_error(self):
        internal_path = self._internal_image()
        Path(internal_path).unlink()

        result = self.workspace_manager.remove_images([internal_path])

        self.assertEqual(result.deleted, [])
        self.assertEqual(result.reference_only, [internal_path])
        # Mission 066: an already-missing file was never a deletion
        # candidate in the first place (classified reference_only
        # before any unlink() is even considered) — never reported as
        # a deletion_failed, which is reserved for a real unlink()
        # attempt that failed.
        self.assertEqual(result.deletion_failed, [])
        self.assertEqual(self.workspace_manager.current_workspace.images, [])

    def test_remove_images_handles_a_mixed_selection_in_one_call(self):
        internal_path = self._internal_image("a.png")
        external_path = self._external_image()

        result = self.workspace_manager.remove_images([internal_path, external_path])

        self.assertEqual(result.deleted, [internal_path])
        self.assertEqual(result.reference_only, [external_path])
        self.assertFalse(Path(internal_path).exists())
        self.assertTrue(Path(external_path).exists())

    def test_remove_images_blocks_atomically_if_any_selected_image_is_referenced(self):
        internal_path = self._internal_image("a.png")
        other_path = self._internal_image("b.png")
        dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(dataset.dataset_id)
        self.dataset_manager.add_images([internal_path])

        result = self.workspace_manager.remove_images([internal_path, other_path])

        self.assertEqual(result.blocked_by, {"Portraits": [internal_path]})
        self.assertEqual(result.deleted, [])
        self.assertEqual(result.reference_only, [])
        self.assertTrue(Path(internal_path).exists())
        self.assertTrue(Path(other_path).exists())
        self.assertEqual(len(self.workspace_manager.current_workspace.images), 2)

    def test_remove_images_saves_only_when_a_mutation_actually_happens(self):
        internal_path = self._internal_image()

        with patch.object(
            self.workspace_manager, "save", wraps=self.workspace_manager.save
        ) as save_spy:
            never_added = str(self.external_dir / "never_added.png")
            result = self.workspace_manager.remove_images([never_added])
            self.assertEqual(result.deleted, [])
            self.assertEqual(result.reference_only, [])
            save_spy.assert_not_called()

            self.workspace_manager.remove_images([internal_path])
            save_spy.assert_called_once()

    def test_remove_images_persists_after_reopen(self):
        internal_path = self._internal_image()
        self.workspace_manager.remove_images([internal_path])

        reopened = WorkspaceManager(event_bus=EventBus())
        reopened.open(self.folder)

        self.assertEqual(reopened.current_workspace.images, [])

    # --- Mission 066: persistence-first order — no file destroyed on a
    # save() failure, batch resilience to an individual unlink() failure
    # after a successful save() ---

    def test_remove_images_when_save_fails_deletes_no_file_and_restores_domain(self):
        internal_path = self._internal_image()
        original_images = list(self.workspace_manager.current_workspace.images)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.workspace_manager.remove_images([internal_path])

        # The file the mini-audit demonstrated could be permanently
        # destroyed by the previous unlink-then-save order is untouched.
        self.assertTrue(Path(internal_path).exists())

        # Domain restored to exactly what it was before the call — same
        # objects, same order — never left dirty/silently persistable by
        # some later, unrelated successful save().
        self.assertEqual(self.workspace_manager.current_workspace.images, original_images)

        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertEqual([img["file_path"] for img in on_disk["images"]], [internal_path])

    def test_remove_images_batch_survives_one_unlink_failure_and_reports_it(self):
        path_a = self._internal_image("a.png")
        path_b = self._internal_image("b.png")
        path_c = self._internal_image("c.png")

        real_unlink = Path.unlink

        def flaky_unlink(self_path, *args, **kwargs):
            if self_path == Path(path_b):
                raise PermissionError("simulated: locked by another process")
            return real_unlink(self_path, *args, **kwargs)

        with patch.object(Path, "unlink", flaky_unlink):
            result = self.workspace_manager.remove_images([path_a, path_b, path_c])

        self.assertEqual(sorted(result.deleted), sorted([path_a, path_c]))
        self.assertEqual(result.deletion_failed, [path_b])
        self.assertEqual(result.reference_only, [])
        self.assertEqual(result.blocked_by, {})

        # A's and C's failure to unlink one another never happened —
        # each file's outcome is independent.
        self.assertFalse(Path(path_a).exists())
        self.assertTrue(Path(path_b).exists())
        self.assertFalse(Path(path_c).exists())

        # Persistence already succeeded before any unlink() was
        # attempted — the logical removal is unconditional and durable
        # regardless of B's physical deletion failure.
        self.assertEqual(self.workspace_manager.current_workspace.images, [])
        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertEqual(on_disk["images"], [])

    def test_remove_images_collects_every_unlink_failure_not_only_the_first(self):
        path_a = self._internal_image("a.png")
        path_b = self._internal_image("b.png")
        path_c = self._internal_image("c.png")
        path_d = self._internal_image("d.png")

        failing = {Path(path_b), Path(path_d)}
        real_unlink = Path.unlink

        def flaky_unlink(self_path, *args, **kwargs):
            if self_path in failing:
                raise PermissionError("simulated: locked by another process")
            return real_unlink(self_path, *args, **kwargs)

        with patch.object(Path, "unlink", flaky_unlink):
            result = self.workspace_manager.remove_images([path_a, path_b, path_c, path_d])

        self.assertEqual(sorted(result.deleted), sorted([path_a, path_c]))
        self.assertEqual(sorted(result.deletion_failed), sorted([path_b, path_d]))
        self.assertEqual(self.workspace_manager.current_workspace.images, [])


class WorkspaceVestigialFieldsRemovalTest(unittest.TestCase):
    """
    Mission 057: Workspace.datasets/.loras/.training (never consumed by
    any Manager — DatasetManager/LoRAManager/TrainingManager read
    exclusively from Character.datasets/.loras/.trainings) and
    Character.history (never populated nor read anywhere) are removed.
    Compatibility contract verified here: a project.json written before
    this removal still loads without error, the now-unread legacy keys
    are simply absent once the workspace is saved again (cleanup of a
    dead schema, not a migration of functional data), and every
    still-real collection (Workspace.models/.workflows,
    Character.datasets/.loras/.trainings/.prompts) survives the cycle
    untouched.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "LegacyProject"

    def _write_legacy_project_json(self):
        # Hand-built payload mirroring exactly what a pre-Mission-057
        # project.json looked like: Workspace.datasets/.loras/.training
        # populated with placeholder junk (proving they are ignored
        # regardless of content, not merely when empty) and a Character
        # carrying a "history" key alongside its real, still-consumed
        # collections.
        self.folder.mkdir(parents=True)
        legacy_payload = {
            "name": "LegacyProject",
            "version": "0.4",
            "images": [],
            "datasets": ["stale-legacy-junk"],
            "models": [{"model_id": "m1", "name": "M", "file_path": ""}],
            "workflows": [{"workflow_id": "w1", "name": "W", "file_path": ""}],
            "loras": ["stale-legacy-junk"],
            "training": {"stale": "legacy-junk"},
            "settings": {},
            "characters": [
                {
                    "character_id": "c1",
                    "name": "Aria",
                    "datasets": [
                        {"dataset_id": "d1", "name": "Portraits", "images": []}
                    ],
                    "loras": [
                        {"lora_id": "l1", "name": "L1", "files": [], "thumbnail": ""}
                    ],
                    "prompts": [
                        {"prompt_id": "p1", "name": "P1", "text": "hello"}
                    ],
                    "trainings": [
                        {"training_id": "t1", "name": "T1", "dataset_id": "d1"}
                    ],
                    "history": ["some", "legacy", "entries"],
                }
            ],
        }
        WorkspaceStorage.save(self.folder, legacy_payload)
        return legacy_payload

    def test_legacy_workspace_json_with_removed_keys_still_loads(self):
        self._write_legacy_project_json()

        manager = WorkspaceManager(event_bus=EventBus())
        workspace = manager.open(self.folder)

        self.assertIsNotNone(workspace)
        self.assertEqual(workspace.name, "LegacyProject")

    def test_legacy_character_json_with_history_key_still_loads(self):
        self._write_legacy_project_json()

        manager = WorkspaceManager(event_bus=EventBus())
        workspace = manager.open(self.folder)

        self.assertEqual(len(workspace.characters), 1)
        self.assertEqual(workspace.characters[0].name, "Aria")

    def test_real_character_collections_survive_the_legacy_load(self):
        self._write_legacy_project_json()

        manager = WorkspaceManager(event_bus=EventBus())
        workspace = manager.open(self.folder)

        character = workspace.characters[0]
        self.assertEqual(len(character.datasets), 1)
        self.assertEqual(character.datasets[0].name, "Portraits")
        self.assertEqual(len(character.loras), 1)
        self.assertEqual(character.loras[0].name, "L1")
        self.assertEqual(len(character.prompts), 1)
        self.assertEqual(character.prompts[0].text, "hello")
        self.assertEqual(len(character.trainings), 1)
        self.assertEqual(character.trainings[0].name, "T1")

    def test_real_workspace_collections_survive_the_legacy_load(self):
        self._write_legacy_project_json()

        manager = WorkspaceManager(event_bus=EventBus())
        workspace = manager.open(self.folder)

        self.assertEqual(len(workspace.models), 1)
        self.assertEqual(workspace.models[0].name, "M")
        self.assertEqual(len(workspace.workflows), 1)
        self.assertEqual(workspace.workflows[0].name, "W")

    def test_resave_no_longer_emits_the_removed_keys(self):
        self._write_legacy_project_json()

        manager = WorkspaceManager(event_bus=EventBus())
        manager.open(self.folder)
        manager.save()

        on_disk = json.loads((self.folder / "project.json").read_text(encoding="utf-8"))

        self.assertNotIn("datasets", on_disk)
        self.assertNotIn("loras", on_disk)
        self.assertNotIn("training", on_disk)
        self.assertNotIn("history", on_disk["characters"][0])

    def test_resave_still_preserves_real_data(self):
        # The removed keys disappear, but nothing functional does — this
        # is a dead-schema cleanup, never an implicit migration of
        # real/active data.
        self._write_legacy_project_json()

        manager = WorkspaceManager(event_bus=EventBus())
        manager.open(self.folder)
        manager.save()

        on_disk = json.loads((self.folder / "project.json").read_text(encoding="utf-8"))

        self.assertEqual(len(on_disk["models"]), 1)
        self.assertEqual(len(on_disk["workflows"]), 1)
        character_on_disk = on_disk["characters"][0]
        self.assertEqual(len(character_on_disk["datasets"]), 1)
        self.assertEqual(len(character_on_disk["loras"]), 1)
        self.assertEqual(len(character_on_disk["prompts"]), 1)
        self.assertEqual(len(character_on_disk["trainings"]), 1)

    def test_workspace_to_dict_never_emits_the_removed_keys_for_a_fresh_workspace(self):
        # Not just a legacy-load edge case: a brand-new Workspace created
        # by this version of the application never writes the removed
        # keys in the first place. CharacterManager is wired so the
        # WORKSPACE_CREATED auto-created principal Character (Mission
        # 026) is present, to also cover its own to_dict() output.
        event_bus = EventBus()
        manager = WorkspaceManager(event_bus=event_bus)
        CharacterManager(manager, event_bus=event_bus)
        manager.create(self.folder)

        on_disk = json.loads((self.folder / "project.json").read_text(encoding="utf-8"))

        self.assertNotIn("datasets", on_disk)
        self.assertNotIn("loras", on_disk)
        self.assertNotIn("training", on_disk)
        self.assertEqual(len(on_disk["characters"]), 1)
        self.assertNotIn("history", on_disk["characters"][0])

    def test_create_close_reopen_cycle_has_no_regression(self):
        manager = WorkspaceManager(event_bus=EventBus())
        manager.create(self.folder)
        manager.close()

        self.assertIsNone(manager.current_workspace)

        reopened = WorkspaceManager(event_bus=EventBus())
        workspace = reopened.open(self.folder)

        self.assertIsNotNone(workspace)
        self.assertEqual(workspace.name, "LegacyProject")

    def test_base_page_file_and_all_references_are_gone(self):
        # Mission 057: BasePage was fully unused (zero inheritance across
        # every Page in the project) and is removed outright, not just
        # deprecated.
        base_page_path = Path("src/ui/pages/base_page.py")
        self.assertFalse(base_page_path.exists())

        pages_dir = Path("src/ui/pages")
        for python_file in pages_dir.glob("*.py"):
            source = python_file.read_text(encoding="utf-8")
            self.assertNotIn("BasePage", source, f"stray reference in {python_file}")
            self.assertNotIn("base_page", source, f"stray reference in {python_file}")


if __name__ == "__main__":
    unittest.main()
