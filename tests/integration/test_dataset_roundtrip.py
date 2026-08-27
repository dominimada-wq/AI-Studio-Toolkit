"""
Integration coverage for the Dataset lifecycle, exercising
DatasetManager, Character.datasets, Workspace persistence, EventBus
and the real DashboardPage/CharactersPage/ImagesPage/DatasetsPage
widgets together — the same wiring MainWindow uses.
"""

import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from src.core.event_bus import EventBus
from src.domain.image import Image
from src.infrastructure.storage.workspace_storage import WorkspaceStorage, WorkspaceStorageError
from src.managers.workspace_manager import (
    WorkspaceManager,
    WorkspaceManagerError,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_SAVED,
    WORKSPACE_CLOSED,
)
from src.managers.character_manager import (
    CharacterManager,
    CHARACTER_CREATED,
    CHARACTER_SELECTED,
    CHARACTER_DELETED,
)
from src.managers.dataset_manager import (
    DatasetManager,
    DATASET_CREATED,
    DATASET_SELECTED,
    DATASET_DELETED,
)
from src.managers.training_manager import (
    TrainingManager,
    TRAINING_CREATED,
    TRAINING_SELECTED,
    TRAINING_DELETED,
)
from src.ui.pages.dashboard_page import DashboardPage
from src.ui.pages.characters_page import CharactersPage
from src.ui.pages.images_page import ImagesPage
from src.ui.pages.datasets_page import DatasetsPage
from src.ui.pages.training_page import TrainingPage

WORKSPACE_EVENTS = (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_SAVED, WORKSPACE_CLOSED)
CHARACTER_EVENTS = (CHARACTER_CREATED, CHARACTER_SELECTED, CHARACTER_DELETED)
DATASET_EVENTS = (DATASET_CREATED, DATASET_SELECTED, DATASET_DELETED)
TRAINING_EVENTS = (TRAINING_CREATED, TRAINING_SELECTED, TRAINING_DELETED)

_app = QApplication.instance() or QApplication([])


class DatasetRoundTripTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "DatasetProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)

        dashboard = DashboardPage()
        characters_page = CharactersPage(character_manager, workspace_manager)
        images = ImagesPage(workspace_manager)
        datasets_page = DatasetsPage(dataset_manager, workspace_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, dashboard.update_project)
            event_bus.subscribe(event_name, images.update_images)
            event_bus.subscribe(event_name, characters_page.update_characters)
            event_bus.subscribe(event_name, datasets_page.update_datasets)

        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, characters_page.update_characters)
            event_bus.subscribe(event_name, datasets_page.update_datasets)

        for event_name in DATASET_EVENTS:
            event_bus.subscribe(event_name, datasets_page.update_datasets)

        return (
            event_bus, workspace_manager, character_manager, dataset_manager,
            dashboard, characters_page, images, datasets_page,
        )

    def test_full_create_select_import_save_close_reopen_cycle(self):

        (event_bus, workspace_manager, character_manager, dataset_manager,
         dashboard, characters_page, images, datasets_page) = self._wire()

        workspace_manager.create(self.folder)
        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)

        portraits = dataset_manager.create("Portraits")
        dataset_manager.select(portraits.dataset_id)

        # Mission 028: add_images() physically copies each external
        # source into <workspace_root>/datasets/<dataset_id>/.
        ref1 = Path(self.tmp_dir) / "ref1.png"
        ref2 = Path(self.tmp_dir) / "ref2.png"
        ref1.write_bytes(b"fake-png-1")
        ref2.write_bytes(b"fake-png-2")

        result = dataset_manager.add_images([str(ref1), str(ref2)])
        self.assertEqual(result.added, 2)

        expected_internal = [
            str(self.folder / "datasets" / portraits.dataset_id / "ref1.png"),
            str(self.folder / "datasets" / portraits.dataset_id / "ref2.png"),
        ]
        # Mission 042: images_list became a thumbnail gallery — item.text()
        # is now the filename only (presentation), Qt.UserRole is the sole
        # source of truth for the full internal path (same convention as
        # ImagesPage since Mission 019).
        self.assertEqual(
            [datasets_page.images_list.item(i).data(Qt.UserRole)
             for i in range(datasets_page.images_list.count())],
            expected_internal,
        )
        self.assertEqual(
            [datasets_page.images_list.item(i).text()
             for i in range(datasets_page.images_list.count())],
            ["ref1.png", "ref2.png"],
        )
        self.assertEqual(
            [image.file_path for image in dataset_manager.active_dataset.images],
            expected_internal,
        )

        workspace_manager.save()
        workspace_manager.close()

        self.assertIsNone(dataset_manager.active_dataset_id)
        self.assertEqual(datasets_page.dataset_list.count(), 0)

        # Reopen with a second _wire() call — fresh instances, simulating
        # a real application restart rather than reusing in-memory state.
        (event_bus_2, workspace_manager_2, character_manager_2, dataset_manager_2,
         dashboard_2, characters_page_2, images_2, datasets_page_2) = self._wire()

        workspace_manager_2.open(self.folder)

        # Runtime-only per Mission 002/003 decisions: neither
        # active_character_id nor active_dataset_id survive a restart.
        # Checked BEFORE selecting anything below — selecting now would
        # trivially make this assertion pass for the wrong reason.
        self.assertIsNone(character_manager_2.active_character_id)
        self.assertIsNone(dataset_manager_2.active_dataset_id)

        # Mission 026: the reopened workspace also holds its auto-created
        # principal Character — retrieve "Aria" explicitly by name (the
        # Character these Datasets actually belong to), not by list index.
        restored_character = next(
            c for c in character_manager_2.characters if c.name == "Aria"
        )
        character_manager_2.select(restored_character.character_id)

        self.assertEqual(len(dataset_manager_2.datasets), 1)
        restored_dataset = dataset_manager_2.datasets[0]
        self.assertEqual(restored_dataset.name, "Portraits")
        self.assertEqual(
            [image.file_path for image in restored_dataset.images],
            expected_internal,
        )

    @patch("src.ui.pages.datasets_page.QMessageBox")
    @patch("src.ui.pages.datasets_page.SelectImagesDialog")
    def test_add_from_gallery_persists_without_physical_duplication_across_reopen(
        self, mock_dialog_cls, _mock_box
    ):
        """
        Mission 044: an image already present in the Workspace's own
        Images gallery, added to a Dataset via DatasetsPage.
        add_images_from_gallery(), must survive a real close/reopen
        cycle and must never be physically duplicated on disk — the
        Dataset's Image.file_path stays identical to the gallery
        Image's file_path, never a new file under
        datasets/<dataset_id>/ (WorkspaceStorage.copy_into_workspace()'s
        already-internal-source reuse, Mission 028).
        """

        (event_bus, workspace_manager, character_manager, dataset_manager,
         dashboard, characters_page, images, datasets_page) = self._wire()

        workspace_manager.create(self.folder)
        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)

        portraits = dataset_manager.create("Portraits")
        dataset_manager.select(portraits.dataset_id)

        gallery_source = Path(self.tmp_dir) / "gallery.png"
        gallery_source.write_bytes(b"fake-png-gallery")
        workspace_manager.add_images([str(gallery_source)])
        internal_gallery_path = workspace_manager.current_workspace.images[0].file_path

        mock_dialog_cls.return_value.exec.return_value = QDialog.Accepted
        mock_dialog_cls.return_value.selected_paths.return_value = [internal_gallery_path]
        datasets_page.add_images_from_gallery()

        self.assertEqual(
            [image.file_path for image in dataset_manager.active_dataset.images],
            [internal_gallery_path],
        )

        # No new file was written under the dataset's own destination
        # folder — it was never created in the first place, since the
        # gallery source is reused as-is.
        datasets_dir = self.folder / "datasets" / portraits.dataset_id
        self.assertFalse(datasets_dir.exists())

        workspace_manager.save()
        workspace_manager.close()

        event_bus_2 = EventBus()
        workspace_manager_2 = WorkspaceManager(event_bus=event_bus_2)
        character_manager_2 = CharacterManager(workspace_manager_2, event_bus=event_bus_2)
        dataset_manager_2 = DatasetManager(character_manager_2, workspace_manager_2, event_bus=event_bus_2)

        workspace_manager_2.open(self.folder)
        restored_character = next(
            c for c in character_manager_2.characters if c.name == "Aria"
        )
        character_manager_2.select(restored_character.character_id)

        self.assertEqual(len(dataset_manager_2.datasets), 1)
        restored_dataset = dataset_manager_2.datasets[0]
        self.assertEqual(
            [image.file_path for image in restored_dataset.images],
            [internal_gallery_path],
        )
        self.assertEqual(
            [image.file_path for image in workspace_manager_2.current_workspace.images],
            [internal_gallery_path],
        )
        self.assertFalse(datasets_dir.exists())

    def test_remove_from_dataset_survives_reopen_and_preserves_other_dataset_and_workspace(self):
        """
        Mission 045: the core property survives a real close/reopen —
        an image shared (via Mission 044's "Ajouter depuis Images...")
        between the Workspace's own gallery and two separate Datasets
        loses only its reference in Dataset A after removal there; it
        remains in Workspace.images, in Dataset B, and on disk, both
        immediately and after a real restart.
        """

        (event_bus, workspace_manager, character_manager, dataset_manager,
         dashboard, characters_page, images, datasets_page) = self._wire()

        workspace_manager.create(self.folder)
        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)

        gallery_source = Path(self.tmp_dir) / "shared.png"
        gallery_source.write_bytes(b"fake-shared-bytes")
        workspace_manager.add_images([str(gallery_source)])
        shared_path = workspace_manager.current_workspace.images[0].file_path

        dataset_a = dataset_manager.create("A")
        dataset_manager.select(dataset_a.dataset_id)
        dataset_manager.add_images([shared_path])

        dataset_b = dataset_manager.create("B")
        dataset_manager.select(dataset_b.dataset_id)
        dataset_manager.add_images([shared_path])

        # Back to Dataset A — remove the shared image from it only.
        dataset_manager.select(dataset_a.dataset_id)
        removed = dataset_manager.remove_images([shared_path])
        self.assertEqual(removed, 1)

        self.assertEqual(dataset_manager.active_dataset.images, [])
        self.assertEqual(datasets_page.images_list.count(), 0)

        workspace_manager.save()
        workspace_manager.close()

        (event_bus_2, workspace_manager_2, character_manager_2, dataset_manager_2,
         dashboard_2, characters_page_2, images_2, datasets_page_2) = self._wire()

        workspace_manager_2.open(self.folder)
        restored_character = next(
            c for c in character_manager_2.characters if c.name == "Aria"
        )
        character_manager_2.select(restored_character.character_id)

        restored_a = next(d for d in dataset_manager_2.datasets if d.name == "A")
        restored_b = next(d for d in dataset_manager_2.datasets if d.name == "B")

        self.assertEqual(restored_a.images, [])
        self.assertEqual([image.file_path for image in restored_b.images], [shared_path])
        self.assertEqual(
            [image.file_path for image in workspace_manager_2.current_workspace.images],
            [shared_path],
        )
        self.assertTrue(Path(shared_path).exists())

    def test_add_images_preserves_order_and_dedups(self):

        _, workspace_manager, character_manager, dataset_manager = self._wire()[:4]
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)

        destination = self.folder / "datasets" / dataset.dataset_id

        def _source(name, content=b"fake"):
            path = Path(self.tmp_dir) / name
            path.write_bytes(content)
            return str(path)

        result1 = dataset_manager.add_images(
            [_source("a.png"), _source("b.png"), _source("c.png")]
        )
        self.assertEqual(result1.added, 3)
        self.assertEqual(
            [image.file_path for image in dataset_manager.active_dataset.images],
            [str(destination / "a.png"), str(destination / "b.png"), str(destination / "c.png")],
        )

        # Mission 028: no cross-call dedup by content — re-selecting the
        # same external "b.png"/"a.png" sources a second time produces
        # its own collision-safe copies ("b_1.png"/"a_1.png"), it does
        # not silently disappear as it used to when file_path itself
        # was the dedup key. New external sources ("d.png"/"e.png")
        # are copied under their own names as before.
        result2 = dataset_manager.add_images(
            [_source("b.png", b"fake-b-2"), _source("d.png"), _source("a.png", b"fake-a-2"), _source("e.png")]
        )
        self.assertEqual(result2.added, 4)
        self.assertEqual(
            [image.file_path for image in dataset_manager.active_dataset.images],
            [
                str(destination / "a.png"), str(destination / "b.png"), str(destination / "c.png"),
                str(destination / "b_1.png"), str(destination / "d.png"),
                str(destination / "a_1.png"), str(destination / "e.png"),
            ],
        )

        # Dedup within a single call (exact same source path selected
        # twice) is still recognized and reported as skipped, first-seen
        # order preserved for the genuinely new ones.
        dataset2 = dataset_manager.create("Other")
        dataset_manager.select(dataset2.dataset_id)
        destination2 = self.folder / "datasets" / dataset2.dataset_id
        x, y, z = _source("x.png"), _source("y.png"), _source("z.png")
        result3 = dataset_manager.add_images([x, y, x, z, y])
        self.assertEqual(result3.added, 3)
        self.assertEqual(result3.skipped, [x, y])
        self.assertEqual(
            [image.file_path for image in dataset_manager.active_dataset.images],
            [str(destination2 / "x.png"), str(destination2 / "y.png"), str(destination2 / "z.png")],
        )

    def test_delete_active_dataset_resets_selection_and_persists(self):

        _, workspace_manager, character_manager, dataset_manager = self._wire()[:4]
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        keep = dataset_manager.create("Keep")
        drop = dataset_manager.create("Drop")
        dataset_manager.select(drop.dataset_id)

        result = dataset_manager.delete(drop.dataset_id)
        self.assertTrue(result.deleted)
        self.assertIsNone(dataset_manager.active_dataset_id)
        self.assertIsNone(dataset_manager.active_dataset)
        self.assertEqual([d.name for d in dataset_manager.datasets], ["Keep"])

        # Persists: reopening shows only the surviving dataset.
        _, workspace_manager_2, character_manager_2, dataset_manager_2 = self._wire()[:4]
        workspace_manager_2.open(self.folder)
        # Mission 026: retrieve "Aria" explicitly by name rather than by
        # list index (the reopened workspace also holds its auto-created
        # principal Character).
        restored_character = next(
            c for c in character_manager_2.characters if c.name == "Aria"
        )
        character_manager_2.select(restored_character.character_id)
        self.assertEqual([d.name for d in dataset_manager_2.datasets], ["Keep"])

    def test_dataset_manager_context_reset_on_character_and_workspace_change(self):

        _, workspace_manager, character_manager, dataset_manager = self._wire()[:4]
        workspace_manager.create(self.folder)

        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)
        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)
        self.assertEqual(dataset_manager.active_dataset_id, dataset.dataset_id)

        # Switching the active character must reset active_dataset_id —
        # the new character's dataset list is unrelated.
        kai = character_manager.create("Kai")
        character_manager.select(kai.character_id)
        self.assertIsNone(dataset_manager.active_dataset_id)

        # Re-select Aria and her dataset, then confirm a workspace close
        # also resets it.
        character_manager.select(aria.character_id)
        dataset_manager.select(dataset.dataset_id)
        self.assertIsNotNone(dataset_manager.active_dataset_id)

        workspace_manager.close()
        self.assertIsNone(dataset_manager.active_dataset_id)

    def test_datasets_page_rebuilds_on_relevant_events(self):

        (_, workspace_manager, character_manager, dataset_manager,
         _dashboard, _characters_page, _images, datasets_page) = self._wire()

        workspace_manager.create(self.folder)
        self.assertEqual(datasets_page.dataset_list.count(), 0)

        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        dataset = dataset_manager.create("Portraits")
        self.assertEqual(datasets_page.dataset_list.count(), 1)

        dataset_manager.select(dataset.dataset_id)
        source = Path(self.tmp_dir) / "a.png"
        source.write_bytes(b"fake-a")
        dataset_manager.add_images([str(source)])
        # add_images() only publishes workspace.saved — this is what
        # DatasetsPage's subscription to it must catch.
        self.assertEqual(datasets_page.images_list.count(), 1)

        workspace_manager.close()
        self.assertEqual(datasets_page.dataset_list.count(), 0)
        self.assertEqual(datasets_page.images_list.count(), 0)

    def test_no_duplicate_subscriptions_between_wire_calls(self):

        wired_1 = self._wire()
        wired_2 = self._wire()

        for obj_1, obj_2 in zip(wired_1, wired_2):
            self.assertIsNot(obj_1, obj_2)

        event_bus_1, event_bus_2 = wired_1[0], wired_2[0]

        # 4 subscribers registered directly by _wire() (dashboard, images,
        # characters_page, datasets_page) + CharacterManager's two own
        # internal subscriptions (active_character_id reset, and
        # Mission 026's principal-Character auto-creation) +
        # DatasetManager's own internal reset subscription = 7, on EACH
        # bus independently.
        self.assertEqual(len(event_bus_1._subscribers[WORKSPACE_CREATED]), 7)
        self.assertEqual(len(event_bus_2._subscribers[WORKSPACE_CREATED]), 7)
        self.assertTrue(
            set(event_bus_1._subscribers[WORKSPACE_CREATED]).isdisjoint(
                event_bus_2._subscribers[WORKSPACE_CREATED]
            )
        )

    def test_dashboard_and_images_unaffected_by_dataset_events(self):

        (_, workspace_manager, character_manager, dataset_manager,
         dashboard, _characters_page, images, _datasets_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        before_dashboard = dashboard.projectCard.value.text()
        before_images_count = images.list_widget.count()

        dataset_manager.create("Portraits")

        self.assertEqual(dashboard.projectCard.value.text(), before_dashboard)
        self.assertEqual(images.list_widget.count(), before_images_count)


class DatasetManagerAddImagesCopyTest(unittest.TestCase):
    """
    Mission 028: DatasetManager.add_images() — real physical copy into
    <workspace_root>/datasets/<dataset_id>/, mirroring
    WorkspaceManager.add_images()'s contract exactly. See
    MISSION_028.md sections 5.2/9/10/17.3.
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
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)
        dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(dataset.dataset_id)
        self.dataset_id = dataset.dataset_id

    def _external(self, name, content=b"fake-bytes"):
        path = self.external_dir / name
        path.write_bytes(content)
        return str(path)

    def test_image_copied_under_dataset_specific_subfolder(self):
        result = self.dataset_manager.add_images([self._external("photo.png")])

        self.assertEqual(result.added, 1)
        expected = self.folder / "datasets" / self.dataset_id / "photo.png"
        self.assertEqual(self.dataset_manager.active_dataset.images[0].file_path, str(expected))
        self.assertTrue(expected.exists())

    def test_source_stays_intact_after_import(self):
        source = self._external("photo.png")
        self.dataset_manager.add_images([source])

        self.assertTrue(Path(source).exists())

    def test_two_datasets_importing_the_same_filename_never_collide(self):
        other = self.dataset_manager.create("Other")

        self.dataset_manager.select(self.dataset_id)
        self.dataset_manager.add_images([self._external("shared.png", b"content-a")])

        self.dataset_manager.select(other.dataset_id)
        self.dataset_manager.add_images([self._external("shared.png", b"content-b")])

        portraits_path = self.folder / "datasets" / self.dataset_id / "shared.png"
        other_path = self.folder / "datasets" / other.dataset_id / "shared.png"

        self.assertTrue(portraits_path.exists())
        self.assertTrue(other_path.exists())
        self.assertEqual(portraits_path.read_bytes(), b"content-a")
        self.assertEqual(other_path.read_bytes(), b"content-b")

    def test_partial_failure_does_not_block_the_rest_of_the_batch(self):
        good = self._external("good.png")
        missing = str(self.external_dir / "missing.png")

        result = self.dataset_manager.add_images([good, missing])

        self.assertEqual(result.added, 1)
        self.assertEqual(result.failed, [missing])

    def test_no_image_persisted_for_a_failed_copy(self):
        missing = str(self.external_dir / "missing.png")

        self.dataset_manager.add_images([missing])

        self.assertEqual(self.dataset_manager.active_dataset.images, [])

    def test_already_internal_source_is_reused_without_a_new_copy(self):
        source = self._external("photo.png")
        self.dataset_manager.add_images([source])
        internal_path = self.dataset_manager.active_dataset.images[0].file_path

        with patch(
            "src.infrastructure.storage.workspace_storage.shutil.copy2"
        ) as copy2_mock:
            result = self.dataset_manager.add_images([internal_path])

        copy2_mock.assert_not_called()
        self.assertEqual(result.added, 0)
        self.assertEqual(result.skipped, [internal_path])
        self.assertEqual(len(self.dataset_manager.active_dataset.images), 1)

    # --- Mission 067: rollback + compensation on a save() failure ---

    def test_save_failure_after_several_copies_rolls_back_all_and_cleans_up(self):
        first = self._external("first.png")
        second = self._external("second.png")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.add_images([first, second])

        self.assertEqual(self.dataset_manager.active_dataset.images, [])
        self.assertFalse((self.folder / "datasets" / self.dataset_id / "first.png").exists())
        self.assertFalse((self.folder / "datasets" / self.dataset_id / "second.png").exists())
        self.assertTrue(Path(first).exists())
        self.assertTrue(Path(second).exists())

    def test_save_failure_with_a_mix_of_successful_and_failed_copies(self):
        good = self._external("good.png")
        missing = str(self.external_dir / "missing.png")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.add_images([good, missing])

        # The copy that already failed on its own terms is reported the
        # same way regardless of the later save() failure — only the
        # genuinely-added entry needs rolling back.
        self.assertEqual(self.dataset_manager.active_dataset.images, [])
        self.assertFalse((self.folder / "datasets" / self.dataset_id / "good.png").exists())

    def test_save_failure_with_a_passthrough_source_never_deletes_it(self):
        # A source already located elsewhere under workspace_root (here,
        # the Workspace's own images/ gallery) — mirrors
        # DatasetsPage.add_images_from_gallery() reusing an image
        # already in Workspace.images without any physical copy.
        gallery_source = self._external("gallery.png")
        self.workspace_manager.add_images([gallery_source])
        internal_gallery_path = self.workspace_manager.current_workspace.images[0].file_path

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.add_images([internal_gallery_path])

        self.assertEqual(self.dataset_manager.active_dataset.images, [])
        self.assertTrue(Path(internal_gallery_path).exists())

    def test_cleanup_failure_preserves_the_original_persistence_error(self):
        source = self._external("photo.png")

        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ), patch.object(Path, "unlink", side_effect=PermissionError("locked")):
            with self.assertRaises(WorkspaceManagerError) as ctx:
                self.dataset_manager.add_images([source])

        message = str(ctx.exception)
        self.assertIn("disk full", message)
        self.assertIn("orphaned", message)
        self.assertEqual(self.dataset_manager.active_dataset.images, [])
        self.assertTrue(Path(source).exists())

    def test_legacy_project_json_with_external_reference_still_loads_unchanged(self):
        legacy_external_path = str(self.external_dir / "legacy.png")
        Path(legacy_external_path).write_bytes(b"legacy-bytes")

        data = self.workspace_manager.current_workspace.to_dict()
        # Mission 026: WORKSPACE_CREATED also auto-created a principal
        # Character named after the project — "Aria" is a second,
        # explicitly-created one. Find it by name rather than assuming
        # a list index, same convention already used elsewhere in this
        # file (e.g. test_full_create_select_import_save_close_reopen_cycle).
        aria_dict = next(c for c in data["characters"] if c["name"] == "Aria")
        aria_dict["datasets"][0]["images"] = [
            {"image_id": "legacy-1", "file_path": legacy_external_path}
        ]
        WorkspaceStorage.save(self.folder, data)

        reopened_workspace_manager = WorkspaceManager(event_bus=EventBus())
        reopened_character_manager = CharacterManager(
            reopened_workspace_manager, event_bus=EventBus()
        )
        reopened_dataset_manager = DatasetManager(
            reopened_character_manager, reopened_workspace_manager, event_bus=EventBus()
        )
        reopened_workspace_manager.open(self.folder)
        restored_aria = next(
            c for c in reopened_character_manager.characters if c.name == "Aria"
        )
        reopened_character_manager.select(restored_aria.character_id)

        self.assertEqual(
            reopened_dataset_manager.datasets[0].images[0].file_path, legacy_external_path
        )

    def test_reopening_after_close_preserves_the_copied_image(self):
        source = self._external("photo.png")
        self.dataset_manager.add_images([source])
        expected_path = str(self.folder / "datasets" / self.dataset_id / "photo.png")

        self.workspace_manager.close()

        reopened_workspace_manager = WorkspaceManager(event_bus=EventBus())
        reopened_character_manager = CharacterManager(
            reopened_workspace_manager, event_bus=EventBus()
        )
        reopened_dataset_manager = DatasetManager(
            reopened_character_manager, reopened_workspace_manager, event_bus=EventBus()
        )
        reopened_workspace_manager.open(self.folder)
        restored_aria = next(
            c for c in reopened_character_manager.characters if c.name == "Aria"
        )
        reopened_character_manager.select(restored_aria.character_id)

        self.assertEqual(
            reopened_dataset_manager.datasets[0].images[0].file_path, expected_path
        )
        self.assertTrue(Path(expected_path).exists())

    def test_import_then_project_rename_remaps_the_internal_dataset_image(self):
        source = self._external("photo.png")
        self.dataset_manager.add_images([source])

        self.workspace_manager.rename("RenamedProject")

        new_root = self.folder.parent / "RenamedProject"
        expected = new_root / "datasets" / self.dataset_id / "photo.png"
        self.assertEqual(
            self.dataset_manager.active_dataset.images[0].file_path, str(expected)
        )
        self.assertTrue(expected.exists())

    # --- Mission 028 second smoke test: preview_collisions()/renames ---

    def test_preview_collisions_scoped_to_this_datasets_own_subfolder(self):
        source = self._external("photo.png")
        self.dataset_manager.add_images([source])

        collision_source = self._external("photo.png", b"different")
        collisions = self.dataset_manager.preview_collisions([collision_source])

        self.assertEqual(len(collisions), 1)
        self.assertEqual(collisions[0].suggested_name, "photo_1.png")

    def test_preview_collisions_empty_for_a_source_already_in_this_datasets_folder(self):
        source = self._external("photo.png")
        self.dataset_manager.add_images([source])
        internal_path = self.dataset_manager.active_dataset.images[0].file_path

        self.assertEqual(self.dataset_manager.preview_collisions([internal_path]), [])

    def test_add_images_uses_the_requested_rename_instead_of_auto_suffix(self):
        self.dataset_manager.add_images([self._external("photo.png")])

        new_source = self._external("also_photo.png", b"different")
        result = self.dataset_manager.add_images(
            [new_source], renames={new_source: "custom_name.png"}
        )

        self.assertEqual(result.added, 1)
        expected = self.folder / "datasets" / self.dataset_id / "custom_name.png"
        self.assertTrue(expected.exists())


class DatasetManagerRemoveImagesTest(unittest.TestCase):
    """
    Mission 045: DatasetManager.remove_images() — removes a reference
    from the active Dataset's own Image pool only, never the physical
    file, never Workspace.images, never another Dataset's own pool
    (Mission 011: each Dataset owns an independent list[Image]).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(self.dataset.dataset_id)

        source = Path(self.tmp_dir) / "photo.png"
        source.write_bytes(b"fake-png-bytes")
        self.dataset_manager.add_images([str(source)])
        self.internal_path = self.dataset_manager.active_dataset.images[0].file_path

    def test_remove_images_removes_the_matching_entry(self):
        removed = self.dataset_manager.remove_images([self.internal_path])

        self.assertEqual(removed, 1)
        self.assertEqual(self.dataset_manager.active_dataset.images, [])

    def test_remove_images_removes_multiple_entries_in_one_call(self):
        second = Path(self.tmp_dir) / "second.png"
        second.write_bytes(b"fake-png-2")
        self.dataset_manager.add_images([str(second)])
        internal_second = self.dataset_manager.active_dataset.images[-1].file_path

        removed = self.dataset_manager.remove_images([self.internal_path, internal_second])

        self.assertEqual(removed, 2)
        self.assertEqual(self.dataset_manager.active_dataset.images, [])

    def test_remove_images_with_an_unknown_path_is_a_no_op(self):
        unknown_path = str(Path(self.tmp_dir) / "never_added.png")

        removed = self.dataset_manager.remove_images([unknown_path])

        self.assertEqual(removed, 0)
        self.assertEqual(len(self.dataset_manager.active_dataset.images), 1)

    def test_remove_images_without_active_dataset_returns_zero(self):
        other_workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        other_character_manager = CharacterManager(other_workspace_manager, event_bus=self.event_bus)
        other_dataset_manager = DatasetManager(
            other_character_manager, other_workspace_manager, event_bus=self.event_bus
        )
        other_folder = Path(self.tmp_dir) / "OtherProject"
        other_workspace_manager.create(other_folder)

        removed = other_dataset_manager.remove_images([self.internal_path])

        self.assertEqual(removed, 0)

    def test_remove_images_never_touches_the_physical_file(self):
        self.dataset_manager.remove_images([self.internal_path])

        self.assertTrue(Path(self.internal_path).exists())

    def test_remove_images_never_touches_workspace_images(self):
        # This dataset's own image was copied under datasets/<id>/, not
        # referenced from Workspace.images — this test only documents
        # that remove_images() has no code path touching
        # workspace_manager.current_workspace.images at all, regardless
        # of where the removed image's file physically lives.
        images_before = list(self.workspace_manager.current_workspace.images)

        self.dataset_manager.remove_images([self.internal_path])

        self.assertEqual(self.workspace_manager.current_workspace.images, images_before)

    def test_remove_images_only_saves_when_something_actually_changed(self):
        with patch.object(self.workspace_manager, "save", wraps=self.workspace_manager.save) as save_spy:
            removed = self.dataset_manager.remove_images(
                [str(Path(self.tmp_dir) / "never_added.png")]
            )
            self.assertEqual(removed, 0)
            save_spy.assert_not_called()

            self.dataset_manager.remove_images([self.internal_path])
            save_spy.assert_called_once()

    def test_remove_images_does_not_affect_another_dataset_sharing_the_same_file(self):
        # The core property of Mission 045: an image added to two
        # Datasets from the same Workspace.images source (Mission 044)
        # is two independent Image objects sharing one file_path —
        # removing it from one Dataset must never touch the other.
        gallery_source = Path(self.tmp_dir) / "shared.png"
        gallery_source.write_bytes(b"fake-shared-bytes")
        self.workspace_manager.add_images([str(gallery_source)])
        shared_internal_path = self.workspace_manager.current_workspace.images[-1].file_path

        dataset_b = self.dataset_manager.create("Landscapes")
        self.dataset_manager.select(dataset_b.dataset_id)
        self.dataset_manager.add_images([shared_internal_path])

        self.dataset_manager.select(self.dataset.dataset_id)
        self.dataset_manager.add_images([shared_internal_path])

        removed = self.dataset_manager.remove_images([shared_internal_path])

        self.assertEqual(removed, 1)
        self.assertNotIn(
            shared_internal_path,
            [image.file_path for image in self.dataset_manager.active_dataset.images],
        )

        dataset_b_reloaded = next(d for d in self.dataset_manager.datasets if d.dataset_id == dataset_b.dataset_id)
        self.assertIn(shared_internal_path, [image.file_path for image in dataset_b_reloaded.images])
        self.assertIn(
            shared_internal_path,
            [image.file_path for image in self.workspace_manager.current_workspace.images],
        )
        self.assertTrue(Path(shared_internal_path).exists())


class DatasetManagerRemoveImagesRollbackTest(unittest.TestCase):
    """
    Mission 076: DatasetManager.remove_images() rolls back dataset.images
    to the exact previous list object if save() fails — no filesystem
    involved (confirmed by the Mission 045 audit above), no dedicated
    event published, no other state touched (active_dataset_id is never
    read/written by this method).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(self.dataset.dataset_id)

        self.paths = []
        for name in ("a.png", "b.png", "c.png"):
            source = Path(self.tmp_dir) / name
            source.write_bytes(f"fake-{name}".encode())
            self.dataset_manager.add_images([str(source)])
            self.paths.append(self.dataset_manager.active_dataset.images[-1].file_path)

    def test_remove_images_succeeds_normally_when_save_works(self):
        removed = self.dataset_manager.remove_images([self.paths[0], self.paths[2]])

        self.assertEqual(removed, 2)
        self.assertEqual(
            [image.file_path for image in self.dataset.images], [self.paths[1]]
        )

    def test_remove_images_save_failure_restores_exact_list_with_multiple_entries(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.remove_images([self.paths[0], self.paths[2]])

        self.assertEqual(
            [image.file_path for image in self.dataset.images], self.paths
        )
        self.assertIs(self.dataset_manager.active_dataset, self.dataset)

    def test_remove_images_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.remove_images([self.paths[1]])

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_remove_images_save_failure_publishes_no_success_event(self):
        received = []
        self.event_bus.subscribe(WORKSPACE_SAVED, lambda payload: received.append(payload))

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.remove_images([self.paths[0]])

        self.assertEqual(received, [])

    def test_remove_images_save_failure_does_not_affect_another_dataset(self):
        other_dataset = self.dataset_manager.create("Landscapes")
        self.dataset_manager.select(other_dataset.dataset_id)
        source = Path(self.tmp_dir) / "other.png"
        source.write_bytes(b"fake-other")
        self.dataset_manager.add_images([str(source)])
        other_path = other_dataset.images[0].file_path
        self.dataset_manager.select(self.dataset.dataset_id)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.remove_images([self.paths[0]])

        self.assertEqual([image.file_path for image in other_dataset.images], [other_path])

    def test_remove_images_save_failure_preserves_preexisting_duplicate_entries(self):
        # Dataset.images can contain two Image entries sharing the same
        # file_path if a hand-edited project.json is loaded (Mission
        # 045's own filtering never guarantees uniqueness) — the
        # rollback must restore both instances exactly, never losing or
        # multiplying either of them.
        duplicate = Image(image_id=str(uuid.uuid4()), file_path=self.paths[0])
        self.dataset.images.append(duplicate)
        original_length = len(self.dataset.images)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.remove_images([self.paths[0]])

        self.assertEqual(len(self.dataset.images), original_length)
        self.assertEqual(
            [image.file_path for image in self.dataset.images], self.paths + [self.paths[0]]
        )

    def test_retry_after_remove_images_failure_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.remove_images([self.paths[0], self.paths[2]])

        removed = self.dataset_manager.remove_images([self.paths[0], self.paths[2]])

        self.assertEqual(removed, 2)
        self.assertEqual([image.file_path for image in self.dataset.images], [self.paths[1]])
        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        dataset_on_disk = next(d for d in aria["datasets"] if d["dataset_id"] == self.dataset.dataset_id)
        self.assertEqual([image["file_path"] for image in dataset_on_disk["images"]], [self.paths[1]])


class DatasetsPageRemoveImagesPersistenceFailureTest(unittest.TestCase):
    """
    Mission 076: DatasetsPage.remove_selected_images_from_dataset()
    catches WorkspaceManagerError around dataset_manager.remove_images()
    and shows QMessageBox.critical() — images_list is resynced to the
    restored (previous) Domain state via update_datasets(), the same
    idiom already established by DatasetsPage.rename_dataset() (Mission
    070).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.page = DatasetsPage(self.dataset_manager, self.workspace_manager)

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)
        self.dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(self.dataset.dataset_id)

        self.paths = []
        for name in ("a.png", "b.png"):
            source = Path(self.tmp_dir) / name
            source.write_bytes(f"fake-{name}".encode())
            self.dataset_manager.add_images([str(source)])
            self.paths.append(self.dataset_manager.active_dataset.images[-1].file_path)

        self.page.update_datasets()

    def test_remove_selected_images_failure_shows_error_and_removes_nothing(self):
        self.page.images_list.item(0).setSelected(True)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.datasets_page.QMessageBox.critical") as critical_mock:
            self.page.remove_selected_images_from_dataset()

        self.assertTrue(critical_mock.called)
        self.assertEqual(
            [image.file_path for image in self.dataset.images], self.paths
        )
        self.assertEqual(self.page.images_list.count(), 2)

    def test_remove_selected_images_failure_leaves_project_json_unchanged(self):
        self.page.images_list.item(0).setSelected(True)

        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.datasets_page.QMessageBox.critical"):
            self.page.remove_selected_images_from_dataset()

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_after_remove_selected_images_failure_actually_removes(self):
        self.page.images_list.item(0).setSelected(True)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.datasets_page.QMessageBox.critical"):
            self.page.remove_selected_images_from_dataset()

        # The failed attempt's own except block already resynced
        # images_list (Domain unchanged, so selection was simply lost) —
        # a genuine retry re-selects and removes for real this time.
        self.page.images_list.item(0).setSelected(True)
        self.page.remove_selected_images_from_dataset()

        self.assertEqual([image.file_path for image in self.dataset.images], [self.paths[1]])
        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        dataset_on_disk = next(d for d in aria["datasets"] if d["dataset_id"] == self.dataset.dataset_id)
        self.assertEqual([image["file_path"] for image in dataset_on_disk["images"]], [self.paths[1]])


