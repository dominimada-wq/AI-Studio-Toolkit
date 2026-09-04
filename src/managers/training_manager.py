import json
import shutil
import uuid
from pathlib import Path
from typing import List, NamedTuple, Optional

from src.core.event_bus import EventBus
from src.domain.training import Training
from src.engines.onetrainer_config import build_training_config
from src.infrastructure.storage.workspace_storage import WorkspaceStorage
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

TRAINING_CREATED = "training.created"
TRAINING_SELECTED = "training.selected"
TRAINING_DELETED = "training.deleted"

# Mission 097 section 3.4: the small, closed, generic architecture
# vocabulary this Toolkit exposes for a Training session — never
# OneTrainer's own ~25-value ModelType enum, which stays entirely
# inside src/engines/onetrainer_config.py's own translation table (that
# module deliberately re-declares the same three string values on its
# own, coordinated by mission specification rather than a shared
# import — same precedent as DEFAULT_REFERENCE_STRENGTH_PERCENT in
# inference_page.py vs. comfyui_workflows.py's own defaults, preserving
# the Manager -> Engine dependency direction).
TRAINING_ARCHITECTURE_SD15 = "SD15"
TRAINING_ARCHITECTURE_SDXL = "SDXL"
# Mission 097 section 3.4: structurally supported by this installed
# OneTrainer version (a real FluxLoRAModelLoader and a real shipped
# preset both exist) and by this Toolkit's own dataset materialization
# (architecture-independent) — included in the generic vocabulary on
# that basis. Never verified as actually trainable on this machine's
# GPU (Quadro P4000, 8GB VRAM, confirmed via Mission 096's real ComfyUI
# smoke test) — this mission never executes a training run, so that
# question does not need answering here; the UI must not present FLUX
# as validated for real execution.
TRAINING_ARCHITECTURE_FLUX = "FLUX"

TRAINING_ARCHITECTURES = (
    TRAINING_ARCHITECTURE_SD15,
    TRAINING_ARCHITECTURE_SDXL,
    TRAINING_ARCHITECTURE_FLUX,
)

# Mission 097 section 3.6: WorkspaceStorage.DIRECTORIES already reserves
# a top-level "training" folder in every Workspace (present since this
# project's earliest scaffolding, never consumed by any code before
# this mission) — reused here rather than inventing a new convention.
_TRAINING_SUBFOLDER_NAME = "training"
_CONCEPT_SUBFOLDER_NAME = "concept"
_OUTPUT_SUBFOLDER_NAME = "output"
_OUTPUT_MODEL_FILENAME = "lora.safetensors"
_CONFIG_FILENAME = "onetrainer_config.json"


class TrainingPreparationError(Exception):
    """
    Raised by TrainingManager.prepare_onetrainer_config() on any real
    failure — an unknown dataset, an empty dataset, or a filesystem
    failure during materialization. Never raised for anything this
    mission does not attempt (no training is ever started by this
    class — see MISSION_097.md section 7/8).
    """


class TrainingPreparationResult(NamedTuple):
    """
    Mission 097: same NamedTuple-result convention already established
    by LoRALibraryDeletionResult/LoRAComfyUIExposureResult — the three
    deterministic, Workspace-relative locations this mission's
    preparation step produces, none of them ever persisted on the
    Training Domain object itself (see MISSION_097.md section 3.6/6).
    """

    concept_path: str
    config_path: str
    output_path: str


