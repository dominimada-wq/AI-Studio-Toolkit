from dataclasses import dataclass, field
from typing import Optional

from src.domain.onetrainer_optimizer_settings import OneTrainerOptimizerSettings


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

    # Mission 127: which of OneTrainer's own GradientCheckpointingMethod
    # values applies — "" means "not configured", never one of the real
    # enum's own values (OFF/ON/CPU_OFFLOADED), omitted from the built
    # config when empty, letting OneTrainer's own real default (ON) apply
    # exactly as it did before this mission — the exact historical Toolkit
    # behavior (see MISSION_127.md section 3.2 for the confirmed asymmetry:
    # CPU_OFFLOADED behaves exactly like ON on SD1.5/SDXL with default
    # offloading settings — enable_activation_offloading=True/
    # enable_async_offloading=True/layer_offload_fraction=0.0, none of
    # which this mission exposes — and only differs for FLUX, which gets
    # real transformer activation offloading from CPU_OFFLOADED alone).
    gradient_checkpointing_mode: str = ""

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

    # Mission 124: whether each Text Encoder's own weights get a LoRA
    # adapter attached and gradients at all — distinct from its
    # weight_dtype above (dtype applies regardless of whether the
    # component is trained). Deliberately Optional[bool], never the
    # str="" sentinel pattern used everywhere else in this class: a
    # boolean has no natural empty-string equivalent, and None is the
    # most direct Python sentinel for a genuine tri-state (not
    # configured / True / False). This is a documented, deliberate
    # deviation (MISSION_124.md section 6) — never a precedent to copy
    # by analogy for a future field that has a natural str/int sentinel
    # available. None is omitted from the built config entirely,
    # letting OneTrainer's own real default (train=True for every
    # TrainModelPartConfig, confirmed in the installed TrainConfig.py)
    # apply exactly as it did before this mission. text_encoder_2_train
    # is not a real component for SD1.5 — validated the same way as
    # text_encoder_2_weight_dtype above, never here (MISSION_124.md
    # section 2.D).
    text_encoder_train: Optional[bool] = None
    text_encoder_2_train: Optional[bool] = None

    # Mission 128: which OneTrainer TimeUnit governs this Text Encoder's
    # stop_training_after — "" means "not configured", never one of the
    # real engine values (NEVER/EPOCH/STEP), omitted from the built
    # config when empty, letting OneTrainer's own real default
    # (30/EPOCH) apply exactly as it did before this mission — the
    # exact historical Toolkit behavior. 0 is never a sentinel for the
    # paired *_after field below: it is a real engine value (an
    # immediate freeze under EPOCH/STEP, confirmed by tracing
    # TimedActionMixin.single_action_elapsed()), never silently
    # converted to "unlimited" (see MISSION_128.md section 3 for the
    # confirmed semantics of TimeUnit.ALWAYS and the STEP/EPOCH boundary
    # behavior — neither exposed by this mission).
    text_encoder_stop_training_mode: str = ""
    text_encoder_stop_training_after: Optional[int] = None

    text_encoder_2_stop_training_mode: str = ""
    text_encoder_2_stop_training_after: Optional[int] = None

    # Mission 124: which LoRA layers actually receive an adapter. ""
    # means "not configured" — never one of the real functional
    # discriminant values (only "ATTN_MLP" so far) — omitted from the
    # built config when empty, letting OneTrainer's own real default
    # (every layer trained, i.e. an empty/absent layer_filter) apply
    # exactly as it did before this mission. Deliberately a Toolkit-
    # facing functional intent, never the literal OneTrainer-resolved
    # pattern string ("attentions"/"attn,ff.net") — see
    # MISSION_124.md section 2.E/4.3: layer_filter_preset itself has no
    # effect in the headless path Toolkit uses, only the real
    # layer_filter/layer_filter_regex pair does, and that per-
    # architecture translation belongs exclusively to
    # src/engines/onetrainer_config.py, never here.
    lora_layer_filter: str = ""

    # Mission 126: flow-matching timestep/noise settings — FLUX-only
    # (validated the same way as text_encoder_2_weight_dtype: rejected
    # for SD1.5/SDXL by build_training_config(), never here). Real
    # OneTrainer fields (TrainConfig.py: timestep_distribution/
    # dynamic_timestep_shifting/timestep_shift), confirmed only ever
    # consumed by flow-matching architectures (FLUX in this project) —
    # see MISSION_126.md section 3.2.
    #
    # "" means "not configured" — never one of TimestepDistribution's
    # own real enum values (7 total). UI vocabulary deliberately
    # restricted to "" / "UNIFORM" / "LOGIT_NORMAL" (MISSION_126.md
    # section 2.5) — this Domain field itself stays a plain str,
    # capable of carrying any of the 7 real enum values (e.g. from a
    # hand-edited project.json), same defensive tolerance as every
    # other str sentinel field in this class.
    timestep_distribution: str = ""

    # Deliberately Optional[bool], never a str="" sentinel — same
    # reasoning as text_encoder_train (Mission 124 section 6): a
    # boolean has no natural empty-string equivalent. None is omitted
    # from the built config entirely, letting OneTrainer's own real
    # default (dynamic_timestep_shifting=False) apply exactly as it did
    # before this mission.
    dynamic_timestep_shifting: Optional[bool] = None

    # Deliberately Optional[float], never a numeric sentinel (0.0 would
    # collide with a value a user could conceivably want to set, and is
    # mathematically degenerate in OneTrainer's own shift formula) —
    # same reasoning as GenerationMetadata.lora_strength. None is
    # omitted from the built config entirely, letting OneTrainer's own
    # real default (timestep_shift=1.0) apply exactly as it did before
    # this mission. Explicitly independent from
    # dynamic_timestep_shifting at the Domain level (MISSION_126.md
    # section 2.8/3.2): configuring one never resets or mutates the
    # other, even though OneTrainer itself ignores this value at
    # runtime when dynamic_timestep_shifting=True.
    timestep_shift: Optional[float] = None

    # Mission 122: optimizer selection — deliberately its own nested
    # structure (never a flat OneTrainerSettings.optimizer field), so
    # that its own extra_overrides (scoped to the optimizer object only,
    # see OneTrainerOptimizerSettings's own docstring) stays distinct
    # from this class's own extra_overrides below. See MISSION_122.md
    # section 3.1.
    optimizer_settings: OneTrainerOptimizerSettings = field(
        default_factory=OneTrainerOptimizerSettings
    )

    # Raw, unstructured OneTrainer config keys this Domain does not yet
    # model explicitly. Never validated here — validation against the
    # protected/structured key lists happens once, at the translation
    # boundary (src/engines/onetrainer_config.py), never duplicated here.
    extra_overrides: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "learning_rate_scheduler": self.learning_rate_scheduler,
            "train_dtype": self.train_dtype,
            "gradient_checkpointing_mode": self.gradient_checkpointing_mode,
            "unet_weight_dtype": self.unet_weight_dtype,
            "transformer_weight_dtype": self.transformer_weight_dtype,
            "text_encoder_weight_dtype": self.text_encoder_weight_dtype,
            "text_encoder_2_weight_dtype": self.text_encoder_2_weight_dtype,
            "vae_weight_dtype": self.vae_weight_dtype,
            "text_encoder_train": self.text_encoder_train,
            "text_encoder_2_train": self.text_encoder_2_train,
            "text_encoder_stop_training_mode": self.text_encoder_stop_training_mode,
            "text_encoder_stop_training_after": self.text_encoder_stop_training_after,
            "text_encoder_2_stop_training_mode": self.text_encoder_2_stop_training_mode,
            "text_encoder_2_stop_training_after": self.text_encoder_2_stop_training_after,
            "lora_layer_filter": self.lora_layer_filter,
            "timestep_distribution": self.timestep_distribution,
            "dynamic_timestep_shifting": self.dynamic_timestep_shifting,
            "timestep_shift": self.timestep_shift,
            "optimizer_settings": self.optimizer_settings.to_dict(),
            "extra_overrides": dict(self.extra_overrides),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OneTrainerSettings":
        extra_overrides = data.get("extra_overrides")
        optimizer_settings = data.get("optimizer_settings")
        # Defensive per CLAUDE.md's explicit-type-guard convention: a
        # malformed, truthy-but-wrong-typed value (e.g. a hand-edited
        # project.json carrying "true" as a string) must degrade to the
        # safe "not configured" sentinel, never pass through as-is.
        raw_text_encoder_train = data.get("text_encoder_train")
        raw_text_encoder_2_train = data.get("text_encoder_2_train")
        raw_dynamic_timestep_shifting = data.get("dynamic_timestep_shifting")
        raw_timestep_shift = data.get("timestep_shift")
        raw_text_encoder_stop_training_after = data.get("text_encoder_stop_training_after")
        raw_text_encoder_2_stop_training_after = data.get("text_encoder_2_stop_training_after")
        return cls(
            learning_rate_scheduler=data.get("learning_rate_scheduler", ""),
            train_dtype=data.get("train_dtype", ""),
            gradient_checkpointing_mode=data.get("gradient_checkpointing_mode", ""),
            unet_weight_dtype=data.get("unet_weight_dtype", ""),
            transformer_weight_dtype=data.get("transformer_weight_dtype", ""),
            text_encoder_weight_dtype=data.get("text_encoder_weight_dtype", ""),
            text_encoder_2_weight_dtype=data.get("text_encoder_2_weight_dtype", ""),
            vae_weight_dtype=data.get("vae_weight_dtype", ""),
            text_encoder_train=(
                raw_text_encoder_train if isinstance(raw_text_encoder_train, bool) else None
            ),
            text_encoder_2_train=(
                raw_text_encoder_2_train if isinstance(raw_text_encoder_2_train, bool) else None
            ),
            text_encoder_stop_training_mode=data.get("text_encoder_stop_training_mode", ""),
            text_encoder_stop_training_after=(
                raw_text_encoder_stop_training_after
                if isinstance(raw_text_encoder_stop_training_after, int)
                and not isinstance(raw_text_encoder_stop_training_after, bool)
                else None
            ),
            text_encoder_2_stop_training_mode=data.get("text_encoder_2_stop_training_mode", ""),
            text_encoder_2_stop_training_after=(
                raw_text_encoder_2_stop_training_after
                if isinstance(raw_text_encoder_2_stop_training_after, int)
                and not isinstance(raw_text_encoder_2_stop_training_after, bool)
                else None
            ),
            lora_layer_filter=data.get("lora_layer_filter", ""),
            timestep_distribution=data.get("timestep_distribution", ""),
            dynamic_timestep_shifting=(
                raw_dynamic_timestep_shifting
                if isinstance(raw_dynamic_timestep_shifting, bool)
                else None
            ),
            timestep_shift=(
                raw_timestep_shift
                if isinstance(raw_timestep_shift, (int, float))
                and not isinstance(raw_timestep_shift, bool)
                else None
            ),
            optimizer_settings=(
                OneTrainerOptimizerSettings.from_dict(optimizer_settings)
                if isinstance(optimizer_settings, dict)
                else OneTrainerOptimizerSettings()
            ),
            extra_overrides=dict(extra_overrides) if isinstance(extra_overrides, dict) else {},
        )
