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

import inspect
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.core.event_bus import EventBus
from src.domain.image import Image
from src.domain.training import Training
from src.domain.character import Character
from src.engines.onetrainer_config import OneTrainerConfigError
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
    TrainingPreparationError,
    TRAINING_ARCHITECTURE_SD15,
    TRAINING_ARCHITECTURE_SDXL,
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
        characters_page = CharactersPage(character_manager, workspace_manager)
        images = ImagesPage(workspace_manager)
        training_page = TrainingPage(training_manager, dataset_manager, workspace_manager)

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
            {
                "training_id": "", "name": "", "dataset_id": "",
                "base_model_source": "", "architecture": "", "resolution": 0,
                "epochs": 100, "learning_rate": 0.0003, "lora_rank": 16,
                "lora_alpha": 1.0, "trigger_word": "",
            },
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

        # Mission 043: trainingCard mirrors datasetsCard/lorasCard — no
        # Training session yet, so it must read "0" before create().
        self.assertEqual(dashboard.trainingCard.value.text(), "0")

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        self.assertEqual(training_page.training_list.count(), 1)
        self.assertIn("Portraits", training_page.dataset_label.text())
        self.assertEqual(dashboard.trainingCard.value.text(), "1")

        workspace_manager.close()

        self.assertIsNone(training_manager.active_training_id)
        self.assertEqual(training_page.training_list.count(), 0)
        self.assertEqual(dashboard.trainingCard.value.text(), "0")

        # Reopen with a second _wire() call — fresh instances, simulating
        # a real application restart rather than reusing in-memory state.
        (event_bus_2, workspace_manager_2, character_manager_2, dataset_manager_2, training_manager_2,
         dashboard_2, characters_page_2, images_2, training_page_2) = self._wire()

        workspace_manager_2.open(self.folder)

        # Mission 043: WORKSPACE_OPENED already carries the reopened
        # workspace's characters/trainings — the restored count is
        # observable immediately, independent of any character/training
        # selection performed below.
        self.assertEqual(dashboard_2.trainingCard.value.text(), "1")

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

    def test_dashboard_training_card_default_value_without_any_workspace(self):
        # Mission 043: a freshly constructed DashboardPage, before any
        # Workspace ever existed, must read "0" — never the "Idle" it
        # displayed before this mission.
        dashboard = DashboardPage()

        self.assertEqual(dashboard.trainingCard.value.text(), "0")

    def test_dashboard_training_card_reflects_multiple_sessions_and_deletion(self):

        (_, workspace_manager, character_manager, dataset_manager, training_manager,
         dashboard, _characters_page, _images, _training_page) = self._wire()

        workspace_manager.create(self.folder)
        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)
        dataset = dataset_manager.create("Portraits")

        first = training_manager.create("Session 1", dataset.dataset_id)
        self.assertEqual(dashboard.trainingCard.value.text(), "1")

        second = training_manager.create("Session 2", dataset.dataset_id)
        self.assertEqual(dashboard.trainingCard.value.text(), "2")

        training_manager.delete(first.training_id)
        self.assertEqual(dashboard.trainingCard.value.text(), "1")

        training_manager.delete(second.training_id)
        self.assertEqual(dashboard.trainingCard.value.text(), "0")

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
            self.assertFalse(result.deleted)
            save_spy.assert_not_called()
        self.assertEqual(dataset_events_seen, [])
        self.assertEqual([d.to_dict() for d in character.datasets], datasets_before)
        self.assertEqual([t.to_dict() for t in character.trainings], trainings_before)

        # 6. delete T1 -> D still blocked (T2 remains), no cascade on D.
        training_manager.delete(t1.training_id)
        self.assertFalse(dataset_manager.delete(dataset.dataset_id).deleted)
        self.assertEqual([d.to_dict() for d in character.datasets], datasets_before)

        # 7-8. delete T2 -> D becomes deletable, deletion succeeds.
        training_manager.delete(t2.training_id)
        dataset_events_seen.clear()
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            result = dataset_manager.delete(dataset.dataset_id)
            self.assertTrue(result.deleted)
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


