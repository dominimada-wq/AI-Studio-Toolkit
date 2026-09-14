from dataclasses import dataclass, field

from src.domain.onetrainer_settings import OneTrainerSettings
from src.domain.training_job import TrainingJob


@dataclass
class Training:

    training_id: str = ""

    name: str = ""

    # Character ownership is implicit via Character.trainings.
    # References the source Dataset used by this training session.
    dataset_id: str = ""

    # Mission 097: generic training hyperparameters — deliberately named
    # for what they mean to AI Studio Toolkit, never for what OneTrainer
    # calls them (see MISSION_097.md section 4). A future second
    # provider would read the exact same fields; only its own adapter
    # module would translate them differently.
    #
    # base_model_source: an opaque string for this Domain — a local
    # .safetensors/.ckpt file, a local Diffusers folder, or (technically
    # accepted by OneTrainer, though not the path exposed by this
    # mission's UI) a Hugging Face identifier. Never validated or
    # interpreted here; only src/engines/onetrainer_config.py's adapter
    # gives it meaning.
    base_model_source: str = ""

    # architecture: one of the small, closed, generic set defined in
    # TrainingManager (TRAINING_ARCHITECTURE_SD15/_SDXL/_FLUX) — never
    # OneTrainer's own ~25-value ModelType enum, which stays entirely
    # inside the OneTrainer adapter's own translation table.
    architecture: str = ""

    # resolution: deliberately no single hardcoded default — the
    # correct value depends entirely on `architecture` (512 for SD15,
    # 1024 for SDXL, 768 for Flux, confirmed against OneTrainer's own
    # real LoRA presets, MISSION_097.md section 3.7). 0 means "not yet
    # configured"; the UI suggests an architecture-appropriate value
    # the moment an architecture is chosen, never this Domain object.
    resolution: int = 0

    # epochs/learning_rate/lora_rank/lora_alpha: MISSION_097.md section
    # 3.7 confirms empirically (identical or unmodified across
    # OneTrainer's own real SD1.5/SDXL/Flux LoRA presets) that a single
    # shared default is not artificial for these four — unlike
    # resolution above.
    epochs: int = 100

    learning_rate: float = 0.0003

    lora_rank: int = 16

    lora_alpha: float = 1.0

    # batch_size/gradient_accumulation_steps: Mission 120 — generic
    # training hyperparameters, independent of OneTrainer's own
    # vocabulary (OneTrainer calls them exactly this, but the concept
    # applies to any real Training provider). 0 is never a legitimate
    # value for either field in OneTrainer's own TrainConfig (a real
    # batch or a real accumulation count is always >= 1) — a safe
    # "not configured" sentinel, same convention already established by
    # `resolution` above (Mission 097). Omitted from the built OneTrainer
    # config when 0, letting OneTrainer's own default (1 for both)
    # apply exactly as it does today — MISSION_120.md section 3.2/4.
    batch_size: int = 0

    gradient_accumulation_steps: int = 0

    # trigger_word: Mission 097's explicitly provisional minimum
    # captioning strategy (see MISSION_097.md section 6.4) — used
    # verbatim as every materialized image's sidecar caption content.
    # Never the final captioning architecture; a future real caption
    # source replaces this field's role without changing the
    # materialized folder's shape or naming contract.
    trigger_word: str = ""

    # onetrainer_settings: Mission 120 — structured, typed OneTrainer-
    # specific configuration (see src/domain/onetrainer_settings.py's
    # own docstring for why this is the one accepted exception to
    # Training's own provider-agnostic vocabulary). Always present,
    # never None, same convention as `jobs` below (an empty/default
    # OneTrainerSettings() is indistinguishable in its effect from this
    # field never having existed — MISSION_120.md section 8).
    onetrainer_settings: OneTrainerSettings = field(default_factory=OneTrainerSettings)

    # Mission 100: every real execution attempt of this Training, in
    # creation order — never shared/overwritten between attempts (see
    # MISSION_100.md section 5/9). A TrainingJob is created only at
    # Start, never by prepare_onetrainer_config().
    jobs: list[TrainingJob] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "training_id": self.training_id,
            "name": self.name,
            "dataset_id": self.dataset_id,
            "base_model_source": self.base_model_source,
            "architecture": self.architecture,
            "resolution": self.resolution,
            "epochs": self.epochs,
            "learning_rate": self.learning_rate,
            "lora_rank": self.lora_rank,
            "lora_alpha": self.lora_alpha,
            "batch_size": self.batch_size,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "trigger_word": self.trigger_word,
            "onetrainer_settings": self.onetrainer_settings.to_dict(),
            "jobs": [job.to_dict() for job in self.jobs],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Training":
        return cls(
            training_id=data.get("training_id", ""),
            name=data.get("name", ""),
            dataset_id=data.get("dataset_id", ""),
            # Mission 097: every new field defaults exactly as this
            # dataclass's own field defaults above when absent — strict
            # backward compatibility with every project.json written
            # before this mission, never a migration.
            base_model_source=data.get("base_model_source", ""),
            architecture=data.get("architecture", ""),
            resolution=data.get("resolution", 0),
            epochs=data.get("epochs", 100),
            learning_rate=data.get("learning_rate", 0.0003),
            lora_rank=data.get("lora_rank", 16),
            lora_alpha=data.get("lora_alpha", 1.0),
            batch_size=data.get("batch_size", 0),
            gradient_accumulation_steps=data.get("gradient_accumulation_steps", 0),
            trigger_word=data.get("trigger_word", ""),
            # Mission 120: absent from any project.json written before
            # this mission — defaults to OneTrainerSettings()'s own
            # defaults exactly like this dataclass's own field default
            # above, never a migration. Same isinstance(x, dict) guard
            # already used for every other nested Domain object
            # deserialized from a possibly hand-edited project.json.
            onetrainer_settings=(
                OneTrainerSettings.from_dict(data["onetrainer_settings"])
                if isinstance(data.get("onetrainer_settings"), dict)
                else OneTrainerSettings()
            ),
            # Mission 100: new field, no prior format existed to be
            # defensive against — same defensive filtering convention
            # as Character.datasets/loras/prompts (isinstance guard
            # against a manually edited project.json), applied here
            # from this field's very introduction.
            jobs=[
                TrainingJob.from_dict(j)
                for j in (data.get("jobs") or [])
                if isinstance(j, dict)
            ],
        )