class DatasetsPageCollisionDialogTest(unittest.TestCase):
    """
    Mission 028 second smoke test: DatasetsPage.import_images() — same
    collision UX contract as ImagesPageCollisionDialogTest
    (test_images_page.py), scoped to a Dataset's own destination
    folder. ImportCollisionDialog.exec() is patched throughout.
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
        self.page = DatasetsPage(self.dataset_manager, self.workspace_manager)

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)
        dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(dataset.dataset_id)
        self.dataset_id = dataset.dataset_id

    def _external(self, name, content=b"fake-bytes"):
        path = self.external_dir / name
        path.write_bytes(content)
        return str(path)

    def _select(self, files):
        return patch(
            "src.ui.pages.datasets_page.QFileDialog.getOpenFileNames",
            return_value=(files, ""),
        )

    def test_no_dialog_shown_when_nothing_collides(self):
        with self._select([self._external("photo.png")]), \
                patch("src.ui.pages.datasets_page.ImportCollisionDialog") as dialog_cls, \
                patch("src.ui.pages.datasets_page.QMessageBox.information"):
            self.page.import_images()

            dialog_cls.assert_not_called()

        self.assertEqual(len(self.dataset_manager.active_dataset.images), 1)

    def test_rename_decision_is_applied_verbatim(self):
        self.dataset_manager.add_images([self._external("photo.png")])
        colliding_source = self._external("photo.png", b"different")

        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Accepted
        dialog.decisions.return_value = {colliding_source: "custom_name.png"}
        with self._select([colliding_source]), \
                patch("src.ui.pages.datasets_page.ImportCollisionDialog", return_value=dialog), \
                patch("src.ui.pages.datasets_page.QMessageBox.information"):
            self.page.import_images()

        images = self.dataset_manager.active_dataset.images
        self.assertEqual(len(images), 2)
        self.assertEqual(
            images[-1].file_path,
            str(self.folder / "datasets" / self.dataset_id / "custom_name.png"),
        )

    def test_skip_decision_never_imports_that_file(self):
        self.dataset_manager.add_images([self._external("photo.png")])
        colliding_source = self._external("photo.png", b"different")

        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Accepted
        dialog.decisions.return_value = {colliding_source: None}
        with self._select([colliding_source]), \
                patch("src.ui.pages.datasets_page.ImportCollisionDialog", return_value=dialog), \
                patch("src.ui.pages.datasets_page.QMessageBox.information") as info_mock:
            self.page.import_images()

        self.assertEqual(len(self.dataset_manager.active_dataset.images), 1)
        info_mock.assert_called_once()

    def test_cancelling_the_dialog_aborts_the_whole_import(self):
        self.dataset_manager.add_images([self._external("photo.png")])
        colliding_source = self._external("photo.png", b"different")

        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Rejected
        with self._select([colliding_source]), \
                patch("src.ui.pages.datasets_page.ImportCollisionDialog", return_value=dialog):
            self.page.import_images()

        self.assertEqual(len(self.dataset_manager.active_dataset.images), 1)


class DatasetsPageImportPersistenceFailureTest(unittest.TestCase):
    """
    Mission 067: DatasetManager.add_images() now rollbacks
    dataset.images and compensates any newly created copy on a save()
    failure — this class covers import_images()/add_images_from_gallery()
    intercepting that WorkspaceManagerError instead of letting it
    propagate unhandled.
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
        self.page = DatasetsPage(self.dataset_manager, self.workspace_manager)

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)
        dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(dataset.dataset_id)

        self.source = str(self.external_dir / "photo.png")
        Path(self.source).write_bytes(b"fake-bytes")

    def test_import_images_save_failure_shows_error_and_imports_nothing(self):
        with patch(
            "src.ui.pages.datasets_page.QFileDialog.getOpenFileNames",
            return_value=([self.source], ""),
        ), patch("src.ui.pages.datasets_page.QMessageBox") as mock_cls, patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ):
            self.page.import_images()

        mock_cls.critical.assert_called_once()
        self.assertEqual(self.dataset_manager.active_dataset.images, [])
        self.assertTrue(Path(self.source).exists())

    @patch("src.ui.pages.datasets_page.SelectImagesDialog")
    def test_add_from_gallery_save_failure_shows_error_and_never_reintroduces_the_image(
        self, mock_dialog_cls
    ):
        gallery_source = str(self.external_dir / "gallery.png")
        Path(gallery_source).write_bytes(b"gallery-bytes")
        self.workspace_manager.add_images([gallery_source])
        internal_gallery_path = self.workspace_manager.current_workspace.images[0].file_path

        mock_dialog_cls.return_value.exec.return_value = QDialog.Accepted
        mock_dialog_cls.return_value.selected_paths.return_value = [internal_gallery_path]

        with patch("src.ui.pages.datasets_page.QMessageBox") as mock_box, patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ):
            self.page.add_images_from_gallery()

        mock_box.critical.assert_called_once()
        self.assertEqual(self.dataset_manager.active_dataset.images, [])
        # A passthrough source (already in the gallery) is never
        # touched by the rollback either.
        self.assertTrue(Path(internal_gallery_path).exists())


