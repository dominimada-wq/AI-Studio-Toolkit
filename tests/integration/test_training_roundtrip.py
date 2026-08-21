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
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
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


if __name__ == "__main__":
    unittest.main()
