import uuid
from typing import List, Optional

from src.core.event_bus import EventBus
from src.domain.character import Character
from src.managers.workspace_manager import WorkspaceManager

CHARACTER_CREATED = "character.created"
CHARACTER_SELECTED = "character.selected"
CHARACTER_DELETED = "character.deleted"


class CharacterManager:
    """
    Coordinates Character CRUD and selection within the current
    workspace. Operates exclusively on
    workspace_manager.current_workspace.characters — never touches
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

        # Runtime-only, like WorkspaceManager.current_workspace.root —
        # never persisted (Mission 002 decision 2).
        self.active_character_id: Optional[str] = None

    @property
    def characters(self) -> List[Character]:
        workspace = self._workspace_manager.current_workspace

        if workspace is None:
            return []

        return workspace.characters

    @property
    def active_character(self) -> Optional[Character]:
        if self.active_character_id is None:
            return None

        return self._find(self.active_character_id)

    def create(self, name: str) -> Optional[Character]:

        workspace = self._workspace_manager.current_workspace

        if workspace is None:
            return None

        character = Character(character_id=str(uuid.uuid4()), name=name)

        workspace.characters.append(character)

        self._workspace_manager.save()

        self._publish(CHARACTER_CREATED, character)

        return character

    def select(self, character_id: str) -> Optional[Character]:

        character = self._find(character_id)

        if character is None:
            return None

        self.active_character_id = character.character_id

        self._publish(CHARACTER_SELECTED, character)

        return character

    def delete(self, character_id: str) -> bool:

        workspace = self._workspace_manager.current_workspace

        if workspace is None:
            return False

        character = self._find(character_id)

        if character is None:
            return False

        workspace.characters.remove(character)

        if self.active_character_id == character_id:
            self.active_character_id = None

        self._workspace_manager.save()

        self._publish(CHARACTER_DELETED, character)

        return True

    def _find(self, character_id: str) -> Optional[Character]:
        for character in self.characters:
            if character.character_id == character_id:
                return character
        return None

    def _publish(self, event_name: str, character: Character) -> None:

        if self._event_bus is None:
            return

        self._event_bus.publish(event_name, character.to_dict())
