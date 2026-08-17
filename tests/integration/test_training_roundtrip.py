"""
Integration coverage for the Training lifecycle, exercising
TrainingManager, Character.trainings, its referential integrity with
Dataset, Workspace persistence, EventBus and the real
DashboardPage/CharactersPage/ImagesPage/TrainingPage widgets together
— the same wiring MainWindow uses. Also covers the Training domain
object's own to_dict()/from_dict() round-trip and default-value
behavior directly, since Training is a new entity introduced this
mission.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from src.core.event_bus import EventBus
from src.domain.training import Training
from src.domain.character import Character
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
from src.managers.training_manager import (
    TrainingManager,
    TRAINING_CREATED,
    TRAINING_SELECTED,
    TRAINING_DELETED,
)
from src.ui.pages.dashboard_page import DashboardPage
from src.ui.pages.characters_page import CharactersPage
from src.ui.pages.images_page import ImagesPage
from src.ui.pages.training_page import TrainingPage

WORKSPACE_EVENTS = (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_SAVED, WORKSPACE_CLOSED)
CHARACTER_EVENTS = (CHARACTER_CREATED, CHARACTER_SELECTED, CHARACTER_DELETED)
DATASET_EVENTS = (DATASET_CREATED, DATASET_SELECTED, DATASET_DELETED)
TRAINING_EVENTS = (TRAINING_CREATED, TRAINING_SELECTED, TRAINING_DELETED)

_app = QApplication.instance() or QApplication([])


class TrainingRoundTripTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "TrainingProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)

        dashboard = DashboardPage()
        characters_page = CharactersPage(character_manager)
        images = ImagesPage(workspace_manager)
        training_page = TrainingPage(training_manager, dataset_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, dashboard.update_project)
            event_bus.subscribe(event_name, images.update_images)
            event_bus.subscribe(event_name, characters_page.update_characters)
            event_bus.subscribe(event_name, training_page.update_trainings)

        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, characters_page.update_characters)
            event_bus.subscribe(event_name, training_page.update_trainings)

        # Deliberately NOT subscribing training_page to DATASET_* events —
        # the dataset picker is re-read on demand via
        # dataset_manager.list_datasets(), never cached (Commit 5's design).
        for event_name in TRAINING_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)

        return (
            event_bus, workspace_manager, character_manager, dataset_manager, training_manager,
            dashboard, characters_page, images, training_page,
        )

    def test_training_domain_object_roundtrip_and_defaults(self):

        # Default values.
        training = Training()
        self.assertEqual(training.training_id, "")
        self.assertEqual(training.name, "")
        self.assertEqual(training.dataset_id, "")
        self.assertEqual(
            training.to_dict(),
            {"training_id": "", "name": "", "dataset_id": ""},
        )

        # Round-trip without loss of information.
        original = Training(training_id="abc", name="Session 1", dataset_id="ds-1")
        restored = Training.from_dict(original.to_dict())
        self.assertEqual(original, restored)

        # Missing key -> default, consistent with every other Domain object.
        self.assertEqual(Training.from_dict({}), Training())
        self.assertEqual(Training.from_dict({"name": "Only Name"}).dataset_id, "")

        # Character.trainings: key absent / [] / None -> [], same
        # defensive-compatibility principle as datasets/loras/prompts.
        self.assertEqual(Character.from_dict({}).trainings, [])
        self.assertEqual(Character.from_dict({"trainings": []}).trainings, [])
        self.assertEqual(Character.from_dict({"trainings": None}).trainings, [])

        # Mixed list[dict|str|None|int] -> only dict entries survive.
        mixed = Character.from_dict({
            "trainings": [
                {"training_id": "T1", "name": "Training 1", "dataset_id": "D1"},
                "invalid",
                None,
                42,
                {"training_id": "T2", "name": "Training 2"},
            ]
        })
        self.assertEqual(len(mixed.trainings), 2)
        self.assertTrue(all(isinstance(t, Training) for t in mixed.trainings))
        self.assertEqual(mixed.trainings[0].training_id, "T1")
        self.assertEqual(mixed.trainings[0].dataset_id, "D1")
        self.assertEqual(mixed.trainings[1].training_id, "T2")
        self.assertEqual(mixed.trainings[1].dataset_id, "")

    def test_full_create_select_save_close_reopen_cycle(self):

        (event_bus, workspace_manager, character_manager, dataset_manager, training_manager,
         dashboard, characters_page, images, training_page) = self._wire()

        workspace_manager.create(self.folder)
        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)

        dataset = dataset_manager.create("Portraits")

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        self.assertEqual(training_page.training_list.count(), 1)
        self.assertIn("Portraits", training_page.dataset_label.text())

        workspace_manager.close()

        self.assertIsNone(training_manager.active_training_id)
        self.assertEqual(training_page.training_list.count(), 0)

        # Reopen with a second _wire() call — fresh instances, simulating
        # a real application restart rather than reusing in-memory state.
        (event_bus_2, workspace_manager_2, character_manager_2, dataset_manager_2, training_manager_2,
         dashboard_2, characters_page_2, images_2, training_page_2) = self._wire()

        workspace_manager_2.open(self.folder)

        # Runtime-only per Mission 002-008 decisions: neither
        # active_character_id nor active_training_id survive a restart.
        # Checked BEFORE selecting anything below.
        self.assertIsNone(character_manager_2.active_character_id)
        self.assertIsNone(training_manager_2.active_training_id)

        # Mission 026: the reopened workspace also holds its auto-created
        # principal Character — retrieve "Aria" explicitly by name (the
        # Character these Trainings actually belong to), not by list index.
        restored_character = next(
            c for c in character_manager_2.characters if c.name == "Aria"
        )
        character_manager_2.select(restored_character.character_id)

        self.assertEqual(len(training_manager_2.trainings), 1)
        restored_training = training_manager_2.trainings[0]
        self.assertEqual(restored_training.name, "Session 1")
        self.assertEqual(restored_training.dataset_id, dataset.dataset_id)

    def test_create_rejects_empty_or_unknown_dataset_id(self):

        event_bus, workspace_manager, character_manager, dataset_manager, training_manager = self._wire()[:5]
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset_manager.create("Portraits")  # exists but irrelevant to the ids under test

        events_seen = []
        for event_name in TRAINING_EVENTS:
            event_bus.subscribe(event_name, lambda payload, name=event_name: events_seen.append(name))

        for invalid_id in ("", "does-not-exist"):
            trainings_before = [t.to_dict() for t in character.trainings]
            active_before = training_manager.active_training_id
            with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
                result = training_manager.create("Session", invalid_id)
                self.assertIsNone(result)
                save_spy.assert_not_called()
            self.assertEqual([t.to_dict() for t in character.trainings], trainings_before)
            self.assertEqual(training_manager.active_training_id, active_before)
            self.assertEqual(events_seen, [])

    def test_create_rejects_dataset_id_from_another_character(self):

        event_bus, workspace_manager, character_manager, dataset_manager, training_manager = self._wire()[:5]
        workspace_manager.create(self.folder)

        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)
        aria_dataset = dataset_manager.create("AriaDS")

        kai = character_manager.create("Kai")
        character_manager.select(kai.character_id)

        events_seen = []
        for event_name in TRAINING_EVENTS:
            event_bus.subscribe(event_name, lambda payload, name=event_name: events_seen.append(name))

        trainings_before = [t.to_dict() for t in kai.trainings]
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            result = training_manager.create("Session", aria_dataset.dataset_id)
            self.assertIsNone(result)
            save_spy.assert_not_called()

        self.assertEqual([t.to_dict() for t in kai.trainings], trainings_before)
        self.assertIsNone(training_manager.active_training_id)
        self.assertEqual(events_seen, [])

    def test_training_manager_context_reset_on_character_and_workspace_change(self):

        _, workspace_manager, character_manager, dataset_manager, training_manager = self._wire()[:5]
        workspace_manager.create(self.folder)

        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)
        dataset = dataset_manager.create("Portraits")
        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)
        self.assertEqual(training_manager.active_training_id, training.training_id)

        # Switching the active character must reset active_training_id —
        # the new character's training list is unrelated.
        kai = character_manager.create("Kai")
        character_manager.select(kai.character_id)
        self.assertIsNone(training_manager.active_training_id)

        # Re-select Aria and her training, then confirm a workspace close
        # also resets it.
        character_manager.select(aria.character_id)
        training_manager.select(training.training_id)
        self.assertIsNotNone(training_manager.active_training_id)

        workspace_manager.close()
        self.assertIsNone(training_manager.active_training_id)

    def test_delete_active_training_resets_selection_and_persists(self):

        _, workspace_manager, character_manager, dataset_manager, training_manager = self._wire()[:5]
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")

        keep = training_manager.create("Keep", dataset.dataset_id)
        drop = training_manager.create("Drop", dataset.dataset_id)
        training_manager.select(drop.training_id)

        result = training_manager.delete(drop.training_id)
        self.assertTrue(result)
        self.assertIsNone(training_manager.active_training_id)
        self.assertIsNone(training_manager.active_training)
        self.assertEqual([t.name for t in training_manager.trainings], ["Keep"])

        # Non-active deletion preserves the current selection.
        other = training_manager.create("Other", dataset.dataset_id)
        training_manager.select(keep.training_id)
        result = training_manager.delete(other.training_id)
        self.assertTrue(result)
        self.assertEqual(training_manager.active_training_id, keep.training_id)

        # Invalid id: no effect at all.
        trainings_before = [t.to_dict() for t in character.trainings]
        result = training_manager.delete("does-not-exist")
        self.assertFalse(result)
        self.assertEqual([t.to_dict() for t in character.trainings], trainings_before)
        self.assertEqual(training_manager.active_training_id, keep.training_id)

        # Persists: reopening shows only the surviving training.
        _, workspace_manager_2, character_manager_2, dataset_manager_2, training_manager_2 = self._wire()[:5]
        workspace_manager_2.open(self.folder)
        # Mission 026: retrieve "Aria" explicitly by name rather than by
        # list index (the reopened workspace also holds its auto-created
        # principal Character).
        restored_character = next(
            c for c in character_manager_2.characters if c.name == "Aria"
        )
        character_manager_2.select(restored_character.character_id)
        self.assertEqual([t.name for t in training_manager_2.trainings], ["Keep"])

    def test_dataset_deletion_blocked_while_referenced_then_unblocks(self):

        event_bus, workspace_manager, character_manager, dataset_manager, training_manager = self._wire()[:5]
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        # 1-2. Dataset D created, two Trainings T1/T2 reference it.
        dataset = dataset_manager.create("Portraits")
        t1 = training_manager.create("T1", dataset.dataset_id)
        t2 = training_manager.create("T2", dataset.dataset_id)

        dataset_events_seen = []
        for event_name in DATASET_EVENTS:
            event_bus.subscribe(event_name, lambda payload, name=event_name: dataset_events_seen.append(name))

        # 3-5. delete(D) -> False, no save/event, T1/T2 unchanged.
        datasets_before = [d.to_dict() for d in character.datasets]
        trainings_before = [t.to_dict() for t in character.trainings]
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            result = dataset_manager.delete(dataset.dataset_id)
            self.assertFalse(result)
            save_spy.assert_not_called()
        self.assertEqual(dataset_events_seen, [])
        self.assertEqual([d.to_dict() for d in character.datasets], datasets_before)
        self.assertEqual([t.to_dict() for t in character.trainings], trainings_before)

        # 6. delete T1 -> D still blocked (T2 remains), no cascade on D.
        training_manager.delete(t1.training_id)
        self.assertFalse(dataset_manager.delete(dataset.dataset_id))
        self.assertEqual([d.to_dict() for d in character.datasets], datasets_before)

        # 7-8. delete T2 -> D becomes deletable, deletion succeeds.
        training_manager.delete(t2.training_id)
        dataset_events_seen.clear()
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            result = dataset_manager.delete(dataset.dataset_id)
            self.assertTrue(result)
            save_spy.assert_called_once()
        self.assertEqual(dataset_events_seen, [DATASET_DELETED])
        self.assertNotIn(dataset.dataset_id, [d.dataset_id for d in character.datasets])

        # 9. No cascade ever occurred: character.trainings was only ever
        # mutated by the explicit training_manager.delete() calls above,
        # never as a side-effect of the two blocked delete(D) attempts.

    def test_training_operations_do_not_mutate_other_character_collections(self):

        _, workspace_manager, character_manager, dataset_manager, training_manager = self._wire()[:5]
        workspace_manager.create(self.folder)

        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)
        dataset = dataset_manager.create("Portraits")

        kai = character_manager.create("Kai")
        character_manager.select(kai.character_id)
        kai_dataset = dataset_manager.create("KaiDS")
        training_manager.create("KaiTraining", kai_dataset.dataset_id)

        character_manager.select(aria.character_id)

        datasets_before = [d.to_dict() for d in aria.datasets]
        loras_before = [l.to_dict() for l in aria.loras]
        prompts_before = [p.to_dict() for p in aria.prompts]
        kai_trainings_before = [t.to_dict() for t in kai.trainings]

        training = training_manager.create("Session", dataset.dataset_id)
        training_manager.select(training.training_id)
        training_manager.delete(training.training_id)

        # The referenced Dataset itself (including its images list) must
        # be untouched — proves no indirect mutation through the
        # dataset_id relationship.
        self.assertEqual([d.to_dict() for d in aria.datasets], datasets_before)
        self.assertEqual([l.to_dict() for l in aria.loras], loras_before)
        self.assertEqual([p.to_dict() for p in aria.prompts], prompts_before)
        self.assertEqual([t.to_dict() for t in kai.trainings], kai_trainings_before)

    def test_training_page_rebuilds_on_relevant_events(self):

        (_, workspace_manager, character_manager, dataset_manager, training_manager,
         _dashboard, _characters_page, _images, training_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")

        training = training_manager.create("Session 1", dataset.dataset_id)
        self.assertEqual(training_page.training_list.count(), 1)

        training_manager.select(training.training_id)
        self.assertIn("Portraits", training_page.dataset_label.text())

        # Historical Training whose Dataset no longer exists displays
        # cleanly, without raising.
        training.dataset_id = "ghost-id"
        training_page.update_trainings()
        self.assertIn("introuvable", training_page.dataset_label.text())
        self.assertIn("ghost-id", training_page.dataset_label.text())

        workspace_manager.close()
        self.assertEqual(training_page.training_list.count(), 0)
        self.assertEqual(training_page.dataset_label.text(), "")

    def test_no_duplicate_subscriptions_between_wire_calls(self):

        wired_1 = self._wire()
        wired_2 = self._wire()

        for obj_1, obj_2 in zip(wired_1, wired_2):
            self.assertIsNot(obj_1, obj_2)

        event_bus_1, event_bus_2 = wired_1[0], wired_2[0]

        # 4 subscribers registered directly by _wire() (dashboard, images,
        # characters_page, training_page) + CharacterManager's two own
        # internal subscriptions (active_character_id reset, and
        # Mission 026's principal-Character auto-creation) + DatasetManager's
        # own internal reset subscription + TrainingManager's own internal
        # reset subscription = 8, on EACH bus independently.
        self.assertEqual(len(event_bus_1._subscribers[WORKSPACE_CREATED]), 8)
        self.assertEqual(len(event_bus_2._subscribers[WORKSPACE_CREATED]), 8)
        self.assertTrue(
            set(event_bus_1._subscribers[WORKSPACE_CREATED]).isdisjoint(
                event_bus_2._subscribers[WORKSPACE_CREATED]
            )
        )

    def test_dashboard_and_images_unaffected_by_training_events(self):

        (_, workspace_manager, character_manager, dataset_manager, training_manager,
         dashboard, _characters_page, images, _training_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")

        before_dashboard = dashboard.projectCard.value.text()
        before_images_count = images.list_widget.count()

        training_manager.create("Session 1", dataset.dataset_id)

        self.assertEqual(dashboard.projectCard.value.text(), before_dashboard)
        self.assertEqual(images.list_widget.count(), before_images_count)


if __name__ == "__main__":
    unittest.main()