class TrainingCreationWithoutManualCharacterSelectionTest(unittest.TestCase):
    """
    Mission 029 regression: same defect as LoRAManager/PromptManager
    (see test_lora_roundtrip.py/test_prompt_roundtrip.py's equivalent
    classes), reproduced for TrainingManager. Also proves that
    create()'s dataset-ownership check (character.datasets, see
    TrainingManager.create()) still correctly restricts against the
    principal Character's own datasets once `character` is resolved
    through principal_character instead of active_character.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)
        return workspace_manager, character_manager, dataset_manager, training_manager

    def test_training_lifecycle_survives_reopen_without_manual_character_selection(self):

        # 1. Create a fresh Workspace, a Dataset, and a Training
        # referencing it, then close.
        (workspace_manager, character_manager,
         dataset_manager, training_manager) = self._wire()
        workspace_manager.create(self.folder)
        principal = character_manager.principal_character

        dataset = dataset_manager.create("Base")
        self.assertIsNotNone(dataset)

        existing = training_manager.create("Run 1", dataset.dataset_id)
        self.assertIsNotNone(existing)

        workspace_manager.close()

        # 2. Reopen — exactly the sequence that leaves active_character_id
        # at None (WORKSPACE_OPENED resets it, and nothing re-selects it,
        # since CharactersPage no longer calls select() at all).
        (workspace_manager, character_manager,
         dataset_manager, training_manager) = self._wire()
        workspace_manager.open(self.folder)

        self.assertIsNone(character_manager.active_character_id)
        self.assertIsNotNone(character_manager.principal_character)
        self.assertEqual(
            character_manager.principal_character.character_id,
            principal.character_id,
        )

        # 3. The Training created before the reopen must still be visible.
        trainings = training_manager.trainings
        self.assertEqual(len(trainings), 1)
        self.assertEqual(trainings[0].name, "Run 1")

        # 4. A second Training referencing the same principal Character's
        # own Dataset must succeed — proves the dataset-ownership check
        # inside create() still resolves against the right Character,
        # not merely that create() returns non-None.
        [dataset_again] = dataset_manager.datasets
        second = training_manager.create("Run 2", dataset_again.dataset_id)
        self.assertIsNotNone(second)
        self.assertIn(second, character_manager.principal_character.trainings)
        self.assertEqual(len(training_manager.trainings), 2)

        # 5. Deleting must succeed too.
        self.assertTrue(training_manager.delete(existing.training_id))
        self.assertEqual(len(training_manager.trainings), 1)

        # 6. Persistence: close and reopen again, confirm only the
        # surviving Training remains.
        workspace_manager.close()
        (workspace_manager, character_manager,
         dataset_manager, training_manager) = self._wire()
        workspace_manager.open(self.folder)

        self.assertIsNone(character_manager.active_character_id)
        final = training_manager.trainings
        self.assertEqual(len(final), 1)
        self.assertEqual(final[0].name, "Run 2")

    def _wire_page_with_fake_dataset(self, workspace_manager, character_manager):
        # TrainingPage.create_training() only reaches the "Aucun
        # personnage" branch under test once a non-empty dataset list
        # has already been displayed — dataset_manager is mocked here
        # to force that, independently of whatever principal_character
        # actually resolves to (see Mission 036 specification, section
        # 3: this branch is a defensive/consistency fix, not a normally
        # reachable path — TrainingManager.create() checks
        # principal_character before dataset ownership, so the fake
        # dataset_id below is never actually consulted in these tests).
        training_manager = TrainingManager(character_manager, workspace_manager)
        dataset_manager = MagicMock()
        dataset_manager.list_datasets.return_value = [
            {"name": "Base", "dataset_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}
        ]
        training_page = TrainingPage(training_manager, dataset_manager, workspace_manager)
        return training_page

    def test_create_training_without_open_workspace_shows_no_project_warning(self):
        # Mission 036 introduced this "Aucun projet ouvert" message, then
        # reached only via TrainingManager.create() returning None (the
        # "Aucun dataset disponible" guard, fired earlier in the method,
        # was masking it whenever list_datasets() was mocked non-empty
        # as done here). Mission 037 moved the workspace_manager.opened
        # check to the very top of create_training(), so this same
        # scenario is now intercepted before list_datasets() is ever
        # consulted and before either QInputDialog is ever shown —
        # asserted explicitly below.
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        training_page = self._wire_page_with_fake_dataset(workspace_manager, character_manager)

        with patch(
            "src.ui.pages.training_page.QInputDialog.getItem",
            return_value=("Base [aaaaaaaa]", True),
        ) as mock_get_item, patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Run 1", True),
        ) as mock_get_text, patch("src.ui.pages.training_page.QMessageBox.warning") as mock_warning:
            training_page.create_training()
            mock_warning.assert_called_once_with(
                training_page,
                "Aucun projet ouvert",
                "Ouvrez ou créez un projet avant de créer une session d'entraînement."
            )
            # Mission 037: the new top-of-method guard must prevent any
            # dataset lookup or dialog from firing in this case.
            training_page.dataset_manager.list_datasets.assert_not_called()
            mock_get_item.assert_not_called()
            mock_get_text.assert_not_called()

    def test_create_training_with_open_workspace_and_no_character_shows_personnage_warning(self):
        # Sibling of the test above: same None from TrainingManager.
        # create(), but here the Workspace is open with zero Character.
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        workspace_manager.create(self.folder)
        principal = character_manager.characters[0]
        character_manager.delete(principal.character_id)
        training_page = self._wire_page_with_fake_dataset(workspace_manager, character_manager)

        with patch(
            "src.ui.pages.training_page.QInputDialog.getItem",
            return_value=("Base [aaaaaaaa]", True),
        ), patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Run 1", True),
        ), patch("src.ui.pages.training_page.QMessageBox.warning") as mock_warning:
            training_page.create_training()
            mock_warning.assert_called_once_with(
                training_page,
                "Aucun personnage",
                "Ce projet ne possède aucun personnage — créez-en un depuis Characters avant de créer une session d'entraînement."
            )

    def test_create_training_with_open_workspace_and_no_dataset_shows_dataset_warning(self):
        # Mission 037: Workspace open, zero Dataset — the pre-existing
        # "Aucun dataset disponible" guard (unrelated to Mission 037,
        # unchanged) must still fire exactly as before, now reached only
        # once the new workspace_manager.opened guard above it has
        # passed. Real WorkspaceManager/DatasetManager here (no mock),
        # unlike the two tests above.
        workspace_manager, character_manager, dataset_manager, training_manager = self._wire()
        workspace_manager.create(self.folder)
        training_page = TrainingPage(training_manager, dataset_manager, workspace_manager)

        with patch("src.ui.pages.training_page.QMessageBox.warning") as mock_warning:
            training_page.create_training()
            mock_warning.assert_called_once_with(
                training_page,
                "Aucun dataset disponible",
                "Créez un dataset avant de créer une session d'entraînement."
            )

        self.assertEqual(training_manager.trainings, [])

    def test_create_training_with_open_workspace_and_dataset_succeeds(self):
        # Mission 037: golden path — Workspace open with a Dataset
        # available must remain entirely unaffected by the new guard.
        workspace_manager, character_manager, dataset_manager, training_manager = self._wire()
        workspace_manager.create(self.folder)
        dataset = dataset_manager.create("Base")
        training_page = TrainingPage(training_manager, dataset_manager, workspace_manager)

        label = f"Base [{dataset.dataset_id[:8]}]"

        with patch(
            "src.ui.pages.training_page.QInputDialog.getItem",
            return_value=(label, True),
        ), patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Run 1", True),
        ), patch("src.ui.pages.training_page.QMessageBox.warning") as mock_warning:
            training_page.create_training()
            mock_warning.assert_not_called()

        self.assertEqual(len(training_manager.trainings), 1)
        self.assertEqual(training_manager.trainings[0].name, "Run 1")
        self.assertEqual(training_manager.trainings[0].dataset_id, dataset.dataset_id)


class TrainingManagerRenameTest(unittest.TestCase):
    """
    Mission 054: TrainingManager.update_name() — mirrors
    PromptManager.update_name()'s exact idempotent contract (Mission
    053), extended to Training. No training engine, no execution state
    introduced or implied.
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
        self.training = self.training_manager.create("Session 1", self.dataset.dataset_id)
        self.training_manager.select(self.training.training_id)

    def test_update_name_renames_the_active_training(self):
        result = self.training_manager.update_name("Session 1 Renamed")

        self.assertTrue(result)
        self.assertEqual(self.training_manager.active_training.name, "Session 1 Renamed")

    def test_update_name_is_idempotent(self):
        with patch.object(self.workspace_manager, "save", wraps=self.workspace_manager.save) as save_spy:
            result = self.training_manager.update_name("Session 1")
            self.assertFalse(result)
            save_spy.assert_not_called()

            result = self.training_manager.update_name("Session 1 Renamed")
            self.assertTrue(result)
            save_spy.assert_called_once()

    def test_update_name_without_active_training_returns_false(self):
        self.training_manager.active_training_id = None

        result = self.training_manager.update_name("Anything")

        self.assertFalse(result)

    def test_update_name_preserves_training_id_and_dataset_id(self):
        original_training_id = self.training.training_id
        original_dataset_id = self.training.dataset_id

        self.training_manager.update_name("Session 1 Renamed")

        self.assertEqual(self.training_manager.active_training.training_id, original_training_id)
        self.assertEqual(self.training_manager.active_training.dataset_id, original_dataset_id)

    def test_update_name_empty_string_is_legitimate(self):
        result = self.training_manager.update_name("")

        self.assertTrue(result)
        self.assertEqual(self.training_manager.active_training.name, "")

    def test_rename_persists_after_close_reopen(self):
        self.training_manager.update_name("Session 1 Renamed")

        self.workspace_manager.close()

        event_bus_2 = EventBus()
        workspace_manager_2 = WorkspaceManager(event_bus=event_bus_2)
        character_manager_2 = CharacterManager(workspace_manager_2, event_bus=event_bus_2)
        training_manager_2 = TrainingManager(character_manager_2, workspace_manager_2, event_bus=event_bus_2)
        workspace_manager_2.open(self.folder)

        restored_character = next(
            c for c in character_manager_2.characters if c.name == "Aria"
        )
        character_manager_2.select(restored_character.character_id)

        self.assertEqual(len(training_manager_2.trainings), 1)
        restored = training_manager_2.trainings[0]
        self.assertEqual(restored.training_id, self.training.training_id)
        self.assertEqual(restored.name, "Session 1 Renamed")
        self.assertEqual(restored.dataset_id, self.dataset.dataset_id)


