import uuid
from typing import List, Optional

from src.core.event_bus import EventBus
from src.domain.workflow import Workflow
from src.managers.workspace_manager import (
    WorkspaceManager,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_CLOSED,
)

WORKFLOW_CREATED = "workflow.created"
WORKFLOW_SELECTED = "workflow.selected"
WORKFLOW_DELETED = "workflow.deleted"


class WorkflowManager:
    """
    Coordinates Workflow CRUD, selection and file path editing within
    the current Workspace. Like ModelManager, Workflow is owned by the
    Workspace, not the active Character (Mission 007's architecture
    audit), so this Manager has no dependency on CharacterManager at
    all. Operates exclusively on
    workspace_manager.current_workspace.workflows — never touches
    storage or Qt directly; persistence is delegated to
    WorkspaceManager.save().
    """

    def __init__(
        self,
        workspace_manager: WorkspaceManager,
        event_bus: Optional[EventBus] = None,
    ):
        self._workspace_manager = workspace_manager
        self._event_bus = event_bus

        # Runtime-only, like ModelManager.active_model_id — never
        # persisted.
        self.active_workflow_id: Optional[str] = None

        # Only a workspace switch resets active_workflow_id — there is
        # no CHARACTER_SELECTED/CHARACTER_DELETED subscription here,
        # since Workflow has no relationship to the active character
        # at all.
        if self._event_bus is not None:
            self._event_bus.subscribe(WORKSPACE_CREATED, self._on_context_changed)
            self._event_bus.subscribe(WORKSPACE_OPENED, self._on_context_changed)
            self._event_bus.subscribe(WORKSPACE_CLOSED, self._on_context_changed)

    def _on_context_changed(self, payload) -> None:
        self.active_workflow_id = None

    @property
    def workflows(self) -> List[Workflow]:
        workspace = self._workspace_manager.current_workspace
        if workspace is None:
            return []
        return workspace.workflows

    def list_workflows(self) -> List[dict]:
        return [workflow.to_dict() for workflow in self.workflows]

    @property
    def active_workflow(self) -> Optional[Workflow]:
        if self.active_workflow_id is None:
            return None
        return self._find(self.active_workflow_id)

    def create(self, name: str) -> Optional[Workflow]:

        workspace = self._workspace_manager.current_workspace

        if workspace is None:
            return None

        workflow = Workflow(workflow_id=str(uuid.uuid4()), name=name)

        workspace.workflows.append(workflow)

        self._workspace_manager.save()

        self._publish(WORKFLOW_CREATED, workflow)

        return workflow

    def select(self, workflow_id: str) -> Optional[Workflow]:

        workflow = self._find(workflow_id)

        if workflow is None:
            return None

        self.active_workflow_id = workflow.workflow_id

        self._publish(WORKFLOW_SELECTED, workflow)

        return workflow

    def delete(self, workflow_id: str) -> bool:

        workspace = self._workspace_manager.current_workspace

        if workspace is None:
            return False

        workflow = self._find(workflow_id)

        if workflow is None:
            return False

        workspace.workflows.remove(workflow)

        if self.active_workflow_id == workflow_id:
            self.active_workflow_id = None

        self._workspace_manager.save()

        self._publish(WORKFLOW_DELETED, workflow)

        return True

    def update_file_path(self, file_path: str) -> bool:
        """
        Replace the active workflow's file_path. Mirrors
        ModelManager.update_file_path()'s exact contract: a single
        scalar edited in place, strictly idempotent. Returns False (no
        save(), no event) if there is no active workflow or if
        `file_path` is identical to the stored value. An empty string
        is a legitimate value — not validated or rejected.
        """

        workflow = self.active_workflow

        if workflow is None:
            return False

        if workflow.file_path == file_path:
            return False

        workflow.file_path = file_path

        self._workspace_manager.save()

        return True

    def _find(self, workflow_id: str) -> Optional[Workflow]:
        for workflow in self.workflows:
            if workflow.workflow_id == workflow_id:
                return workflow
        return None

    def _publish(self, event_name: str, workflow: Workflow) -> None:

        if self._event_bus is None:
            return

        self._event_bus.publish(event_name, workflow.to_dict())
