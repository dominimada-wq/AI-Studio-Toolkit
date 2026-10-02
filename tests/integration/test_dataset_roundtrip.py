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
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from src.core.event_bus import EventBus
from src.domain.dataset import Dataset, DatasetEntryMetadata
from src.domain.image import Image
from src.infrastructure.storage.workspace_storage import WorkspaceStorage, WorkspaceStorageError
from src.managers.application_settings_manager import ApplicationSettingsManager
from src.managers.workspace_manager import (
    WorkspaceManager,
    WorkspaceManagerError,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_SAVED,
    WORKSPACE_CLOSED,
    WORKSPACE_RENAMED,
)
from src.managers.character_manager import (
    CharacterManager,
    CHARACTER_CREATED,
    CHARACTER_SELECTED,
    CHARACTER_DELETED,
)
from src.managers.workspace_lifecycle import create_workspace_with_default_character
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
from src.ui.main_window import MainWindow
from src.ui.pages.training_page import TrainingPage
from tests.integration._qt_dialog_safety_net import start_dialog_guard, stop_dialog_guard

WORKSPACE_EVENTS = (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_SAVED, WORKSPACE_CLOSED)
CHARACTER_EVENTS = (CHARACTER_CREATED, CHARACTER_SELECTED, CHARACTER_DELETED)
DATASET_EVENTS = (DATASET_CREATED, DATASET_SELECTED, DATASET_DELETED)
TRAINING_EVENTS = (TRAINING_CREATED, TRAINING_SELECTED, TRAINING_DELETED)

_app = QApplication.instance() or QApplication([])


class DatasetEntryMetadataDomainTest(unittest.TestCase):
    """
    Mission 098: pure Domain round-trip of Dataset.entries/
    DatasetEntryMetadata — additive to Dataset.images, never restructuring
    it (see MISSION_098.md section 3/4).
    """

    def test_default_entries_is_empty_dict(self):
        dataset = Dataset(dataset_id="d1", name="Portraits")
        self.assertEqual(dataset.entries, {})

    def test_to_dict_includes_entries_alongside_unchanged_images(self):
        dataset = Dataset(
            dataset_id="d1",
            name="Portraits",
            images=[Image(image_id="img1", file_path="/a.png")],
            entries={"img1": DatasetEntryMetadata(caption="a girl smiling")},
        )
        data = dataset.to_dict()
        self.assertEqual(data["images"], [{"image_id": "img1", "file_path": "/a.png"}])
        self.assertEqual(data["entries"], {"img1": {"caption": "a girl smiling"}})

    def test_from_dict_round_trips_entries(self):
        data = {
            "dataset_id": "d1",
            "name": "Portraits",
            "images": [{"image_id": "img1", "file_path": "/a.png"}],
            "entries": {"img1": {"caption": "a girl smiling"}},
        }
        dataset = Dataset.from_dict(data)
        self.assertEqual(dataset.entries, {"img1": DatasetEntryMetadata(caption="a girl smiling")})

    def test_from_dict_defaults_entries_to_empty_dict_when_key_absent(self):
        # A project.json saved before Mission 098 has no "entries" key at
        # all — must load exactly as if entries were {}, no migration.
        data = {
            "dataset_id": "d1",
            "name": "Portraits",
            "images": [{"image_id": "img1", "file_path": "/a.png"}],
        }
        dataset = Dataset.from_dict(data)
        self.assertEqual(dataset.entries, {})
        # And Dataset.images is entirely unaffected by this field's
        # presence or absence.
        self.assertEqual(dataset.images, [Image(image_id="img1", file_path="/a.png")])

    def test_from_dict_ignores_non_dict_entries_value(self):
        data = {"dataset_id": "d1", "name": "Portraits", "entries": "not-a-dict"}
        dataset = Dataset.from_dict(data)
        self.assertEqual(dataset.entries, {})

    def test_from_dict_filters_out_malformed_entry_rows(self):
        # Defensive compatibility (never presented as a real migration):
        # a hand-edited project.json with a non-str key or a non-dict
        # value for one entry is dropped, not raised.
        data = {
            "dataset_id": "d1",
            "name": "Portraits",
            "entries": {
                "img1": {"caption": "valid"},
                "img2": "not-a-dict",
                42: {"caption": "non-str key"},
            },
        }
        dataset = Dataset.from_dict(data)
        self.assertEqual(dataset.entries, {"img1": DatasetEntryMetadata(caption="valid")})

    def test_entry_metadata_caption_defaults_to_empty_string(self):
        metadata = DatasetEntryMetadata.from_dict({})
        self.assertEqual(metadata.caption, "")

    def test_entry_metadata_from_dict_ignores_non_str_caption(self):
        metadata = DatasetEntryMetadata.from_dict({"caption": 42})
        self.assertEqual(metadata.caption, "")

    def test_explicit_empty_caption_round_trips_distinctly_from_absence(self):
        # An explicitly empty caption must survive a round trip as a
        # present entry — never collapsed to "no entry at all".
        dataset = Dataset(entries={"img1": DatasetEntryMetadata(caption="")})
        restored = Dataset.from_dict(dataset.to_dict())
        self.assertIn("img1", restored.entries)
        self.assertEqual(restored.entries["img1"].caption, "")
        self.assertNotIn("img2", restored.entries)


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
        # characters_page, datasets_page) + DatasetManager's own internal
        # reset subscription = 5, on EACH bus independently. Mission 137:
        # CharacterManager no longer subscribes anything to
        # WORKSPACE_CREATED — Mission 026's principal-Character
        # auto-creation is now an explicit call made by
        # workspace_lifecycle.create_workspace_with_default_character(),
        # and active_character_id's reset-on-workspace-switch no longer
        # needs to react to CREATED specifically (see
        # CharacterManager.__init__'s own comment for why).
        self.assertEqual(len(event_bus_1._subscribers[WORKSPACE_CREATED]), 5)
        self.assertEqual(len(event_bus_2._subscribers[WORKSPACE_CREATED]), 5)
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


