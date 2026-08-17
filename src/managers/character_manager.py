import uuid
from typing import List, Optional

from src.core.event_bus import EventBus
from src.domain.character import Character
from src.managers.workspace_manager import (
    WorkspaceManager,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_CLOSED,
)

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

        # A workspace switch (create/open/close) must never leave
        # active_character_id pointing at a character from a different
        # (or no longer open) workspace.
        if self._event_bus is not None:
            self._event_bus.subscribe(WORKSPACE_CREATED, self._on_workspace_changed)
            self._event_bus.subscribe(WORKSPACE_OPENED, self._on_workspace_changed)
            self._event_bus.subscribe(WORKSPACE_CLOSED, self._on_workspace_changed)
            self._event_bus.subscribe(WORKSPACE_CREATED, self._ensure_default_character)

    def _on_workspace_changed(self, payload) -> None:
        self.active_character_id = None

    def _ensure_default_character(self, payload) -> None:
        """
        Mission 026: a freshly created Workspace should not force a
        "New character" click before its identity fiche is usable —
        exactly one principal Character is created and selected, named
        from workspace.name (the project's own name, already set by
        WorkspaceManager.create()), so CharactersPage shows a populated
        fiche immediately. Deliberately WORKSPACE_CREATED-only, never
        WORKSPACE_OPENED — reopening a legacy/emptied workspace must
        never silently resurrect a character a user may have deleted on
        purpose (no reliable way to distinguish the two cases today).
        Only fires when workspace.characters is empty, so it never
        interferes with an existing multi-character workspace.
        """

        workspace = self._workspace_manager.current_workspace

        if workspace is None or workspace.characters:
            return

        character = self.create(workspace.name)
        self.select(character.character_id)

    @property
    def characters(self) -> List[Character]:
        workspace = self._workspace_manager.current_workspace

        if workspace is None:
            return []

        return workspace.characters

    def list_characters(self) -> List[dict]:
        # Dict-shaped read surface for the Presentation layer — pages
        # must never depend on the Character domain class directly,
        # same principle as Workspace.to_dict() feeding DashboardPage/
        # ImagesPage.
        return [character.to_dict() for character in self.characters]

    @property
    def active_character(self) -> Optional[Character]:
        if self.active_character_id is None:
            return None

        return self._find(self.active_character_id)

    @property
    def principal_character(self) -> Optional[Character]:
        """
        Mission 026 (post-smoke-test revision): the Character
        CharactersPage's identity fiche actually edits. Prefers
        active_character when it resolves to a real Character (keeps
        the historical multi-character selection mechanism fully
        authoritative whenever it is genuinely in use — e.g. every
        multi-character test in this project explicitly calls select()
        first). Falls back to the first Character in the Workspace
        otherwise — the auto-created principal is always created before
        any other Character can exist (Mission 026 decision 1), so this
        fallback is never ambiguous for the "1 Workspace = 1 principal
        Character" target UX, and CharactersPage no longer exposes any
        UI to lose that selection in the first place. This decouples
        the fiche from depending on active_character_id staying valid
        through the full lifetime of a session, per the architect's own
        stated principle: CharactersPage now represents the Workspace's
        Character directly, not an item picked from a visible list.
        """
        character = self.active_character
        if character is not None:
            return character

        characters = self.characters
        return characters[0] if characters else None

    @property
    def principal_character_id(self) -> Optional[str]:
        # Dict/id-shaped counterpart to principal_character, for the
        # Presentation layer — CharactersPage must never depend on the
        # Character Domain class directly (same rule already followed
        # by list_characters() vs. self.characters).
        character = self.principal_character
        return character.character_id if character is not None else None

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

    def update(
        self,
        character_id: str,
        name: Optional[str] = None,
        bio: Optional[str] = None,
        description: Optional[str] = None,
        character_lock: Optional[str] = None,
        personality: Optional[str] = None,
        interests: Optional[str] = None,
        trigger_token: Optional[str] = None,
    ) -> bool:
        """
        Updates the identity fiche of a Character (Mission 026) — name
        included, so a rename and an identity edit share the exact same
        idempotent mechanism instead of a separate rename flow. Strictly
        idempotent, same contract as PromptManager.update_text()/
        ApplicationSettingsManager.update(): a field left as None is
        untouched, an empty string is a legitimate value distinct from
        "not provided", and no save()/event fires unless something
        actually changed.
        """

        character = self._find(character_id)

        if character is None:
            return False

        changed = (
            (name is not None and name != character.name)
            or (bio is not None and bio != character.bio)
            or (description is not None and description != character.description)
            or (character_lock is not None and character_lock != character.character_lock)
            or (personality is not None and personality != character.personality)
            or (interests is not None and interests != character.interests)
            or (trigger_token is not None and trigger_token != character.trigger_token)
        )

        if not changed:
            return False

        if name is not None:
            character.name = name
        if bio is not None:
            character.bio = bio
        if description is not None:
            character.description = description
        if character_lock is not None:
            character.character_lock = character_lock
        if personality is not None:
            character.personality = personality
        if interests is not None:
            character.interests = interests
        if trigger_token is not None:
            character.trigger_token = trigger_token

        self._workspace_manager.save()

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