class TrainingManagerCreateRollbackTest(unittest.TestCase):
    """
    Mission 072: TrainingManager.create() rolls back the in-memory
    append (the same Training instance just constructed) if save()
    fails — mirrors DatasetManager.create()'s rollback contract.
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
        self.existing_training = self.training_manager.create("Session 1", self.dataset.dataset_id)

    def test_create_succeeds_normally_when_save_works(self):
        training = self.training_manager.create("Session 2", self.dataset.dataset_id)

        self.assertIsNotNone(training)
        self.assertEqual(
            [t.training_id for t in self.training_manager.trainings],
            [self.existing_training.training_id, training.training_id],
        )

    def test_create_save_failure_removes_the_phantom_training(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.create("Session 2", self.dataset.dataset_id)

        self.assertEqual(
            [t.training_id for t in self.training_manager.trainings],
            [self.existing_training.training_id],
        )

    def test_create_save_failure_publishes_no_success_event(self):
        received = []
        self.event_bus.subscribe(TRAINING_CREATED, lambda payload: received.append(payload))

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.create("Session 2", self.dataset.dataset_id)

        self.assertEqual(received, [])

    def test_create_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.create("Session 2", self.dataset.dataset_id)

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_after_create_failure_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.create("Session 2", self.dataset.dataset_id)

        training = self.training_manager.create("Session 2", self.dataset.dataset_id)

        self.assertIsNotNone(training)
        self.assertEqual(
            [t.training_id for t in self.training_manager.trainings],
            [self.existing_training.training_id, training.training_id],
        )

        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        self.assertEqual(
            sorted(t["training_id"] for t in aria["trainings"]),
            sorted([self.existing_training.training_id, training.training_id]),
        )

    def test_create_save_failure_does_not_affect_a_preexisting_unrelated_training(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.create("Session 2", self.dataset.dataset_id)

        trainings = self.training_manager.trainings
        self.assertEqual(len(trainings), 1)
        self.assertIs(trainings[0], self.existing_training)


class TrainingPageCreatePersistenceFailureTest(unittest.TestCase):
    """
    Mission 072: TrainingPage.create_training() catches
    WorkspaceManagerError around training_manager.create() and shows
    QMessageBox.critical().
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
        self.training_page = TrainingPage(
            self.training_manager, self.dataset_manager, self.workspace_manager
        )
        for event_name in TRAINING_EVENTS:
            self.event_bus.subscribe(event_name, self.training_page.update_trainings)

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)
        self.dataset = self.dataset_manager.create("Portraits")
        self.label = f"Portraits [{self.dataset.dataset_id[:8]}]"

    def test_create_failure_shows_error_and_training_list_stays_empty(self):
        with patch(
            "src.ui.pages.training_page.QInputDialog.getItem",
            return_value=(self.label, True),
        ), patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Session 1", True),
        ), patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.training_page.QMessageBox.critical") as mock_critical:
            self.training_page.create_training()

        self.assertTrue(mock_critical.called)
        self.assertEqual(self.training_manager.trainings, [])
        self.assertEqual(self.training_page.training_list.count(), 0)

    def test_create_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch(
            "src.ui.pages.training_page.QInputDialog.getItem",
            return_value=(self.label, True),
        ), patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Session 1", True),
        ), patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.training_page.QMessageBox.critical"):
            self.training_page.create_training()

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_after_create_failure_actually_creates(self):
        with patch(
            "src.ui.pages.training_page.QInputDialog.getItem",
            return_value=(self.label, True),
        ), patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Session 1", True),
        ), patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.training_page.QMessageBox.critical"):
            self.training_page.create_training()

        with patch(
            "src.ui.pages.training_page.QInputDialog.getItem",
            return_value=(self.label, True),
        ), patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Session 1", True),
        ):
            self.training_page.create_training()

        self.assertEqual(len(self.training_manager.trainings), 1)
        self.assertEqual(self.training_page.training_list.count(), 1)


