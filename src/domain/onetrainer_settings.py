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

    # Mission 121: precision/weight-dtype fields — "" means "not
    # configured", never one of DataType's own real enum values (see
    # MISSION_121.md section 3.2). Each is omitted from the built config
    # when empty, letting OneTrainer's own real default apply exactly as
    # it did before this mission (train_dtype=FLOAT_16, every
    # weight_dtype=FLOAT_32 today — never injected here).
    #
    # train_dtype: global compute dtype (TrainConfig.train_dtype).
    train_dtype: str = ""

    # unet_weight_dtype/transformer_weight_dtype: deliberately two
    # distinct fields, never merged — TrainConfig.unet and
    # TrainConfig.transformer are two different, mutually exclusive
    # components depending on the architecture (SD1.5/SDXL use unet,
    # FLUX_DEV_1 uses transformer, confirmed in modules/model/
    # StableDiffusionModel.py/StableDiffusionXLModel.py/FluxModel.py) —
    # see MISSION_121.md section 3.1. build_training_config() is the
    # only place that validates which one is legal for a given
    # architecture (section 3.3 there).
    unet_weight_dtype: str = ""
    transformer_weight_dtype: str = ""

    # text_encoder_weight_dtype/text_encoder_2_weight_dtype:
    # TrainConfig.text_encoder/text_encoder_2. text_encoder_2 is not a
    # real component for SD1.5 (see MISSION_121.md section 3.3/4) —
    # validated the same way as unet/transformer above, never here.
    text_encoder_weight_dtype: str = ""
    text_encoder_2_weight_dtype: str = ""

    # vae_weight_dtype: TrainConfig.vae — present for all three
    # architectures Toolkit currently exposes.
    vae_weight_dtype: str = ""

    # Raw, unstructured OneTrainer config keys this Domain does not yet
    # model explicitly. Never validated here — validation against the
    # protected/structured key lists happens once, at the translation
    # boundary (src/engines/onetrainer_config.py), never duplicated here.
    extra_overrides: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "learning_rate_scheduler": self.learning_rate_scheduler,
            "train_dtype": self.train_dtype,
            "unet_weight_dtype": self.unet_weight_dtype,
            "transformer_weight_dtype": self.transformer_weight_dtype,
            "text_encoder_weight_dtype": self.text_encoder_weight_dtype,
            "text_encoder_2_weight_dtype": self.text_encoder_2_weight_dtype,
            "vae_weight_dtype": self.vae_weight_dtype,
            "extra_overrides": dict(self.extra_overrides),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OneTrainerSettings":
        extra_overrides = data.get("extra_overrides")
        return cls(
            learning_rate_scheduler=data.get("learning_rate_scheduler", ""),
            train_dtype=data.get("train_dtype", ""),
            unet_weight_dtype=data.get("unet_weight_dtype", ""),
            transformer_weight_dtype=data.get("transformer_weight_dtype", ""),
            text_encoder_weight_dtype=data.get("text_encoder_weight_dtype", ""),
            text_encoder_2_weight_dtype=data.get("text_encoder_2_weight_dtype", ""),
            vae_weight_dtype=data.get("vae_weight_dtype", ""),
            extra_overrides=dict(extra_overrides) if isinstance(extra_overrides, dict) else {},
        )
