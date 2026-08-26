import os
import uuid
from pathlib import Path
from typing import List, Optional

from src.core.event_bus import EventBus
from src.domain.dataset import Dataset
from src.domain.image import Image
from src.infrastructure.storage.workspace_storage import (
    WorkspaceStorage,
    WorkspaceStorageError,
)
from src.managers.character_manager import (
    CharacterManager,
    CHARACTER_SELECTED,
    CHARACTER_DELETED,
)
from src.managers.workspace_manager import (
    CollisionInfo,
    ImportResult,
    WorkspaceManager,
    WorkspaceManagerError,
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
    Workspace's principal Character (Mission 026/028). Operates
    exclusively on character_manager.principal_character.datasets —
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
        # Mission 028 smoke test fix: reads principal_character, not
        # active_character. Since Mission 026, CharactersPage no
        # longer calls CharacterManager.select() at all — it only
        # *reads* principal_character to populate the identity fiche —
        # so on any Workspace opened via WORKSPACE_OPENED (as opposed
        # to freshly created), active_character_id stays None for the
        # entire session unless a test/caller explicitly calls
        # select(). Depending on active_character here silently broke
        # Datasets ("Aucun personnage actif") for every already-existing
        # project, with no way for the user to fix it (the
        # multi-character selection UI is hidden). principal_character
        # already resolves to active_character whenever a real
        # multi-character selection is genuinely in use (preserved,
        # e.g. every multi-character test in this suite calls select()
        # explicitly), and falls back to the Workspace's first/principal
        # Character otherwise — the exact fix already applied to
        # CharactersPage in Mission 026 (see CharacterManager.
        # principal_character's own docstring).
        character = self._character_manager.principal_character
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

        character = self._character_manager.principal_character

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

    def update_name(self, name: str) -> bool:
        """
        Rename the active dataset. Mirrors PromptManager.update_name()'s
        exact contract: a single scalar edited in place, strictly
        idempotent. Returns False (no save()) if there is no active
        dataset or if `name` is identical to the stored value. Not
        validated (empty string legitimate, no stripping) — same
        convention already used by CharacterManager.update(name=...)/
        ModelManager.update_name()/WorkflowManager.update_name()/
        LoRAManager.update_name()/PromptManager.update_name() (Missions
        052/053). Never touches `images` or `dataset_id`.
        """

        dataset = self.active_dataset

        if dataset is None:
            return False

        if dataset.name == name:
            return False

        dataset.name = name

        self._workspace_manager.save()

        return True

    def is_referenced_by_training(self, dataset_id: str) -> bool:
        character = self._character_manager.principal_character
        if character is None:
            return False
        return any(
            training.dataset_id == dataset_id for training in character.trainings
        )

    def delete(self, dataset_id: str) -> bool:
        """
        Mission 068: if save() fails after the Dataset has already been
        removed from character.datasets, the deletion is rolled back
        before the exception is re-raised — the same Dataset object is
        reinserted at its original index, and active_dataset_id (if it
        pointed at this Dataset) is restored to its previous value.
        Domain-only mutation, no filesystem involved, so a local rollback
        is sufficient — no snapshot of the wider Workspace is needed.
        """

        character = self._character_manager.principal_character

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

        index = character.datasets.index(dataset)
        previous_active_dataset_id = self.active_dataset_id

        character.datasets.remove(dataset)

        if self.active_dataset_id == dataset_id:
            self.active_dataset_id = None

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError:
            character.datasets.insert(index, dataset)
            self.active_dataset_id = previous_active_dataset_id
            raise

        self._publish(DATASET_DELETED, dataset)

        return True

    def preview_collisions(self, paths: List[str]) -> List[CollisionInfo]:
        """
        Read-only prediction (Mission 028 second smoke test) of every
        source in `paths` that would collide with a name already taken
        in <workspace_root>/datasets/<dataset_id>/ — mirrors
        WorkspaceManager.preview_collisions() exactly, scoped to the
        active Dataset's own destination folder instead of images/.
        See that method's docstring for the full rationale.
        """

        dataset = self.active_dataset

        if dataset is None:
            return []

        workspace_root = self._workspace_manager.current_workspace.root
        destination_folder = workspace_root / "datasets" / dataset.dataset_id

        seen_sources = set()
        claimed_names = set()
        collisions = []

        for path in paths:
            source = Path(path)
            resolved_source = os.path.normcase(str(source.resolve()))

            if resolved_source in seen_sources:
                continue
            seen_sources.add(resolved_source)

            if WorkspaceStorage.is_inside(source, workspace_root):
                continue

            resolved_target = WorkspaceStorage.resolve_collision_free_name(
                source, destination_folder, also_avoid=claimed_names
            )
            claimed_names.add(resolved_target.name)

            if resolved_target.name != source.name:
                collisions.append(CollisionInfo(source=str(path), suggested_name=resolved_target.name))

        return collisions

    def add_images(self, paths: List[str], renames: Optional[dict] = None) -> ImportResult:
        """
        Copies each path in `paths` into
        <workspace_root>/datasets/<dataset_id>/ (Mission 028) — mirrors
        WorkspaceManager.add_images()'s contract exactly (best-effort,
        already-internal sources reused as-is via
        WorkspaceStorage.copy_into_workspace(), nothing persisted for a
        failed copy, `renames` for collisions the caller already
        resolved with the user via preview_collisions() — see that
        method and WorkspaceManager.add_images() for the full
        rationale), operating on active_dataset the same way
        WorkspaceManager operates on the single current workspace (no
        dataset_id parameter needed). dataset_id (not dataset.name) is
        used for the destination folder — stable, filesystem-safe,
        never a duplicate across datasets, consistent with how this
        Domain already identifies a Dataset everywhere else. Each
        accepted path becomes its own Image (Mission 011: this
        Dataset's own Image pool, independent from Workspace.images —
        no shared registry, no cross-pool reference).

        Mission 067: if save() fails after some images were added,
        dataset.images is restored to exactly its pre-call state (same
        objects, same order) and a best-effort cleanup deletes only the
        physical copies this very call actually created — never a
        passthrough source already located under workspace_root
        (resolved effective_path identical to the resolved source —
        e.g. add_images_from_gallery() reusing an image already in
        Workspace.images), and never anything that existed before this
        call. A cleanup failure never masks the original persistence
        error, only adds orphan information to it (mirrors
        WorkspaceManager.add_images()/rename()'s same principle).
        """

        dataset = self.active_dataset

        if dataset is None:
            return ImportResult(added=0, failed=[], skipped=[])

        renames = renames or {}
        workspace = self._workspace_manager.current_workspace
        workspace_root = workspace.root
        destination_folder = workspace_root / "datasets" / dataset.dataset_id

        existing = {
            os.path.normcase(str(Path(image.file_path).resolve()))
            for image in dataset.images
            if image.file_path
        }

        seen_in_batch = set()
        new_images = []
        created_copies = []
        failed = []
        skipped = []

        for path in paths:
            resolved_source = os.path.normcase(str(Path(path).resolve()))

            if resolved_source in seen_in_batch:
                skipped.append(path)
                continue
            seen_in_batch.add(resolved_source)

            try:
                effective_path = WorkspaceStorage.copy_into_workspace(
                    Path(path), destination_folder, workspace_root,
                    target_name=renames.get(path),
                )
            except WorkspaceStorageError:
                failed.append(path)
                continue

            effective_key = os.path.normcase(str(effective_path))

            if effective_key in existing:
                skipped.append(path)
                continue
            existing.add(effective_key)

            if effective_key != resolved_source:
                created_copies.append(effective_path)

            new_images.append(Image(image_id=str(uuid.uuid4()), file_path=str(effective_path)))

        if new_images:
            original_images = dataset.images
            dataset.images = original_images + new_images
            try:
                self._workspace_manager.save()
            except WorkspaceManagerError as exc:
                dataset.images = original_images
                orphaned = []
                for copy_path in created_copies:
                    try:
                        copy_path.unlink()
                    except OSError:
                        orphaned.append(str(copy_path))
                if orphaned:
                    raise WorkspaceManagerError(
                        f"{exc} Additionally, the following newly copied file(s) could not be "
                        f"cleaned up and remain orphaned on disk: {', '.join(orphaned)}."
                    ) from exc
                raise

        return ImportResult(added=len(new_images), failed=failed, skipped=skipped)

    def remove_images(self, paths: List[str]) -> int:
        """
        Removes from the active Dataset's own Image pool every entry
        whose file_path resolves to one of `paths` (Mission 045) —
        never touches the filesystem, Workspace.images, or any other
        Dataset. Each Dataset owns an independent list[Image] (Mission
        011), so this can only ever mutate the active Dataset's own
        list. Mirrors add_images()'s resolved-path comparison
        convention exactly, and its "only save if something actually
        changed" principle — no dedicated event published, same as
        add_images().
        """

        dataset = self.active_dataset

        if dataset is None:
            return 0

        resolved_targets = {
            os.path.normcase(str(Path(path).resolve())) for path in paths
        }

        before = len(dataset.images)
        dataset.images[:] = [
            image for image in dataset.images
            if os.path.normcase(str(Path(image.file_path).resolve())) not in resolved_targets
        ]
        removed = before - len(dataset.images)

        if removed:
            self._workspace_manager.save()

        return removed

    def _find(self, dataset_id: str) -> Optional[Dataset]:
        for dataset in self.datasets:
            if dataset.dataset_id == dataset_id:
                return dataset
        return None

    def _publish(self, event_name: str, dataset: Dataset) -> None:

        if self._event_bus is None:
            return

        self._event_bus.publish(event_name, dataset.to_dict())
