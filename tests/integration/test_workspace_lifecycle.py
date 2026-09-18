"""
Mission 137: create_workspace_with_default_character() is the sole
product-level operation that guarantees "a created Workspace always has
a usable principal Character" (Mission 026/036) — WorkspaceManager.create()
alone no longer does, since Mission 136 made EventBus.publish() never
re-raise a subscriber's exception, silently defeating the old implicit
guarantee. These tests lock the orchestrator's own contract directly,
independent of any Page/EventBus wiring: materialize the Workspace,
create+select the Character, publish WORKSPACE_CREATED only once that
invariant holds — and on any failure before that point, roll back
completely and never announce a Workspace that doesn't (or won't) exist.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.event_bus import EventBus
from src.infrastructure.storage.workspace_storage import WorkspaceStorage, WorkspaceStorageError
from src.managers.character_manager import CharacterManager, CHARACTER_CREATED, CHARACTER_SELECTED
from src.managers.workspace_manager import (
    WorkspaceManager,
    WorkspaceManagerError,
    WORKSPACE_CREATED,
    WORKSPACE_SAVED,
)
from src.managers.workspace_lifecycle import create_workspace_with_default_character


class WorkspaceLifecycleSuccessTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        return event_bus, workspace_manager, character_manager

    def test_workspace_created_and_principal_character_created_and_selected(self):
        _, workspace_manager, character_manager = self._wire()

        workspace = create_workspace_with_default_character(
            workspace_manager, character_manager, self.folder
        )

        self.assertIs(workspace, workspace_manager.current_workspace)
        self.assertEqual(len(character_manager.characters), 1)
        self.assertEqual(character_manager.characters[0].name, self.folder.name)
        self.assertEqual(character_manager.active_character_id, character_manager.characters[0].character_id)

    def test_exact_event_order_on_success(self):
        event_bus, workspace_manager, character_manager = self._wire()
        order = []
        for event_name in (WORKSPACE_SAVED, CHARACTER_CREATED, CHARACTER_SELECTED, WORKSPACE_CREATED):
            event_bus.subscribe(event_name, lambda payload, name=event_name: order.append(name))

        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

        self.assertEqual(order, [WORKSPACE_SAVED, CHARACTER_CREATED, CHARACTER_SELECTED, WORKSPACE_CREATED])

    def test_workspace_created_subscribers_see_the_character_already_in_place(self):
        # Locks the entire point of deferring WORKSPACE_CREATED: every
        # one of its subscribers must already observe a fully complete
        # Workspace, never a transient 0-Character state.
        event_bus, workspace_manager, character_manager = self._wire()
        observed = {}

        def on_workspace_created(payload):
            observed["character_count"] = len(character_manager.characters)
            observed["active_character_id"] = character_manager.active_character_id

        event_bus.subscribe(WORKSPACE_CREATED, on_workspace_created)

        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

        self.assertEqual(observed["character_count"], 1)
        self.assertIsNotNone(observed["active_character_id"])

    def test_workspace_manager_create_alone_still_works_without_character_manager(self):
        # Mission 137: WorkspaceManager.create() keeps its historical
        # contract unchanged — it must still materialize and publish
        # WORKSPACE_CREATED on its own, with no CharacterManager
        # involved at all, exactly as before this mission.
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        received = []
        event_bus.subscribe(WORKSPACE_CREATED, lambda payload: received.append(payload))

        workspace = workspace_manager.create(self.folder)

        self.assertIs(workspace, workspace_manager.current_workspace)
        self.assertEqual(len(received), 1)
        self.assertEqual(workspace.characters, [])


class WorkspaceLifecycleFailureTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        return event_bus, workspace_manager, character_manager

    @staticmethod
    def _fail_on_second_save(message="disk full"):
        # The first WorkspaceStorage.save() call belongs to
        # create_without_publishing() (materializing the Workspace
        # itself, must succeed so there is something real to roll back);
        # the second belongs to CharacterManager.create() (the failure
        # this whole class exercises).
        real_save = WorkspaceStorage.save
        calls = {"count": 0}

        def side_effect(folder, data):
            calls["count"] += 1
            if calls["count"] >= 2:
                raise WorkspaceStorageError(message)
            return real_save(folder, data)

        return patch.object(WorkspaceStorage, "save", side_effect=side_effect)

    def test_character_creation_failure_raises_workspace_manager_error(self):
        _, workspace_manager, character_manager = self._wire()

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

    def test_workspace_created_is_never_published_on_failure(self):
        event_bus, workspace_manager, character_manager = self._wire()
        received = []
        event_bus.subscribe(WORKSPACE_CREATED, lambda payload: received.append(payload))

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

        self.assertEqual(received, [])

    def test_filesystem_is_cleaned_up_on_failure(self):
        _, workspace_manager, character_manager = self._wire()

        with self._fail_on_second_save():
            with self.assertRaises(WorkspaceManagerError):
                create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

        self.assertFalse(self.folder.exists())

    def test_domain_has_no_character_left_after_failure(self):
        _, workspace_manager, character_manager = self._wire()

        with self._fail_on_second_save():
            with self.assertRaises(WorkspaceManagerError):
                create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

        self.assertEqual(character_manager.characters, [])

    def test_current_workspace_restored_to_none_when_none_before(self):
        _, workspace_manager, character_manager = self._wire()
        self.assertIsNone(workspace_manager.current_workspace)

        with self._fail_on_second_save():
            with self.assertRaises(WorkspaceManagerError):
                create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

        self.assertIsNone(workspace_manager.current_workspace)

    def test_current_workspace_restored_to_the_previous_one_when_it_existed(self):
        _, workspace_manager, character_manager = self._wire()
        previous_folder = Path(self.tmp_dir) / "PreviousProject"
        previous_workspace = create_workspace_with_default_character(
            workspace_manager, character_manager, previous_folder
        )

        new_folder = Path(self.tmp_dir) / "NewProject"
        with self._fail_on_second_save():
            with self.assertRaises(WorkspaceManagerError):
                create_workspace_with_default_character(workspace_manager, character_manager, new_folder)

        self.assertIs(workspace_manager.current_workspace, previous_workspace)
        self.assertEqual(workspace_manager.current_workspace.root, previous_folder)

    def test_no_zombie_workspace_folder_survives_a_failure(self):
        _, workspace_manager, character_manager = self._wire()

        with self._fail_on_second_save():
            with self.assertRaises(WorkspaceManagerError):
                create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

        self.assertFalse((self.folder / "project.json").exists())
        self.assertFalse(self.folder.exists())

    def test_primary_cause_is_preserved_when_cleanup_also_fails(self):
        _, workspace_manager, character_manager = self._wire()

        with self._fail_on_second_save(), \
                patch.object(WorkspaceStorage, "delete_folder", side_effect=WorkspaceStorageError("locked")):
            with self.assertRaises(WorkspaceManagerError) as ctx:
                create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

        message = str(ctx.exception)
        self.assertIn("disk full", message)

    def test_cleanup_failure_is_also_diagnosed_without_replacing_the_primary_cause(self):
        _, workspace_manager, character_manager = self._wire()

        with self._fail_on_second_save(), \
                patch.object(WorkspaceStorage, "delete_folder", side_effect=WorkspaceStorageError("locked")):
            with self.assertRaises(WorkspaceManagerError) as ctx:
                create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

        message = str(ctx.exception)
        self.assertIn("disk full", message)
        self.assertIn("cleaned up", message)
        self.assertIn(str(self.folder), message)
        # Mission 134/LoRALibraryManager.import_lora() idiom: the cause
        # chain always points to the primary failure (the
        # WorkspaceManagerError raised by CharacterManager.create()'s
        # own save() failure), never to the cleanup failure itself.
        self.assertIsInstance(ctx.exception.__cause__, WorkspaceManagerError)
        self.assertEqual(str(ctx.exception.__cause__), "disk full")

    def test_invariant_does_not_depend_on_any_eventbus_exception(self):
        # Mission 136/137: the guarantee must hold purely through the
        # orchestrator's own explicit control flow — never by relying on
        # EventBus.publish() propagating a subscriber's exception (which
        # it never does, by design, since Mission 136). A dummy failing
        # subscriber on an unrelated event proves EventBus's own
        # continue-and-log policy is untouched and irrelevant here.
        event_bus, workspace_manager, character_manager = self._wire()

        def unrelated_failing_subscriber(payload):
            raise RuntimeError("unrelated subscriber failure")

        event_bus.subscribe(CHARACTER_CREATED, unrelated_failing_subscriber)

        with self.assertLogs("src.core.event_bus", level="ERROR"):
            workspace = create_workspace_with_default_character(
                workspace_manager, character_manager, self.folder
            )

        self.assertEqual(len(character_manager.characters), 1)
        self.assertIs(workspace, workspace_manager.current_workspace)


if __name__ == "__main__":
    unittest.main()
