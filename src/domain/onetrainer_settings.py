from dataclasses import dataclass, field


@dataclass
class OneTrainerSettings:
    """
    Mission 120: structured, typed OneTrainer-specific configuration
    owned by a Training — distinct from Training's own generic fields
    (architecture/resolution/epochs/learning_rate/lora_rank/lora_alpha/
    batch_size/gradient_accumulation_steps), which stay provider-
    agnostic in Toolkit's own vocabulary. This structure is the one
    accepted exception to that discipline (see MISSION_120.md section
    3.1): OneTrainer is the only Training provider actually integrated
    today, and most of what belongs here (optimizer, precision/dtypes,
    memory/offloading, timestep/noise, quantization...) is genuinely
    OneTrainer-shaped vocabulary, not a cross-provider ML concept like
    `architecture` is. Grows field by field across future missions —
    never in one block — without requiring a new refactor each time.

    extra_overrides is the escape hatch for any real OneTrainer config
    key not yet modeled as a typed field here — always snapshotted like
    the rest of the configuration, and always validated by
    src.engines.onetrainer_config.build_training_config() against both
    the protected-internal-keys and the already-structured-keys lists
    before being merged (MISSION_120.md section 3.3) — never a silent
    way to bypass a canonical value or an internal path.
    """

    # "" means "not configured" — never one of LearningRateScheduler's
    # own real enum values (CONSTANT/LINEAR/COSINE/...), so this is a
    # safe sentinel (MISSION_120.md section 3.2). Omitted from the built
    # config dict when empty, letting OneTrainer's own default
    # (CONSTANT) apply exactly as it does today.
    learning_rate_scheduler: str = ""

    # Raw, unstructured OneTrainer config keys this Domain does not yet
    # model explicitly. Never validated here — validation against the
    # protected/structured key lists happens once, at the translation
    # boundary (src/engines/onetrainer_config.py), never duplicated here.
    extra_overrides: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "learning_rate_scheduler": self.learning_rate_scheduler,
            "extra_overrides": dict(self.extra_overrides),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OneTrainerSettings":
        extra_overrides = data.get("extra_overrides")
        return cls(
            learning_rate_scheduler=data.get("learning_rate_scheduler", ""),
            extra_overrides=dict(extra_overrides) if isinstance(extra_overrides, dict) else {},
        )
