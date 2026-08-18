import uuid
from typing import List, Optional

from src.core.event_bus import EventBus
from src.domain.lora import LoRA
from src.managers.character_manager import (
    CharacterManager,
    CHARACTER_SELECTED,
    CHARACTER_DELETED,
)
from src.managers.workspace_manager import (
    WorkspaceManager,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_CLOSED,
)

LORA_CREATED = "lora.created"
LORA_SELECTED = "lora.selected"
LORA_DELETED = "lora.deleted"


class LoRAManager:
    """
    Coordinates LoRA CRUD, selection and file import within the
    Workspace's principal Character (Mission 026/028/029). Operates
    exclusively on character_manager.principal_character.loras — never
    touches storage or Qt directly; persistence is delegated to
    WorkspaceManager.save().
    """

    def __init__(
        self,
        character_manager: CharacterManager,
        workspace_manager: WorkspaceManager,
        event_bus: Optional[EventBus] = None,
    ):
        self._character_manager = character_manager
        self._workspace_manager = workspace_manager
        self._event_bus = event_bus

        # Runtime-only, like DatasetManager.active_dataset_id — never
        # persisted.
        self.active_lora_id: Optional[str] = None

        # A character switch (selection or deletion) or a workspace
        # switch must never leave active_lora_id pointing at a LoRA
        # that no longer belongs to the active character.
        if self._event_bus is not None:
            self._event_bus.subscribe(CHARACTER_SELECTED, self._on_context_changed)
            self._event_bus.subscribe(CHARACTER_DELETED, self._on_context_changed)
            self._event_bus.subscribe(WORKSPACE_CREATED, self._on_context_changed)
            self._event_bus.subscribe(WORKSPACE_OPENED, self._on_context_changed)
            self._event_bus.subscribe(WORKSPACE_CLOSED, self._on_context_changed)

    def _on_context_changed(self, payload) -> None:
        self.active_lora_id = None

    @property
    def loras(self) -> List[LoRA]:
        # Mission 029: reads principal_character, not active_character —
        # same fix already applied to DatasetManager in Mission 028 (see
        # its property's docstring for the full rationale). Any Workspace
        # opened via WORKSPACE_OPENED (as opposed to freshly created)
        # otherwise leaves active_character_id at None for the whole
        # session, since CharactersPage never calls select() anymore.
        character = self._character_manager.principal_character
        if character is None:
            return []
        return character.loras

    def list_loras(self) -> List[dict]:
        return [lora.to_dict() for lora in self.loras]

    @property
    def active_lora(self) -> Optional[LoRA]:
        if self.active_lora_id is None:
            return None
        return self._find(self.active_lora_id)

    def create(self, name: str) -> Optional[LoRA]:

        character = self._character_manager.principal_character

        if character is None:
            return None

        lora = LoRA(lora_id=str(uuid.uuid4()), name=name)

        character.loras.append(lora)

        self._workspace_manager.save()

        self._publish(LORA_CREATED, lora)

        return lora

    def select(self, lora_id: str) -> Optional[LoRA]:

        lora = self._find(lora_id)

        if lora is None:
            return None

        self.active_lora_id = lora.lora_id

        self._publish(LORA_SELECTED, lora)

        return lora

    def delete(self, lora_id: str) -> bool:

        character = self._character_manager.principal_character

        if character is None:
            return False

        lora = self._find(lora_id)

        if lora is None:
            return False

        character.loras.remove(lora)

        if self.active_lora_id == lora_id:
            self.active_lora_id = None

        self._workspace_manager.save()

        self._publish(LORA_DELETED, lora)

        return True

    def add_files(self, paths: List[str]) -> int:
        """
        Append paths not already present in the active LoRA's files.
        Returns the number of files actually added — mirrors
        DatasetManager.add_images()'s dedup contract exactly, operating
        on active_lora the same way.
        """

        lora = self.active_lora

        if lora is None:
            return 0

        seen = set(lora.files)
        new_paths = []

        for path in paths:
            if path in seen:
                continue
            seen.add(path)
            new_paths.append(path)

        if not new_paths:
            return 0

        lora.files.extend(new_paths)

        self._workspace_manager.save()

        return len(new_paths)

    def _find(self, lora_id: str) -> Optional[LoRA]:
        for lora in self.loras:
            if lora.lora_id == lora_id:
                return lora
        return None

    def _publish(self, event_name: str, lora: LoRA) -> None:

        if self._event_bus is None:
            return

        self._event_bus.publish(event_name, lora.to_dict())
