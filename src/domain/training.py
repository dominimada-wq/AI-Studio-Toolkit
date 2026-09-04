from dataclasses import dataclass


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

    # trigger_word: Mission 097's explicitly provisional minimum
    # captioning strategy (see MISSION_097.md section 6.4) — used
    # verbatim as every materialized image's sidecar caption content.
    # Never the final captioning architecture; a future real caption
    # source replaces this field's role without changing the
    # materialized folder's shape or naming contract.
    trigger_word: str = ""

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
            "trigger_word": self.trigger_word,
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
            trigger_word=data.get("trigger_word", ""),
        )
