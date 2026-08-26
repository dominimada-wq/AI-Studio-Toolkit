import uuid
from typing import List, Optional

from src.core.event_bus import EventBus
from src.domain.prompt import Prompt
from src.managers.character_manager import (
    CharacterManager,
    CHARACTER_SELECTED,
    CHARACTER_DELETED,
)
from src.managers.workspace_manager import (
    WorkspaceManager,
    WorkspaceManagerError,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_CLOSED,
)

PROMPT_CREATED = "prompt.created"
PROMPT_SELECTED = "prompt.selected"
PROMPT_DELETED = "prompt.deleted"


class PromptManager:
    """
    Coordinates Prompt CRUD, selection and text editing within the
    Workspace's principal Character (Mission 026/028/029). Operates
    exclusively on character_manager.principal_character.prompts —
    never touches storage or Qt directly; persistence is delegated to
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

        # Runtime-only, like DatasetManager.active_dataset_id /
        # LoRAManager.active_lora_id — never persisted.
        self.active_prompt_id: Optional[str] = None

        # A character switch (selection or deletion) or a workspace
        # switch must never leave active_prompt_id pointing at a prompt
        # that no longer belongs to the active character.
        if self._event_bus is not None:
            self._event_bus.subscribe(CHARACTER_SELECTED, self._on_context_changed)
            self._event_bus.subscribe(CHARACTER_DELETED, self._on_context_changed)
            self._event_bus.subscribe(WORKSPACE_CREATED, self._on_context_changed)
            self._event_bus.subscribe(WORKSPACE_OPENED, self._on_context_changed)
            self._event_bus.subscribe(WORKSPACE_CLOSED, self._on_context_changed)

    def _on_context_changed(self, payload) -> None:
        self.active_prompt_id = None

    @property
    def prompts(self) -> List[Prompt]:
        # Mission 029: reads principal_character, not active_character —
        # same fix already applied to DatasetManager in Mission 028 (see
        # its property's docstring for the full rationale). Any Workspace
        # opened via WORKSPACE_OPENED (as opposed to freshly created)
        # otherwise leaves active_character_id at None for the whole
        # session, since CharactersPage never calls select() anymore.
        character = self._character_manager.principal_character
        if character is None:
            return []
        return character.prompts

    def list_prompts(self) -> List[dict]:
        return [prompt.to_dict() for prompt in self.prompts]

    @property
    def active_prompt(self) -> Optional[Prompt]:
        if self.active_prompt_id is None:
            return None
        return self._find(self.active_prompt_id)

    def create(self, name: str, text: str = "") -> Optional[Prompt]:
        """
        text defaults to "" — existing callers (PromptsPage.create_prompt())
        are entirely unaffected. Mission 031: lets a caller create an
        already-filled Prompt in one call, without going through
        select()/update_text() afterward — which would change
        active_prompt_id and publish PROMPT_SELECTED, a side effect
        InferencePage's "Enregistrer dans Prompts" must not trigger
        (it must never silently change PromptsPage's current selection).
        """

        character = self._character_manager.principal_character

        if character is None:
            return None

        prompt = Prompt(prompt_id=str(uuid.uuid4()), name=name, text=text)

        character.prompts.append(prompt)

        self._workspace_manager.save()

        self._publish(PROMPT_CREATED, prompt)

        return prompt

    def select(self, prompt_id: str) -> Optional[Prompt]:

        prompt = self._find(prompt_id)

        if prompt is None:
            return None

        self.active_prompt_id = prompt.prompt_id

        self._publish(PROMPT_SELECTED, prompt)

        return prompt

    def delete(self, prompt_id: str) -> bool:
        """
        Mission 071: if save() fails after the Prompt has already been
        removed from character.prompts, the deletion is rolled back
        before the exception is re-raised — the same Prompt object is
        reinserted at its original index, and active_prompt_id (if it
        pointed at this Prompt) is restored to its previous value.
        Domain-only mutation, no filesystem involved, so a local
        rollback is sufficient — mirrors DatasetManager.delete()/
        LoRAManager.delete()/ModelManager.delete()/
        TrainingManager.delete()/WorkflowManager.delete() (Mission 068),
        a family this method was inadvertently left out of.
        """

        character = self._character_manager.principal_character

        if character is None:
            return False

        prompt = self._find(prompt_id)

        if prompt is None:
            return False

        index = character.prompts.index(prompt)
        previous_active_prompt_id = self.active_prompt_id

        character.prompts.remove(prompt)

        if self.active_prompt_id == prompt_id:
            self.active_prompt_id = None

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError:
            character.prompts.insert(index, prompt)
            self.active_prompt_id = previous_active_prompt_id
            raise

        self._publish(PROMPT_DELETED, prompt)

        return True

    def update_text(self, text: str) -> bool:
        """
        Replace the active prompt's text. Unlike DatasetManager.add_images()/
        LoRAManager.add_files(), there is nothing to accumulate or
        deduplicate — text is a single scalar, edited in place. Strictly
        idempotent: returns False (no save(), no event) if there is no
        active prompt or if `text` is identical to the stored value.
        """

        prompt = self.active_prompt

        if prompt is None:
            return False

        if prompt.text == text:
            return False

        old_text = prompt.text
        prompt.text = text

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError:
            prompt.text = old_text
            raise

        return True

    def update_name(self, name: str) -> bool:
        """
        Rename the active prompt. Mirrors update_text()'s exact
        contract: a single scalar edited in place, strictly idempotent.
        Returns False (no save()) if there is no active prompt or if
        `name` is identical to the stored value. Not validated (empty
        string legitimate, no stripping) — same convention already used
        by CharacterManager.update(name=...)/ModelManager.update_name()/
        WorkflowManager.update_name()/LoRAManager.update_name() (Mission
        052). Never touches `text`.
        """

        prompt = self.active_prompt

        if prompt is None:
            return False

        if prompt.name == name:
            return False

        old_name = prompt.name
        prompt.name = name

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError:
            prompt.name = old_name
            raise

        return True

    def _find(self, prompt_id: str) -> Optional[Prompt]:
        for prompt in self.prompts:
            if prompt.prompt_id == prompt_id:
                return prompt
        return None

    def _publish(self, event_name: str, prompt: Prompt) -> None:

        if self._event_bus is None:
            return

        self._event_bus.publish(event_name, prompt.to_dict())