class DatasetCreationWithoutManualCharacterSelectionTest(unittest.TestCase):
    """
    Mission 028 second smoke test — regression: DatasetManager used to
    depend on CharacterManager.active_character, which (since Mission
    026 hid the multi-character selection UI, and CharactersPage only
    ever *reads* principal_character, never calls select()) stays None
    for the entire session on any Workspace opened via WORKSPACE_OPENED
    — a user reopening an existing project had no selection and no way
    to make one, so "Nouveau dataset" always failed with "Aucun
    personnage actif". Fixed by switching DatasetManager to
    principal_character (see dataset_manager.py), the exact fix
    already applied to CharactersPage in Mission 026. Reproduces the
    architect's exact real sequence: create/open a Workspace, never
    call CharacterManager.select() at all, go straight to Datasets,
    create a Dataset, then import images into it — plus a close/reopen
    cycle, since that is precisely the path that used to trigger the
    bug (WORKSPACE_OPENED, never WORKSPACE_CREATED).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"
        self.external_dir = Path(self.tmp_dir) / "External"
        self.external_dir.mkdir()

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        datasets_page = DatasetsPage(dataset_manager, workspace_manager)
        for event_name in DATASET_EVENTS:
            event_bus.subscribe(event_name, datasets_page.update_datasets)
        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, datasets_page.update_datasets)
        return workspace_manager, character_manager, dataset_manager, datasets_page

    def test_create_dataset_and_import_images_without_ever_selecting_a_character(self):
        # 1. Create a fresh Workspace (auto-creates/selects the
        # principal Character, Mission 026) then close it and reopen
        # it — exactly the sequence that leaves active_character_id at
        # None (WORKSPACE_OPENED resets it, and nothing re-selects it,
        # since CharactersPage no longer calls select() at all).
        workspace_manager, character_manager, dataset_manager, datasets_page = self._wire()
        workspace_manager.create(self.folder)
        workspace_manager.close()

        (workspace_manager, character_manager,
         dataset_manager, datasets_page) = self._wire()
        workspace_manager.open(self.folder)

        self.assertIsNone(character_manager.active_character_id)
        self.assertIsNotNone(character_manager.principal_character)

        # 2. "Nouveau dataset" (DatasetsPage.create_dataset()'s own
        # logic, exercised directly through the Manager it delegates
        # to) must succeed without any manual Character selection.
        dataset = dataset_manager.create("Portraits")
        self.assertIsNotNone(dataset)
        self.assertEqual(len(dataset_manager.datasets), 1)

        dataset_manager.select(dataset.dataset_id)

        # 3. "Importer des images" must then succeed too — the second
        # reported symptom was only a consequence of the Dataset never
        # having been created in the first place.
        source = self.external_dir / "photo.png"
        source.write_bytes(b"fake-bytes")

        result = dataset_manager.add_images([str(source)])

        self.assertEqual(result.added, 1)
        expected = self.folder / "datasets" / dataset.dataset_id / "photo.png"
        self.assertEqual(dataset_manager.active_dataset.images[0].file_path, str(expected))
        self.assertTrue(expected.exists())
        self.assertTrue(source.exists())

        # 4. Reflected in DatasetsPage without any Character selection
        # ever having been made by the user.
        self.assertEqual(datasets_page.dataset_list.count(), 1)

        # 5. Survives a further close/reopen cycle.
        workspace_manager.close()
        (workspace_manager_2, character_manager_2,
         dataset_manager_2, datasets_page_2) = self._wire()
        workspace_manager_2.open(self.folder)

        self.assertIsNone(character_manager_2.active_character_id)
        self.assertEqual(len(dataset_manager_2.datasets), 1)
        self.assertEqual(
            dataset_manager_2.datasets[0].images[0].file_path, str(expected)
        )

    def test_create_dataset_without_open_workspace_shows_no_project_warning(self):
        # Mission 036: DatasetsPage.create_dataset() must distinguish
        # "no Workspace open" from "Workspace open, zero Character"
        # (see the sibling test below) — both make DatasetManager.
        # create() return None.
        _, _, _, datasets_page = self._wire()

        with patch(
            "src.ui.pages.datasets_page.QInputDialog.getText",
            return_value=("Portraits", True),
        ), patch("src.ui.pages.datasets_page.QMessageBox.warning") as mock_warning:
            datasets_page.create_dataset()
            mock_warning.assert_called_once_with(
                datasets_page,
                "Aucun projet ouvert",
                "Ouvrez ou créez un projet avant de créer un dataset."
            )

    def test_create_dataset_with_open_workspace_and_no_character_shows_personnage_warning(self):
        # Sibling of the test above: same None from DatasetManager.
        # create(), but here the Workspace is open with zero Character.
        workspace_manager, character_manager, _, datasets_page = self._wire()
        workspace_manager.create(self.folder)
        principal = character_manager.characters[0]
        character_manager.delete(principal.character_id)

        with patch(
            "src.ui.pages.datasets_page.QInputDialog.getText",
            return_value=("Portraits", True),
        ), patch("src.ui.pages.datasets_page.QMessageBox.warning") as mock_warning:
            datasets_page.create_dataset()
            mock_warning.assert_called_once_with(
                datasets_page,
                "Aucun personnage",
                "Ce projet ne possède aucun personnage — créez-en un depuis Characters avant de créer un dataset."
            )


class DatasetManagerCreateRollbackTest(unittest.TestCase):
    """
    Mission 072: DatasetManager.create() rolls back the in-memory
    append (the same Dataset instance just constructed) if save()
    fails — no snapshot, no filesystem involved, mirrors the delete()/
    update_name() rollback contracts already established by Missions
    068/070, applied here to the last remaining unsecured Domain-only
    mutation family.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.existing_dataset = self.dataset_manager.create("Alpha")

    def test_create_succeeds_normally_when_save_works(self):
        dataset = self.dataset_manager.create("Beta")

        self.assertIsNotNone(dataset)
        self.assertEqual(
            [d.dataset_id for d in self.dataset_manager.datasets],
            [self.existing_dataset.dataset_id, dataset.dataset_id],
        )

    def test_create_save_failure_removes_the_phantom_dataset(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.create("Beta")

        self.assertEqual(
            [d.dataset_id for d in self.dataset_manager.datasets],
            [self.existing_dataset.dataset_id],
        )

    def test_create_save_failure_publishes_no_success_event(self):
        received = []
        self.event_bus.subscribe(DATASET_CREATED, lambda payload: received.append(payload))

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.create("Beta")

        self.assertEqual(received, [])

    def test_create_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.create("Beta")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_after_create_failure_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.create("Beta")

        dataset = self.dataset_manager.create("Beta")

        self.assertIsNotNone(dataset)
        self.assertEqual(
            [d.dataset_id for d in self.dataset_manager.datasets],
            [self.existing_dataset.dataset_id, dataset.dataset_id],
        )

        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        self.assertEqual(
            sorted(d["dataset_id"] for d in aria["datasets"]),
            sorted([self.existing_dataset.dataset_id, dataset.dataset_id]),
        )

    def test_create_save_failure_does_not_affect_a_preexisting_unrelated_dataset(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.create("Beta")

        datasets = self.dataset_manager.datasets
        self.assertEqual(len(datasets), 1)
        # Same object, never touched by the failed second create().
        self.assertIs(datasets[0], self.existing_dataset)
        self.assertEqual(datasets[0].name, "Alpha")


class DatasetsPageCreatePersistenceFailureTest(unittest.TestCase):
    """
    Mission 072: DatasetsPage.create_dataset() catches
    WorkspaceManagerError around dataset_manager.create() and shows
    QMessageBox.critical() — mirrors the Presentation contract already
    used for rename/delete failures (Missions 070/068).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.datasets_page = DatasetsPage(self.dataset_manager, self.workspace_manager)
        for event_name in DATASET_EVENTS:
            self.event_bus.subscribe(event_name, self.datasets_page.update_datasets)

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

    def test_create_failure_shows_error_and_dataset_list_stays_empty(self):
        with patch(
            "src.ui.pages.datasets_page.QInputDialog.getText",
            return_value=("Portraits", True),
        ), patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.datasets_page.QMessageBox.critical") as mock_critical:
            self.datasets_page.create_dataset()

        self.assertTrue(mock_critical.called)
        self.assertEqual(self.dataset_manager.datasets, [])
        self.assertEqual(self.datasets_page.dataset_list.count(), 0)

    def test_create_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch(
            "src.ui.pages.datasets_page.QInputDialog.getText",
            return_value=("Portraits", True),
        ), patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.datasets_page.QMessageBox.critical"):
            self.datasets_page.create_dataset()

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_after_create_failure_actually_creates(self):
        with patch(
            "src.ui.pages.datasets_page.QInputDialog.getText",
            return_value=("Portraits", True),
        ), patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.datasets_page.QMessageBox.critical"):
            self.datasets_page.create_dataset()

        with patch(
            "src.ui.pages.datasets_page.QInputDialog.getText",
            return_value=("Portraits", True),
        ):
            self.datasets_page.create_dataset()

        self.assertEqual(len(self.dataset_manager.datasets), 1)
        self.assertEqual(self.datasets_page.dataset_list.count(), 1)


class DatasetManagerRenameTest(unittest.TestCase):
    """
    Mission 054: DatasetManager.update_name() — mirrors
    PromptManager.update_name()'s exact idempotent contract (Mission
    053), extended to Dataset. Never touches `images`, never touches a
    Training's own dataset_id reference.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.training_manager = TrainingManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(self.dataset.dataset_id)

        source = Path(self.tmp_dir) / "photo.png"
        source.write_bytes(b"fake-png-bytes")
        self.dataset_manager.add_images([str(source)])

    def test_update_name_renames_the_active_dataset(self):
        result = self.dataset_manager.update_name("Portraits Renamed")

        self.assertTrue(result)
        self.assertEqual(self.dataset_manager.active_dataset.name, "Portraits Renamed")

    def test_update_name_is_idempotent(self):
        with patch.object(self.workspace_manager, "save", wraps=self.workspace_manager.save) as save_spy:
            result = self.dataset_manager.update_name("Portraits")
            self.assertFalse(result)
            save_spy.assert_not_called()

            result = self.dataset_manager.update_name("Portraits Renamed")
            self.assertTrue(result)
            save_spy.assert_called_once()

    def test_update_name_without_active_dataset_returns_false(self):
        self.dataset_manager.active_dataset_id = None

        result = self.dataset_manager.update_name("Anything")

        self.assertFalse(result)

    def test_update_name_preserves_dataset_id_and_images(self):
        original_dataset_id = self.dataset.dataset_id
        original_images = list(self.dataset_manager.active_dataset.images)

        self.dataset_manager.update_name("Portraits Renamed")

        self.assertEqual(self.dataset_manager.active_dataset.dataset_id, original_dataset_id)
        self.assertEqual(self.dataset_manager.active_dataset.images, original_images)

    def test_update_name_empty_string_is_legitimate(self):
        result = self.dataset_manager.update_name("")

        self.assertTrue(result)
        self.assertEqual(self.dataset_manager.active_dataset.name, "")

    def test_update_name_never_touches_physical_files(self):
        internal_path = self.dataset_manager.active_dataset.images[0].file_path

        self.dataset_manager.update_name("Portraits Renamed")

        self.assertTrue(Path(internal_path).exists())

    def test_rename_preserves_training_reference_by_id(self):
        training = self.training_manager.create("Session 1", self.dataset.dataset_id)

        self.dataset_manager.update_name("Portraits Renamed")

        # The Training's dataset_id must still resolve to the same
        # Dataset — renamed, never recreated, never a new dataset_id.
        self.assertEqual(training.dataset_id, self.dataset.dataset_id)
        self.assertTrue(self.dataset_manager.is_referenced_by_training(self.dataset.dataset_id))
        resolved = next(d for d in self.dataset_manager.datasets if d.dataset_id == training.dataset_id)
        self.assertEqual(resolved.name, "Portraits Renamed")

    def test_rename_persists_after_close_reopen(self):
        self.dataset_manager.update_name("Portraits Renamed")

        self.workspace_manager.close()

        event_bus_2 = EventBus()
        workspace_manager_2 = WorkspaceManager(event_bus=event_bus_2)
        character_manager_2 = CharacterManager(workspace_manager_2, event_bus=event_bus_2)
        dataset_manager_2 = DatasetManager(character_manager_2, workspace_manager_2, event_bus=event_bus_2)
        workspace_manager_2.open(self.folder)

        restored_character = next(
            c for c in character_manager_2.characters if c.name == "Aria"
        )
        character_manager_2.select(restored_character.character_id)

        self.assertEqual(len(dataset_manager_2.datasets), 1)
        restored = dataset_manager_2.datasets[0]
        self.assertEqual(restored.dataset_id, self.dataset.dataset_id)
        self.assertEqual(restored.name, "Portraits Renamed")
        self.assertEqual(len(restored.images), 1)


class DatasetManagerRenameRollbackTest(unittest.TestCase):
    """
    Mission 070: DatasetManager.update_name() rolls back Dataset.name to
    its previous value if save() fails — a single-scalar Domain-only
    mutation, no filesystem involved, so a local rollback is sufficient.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(self.dataset.dataset_id)

    def test_update_name_succeeds_normally_when_save_works(self):
        result = self.dataset_manager.update_name("Portraits Renamed")

        self.assertTrue(result)
        self.assertEqual(self.dataset.name, "Portraits Renamed")

    def test_update_name_save_failure_restores_previous_name_on_same_object(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.update_name("Portraits Renamed")

        self.assertEqual(self.dataset.name, "Portraits")
        self.assertIs(self.dataset_manager.active_dataset, self.dataset)

    def test_update_name_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.update_name("Portraits Renamed")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_update_name_save_failure_publishes_no_success_event(self):
        # No dedicated *_RENAMED event exists for Dataset — this checks
        # that WORKSPACE_SAVED (published unconditionally by save() on
        # success) is not published on a failed attempt.
        received = []
        self.event_bus.subscribe(WORKSPACE_SAVED, lambda payload: received.append(payload))

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.update_name("Portraits Renamed")

        self.assertEqual(received, [])

    def test_retry_of_the_same_previously_rejected_name_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.update_name("Portraits Renamed")

        # Domain was rolled back to "Portraits" — retrying the exact
        # same "Portraits Renamed" value must not be short-circuited by
        # the idempotence guard, since it no longer matches.
        result = self.dataset_manager.update_name("Portraits Renamed")

        self.assertTrue(result)
        self.assertEqual(self.dataset.name, "Portraits Renamed")
        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        self.assertEqual(aria["datasets"][0]["name"], "Portraits Renamed")

    def test_update_name_idempotence_guard_still_applies_to_the_truly_persisted_value(self):
        with patch.object(self.workspace_manager, "save", wraps=self.workspace_manager.save) as save_spy:
            result = self.dataset_manager.update_name("Portraits")
            self.assertFalse(result)
            save_spy.assert_not_called()


class DatasetsPageRenameTest(unittest.TestCase):
    """
    Mission 054: DatasetsPage.name_edit — real-widget rename, mirroring
    PromptsPageRenameTest (Mission 053). dataset_list is NOT sorted
    (confirmed by inspection: update_datasets() never calls sorted() on
    datasets, unlike Model/Workflow/Training/Prompt/LoRA since Mission
    051) — a rename must never introduce a new sort, and selection must
    stay correct by dataset_id regardless.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "DatasetRenameProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)
        datasets_page = DatasetsPage(dataset_manager, workspace_manager)
        training_page = TrainingPage(training_manager, dataset_manager, workspace_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, datasets_page.update_datasets)
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, datasets_page.update_datasets)
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in DATASET_EVENTS:
            event_bus.subscribe(event_name, datasets_page.update_datasets)
        for event_name in TRAINING_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)

        return (
            event_bus, workspace_manager, character_manager, dataset_manager,
            training_manager, datasets_page, training_page,
        )

    def test_rename_via_widget_updates_manager_and_display(self):
        (_, workspace_manager, character_manager, dataset_manager,
         _, datasets_page, _) = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)

        self.assertEqual(datasets_page.name_edit.text(), "Portraits")

        datasets_page.name_edit.setText("Portraits Renamed")
        datasets_page.name_edit.editingFinished.emit()

        self.assertEqual(dataset_manager.active_dataset.name, "Portraits Renamed")
        self.assertEqual(dataset_manager.active_dataset.dataset_id, dataset.dataset_id)
        self.assertIn("Portraits Renamed", datasets_page.dataset_list.currentItem().text())

    def test_rename_with_no_active_dataset_is_a_no_op(self):
        (_, workspace_manager, character_manager, dataset_manager,
         _, datasets_page, _) = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        datasets_page.name_edit.setText("Anything")
        datasets_page.name_edit.editingFinished.emit()

        self.assertIsNone(dataset_manager.active_dataset_id)

    def test_dataset_list_stays_in_insertion_order_after_rename(self):
        # Mission 054 must not introduce a new sort for DatasetsPage —
        # unlike training_list (Mission 051), dataset_list keeps
        # Character.datasets' own insertion order.
        (_, workspace_manager, character_manager, dataset_manager,
         _, datasets_page, _) = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        zebra = dataset_manager.create("Zebra")
        apple = dataset_manager.create("Apple")
        dataset_manager.select(zebra.dataset_id)

        datasets_page.name_edit.setText("Aardvark")
        datasets_page.name_edit.editingFinished.emit()

        displayed_ids = [
            datasets_page.dataset_list.item(i).data(Qt.UserRole)
            for i in range(datasets_page.dataset_list.count())
        ]
        # Insertion order preserved (Zebra, now "Aardvark", still first;
        # Apple still second) — never reordered by name.
        self.assertEqual(displayed_ids, [zebra.dataset_id, apple.dataset_id])
        self.assertEqual(dataset_manager.active_dataset_id, zebra.dataset_id)
        self.assertEqual(datasets_page.dataset_list.currentItem().data(Qt.UserRole), zebra.dataset_id)
        self.assertIn("Aardvark", datasets_page.dataset_list.currentItem().text())

    def test_rename_updates_training_dataset_label(self):
        (_, workspace_manager, character_manager, dataset_manager,
         training_manager, datasets_page, training_page) = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)
        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        self.assertIn("Portraits", training_page.dataset_label.text())

        datasets_page.name_edit.setText("Portraits Renamed")
        datasets_page.name_edit.editingFinished.emit()

        # No new EventBus wiring involved — WORKSPACE_SAVED (already
        # subscribed by both Pages) is the only channel needed.
        self.assertIn("Portraits Renamed", training_page.dataset_label.text())
        self.assertEqual(training_manager.active_training.dataset_id, dataset.dataset_id)

    def test_rename_persists_after_close_reopen_via_ui(self):
        (_, workspace_manager, character_manager, dataset_manager,
         _, datasets_page, _) = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)

        datasets_page.name_edit.setText("Portraits Renamed")
        datasets_page.name_edit.editingFinished.emit()

        workspace_manager.close()

        (_, workspace_manager_2, character_manager_2, dataset_manager_2,
         _, datasets_page_2, _) = self._wire()
        workspace_manager_2.open(self.folder)

        restored_character = next(
            c for c in character_manager_2.characters if c.name == "Aria"
        )
        character_manager_2.select(restored_character.character_id)
        dataset_manager_2.select(dataset.dataset_id)

        restored = dataset_manager_2.active_dataset
        self.assertEqual(restored.name, "Portraits Renamed")
        self.assertEqual(restored.dataset_id, dataset.dataset_id)

    def test_rename_save_failure_shows_error_and_restores_widget_to_previous_name(self):
        (_, workspace_manager, character_manager, dataset_manager,
         _, datasets_page, _) = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)

        datasets_page.name_edit.setText("Portraits Renamed")
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.datasets_page.QMessageBox.critical") as critical_mock:
            datasets_page.name_edit.editingFinished.emit()

        self.assertTrue(critical_mock.called)
        self.assertEqual(dataset.name, "Portraits")
        self.assertEqual(datasets_page.name_edit.text(), "Portraits")
        self.assertIn("Portraits", datasets_page.dataset_list.currentItem().text())
        self.assertNotIn("Portraits Renamed", datasets_page.dataset_list.currentItem().text())

    def test_retry_after_rename_save_failure_actually_renames(self):
        (_, workspace_manager, character_manager, dataset_manager,
         _, datasets_page, _) = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)

        datasets_page.name_edit.setText("Portraits Renamed")
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.datasets_page.QMessageBox.critical"):
            datasets_page.name_edit.editingFinished.emit()

        datasets_page.name_edit.setText("Portraits Renamed")
        datasets_page.name_edit.editingFinished.emit()

        self.assertEqual(dataset.name, "Portraits Renamed")
        self.assertIn("Portraits Renamed", datasets_page.dataset_list.currentItem().text())


