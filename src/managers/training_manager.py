import uuid
from typing import List, Optional

from src.core.event_bus import EventBus
from src.domain.training import Training
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

TRAINING_CREATED = "training.created"
TRAINING_SELECTED = "training.selected"
TRAINING_DELETED = "training.deleted"


class TrainingManager:
    """
    Coordinates Training CRUD and selection within the active
    Character. Operates exclusively on
    character_manager.active_character.trainings — never touches
    storage or Qt directly; persistence is delegated to
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
        # LoRAManager.active_lora_id / PromptManager.active_prompt_id —
        # never persisted.
        self.active_training_id: Optional[str] = None

        # A character switch (selection or deletion) or a workspace
        # switch must never leave active_training_id pointing at a
        # training that no longer belongs to the active character.
        if self._event_bus is not None:
            self._event_bus.subscribe(CHARACTER_SELECTED, self._on_context_changed)
            self._event_bus.subscribe(CHARACTER_DELETED, self._on_context_changed)
            self._event_bus.subscribe(WORKSPACE_CREATED, self._on_context_changed)
            self._event_bus.subscribe(WORKSPACE_OPENED, self._on_context_changed)
            self._event_bus.subscribe(WORKSPACE_CLOSED, self._on_context_changed)

    def _on_context_changed(self, payload) -> None:
        self.active_training_id = None

    @property
    def trainings(self) -> List[Training]:
        character = self._character_manager.active_character
        if character is None:
            return []
        return character.trainings

    def list_trainings(self) -> List[dict]:
        return [training.to_dict() for training in self.trainings]

    @property
    def active_training(self) -> Optional[Training]:
        if self.active_training_id is None:
            return None
        return self._find(self.active_training_id)

    def create(self, name: str, dataset_id: str) -> Optional[Training]:

        character = self._character_manager.active_character

        if character is None:
            return None

        # The active Character's own datasets are the sole authority —
        # never a workspace-wide search. A dataset_id belonging to
        # another Character is indistinguishable from an unknown one.
        if not any(dataset.dataset_id == dataset_id for dataset in character.datasets):
            return None

        training = Training(
            training_id=str(uuid.uuid4()), name=name, dataset_id=dataset_id
        )

        character.trainings.append(training)

        self._workspace_manager.save()

        self._publish(TRAINING_CREATED, training)

        return training

    def select(self, training_id: str) -> Optional[Training]:

        training = self._find(training_id)

        if training is None:
            return None

        self.active_training_id = training.training_id

        self._publish(TRAINING_SELECTED, training)

        return training

    def delete(self, training_id: str) -> bool:

        character = self._character_manager.active_character

        if character is None:
            return False

        training = self._find(training_id)

        if training is None:
            return False

        character.trainings.remove(training)

        if self.active_training_id == training_id:
            self.active_training_id = None

        self._workspace_manager.save()

        self._publish(TRAINING_DELETED, training)

        return True

    def _find(self, training_id: str) -> Optional[Training]:
        for training in self.trainings:
            if training.training_id == training_id:
                return training
        return None

    def _publish(self, event_name: str, training: Training) -> None:

        if self._event_bus is None:
            return

        self._event_bus.publish(event_name, training.to_dict())
