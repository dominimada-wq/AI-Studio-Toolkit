"""
Integration coverage for the Workflow lifecycle, exercising
WorkflowManager, Workspace.workflows, EventBus and the real
DashboardPage/CharactersPage/ImagesPage/WorkflowsPage widgets together
— the same wiring MainWindow uses. Also covers the Workflow domain
object's own to_dict()/from_dict() round-trip and default-value
behavior directly, since Workflow is a new entity introduced this
mission.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from src.core.event_bus import EventBus
from src.domain.workflow import Workflow
from src.domain.workspace import Workspace
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
from src.managers.workflow_manager import (
    WorkflowManager,
    WORKFLOW_CREATED,
    WORKFLOW_SELECTED,
    WORKFLOW_DELETED,
)
from src.ui.pages.dashboard_page import DashboardPage
from src.ui.pages.characters_page import CharactersPage
from src.ui.pages.images_page import ImagesPage
from src.ui.pages.workflows_page import WorkflowsPage

WORKSPACE_EVENTS = (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_SAVED, WORKSPACE_CLOSED)
CHARACTER_EVENTS = (CHARACTER_CREATED, CHARACTER_SELECTED, CHARACTER_DELETED)
WORKFLOW_EVENTS = (WORKFLOW_CREATED, WORKFLOW_SELECTED, WORKFLOW_DELETED)

_app = QApplication.instance() or QApplication([])


class WorkflowRoundTripTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "WorkflowProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        workflow_manager = WorkflowManager(workspace_manager, event_bus=event_bus)

        dashboard = DashboardPage()
        characters_page = CharactersPage(character_manager)
        images = ImagesPage(workspace_manager)
        workflows_page = WorkflowsPage(workflow_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, dashboard.update_project)
            event_bus.subscribe(event_name, images.update_images)
            event_bus.subscribe(event_name, characters_page.update_characters)
            event_bus.subscribe(event_name, workflows_page.update_workflows)

        # Deliberately NOT subscribing workflows_page to CHARACTER_* events —
        # Workflow is Workspace-owned, mirrors main_window.py's real wiring.
        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, characters_page.update_characters)

        for event_name in WORKFLOW_EVENTS:
            event_bus.subscribe(event_name, workflows_page.update_workflows)

        return (
            event_bus, workspace_manager, character_manager, workflow_manager,
            dashboard, characters_page, images, workflows_page,
        )

    def test_workflow_domain_object_roundtrip_and_defaults(self):

        # Default values.
        workflow = Workflow()
        self.assertEqual(workflow.workflow_id, "")
        self.assertEqual(workflow.name, "")
        self.assertEqual(workflow.file_path, "")
        self.assertEqual(
            workflow.to_dict(),
            {"workflow_id": "", "name": "", "file_path": ""},
        )

        # Round-trip without loss of information.
        original = Workflow(workflow_id="abc", name="ComfyFlow", file_path="C:/wf/flow.json")
        restored = Workflow.from_dict(original.to_dict())
        self.assertEqual(original, restored)

        # Missing key -> default, consistent with every other Domain object.
        self.assertEqual(Workflow.from_dict({}), Workflow())
        self.assertEqual(Workflow.from_dict({"name": "Only Name"}).file_path, "")

        # Historical compatibility: an old project.json predating Mission
        # 007 never had a "workflows" key at all.
        self.assertEqual(Workspace.from_dict({}).workflows, [])
        self.assertEqual(Workspace.from_dict({"workflows": []}).workflows, [])
        self.assertEqual(Workspace.from_dict({"workflows": None}).workflows, [])

        # Workspace.workflows: mixed list[dict|str|None|int] -> only dict
        # entries survive, same defensive-compatibility principle already
        # applied to Character.datasets/loras/prompts and Workspace.models.
        mixed = Workspace.from_dict({
            "workflows": [
                {"workflow_id": "W1", "name": "Workflow 1", "file_path": "a.json"},
                "invalid",
                None,
                42,
                {"workflow_id": "W2", "name": "Workflow 2"},
            ]
        })
        self.assertEqual(len(mixed.workflows), 2)
        self.assertTrue(all(isinstance(w, Workflow) for w in mixed.workflows))
        self.assertEqual(mixed.workflows[0].workflow_id, "W1")
        self.assertEqual(mixed.workflows[0].file_path, "a.json")
        self.assertEqual(mixed.workflows[1].workflow_id, "W2")
        self.assertEqual(mixed.workflows[1].file_path, "")

    def test_full_create_select_edit_save_close_reopen_cycle(self):

        (event_bus, workspace_manager, character_manager, workflow_manager,
         dashboard, characters_page, images, workflows_page) = self._wire()

        workspace_manager.create(self.folder)

        workflow = workflow_manager.create("ComfyFlow")
        workflow_manager.select(workflow.workflow_id)
        changed = workflow_manager.update_file_path("C:/wf/comfy_flow.json")
        self.assertTrue(changed)

        self.assertEqual(
            workflows_page.file_path_edit.text(),
            "C:/wf/comfy_flow.json",
        )

        workspace_manager.close()

        self.assertIsNone(workflow_manager.active_workflow_id)
        self.assertEqual(workflows_page.workflow_list.count(), 0)

        # Reopen with a second _wire() call — fresh instances, simulating
        # a real application restart rather than reusing in-memory state.
        # Real disk round-trip via WorkspaceManager, no mock.
        (event_bus_2, workspace_manager_2, character_manager_2, workflow_manager_2,
         dashboard_2, characters_page_2, images_2, workflows_page_2) = self._wire()

        workspace_manager_2.open(self.folder)

        # Runtime-only per Mission 002-007 decisions: active_workflow_id
        # does not survive a restart. No character selection is involved
        # here at all — Workflow is Workspace-owned.
        self.assertIsNone(workflow_manager_2.active_workflow_id)

        self.assertEqual(len(workflow_manager_2.workflows), 1)
        restored_workflow = workflow_manager_2.workflows[0]
        self.assertEqual(restored_workflow.workflow_id, workflow.workflow_id)
        self.assertEqual(restored_workflow.name, "ComfyFlow")
        self.assertEqual(restored_workflow.file_path, "C:/wf/comfy_flow.json")

    def test_update_file_path_is_idempotent(self):

        event_bus, workspace_manager, character_manager, workflow_manager = self._wire()[:4]
        workspace_manager.create(self.folder)
        workflow = workflow_manager.create("ComfyFlow")
        workflow_manager.select(workflow.workflow_id)

        events_seen = []
        for event_name in WORKFLOW_EVENTS:
            event_bus.subscribe(event_name, lambda payload, name=event_name: events_seen.append(name))

        # No active workflow at all: False, no save().
        workflow_manager.active_workflow_id = None
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertFalse(workflow_manager.update_file_path("irrelevant"))
            save_spy.assert_not_called()

        workflow_manager.select(workflow.workflow_id)
        events_seen.clear()  # select() above legitimately publishes workflow.selected

        # First real change: True, save() called, no workflow.* event.
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertTrue(workflow_manager.update_file_path("C:/wf/a.json"))
            save_spy.assert_called_once()
        self.assertEqual(workflow_manager.active_workflow.file_path, "C:/wf/a.json")
        self.assertEqual(events_seen, [])

        # Identical value again: False, save() NOT called, no workflow.* event.
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertFalse(workflow_manager.update_file_path("C:/wf/a.json"))
            save_spy.assert_not_called()
        self.assertEqual(events_seen, [])

        # Empty string is a legitimate value ("no file yet"): a real
        # change from a non-empty value, so True + save().
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertTrue(workflow_manager.update_file_path(""))
            save_spy.assert_called_once()
        self.assertEqual(workflow_manager.active_workflow.file_path, "")

    def test_delete_active_workflow_resets_selection_and_persists(self):

        _, workspace_manager, character_manager, workflow_manager = self._wire()[:4]
        workspace_manager.create(self.folder)

        keep = workflow_manager.create("Keep")
        drop = workflow_manager.create("Drop")
        workflow_manager.select(drop.workflow_id)

        result = workflow_manager.delete(drop.workflow_id)
        self.assertTrue(result)
        self.assertIsNone(workflow_manager.active_workflow_id)
        self.assertIsNone(workflow_manager.active_workflow)
        self.assertEqual([w.name for w in workflow_manager.workflows], ["Keep"])

        # Persists: reopening shows only the surviving workflow.
        _, workspace_manager_2, character_manager_2, workflow_manager_2 = self._wire()[:4]
        workspace_manager_2.open(self.folder)
        self.assertEqual([w.name for w in workflow_manager_2.workflows], ["Keep"])

    def test_workflow_manager_context_reset_on_workspace_change_only(self):

        _, workspace_manager, character_manager, workflow_manager = self._wire()[:4]
        workspace_manager.create(self.folder)

        workflow = workflow_manager.create("ComfyFlow")
        workflow_manager.select(workflow.workflow_id)
        self.assertEqual(workflow_manager.active_workflow_id, workflow.workflow_id)

        # A character switch must NEVER reset active_workflow_id — Workflow
        # has no relationship to the active character at all, unlike
        # Dataset/LoRA/Prompt. This is the inverted invariant specific to
        # Workspace-owned resources (already validated for Model).
        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)
        self.assertEqual(
            workflow_manager.active_workflow_id, workflow.workflow_id,
            "a character switch must never affect active_workflow_id (Workflow is Workspace-owned)",
        )

        kai = character_manager.create("Kai")
        character_manager.select(kai.character_id)
        character_manager.delete(kai.character_id)
        self.assertEqual(workflow_manager.active_workflow_id, workflow.workflow_id)

        # A workspace close still resets it.
        workspace_manager.close()
        self.assertIsNone(workflow_manager.active_workflow_id)

    def test_workflows_page_rebuilds_on_relevant_events(self):

        (_, workspace_manager, character_manager, workflow_manager,
         _dashboard, _characters_page, _images, workflows_page) = self._wire()

        workspace_manager.create(self.folder)
        self.assertEqual(workflows_page.workflow_list.count(), 0)

        workflow = workflow_manager.create("ComfyFlow")
        self.assertEqual(workflows_page.workflow_list.count(), 1)

        workflow_manager.select(workflow.workflow_id)
        workflow_manager.update_file_path("C:/wf/a.json")
        # update_file_path() only publishes workspace.saved — this is what
        # WorkflowsPage's subscription to it must catch.
        self.assertEqual(workflows_page.file_path_edit.text(), "C:/wf/a.json")

        # Character activity must never rebuild WorkflowsPage's data away.
        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)
        self.assertEqual(workflows_page.workflow_list.count(), 1)
        self.assertEqual(workflows_page.file_path_edit.text(), "C:/wf/a.json")

        workspace_manager.close()
        self.assertEqual(workflows_page.workflow_list.count(), 0)
        self.assertEqual(workflows_page.file_path_edit.text(), "")

    def test_no_duplicate_subscriptions_between_wire_calls(self):

        wired_1 = self._wire()
        wired_2 = self._wire()

        for obj_1, obj_2 in zip(wired_1, wired_2):
            self.assertIsNot(obj_1, obj_2)

        event_bus_1, event_bus_2 = wired_1[0], wired_2[0]

        # 4 subscribers registered directly by _wire() (dashboard, images,
        # characters_page, workflows_page) + CharacterManager's own internal
        # reset subscription + WorkflowManager's own internal reset
        # subscription = 6, on EACH bus independently.
        self.assertEqual(len(event_bus_1._subscribers[WORKSPACE_CREATED]), 6)
        self.assertEqual(len(event_bus_2._subscribers[WORKSPACE_CREATED]), 6)
        self.assertTrue(
            set(event_bus_1._subscribers[WORKSPACE_CREATED]).isdisjoint(
                event_bus_2._subscribers[WORKSPACE_CREATED]
            )
        )

    def test_dashboard_and_images_unaffected_by_workflow_events(self):

        (_, workspace_manager, character_manager, workflow_manager,
         dashboard, _characters_page, images, _workflows_page) = self._wire()

        workspace_manager.create(self.folder)

        before_dashboard = dashboard.projectCard.value.text()
        before_images_count = images.list_widget.count()

        workflow_manager.create("ComfyFlow")

        self.assertEqual(dashboard.projectCard.value.text(), before_dashboard)
        self.assertEqual(images.list_widget.count(), before_images_count)

    def test_workflow_operations_do_not_mutate_other_workspace_collections(self):

        _, workspace_manager, character_manager, workflow_manager = self._wire()[:4]
        workspace_manager.create(self.folder)

        workspace = workspace_manager.current_workspace
        models_before = list(workspace.models)
        datasets_before = list(workspace.datasets)
        loras_before = list(workspace.loras)
        characters_before = list(workspace.characters)

        workflow = workflow_manager.create("ComfyFlow")
        workflow_manager.select(workflow.workflow_id)
        workflow_manager.update_file_path("C:/wf/a.json")
        workflow_manager.delete(workflow.workflow_id)

        self.assertEqual(workspace.models, models_before)
        self.assertEqual(workspace.datasets, datasets_before)
        self.assertEqual(workspace.loras, loras_before)
        self.assertEqual(workspace.characters, characters_before)


if __name__ == "__main__":
    unittest.main()