class TrainingManagerRenameRollbackTest(unittest.TestCase):
    """
    Mission 070: TrainingManager.update_name() rolls back Training.name
    to its previous value if save() fails — a single-scalar Domain-only
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
        self.training_manager = TrainingManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.dataset = self.dataset_manager.create("Portraits")
        self.training = self.training_manager.create("Session 1", self.dataset.dataset_id)
        self.training_manager.select(self.training.training_id)

    def test_update_name_succeeds_normally_when_save_works(self):
        result = self.training_manager.update_name("Session 1 Renamed")

        self.assertTrue(result)
        self.assertEqual(self.training.name, "Session 1 Renamed")

    def test_update_name_save_failure_restores_previous_name_on_same_object(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.update_name("Session 1 Renamed")

        self.assertEqual(self.training.name, "Session 1")
        self.assertIs(self.training_manager.active_training, self.training)

    def test_update_name_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.update_name("Session 1 Renamed")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_update_name_save_failure_never_touches_dataset_id(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.update_name("Session 1 Renamed")

        self.assertEqual(self.training.dataset_id, self.dataset.dataset_id)

    def test_retry_of_the_same_previously_rejected_name_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.update_name("Session 1 Renamed")

        result = self.training_manager.update_name("Session 1 Renamed")

        self.assertTrue(result)
        self.assertEqual(self.training.name, "Session 1 Renamed")


class TrainingPageSortTest(unittest.TestCase):
    """
    Mission 051: TrainingPage.training_list is now sorted by name,
    case-insensitive, always active — same pattern as Mission 048.
    Character.trainings (Domain) must never be reordered.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "TrainingSortProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)
        training_page = TrainingPage(training_manager, dataset_manager, workspace_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in TRAINING_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)

        return event_bus, workspace_manager, character_manager, dataset_manager, training_manager, training_page

    def _setup_character_and_dataset(self, character_manager, dataset_manager):
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        return character, dataset

    def test_display_order_is_alphabetical_case_insensitive(self):

        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        _, dataset = self._setup_character_and_dataset(character_manager, dataset_manager)

        for name in ("Zebra", "mango", "Apple", "banana", "Cherry"):
            training_manager.create(name, dataset.dataset_id)

        displayed = [
            training_page.training_list.item(i).text()
            for i in range(training_page.training_list.count())
        ]
        self.assertEqual(displayed, ["Apple", "banana", "Cherry", "mango", "Zebra"])

    def test_domain_collection_keeps_insertion_order(self):

        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character, dataset = self._setup_character_and_dataset(character_manager, dataset_manager)

        for name in ("Zebra", "mango", "Apple"):
            training_manager.create(name, dataset.dataset_id)

        self.assertEqual(
            [t.name for t in character.trainings],
            ["Zebra", "mango", "Apple"],
        )

    def test_sort_is_stable_for_identical_names(self):

        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        _, dataset = self._setup_character_and_dataset(character_manager, dataset_manager)

        first = training_manager.create("Same", dataset.dataset_id)
        second = training_manager.create("Same", dataset.dataset_id)

        displayed_ids = [
            training_page.training_list.item(i).data(Qt.UserRole)
            for i in range(training_page.training_list.count())
        ]
        self.assertEqual(displayed_ids, [first.training_id, second.training_id])

    def test_selection_targets_correct_training_despite_display_reorder(self):

        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character, portraits = self._setup_character_and_dataset(character_manager, dataset_manager)
        landscapes = dataset_manager.create("Landscapes")

        zebra = training_manager.create("Zebra", portraits.dataset_id)
        apple = training_manager.create("Apple", landscapes.dataset_id)

        training_manager.select(apple.training_id)

        # "Apple" now displays at position 0, ahead of "Zebra" — confirm
        # the correct training's dataset is reflected, not positional.
        self.assertEqual(training_page.training_list.item(0).text(), "Apple")
        self.assertIn("Landscapes", training_page.dataset_label.text())

        training_manager.select(zebra.training_id)
        self.assertIn("Portraits", training_page.dataset_label.text())

    def test_refresh_after_second_creation_resorts_entire_list(self):

        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        _, dataset = self._setup_character_and_dataset(character_manager, dataset_manager)

        training_manager.create("Mango", dataset.dataset_id)
        training_manager.create("Zebra", dataset.dataset_id)
        training_manager.create("Apple", dataset.dataset_id)

        displayed = [
            training_page.training_list.item(i).text()
            for i in range(training_page.training_list.count())
        ]
        self.assertEqual(displayed, ["Apple", "Mango", "Zebra"])


