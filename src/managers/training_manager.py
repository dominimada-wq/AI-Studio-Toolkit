import json
import shutil
import time
import uuid
from pathlib import Path
from typing import List, NamedTuple, Optional

from src.core.event_bus import EventBus
from src.domain.training import Training
from src.domain.training_job import TrainingJob
from src.engines.onetrainer_config import build_training_config
from src.infrastructure.storage.workspace_storage import WorkspaceStorage, WorkspaceStorageError
from src.utils.base_model_source import InvalidBaseModelSourceError, validate_base_model_source
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

# Mission 124: update()'s own long-standing convention is "a parameter
# left as its default (None) means leave this field untouched" — which
# works cleanly for every str/int/float field, whose own Domain "not
# configured" sentinel (""/0) is a different value from None. For
# text_encoder_train/text_encoder_2_train, the Domain "not configured"
# sentinel is itself None (see src/domain/onetrainer_settings.py) —
# reusing update()'s own None-means-untouched convention for these two
# parameters would make it impossible to ever explicitly reset either
# field back to "not configured" via this method. _UNSET is a private,
# module-level sentinel used only as those two parameters' own default,
# so "argument not passed to this call" (leave untouched) and "None
# passed explicitly" (reset to not-configured) stay distinguishable.
_UNSET = object()

# Mission 100 section 5.2: no "prepared" state — Prepare stays
# Training-scoped, entirely outside a TrainingJob's own lifecycle. A Job
# is created only at Start (create_job() below) and its state is set/
# transitioned exclusively by whichever caller owns the real QProcess
# (src/ui/, this Manager stays Qt-free — same layering already
# established by GenerationManager/GenerationWorker for Inference).
TRAINING_JOB_STATE_STARTING = "starting"
TRAINING_JOB_STATE_RUNNING = "running"
TRAINING_JOB_STATE_SUCCEEDED = "succeeded"
TRAINING_JOB_STATE_FAILED = "failed"
TRAINING_JOB_STATE_CANCELLED = "cancelled"
# Mission 100 section 12: a Job found "starting"/"running" when a
# Workspace is opened has necessarily lost its QProcess supervision —
# this can only happen after an abnormal termination (crash/forced
# kill/power loss), never a normal close (blocked by the close guard,
# MISSION_100.md section 11). Its real outcome is never guessed:
# QProcess cannot reattach to an external process by PID, and Windows
# can reuse a persisted PID for an unrelated process, so no reliable
# "is this still the same process" check exists without a new
# dependency. Never transitioned automatically to any other state.
TRAINING_JOB_STATE_UNKNOWN = "unknown"

TRAINING_JOB_ACTIVE_STATES = (TRAINING_JOB_STATE_STARTING, TRAINING_JOB_STATE_RUNNING)
TRAINING_JOB_TERMINAL_STATES = (
    TRAINING_JOB_STATE_SUCCEEDED,
    TRAINING_JOB_STATE_FAILED,
    TRAINING_JOB_STATE_CANCELLED,
    TRAINING_JOB_STATE_UNKNOWN,
)

TRAINING_JOB_CREATED = "training_job.created"
TRAINING_JOB_STATE_CHANGED = "training_job.state_changed"

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

# Mission 100 section 9: one self-contained folder per real execution
# attempt, under the Training's own folder — never shared between two
# TrainingJob of the same Training, never written under the OneTrainer
# installation itself. workspace_dir/cache_dir/debug_dir mirror
# OneTrainer's own TrainConfig field names (they default to relative
# paths resolved against the OneTrainer process's cwd otherwise — see
# MISSION_100.md section 3.1's "constat critique").
_JOBS_SUBFOLDER_NAME = "jobs"
_JOB_WORKSPACE_SUBFOLDER_NAME = "workspace"
_JOB_CACHE_SUBFOLDER_NAME = "cache"
_JOB_DEBUG_SUBFOLDER_NAME = "debug"
_JOB_COMMAND_PIPE_FILENAME = "command.pipe"

# Mission 139: the concept snapshot a Job actually trains against is
# now isolated exactly like workspace_dir/cache_dir/debug_dir above —
# a later Prepare/Start of a different Job of the same Training must
# never be able to mutate the data an already-created Job was set up
# with (see create_job()).
_JOB_CONCEPT_SUBFOLDER_NAME = "concept"


class TrainingJobError(Exception):
    """
    Raised by create_job() on any real failure — an unknown training, a
    training never prepared (no onetrainer_config.json yet), or a
    filesystem failure while setting up the job's own folder. Kept
    distinct from TrainingPreparationError (Prepare's own exception,
    Mission 097) since a Job's lifecycle is Mission 100's own concern,
    never raised by prepare_onetrainer_config() itself.
    """


class TrainingJobPaths(NamedTuple):
    """
    Mission 100: every deterministic, Workspace-owned filesystem
    location associated with one TrainingJob — computed independently
    of whether the job/its folder actually exist yet (pure path
    arithmetic, no I/O), so the same computation serves create_job()
    (which creates these paths) and the QProcess-owning runner (src/ui/,
    which only ever reads/writes into paths it did not itself invent).
    """

    job_id: str
    config_snapshot_path: str
    expected_output_path: str
    command_pipe_path: str
    workspace_dir: str
    cache_dir: str
    debug_dir: str
    concept_dir: str


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


class TrainingActiveError(Exception):
    """
    Raised by delete() when the targeted Training itself has a job in
    TRAINING_JOB_ACTIVE_STATES (starting/running) — Mission 145. Scoped
    to that one Training's own jobs only, never has_active_job()'s
    whole-Character scan (Mission 100's close guard), so deleting an
    unrelated Training with no active job of its own is never blocked
    by one running elsewhere. delete() never cancels the active job
    itself — no QProcess/async orchestration lives in this Qt-free
    Manager — the caller must cancel it first, then retry.
    """


