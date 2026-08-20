"""
Integration coverage for the Dataset lifecycle, exercising
DatasetManager, Character.datasets, Workspace persistence, EventBus
and the real DashboardPage/CharactersPage/ImagesPage/DatasetsPage
widgets together — the same wiring MainWindow uses.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QDialog

from src.core.event_bus import EventBus
from src.infrastructure.storage.workspace_storage import WorkspaceStorage
from src.managers.workspace_manager import (
    WorkspaceManager,
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
from src.ui.pages.dashboard_page import DashboardPage
from src.ui.pages.characters_page import CharactersPage
from src.ui.pages.images_page import ImagesPage
from src.ui.pages.datasets_page import DatasetsPage

WORKSPACE_EVENTS = (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_SAVED, WORKSPACE_CLOSED)
CHARACTER_EVENTS = (CHARACTER_CREATED, CHARACTER_SELECTED, CHARACTER_DELETED)
DATASET_EVENTS = (DATASET_CREATED, DATASET_SELECTED, DATASET_DELETED)

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
        self.assertEqual(
            [datasets_page.images_list.item(i).text()
             for i in range(datasets_page.images_list.count())],
            expected_internal,
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
        self.assertTrue(result)
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


if __name__ == "__main__":
    unittest.main()