class TrainingPageRenameTest(unittest.TestCase):
    """
    Mission 054: TrainingPage.name_edit — real-widget rename, mirroring
    PromptsPageRenameTest (Mission 053). training_list is sorted
    (Mission 051), so a rename must resort the list while keeping the
    selection on the renamed entity by training_id, never by position.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "TrainingRenameProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)
        training_page = TrainingPage(training_manager, dataset_manager, workspace_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in TRAINING_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)

        return event_bus, workspace_manager, character_manager, dataset_manager, training_manager, training_page

    def _setup_character_and_dataset(self, character_manager, dataset_manager):
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        return character, dataset

    def test_rename_via_widget_updates_manager_and_display(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        _, dataset = self._setup_character_and_dataset(character_manager, dataset_manager)

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        self.assertEqual(training_page.name_edit.text(), "Session 1")

        training_page.name_edit.setText("Session 1 Renamed")
        training_page.name_edit.editingFinished.emit()

        self.assertEqual(training_manager.active_training.name, "Session 1 Renamed")
        self.assertEqual(training_manager.active_training.training_id, training.training_id)
        self.assertEqual(training_manager.active_training.dataset_id, dataset.dataset_id)

    def test_rename_with_no_active_training_is_a_no_op(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        self._setup_character_and_dataset(character_manager, dataset_manager)

        training_page.name_edit.setText("Anything")
        training_page.name_edit.editingFinished.emit()

        self.assertIsNone(training_manager.active_training_id)

    def test_rename_moving_entity_to_front_keeps_correct_selection(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        _, dataset = self._setup_character_and_dataset(character_manager, dataset_manager)

        apple = training_manager.create("Apple", dataset.dataset_id)
        zebra = training_manager.create("Zebra", dataset.dataset_id)
        training_manager.select(zebra.training_id)

        training_page.name_edit.setText("Aardvark")
        training_page.name_edit.editingFinished.emit()

        displayed = [
            training_page.training_list.item(i).text()
            for i in range(training_page.training_list.count())
        ]
        self.assertEqual(displayed, ["Aardvark", "Apple"])
        self.assertEqual(training_manager.active_training_id, zebra.training_id)
        self.assertEqual(training_page.training_list.currentItem().data(Qt.UserRole), zebra.training_id)

    def test_rename_moving_entity_to_back_keeps_correct_selection(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        _, dataset = self._setup_character_and_dataset(character_manager, dataset_manager)

        apple = training_manager.create("Apple", dataset.dataset_id)
        zebra = training_manager.create("Zebra", dataset.dataset_id)
        training_manager.select(apple.training_id)

        training_page.name_edit.setText("Zzz")
        training_page.name_edit.editingFinished.emit()

        displayed = [
            training_page.training_list.item(i).text()
            for i in range(training_page.training_list.count())
        ]
        self.assertEqual(displayed, ["Zebra", "Zzz"])
        self.assertEqual(training_manager.active_training_id, apple.training_id)
        self.assertEqual(training_page.training_list.currentItem().data(Qt.UserRole), apple.training_id)

    def test_rename_persists_after_close_reopen_via_ui(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        _, dataset = self._setup_character_and_dataset(character_manager, dataset_manager)

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        training_page.name_edit.setText("Session 1 Renamed")
        training_page.name_edit.editingFinished.emit()

        workspace_manager.close()

        (_, workspace_manager_2, character_manager_2, dataset_manager_2,
         training_manager_2, training_page_2) = self._wire()
        workspace_manager_2.open(self.folder)

        restored_character = next(
            c for c in character_manager_2.characters if c.name == "Aria"
        )
        character_manager_2.select(restored_character.character_id)
        training_manager_2.select(training.training_id)

        restored = training_manager_2.active_training
        self.assertEqual(restored.name, "Session 1 Renamed")
        self.assertEqual(restored.training_id, training.training_id)
        self.assertEqual(restored.dataset_id, dataset.dataset_id)

    def test_rename_save_failure_shows_error_and_restores_widget_to_previous_name(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        _, dataset = self._setup_character_and_dataset(character_manager, dataset_manager)

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        training_page.name_edit.setText("Session 1 Renamed")
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.training_page.QMessageBox.critical") as critical_mock:
            training_page.name_edit.editingFinished.emit()

        self.assertTrue(critical_mock.called)
        self.assertEqual(training.name, "Session 1")
        self.assertEqual(training_page.name_edit.text(), "Session 1")
        self.assertEqual(training_page.training_list.currentItem().text(), "Session 1")

    def test_retry_after_rename_save_failure_actually_renames(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        _, dataset = self._setup_character_and_dataset(character_manager, dataset_manager)

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        training_page.name_edit.setText("Session 1 Renamed")
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.training_page.QMessageBox.critical"):
            training_page.name_edit.editingFinished.emit()

        training_page.name_edit.setText("Session 1 Renamed")
        training_page.name_edit.editingFinished.emit()

        self.assertEqual(training.name, "Session 1 Renamed")
        self.assertEqual(training_page.training_list.currentItem().text(), "Session 1 Renamed")


class TrainingManagerDeleteRollbackTest(unittest.TestCase):
    """
    Mission 068: TrainingManager.delete() rolls back the in-memory
    removal (and active_training_id) if save() fails — Domain-only
    mutation, so the rollback is a simple local re-insertion at the
    original index, never a full Workspace snapshot. dataset_id is
    never touched by delete() at all, so no separate rollback for it is
    needed.
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

        self.training_a = self.training_manager.create("Alpha", self.dataset.dataset_id)
        self.training_b = self.training_manager.create("Beta", self.dataset.dataset_id)
        self.training_c = self.training_manager.create("Gamma", self.dataset.dataset_id)
        self.training_manager.select(self.training_b.training_id)

    def test_delete_succeeds_normally_when_save_works(self):
        result = self.training_manager.delete(self.training_b.training_id)

        self.assertTrue(result)
        self.assertEqual(
            [t.training_id for t in self.training_manager.trainings],
            [self.training_a.training_id, self.training_c.training_id],
        )
        self.assertIsNone(self.training_manager.active_training_id)

    def test_delete_save_failure_restores_object_at_original_index(self):
        received = []
        self.event_bus.subscribe(TRAINING_DELETED, lambda payload: received.append(payload))

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.delete(self.training_b.training_id)

        trainings = self.training_manager.trainings
        self.assertEqual(
            [t.training_id for t in trainings],
            [self.training_a.training_id, self.training_b.training_id, self.training_c.training_id],
        )
        self.assertIs(trainings[1], self.training_b)
        self.assertEqual(self.training_b.dataset_id, self.dataset.dataset_id)
        self.assertEqual(received, [])

    def test_delete_save_failure_restores_active_training_id(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.delete(self.training_b.training_id)

        self.assertEqual(self.training_manager.active_training_id, self.training_b.training_id)

    def test_delete_save_failure_never_touches_an_unrelated_active_id(self):
        self.training_manager.select(self.training_a.training_id)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.delete(self.training_b.training_id)

        self.assertEqual(self.training_manager.active_training_id, self.training_a.training_id)

    def test_delete_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.delete(self.training_b.training_id)

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_after_save_failure_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.delete(self.training_b.training_id)

        result = self.training_manager.delete(self.training_b.training_id)

        self.assertTrue(result)
        self.assertEqual(
            [t.training_id for t in self.training_manager.trainings],
            [self.training_a.training_id, self.training_c.training_id],
        )


class TrainingPageDeleteConfirmationTest(unittest.TestCase):
    """
    Mission 062: TrainingPage.delete_training() now confirms before
    deleting, mirroring ImagesPage.delete_selected_images()'s
    established QMessageBox pattern (Mission 046) — Cancel is the safe
    default.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "TrainingDeleteProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)
        training_page = TrainingPage(training_manager, dataset_manager, workspace_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in TRAINING_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)

        return event_bus, workspace_manager, character_manager, dataset_manager, training_manager, training_page

    def _confirm_delete(self, accept: bool):
        patcher = patch("src.ui.pages.training_page.QMessageBox")
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
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)

        mock_cls = self._confirm_delete(accept=True)

        training_page.delete_training()

        mock_cls.assert_not_called()

    def test_delete_confirmed_removes_training(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        self._confirm_delete(accept=True)

        training_page.delete_training()

        self.assertIsNone(training_manager.active_training_id)
        self.assertEqual(training_manager.trainings, [])

    def test_delete_cancelled_calls_neither_manager_nor_mutates_state(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        self._confirm_delete(accept=False)

        with patch.object(training_manager, "delete") as delete_mock:
            training_page.delete_training()
            delete_mock.assert_not_called()

        self.assertEqual(training_manager.active_training_id, training.training_id)
        self.assertEqual(len(training_manager.trainings), 1)

    def test_delete_confirmed_save_failure_shows_error_and_keeps_the_training(self):
        """
        Mission 068: TrainingManager.delete() rolls back the Domain
        removal (and active_training_id) before re-raising on a save()
        failure — the Page must intercept WorkspaceManagerError, inform
        the user, and never present the deletion as successful.
        """
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        mock_cls = self._confirm_delete(accept=True)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            training_page.delete_training()

        mock_cls.critical.assert_called_once()
        self.assertEqual(training_manager.active_training_id, training.training_id)
        self.assertEqual(len(training_manager.trainings), 1)
        self.assertIs(training_manager.trainings[0], training)

    def test_retry_after_save_failure_actually_deletes(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        self._confirm_delete(accept=True)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            training_page.delete_training()

        self._confirm_delete(accept=True)
        training_page.delete_training()

        self.assertIsNone(training_manager.active_training_id)
        self.assertEqual(training_manager.trainings, [])


class TrainingPageDeleteButtonStateTest(unittest.TestCase):
    """
    Mission 063: "Supprimer" must always reflect whether there is
    currently a valid selection to act on, mirroring ImagesPage's
    established delete_button.setEnabled() pattern (Mission 046) —
    never a silent no-op behind an always-clickable button.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "TrainingButtonStateProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)
        training_page = TrainingPage(training_manager, dataset_manager, workspace_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in TRAINING_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)

        return workspace_manager, character_manager, dataset_manager, training_manager, training_page

    def test_disabled_before_any_workspace(self):
        _, _, _, _, training_page = self._wire()
        self.assertFalse(training_page.delete_button.isEnabled())

    def test_disabled_with_no_selection_then_enabled_on_select(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")

        self.assertFalse(training_page.delete_button.isEnabled())

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        self.assertTrue(training_page.delete_button.isEnabled())

    def test_deselecting_disables_delete_button(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)
        self.assertTrue(training_page.delete_button.isEnabled())

        training_page.training_list.setCurrentItem(None)

        self.assertFalse(training_page.delete_button.isEnabled())

    def test_delete_button_stays_consistent_after_list_rebuild(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        training_a = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training_a.training_id)
        self.assertTrue(training_page.delete_button.isEnabled())

        # TRAINING_CREATED triggers update_trainings() -> a full list
        # rebuild, while the active selection itself is untouched.
        training_manager.create("Session 2", dataset.dataset_id)

        self.assertTrue(training_page.delete_button.isEnabled())
        self.assertEqual(
            training_page.training_list.currentItem().data(Qt.UserRole), training_a.training_id
        )

    def test_disabled_after_workspace_closed(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)
        self.assertTrue(training_page.delete_button.isEnabled())

        workspace_manager.close()

        self.assertFalse(training_page.delete_button.isEnabled())

    def test_disabled_after_deleting_the_selected_training(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)
        self.assertTrue(training_page.delete_button.isEnabled())

        # TRAINING_DELETED triggers update_trainings() -> the button
        # must be recomputed from the resulting (now empty) selection.
        training_manager.delete(training.training_id)

        self.assertFalse(training_page.delete_button.isEnabled())


class TrainingPageOnetrainerParametersTest(unittest.TestCase):
    """
    Mission 097: TrainingPage's new generic-hyperparameter widgets, the
    "Enregistrer les paramètres d'entraînement" button
    (TrainingManager.update()), and the "Préparer la configuration
    OneTrainer" button (TrainingManager.prepare_onetrainer_config()) —
    real widgets throughout, QMessageBox/QFileDialog mocked (this
    mission never shows a real modal during automated tests, same
    discipline as every other page in this codebase).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "TrainingParamsProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)
        training_page = TrainingPage(training_manager, dataset_manager, workspace_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in TRAINING_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)

        return workspace_manager, character_manager, dataset_manager, training_manager, training_page

    def _create_selected_training(self, workspace_manager, character_manager, dataset_manager, training_manager):
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)
        return dataset, training

    def test_new_buttons_disabled_with_no_selection(self):
        _, _, _, _, training_page = self._wire()

        self.assertFalse(training_page.save_parameters_button.isEnabled())
        self.assertFalse(training_page.prepare_config_button.isEnabled())

    def test_new_buttons_enabled_once_a_training_is_selected(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)

        self.assertTrue(training_page.save_parameters_button.isEnabled())
        self.assertTrue(training_page.prepare_config_button.isEnabled())

    def test_architecture_change_suggests_the_matching_resolution(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)
        self.assertEqual(training_page.resolution_spinbox.value(), 512)

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)
        self.assertEqual(training_page.resolution_spinbox.value(), 1024)

    def test_reloading_a_saved_training_never_re_triggers_the_resolution_suggestion(self):
        # Mission 097: update_trainings() must blockSignals() on
        # architecture_combo while restoring a training's own saved
        # values — otherwise a stored, deliberately non-default
        # resolution would be silently overwritten by the suggestion.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        _, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_manager.update(architecture=TRAINING_ARCHITECTURE_SDXL, resolution=900)

        training_page.update_trainings()

        self.assertEqual(training_page.architecture_combo.currentText(), TRAINING_ARCHITECTURE_SDXL)
        self.assertEqual(training_page.resolution_spinbox.value(), 900)

    def test_save_button_persists_every_field_via_training_manager_update(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        _, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )

        training_page.base_model_edit.setText("/models/base.safetensors")
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)
        training_page.resolution_spinbox.setValue(1024)
        training_page.epochs_spinbox.setValue(30)
        training_page.learning_rate_spinbox.setValue(0.0007)
        training_page.lora_rank_spinbox.setValue(8)
        training_page.lora_alpha_spinbox.setValue(4.0)
        training_page.trigger_word_edit.setText("ohwx")

        training_page.save_training_parameters()

        self.assertEqual(training.base_model_source, "/models/base.safetensors")
        self.assertEqual(training.architecture, TRAINING_ARCHITECTURE_SDXL)
        self.assertEqual(training.resolution, 1024)
        self.assertEqual(training.epochs, 30)
        self.assertEqual(training.learning_rate, 0.0007)
        self.assertEqual(training.lora_rank, 8)
        self.assertEqual(training.lora_alpha, 4.0)
        self.assertEqual(training.trigger_word, "ohwx")

    def test_save_button_failure_shows_error_and_restores_widgets(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.trigger_word_edit.setText("ohwx")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.training_page.QMessageBox.critical") as mock_critical:
            training_page.save_training_parameters()
            mock_critical.assert_called_once()

        # update_trainings() (called on failure) redraws from the
        # rolled-back Domain state — never the invalid attempted value.
        self.assertEqual(training_page.trigger_word_edit.text(), "")

    def test_browse_base_model_source_sets_the_selected_path(self):
        _, _, _, _, training_page = self._wire()

        with patch(
            "src.ui.pages.training_page.QFileDialog.getOpenFileName",
            return_value=("/models/chosen.safetensors", ""),
        ):
            training_page.browse_base_model_source()

        self.assertEqual(training_page.base_model_edit.text(), "/models/chosen.safetensors")

    def test_browse_base_model_source_cancelled_leaves_the_field_untouched(self):
        _, _, _, _, training_page = self._wire()
        training_page.base_model_edit.setText("/already/set.safetensors")

        with patch(
            "src.ui.pages.training_page.QFileDialog.getOpenFileName",
            return_value=("", ""),
        ):
            training_page.browse_base_model_source()

        self.assertEqual(training_page.base_model_edit.text(), "/already/set.safetensors")

    def test_prepare_config_success_shows_the_three_paths_and_starts_no_training(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        dataset, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        image_path = Path(self.tmp_dir) / "a.png"
        image_path.write_bytes(b"fake")
        dataset.images = [Image(image_id="i1", file_path=str(image_path))]
        training_manager.update(architecture=TRAINING_ARCHITECTURE_SD15, resolution=512)

        with patch("src.ui.pages.training_page.QMessageBox.information") as mock_information:
            training_page.prepare_onetrainer_config()
            mock_information.assert_called_once()
            shown_text = mock_information.call_args.args[2]
            self.assertIn("training", shown_text.lower())
            self.assertIn("Aucun entraînement n'a été lancé", shown_text)

    def test_prepare_config_failure_shows_a_critical_message(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        dataset, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        # No images in the dataset -> TrainingPreparationError.

        with patch("src.ui.pages.training_page.QMessageBox.critical") as mock_critical:
            training_page.prepare_onetrainer_config()
            mock_critical.assert_called_once()

    def test_prepare_config_with_no_selection_is_a_no_op(self):
        _, _, _, _, training_page = self._wire()

        with patch("src.ui.pages.training_page.QMessageBox.information") as mock_information, \
                patch("src.ui.pages.training_page.QMessageBox.critical") as mock_critical:
            training_page.prepare_onetrainer_config()
            mock_information.assert_not_called()
            mock_critical.assert_not_called()


class TrainingManagerUpdateTest(unittest.TestCase):
    """
    Mission 097: TrainingManager.update() — same combined-multi-field,
    strictly idempotent, rollback-on-save-failure contract as
    LoRAManager.update() (Mission 073), adapted to act on
    self.active_training (this Manager's own existing convention,
    established by update_name()).
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
        self.training = self.training_manager.create("Session 1", self.dataset.dataset_id)
        self.training_manager.select(self.training.training_id)

    def test_update_sets_every_field(self):
        result = self.training_manager.update(
            base_model_source="/models/base.safetensors",
            architecture=TRAINING_ARCHITECTURE_SDXL,
            resolution=1024,
            epochs=50,
            learning_rate=0.0005,
            lora_rank=32,
            lora_alpha=2.0,
            trigger_word="ohwx",
        )

        self.assertTrue(result)
        self.assertEqual(self.training.base_model_source, "/models/base.safetensors")
        self.assertEqual(self.training.architecture, TRAINING_ARCHITECTURE_SDXL)
        self.assertEqual(self.training.resolution, 1024)
        self.assertEqual(self.training.epochs, 50)
        self.assertEqual(self.training.learning_rate, 0.0005)
        self.assertEqual(self.training.lora_rank, 32)
        self.assertEqual(self.training.lora_alpha, 2.0)
        self.assertEqual(self.training.trigger_word, "ohwx")

    def test_update_is_idempotent(self):
        self.training_manager.update(architecture=TRAINING_ARCHITECTURE_SD15, resolution=512)

        with patch.object(self.workspace_manager, "save", wraps=self.workspace_manager.save) as save_spy:
            result = self.training_manager.update(architecture=TRAINING_ARCHITECTURE_SD15, resolution=512)
            self.assertFalse(result)
            save_spy.assert_not_called()

            result = self.training_manager.update(resolution=768)
            self.assertTrue(result)
            save_spy.assert_called_once()

    def test_update_leaves_untouched_fields_alone(self):
        self.training_manager.update(trigger_word="ohwx")

        self.training_manager.update(epochs=10)

        self.assertEqual(self.training.trigger_word, "ohwx")

    def test_update_without_active_training_returns_false(self):
        self.training_manager.active_training_id = None

        result = self.training_manager.update(trigger_word="anything")

        self.assertFalse(result)

    def test_update_save_failure_restores_every_field_on_the_same_object(self):
        self.training_manager.update(architecture=TRAINING_ARCHITECTURE_SD15, resolution=512, trigger_word="x")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.update(architecture=TRAINING_ARCHITECTURE_SDXL, resolution=1024, trigger_word="y")

        self.assertEqual(self.training.architecture, TRAINING_ARCHITECTURE_SD15)
        self.assertEqual(self.training.resolution, 512)
        self.assertEqual(self.training.trigger_word, "x")
        self.assertIs(self.training_manager.active_training, self.training)


class TrainingManagerPrepareOnetrainerConfigTest(unittest.TestCase):
    """
    Mission 097: TrainingManager.prepare_onetrainer_config() — real
    filesystem materialization (never mocked for the nominal cases) and
    real config-file generation. Never starts OneTrainer, never imports
    OneTrainer's own code — see MISSION_097.md section 7/8.
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
        self.training = self.training_manager.create("Session 1", self.dataset.dataset_id)
        self.training_manager.select(self.training.training_id)
        self.training_manager.update(
            base_model_source="/models/v1-5-pruned.safetensors",
            architecture=TRAINING_ARCHITECTURE_SD15,
            resolution=512,
            trigger_word="ohwx",
        )

    def _add_real_image(self, subdir_name, filename, content=b"fake-png-bytes"):
        source_dir = Path(self.tmp_dir) / subdir_name
        source_dir.mkdir(parents=True, exist_ok=True)
        path = source_dir / filename
        path.write_bytes(content)
        return Image(image_id=str(path), file_path=str(path))

    def test_materializes_real_images_with_matching_caption_sidecars(self):
        self.dataset.images = [
            self._add_real_image("SourceA", "portrait1.png", b"AAA"),
            self._add_real_image("SourceB", "portrait2.png", b"BBB"),
        ]

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        concept_folder = Path(result.concept_path)
        produced = sorted(p.name for p in concept_folder.iterdir())
        self.assertEqual(produced, ["portrait1.png", "portrait1.txt", "portrait2.png", "portrait2.txt"])
        self.assertEqual((concept_folder / "portrait1.png").read_bytes(), b"AAA")
        self.assertEqual((concept_folder / "portrait1.txt").read_text(encoding="utf-8"), "ohwx")
        self.assertEqual((concept_folder / "portrait2.txt").read_text(encoding="utf-8"), "ohwx")

    def test_deterministic_paths_derived_from_workspace_and_training_id(self):
        self.dataset.images = [self._add_real_image("Source", "a.png")]

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        expected_root = self.folder / "training" / self.training.training_id
        self.assertEqual(Path(result.concept_path), expected_root / "concept")
        self.assertEqual(Path(result.config_path), expected_root / "onetrainer_config.json")
        self.assertEqual(Path(result.output_path), expected_root / "output" / "lora.safetensors")

    def test_no_absolute_path_is_ever_persisted_on_training_itself(self):
        self.dataset.images = [self._add_real_image("Source", "a.png")]

        self.training_manager.prepare_onetrainer_config(self.training.training_id)

        for value in vars(self.training).values():
            if isinstance(value, str):
                self.assertNotIn(str(self.folder), value)

    def test_collision_free_naming_for_two_sources_sharing_a_basename(self):
        # Mission 097 section 5/6: two distinct source images both
        # named "001.png" from different folders must never overwrite
        # each other in the materialized concept — reusing
        # WorkspaceStorage.resolve_collision_free_name() directly.
        self.dataset.images = [
            self._add_real_image("SourceA", "001.png", b"FROM_A"),
            self._add_real_image("SourceB", "001.png", b"FROM_B"),
        ]

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        concept_folder = Path(result.concept_path)
        produced = sorted(p.name for p in concept_folder.glob("*.png"))
        self.assertEqual(produced, ["001.png", "001_1.png"])
        contents = {(concept_folder / name).read_bytes() for name in produced}
        self.assertEqual(contents, {b"FROM_A", b"FROM_B"})
        # Every image has its own caption sidecar, collision-free too.
        self.assertTrue((concept_folder / "001.txt").exists())
        self.assertTrue((concept_folder / "001_1.txt").exists())

    def test_source_dataset_images_are_never_modified(self):
        image = self._add_real_image("Source", "a.png", b"ORIGINAL")
        self.dataset.images = [image]

        self.training_manager.prepare_onetrainer_config(self.training.training_id)

        self.assertEqual(Path(image.file_path).read_bytes(), b"ORIGINAL")
        # Only the materialized copy carries a caption — never the source.
        self.assertFalse(Path(image.file_path).with_suffix(".txt").exists())

    def test_rerunning_rebuilds_the_concept_from_the_current_dataset_state(self):
        # Mission 097 section 6: reproducible/cleanable — a stale prior
        # materialization must never linger once the Dataset changes.
        first_image = self._add_real_image("Source", "first.png")
        self.dataset.images = [first_image]
        self.training_manager.prepare_onetrainer_config(self.training.training_id)

        second_image = self._add_real_image("Source", "second.png")
        self.dataset.images = [second_image]
        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        concept_folder = Path(result.concept_path)
        produced = sorted(p.name for p in concept_folder.glob("*.png"))
        self.assertEqual(produced, ["second.png"])

    def test_config_file_reflects_the_real_materialized_concept_and_training_fields(self):
        self.dataset.images = [self._add_real_image("Source", "a.png")]

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        with open(result.config_path, encoding="utf-8") as f:
            config = json.load(f)

        self.assertEqual(config["training_method"], "LORA")
        self.assertEqual(config["model_type"], "STABLE_DIFFUSION_15")
        self.assertEqual(config["base_model_name"], "/models/v1-5-pruned.safetensors")
        self.assertEqual(config["resolution"], "512")
        self.assertEqual(config["output_model_destination"], result.output_path)
        self.assertEqual(config["concepts"], [{"name": "Session 1", "path": result.concept_path}])

    def test_unknown_training_id_raises_explicitly(self):
        with self.assertRaises(TrainingPreparationError):
            self.training_manager.prepare_onetrainer_config("does-not-exist")

    def test_dataset_with_no_images_raises_explicitly(self):
        self.dataset.images = []

        with self.assertRaises(TrainingPreparationError):
            self.training_manager.prepare_onetrainer_config(self.training.training_id)

    def test_dataset_no_longer_existing_raises_explicitly(self):
        self.dataset.images = [self._add_real_image("Source", "a.png")]
        self.character_manager.principal_character.datasets.remove(self.dataset)

        with self.assertRaises(TrainingPreparationError):
            self.training_manager.prepare_onetrainer_config(self.training.training_id)

    def test_invalid_architecture_raises_the_adapter_error(self):
        self.dataset.images = [self._add_real_image("Source", "a.png")]
        self.training.architecture = "POKEMON"

        with self.assertRaises(OneTrainerConfigError):
            self.training_manager.prepare_onetrainer_config(self.training.training_id)

    def test_never_imports_onetrainer_itself(self):
        # Mission 097 section 7/8: this Manager must never depend on
        # OneTrainer actually being installed — it only ever produces a
        # plain JSON file.
        source = Path(inspect.getfile(TrainingManager)).read_text(encoding="utf-8").lower()
        self.assertNotIn("import onetrainer", source)
        self.assertNotIn("trainer.start", source)
        self.assertNotIn("trainer.train", source)
        self.assertNotIn("subprocess", source)


if __name__ == "__main__":
    unittest.main()
