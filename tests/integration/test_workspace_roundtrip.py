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

        # 2. Import images
        added = manager.add_images(["ref1.png", "ref2.png"])
        self.assertEqual(added, 2)
        self.assertEqual(
            [images.list_widget.item(i).text() for i in range(images.list_widget.count())],
            ["ref1.png", "ref2.png"],
        )
        self.assertEqual(dashboard.imagesCard.value.text(), "2")

        # 3. Save
        manager.save()

        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertEqual(
            [image["file_path"] for image in on_disk["images"]],
            ["ref1.png", "ref2.png"],
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
            ["ref1.png", "ref2.png"],
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


if __name__ == "__main__":
    unittest.main()
