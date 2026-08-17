"""
Integration coverage for the Character lifecycle, exercising
CharacterManager, Workspace.characters, EventBus and the real
CharactersPage/DashboardPage/ImagesPage widgets together — the same
wiring MainWindow uses (see src/ui/main_window.py).
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

        # Mission 026: workspace creation auto-creates and auto-selects
        # a principal Character named after the project itself.
        principal_name = self.folder.name
        self.assertEqual(character_manager.active_character.name, principal_name)

        aria = character_manager.create("Aria")
        character_manager.create("Kai")

        self.assertEqual(
            [characters_page.list_widget.item(i).text()
             for i in range(characters_page.list_widget.count())],
            [principal_name, "Aria", "Kai"],
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

        # WORKSPACE_OPENED never auto-creates (Mission 026 decision) —
        # the persisted list is exactly principal + Aria + Kai.
        self.assertEqual(
            sorted(c.name for c in character_manager_2.characters),
            sorted([principal_name, "Aria", "Kai"]),
        )

        # Runtime-only per Mission 002 decision 2: selection does NOT
        # survive a restart, even though the character list does.
        self.assertIsNone(character_manager_2.active_character_id)

        self.assertEqual(
            sorted(characters_page_2.list_widget.item(i).text()
                   for i in range(characters_page_2.list_widget.count())),
            sorted([principal_name, "Aria", "Kai"]),
        )

    def test_delete_character_persists(self):

        workspace_manager, character_manager = self._wire()[1:3]
        workspace_manager.create(self.folder)
        # Mission 026: the principal Character auto-created on workspace
        # creation is not touched by this test — only Aria is deleted.
        principal_name = self.folder.name

        aria = character_manager.create("Aria")
        character_manager.create("Kai")

        character_manager.delete(aria.character_id)

        workspace_manager_2, character_manager_2 = self._wire()[1:3]
        workspace_manager_2.open(self.folder)

        self.assertEqual(
            sorted(c.name for c in character_manager_2.characters),
            sorted([principal_name, "Kai"]),
        )

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

        # Mission 026: the principal Character auto-created on workspace
        # creation was never touched — only "ToDelete" was removed.
        self.assertEqual(
            [c.name for c in character_manager_2.characters], [self.folder.name]
        )

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

        # WORKSPACE_CREATED -> rendered with exactly the auto-created
        # principal Character (Mission 026) — never empty anymore.
        workspace_manager.create(self.folder)
        principal_name = self.folder.name
        self.assertEqual(characters_page.list_widget.count(), 1)
        self.assertEqual(characters_page.list_widget.item(0).text(), principal_name)

        character_manager.create("Aria")
        character_manager.create("Kai")
        self.assertEqual(characters_page.list_widget.count(), 3)

        # WORKSPACE_CLOSED -> list cleared
        workspace_manager.close()
        self.assertEqual(characters_page.list_widget.count(), 0)

        # WORKSPACE_OPENED -> list rebuilt from the reopened workspace,
        # never auto-creating (Mission 026: CREATED-only).
        workspace_manager.open(self.folder)
        self.assertEqual(
            sorted(characters_page.list_widget.item(i).text()
                   for i in range(characters_page.list_widget.count())),
            sorted([principal_name, "Aria", "Kai"]),
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

        # Exactly 5 subscribers on WORKSPACE_CREATED: the 3 _wire()
        # registers directly (dashboard, images, characters_page) plus
        # CharacterManager's two own internal subscriptions — resetting
        # active_character_id (Commit 4), and auto-creating/selecting
        # the principal Character (Mission 026) — on EACH bus,
        # independently.
        self.assertEqual(len(event_bus_1._subscribers[WORKSPACE_CREATED]), 5)
        self.assertEqual(len(event_bus_2._subscribers[WORKSPACE_CREATED]), 5)
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

        # Each workspace creation auto-creates its own principal
        # Character (Mission 026); bus #2 additionally gets "Aria".
        self.assertEqual(characters_page_1.list_widget.count(), 1)
        self.assertEqual(characters_page_2.list_widget.count(), 2)


class CharacterIdentityDomainTest(unittest.TestCase):
    """
    Mission 026: Character gains six additive identity fields
    (bio/description/character_lock/personality/interests/trigger_token),
    all str, default "" — pure storage, consumed by nothing yet.
    """

    def test_identity_fields_default_to_empty_string(self):
        character = Character(character_id="c1", name="Aria")

        self.assertEqual(character.bio, "")
        self.assertEqual(character.description, "")
        self.assertEqual(character.character_lock, "")
        self.assertEqual(character.personality, "")
        self.assertEqual(character.interests, "")
        self.assertEqual(character.trigger_token, "")

    def test_to_dict_includes_identity_fields(self):
        character = Character(
            character_id="c1",
            name="Aria",
            bio="Born in a small town.",
            description="Tall, red hair.",
            character_lock="Always has green eyes and a scar on the left cheek.",
            personality="Curious, stubborn, kind.",
            interests="Astronomy, hiking, jazz.",
            trigger_token="ariaidentity",
        )

        data = character.to_dict()

        self.assertEqual(data["bio"], "Born in a small town.")
        self.assertEqual(data["description"], "Tall, red hair.")
        self.assertEqual(
            data["character_lock"], "Always has green eyes and a scar on the left cheek."
        )
        self.assertEqual(data["personality"], "Curious, stubborn, kind.")
        self.assertEqual(data["interests"], "Astronomy, hiking, jazz.")
        self.assertEqual(data["trigger_token"], "ariaidentity")

    def test_from_dict_restores_identity_fields(self):
        restored = Character.from_dict({
            "character_id": "c1",
            "name": "Aria",
            "bio": "Born in a small town.",
            "description": "Tall, red hair.",
            "character_lock": "Always has green eyes.",
            "personality": "Curious.",
            "interests": "Astronomy.",
            "trigger_token": "ariaidentity",
        })

        self.assertEqual(restored.bio, "Born in a small town.")
        self.assertEqual(restored.description, "Tall, red hair.")
        self.assertEqual(restored.character_lock, "Always has green eyes.")
        self.assertEqual(restored.personality, "Curious.")
        self.assertEqual(restored.interests, "Astronomy.")
        self.assertEqual(restored.trigger_token, "ariaidentity")

    def test_from_dict_legacy_character_without_identity_fields_defaults_to_empty_string(self):
        # A project.json written before Mission 026 never carried these
        # six keys — must load without exception, defaulting to "".
        legacy = Character.from_dict({"character_id": "c1", "name": "Aria"})

        self.assertEqual(legacy.bio, "")
        self.assertEqual(legacy.description, "")
        self.assertEqual(legacy.character_lock, "")
        self.assertEqual(legacy.personality, "")
        self.assertEqual(legacy.interests, "")
        self.assertEqual(legacy.trigger_token, "")


class CharacterManagerUpdateTest(unittest.TestCase):
    """
    Mission 026: CharacterManager.update() — idempotent identity/rename
    mechanism, same contract as PromptManager.update_text()/
    ApplicationSettingsManager.update(). Never publishes an event.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "IdentityProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        return event_bus, workspace_manager, character_manager

    def test_update_returns_false_for_unknown_character_id(self):
        _, workspace_manager, character_manager = self._wire()
        workspace_manager.create(self.folder)

        self.assertFalse(character_manager.update("does-not-exist", bio="Hello"))

    def test_update_is_idempotent_when_values_unchanged(self):
        _, workspace_manager, character_manager = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")

        character_manager.update(character.character_id, bio="Born in a small town.")

        self.assertFalse(
            character_manager.update(character.character_id, bio="Born in a small town.")
        )

    def test_update_changes_a_single_field_and_persists(self):
        _, workspace_manager, character_manager = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")

        result = character_manager.update(character.character_id, bio="Born in a small town.")

        self.assertTrue(result)
        self.assertEqual(character.bio, "Born in a small town.")

    def test_update_partial_fields_does_not_touch_others(self):
        _, workspace_manager, character_manager = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")

        character_manager.update(
            character.character_id, description="Tall, red hair.", personality="Curious."
        )
        character_manager.update(character.character_id, interests="Astronomy.")

        self.assertEqual(character.description, "Tall, red hair.")
        self.assertEqual(character.personality, "Curious.")
        self.assertEqual(character.interests, "Astronomy.")

    def test_update_empty_string_is_a_legitimate_value(self):
        _, workspace_manager, character_manager = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.update(character.character_id, bio="Something")

        result = character_manager.update(character.character_id, bio="")

        self.assertTrue(result)
        self.assertEqual(character.bio, "")

    def test_update_can_rename_the_character(self):
        _, workspace_manager, character_manager = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")

        result = character_manager.update(character.character_id, name="Aria Nightsong")

        self.assertTrue(result)
        self.assertEqual(character.name, "Aria Nightsong")

    def test_update_never_publishes_an_event(self):
        event_bus, workspace_manager, character_manager = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")

        events_seen = []
        for event_name in (CHARACTER_CREATED, CHARACTER_SELECTED, CHARACTER_DELETED):
            event_bus.subscribe(event_name, lambda payload, name=event_name: events_seen.append(name))

        character_manager.update(character.character_id, bio="Born in a small town.")

        self.assertEqual(events_seen, [])

    def test_identity_fields_persist_across_close_and_reopen(self):
        _, workspace_manager, character_manager = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")

        character_manager.update(
            character.character_id,
            name="Aria Nightsong",
            bio="Born in a small town.",
            description="Tall, red hair.",
            character_lock="Always has green eyes.",
            personality="Curious, stubborn, kind.",
            interests="Astronomy, hiking, jazz.",
            trigger_token="ariaidentity",
        )

        workspace_manager.close()

        _, workspace_manager_2, character_manager_2 = self._wire()
        workspace_manager_2.open(self.folder)

        # Mission 026: the workspace also holds the auto-created
        # principal Character (from the earlier workspace_manager.create()
        # call) — retrieve "Aria Nightsong" explicitly by id rather than
        # assuming list order/index.
        restored = next(
            c for c in character_manager_2.characters if c.character_id == character.character_id
        )
        self.assertEqual(restored.name, "Aria Nightsong")
        self.assertEqual(restored.bio, "Born in a small town.")
        self.assertEqual(restored.description, "Tall, red hair.")
        self.assertEqual(restored.character_lock, "Always has green eyes.")
        self.assertEqual(restored.personality, "Curious, stubborn, kind.")
        self.assertEqual(restored.interests, "Astronomy, hiking, jazz.")
        self.assertEqual(restored.trigger_token, "ariaidentity")

    def test_legacy_project_json_without_identity_fields_loads_without_exception(self):
        # Simulates a real pre-Mission-026 project.json: characters
        # carrying only character_id/name, no identity keys at all.
        workspace_manager = WorkspaceManager()
        workspace_manager.create(self.folder)

        raw = json.loads((self.folder / "project.json").read_text(encoding="utf-8"))
        raw["characters"] = [{"character_id": "legacy-1", "name": "Legacy"}]
        (self.folder / "project.json").write_text(json.dumps(raw), encoding="utf-8")

        _, workspace_manager_2, character_manager_2 = self._wire()
        result = workspace_manager_2.open(self.folder)

        self.assertIsNotNone(result)
        restored = character_manager_2.characters[0]
        self.assertEqual(restored.name, "Legacy")
        self.assertEqual(restored.bio, "")
        self.assertEqual(restored.description, "")
        self.assertEqual(restored.character_lock, "")
        self.assertEqual(restored.personality, "")
        self.assertEqual(restored.interests, "")
        self.assertEqual(restored.trigger_token, "")


