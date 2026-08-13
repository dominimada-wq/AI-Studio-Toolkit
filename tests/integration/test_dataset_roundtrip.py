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

from PySide6.QtWidgets import QApplication

from src.core.event_bus import EventBus
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
        characters_page = CharactersPage(character_manager)
        images = ImagesPage(workspace_manager)
        datasets_page = DatasetsPage(dataset_manager)

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
        added = dataset_manager.add_images(["ref1.png", "ref2.png"])
        self.assertEqual(added, 2)

        self.assertEqual(
            [datasets_page.images_list.item(i).text()
             for i in range(datasets_page.images_list.count())],
            ["ref1.png", "ref2.png"],
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

        restored_character = character_manager_2.characters[0]
        character_manager_2.select(restored_character.character_id)

        self.assertEqual(len(dataset_manager_2.datasets), 1)
        restored_dataset = dataset_manager_2.datasets[0]
        self.assertEqual(restored_dataset.name, "Portraits")
        self.assertEqual(
            [image.file_path for image in restored_dataset.images],
            ["ref1.png", "ref2.png"],
        )

    def test_add_images_preserves_order_and_dedups(self):

        _, workspace_manager, character_manager, dataset_manager = self._wire()[:4]
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)

        added1 = dataset_manager.add_images(["a.png", "b.png", "c.png"])
        self.assertEqual(added1, 3)
        self.assertEqual(
            [image.file_path for image in dataset_manager.active_dataset.images],
            ["a.png", "b.png", "c.png"],
        )

        # Dedup across separate calls, arrival order preserved for new ones.
        added2 = dataset_manager.add_images(["b.png", "d.png", "a.png", "e.png"])
        self.assertEqual(added2, 2)
        self.assertEqual(
            [image.file_path for image in dataset_manager.active_dataset.images],
            ["a.png", "b.png", "c.png", "d.png", "e.png"],
        )

        # Dedup within a single call, first-seen order preserved.
        dataset2 = dataset_manager.create("Other")
        dataset_manager.select(dataset2.dataset_id)
        added3 = dataset_manager.add_images(["x.png", "y.png", "x.png", "z.png", "y.png"])
        self.assertEqual(added3, 3)
        self.assertEqual(
            [image.file_path for image in dataset_manager.active_dataset.images],
            ["x.png", "y.png", "z.png"],
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
        character_manager_2.select(character_manager_2.characters[0].character_id)
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
        dataset_manager.add_images(["a.png"])
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
        # characters_page, datasets_page) + CharacterManager's own
        # internal reset subscription + DatasetManager's own internal
        # reset subscription = 6, on EACH bus independently.
        self.assertEqual(len(event_bus_1._subscribers[WORKSPACE_CREATED]), 6)
        self.assertEqual(len(event_bus_2._subscribers[WORKSPACE_CREATED]), 6)
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


if __name__ == "__main__":
    unittest.main()
