import uuid
from typing import List, Optional

from src.core.event_bus import EventBus
from src.domain.model import Model
from src.managers.workspace_manager import (
    WorkspaceManager,
    WorkspaceManagerError,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_CLOSED,
)

MODEL_CREATED = "model.created"
MODEL_SELECTED = "model.selected"
MODEL_DELETED = "model.deleted"


class ModelManager:
    """
    Coordinates Model CRUD, selection and file path editing within the
    current Workspace. Unlike DatasetManager/LoRAManager/PromptManager,
    Model is owned by the Workspace, not the active Character (per the
    Blueprint — see Mission 006's architecture audit), so this Manager
    has no dependency on CharacterManager at all. Operates exclusively
    on workspace_manager.current_workspace.models — never touches
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

        # Runtime-only, like DatasetManager.active_dataset_id /
        # LoRAManager.active_lora_id / PromptManager.active_prompt_id —
        # never persisted.
        self.active_model_id: Optional[str] = None

        # Only a workspace switch resets active_model_id — there is no
        # CHARACTER_SELECTED/CHARACTER_DELETED subscription here, since
        # Model has no relationship to the active character at all.
        if self._event_bus is not None:
            self._event_bus.subscribe(WORKSPACE_CREATED, self._on_context_changed)
            self._event_bus.subscribe(WORKSPACE_OPENED, self._on_context_changed)
            self._event_bus.subscribe(WORKSPACE_CLOSED, self._on_context_changed)

    def _on_context_changed(self, payload) -> None:
        self.active_model_id = None

    @property
    def models(self) -> List[Model]:
        workspace = self._workspace_manager.current_workspace
        if workspace is None:
            return []
        return workspace.models

    def list_models(self) -> List[dict]:
        return [model.to_dict() for model in self.models]

    @property
    def active_model(self) -> Optional[Model]:
        if self.active_model_id is None:
            return None
        return self._find(self.active_model_id)

    def create(self, name: str) -> Optional[Model]:

        workspace = self._workspace_manager.current_workspace

        if workspace is None:
            return None

        model = Model(model_id=str(uuid.uuid4()), name=name)

        workspace.models.append(model)

        self._workspace_manager.save()

        self._publish(MODEL_CREATED, model)

        return model

    def select(self, model_id: str) -> Optional[Model]:

        model = self._find(model_id)

        if model is None:
            return None

        self.active_model_id = model.model_id

        self._publish(MODEL_SELECTED, model)

        return model

    def delete(self, model_id: str) -> bool:
        """
        Mission 068: if save() fails after the Model has already been
        removed from workspace.models, the deletion is rolled back
        before the exception is re-raised — the same Model object is
        reinserted at its original index, and active_model_id (if it
        pointed at this Model) is restored to its previous value.
        Domain-only mutation, no filesystem involved, so a local
        rollback is sufficient — no snapshot of the wider Workspace is
        needed.
        """

        workspace = self._workspace_manager.current_workspace

        if workspace is None:
            return False

        model = self._find(model_id)

        if model is None:
            return False

        index = workspace.models.index(model)
        previous_active_model_id = self.active_model_id

        workspace.models.remove(model)

        if self.active_model_id == model_id:
            self.active_model_id = None

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError:
            workspace.models.insert(index, model)
            self.active_model_id = previous_active_model_id
            raise

        self._publish(MODEL_DELETED, model)

        return True

    def update_file_path(self, file_path: str) -> bool:
        """
        Replace the active model's file_path. Mirrors
        PromptManager.update_text()'s exact contract: a single scalar
        edited in place, strictly idempotent. Returns False (no save(),
        no event) if there is no active model or if `file_path` is
        identical to the stored value. An empty string is a legitimate
        value ("no file associated yet") — not validated or rejected.
        """

        model = self.active_model

        if model is None:
            return False

        if model.file_path == file_path:
            return False

        old_file_path = model.file_path
        model.file_path = file_path

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError:
            model.file_path = old_file_path
            raise

        return True

    def update_name(self, name: str) -> bool:
        """
        Rename the active model. Mirrors update_file_path()'s exact
        contract: a single scalar edited in place, strictly idempotent.
        Returns False (no save()) if there is no active model or if
        `name` is identical to the stored value. Not validated (empty
        string legitimate, no stripping) — same convention already used
        by CharacterManager.update(name=...) when called from
        CharactersPage.save_identity().
        """

        model = self.active_model

        if model is None:
            return False

        if model.name == name:
            return False

        old_name = model.name
        model.name = name

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError:
            model.name = old_name
            raise

        return True

    def _find(self, model_id: str) -> Optional[Model]:
        for model in self.models:
            if model.model_id == model_id:
                return model
        return None

    def _publish(self, event_name: str, model: Model) -> None:

        if self._event_bus is None:
            return

        self._event_bus.publish(event_name, model.to_dict())
