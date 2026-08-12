"""
Integration coverage for the Character lifecycle, exercising
CharacterManager, Workspace.characters, EventBus and the real
CharactersPage/DashboardPage/ImagesPage widgets together — the same
wiring MainWindow uses (see src/ui/main_window.py).
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
from src.managers.dataset_manager import DatasetManager, DATASET_DELETED
from src.managers.training_manager import TrainingManager, TRAINING_DELETED
from src.ui.pages.dashboard_page import DashboardPage
from src.ui.pages.characters_page import CharactersPage
from src.ui.pages.images_page import ImagesPage

WORKSPACE_EVENTS = (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_SAVED, WORKSPACE_CLOSED)
CHARACTER_EVENTS = (CHARACTER_CREATED, CHARACTER_SELECTED, CHARACTER_DELETED)

_app = QApplication.instance() or QApplication([])


class CharacterRoundTripTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "CharacterProject"

    def _wire(self):
        # Every call builds a fully independent stack — new EventBus,
        # new managers, new widgets — so two calls in the same test
        # genuinely simulate two separate application runs rather than
        # reusing in-memory state.
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)

        dashboard = DashboardPage()
        characters_page = CharactersPage(character_manager)
        images = ImagesPage(workspace_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, dashboard.update_project)
            event_bus.subscribe(event_name, images.update_images)
            event_bus.subscribe(event_name, characters_page.update_characters)

        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, characters_page.update_characters)

        return event_bus, workspace_manager, character_manager, dashboard, characters_page, images

    def test_full_create_select_save_close_reopen_cycle(self):

        (event_bus, workspace_manager, character_manager,
         dashboard, characters_page, images) = self._wire()

        workspace_manager.create(self.folder)

        aria = character_manager.create("Aria")
        character_manager.create("Kai")

        self.assertEqual(
            [characters_page.list_widget.item(i).text()
             for i in range(characters_page.list_widget.count())],
            ["Aria", "Kai"],
        )

        character_manager.select(aria.character_id)
        self.assertEqual(character_manager.active_character_id, aria.character_id)

        workspace_manager.save()
        workspace_manager.close()

        self.assertIsNone(character_manager.active_character_id)
        self.assertEqual(characters_page.list_widget.count(), 0)

        # Reopen with a second _wire() call: every object below is a
        # brand new instance, not a reuse of the ones above.
        (event_bus_2, workspace_manager_2, character_manager_2,
         dashboard_2, characters_page_2, images_2) = self._wire()

        self.assertIsNot(event_bus_2, event_bus)
        self.assertIsNot(workspace_manager_2, workspace_manager)
        self.assertIsNot(character_manager_2, character_manager)
        self.assertIsNot(dashboard_2, dashboard)
        self.assertIsNot(characters_page_2, characters_page)
        self.assertIsNot(images_2, images)

        workspace_manager_2.open(self.folder)

        self.assertEqual(
            sorted(c.name for c in character_manager_2.characters),
            ["Aria", "Kai"],
        )

        # Runtime-only per Mission 002 decision 2: selection does NOT
        # survive a restart, even though the character list does.
        self.assertIsNone(character_manager_2.active_character_id)

        self.assertEqual(
            sorted(characters_page_2.list_widget.item(i).text()
                   for i in range(characters_page_2.list_widget.count())),
            ["Aria", "Kai"],
        )

    def test_delete_character_persists(self):

        workspace_manager, character_manager = self._wire()[1:3]
        workspace_manager.create(self.folder)

        aria = character_manager.create("Aria")
        character_manager.create("Kai")

        character_manager.delete(aria.character_id)

        workspace_manager_2, character_manager_2 = self._wire()[1:3]
        workspace_manager_2.open(self.folder)

        self.assertEqual([c.name for c in character_manager_2.characters], ["Kai"])

    def test_delete_character_removes_its_dataset_and_training_subtree(self):
        """
        Regression guard identified during the Mission 009 architecture
        audit: CharacterManager.delete() removes the Character object
        from workspace.characters wholesale (character_manager.py) —
        it never calls DatasetManager.delete()/TrainingManager.delete()
        on the Character's own Datasets/Trainings. This test proves
        that structural removal alone is sufficient: nothing leaks,
        because Dataset/Training only ever exist nested inside their
        owning Character in this persistence model, not in an
        independent registry.
        """

        event_bus, workspace_manager, character_manager = self._wire()[:3]
        workspace_manager.create(self.folder)

        character = character_manager.create("ToDelete")
        character_manager.select(character.character_id)

        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        dataset = dataset_manager.create("OrphanCheckDataset")

        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)
        training = training_manager.create("OrphanCheckTraining", dataset.dataset_id)
        self.assertEqual(training.dataset_id, dataset.dataset_id)

        events_seen = []
        for event_name in (CHARACTER_DELETED, DATASET_DELETED, TRAINING_DELETED):
            event_bus.subscribe(event_name, lambda payload, name=event_name: events_seen.append(name))

        result = character_manager.delete(character.character_id)
        self.assertTrue(result)

        # Immediate in-memory removal, before any close/reopen.
        self.assertNotIn(
            character.character_id,
            [c.character_id for c in workspace_manager.current_workspace.characters],
        )

        # Structural removal only — no cascade through the child
        # Managers' own delete() methods or events.
        self.assertEqual(events_seen, [CHARACTER_DELETED])
        self.assertEqual(events_seen.count(DATASET_DELETED), 0)
        self.assertEqual(events_seen.count(TRAINING_DELETED), 0)

        workspace_manager.close()

        # Reopen with a brand new stack — real disk round-trip, not
        # reused in-memory state.
        _, workspace_manager_2, character_manager_2 = self._wire()[:3]
        workspace_manager_2.open(self.folder)

        self.assertEqual(character_manager_2.characters, [])

        # Strictest proof available given this persistence model: read
        # the real project.json back and confirm the deleted subtree's
        # own identifiers are nowhere in it — there is no separate
        # Dataset/Training registry to check independently of Character.
        raw_json = (self.folder / "project.json").read_text(encoding="utf-8")

        self.assertNotIn(character.character_id, raw_json)
        self.assertNotIn(dataset.dataset_id, raw_json)
        self.assertNotIn(training.training_id, raw_json)
        self.assertNotIn("ToDelete", raw_json)
        self.assertNotIn("OrphanCheckDataset", raw_json)
        self.assertNotIn("OrphanCheckTraining", raw_json)

    def test_failed_open_does_not_reset_active_character(self):
        """
        Regression guard: WorkspaceManager.open() on an invalid folder
        does not touch current_workspace (fixed pre-Mission-002) and
        therefore never publishes WORKSPACE_OPENED — so
        CharacterManager's active_character_id reset (Commit 4) must
        not fire either.
        """

        workspace_manager, character_manager = self._wire()[1:3]
        workspace_manager.create(self.folder)

        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)

        invalid_folder = Path(self.tmp_dir) / "NoProjectJsonHere"
        invalid_folder.mkdir()

        result = workspace_manager.open(invalid_folder)

        self.assertIsNone(result)
        self.assertEqual(character_manager.active_character_id, aria.character_id)

    def test_dashboard_and_images_unaffected_by_character_events(self):
        """
        Locks in Mission 002 decision 5: the Dashboard stays untouched
        by character.* events, no Characters card.
        """

        (_, workspace_manager, character_manager,
         dashboard, characters_page, images) = self._wire()

        workspace_manager.create(self.folder)

        before_dashboard = dashboard.projectCard.value.text()
        before_images_count = images.list_widget.count()

        character_manager.create("Aria")

        self.assertEqual(dashboard.projectCard.value.text(), before_dashboard)
        self.assertEqual(images.list_widget.count(), before_images_count)
        self.assertFalse(hasattr(dashboard, "charactersCard"))

    def test_characters_page_rebuilds_on_workspace_events(self):
        """
        Isolated guard for the WORKSPACE_* -> CharactersPage.update_characters
        wiring specifically: creating, closing and reopening a workspace
        must each correctly clear/rebuild the character list, independent
        of any character.* event.
        """

        (_, workspace_manager, character_manager,
         _dashboard, characters_page, _images) = self._wire()

        # WORKSPACE_CREATED -> rendered, empty (no characters yet)
        workspace_manager.create(self.folder)
        self.assertEqual(characters_page.list_widget.count(), 0)

        character_manager.create("Aria")
        character_manager.create("Kai")
        self.assertEqual(characters_page.list_widget.count(), 2)

        # WORKSPACE_CLOSED -> list cleared
        workspace_manager.close()
        self.assertEqual(characters_page.list_widget.count(), 0)

        # WORKSPACE_OPENED -> list rebuilt from the reopened workspace
        workspace_manager.open(self.folder)
        self.assertEqual(
            sorted(characters_page.list_widget.item(i).text()
                   for i in range(characters_page.list_widget.count())),
            ["Aria", "Kai"],
        )

    def test_no_duplicate_subscriptions_between_wire_calls(self):
        """
        Confirms each _wire() call builds a fully independent stack: a
        new EventBus with no leftover subscribers from a previous
        _wire() call. Reaches into EventBus._subscribers deliberately —
        this test's whole purpose is to verify that internal invariant
        directly, since update_characters() being idempotent
        (clear-then-rebuild) would hide a duplicate-subscription bug
        from any purely behavioural assertion.
        """

        (event_bus_1, workspace_manager_1, character_manager_1,
         dashboard_1, characters_page_1, images_1) = self._wire()

        (event_bus_2, workspace_manager_2, character_manager_2,
         dashboard_2, characters_page_2, images_2) = self._wire()

        self.assertIsNot(event_bus_1, event_bus_2)
        self.assertIsNot(workspace_manager_1, workspace_manager_2)
        self.assertIsNot(character_manager_1, character_manager_2)
        self.assertIsNot(dashboard_1, dashboard_2)
        self.assertIsNot(characters_page_1, characters_page_2)
        self.assertIsNot(images_1, images_2)

        # Exactly 4 subscribers on WORKSPACE_CREATED: the 3 _wire()
        # registers directly (dashboard, images, characters_page) plus
        # CharacterManager's own internal subscription to reset
        # active_character_id (added in Commit 4) — on EACH bus,
        # independently.
        self.assertEqual(len(event_bus_1._subscribers[WORKSPACE_CREATED]), 4)
        self.assertEqual(len(event_bus_2._subscribers[WORKSPACE_CREATED]), 4)
        self.assertTrue(
            set(event_bus_1._subscribers[WORKSPACE_CREATED]).isdisjoint(
                event_bus_2._subscribers[WORKSPACE_CREATED]
            )
        )

        # Behavioural confirmation on top of the structural one: acting
        # on bus #2 only ever affects bus #2's widgets.
        workspace_manager_1.create(self.folder / "P1")
        workspace_manager_2.create(self.folder / "P2")
        character_manager_2.create("Aria")

        self.assertEqual(characters_page_1.list_widget.count(), 0)
        self.assertEqual(characters_page_2.list_widget.count(), 1)


if __name__ == "__main__":
    unittest.main()