class DatasetManagerCaptionTest(unittest.TestCase):
    """
    Mission 098: DatasetManager.set_caption()/entries cleanup on
    remove_images()/sidecar caption detection in add_images() — all
    additive to Dataset.images, never restructuring it. See
    MISSION_098.md sections 3/4.
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
        self.dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(self.dataset.dataset_id)

        source = Path(self.tmp_dir) / "photo.png"
        source.write_bytes(b"fake-png-bytes")
        self.dataset_manager.add_images([str(source)])
        self.image_id = self.dataset_manager.active_dataset.images[0].image_id

    def _external(self, name, content=b"fake-bytes"):
        path = self.external_dir / name
        path.write_bytes(content)
        return str(path)

    # --- set_caption() ---

    def test_set_caption_creates_a_new_entry(self):
        changed = self.dataset_manager.set_caption(self.image_id, "a girl smiling")

        self.assertTrue(changed)
        self.assertEqual(self.dataset.entries[self.image_id].caption, "a girl smiling")

    def test_set_caption_identical_value_is_idempotent(self):
        self.dataset_manager.set_caption(self.image_id, "a girl smiling")

        with patch.object(self.workspace_manager, "save", wraps=self.workspace_manager.save) as save_spy:
            changed = self.dataset_manager.set_caption(self.image_id, "a girl smiling")
            self.assertFalse(changed)
            save_spy.assert_not_called()

    def test_set_caption_with_empty_string_creates_an_explicit_entry(self):
        # An explicitly empty caption is legitimate and distinct from no
        # entry at all — it must never be treated as "nothing to save".
        changed = self.dataset_manager.set_caption(self.image_id, "")

        self.assertTrue(changed)
        self.assertIn(self.image_id, self.dataset.entries)
        self.assertEqual(self.dataset.entries[self.image_id].caption, "")

    def test_set_caption_without_active_dataset_returns_false(self):
        other_workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        other_character_manager = CharacterManager(other_workspace_manager, event_bus=self.event_bus)
        other_dataset_manager = DatasetManager(
            other_character_manager, other_workspace_manager, event_bus=self.event_bus
        )
        other_folder = Path(self.tmp_dir) / "OtherProject"
        other_workspace_manager.create(other_folder)

        self.assertFalse(other_dataset_manager.set_caption(self.image_id, "anything"))

    def test_set_caption_save_failure_rolls_back_a_new_entry(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.set_caption(self.image_id, "a girl smiling")

        self.assertNotIn(self.image_id, self.dataset.entries)

    def test_set_caption_save_failure_restores_previous_value(self):
        self.dataset_manager.set_caption(self.image_id, "first caption")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.set_caption(self.image_id, "second caption")

        self.assertEqual(self.dataset.entries[self.image_id].caption, "first caption")

    # --- remove_images() cleanup ---

    def test_remove_images_deletes_the_entry_for_the_removed_image(self):
        self.dataset_manager.set_caption(self.image_id, "a girl smiling")
        internal_path = self.dataset.images[0].file_path

        self.dataset_manager.remove_images([internal_path])

        self.assertEqual(self.dataset.entries, {})

    def test_remove_images_never_deletes_entries_of_images_that_stay(self):
        second_source = self._external("second.png")
        self.dataset_manager.add_images([second_source])
        first_path = self.dataset.images[0].file_path
        self.dataset_manager.set_caption(self.image_id, "first caption")
        self.dataset_manager.set_caption(self.dataset.images[-1].image_id, "second caption")

        self.dataset_manager.remove_images([first_path])

        self.assertNotIn(self.image_id, self.dataset.entries)
        self.assertEqual(len(self.dataset.entries), 1)

    def test_remove_images_save_failure_restores_entries_exactly(self):
        self.dataset_manager.set_caption(self.image_id, "a girl smiling")
        internal_path = self.dataset.images[0].file_path

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.remove_images([internal_path])

        self.assertEqual(self.dataset.entries[self.image_id].caption, "a girl smiling")

    # --- add_images(detect_caption_sidecars=...) ---

    def test_sidecar_with_text_becomes_the_new_entry_caption(self):
        image_path = self._external("with_caption.png")
        Path(image_path).with_suffix(".txt").write_text("a red car", encoding="utf-8")

        self.dataset_manager.add_images([image_path], detect_caption_sidecars=True)

        new_image = self.dataset.images[-1]
        self.assertEqual(self.dataset.entries[new_image.image_id].caption, "a red car")

    def test_sidecar_present_but_empty_still_creates_an_explicit_entry(self):
        image_path = self._external("empty_caption.png")
        Path(image_path).with_suffix(".txt").write_text("", encoding="utf-8")

        self.dataset_manager.add_images([image_path], detect_caption_sidecars=True)

        new_image = self.dataset.images[-1]
        self.assertIn(new_image.image_id, self.dataset.entries)
        self.assertEqual(self.dataset.entries[new_image.image_id].caption, "")

    def test_absent_sidecar_creates_no_entry_at_all(self):
        image_path = self._external("no_caption.png")

        self.dataset_manager.add_images([image_path], detect_caption_sidecars=True)

        new_image = self.dataset.images[-1]
        self.assertNotIn(new_image.image_id, self.dataset.entries)

    def test_sidecar_txt_itself_is_never_added_as_a_dataset_image(self):
        image_path = self._external("photo2.png")
        Path(image_path).with_suffix(".txt").write_text("caption", encoding="utf-8")

        self.dataset_manager.add_images([image_path], detect_caption_sidecars=True)

        self.assertEqual(
            [Path(image.file_path).suffix for image in self.dataset.images],
            [".png", ".png"],
        )

    def test_sidecar_detection_disabled_by_default(self):
        # add_images_from_gallery() never passes detect_caption_sidecars
        # — default must stay False so a future caller never triggers it
        # implicitly.
        image_path = self._external("gallery_style.png")
        Path(image_path).with_suffix(".txt").write_text("should be ignored", encoding="utf-8")

        self.dataset_manager.add_images([image_path])

        new_image = self.dataset.images[-1]
        self.assertNotIn(new_image.image_id, self.dataset.entries)

    def test_sidecar_save_failure_rolls_back_new_entries_too(self):
        image_path = self._external("rollback.png")
        Path(image_path).with_suffix(".txt").write_text("a caption", encoding="utf-8")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.add_images([image_path], detect_caption_sidecars=True)

        self.assertEqual(self.dataset.entries, {})

    def test_sidecar_inspection_oserror_is_tolerated_like_absent_sidecar_and_batch_continues(self):
        """
        Mission 164: sidecar.is_file() itself can raise OSError (an
        antivirus lock, a disconnected network share) instead of
        cleanly returning False. Before this mission, that OSError
        escaped add_images() uncaught, aborting the whole batch mid-loop
        and leaving every already-copied image (including the one whose
        sidecar failed) orphaned on disk, unreferenced by dataset.images
        and never persisted. The patch below targets only the third
        image's sidecar path — delegating every other Path.is_file()
        call (the other three sidecars) to the real implementation —
        and records every inspected path to prove the faulty one was
        genuinely reached, not merely bypassed.
        """
        image_paths = [self._external(f"batch_{i}.png") for i in range(1, 5)]
        for i, image_path in enumerate(image_paths, start=1):
            if i != 3:
                Path(image_path).with_suffix(".txt").write_text(
                    f"caption {i}", encoding="utf-8"
                )
        faulty_sidecar = Path(image_paths[2]).with_suffix(".txt")

        original_is_file = Path.is_file
        inspected_paths = []

        def selective_is_file(path_self):
            inspected_paths.append(path_self)
            if path_self == faulty_sidecar:
                raise OSError("simulated antivirus lock")
            return original_is_file(path_self)

        baseline_count = len(self.dataset.images)
        source_bytes_before = [Path(p).read_bytes() for p in image_paths]

        with patch.object(Path, "is_file", selective_is_file):
            result = self.dataset_manager.add_images(
                image_paths, detect_caption_sidecars=True
            )

        # The faulty sidecar was genuinely inspected, never bypassed.
        self.assertIn(faulty_sidecar, inspected_paths)

        self.assertEqual(result.added, 4)
        self.assertEqual(result.failed, [])
        self.assertEqual(result.skipped, [])

        new_images = self.dataset.images[baseline_count:]
        self.assertEqual(len(new_images), 4)

        # All four copies exist on disk, referenced, and no orphan
        # beyond what this call actually created (exactly 4 new files,
        # plus the one already present from setUp()).
        destination_folder = (
            self.workspace_manager.current_workspace.root
            / "datasets" / self.dataset.dataset_id
        )
        self.assertEqual(len(list(destination_folder.iterdir())), baseline_count + 4)
        for image in new_images:
            self.assertTrue(Path(image.file_path).is_file())

        # Third image: no caption entry — identical outcome to an
        # absent sidecar, never an abandoned/skipped image.
        third_image = new_images[2]
        self.assertNotIn(third_image.image_id, self.dataset.entries)

        # The other three keep their valid captions.
        for index in (0, 1, 3):
            image = new_images[index]
            self.assertEqual(
                self.dataset.entries[image.image_id].caption,
                f"caption {index + 1}",
            )

        # Original source files untouched — copy_into_workspace() only
        # ever copies, never moves/modifies the source.
        for path, original_bytes in zip(image_paths, source_bytes_before):
            self.assertTrue(Path(path).exists())
            self.assertEqual(Path(path).read_bytes(), original_bytes)

        # Persisted state survives a real reopen from disk, not just
        # the in-memory Domain object.
        reopened_event_bus = EventBus()
        reopened_workspace_manager = WorkspaceManager(event_bus=reopened_event_bus)
        reopened_character_manager = CharacterManager(
            reopened_workspace_manager, event_bus=reopened_event_bus
        )
        reopened_dataset_manager = DatasetManager(
            reopened_character_manager, reopened_workspace_manager, event_bus=reopened_event_bus
        )
        reopened_workspace_manager.open(self.folder)
        reopened_dataset = reopened_character_manager.principal_character.datasets[0]

        self.assertEqual(len(reopened_dataset.images), baseline_count + 4)
        reopened_new_images = reopened_dataset.images[baseline_count:]
        third_reopened_image = reopened_new_images[2]
        self.assertNotIn(third_reopened_image.image_id, reopened_dataset.entries)
        for index in (0, 1, 3):
            image = reopened_new_images[index]
            self.assertEqual(
                reopened_dataset.entries[image.image_id].caption,
                f"caption {index + 1}",
            )
        # Constructed only to exercise a real reopen; never used to
        # mutate anything further.
        del reopened_dataset_manager

    def test_sidecar_read_oserror_is_tolerated_and_image_still_imported(self):
        """
        Mission 164: explicit coverage for the OSError branch of
        read_text()'s own pre-existing except clause (production
        behavior unchanged by this mission) — the sidecar genuinely
        exists (is_file() still returns True normally), only reading it
        fails. The patch below targets only this image's own sidecar
        path, delegating every other Path.read_text() call to the real
        implementation, and records every attempted read to prove the
        faulty one was genuinely reached, not merely bypassed.
        """
        image_path = self._external("read_oserror.png")
        sidecar = Path(image_path).with_suffix(".txt")
        sidecar.write_text("unreachable caption", encoding="utf-8")

        baseline_ids = {image.image_id for image in self.dataset.images}
        baseline_count = len(self.dataset.images)

        original_read_text = Path.read_text
        attempted_reads = []

        def selective_read_text(path_self, *args, **kwargs):
            attempted_reads.append(path_self)
            if path_self == sidecar:
                raise OSError("simulated read failure")
            return original_read_text(path_self, *args, **kwargs)

        with patch.object(Path, "read_text", selective_read_text):
            result = self.dataset_manager.add_images(
                [image_path], detect_caption_sidecars=True
            )

        # The faulty sidecar was genuinely read, never bypassed.
        self.assertIn(sidecar, attempted_reads)

        self.assertEqual(result.added, 1)
        self.assertEqual(result.failed, [])
        self.assertEqual(result.skipped, [])
        self.assertEqual(len(self.dataset.images), baseline_count + 1)

        new_image = self.dataset.images[-1]
        self.assertNotIn(new_image.image_id, baseline_ids)
        self.assertTrue(Path(new_image.file_path).is_file())
        self.assertNotIn(new_image.image_id, self.dataset.entries)

    def test_sidecar_read_unicode_decode_error_is_tolerated_and_image_still_imported(self):
        """
        Mission 164: explicit coverage for the UnicodeDecodeError branch
        of read_text()'s own pre-existing except clause (production
        behavior unchanged by this mission) — a real non-UTF-8 sidecar,
        no mock needed to trigger the real decode failure.
        """
        image_path = self._external("read_badencoding.png")
        sidecar = Path(image_path).with_suffix(".txt")
        sidecar.write_bytes("caption en français".encode("utf-16"))

        baseline_ids = {image.image_id for image in self.dataset.images}
        baseline_count = len(self.dataset.images)

        result = self.dataset_manager.add_images(
            [image_path], detect_caption_sidecars=True
        )

        self.assertEqual(result.added, 1)
        self.assertEqual(result.failed, [])
        self.assertEqual(result.skipped, [])
        self.assertEqual(len(self.dataset.images), baseline_count + 1)

        new_image = self.dataset.images[-1]
        self.assertNotIn(new_image.image_id, baseline_ids)
        self.assertTrue(Path(new_image.file_path).is_file())
        self.assertNotIn(new_image.image_id, self.dataset.entries)

    def test_sidecar_inspection_oserror_tolerated_then_save_failure_rolls_back_via_m067(self):
        """
        Mission 164: the is_file() tolerance above must never interfere
        with the pre-existing Mission 067 rollback — if tolerating the
        sidecar error lets the batch reach a final save() that then
        itself fails, every new image/entry/copy created during this
        call (including the one whose sidecar failed) must still be
        rolled back exactly as Mission 067 already guarantees for any
        other add_images() failure.
        """
        image_paths = [self._external(f"rollback_batch_{i}.png") for i in range(1, 3)]
        Path(image_paths[0]).with_suffix(".txt").write_text("kept caption", encoding="utf-8")
        faulty_sidecar = Path(image_paths[1]).with_suffix(".txt")

        original_is_file = Path.is_file

        def selective_is_file(path_self):
            if path_self == faulty_sidecar:
                raise OSError("simulated antivirus lock")
            return original_is_file(path_self)

        baseline_images = list(self.dataset.images)
        baseline_entries = dict(self.dataset.entries)
        destination_folder = (
            self.workspace_manager.current_workspace.root
            / "datasets" / self.dataset.dataset_id
        )
        baseline_files = set(destination_folder.iterdir())
        source_bytes_before = [Path(p).read_bytes() for p in image_paths]

        with patch.object(Path, "is_file", selective_is_file), \
                patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.dataset_manager.add_images(image_paths, detect_caption_sidecars=True)

        # Domain fully restored — the tolerated sidecar error never
        # partially survives the later, unrelated save() failure.
        self.assertEqual(self.dataset.images, baseline_images)
        self.assertEqual(self.dataset.entries, baseline_entries)

        # Both new copies (including the one whose sidecar failed)
        # cleaned up by the existing Mission 067 mechanism — nothing
        # beyond the pre-existing file remains.
        self.assertEqual(set(destination_folder.iterdir()), baseline_files)

        # Original sources preserved.
        for path, original_bytes in zip(image_paths, source_bytes_before):
            self.assertTrue(Path(path).exists())
            self.assertEqual(Path(path).read_bytes(), original_bytes)


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
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)
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
        # Mission 137: WorkspaceManager.create() alone no longer
        # auto-creates a Character, so this state is reached directly.
        workspace_manager, character_manager, _, datasets_page = self._wire()
        workspace_manager.create(self.folder)

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
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings"
        )
        lora_library_manager = MagicMock()
        lora_library_manager.get.return_value = None
        training_page = TrainingPage(
            training_manager, dataset_manager, workspace_manager, application_settings_manager,
            lora_library_manager,
        )

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


class DatasetsPageNameDraftProtectionTest(unittest.TestCase):
    """
    Mission 165: DatasetsPage.name_edit is a commit-on-blur field
    (editingFinished only, no Save button, no dirty tracking) —
    update_datasets() used to overwrite it unconditionally on every
    WORKSPACE_SAVED/RENAMED/CHARACTER_CREATED/DATASET_* event, silently
    discarding an in-progress, not-yet-committed rename whenever an
    unrelated event fired elsewhere in the same Workspace. Fixed by
    tracking the identity/value name_edit was last loaded for
    (_name_editor_owner_id/_name_editor_loaded_value) and a reentrancy
    guard (_renaming_in_progress) — see rename_dataset()/
    update_datasets()/_reload_name_editor()/_has_unsaved_name_draft()/
    reset_for_context_change(). Commit-on-blur itself is unchanged.

    _wire() reproduces the exact subscriptions main_window.py registers
    for DatasetsPage — notably WORKSPACE_RENAMED and CHARACTER_CREATED
    (absent from this file's shared WORKSPACE_EVENTS/CHARACTER_EVENTS
    tuples) and the 5 context-reset events routed to
    reset_for_context_change() rather than update_datasets() — and
    constructs DatasetManager before the page, as MainWindow does, so
    the Manager's own context-reset subscriptions run first. Real QTest
    key/focus/mouse events are used wherever a scenario hinges on real
    Qt signal ordering. Caption-draft interactions live in
    test_datasets_page.py (DatasetsPageNameAndCaptionDraftTest).
    """

    def setUp(self):
        # Armed first, hence stopped last (cleanups run in reverse
        # registration order): any real QMessageBox that appears — e.g.
        # from a rename fired by a widget closing — is closed on the next
        # tick and turned into a clean UnexpectedDialogError instead of
        # waiting for a human click.
        self.dialog_guard = start_dialog_guard()
        self.addCleanup(stop_dialog_guard, self.dialog_guard)

        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "DatasetNameDraftProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        datasets_page = DatasetsPage(dataset_manager, workspace_manager)

        for event_name in (
            WORKSPACE_SAVED, WORKSPACE_RENAMED, CHARACTER_CREATED,
            DATASET_CREATED, DATASET_SELECTED, DATASET_DELETED,
        ):
            event_bus.subscribe(event_name, datasets_page.update_datasets)
        for event_name in (
            WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED,
            CHARACTER_SELECTED, CHARACTER_DELETED,
        ):
            event_bus.subscribe(event_name, datasets_page.reset_for_context_change)

        return event_bus, workspace_manager, character_manager, dataset_manager, datasets_page

    def _open_with(self, workspace_manager, character_manager, dataset_manager, *names, folder=None):
        create_workspace_with_default_character(
            workspace_manager, character_manager, folder or self.folder
        )
        datasets = [dataset_manager.create(name) for name in names]
        dataset_manager.select(datasets[0].dataset_id)
        return datasets

    def _show_and_focus(self, page):
        page.resize(500, 700)
        page.show()
        self.addCleanup(page.close)
        QTest.qWaitForWindowExposed(page)
        page.name_edit.setFocus()
        QTest.qWait(10)

    @staticmethod
    def _count_calls(obj, attribute_name):
        calls = []
        original = getattr(obj, attribute_name)

        def counting(*args, **kwargs):
            calls.append(args)
            return original(*args, **kwargs)

        setattr(obj, attribute_name, counting)
        return calls

    @staticmethod
    def _track_subscription(event_bus, event_name, callback, probe=None):
        """
        Swaps `callback`'s entry inside the EventBus's own subscriber
        list (not an instance attribute, which an already-captured
        subscription would not see) for a recording wrapper — proves
        this exact event actually invoked it. `probe`, when given, is
        evaluated at call time and recorded instead of the payload.
        """
        calls = []

        def tracking(payload=None):
            calls.append(probe() if probe is not None else payload)
            callback(payload)

        event_bus._subscribers[event_name] = [
            tracking if subscriber == callback else subscriber
            for subscriber in event_bus._subscribers[event_name]
        ]
        return calls

    @staticmethod
    def _spy_reload(manager_pair, page):
        """
        Records, at every _reload_name_editor() call, which Dataset the
        Manager reports as active and whether a Workspace is open — the
        Domain context a reset actually ran against.
        """
        dataset_manager, workspace_manager = manager_pair
        contexts = []
        # Tolerates the method's absence: a spy that raised before the
        # scenario's own assertions would hide *why* the behavior fails.
        original = getattr(page, "_reload_name_editor", None)

        def spy():
            contexts.append((dataset_manager.active_dataset_id, workspace_manager.opened))
            return original() if original is not None else None

        page._reload_name_editor = spy
        return contexts

    @staticmethod
    def _item_for(page, dataset_id):
        return next(
            page.dataset_list.item(i)
            for i in range(page.dataset_list.count())
            if page.dataset_list.item(i).data(Qt.UserRole) == dataset_id
        )

    # --- Unrelated events never overwrite a real draft ---

    def test_unrelated_workspace_saved_causes_no_rename_and_preserves_a_real_draft(self):

        _, workspace_manager, character_manager, dataset_manager, page = self._wire()
        (alpha,) = self._open_with(workspace_manager, character_manager, dataset_manager, "Alpha")

        self._show_and_focus(page)
        QTest.keyClicks(page.name_edit, " EDIT")
        self.assertEqual(page.name_edit.text(), "Alpha EDIT")

        update_name_calls = self._count_calls(dataset_manager, "update_name")
        save_calls = self._count_calls(workspace_manager, "save")
        reload_contexts = self._spy_reload((dataset_manager, workspace_manager), page)

        # Something else in the same Workspace persists successfully —
        # e.g. a background Training job's terminal state — with no
        # relation to this Dataset at all. workspace_manager.save() is
        # itself a persistence: the assertion is that the *refresh* it
        # triggers causes no rename and no further save.
        workspace_manager.save()

        self.assertEqual(len(save_calls), 1)
        self.assertEqual(update_name_calls, [])
        self.assertEqual(reload_contexts, [])
        self.assertEqual(page.name_edit.text(), "Alpha EDIT")
        self.assertEqual(alpha.name, "Alpha")

    def test_repeated_events_and_workspace_renamed_preserve_the_draft(self):

        event_bus, workspace_manager, character_manager, dataset_manager, page = self._wire()
        (alpha,) = self._open_with(workspace_manager, character_manager, dataset_manager, "Alpha")

        self._show_and_focus(page)
        QTest.keyClicks(page.name_edit, " EDIT")

        workspace_manager.save()
        workspace_manager.save()
        self.assertEqual(page.name_edit.text(), "Alpha EDIT")

        # WorkspaceManager.rename() publishes only WORKSPACE_RENAMED,
        # never WORKSPACE_SAVED — so no subsequent save() can mask a
        # missing RENAMED subscription. The callback is swapped inside
        # the EventBus's own subscriber list to prove this exact event
        # actually reached update_datasets().
        rename_event_calls = self._track_subscription(
            event_bus, WORKSPACE_RENAMED, page.update_datasets
        )

        workspace_manager.rename("RenamedProject")

        self.assertEqual(len(rename_event_calls), 1)
        self.assertEqual(page.name_edit.text(), "Alpha EDIT")
        self.assertEqual(alpha.name, "Alpha")

    def test_character_created_dataset_created_and_sort_change_preserve_the_draft(self):

        _, workspace_manager, character_manager, dataset_manager, page = self._wire()
        (alpha,) = self._open_with(workspace_manager, character_manager, dataset_manager, "Alpha")

        self._show_and_focus(page)
        QTest.keyClicks(page.name_edit, " EDIT")

        character_manager.create("Another")
        self.assertEqual(page.name_edit.text(), "Alpha EDIT")

        # create() publishes DATASET_CREATED without ever selecting the
        # new Dataset — the active identity is unchanged.
        dataset_manager.create("Gamma")
        self.assertEqual(page.name_edit.text(), "Alpha EDIT")

        page.sort_combo.setCurrentIndex(1)
        self.assertEqual(page.name_edit.text(), "Alpha EDIT")

        self.assertEqual(alpha.name, "Alpha")

    def test_focused_clean_editor_reflects_a_domain_update(self):

        _, workspace_manager, character_manager, dataset_manager, page = self._wire()
        self._open_with(workspace_manager, character_manager, dataset_manager, "Alpha")

        self._show_and_focus(page)
        # No typing: name_edit still matches the loaded value exactly.
        self.assertEqual(page.name_edit.text(), "Alpha")

        # The Domain value changes via a path other than this widget's
        # own commit flow — with nothing locally unsaved, the refresh
        # must still apply.
        dataset_manager.update_name("Alpha Renamed Elsewhere")

        self.assertEqual(page.name_edit.text(), "Alpha Renamed Elsewhere")

    def test_return_to_original_name_before_commit_is_not_persisted(self):

        _, workspace_manager, character_manager, dataset_manager, page = self._wire()
        (alpha,) = self._open_with(workspace_manager, character_manager, dataset_manager, "Alpha")

        self._show_and_focus(page)
        QTest.keyClicks(page.name_edit, " TMP")
        for _ in range(4):
            QTest.keyClick(page.name_edit, Qt.Key_Backspace)
        self.assertEqual(page.name_edit.text(), "Alpha")

        save_calls = self._count_calls(workspace_manager, "save")

        QTest.keyClick(page.name_edit, Qt.Key_Return)

        self.assertEqual(len(save_calls), 0)
        self.assertEqual(alpha.name, "Alpha")

        # Back on the loaded value, the editor is no longer a draft: a
        # later Domain update applies again.
        dataset_manager.update_name("Alpha Elsewhere")
        self.assertEqual(page.name_edit.text(), "Alpha Elsewhere")

    # --- Commit paths ---

    def test_synchronous_success_persists_exactly_once_and_reconciles_the_editor(self):

        event_bus, workspace_manager, character_manager, dataset_manager, page = self._wire()
        (alpha,) = self._open_with(workspace_manager, character_manager, dataset_manager, "Alpha")

        update_name_calls = self._count_calls(dataset_manager, "update_name")
        save_calls = self._count_calls(workspace_manager, "save")
        # The synchronous WORKSPACE_SAVED published from inside save()
        # must reach update_datasets() while the reentrancy guard is
        # still held — recorded at call time.
        saved_callbacks = self._track_subscription(
            event_bus, WORKSPACE_SAVED, page.update_datasets,
            probe=lambda: page._renaming_in_progress,
        )

        self._show_and_focus(page)
        QTest.keyClicks(page.name_edit, " RENAMED")
        QTest.keyClick(page.name_edit, Qt.Key_Return)

        self.assertEqual(len(update_name_calls), 1)
        self.assertEqual(len(save_calls), 1)
        self.assertEqual(saved_callbacks, [True])
        self.assertEqual(alpha.name, "Alpha RENAMED")
        self.assertEqual(page.name_edit.text(), "Alpha RENAMED")
        self.assertEqual(page._name_editor_loaded_value, "Alpha RENAMED")
        self.assertEqual(page._name_editor_owner_id, alpha.dataset_id)
        self.assertIn("Alpha RENAMED", page.dataset_list.currentItem().text())
        self.assertFalse(page._renaming_in_progress)

    def test_enter_then_real_focus_loss_persists_only_once(self):

        _, workspace_manager, character_manager, dataset_manager, page = self._wire()
        (alpha,) = self._open_with(workspace_manager, character_manager, dataset_manager, "Alpha")

        save_calls = self._count_calls(workspace_manager, "save")

        self._show_and_focus(page)
        QTest.keyClicks(page.name_edit, " RENAMED")
        QTest.keyClick(page.name_edit, Qt.Key_Return)
        # A real, separate focus transfer after the Enter-triggered commit.
        page.dataset_list.setFocus()
        QTest.qWait(10)

        self.assertEqual(len(save_calls), 1)
        self.assertEqual(alpha.name, "Alpha RENAMED")

    def test_failure_restores_canonical_value_with_focus(self):

        _, workspace_manager, character_manager, dataset_manager, page = self._wire()
        (alpha,) = self._open_with(workspace_manager, character_manager, dataset_manager, "Alpha")

        self._show_and_focus(page)
        QTest.keyClicks(page.name_edit, " WILL_FAIL")
        self.assertTrue(page.name_edit.hasFocus())

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.datasets_page.QMessageBox.critical") as critical_mock:
            QTest.keyClick(page.name_edit, Qt.Key_Return)

        self.assertEqual(critical_mock.call_count, 1)
        self.assertEqual(alpha.name, "Alpha")
        self.assertEqual(page.name_edit.text(), "Alpha")
        self.assertEqual(page._name_editor_loaded_value, "Alpha")
        self.assertIn("Alpha", page.dataset_list.currentItem().text())
        self.assertNotIn("WILL_FAIL", page.dataset_list.currentItem().text())
        self.assertFalse(page._renaming_in_progress)

    def test_failure_restores_canonical_value_without_any_focus(self):

        _, workspace_manager, character_manager, dataset_manager, page = self._wire()
        (alpha,) = self._open_with(workspace_manager, character_manager, dataset_manager, "Alpha")

        # Page never shown, no widget ever focused: restoration must not
        # depend on focus state at all.
        self.assertFalse(page.name_edit.hasFocus())
        page.name_edit.setText("Alpha WILL_FAIL")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.datasets_page.QMessageBox.critical") as critical_mock:
            page.name_edit.editingFinished.emit()

        self.assertEqual(critical_mock.call_count, 1)
        self.assertEqual(alpha.name, "Alpha")
        self.assertEqual(page.name_edit.text(), "Alpha")
        self.assertFalse(page._renaming_in_progress)

        # A retry is a genuine new attempt that actually persists.
        page.name_edit.setText("Alpha RETRY")
        page.name_edit.editingFinished.emit()
        self.assertEqual(alpha.name, "Alpha RETRY")
        self.assertEqual(page.name_edit.text(), "Alpha RETRY")

    # --- Identity and existence at the write point ---

    def test_identity_discordance_at_the_write_point_refuses_the_write(self):
        """
        Defense-in-depth: constructs a real discordance at the exact
        point rename_dataset() reads it — the editor still owns Alpha's
        draft, but the Manager's active object is Beta, with no
        intermediate refresh having reconciled it — and proves the guard
        in rename_dataset() itself, not merely the observed Qt click
        ordering, is what prevents a mis-targeted write. Calling
        dataset_manager.select(beta.dataset_id) here would publish
        DATASET_SELECTED, which update_datasets() is itself subscribed to
        — that reconciling refresh would reload the editor onto Beta
        *before* editingFinished ever fires, leaving no discordance left
        to catch and making the test pass for the wrong reason. Setting
        active_dataset_id directly bypasses that event entirely.
        """

        _, workspace_manager, character_manager, dataset_manager, page = self._wire()
        alpha, beta = self._open_with(
            workspace_manager, character_manager, dataset_manager, "Alpha", "Beta"
        )

        page.name_edit.setText("Alpha EDIT")

        # Controlled, direct construction of the exact discordant state —
        # no DATASET_SELECTED event, no reconciling refresh.
        dataset_manager.active_dataset_id = beta.dataset_id

        # State verified BEFORE the direct call under test.
        self.assertEqual(page._name_editor_owner_id, alpha.dataset_id)
        self.assertEqual(page.name_edit.text(), "Alpha EDIT")
        self.assertEqual(dataset_manager.active_dataset_id, beta.dataset_id)
        self.assertIsNotNone(dataset_manager.active_dataset)
        self.assertNotEqual(page._name_editor_owner_id, dataset_manager.active_dataset_id)

        update_name_calls = self._count_calls(dataset_manager, "update_name")
        save_calls = self._count_calls(workspace_manager, "save")

        # Called directly, not via .emit() — a direct call is the only
        # way a raised exception would actually surface in this test.
        page.rename_dataset()

        self.assertEqual(len(update_name_calls), 0)
        self.assertEqual(len(save_calls), 0)
        self.assertEqual(alpha.name, "Alpha")
        self.assertEqual(beta.name, "Beta")
        self.assertEqual(page.name_edit.text(), "Beta")
        self.assertEqual(page._name_editor_owner_id, beta.dataset_id)

    def test_no_active_dataset_is_a_no_op_and_editor_stays_empty(self):

        _, workspace_manager, character_manager, dataset_manager, page = self._wire()
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)
        dataset = dataset_manager.create("Alpha")  # created, never selected

        self.assertIsNone(dataset_manager.active_dataset)
        self.assertIsNone(page._name_editor_owner_id)
        self.assertEqual(page.name_edit.text(), "")

        update_name_calls = self._count_calls(dataset_manager, "update_name")

        page.name_edit.setText("Whatever")
        page.name_edit.editingFinished.emit()

        self.assertEqual(update_name_calls, [])
        self.assertEqual(dataset.name, "Alpha")
        # No active object: rename_dataset() takes the reload-only
        # branch, resetting the editor rather than persisting stray text.
        self.assertEqual(page.name_edit.text(), "")

    def test_active_id_without_an_existing_object_is_never_written(self):

        _, workspace_manager, character_manager, dataset_manager, page = self._wire()
        (alpha,) = self._open_with(workspace_manager, character_manager, dataset_manager, "Alpha")

        page.name_edit.setText("Alpha EDIT")
        # An id is present but no object resolves from it: existence is
        # checked on the object, never inferred from the id alone.
        dataset_manager.active_dataset_id = "ghost-id"
        self.assertIsNone(dataset_manager.active_dataset)

        update_name_calls = self._count_calls(dataset_manager, "update_name")
        page.rename_dataset()

        self.assertEqual(update_name_calls, [])
        self.assertEqual(alpha.name, "Alpha")
        self.assertEqual(page.name_edit.text(), "")
        self.assertIsNone(page._name_editor_owner_id)

    def test_dataset_selected_programmatically_reloads_the_editor_without_cross_write(self):

        _, workspace_manager, character_manager, dataset_manager, page = self._wire()
        alpha, beta = self._open_with(
            workspace_manager, character_manager, dataset_manager, "Alpha", "Beta"
        )

        page.name_edit.setText("Alpha EDIT")  # an uncommitted draft for Alpha

        # A genuine identity change published as DATASET_SELECTED (no
        # focus loss ever occurred, so editingFinished never committed
        # the draft): the editor reloads for Beta — the draft is never
        # transferred to, or written under, either Dataset.
        dataset_manager.select(beta.dataset_id)

        self.assertEqual(page.name_edit.text(), "Beta")
        self.assertEqual(page._name_editor_owner_id, beta.dataset_id)
        self.assertEqual(alpha.name, "Alpha")
        self.assertEqual(beta.name, "Beta")

    def test_dataset_deleted_resets_the_editor(self):

        _, workspace_manager, character_manager, dataset_manager, page = self._wire()
        (alpha,) = self._open_with(workspace_manager, character_manager, dataset_manager, "Alpha")

        page.name_edit.setText("Alpha EDIT")
        dataset_manager.delete(alpha.dataset_id)

        self.assertIsNone(dataset_manager.active_dataset)
        self.assertEqual(page.name_edit.text(), "")
        self.assertIsNone(page._name_editor_owner_id)

    def test_identity_change_via_real_click_never_transfers_or_misrenames_draft(self):

        _, workspace_manager, character_manager, dataset_manager, page = self._wire()
        alpha, beta = self._open_with(
            workspace_manager, character_manager, dataset_manager, "Alpha", "Beta"
        )

        self._show_and_focus(page)
        QTest.keyClicks(page.name_edit, " EDIT")

        rect = page.dataset_list.visualItemRect(self._item_for(page, beta.dataset_id))
        QTest.mouseClick(page.dataset_list.viewport(), Qt.LeftButton, pos=rect.center())
        QTest.qWait(20)

        # The real focus loss committed the draft for the Dataset that
        # was active when it happened — never for Beta.
        self.assertEqual(alpha.name, "Alpha EDIT")
        self.assertEqual(beta.name, "Beta")
        self.assertEqual(dataset_manager.active_dataset_id, beta.dataset_id)
        self.assertEqual(page.name_edit.text(), "Beta")
        self.assertEqual(page._name_editor_owner_id, beta.dataset_id)

    # --- Reentrancy guard ---

    def test_reentrant_rename_during_error_dialog_is_ignored(self):

        _, workspace_manager, character_manager, dataset_manager, page = self._wire()
        (alpha,) = self._open_with(workspace_manager, character_manager, dataset_manager, "Alpha")

        page.name_edit.setText("Alpha WILL_FAIL")

        update_name_calls = self._count_calls(dataset_manager, "update_name")
        manager_save_attempts = self._count_calls(workspace_manager, "save")

        def reentrant_critical(parent, title, text):
            # Simulates a second editingFinished firing while the real
            # dialog's nested event loop would still be running.
            page.rename_dataset()

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")) as storage_save_mock, \
                patch("src.ui.pages.datasets_page.QMessageBox.critical", side_effect=reentrant_critical) as critical_mock:
            page.name_edit.editingFinished.emit()

        # Counted separately: Manager call, persistence attempts (at the
        # WorkspaceManager and at the Storage level), and dialogs.
        self.assertEqual(len(update_name_calls), 1)
        self.assertEqual(len(manager_save_attempts), 1)
        self.assertEqual(storage_save_mock.call_count, 1)
        self.assertEqual(critical_mock.call_count, 1)
        self.assertEqual(alpha.name, "Alpha")
        self.assertEqual(page.name_edit.text(), "Alpha")
        self.assertFalse(page._renaming_in_progress)

    def test_reentrancy_guard_released_even_if_reconciliation_fails(self):

        _, workspace_manager, character_manager, dataset_manager, page = self._wire()
        self._open_with(workspace_manager, character_manager, dataset_manager, "Alpha")

        page.name_edit.setText("Alpha RENAMED")

        def broken_reload():
            raise RuntimeError("simulated reconciliation failure")

        page._reload_name_editor = broken_reload

        # Called directly (not via .emit()): PySide6 does not propagate a
        # slot's exception back through signal emission in this
        # environment — a direct call is the only way to observe it.
        with self.assertRaises(RuntimeError):
            page.rename_dataset()

        self.assertFalse(page._renaming_in_progress)

    def test_reentrancy_guard_released_when_reconciliation_fails_after_a_save_failure(self):

        _, workspace_manager, character_manager, dataset_manager, page = self._wire()
        (alpha,) = self._open_with(workspace_manager, character_manager, dataset_manager, "Alpha")

        page.name_edit.setText("Alpha WILL_FAIL")

        def broken_reload():
            raise RuntimeError("simulated reconciliation failure")

        page._reload_name_editor = broken_reload

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.datasets_page.QMessageBox.critical") as critical_mock:
            with self.assertRaises(RuntimeError):
                page.rename_dataset()

        self.assertEqual(critical_mock.call_count, 1)
        self.assertEqual(alpha.name, "Alpha")
        self.assertFalse(page._renaming_in_progress)

    # --- Context resets (forced) ---

    def test_workspace_closed_with_a_focused_draft_resets_the_editor_without_writing(self):

        event_bus, workspace_manager, character_manager, dataset_manager, page = self._wire()
        (alpha,) = self._open_with(workspace_manager, character_manager, dataset_manager, "Alpha")

        self._show_and_focus(page)
        QTest.keyClicks(page.name_edit, " EDIT")
        self.assertEqual(page.name_edit.text(), "Alpha EDIT")

        update_name_calls = self._count_calls(dataset_manager, "update_name")
        reset_contexts = self._track_subscription(
            event_bus, WORKSPACE_CLOSED, page.reset_for_context_change,
            probe=lambda: (dataset_manager.active_dataset_id, workspace_manager.opened),
        )

        workspace_manager.close()

        self.assertEqual(update_name_calls, [])
        self.assertEqual(page.name_edit.text(), "")
        self.assertIsNone(page._name_editor_owner_id)
        self.assertEqual(alpha.name, "Alpha")
        # At the moment the reset handler actually ran, the Domain
        # context was the expected one: no active Dataset (the Manager's
        # own subscription already ran first), no open Workspace.
        self.assertEqual(reset_contexts, [(None, False)])

    def test_workspace_created_with_a_draft_resets_the_editor_in_the_new_context(self):

        event_bus, workspace_manager, character_manager, dataset_manager, page = self._wire()
        (alpha,) = self._open_with(workspace_manager, character_manager, dataset_manager, "Alpha")

        page.name_edit.setText("Alpha EDIT")
        reset_contexts = self._track_subscription(
            event_bus, WORKSPACE_CREATED, page.reset_for_context_change,
            probe=lambda: (dataset_manager.active_dataset_id, workspace_manager.opened),
        )

        # create() publishes WORKSPACE_SAVED/CHARACTER_CREATED/
        # CHARACTER_SELECTED *before* WORKSPACE_CREATED, so the earlier
        # non-forced refreshes still see the previous active id — which
        # resolves to no object in the new Workspace and therefore never
        # counts as a draft. The forced reset itself runs once the
        # Manager has cleared its active Dataset.
        create_workspace_with_default_character(
            workspace_manager, character_manager, Path(self.tmp_dir) / "OtherProject"
        )

        self.assertEqual(page.name_edit.text(), "")
        self.assertIsNone(page._name_editor_owner_id)
        self.assertEqual(alpha.name, "Alpha")
        self.assertEqual(reset_contexts, [(None, True)])

    def test_reopening_the_same_workspace_with_identical_ids_never_carries_the_draft(self):

        event_bus, workspace_manager, character_manager, dataset_manager, page = self._wire()
        (alpha,) = self._open_with(workspace_manager, character_manager, dataset_manager, "Alpha")

        page.name_edit.setText("Alpha EDIT")
        self.assertEqual(page._name_editor_owner_id, alpha.dataset_id)
        reset_contexts = self._track_subscription(
            event_bus, WORKSPACE_OPENED, page.reset_for_context_change,
            probe=lambda: (dataset_manager.active_dataset_id, workspace_manager.opened),
        )

        # Same project folder, hence the very same dataset_id once
        # reloaded — a naive identity comparison could not tell this
        # apart from "nothing changed".
        workspace_manager.open(self.folder)

        self.assertEqual(page.name_edit.text(), "")
        self.assertIsNone(page._name_editor_owner_id)
        self.assertEqual(reset_contexts, [(None, True)])

        dataset_manager.select(alpha.dataset_id)

        reopened = dataset_manager.active_dataset
        self.assertIsNotNone(reopened)
        self.assertIsNot(reopened, alpha)
        self.assertEqual(reopened.dataset_id, alpha.dataset_id)
        self.assertEqual(page.name_edit.text(), "Alpha")
        self.assertEqual(page._name_editor_owner_id, alpha.dataset_id)

    def test_character_context_resets_clear_the_draft_through_the_forced_path(self):

        event_bus, workspace_manager, character_manager, dataset_manager, page = self._wire()
        (alpha,) = self._open_with(workspace_manager, character_manager, dataset_manager, "Alpha")

        page.name_edit.setText("Alpha EDIT")
        reset_contexts = self._track_subscription(
            event_bus, CHARACTER_SELECTED, page.reset_for_context_change,
            probe=lambda: (dataset_manager.active_dataset_id, workspace_manager.opened),
        )

        # CHARACTER_SELECTED is a context-reset event for this page: the
        # Manager clears its active Dataset first, then the page resets.
        character_manager.select(character_manager.principal_character.character_id)

        self.assertEqual(page.name_edit.text(), "")
        self.assertIsNone(page._name_editor_owner_id)
        self.assertEqual(alpha.name, "Alpha")
        self.assertEqual(reset_contexts, [(None, True)])

    def test_forced_reset_is_never_used_for_workspace_saved_or_renamed(self):

        event_bus, workspace_manager, character_manager, dataset_manager, page = self._wire()
        self._open_with(workspace_manager, character_manager, dataset_manager, "Alpha")

        page.name_edit.setText("Alpha EDIT")

        # The forced-reset path is wired only to the 5 context-reset
        # events — never to WORKSPACE_SAVED/RENAMED (nor to the other
        # events that go to update_datasets()).
        for event_name in (
            WORKSPACE_SAVED, WORKSPACE_RENAMED, CHARACTER_CREATED,
            DATASET_CREATED, DATASET_SELECTED, DATASET_DELETED,
        ):
            self.assertNotIn(page.reset_for_context_change, event_bus._subscribers[event_name])
        for event_name in (
            WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED,
            CHARACTER_SELECTED, CHARACTER_DELETED,
        ):
            self.assertIn(page.reset_for_context_change, event_bus._subscribers[event_name])

        contexts = self._spy_reload((dataset_manager, workspace_manager), page)

        workspace_manager.save()
        workspace_manager.rename("RenamedProject")

        # A real draft: neither event reloads the editor at all.
        self.assertEqual(contexts, [])
        self.assertEqual(page.name_edit.text(), "Alpha EDIT")


class DatasetsPageNameDraftMainWindowTest(unittest.TestCase):
    """
    Mission 165: the two scenarios whose fidelity depends on the real
    MainWindow wiring rather than a reproduction of it — the actual
    subscriber order of the context-reset events, and a real mouse click
    on the toolbar's Save button. Observations here are limited to what
    these exact scenarios exercise on the platform running the suite.
    """

    def setUp(self):
        # Cleanups run in reverse registration order, so the order below
        # is deliberate: (1) the dialog guard is armed first and stopped
        # LAST — a real QMessageBox is closed on the next tick and turned
        # into a clean UnexpectedDialogError instead of waiting for a
        # human click; (2) the temporary folder is registered BEFORE the
        # window, so the window is closed BEFORE the folder is removed.
        # Closing a window whose name_edit still holds a draft fires
        # editingFinished, hence a real rename: it must run against a
        # Workspace folder that still exists, never against a deleted one
        # (which makes save() fail and shows the real error dialog).
        self.dialog_guard = start_dialog_guard()
        self.addCleanup(stop_dialog_guard, self.dialog_guard)

        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "MainWindowNameDraftProject"

        self.window = MainWindow()
        self.addCleanup(self.window.close)

        create_workspace_with_default_character(
            self.window.workspace_manager, self.window.character_manager, self.folder
        )
        self.alpha = self.window.dataset_manager.create("Alpha")
        self.window.dataset_manager.select(self.alpha.dataset_id)

        self.page = self.window.datasets_page

    def _track_reset(self, event_name):
        """
        Swaps the page's reset_for_context_change() entry inside the real
        EventBus's subscriber list for a recording wrapper -- the Domain
        context (active Dataset id, Workspace open) is captured at the
        exact moment the handler is invoked.
        """
        reset_contexts = []
        callback = self.page.reset_for_context_change

        def tracking(payload=None):
            reset_contexts.append((
                self.window.dataset_manager.active_dataset_id,
                self.window.workspace_manager.opened,
            ))
            callback(payload)

        subscribers = self.window.event_bus._subscribers[event_name]
        self.assertIn(callback, subscribers)
        self.window.event_bus._subscribers[event_name] = [
            tracking if subscriber == callback else subscriber for subscriber in subscribers
        ]
        return reset_contexts

    def _show_and_focus(self):
        self.window.show()
        QTest.qWaitForWindowExposed(self.window)
        self.window.stack.setCurrentWidget(self.page)
        self.window.activateWindow()
        QTest.qWait(30)
        self.page.name_edit.setFocus()
        QTest.qWait(10)

    def test_real_toolbar_save_click_keeps_the_draft_displayed_and_commits_only_via_editing_finished(self):

        self._show_and_focus()

        editing_finished = []
        self.page.name_edit.editingFinished.connect(lambda: editing_finished.append(1))

        QTest.keyClicks(self.page.name_edit, " EDIT")
        self.assertEqual(self.page.name_edit.text(), "Alpha EDIT")

        save_calls = []
        original_save = self.window.workspace_manager.save
        self.window.workspace_manager.save = lambda: (save_calls.append(1), original_save())[-1]

        button = self.window.toolbar.widgetForAction(self.window.toolbar.action_save)
        QTest.mouseClick(button, Qt.LeftButton)
        QTest.qWait(30)

        # The draft is still displayed after the real click.
        self.assertEqual(self.page.name_edit.text(), "Alpha EDIT")
        # The name is persisted if and only if editingFinished fired
        # during this click — the click itself never persists it. (What
        # the platform's focus handling emits here is deliberately not
        # asserted.)
        self.assertEqual(self.alpha.name == "Alpha EDIT", bool(editing_finished))

        # The commit stays driven by editingFinished.
        QTest.keyClick(self.page.name_edit, Qt.Key_Return)
        self.assertEqual(self.alpha.name, "Alpha EDIT")
        self.assertEqual(self.page.name_edit.text(), "Alpha EDIT")

    def test_real_workspace_wiring_resets_the_editor_in_the_expected_domain_context(self):

        self._show_and_focus()
        QTest.keyClicks(self.page.name_edit, " EDIT")

        reset_contexts = self._track_reset(WORKSPACE_CLOSED)

        self.window.workspace_manager.close()

        self.assertEqual(self.page.name_edit.text(), "")
        self.assertIsNone(self.page._name_editor_owner_id)
        self.assertEqual(self.alpha.name, "Alpha")
        # Real subscriber order: when the page's reset handler ran, the
        # Manager had already cleared its active Dataset.
        self.assertEqual(reset_contexts, [(None, False)])

    def test_real_wiring_reopening_the_same_workspace_never_carries_the_draft(self):

        self._show_and_focus()
        QTest.keyClicks(self.page.name_edit, " EDIT")
        self.assertEqual(self.page._name_editor_owner_id, self.alpha.dataset_id)

        reset_contexts = self._track_reset(WORKSPACE_OPENED)

        # Same folder, hence identical dataset ids after reloading.
        self.window.workspace_manager.open(self.folder)

        self.assertEqual(self.page.name_edit.text(), "")
        self.assertIsNone(self.page._name_editor_owner_id)
        self.assertEqual(reset_contexts, [(None, True)])

        self.window.dataset_manager.select(self.alpha.dataset_id)
        self.assertEqual(self.page.name_edit.text(), "Alpha")


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
