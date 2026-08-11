import uuid
from typing import List, Optional

from src.core.event_bus import EventBus
from src.domain.dataset import Dataset
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

DATASET_CREATED = "dataset.created"
DATASET_SELECTED = "dataset.selected"
DATASET_DELETED = "dataset.deleted"


class DatasetManager:
    """
    Coordinates Dataset CRUD, selection and image import within the
    active Character. Operates exclusively on
    character_manager.active_character.datasets — never touches
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

        # Runtime-only, like CharacterManager.active_character_id —
        # never persisted.
        self.active_dataset_id: Optional[str] = None

        # A character switch (selection or deletion) or a workspace
        # switch must never leave active_dataset_id pointing at a
        # dataset that no longer belongs to the active character.
        if self._event_bus is not None:
            self._event_bus.subscribe(CHARACTER_SELECTED, self._on_context_changed)
            self._event_bus.subscribe(CHARACTER_DELETED, self._on_context_changed)
            self._event_bus.subscribe(WORKSPACE_CREATED, self._on_context_changed)
            self._event_bus.subscribe(WORKSPACE_OPENED, self._on_context_changed)
            self._event_bus.subscribe(WORKSPACE_CLOSED, self._on_context_changed)

    def _on_context_changed(self, payload) -> None:
        self.active_dataset_id = None

    @property
    def datasets(self) -> List[Dataset]:
        character = self._character_manager.active_character
        if character is None:
            return []
        return character.datasets

    def list_datasets(self) -> List[dict]:
        return [dataset.to_dict() for dataset in self.datasets]

    @property
    def active_dataset(self) -> Optional[Dataset]:
        if self.active_dataset_id is None:
            return None
        return self._find(self.active_dataset_id)

    def create(self, name: str) -> Optional[Dataset]:

        character = self._character_manager.active_character

        if character is None:
            return None

        dataset = Dataset(dataset_id=str(uuid.uuid4()), name=name)

        character.datasets.append(dataset)

        self._workspace_manager.save()

        self._publish(DATASET_CREATED, dataset)

        return dataset

    def select(self, dataset_id: str) -> Optional[Dataset]:

        dataset = self._find(dataset_id)

        if dataset is None:
            return None

        self.active_dataset_id = dataset.dataset_id

        self._publish(DATASET_SELECTED, dataset)

        return dataset

    def is_referenced_by_training(self, dataset_id: str) -> bool:
        character = self._character_manager.active_character
        if character is None:
            return False
        return any(
            training.dataset_id == dataset_id for training in character.trainings
        )

    def delete(self, dataset_id: str) -> bool:

        character = self._character_manager.active_character

        if character is None:
            return False

        dataset = self._find(dataset_id)

        if dataset is None:
            return False

        # A Dataset referenced by at least one Training may never be
        # deleted, enforced here regardless of whether the UI already
        # performed the same check — the Manager is the sole authority.
        if self.is_referenced_by_training(dataset_id):
            return False

        character.datasets.remove(dataset)

        if self.active_dataset_id == dataset_id:
            self.active_dataset_id = None

        self._workspace_manager.save()

        self._publish(DATASET_DELETED, dataset)

        return True

    def add_images(self, paths: List[str]) -> int:
        """
        Append paths not already present in the active dataset's
        images. Returns the number of images actually added — mirrors
        WorkspaceManager.add_images()'s dedup contract, operating on
        active_dataset the same way WorkspaceManager operates on the
        single current workspace (no dataset_id parameter needed).
        """

        dataset = self.active_dataset

        if dataset is None:
            return 0

        seen = set(dataset.images)
        new_paths = []

        for path in paths:
            if path in seen:
                continue
            seen.add(path)
            new_paths.append(path)

        if not new_paths:
            return 0

        dataset.images.extend(new_paths)

        self._workspace_manager.save()

        return len(new_paths)

    def _find(self, dataset_id: str) -> Optional[Dataset]:
        for dataset in self.datasets:
            if dataset.dataset_id == dataset_id:
                return dataset
        return None

    def _publish(self, event_name: str, dataset: Dataset) -> None:

        if self._event_bus is None:
            return

        self._event_bus.publish(event_name, dataset.to_dict())