class TrainingDeletionResult(NamedTuple):
    """
    Mission 145: delete()'s return type — same convention already
    established by LoRADeletionResult/DatasetDeletionResult (Mission
    075), now that delete() also stages/purges the Training's own
    folder (previously Domain-only, see the method's own docstring).
    """

    deleted: bool
    cleanup_failed: bool
    residual_path: Optional[str]


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
            # Mission 100 section 12: only WORKSPACE_OPENED — a brand
            # new project (WORKSPACE_CREATED) cannot carry any job, and
            # WORKSPACE_CLOSED has nothing left to recover.
            self._event_bus.subscribe(WORKSPACE_OPENED, self._recover_stale_jobs)

    def _on_context_changed(self, payload) -> None:
        self.active_training_id = None

    def _recover_stale_jobs(self, payload) -> None:
        """
        Mission 100 section 12: any TrainingJob found "starting"/
        "running" at the moment a Workspace is opened has necessarily
        lost its QProcess supervision (this process just started, or
        the previous one never reached a persisted terminal state) —
        it can only have gotten there through an abnormal termination,
        never a normal close (blocked by the close guard, section 11).
        Transitioned to TRAINING_JOB_STATE_UNKNOWN — never guessed as
        succeeded/failed/cancelled — via the same update_job_state()
        used everywhere else, so this follows the identical
        idempotent/rollback-on-save-failure contract.
        """
        for training in self.trainings:
            for job in list(training.jobs):
                if job.state in TRAINING_JOB_ACTIVE_STATES:
                    self.update_job_state(job.job_id, TRAINING_JOB_STATE_UNKNOWN)

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

        # Mission 111: trigger_word defaults from the principal
        # Character's own trigger_token at creation time only — a plain
        # initial value, never a lasting link (see character.trigger_token
        # is not reread anywhere else in this class). `or ""` normalizes
        # the unlikely case of a hand-edited project.json carrying an
        # explicit null for this scalar field (character.py:62's
        # from_dict() only guards a missing key, not an explicit null —
        # same limitation as every other scalar field on Character),
        # keeping Training.trigger_word a plain str as its own contract
        # requires (training.py:64).
        training = Training(
            training_id=str(uuid.uuid4()), name=name, dataset_id=dataset_id,
            trigger_word=character.trigger_token or "",
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
        batch_size: Optional[int] = None,
        gradient_accumulation_steps: Optional[int] = None,
        learning_rate_scheduler: Optional[str] = None,
        train_dtype: Optional[str] = None,
        gradient_checkpointing_mode: Optional[str] = None,
        unet_weight_dtype: Optional[str] = None,
        transformer_weight_dtype: Optional[str] = None,
        text_encoder_weight_dtype: Optional[str] = None,
        text_encoder_2_weight_dtype: Optional[str] = None,
        vae_weight_dtype: Optional[str] = None,
        optimizer: Optional[str] = None,
        text_encoder_train: Optional[bool] = _UNSET,
        text_encoder_2_train: Optional[bool] = _UNSET,
        text_encoder_stop_training_mode: Optional[str] = None,
        text_encoder_stop_training_after: Optional[int] = _UNSET,
        text_encoder_2_stop_training_mode: Optional[str] = None,
        text_encoder_2_stop_training_after: Optional[int] = _UNSET,
        lora_layer_filter: Optional[str] = None,
        timestep_distribution: Optional[str] = None,
        dynamic_timestep_shifting: Optional[bool] = _UNSET,
        timestep_shift: Optional[float] = _UNSET,
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

        Mission 120: batch_size/gradient_accumulation_steps live on
        Training itself (generic fields, same rollback contract as the
        rest of this method); learning_rate_scheduler lives on the
        nested training.onetrainer_settings (Mission 120 architecture —
        see src/domain/onetrainer_settings.py) and is rolled back on
        that same nested object, never by replacing it wholesale (so an
        untouched extra_overrides on it is never disturbed by this
        call). None means "leave untouched" for all three, exactly like
        every other parameter here — never confused with these fields'
        own "not configured" sentinels (0/""), which are real values a
        caller can explicitly set.

        Mission 121: train_dtype/unet_weight_dtype/
        transformer_weight_dtype/text_encoder_weight_dtype/
        text_encoder_2_weight_dtype/vae_weight_dtype follow the exact
        same nested-object mutation/rollback contract as
        learning_rate_scheduler above — same onetrainer_settings
        instance, never replaced wholesale.

        Mission 122: optimizer lives one level deeper still, on
        onetrainer_settings.optimizer_settings (Mission 122 architecture
        — see src/domain/onetrainer_optimizer_settings.py). Only its own
        `.optimizer` field is mutated in place here — never the
        optimizer_settings object itself replaced wholesale, and never
        its own `.extra_overrides` touched by this method (not yet
        UI-editable in this mission), exactly the same "mutate the field,
        never the container" discipline as onetrainer_settings itself.

        Mission 124: lora_layer_filter follows the same nested-object
        mutation/rollback contract as the Mission 121 dtype fields
        above (None means "leave untouched", "" is a real, explicit
        "not configured" value distinct from None). text_encoder_train/
        text_encoder_2_train do not — see this module's own _UNSET
        sentinel above for why: their Domain "not configured" sentinel
        is None itself, so they default to _UNSET here instead, and
        None is a real, explicit value meaning "reset to not
        configured", never "leave untouched".

        Mission 126: timestep_distribution follows the same "" sentinel
        contract as lora_layer_filter above (None means "leave
        untouched"). dynamic_timestep_shifting/timestep_shift follow
        the same _UNSET contract as text_encoder_train/
        text_encoder_2_train above, for the exact same reason — their
        Domain "not configured" sentinel is None itself, so a genuine
        explicit reset to "not configured" must stay distinguishable
        from "argument not passed to this call" (see MISSION_126.md
        section 6). Never generalized to any other parameter of this
        method.

        Mission 127: gradient_checkpointing_mode follows the exact same
        "" sentinel contract as train_dtype/learning_rate_scheduler
        above — its Domain "not configured" sentinel is already "",
        never None, so None here means "leave untouched" and an
        explicit "" resets it to "not configured" (see MISSION_127.md
        section 1.B) — no _UNSET needed, never generalized beyond this
        field's own str sentinel.

        Mission 128: text_encoder_stop_training_mode/
        text_encoder_2_stop_training_mode follow the same "" sentinel
        contract as gradient_checkpointing_mode immediately above (None
        means "leave untouched", explicit "" resets to "not
        configured"). text_encoder_stop_training_after/
        text_encoder_2_stop_training_after follow the _UNSET contract
        instead, for the exact same reason as text_encoder_train/
        text_encoder_2_train above — their Domain "not configured"
        sentinel is None itself, so a genuine explicit reset to "not
        configured" must stay distinguishable from "argument not passed
        to this call": omitting the argument leaves the stored value
        untouched (e.g. update() with no after-argument after a prior
        after=10 still leaves it at 10), while update(..._after=None)
        explicitly resets it to None, and update(..._after=5) sets it
        to 5 — 0 is a real, explicit value here, never treated as a
        sentinel (see MISSION_128.md section 2).
        """

        training = self.active_training

        if training is None:
            return False

        onetrainer_settings = training.onetrainer_settings
        optimizer_settings = onetrainer_settings.optimizer_settings

        changed = (
            (base_model_source is not None and base_model_source != training.base_model_source)
            or (architecture is not None and architecture != training.architecture)
            or (resolution is not None and resolution != training.resolution)
            or (epochs is not None and epochs != training.epochs)
            or (learning_rate is not None and learning_rate != training.learning_rate)
            or (lora_rank is not None and lora_rank != training.lora_rank)
            or (lora_alpha is not None and lora_alpha != training.lora_alpha)
            or (trigger_word is not None and trigger_word != training.trigger_word)
            or (batch_size is not None and batch_size != training.batch_size)
            or (
                gradient_accumulation_steps is not None
                and gradient_accumulation_steps != training.gradient_accumulation_steps
            )
            or (
                learning_rate_scheduler is not None
                and learning_rate_scheduler != onetrainer_settings.learning_rate_scheduler
            )
            or (train_dtype is not None and train_dtype != onetrainer_settings.train_dtype)
            or (
                gradient_checkpointing_mode is not None
                and gradient_checkpointing_mode != onetrainer_settings.gradient_checkpointing_mode
            )
            or (
                unet_weight_dtype is not None
                and unet_weight_dtype != onetrainer_settings.unet_weight_dtype
            )
            or (
                transformer_weight_dtype is not None
                and transformer_weight_dtype != onetrainer_settings.transformer_weight_dtype
            )
            or (
                text_encoder_weight_dtype is not None
                and text_encoder_weight_dtype != onetrainer_settings.text_encoder_weight_dtype
            )
            or (
                text_encoder_2_weight_dtype is not None
                and text_encoder_2_weight_dtype != onetrainer_settings.text_encoder_2_weight_dtype
            )
            or (
                vae_weight_dtype is not None
                and vae_weight_dtype != onetrainer_settings.vae_weight_dtype
            )
            or (optimizer is not None and optimizer != optimizer_settings.optimizer)
            or (
                text_encoder_train is not _UNSET
                and text_encoder_train != onetrainer_settings.text_encoder_train
            )
            or (
                text_encoder_2_train is not _UNSET
                and text_encoder_2_train != onetrainer_settings.text_encoder_2_train
            )
            or (
                text_encoder_stop_training_mode is not None
                and text_encoder_stop_training_mode
                != onetrainer_settings.text_encoder_stop_training_mode
            )
            or (
                text_encoder_stop_training_after is not _UNSET
                and text_encoder_stop_training_after
                != onetrainer_settings.text_encoder_stop_training_after
            )
            or (
                text_encoder_2_stop_training_mode is not None
                and text_encoder_2_stop_training_mode
                != onetrainer_settings.text_encoder_2_stop_training_mode
            )
            or (
                text_encoder_2_stop_training_after is not _UNSET
                and text_encoder_2_stop_training_after
                != onetrainer_settings.text_encoder_2_stop_training_after
            )
            or (
                lora_layer_filter is not None
                and lora_layer_filter != onetrainer_settings.lora_layer_filter
            )
            or (
                timestep_distribution is not None
                and timestep_distribution != onetrainer_settings.timestep_distribution
            )
            or (
                dynamic_timestep_shifting is not _UNSET
                and dynamic_timestep_shifting != onetrainer_settings.dynamic_timestep_shifting
            )
            or (
                timestep_shift is not _UNSET
                and timestep_shift != onetrainer_settings.timestep_shift
            )
        )

        if not changed:
            return False

        previous = (
            training.base_model_source, training.architecture, training.resolution,
            training.epochs, training.learning_rate, training.lora_rank,
            training.lora_alpha, training.trigger_word,
            training.batch_size, training.gradient_accumulation_steps,
            onetrainer_settings.learning_rate_scheduler,
            onetrainer_settings.train_dtype,
            onetrainer_settings.gradient_checkpointing_mode,
            onetrainer_settings.unet_weight_dtype,
            onetrainer_settings.transformer_weight_dtype,
            onetrainer_settings.text_encoder_weight_dtype,
            onetrainer_settings.text_encoder_2_weight_dtype,
            onetrainer_settings.vae_weight_dtype,
            optimizer_settings.optimizer,
            onetrainer_settings.text_encoder_train,
            onetrainer_settings.text_encoder_2_train,
            onetrainer_settings.text_encoder_stop_training_mode,
            onetrainer_settings.text_encoder_stop_training_after,
            onetrainer_settings.text_encoder_2_stop_training_mode,
            onetrainer_settings.text_encoder_2_stop_training_after,
            onetrainer_settings.lora_layer_filter,
            onetrainer_settings.timestep_distribution,
            onetrainer_settings.dynamic_timestep_shifting,
            onetrainer_settings.timestep_shift,
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
        if batch_size is not None:
            training.batch_size = batch_size
        if gradient_accumulation_steps is not None:
            training.gradient_accumulation_steps = gradient_accumulation_steps
        if learning_rate_scheduler is not None:
            onetrainer_settings.learning_rate_scheduler = learning_rate_scheduler
        if train_dtype is not None:
            onetrainer_settings.train_dtype = train_dtype
        if gradient_checkpointing_mode is not None:
            onetrainer_settings.gradient_checkpointing_mode = gradient_checkpointing_mode
        if unet_weight_dtype is not None:
            onetrainer_settings.unet_weight_dtype = unet_weight_dtype
        if transformer_weight_dtype is not None:
            onetrainer_settings.transformer_weight_dtype = transformer_weight_dtype
        if text_encoder_weight_dtype is not None:
            onetrainer_settings.text_encoder_weight_dtype = text_encoder_weight_dtype
        if text_encoder_2_weight_dtype is not None:
            onetrainer_settings.text_encoder_2_weight_dtype = text_encoder_2_weight_dtype
        if vae_weight_dtype is not None:
            onetrainer_settings.vae_weight_dtype = vae_weight_dtype
        if optimizer is not None:
            optimizer_settings.optimizer = optimizer
        if text_encoder_train is not _UNSET:
            onetrainer_settings.text_encoder_train = text_encoder_train
        if text_encoder_2_train is not _UNSET:
            onetrainer_settings.text_encoder_2_train = text_encoder_2_train
        if text_encoder_stop_training_mode is not None:
            onetrainer_settings.text_encoder_stop_training_mode = text_encoder_stop_training_mode
        if text_encoder_stop_training_after is not _UNSET:
            onetrainer_settings.text_encoder_stop_training_after = text_encoder_stop_training_after
        if text_encoder_2_stop_training_mode is not None:
            onetrainer_settings.text_encoder_2_stop_training_mode = (
                text_encoder_2_stop_training_mode
            )
        if text_encoder_2_stop_training_after is not _UNSET:
            onetrainer_settings.text_encoder_2_stop_training_after = (
                text_encoder_2_stop_training_after
            )
        if lora_layer_filter is not None:
            onetrainer_settings.lora_layer_filter = lora_layer_filter
        if timestep_distribution is not None:
            onetrainer_settings.timestep_distribution = timestep_distribution
        if dynamic_timestep_shifting is not _UNSET:
            onetrainer_settings.dynamic_timestep_shifting = dynamic_timestep_shifting
        if timestep_shift is not _UNSET:
            onetrainer_settings.timestep_shift = timestep_shift

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError:
            (
                training.base_model_source, training.architecture, training.resolution,
                training.epochs, training.learning_rate, training.lora_rank,
                training.lora_alpha, training.trigger_word,
                training.batch_size, training.gradient_accumulation_steps,
                onetrainer_settings.learning_rate_scheduler,
                onetrainer_settings.train_dtype,
                onetrainer_settings.gradient_checkpointing_mode,
                onetrainer_settings.unet_weight_dtype,
                onetrainer_settings.transformer_weight_dtype,
                onetrainer_settings.text_encoder_weight_dtype,
                onetrainer_settings.text_encoder_2_weight_dtype,
                onetrainer_settings.vae_weight_dtype,
                optimizer_settings.optimizer,
                onetrainer_settings.text_encoder_train,
                onetrainer_settings.text_encoder_2_train,
                onetrainer_settings.text_encoder_stop_training_mode,
                onetrainer_settings.text_encoder_stop_training_after,
                onetrainer_settings.text_encoder_2_stop_training_mode,
                onetrainer_settings.text_encoder_2_stop_training_after,
                onetrainer_settings.lora_layer_filter,
                onetrainer_settings.timestep_distribution,
                onetrainer_settings.dynamic_timestep_shifting,
                onetrainer_settings.timestep_shift,
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
        wiped and rebuilt from scratch on every call, so a stale prior
        materialization (an old Dataset state, an old trigger_word)
        never lingers — always exactly reflects the Dataset/Training as
        they are right now. "Best-effort" applies only to a folder that
        does not exist yet (WorkspaceStorage.delete_folder() treats
        that as a no-op, never an error) — a real wipe failure (e.g. a
        file locked by another process) is never silently ignored (see
        Mission 134): it fails this call outright, via the same
        best-effort-cleanup-then-raise discipline already used by
        LoRALibraryManager.import_lora() for a partially copied entry.
        A materialization either ends up complete and consistent with
        the current Dataset/Training, or the concept folder ends up
        absent again — never left half-rebuilt, which is what let a
        stale prior materialization be silently trusted by create_job()
        reading a stale onetrainer_config.json from an earlier
        successful Prepare (Mission 134 section 3).

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

        Mission 098: each image's caption comes from
        dataset.entries[image.image_id].caption when that entry exists
        — including when its caption is an explicitly empty string,
        which is never replaced by trigger_word (`metadata.caption if
        metadata is not None else training.trigger_word`, never `caption
        or training.trigger_word` — the latter would incorrectly treat
        an explicit empty caption the same as no entry at all). Absent
        entry falls back to training.trigger_word, reproducing Mission
        097's exact original behavior. A `.txt` is still written for
        every image unconditionally, even when the caption is empty —
        verified directly against the real dependency OneTrainer uses to
        load this sidecar (mgds/pipelineModules/LoadMultipleTexts.py):
        an absent file and a present-but-empty file both resolve to the
        same effective prompt, so this choice has no effect on training,
        only on code simplicity.
        """
        concept_folder = self._training_folder(training.training_id) / _CONCEPT_SUBFOLDER_NAME

        try:
            WorkspaceStorage.delete_folder(concept_folder)
            concept_folder.mkdir(parents=True, exist_ok=True)

            for image in dataset.images:
                source = Path(image.file_path)
                target = WorkspaceStorage.resolve_collision_free_name(source, concept_folder)
                shutil.copy2(source, target)
                metadata = dataset.entries.get(image.image_id)
                caption = metadata.caption if metadata is not None else training.trigger_word
                target.with_suffix(".txt").write_text(caption, encoding="utf-8")
        except (WorkspaceStorageError, OSError) as exc:
            # Mission 134: whatever failed above (the wipe itself, or a
            # copy/write partway through the loop) may have left the
            # concept folder half-rebuilt — never left as-is, since a
            # half-rebuilt folder could later be silently trusted by
            # create_job() reading a stale onetrainer_config.json from
            # an earlier successful Prepare (section 3). This recovery
            # cleanup failing too is never masked as success, and never
            # replaces the original cause `exc` — only appended to it,
            # same idiom as LoRALibraryManager.import_lora()'s own
            # partial-copy-failure cleanup.
            try:
                WorkspaceStorage.delete_folder(concept_folder)
            except WorkspaceStorageError:
                raise TrainingPreparationError(
                    f"Could not materialize the dataset concept folder for training "
                    f"{training.training_id!r}: {exc} Additionally, the partially "
                    f"materialized concept folder could not be cleaned up and remains "
                    f"on disk at {concept_folder} — do not start a training job for "
                    f"this Training without a successful re-run of Prepare."
                ) from exc
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
        base_model_source is empty/whitespace-only or an absolute local
        path that does not exist (Mission 106 — checked first,
        deliberately, before any Character/Dataset resolution: the
        cheapest possible check in this method, and the one guarding
        against a real Dataset materialization for a value already
        certain to be unusable — see src/utils/base_model_source.py),
        if its dataset_id no longer resolves to a real Dataset of the
        active Character, if that Dataset has no images at all (nothing
        to materialize), or on any filesystem failure. Raises
        src.engines.onetrainer_config.OneTrainerConfigError if
        training.architecture is not one of TRAINING_ARCHITECTURES —
        both are real, explicit failures, never silently guessed past.
        """
        training = self._find(training_id)
        if training is None:
            raise TrainingPreparationError(f"Unknown training: {training_id!r}")

        try:
            validate_base_model_source(training.base_model_source)
        except InvalidBaseModelSourceError as exc:
            raise TrainingPreparationError(str(exc)) from exc

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
            # Mission 120: forwarded verbatim — build_training_config()
            # is the only place that knows which of these are still at
            # their "not configured" sentinel (omitted from the built
            # dict) versus explicitly set. extra_overrides validation
            # (protected/structured key collisions) also happens there,
            # never duplicated here.
            batch_size=training.batch_size,
            gradient_accumulation_steps=training.gradient_accumulation_steps,
            learning_rate_scheduler=training.onetrainer_settings.learning_rate_scheduler,
            # Mission 121: forwarded verbatim, same discipline as the
            # Mission 120 fields above — build_training_config() is the
            # only place that knows the "not configured" sentinel (""),
            # translates a configured *_weight_dtype into OneTrainer's
            # real nested shape, and validates architecture/component
            # compatibility.
            train_dtype=training.onetrainer_settings.train_dtype,
            # Mission 127: forwarded verbatim, same discipline as every
            # other OneTrainerSettings field above — build_training_config()
            # is the only place that knows the "not configured" sentinel
            # (""), validates it against OneTrainer's own real
            # GradientCheckpointingMethod values, and writes the flat
            # top-level "gradient_checkpointing" key when configured.
            gradient_checkpointing_mode=training.onetrainer_settings.gradient_checkpointing_mode,
            unet_weight_dtype=training.onetrainer_settings.unet_weight_dtype,
            transformer_weight_dtype=training.onetrainer_settings.transformer_weight_dtype,
            text_encoder_weight_dtype=training.onetrainer_settings.text_encoder_weight_dtype,
            text_encoder_2_weight_dtype=training.onetrainer_settings.text_encoder_2_weight_dtype,
            vae_weight_dtype=training.onetrainer_settings.vae_weight_dtype,
            # Mission 122: forwarded verbatim from the nested
            # optimizer_settings object — build_training_config() is the
            # only place that knows the "not configured" sentinel (""),
            # builds the real nested {"optimizer": {...}} shape, and
            # validates the local optimizer_extra_overrides collision.
            optimizer=training.onetrainer_settings.optimizer_settings.optimizer,
            optimizer_extra_overrides=training.onetrainer_settings.optimizer_settings.extra_overrides,
            # Mission 124: forwarded verbatim, same discipline as every
            # onetrainer_settings field above — build_training_config()
            # is the only place that knows the "not configured"
            # sentinels (None/""), merges train alongside weight_dtype
            # into a single nested component object, validates
            # architecture/component compatibility, and resolves
            # lora_layer_filter's functional intent into the real
            # OneTrainer layer_filter/layer_filter_regex pair.
            text_encoder_train=training.onetrainer_settings.text_encoder_train,
            text_encoder_2_train=training.onetrainer_settings.text_encoder_2_train,
            # Mission 128: forwarded verbatim, same discipline as every
            # onetrainer_settings field above — build_training_config()
            # is the only place that knows the "not configured"
            # sentinels ("" / None), validates the mode/after
            # combination, validates architecture compatibility (TE2
            # rejected for SD1.5), and merges the stop keys into the
            # same nested component object as weight_dtype/train.
            text_encoder_stop_training_mode=(
                training.onetrainer_settings.text_encoder_stop_training_mode
            ),
            text_encoder_stop_training_after=(
                training.onetrainer_settings.text_encoder_stop_training_after
            ),
            text_encoder_2_stop_training_mode=(
                training.onetrainer_settings.text_encoder_2_stop_training_mode
            ),
            text_encoder_2_stop_training_after=(
                training.onetrainer_settings.text_encoder_2_stop_training_after
            ),
            lora_layer_filter=training.onetrainer_settings.lora_layer_filter,
            # Mission 126: forwarded verbatim, same discipline as every
            # onetrainer_settings field above — build_training_config()
            # is the only place that knows the "not configured"
            # sentinels ("" / None / None), validates architecture
            # compatibility (FLUX-only), and translates each field
            # independently, never conditioning one on another.
            timestep_distribution=training.onetrainer_settings.timestep_distribution,
            dynamic_timestep_shifting=training.onetrainer_settings.dynamic_timestep_shifting,
            timestep_shift=training.onetrainer_settings.timestep_shift,
            extra_overrides=training.onetrainer_settings.extra_overrides,
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

    def job_paths(self, training_id: str, job_id: str) -> TrainingJobPaths:
        """
        Mission 100 section 9: pure path arithmetic, no I/O — every
        deterministic, Workspace-owned location for one TrainingJob.
        Used by create_job() below to know where to write, and meant to
        be called again by the QProcess-owning runner (src/ui/) to know
        where to read/watch, without either side re-deriving the
        convention independently.
        """
        job_folder = self._training_folder(training_id) / _JOBS_SUBFOLDER_NAME / job_id
        output_folder = job_folder / _OUTPUT_SUBFOLDER_NAME
        return TrainingJobPaths(
            job_id=job_id,
            config_snapshot_path=str(job_folder / _CONFIG_FILENAME),
            expected_output_path=str(output_folder / _OUTPUT_MODEL_FILENAME),
            command_pipe_path=str(job_folder / _JOB_COMMAND_PIPE_FILENAME),
            workspace_dir=str(job_folder / _JOB_WORKSPACE_SUBFOLDER_NAME),
            cache_dir=str(job_folder / _JOB_CACHE_SUBFOLDER_NAME),
            debug_dir=str(job_folder / _JOB_DEBUG_SUBFOLDER_NAME),
            concept_dir=str(job_folder / _JOB_CONCEPT_SUBFOLDER_NAME),
        )

    def create_job(self, training_id: str) -> TrainingJob:
        """
        Mission 100 section 5.1 (Option B, validated): called only at
        Start, never by prepare_onetrainer_config() — a Prepare, however
        often repeated, never creates a TrainingJob. Captures a frozen
        copy of the Training-level onetrainer_config.json (written by
        the last successful Prepare) into this Job's own folder, with
        output_model_destination/workspace_dir/cache_dir/debug_dir
        overridden to this Job's own Workspace-owned locations (section
        9) — a later Prepare rewrites the Training-level file but never
        this snapshot, and no OneTrainer runtime file is ever written
        under the OneTrainer installation itself.

        Also pre-creates an empty command.pipe — mandatory before the
        OneTrainer process starts, per the empirical protocol result in
        MISSION_100.md section 3.4: OneTrainer's own command reader
        thread permanently exits on FileNotFoundError the very first
        time it does not find this file. No callback.pipe is ever
        created or consumed by Mission 100 (revised contract, section
        7): the OneTrainer process is launched without
        --callback-path, so its own TrainCallbacks stays a pure no-op
        and never attempts to write one — stdout/stderr is the only
        runtime channel this mission uses.

        Raises TrainingJobError if training_id is unknown, if it has
        never been prepared (no onetrainer_config.json yet), or on any
        filesystem failure. Filesystem writes happen before the Domain
        mutation/save() below (same non-transactional convention already
        used by _materialize_concept()/prepare_onetrainer_config() —
        this is an additive, per-job-id folder, harmless to leave
        orphaned if save() subsequently fails, unlike the destructive
        operations Missions 066-077 guard with persistence-first).

        Mission 139: also copies the Training-level concept folder
        (already fully materialized by the Prepare this method requires
        above) into this Job's own concept_dir, and rewrites the
        snapshot's "concepts"[0]["path"] to point at that copy instead
        of the shared Training-level folder. Without this, every Job of
        the same Training would keep referencing the one shared
        `training/<id>/concept/` folder, which _materialize_concept()
        wipes and rebuilds on every later Prepare/Start of *any* Job of
        that Training — silently invalidating what an already-created
        Job's own frozen config snapshot implicitly assumed. This is a
        real isolation gap independent of any interrupted-training/
        resume scenario (see MISSION_139.md); it happens to also be a
        hard prerequisite for a future safe resume, but this mission
        does not implement resume. Unlike output/workspace/cache/debug
        below, a failure copying this concept snapshot is never left
        orphaned on disk: it is cleaned up best-effort before
        TrainingJobError is raised (never touching the shared source
        concept folder), since a partial concept snapshot could
        otherwise later be mistaken for a complete one.
        """
        training = self._find(training_id)
        if training is None:
            raise TrainingJobError(f"Unknown training: {training_id!r}")

        training_config_path = self._training_folder(training_id) / _CONFIG_FILENAME
        if not training_config_path.is_file():
            raise TrainingJobError(
                f"Training {training_id!r} has not been prepared yet — "
                f"call prepare_onetrainer_config() before creating a job"
            )

        try:
            with open(training_config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (OSError, ValueError) as exc:
            raise TrainingJobError(
                f"Could not read the prepared configuration for training {training_id!r}: {exc}"
            ) from exc

        job_id = str(uuid.uuid4())
        paths = self.job_paths(training_id, job_id)
        concept_source_folder = self._training_folder(training_id) / _CONCEPT_SUBFOLDER_NAME

        try:
            Path(paths.concept_dir).mkdir(parents=True, exist_ok=True)
            for source_file in concept_source_folder.iterdir():
                shutil.copy2(source_file, Path(paths.concept_dir) / source_file.name)
        except OSError as exc:
            # Mission 139: this Job's own concept_dir is a brand-new,
            # never-yet-referenced folder (unlike output/workspace/cache/
            # debug below, whose "harmless if orphaned" convention
            # predates this mission and is deliberately left untouched
            # here) — a partial copy must never be left on disk to be
            # mistaken later for a complete snapshot. Same cleanup-then-
            # raise idiom as _materialize_concept() above and
            # LoRALibraryManager.import_lora(): the cleanup failing too
            # is never masked as success and never replaces `exc`, only
            # appended to it. The shared source concept folder is never
            # touched — only this Job's own copy is a candidate for
            # cleanup.
            try:
                WorkspaceStorage.delete_folder(paths.concept_dir)
            except WorkspaceStorageError:
                raise TrainingJobError(
                    f"Could not materialize the concept snapshot for a new job of "
                    f"training {training_id!r}: {exc} Additionally, the partially "
                    f"copied concept snapshot could not be cleaned up and remains "
                    f"on disk at {paths.concept_dir} — remove it manually before "
                    f"creating another job for this training."
                ) from exc
            raise TrainingJobError(
                f"Could not materialize the concept snapshot for a new job of "
                f"training {training_id!r}: {exc}"
            ) from exc

        config["output_model_destination"] = paths.expected_output_path
        config["workspace_dir"] = paths.workspace_dir
        config["cache_dir"] = paths.cache_dir
        config["debug_dir"] = paths.debug_dir
        config["concepts"][0]["path"] = paths.concept_dir

        try:
            Path(paths.expected_output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(paths.workspace_dir).mkdir(parents=True, exist_ok=True)
            Path(paths.cache_dir).mkdir(parents=True, exist_ok=True)
            Path(paths.debug_dir).mkdir(parents=True, exist_ok=True)
            Path(paths.config_snapshot_path).write_text(
                json.dumps(config, indent=4), encoding="utf-8"
            )
            Path(paths.command_pipe_path).touch(exist_ok=True)
        except OSError as exc:
            raise TrainingJobError(
                f"Could not set up the execution folder for a new job of training {training_id!r}: {exc}"
            ) from exc

        job = TrainingJob(
            job_id=job_id,
            state=TRAINING_JOB_STATE_STARTING,
            config_snapshot_path=paths.config_snapshot_path,
            expected_output_path=paths.expected_output_path,
            created_at=time.time(),
        )

        training.jobs.append(job)

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError:
            training.jobs.remove(job)
            raise

        self._publish_job(TRAINING_JOB_CREATED, job)

        return job

    def update_job_state(
        self,
        job_id: str,
        state: str,
        final_output_path: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Mission 100: strictly idempotent, same discipline as every other
        update_*() in this project — returns False (no save(), no event)
        if `state` already equals the job's current state and neither
        final_output_path nor error_message actually changes anything.
        `ended_at` is stamped once, the first time the job reaches a
        TRAINING_JOB_TERMINAL_STATES value — never overwritten again.

        Never validates `state` against TRAINING_JOB_STATE_* — the only
        caller that knows the real transition rules (starting -> running
        -> succeeded/failed/cancelled, or -> unknown on recovery) is the
        QProcess-owning runner (src/ui/) and this Manager's own
        _recover_stale_jobs(); this method only persists whatever it is
        told, exactly like update_name()/update() elsewhere in this
        Manager never validate business content.
        """
        job = self._find_job(job_id)
        if job is None:
            return False

        changed = (
            state != job.state
            or (final_output_path is not None and final_output_path != job.final_output_path)
            or (error_message is not None and error_message != job.error_message)
        )
        if not changed:
            return False

        previous = (job.state, job.final_output_path, job.error_message, job.ended_at)

        job.state = state
        if final_output_path is not None:
            job.final_output_path = final_output_path
        if error_message is not None:
            job.error_message = error_message
        if state in TRAINING_JOB_TERMINAL_STATES and job.ended_at == 0.0:
            job.ended_at = time.time()

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError:
            job.state, job.final_output_path, job.error_message, job.ended_at = previous
            raise

        self._publish_job(TRAINING_JOB_STATE_CHANGED, job)

        return True

    def set_job_imported_lora_id(self, job_id: str, lora_id: str) -> bool:
        """
        Mission 103: persists the link between a succeeded TrainingJob
        and the Central LoRA Library entry it was imported into.
        Deliberately a separate method from update_job_state() — this is
        a Library-linkage concern, not an execution-lifecycle
        transition, and must never touch state/final_output_path/
        error_message. Called only after LoRALibraryManager.import_lora()
        has already returned successfully (MISSION_103.md section 3.5) —
        never before, never on its failure.

        Same idempotent/rollback-on-save-failure discipline as every
        other update_*() method in this project: same value -> False, no
        save(), no event. No event is published on a real change either
        (MISSION_103.md section 3.4) — no other component needs to know
        this link changed; TrainingPage, the only caller, already knows
        the result of its own call and refreshes itself directly.
        """
        job = self._find_job(job_id)
        if job is None:
            return False

        if lora_id == job.imported_lora_id:
            return False

        previous = job.imported_lora_id
        job.imported_lora_id = lora_id

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError:
            job.imported_lora_id = previous
            raise

        return True

    def has_active_job(self) -> bool:
        """
        Mission 100 section 11 (close guard): True if any TrainingJob of
        any Training belonging to the active Character is currently
        "starting"/"running" — checked across every Training, not just
        the selected one, since a Job's real OS process keeps running
        regardless of what is currently selected in the UI.
        """
        for training in self.trainings:
            for job in training.jobs:
                if job.state in TRAINING_JOB_ACTIVE_STATES:
                    return True
        return False

    def _find_job(self, job_id: str) -> Optional[TrainingJob]:
        for training in self.trainings:
            for job in training.jobs:
                if job.job_id == job_id:
                    return job
        return None

    def _publish_job(self, event_name: str, job: TrainingJob) -> None:
        if self._event_bus is None:
            return
        self._event_bus.publish(event_name, job.to_dict())

    def delete(self, training_id: str) -> TrainingDeletionResult:
        """
        Mission 068: if save() fails after the Training has already been
        removed from character.trainings, the deletion is rolled back
        before the exception is re-raised — the same Training object is
        reinserted at its original index, and active_training_id (if it
        pointed at this Training) is restored to its previous value.

        Mission 145: refuses outright (TrainingActiveError, before any
        mutation) if the targeted Training itself has a job in
        TRAINING_JOB_ACTIVE_STATES — see TrainingActiveError's own
        docstring for why this is scoped to this Training alone rather
        than has_active_job()'s whole-Character scan.

        The Training's own folder (training/<training_id>/, which
        already covers every one of its TrainingJobs and their
        artifacts in a single subtree — see job_paths()) is now deleted
        transactionally along with the Domain object, same order as
        LoRAManager.delete() (see its docstring for the full rationale):
        moved atomically into a lazily-created `.trash/` staging area
        before the Domain mutation — abort before anything is touched
        if that move fails; on a save() failure the Domain rollback
        above always runs first (cannot itself fail), then the folder
        is independently moved back, with an enriched
        WorkspaceManagerError if that reverse move also fails; on
        save() success the staged folder is permanently deleted on a
        best-effort basis, never rolling back an already-persisted
        deletion on failure — only reported via the returned
        TrainingDeletionResult. A folder that never existed (e.g. a
        Training created but never started) is tolerated exactly like
        Dataset/LoRA: the filesystem step is skipped entirely.

        A LoRA already imported into the Central LoRA Library is
        unaffected either way — import_lora() always copies the file
        into the Library's own, independent storage tree, never
        referencing training/<training_id>/ afterward.
        """

        character = self._character_manager.principal_character

        if character is None:
            return TrainingDeletionResult(deleted=False, cleanup_failed=False, residual_path=None)

        training = self._find(training_id)

        if training is None:
            return TrainingDeletionResult(deleted=False, cleanup_failed=False, residual_path=None)

        if any(job.state in TRAINING_JOB_ACTIVE_STATES for job in training.jobs):
            raise TrainingActiveError(
                f"Training {training_id} has an active job and cannot be "
                "deleted. Cancel the running job first, then try again."
            )

        source_folder = self._training_folder(training_id)
        trash_folder = None

        if source_folder.exists():
            workspace_root = Path(self._workspace_manager.current_workspace.root)
            trash_folder = workspace_root / ".trash" / f"training_{training_id}_{uuid.uuid4().hex}"
            try:
                WorkspaceStorage.rename_folder(source_folder, trash_folder)
            except WorkspaceStorageError as exc:
                raise WorkspaceManagerError(str(exc)) from exc

        index = character.trainings.index(training)
        previous_active_training_id = self.active_training_id

        character.trainings.remove(training)

        if self.active_training_id == training_id:
            self.active_training_id = None

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError as exc:
            # The Domain rollback must always run, regardless of whether
            # the filesystem rollback below succeeds — these two plain
            # statements cannot themselves raise.
            character.trainings.insert(index, training)
            self.active_training_id = previous_active_training_id

            if trash_folder is not None:
                try:
                    WorkspaceStorage.rename_folder(trash_folder, source_folder)
                except WorkspaceStorageError as rollback_exc:
                    raise WorkspaceManagerError(
                        f"{exc} The Training itself has been restored in "
                        f"the project and is safe. However, its folder "
                        f"could not be moved back from its temporary "
                        f"location and now remains at {trash_folder} "
                        f"instead of {source_folder} ({rollback_exc}). "
                        f"Manual recovery required: move {trash_folder} "
                        f"back to {source_folder} yourself once the "
                        "underlying issue is resolved."
                    ) from rollback_exc
            raise

        cleanup_failed = False
        residual_path = None

        if trash_folder is not None:
            try:
                WorkspaceStorage.delete_folder(trash_folder)
            except WorkspaceStorageError:
                cleanup_failed = True
                residual_path = str(trash_folder)

        self._publish(TRAINING_DELETED, training)

        return TrainingDeletionResult(
            deleted=True, cleanup_failed=cleanup_failed, residual_path=residual_path
        )

    def _find(self, training_id: str) -> Optional[Training]:
        for training in self.trainings:
            if training.training_id == training_id:
                return training
        return None

    def _publish(self, event_name: str, training: Training) -> None:

        if self._event_bus is None:
            return

        self._event_bus.publish(event_name, training.to_dict())