class CharacterManagerAutoCreateDefaultTest(unittest.TestCase):
    """
    Mission 026 (post-smoke-test revision): a freshly created Workspace
    must not force a "New character" click before its identity fiche is
    usable — CharacterManager auto-creates and auto-selects exactly one
    principal Character, named from workspace.name, reacting to
    WORKSPACE_CREATED only (never WORKSPACE_OPENED — see
    test_workspace_opened_never_auto_creates for why).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Lauraya"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        return event_bus, workspace_manager, character_manager

    def test_workspace_created_with_empty_characters_creates_exactly_one(self):
        _, workspace_manager, character_manager = self._wire()

        workspace_manager.create(self.folder)

        self.assertEqual(len(character_manager.characters), 1)

    def test_auto_created_character_name_matches_workspace_name(self):
        _, workspace_manager, character_manager = self._wire()

        workspace_manager.create(self.folder)

        self.assertEqual(character_manager.characters[0].name, "Lauraya")
        self.assertEqual(character_manager.characters[0].name, workspace_manager.current_workspace.name)

    def test_auto_created_character_is_automatically_selected(self):
        _, workspace_manager, character_manager = self._wire()

        workspace_manager.create(self.folder)

        self.assertIsNotNone(character_manager.active_character_id)
        self.assertEqual(character_manager.active_character.name, "Lauraya")

    def test_auto_created_character_is_persisted_in_project_json(self):
        _, workspace_manager, character_manager = self._wire()
        workspace_manager.create(self.folder)

        raw = json.loads((self.folder / "project.json").read_text(encoding="utf-8"))

        self.assertEqual(len(raw["characters"]), 1)
        self.assertEqual(raw["characters"][0]["name"], "Lauraya")

    def test_no_double_creation_when_workspace_created_republished_on_non_empty_characters(self):
        event_bus, workspace_manager, character_manager = self._wire()
        workspace_manager.create(self.folder)
        self.assertEqual(len(character_manager.characters), 1)

        # Republishing WORKSPACE_CREATED on an already-populated
        # workspace must never create a second principal Character —
        # the guard checks workspace.characters, not "has this ever
        # fired before".
        event_bus.publish(WORKSPACE_CREATED, workspace_manager.current_workspace.to_dict())

        self.assertEqual(len(character_manager.characters), 1)

    def test_workspace_opened_never_auto_creates(self):
        _, workspace_manager, character_manager = self._wire()
        workspace_manager.create(self.folder)

        # A user can delete their only Character via the still-available
        # CRUD — this must be respected, not silently reversed on the
        # next open (Mission 026 decision 2).
        principal = character_manager.characters[0]
        character_manager.delete(principal.character_id)
        workspace_manager.close()

        _, workspace_manager_2, character_manager_2 = self._wire()
        workspace_manager_2.open(self.folder)

        self.assertEqual(character_manager_2.characters, [])

    def test_renaming_via_update_never_changes_workspace_name(self):
        _, workspace_manager, character_manager = self._wire()
        workspace_manager.create(self.folder)
        principal = character_manager.characters[0]

        character_manager.update(principal.character_id, name="Lauraya Nightborn")

        self.assertEqual(principal.name, "Lauraya Nightborn")
        self.assertEqual(workspace_manager.current_workspace.name, "Lauraya")


class CharactersPageIdentityFicheTest(unittest.TestCase):
    """
    Mission 026: CharactersPage's identity fiche — 5 visually separated
    sections (Identité/Apparence/Personnalité/Goûts et centres
    d'intérêt/Informations techniques IA), populated/cleared alongside
    the existing character list, never leaking values between two
    different selected characters.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "FicheProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        characters_page = CharactersPage(character_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, characters_page.update_characters)
        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, characters_page.update_characters)

        return event_bus, workspace_manager, character_manager, characters_page

    def test_identity_sections_exist(self):
        _, _, _, page = self._wire()

        for attribute in (
            "name_edit", "bio_edit", "description_edit", "character_lock_edit",
            "personality_edit", "interests_edit", "trigger_token_edit",
            "save_identity_button",
        ):
            self.assertTrue(hasattr(page, attribute), f"missing {attribute}")

    def test_save_identity_succeeds_on_fresh_workspace_without_any_manual_selection(self):
        # Reproduces the reported smoke-test scenario exactly: create a
        # Workspace, never click/select anything in CharactersPage, edit
        # the fiche, click "Enregistrer l'identité" — must succeed and
        # persist, since the principal Character is already the one and
        # only Character and should never require a manual re-selection
        # through a list that is not even visible anymore.
        _, workspace_manager, character_manager, page = self._wire()

        workspace_manager.create(self.folder)

        page.bio_edit.setPlainText("Born in a small town.")
        page.description_edit.setPlainText("Tall, red hair.")
        page.character_lock_edit.setPlainText("Always has green eyes.")
        page.personality_edit.setPlainText("Curious.")
        page.interests_edit.setPlainText("Astronomy.")
        page.trigger_token_edit.setText("laurayaidentity")

        with patch("src.ui.pages.characters_page.QMessageBox.warning") as mock_warning:
            page.save_identity()
            mock_warning.assert_not_called()

        principal = character_manager.characters[0]
        self.assertEqual(principal.bio, "Born in a small town.")
        self.assertEqual(principal.description, "Tall, red hair.")
        self.assertEqual(principal.character_lock, "Always has green eyes.")
        self.assertEqual(principal.personality, "Curious.")
        self.assertEqual(principal.interests, "Astronomy.")
        self.assertEqual(principal.trigger_token, "laurayaidentity")

    def test_save_identity_succeeds_even_if_active_character_id_was_lost(self):
        # Regression guard for the reported smoke-test failure: if
        # active_character_id ever ends up None (whatever the exact
        # trigger — the architect's real GUI run showed this happening
        # in practice) while the Workspace still holds its one and only
        # principal Character, save_identity() must still succeed rather
        # than show "Aucun personnage sélectionné" — CharactersPage now
        # represents that Character directly, it must not depend on the
        # historical active_character_id/list-selection mechanism to
        # know which Character its own fiche edits. FAILS before the
        # CharacterManager.principal_character fallback fix (with the
        # QMessageBox mocked so a real bug here reports as a failed
        # assertion, never as a hang — same precaution as every other
        # QMessageBox-adjacent test in this file/project).
        _, workspace_manager, character_manager, page = self._wire()
        workspace_manager.create(self.folder)

        character_manager.active_character_id = None

        page.bio_edit.setPlainText("Born in a small town.")

        with patch("src.ui.pages.characters_page.QMessageBox.warning") as mock_warning:
            page.save_identity()
            mock_warning.assert_not_called()

        principal = character_manager.characters[0]
        self.assertEqual(principal.bio, "Born in a small town.")

    def test_multi_character_controls_are_hidden_from_ui(self):
        # Mission 026 (UX revision): the list/"Nouveau personnage"/
        # "Supprimer" controls stay fully wired internally (the historical
        # multi-character tests in CharacterRoundTripTest still exercise
        # them directly) but must never be visible to the user — the
        # target UX is "1 Workspace = 1 principal Character", never a
        # list to manage. isHidden() (not isVisible()) is the correct
        # check here: isVisible() would be False regardless simply
        # because the top-level Page is never shown in this headless
        # test, while isHidden() specifically reflects an explicit
        # setVisible(False) call.
        _, _, _, page = self._wire()

        self.assertTrue(page.list_widget.isHidden())
        self.assertTrue(page.new_button.isHidden())
        self.assertTrue(page.delete_button.isHidden())

    def test_fiche_is_immediately_populated_on_new_workspace_without_any_click(self):
        # Mission 026 (post-smoke-test revision): the exact UX the
        # architect required — create a project, open Characters, the
        # fiche is already there with the project's name, no "New
        # character" click needed.
        _, workspace_manager, character_manager, page = self._wire()

        workspace_manager.create(self.folder)

        self.assertEqual(page.list_widget.count(), 1)
        self.assertEqual(page.name_edit.text(), self.folder.name)

    def test_identity_panel_cleared_when_no_character_exists_at_all(self):
        # Mission 026 (post-smoke-test revision): principal_character_id
        # now falls back to the first Character whenever one exists, so
        # a mere "nothing actively selected" state (e.g. right after
        # close/reopen) no longer leaves the fiche empty — that fallback
        # is the whole point of the fix. The fiche is only genuinely
        # empty when the Workspace has zero Characters at all, which can
        # only happen if the user explicitly deletes the principal one
        # via the still-available internal CRUD.
        _, workspace_manager, character_manager, page = self._wire()
        workspace_manager.create(self.folder)

        principal = character_manager.characters[0]
        character_manager.delete(principal.character_id)

        self.assertEqual(page.name_edit.text(), "")
        self.assertEqual(page.bio_edit.toPlainText(), "")
        self.assertEqual(page.trigger_token_edit.text(), "")

    def test_identity_panel_populated_on_selection(self):
        _, workspace_manager, character_manager, page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.update(
            character.character_id,
            bio="Born in a small town.",
            description="Tall, red hair.",
            character_lock="Always has green eyes.",
            personality="Curious.",
            interests="Astronomy.",
            trigger_token="ariaidentity",
        )

        character_manager.select(character.character_id)

        self.assertEqual(page.name_edit.text(), "Aria")
        self.assertEqual(page.bio_edit.toPlainText(), "Born in a small town.")
        self.assertEqual(page.description_edit.toPlainText(), "Tall, red hair.")
        self.assertEqual(page.character_lock_edit.toPlainText(), "Always has green eyes.")
        self.assertEqual(page.personality_edit.toPlainText(), "Curious.")
        self.assertEqual(page.interests_edit.toPlainText(), "Astronomy.")
        self.assertEqual(page.trigger_token_edit.text(), "ariaidentity")

    def test_save_identity_without_any_character_shows_warning(self):
        # Mission 026 (post-smoke-test revision): the warning path now
        # only triggers when the Workspace genuinely has zero Characters
        # (see test_identity_panel_cleared_when_no_character_exists_at_all
        # for why a mere "nothing actively selected" state no longer
        # qualifies, now that principal_character_id falls back to the
        # first Character).
        _, workspace_manager, character_manager, page = self._wire()
        workspace_manager.create(self.folder)

        principal = character_manager.characters[0]
        character_manager.delete(principal.character_id)

        with patch("src.ui.pages.characters_page.QMessageBox.warning") as mock_warning:
            page.save_identity()
            mock_warning.assert_called_once()

    def test_save_identity_calls_manager_update_with_entered_values(self):
        _, workspace_manager, character_manager, page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        page.name_edit.setText("Aria Nightsong")
        page.bio_edit.setPlainText("Born in a small town.")
        page.description_edit.setPlainText("Tall, red hair.")
        page.character_lock_edit.setPlainText("Always has green eyes.")
        page.personality_edit.setPlainText("Curious.")
        page.interests_edit.setPlainText("Astronomy.")
        page.trigger_token_edit.setText("ariaidentity")

        page.save_identity()

        self.assertEqual(character.name, "Aria Nightsong")
        self.assertEqual(character.bio, "Born in a small town.")
        self.assertEqual(character.description, "Tall, red hair.")
        self.assertEqual(character.character_lock, "Always has green eyes.")
        self.assertEqual(character.personality, "Curious.")
        self.assertEqual(character.interests, "Astronomy.")
        self.assertEqual(character.trigger_token, "ariaidentity")

    def test_switching_selected_character_refreshes_identity_panel_without_leaking_values(self):
        _, workspace_manager, character_manager, page = self._wire()
        workspace_manager.create(self.folder)

        aria = character_manager.create("Aria")
        character_manager.update(aria.character_id, bio="Aria's bio.")
        kai = character_manager.create("Kai")
        character_manager.update(kai.character_id, bio="Kai's bio.")

        character_manager.select(aria.character_id)
        self.assertEqual(page.bio_edit.toPlainText(), "Aria's bio.")

        character_manager.select(kai.character_id)
        self.assertEqual(page.bio_edit.toPlainText(), "Kai's bio.")
        self.assertNotEqual(page.bio_edit.toPlainText(), "Aria's bio.")

    def test_renaming_via_identity_panel_updates_list_widget_label(self):
        _, workspace_manager, character_manager, page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        page.name_edit.setText("Aria Nightsong")
        page.save_identity()

        self.assertEqual(page.list_widget.currentItem().text(), "Aria Nightsong")


class CharacterIdentityArchitecturalConstraintsTest(unittest.TestCase):
    """
    Mission 026: bio/description/character_lock/personality/interests/
    trigger_token are pure storage in this mission — no generation/
    Inference code may reference them yet (consumption is explicitly
    deferred), same pattern as Mission 024's anti-"denoise" test.
    """

    def test_generation_code_never_references_identity_fields(self):
        forbidden_terms = (
            "character_lock", "trigger_token", "personality", "interests", "bio",
        )
        source_paths = [
            Path("src/managers/generation_manager.py"),
            Path("src/engines/comfyui_engine.py"),
            Path("src/engines/workflows/comfyui_workflows.py"),
            Path("src/ui/pages/inference_page.py"),
        ]

        for path in source_paths:
            source = path.read_text(encoding="utf-8").lower()
            for term in forbidden_terms:
                self.assertNotIn(
                    term, source, f"{term!r} must not leak into {path} in Mission 026"
                )


if __name__ == "__main__":
    unittest.main()