class TrainingManager:
    """
    Coordinates Training CRUD and selection within the Workspace's
    principal Character (Mission 026/028/029). Operates exclusively on
    character_manager.principal_character.trainings — never touches
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
        # Mission 029: reads principal_character, not active_character —
        # same fix already applied to DatasetManager in Mission 028 (see
        # its property's docstring for the full rationale). Any Workspace
        # opened via WORKSPACE_OPENED (as opposed to freshly created)
        # otherwise leaves active_character_id at None for the whole
        # session, since CharactersPage never calls select() anymore.
        character = self._character_manager.principal_character
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

        character = self._character_manager.principal_character

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

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError:
            character.trainings.remove(training)
            raise

        self._publish(TRAINING_CREATED, training)

        return training

    def select(self, training_id: str) -> Optional[Training]:

        training = self._find(training_id)

        if training is None:
            return None

        self.active_training_id = training.training_id

        self._publish(TRAINING_SELECTED, training)

        return training

    def update_name(self, name: str) -> bool:
        """
        Rename the active training. Mirrors PromptManager.update_name()'s
        exact contract: a single scalar edited in place, strictly
        idempotent. Returns False (no save()) if there is no active
        training or if `name` is identical to the stored value. Not
        validated (empty string legitimate, no stripping) — same
        convention already used by CharacterManager.update(name=...)/
        ModelManager.update_name()/WorkflowManager.update_name()/
        LoRAManager.update_name()/PromptManager.update_name()/
        DatasetManager.update_name() (Missions 052/053/054). Never
        touches `dataset_id` or any other property.
        """

        training = self.active_training

        if training is None:
            return False

        if training.name == name:
            return False

        old_name = training.name
        training.name = name

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError:
            training.name = old_name
            raise

        return True

    def update(
        self,
        base_model_source: Optional[str] = None,
        architecture: Optional[str] = None,
        resolution: Optional[int] = None,
        epochs: Optional[int] = None,
        learning_rate: Optional[float] = None,
        lora_rank: Optional[int] = None,
        lora_alpha: Optional[float] = None,
        trigger_word: Optional[str] = None,
    ) -> bool:
        """
        Mission 097: updates the active training's generic hyperparameters
        — same combined-multi-field contract as LoRAManager.update()
        (Mission 073): acts on self.active_training (this Manager's own
        existing convention, established by update_name() above, unlike
        LoRAManager which targets an explicit lora_id), a field left as
        None is untouched, strictly idempotent (no save() unless
        something actually changed), and every field is rolled back to
        its exact previous value on the same Training instance if
        save() fails. No event is published (never had one for scalar
        edits on this Manager, same as update_name() above). Never
        touches `name`/`dataset_id` — name has update_name(), dataset_id
        is fixed at creation (Mission 097 scope: a Training's source
        Dataset is never reassigned after creation).
        """

        training = self.active_training

        if training is None:
            return False

        changed = (
            (base_model_source is not None and base_model_source != training.base_model_source)
            or (architecture is not None and architecture != training.architecture)
            or (resolution is not None and resolution != training.resolution)
            or (epochs is not None and epochs != training.epochs)
            or (learning_rate is not None and learning_rate != training.learning_rate)
            or (lora_rank is not None and lora_rank != training.lora_rank)
            or (lora_alpha is not None and lora_alpha != training.lora_alpha)
            or (trigger_word is not None and trigger_word != training.trigger_word)
        )

        if not changed:
            return False

        previous = (
            training.base_model_source, training.architecture, training.resolution,
            training.epochs, training.learning_rate, training.lora_rank,
            training.lora_alpha, training.trigger_word,
        )

        if base_model_source is not None:
            training.base_model_source = base_model_source
        if architecture is not None:
            training.architecture = architecture
        if resolution is not None:
            training.resolution = resolution
        if epochs is not None:
            training.epochs = epochs
        if learning_rate is not None:
            training.learning_rate = learning_rate
        if lora_rank is not None:
            training.lora_rank = lora_rank
        if lora_alpha is not None:
            training.lora_alpha = lora_alpha
        if trigger_word is not None:
            training.trigger_word = trigger_word

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError:
            (
                training.base_model_source, training.architecture, training.resolution,
                training.epochs, training.learning_rate, training.lora_rank,
                training.lora_alpha, training.trigger_word,
            ) = previous
            raise

        return True

    def _training_folder(self, training_id: str) -> Path:
        return Path(self._workspace_manager.current_workspace.root) / _TRAINING_SUBFOLDER_NAME / training_id

    def _materialize_concept(self, training: Training, dataset) -> Path:
        """
        Mission 097 section 6: copies every image of `dataset` into this
        training's own concept folder, writing a same-name `.txt`
        caption sidecar next to each (content: training.trigger_word —
        explicitly provisional, see Training.trigger_word's own
        docstring). Never touches the Dataset's own source images.

        Deterministic/reproducible/cleanable: the concept folder is
        wiped (best-effort) and rebuilt from scratch on every call, so
        a stale prior materialization (an old Dataset state, an old
        trigger_word) never lingers — always exactly reflects the
        Dataset/Training as they are right now.

        Collision-free naming reuses WorkspaceStorage.
        resolve_collision_free_name() directly (Mission 097 section
        3.6) — deliberately NOT WorkspaceStorage.copy_into_workspace(),
        whose passthrough skip (never copying a source already inside
        workspace_root) is correct for Dataset/LoRA import but wrong
        here: materialization must always produce a real physical copy
        inside the concept folder, regardless of where the source
        currently lives. Copies are made one at a time, synchronously
        — by the time a later image's name is resolved, every earlier
        one is already physically on disk, so disk state alone is
        sufficient (same reasoning already documented on
        resolve_collision_free_name() itself for copy_into_workspace()'s
        own sequential copy).
        """
        concept_folder = self._training_folder(training.training_id) / _CONCEPT_SUBFOLDER_NAME

        shutil.rmtree(concept_folder, ignore_errors=True)

        try:
            concept_folder.mkdir(parents=True, exist_ok=True)

            for image in dataset.images:
                source = Path(image.file_path)
                target = WorkspaceStorage.resolve_collision_free_name(source, concept_folder)
                shutil.copy2(source, target)
                target.with_suffix(".txt").write_text(training.trigger_word, encoding="utf-8")
        except OSError as exc:
            raise TrainingPreparationError(
                f"Could not materialize the dataset concept folder for training {training.training_id!r}: {exc}"
            ) from exc

        return concept_folder

    def prepare_onetrainer_config(self, training_id: str) -> TrainingPreparationResult:
        """
        Mission 097: the single orchestration entry point this mission
        introduces — materializes the active Dataset into this
        training's concept folder (see _materialize_concept()), builds
        the OneTrainer configuration dict (src/engines/onetrainer_config.
        build_training_config(), Mission 097 section 3), and writes it
        to a deterministic, Workspace-relative location. Never starts
        OneTrainer, never imports OneTrainer's own code, never touches
        the network or the GPU — see MISSION_097.md section 7/8 for the
        explicit boundary this method never crosses.

        Raises TrainingPreparationError if training_id is unknown, if
        its dataset_id no longer resolves to a real Dataset of the
        active Character, if that Dataset has no images at all (nothing
        to materialize), or on any filesystem failure. Raises
        src.engines.onetrainer_config.OneTrainerConfigError if
        training.architecture is not one of TRAINING_ARCHITECTURES —
        both are real, explicit failures, never silently guessed past.
        """
        training = self._find(training_id)
        if training is None:
            raise TrainingPreparationError(f"Unknown training: {training_id!r}")

        character = self._character_manager.principal_character
        dataset = None
        if character is not None:
            dataset = next(
                (d for d in character.datasets if d.dataset_id == training.dataset_id), None
            )
        if dataset is None:
            raise TrainingPreparationError(
                f"Training {training_id!r} references dataset {training.dataset_id!r}, "
                f"which no longer exists"
            )
        if not dataset.images:
            raise TrainingPreparationError(
                f"Dataset {training.dataset_id!r} has no images — nothing to materialize"
            )

        concept_folder = self._materialize_concept(training, dataset)

        training_folder = self._training_folder(training_id)
        output_folder = training_folder / _OUTPUT_SUBFOLDER_NAME
        output_path = output_folder / _OUTPUT_MODEL_FILENAME

        try:
            output_folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise TrainingPreparationError(
                f"Could not create the output folder for training {training_id!r}: {exc}"
            ) from exc

        config = build_training_config(
            architecture=training.architecture,
            base_model_source=training.base_model_source,
            resolution=training.resolution,
            epochs=training.epochs,
            learning_rate=training.learning_rate,
            lora_rank=training.lora_rank,
            lora_alpha=training.lora_alpha,
            output_model_destination=str(output_path),
            concept_name=training.name,
            concept_path=str(concept_folder),
        )

        config_path = training_folder / _CONFIG_FILENAME
        try:
            config_path.write_text(json.dumps(config, indent=4), encoding="utf-8")
        except OSError as exc:
            raise TrainingPreparationError(
                f"Could not write the OneTrainer configuration for training {training_id!r}: {exc}"
            ) from exc

        return TrainingPreparationResult(
            concept_path=str(concept_folder),
            config_path=str(config_path),
            output_path=str(output_path),
        )

    def delete(self, training_id: str) -> bool:
        """
        Mission 068: if save() fails after the Training has already been
        removed from character.trainings, the deletion is rolled back
        before the exception is re-raised — the same Training object is
        reinserted at its original index, and active_training_id (if it
        pointed at this Training) is restored to its previous value.
        Domain-only mutation, no filesystem involved, so a local
        rollback is sufficient — no snapshot of the wider Workspace is
        needed.
        """

        character = self._character_manager.principal_character

        if character is None:
            return False

        training = self._find(training_id)

        if training is None:
            return False

        index = character.trainings.index(training)
        previous_active_training_id = self.active_training_id

        character.trainings.remove(training)

        if self.active_training_id == training_id:
            self.active_training_id = None

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError:
            character.trainings.insert(index, training)
            self.active_training_id = previous_active_training_id
            raise

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