class DatasetManagerDeleteRollbackTest(unittest.TestCase):
    """
    Mission 068: DatasetManager.delete() rolls back the in-memory
    removal (and active_dataset_id) if save() fails — Domain-only
    mutation, no filesystem involved, so the rollback is a simple local
    re-insertion at the original index, never a full Workspace snapshot.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.dataset_a = self.dataset_manager.create("Alpha")
        self.dataset_b = self.dataset_manager.create("Beta")
        self.dataset_c = self.dataset_manager.create("Gamma")
        self.dataset_manager.select(self.dataset_b.dataset_id)

    def test_delete_succeeds_normally_when_save_works(self):
        result = self.dataset_manager.delete(self.dataset_b.dataset_id)

        self.assertTrue(result.deleted)
        self.assertFalse(result.cleanup_failed)
        self.assertIsNone(result.residual_path)
        self.assertEqual(
            [d.dataset_id for d in self.dataset_manager.datasets],
            [self.dataset_a.dataset_id, self.dataset_c.dataset_id],
        )
        self.assertIsNone(self.dataset_manager.active_dataset_id)

    def test_delete_save_failure_restores_object_at_original_index(self):
        received = []
        self.event_bus.subscribe(DATASET_DELETED, lambda payload: received.append(payload))

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.delete(self.dataset_b.dataset_id)

        datasets = self.dataset_manager.datasets
        self.assertEqual(
            [d.dataset_id for d in datasets],
            [self.dataset_a.dataset_id, self.dataset_b.dataset_id, self.dataset_c.dataset_id],
        )
        # Same object, not a recreated equivalent.
        self.assertIs(datasets[1], self.dataset_b)
        self.assertEqual(received, [])

    def test_delete_save_failure_restores_active_dataset_id(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.delete(self.dataset_b.dataset_id)

        self.assertEqual(self.dataset_manager.active_dataset_id, self.dataset_b.dataset_id)

    def test_delete_save_failure_never_touches_an_unrelated_active_id(self):
        self.dataset_manager.select(self.dataset_a.dataset_id)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.delete(self.dataset_b.dataset_id)

        self.assertEqual(self.dataset_manager.active_dataset_id, self.dataset_a.dataset_id)

    def test_delete_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.delete(self.dataset_b.dataset_id)

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_after_save_failure_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.delete(self.dataset_b.dataset_id)

        result = self.dataset_manager.delete(self.dataset_b.dataset_id)

        self.assertTrue(result.deleted)
        self.assertEqual(
            [d.dataset_id for d in self.dataset_manager.datasets],
            [self.dataset_a.dataset_id, self.dataset_c.dataset_id],
        )

        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        self.assertEqual(
            sorted(d["dataset_id"] for d in aria["datasets"]),
            sorted([self.dataset_a.dataset_id, self.dataset_c.dataset_id]),
        )

    def test_delete_save_failure_still_respects_the_training_guard(self):
        training_manager = TrainingManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        training_manager.create("Session 1", self.dataset_b.dataset_id)

        # The referenced-by-training guard must reject the deletion
        # before the transactional path is ever entered — save() must
        # not even be attempted.
        with patch.object(WorkspaceStorage, "save") as save_spy:
            result = self.dataset_manager.delete(self.dataset_b.dataset_id)
            save_spy.assert_not_called()

        self.assertFalse(result.deleted)
        self.assertEqual(len(self.dataset_manager.datasets), 3)


class DatasetManagerPhysicalDeletionTest(unittest.TestCase):
    """
    Mission 075: DatasetManager.delete() now also transactionally
    removes the Dataset's private folder (datasets/<id>/) — created
    lazily only for directly-imported images, never for images
    referenced from the gallery. Covers the folder-move/persist/
    permanent-delete pipeline with real files on disk, independently
    of the pre-existing Domain-only rollback already covered by
    DatasetManagerDeleteRollbackTest (which never touches the
    filesystem, since its dataset_b never receives any image).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"
        self.source_dir = Path(self.tmp_dir) / "External"
        self.source_dir.mkdir()

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(self.dataset.dataset_id)

        self.image_source = self.source_dir / "photo.png"
        self.image_source.write_bytes(b"fake png data")

    def _dataset_folder(self):
        return self.folder / "datasets" / self.dataset.dataset_id

    def test_delete_with_no_physical_folder_is_unaffected(self):
        # Never imported directly -> no folder was ever created.
        result = self.dataset_manager.delete(self.dataset.dataset_id)

        self.assertTrue(result.deleted)
        self.assertFalse(result.cleanup_failed)
        self.assertFalse((self.folder / ".trash").exists())

    def test_delete_removes_the_physical_folder_entirely(self):
        self.dataset_manager.add_images([str(self.image_source)])
        dataset_folder = self._dataset_folder()
        self.assertTrue(dataset_folder.exists())
        self.assertEqual([p.name for p in dataset_folder.iterdir()], ["photo.png"])

        result = self.dataset_manager.delete(self.dataset.dataset_id)

        self.assertTrue(result.deleted)
        self.assertFalse(result.cleanup_failed)
        self.assertFalse(dataset_folder.exists())
        # Nothing left behind in .trash/ either — permanent cleanup succeeded.
        trash_root = self.folder / ".trash"
        self.assertTrue(not trash_root.exists() or list(trash_root.iterdir()) == [])

    def test_delete_failure_to_move_folder_aborts_before_any_mutation(self):
        self.dataset_manager.add_images([str(self.image_source)])
        dataset_folder = self._dataset_folder()

        with patch.object(
            WorkspaceStorage, "rename_folder",
            side_effect=WorkspaceStorageError("locked by another process"),
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.delete(self.dataset.dataset_id)

        # Nothing was touched: folder still there, Domain untouched, no save().
        self.assertTrue(dataset_folder.exists())
        self.assertEqual(
            [d.dataset_id for d in self.dataset_manager.datasets],
            [self.dataset.dataset_id],
        )

    def test_delete_save_failure_restores_folder_to_its_original_location_with_content(self):
        self.dataset_manager.add_images([str(self.image_source)])
        dataset_folder = self._dataset_folder()

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.delete(self.dataset.dataset_id)

        self.assertTrue(dataset_folder.exists())
        self.assertEqual([p.name for p in dataset_folder.iterdir()], ["photo.png"])
        self.assertEqual(
            [d.dataset_id for d in self.dataset_manager.datasets],
            [self.dataset.dataset_id],
        )
        # .trash/ itself (an empty staging directory) may still exist —
        # only its content, the actually moved folder, must be gone.
        trash_root = self.folder / ".trash"
        self.assertTrue(not trash_root.exists() or list(trash_root.iterdir()) == [])

    def test_delete_double_failure_still_restores_domain_and_reports_manual_recovery(self):
        self.dataset_manager.add_images([str(self.image_source)])
        dataset_folder = self._dataset_folder()
        other = self.dataset_manager.create("Unrelated")

        original_rename_folder = WorkspaceStorage.rename_folder
        call_count = {"n": 0}

        def flaky_rename_folder(old_root, new_root):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First call: the move into .trash/ itself, let it succeed.
                return original_rename_folder(old_root, new_root)
            # Second call: the reverse move attempted after save() fails.
            raise WorkspaceStorageError("still locked by another process")

        with patch.object(WorkspaceStorage, "rename_folder", side_effect=flaky_rename_folder), \
                patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError) as ctx:
                self.dataset_manager.delete(self.dataset.dataset_id)

        # Domain restored regardless of the filesystem rollback failure:
        # same object, same index, active_dataset_id restored.
        datasets = self.dataset_manager.datasets
        self.assertEqual(
            [d.dataset_id for d in datasets],
            [self.dataset.dataset_id, other.dataset_id],
        )
        self.assertIs(datasets[0], self.dataset)

        # The folder is left in .trash/, not at its original location.
        self.assertFalse(dataset_folder.exists())
        trash_root = self.folder / ".trash"
        residual = list(trash_root.iterdir())
        self.assertEqual(len(residual), 1)
        self.assertEqual([p.name for p in residual[0].iterdir()], ["photo.png"])

        # No other entity or folder touched.
        self.assertEqual(len(self.dataset_manager.datasets), 2)

        # The error message contains actionable manual-recovery information.
        message = str(ctx.exception)
        self.assertIn(str(residual[0]), message)
        self.assertIn(str(dataset_folder), message)
        self.assertIn("restored", message)

    def test_delete_permanent_cleanup_failure_never_rolls_back_the_persisted_deletion(self):
        self.dataset_manager.add_images([str(self.image_source)])
        dataset_folder = self._dataset_folder()

        with patch.object(WorkspaceStorage, "delete_folder", side_effect=WorkspaceStorageError("locked")):
            result = self.dataset_manager.delete(self.dataset.dataset_id)

        self.assertTrue(result.deleted)
        self.assertTrue(result.cleanup_failed)
        self.assertIsNotNone(result.residual_path)
        self.assertFalse(dataset_folder.exists())
        self.assertEqual(self.dataset_manager.datasets, [])
        self.assertTrue(Path(result.residual_path).exists())

        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        self.assertEqual(aria["datasets"], [])

    def test_delete_never_touches_an_unrelated_datasets_folder(self):
        self.dataset_manager.add_images([str(self.image_source)])
        other = self.dataset_manager.create("Unrelated")
        other_source = self.source_dir / "other.png"
        other_source.write_bytes(b"other data")
        self.dataset_manager.select(other.dataset_id)
        self.dataset_manager.add_images([str(other_source)])
        other_folder = self.folder / "datasets" / other.dataset_id

        self.dataset_manager.delete(self.dataset.dataset_id)

        self.assertTrue(other_folder.exists())
        self.assertEqual([p.name for p in other_folder.iterdir()], ["other.png"])

    def test_retry_after_move_failure_is_a_genuine_new_attempt(self):
        self.dataset_manager.add_images([str(self.image_source)])
        dataset_folder = self._dataset_folder()

        with patch.object(
            WorkspaceStorage, "rename_folder",
            side_effect=WorkspaceStorageError("locked by another process"),
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.delete(self.dataset.dataset_id)

        result = self.dataset_manager.delete(self.dataset.dataset_id)

        self.assertTrue(result.deleted)
        self.assertFalse(dataset_folder.exists())
        self.assertEqual(self.dataset_manager.datasets, [])

    def test_trash_folder_names_never_collide_across_attempts(self):
        # A first attempt that fails at save() leaves the Domain intact
        # (retried below), but exercises the same trash-naming logic; a
        # leftover residue from a previous permanent-cleanup failure must
        # never cause the next attempt's move to collide with it.
        self.dataset_manager.add_images([str(self.image_source)])

        with patch.object(WorkspaceStorage, "delete_folder", side_effect=WorkspaceStorageError("locked")):
            first = self.dataset_manager.delete(self.dataset.dataset_id)

        self.assertTrue(first.deleted)
        self.assertTrue(first.cleanup_failed)
        first_residual = Path(first.residual_path)
        self.assertTrue(first_residual.exists())

        # Recreate a dataset with a colliding id is not possible (uuid4),
        # but re-populating and re-deleting the *same* dataset_id is not
        # possible either once deleted — instead, verify a second,
        # independent dataset's own transit name never collides with the
        # residue left behind by the first.
        second_dataset = self.dataset_manager.create("Portraits 2")
        self.dataset_manager.select(second_dataset.dataset_id)
        second_source = self.source_dir / "second.png"
        second_source.write_bytes(b"second data")
        self.dataset_manager.add_images([str(second_source)])

        second = self.dataset_manager.delete(second_dataset.dataset_id)

        self.assertTrue(second.deleted)
        self.assertFalse(second.cleanup_failed)
        # The first residue is still exactly where it was, untouched.
        self.assertTrue(first_residual.exists())
        self.assertEqual([p.name for p in first_residual.iterdir()], ["photo.png"])


class DatasetsPageDeleteConfirmationTest(unittest.TestCase):
    """
    Mission 062: DatasetsPage.delete_dataset() now confirms before
    deleting, mirroring ImagesPage.delete_selected_images()'s
    established QMessageBox pattern (Mission 046) — Cancel is the safe
    default. The pre-existing "referenced by a Training" guard must
    still run, and refuse the deletion, *before* any confirmation
    dialog is shown — a Dataset that cannot be deleted must never first
    ask "are you sure?".
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "DatasetDeleteProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)
        datasets_page = DatasetsPage(dataset_manager, workspace_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, datasets_page.update_datasets)
        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, datasets_page.update_datasets)
        for event_name in DATASET_EVENTS:
            event_bus.subscribe(event_name, datasets_page.update_datasets)

        return (
            event_bus, workspace_manager, character_manager, dataset_manager,
            training_manager, datasets_page,
        )

    def _confirm_delete(self, accept: bool):
        # Same headless technique as test_images_page.py's
        # _confirm_delete() — avoids ever showing a real modal.
        patcher = patch("src.ui.pages.datasets_page.QMessageBox")
        mock_cls = patcher.start()
        self.addCleanup(patcher.stop)

        accept_sentinel = object()
        cancel_sentinel = object()
        box_instance = mock_cls.return_value
        box_instance.addButton.side_effect = [accept_sentinel, cancel_sentinel]
        box_instance.clickedButton.return_value = (
            accept_sentinel if accept else cancel_sentinel
        )

        return mock_cls

    def test_delete_with_no_selection_is_a_no_op(self):
        _, workspace_manager, character_manager, dataset_manager, _, datasets_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        mock_cls = self._confirm_delete(accept=True)

        datasets_page.delete_dataset()

        mock_cls.assert_not_called()

    def test_delete_confirmed_removes_dataset(self):
        (_, workspace_manager, character_manager, dataset_manager,
         _, datasets_page) = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)

        self._confirm_delete(accept=True)

        datasets_page.delete_dataset()

        self.assertIsNone(dataset_manager.active_dataset_id)
        self.assertEqual(dataset_manager.datasets, [])

    def test_delete_cancelled_calls_neither_manager_nor_mutates_state(self):
        (_, workspace_manager, character_manager, dataset_manager,
         _, datasets_page) = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)

        self._confirm_delete(accept=False)

        with patch.object(dataset_manager, "delete") as delete_mock:
            datasets_page.delete_dataset()
            delete_mock.assert_not_called()

        self.assertEqual(dataset_manager.active_dataset_id, dataset.dataset_id)
        self.assertEqual(len(dataset_manager.datasets), 1)

    def test_delete_blocked_by_training_reference_never_shows_confirmation(self):
        (_, workspace_manager, character_manager, dataset_manager,
         training_manager, datasets_page) = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)
        training_manager.create("Session 1", dataset.dataset_id)

        mock_cls = self._confirm_delete(accept=True)

        datasets_page.delete_dataset()

        # The existing guard fires .warning() (a classmethod on
        # QMessageBox) — never constructs/execs a confirmation instance.
        mock_cls.warning.assert_called_once()
        mock_cls.return_value.exec.assert_not_called()
        self.assertEqual(len(dataset_manager.datasets), 1)

    def test_delete_confirmed_save_failure_shows_error_and_keeps_the_dataset(self):
        """
        Mission 068: DatasetManager.delete() rolls back the Domain
        removal (and active_dataset_id) before re-raising on a save()
        failure — the Page must intercept WorkspaceManagerError, inform
        the user, and never present the deletion as successful. Nothing
        was ever removed from dataset_list itself (no refresh happens on
        a failure), so the dataset stays visible/selectable without any
        extra refresh call.
        """
        (_, workspace_manager, character_manager, dataset_manager,
         _, datasets_page) = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)

        mock_cls = self._confirm_delete(accept=True)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            datasets_page.delete_dataset()

        mock_cls.critical.assert_called_once()
        self.assertEqual(dataset_manager.active_dataset_id, dataset.dataset_id)
        self.assertEqual(len(dataset_manager.datasets), 1)
        self.assertIs(dataset_manager.datasets[0], dataset)

    def test_retry_after_save_failure_actually_deletes(self):
        (_, workspace_manager, character_manager, dataset_manager,
         _, datasets_page) = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)

        self._confirm_delete(accept=True)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            datasets_page.delete_dataset()

        self._confirm_delete(accept=True)
        datasets_page.delete_dataset()

        self.assertIsNone(dataset_manager.active_dataset_id)
        self.assertEqual(dataset_manager.datasets, [])

    def test_confirmation_text_distinguishes_gallery_from_private_copies(self):
        """
        Mission 075: delete_dataset() now physically removes the
        Dataset's private folder — the pre-existing confirmation text
        must no longer imply that every image it contains survives.
        """
        (_, workspace_manager, character_manager, dataset_manager,
         _, datasets_page) = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)

        mock_cls = self._confirm_delete(accept=False)

        datasets_page.delete_dataset()

        text = mock_cls.return_value.setText.call_args[0][0]
        self.assertIn("galerie", text)
        self.assertIn("importées directement", text)

    def test_delete_confirmed_shows_warning_when_cleanup_fails(self):
        (_, workspace_manager, character_manager, dataset_manager,
         _, datasets_page) = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        source_dir = Path(self.tmp_dir) / "External"
        source_dir.mkdir()
        image_source = source_dir / "photo.png"
        image_source.write_bytes(b"fake png data")

        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)
        dataset_manager.add_images([str(image_source)])

        mock_cls = self._confirm_delete(accept=True)

        with patch.object(WorkspaceStorage, "delete_folder", side_effect=WorkspaceStorageError("locked")):
            datasets_page.delete_dataset()

        mock_cls.warning.assert_called_once()
        mock_cls.critical.assert_not_called()
        self.assertEqual(dataset_manager.datasets, [])


class DatasetsPageDeleteButtonStateTest(unittest.TestCase):
    """
    Mission 063: "Supprimer" must always reflect whether there is
    currently a valid selection to act on, mirroring ImagesPage's
    established delete_button.setEnabled() pattern (Mission 046) —
    never a silent no-op behind an always-clickable button. This is
    strictly about selection state: the pre-existing "referenced by a
    Training" guard (Mission 062, above) still only intervenes at
    click time via delete_dataset(), never by disabling the button.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "DatasetButtonStateProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)
        datasets_page = DatasetsPage(dataset_manager, workspace_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, datasets_page.update_datasets)
        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, datasets_page.update_datasets)
        for event_name in DATASET_EVENTS:
            event_bus.subscribe(event_name, datasets_page.update_datasets)

        return (
            workspace_manager, character_manager, dataset_manager,
            training_manager, datasets_page,
        )

    def test_disabled_before_any_workspace(self):
        _, _, _, _, datasets_page = self._wire()
        self.assertFalse(datasets_page.delete_button.isEnabled())

    def test_disabled_with_no_selection_then_enabled_on_select(self):
        workspace_manager, character_manager, dataset_manager, _, datasets_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        self.assertFalse(datasets_page.delete_button.isEnabled())

        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)

        self.assertTrue(datasets_page.delete_button.isEnabled())

    def test_deselecting_disables_delete_button(self):
        workspace_manager, character_manager, dataset_manager, _, datasets_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)
        self.assertTrue(datasets_page.delete_button.isEnabled())

        datasets_page.dataset_list.setCurrentItem(None)

        self.assertFalse(datasets_page.delete_button.isEnabled())

    def test_delete_button_stays_consistent_after_list_rebuild(self):
        workspace_manager, character_manager, dataset_manager, _, datasets_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset_a = dataset_manager.create("Portraits")
        dataset_manager.select(dataset_a.dataset_id)
        self.assertTrue(datasets_page.delete_button.isEnabled())

        # DATASET_CREATED triggers update_datasets() -> a full list
        # rebuild, while the active selection itself is untouched.
        dataset_manager.create("Poses")

        self.assertTrue(datasets_page.delete_button.isEnabled())
        self.assertEqual(
            datasets_page.dataset_list.currentItem().data(Qt.UserRole), dataset_a.dataset_id
        )

    def test_disabled_after_workspace_closed(self):
        workspace_manager, character_manager, dataset_manager, _, datasets_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)
        self.assertTrue(datasets_page.delete_button.isEnabled())

        workspace_manager.close()

        self.assertFalse(datasets_page.delete_button.isEnabled())

    def test_disabled_after_deleting_the_selected_dataset(self):
        workspace_manager, character_manager, dataset_manager, _, datasets_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)
        self.assertTrue(datasets_page.delete_button.isEnabled())

        # DATASET_DELETED triggers update_datasets() -> the button must
        # be recomputed from the resulting (now empty) selection.
        dataset_manager.delete(dataset.dataset_id)

        self.assertFalse(datasets_page.delete_button.isEnabled())

    def test_selecting_a_dataset_referenced_by_training_still_enables_button(self):
        # Mission 063 is strictly about selection state — the Training
        # guard only intervenes at click time (see
        # DatasetsPageDeleteConfirmationTest above), never by disabling
        # the button itself.
        (workspace_manager, character_manager, dataset_manager,
         training_manager, datasets_page) = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)
        training_manager.create("Session 1", dataset.dataset_id)

        self.assertTrue(datasets_page.delete_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
