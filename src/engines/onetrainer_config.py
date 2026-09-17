"""
Mission 097: pure OneTrainer configuration-dict construction — plain
functions returning dict, no filesystem I/O, no knowledge of Workspace/
Training/Character. Mirrors src/engines/workflows/comfyui_workflows.py's
own placement and philosophy exactly: this is the one and only place
that knows OneTrainer's own vocabulary (ModelType, TrainConfig's field
names, ConceptConfig's shape) — TrainingManager passes it plain,
Toolkit-generic values and never learns any of that vocabulary itself.

Audited directly against the OneTrainer installation present on this
machine (J:\\Programmes\\Onetrainer\\, version confirmed via
modules/util/config/TrainConfig.py/ConceptConfig.py — see
MISSION_097.md section 3 for the full trail of evidence). Not a package
dependency of this project: AI Studio Toolkit never imports OneTrainer's
own code, it only ever produces a plain dict that OneTrainer's own
scripts/train.py --config-path can consume.

Deliberately minimal, same discipline as comfyui_workflows.py: only the
keys this mission actually needs to set are included in the returned
dict. Every other TrainConfig/ConceptConfig field is left absent —
confirmed in source (modules/util/config/BaseConfig.py's from_dict(),
which only ever mutates fields present in the input dict, silently
keeping every default_values() default otherwise) that OneTrainer
itself fills in a safe, complete default for anything omitted. This is
what keeps this adapter from having to know or duplicate OneTrainer's
own ~150-field schema.
"""

from typing import Optional

# Mission 097 section 3.4: the only three architectures this mission
# supports, each confirmed against a real model loader and a real
# shipped LoRA preset in the installed OneTrainer version. Never
# OneTrainer's own ModelType enum (~25 values) — TrainingManager's
# TRAINING_ARCHITECTURE_* constants are the Toolkit-facing vocabulary;
# this dict is the one and only place the translation happens. Kept as
# plain strings (never importing OneTrainer's own enum, which would add
# a real package dependency this project does not have) — these are
# exactly ModelType's own .value strings, confirmed in
# modules/util/enum/ModelType.py.
_MODEL_TYPE_BY_ARCHITECTURE = {
    "SD15": "STABLE_DIFFUSION_15",
    "SDXL": "STABLE_DIFFUSION_XL_10_BASE",
    "FLUX": "FLUX_DEV_1",
}

# Mission 097 — discovered empirically while running this mission's own
# real smoke test (not anticipated by the mini-audit): BaseConfig.
# from_dict() (modules/util/config/BaseConfig.py in the installed
# OneTrainer) reads an optional top-level "__version" key and, when it
# is ABSENT, defaults to version 0 and replays every migration function
# registered up to TrainConfig's own current config_version — each of
# those migrations assumes it is transforming a real, fully-populated
# OLD config previously saved by OneTrainer itself, not a fresh, sparse
# dict this adapter deliberately keeps minimal (see this module's own
# docstring). Replaying them against a minimal dict crashes partway
# through (confirmed: migration 9 raises KeyError on a "unet" structure
# this adapter never sends). Sending "__version" already equal to the
# installed TrainConfig's own config_version makes that replay loop a
# no-op, letting the plain per-field default-merge this adapter was
# actually designed around run as originally verified.
#
# _AUDITED_CONFIG_VERSION is NOT a universal OneTrainer format
# constant — it is this specific installation's TrainConfig.
# config_version at the time Mission 097 was audited and implemented
# (confirmed via `grep config_version= TrainConfig.py` -> 10, and via
# this mission's own real smoke test using the installed TrainConfig
# class itself). A future OneTrainer update on this machine can change
# that number; this module has no way to detect that on its own (no
# dynamic version discovery is introduced here — deliberately out of
# scope for Mission 097, see MISSION_097.md). Any mission that goes on
# to actually launch OneTrainer must re-audit config_version first —
# see MISSION_097.md's own documented future condition/debt.
_AUDITED_CONFIG_VERSION = 10

# Mission 120 section 3.3: every OneTrainer config key that
# TrainingManager itself computes and writes last (job_paths()/
# create_job(), never a Domain field, never user-editable) — always
# forbidden in extra_overrides, regardless of whether this function
# happens to set any of them itself. Centralized here, in the one
# module that validates extra_overrides, and covered by a dedicated
# test enumerating this exact set (test_onetrainer_config.py) so a
# future change to this set is never silent.
_PROTECTED_CONFIG_KEYS = frozenset(
    {
        "workspace_dir",
        "cache_dir",
        "debug_dir",
        "output_model_destination",
        "concept_file_name",
        "concepts",
        "__version",
    }
)

# Mission 120 section 3.3: every OneTrainer config key this function
# already sets from a structured Training/OneTrainerSettings field —
# forbidden in extra_overrides so a single value never has two
# conflicting sources of truth. A future mission that promotes another
# field to a structured parameter must add its OneTrainer key here in
# the same change, never after the fact.
#
# Mission 121 section 3.5: "train_dtype" (flat) and "unet"/"transformer"/
# "text_encoder"/"text_encoder_2"/"vae" (the nested component keys
# themselves, not a sub-path within them) are reserved unconditionally
# — extra_overrides can never carry a raw dict for any of these, which
# would otherwise silently collide with (or bypass) the structured
# {"weight_dtype": ...} object this function builds for a configured
# dtype field. Reserved regardless of whether the corresponding
# OneTrainerSettings dtype field is itself configured for this
# Training — same unconditional-reservation precedent already
# established for "batch_size"/"gradient_accumulation_steps" by
# Mission 120.
#
# Mission 124 section 2.G: "layer_filter"/"layer_filter_regex" join this
# set for the exact same reason — once lora_layer_filter becomes a real
# structured field, extra_overrides must never be able to recreate a
# second, conflicting source of truth for either key. Reserved
# unconditionally, regardless of whether lora_layer_filter itself is
# configured for this Training, same as every other key above.
#
# Mission 126 section 6: "timestep_distribution"/
# "dynamic_timestep_shifting"/"timestep_shift" join this set for the
# same reason, flat top-level keys this time (no nested component
# object) — reserved unconditionally, regardless of whether any of the
# three OneTrainerSettings fields is itself configured for this
# Training.
#
# Mission 127 section 5: "gradient_checkpointing" joins this set for the
# same reason — a flat top-level key, reserved unconditionally regardless
# of whether gradient_checkpointing_mode is itself configured for this
# Training, so extra_overrides can never become a second, conflicting
# source of truth for it.
_STRUCTURED_CONFIG_KEYS = frozenset(
    {
        "training_method",
        "model_type",
        "base_model_name",
        "resolution",
        "epochs",
        "learning_rate",
        "lora_rank",
        "lora_alpha",
        "batch_size",
        "gradient_accumulation_steps",
        "learning_rate_scheduler",
        "output_model_format",
        "train_dtype",
        "gradient_checkpointing",
        "unet",
        "transformer",
        "text_encoder",
        "text_encoder_2",
        "vae",
        "optimizer",
        "layer_filter",
        "layer_filter_regex",
        "timestep_distribution",
        "dynamic_timestep_shifting",
        "timestep_shift",
    }
)

# Mission 122 section 3.3: a second, narrower reservation — checked only
# against OneTrainerOptimizerSettings.extra_overrides (the escape hatch
# scoped to the optimizer object itself), never against the global
# extra_overrides above. Protects only the "optimizer" discriminant
# sub-key from being redefined a second time inside its own object —
# every other real OneTrainer optimizer hyperparameter (weight_decay,
# beta1, ...) stays legal there until a future mission types it as a
# field of OneTrainerOptimizerSettings, at which point its name joins
# this set in the same change (same discipline as
# _STRUCTURED_CONFIG_KEYS itself).
_OPTIMIZER_STRUCTURED_SUBKEYS = frozenset({"optimizer"})

# Mission 121 section 3.3/4: which of the 5 per-component
# OneTrainerSettings dtype fields are actually valid for a given
# Toolkit architecture — confirmed directly against the real component
# fields of modules/model/StableDiffusionModel.py (unet/text_encoder/
# vae, no transformer/text_encoder_2), StableDiffusionXLModel.py
# (unet/text_encoder/text_encoder_2/vae, no transformer), and
# FluxModel.py (transformer/text_encoder/text_encoder_2/vae, no unet).
# "train_dtype" is global and valid for all three, so it is
# deliberately absent from these per-architecture sets (never checked
# against them — see build_training_config()'s own validation below).
_DTYPE_FIELDS_BY_ARCHITECTURE = {
    "SD15": frozenset({"unet_weight_dtype", "text_encoder_weight_dtype", "vae_weight_dtype"}),
    "SDXL": frozenset(
        {
            "unet_weight_dtype",
            "text_encoder_weight_dtype",
            "text_encoder_2_weight_dtype",
            "vae_weight_dtype",
        }
    ),
    "FLUX": frozenset(
        {
            "transformer_weight_dtype",
            "text_encoder_weight_dtype",
            "text_encoder_2_weight_dtype",
            "vae_weight_dtype",
        }
    ),
}

# Mission 121 section 3.4: translation from each Toolkit dtype field
# name to the real nested OneTrainer component key it maps to.
_DTYPE_FIELD_TO_COMPONENT_KEY = {
    "unet_weight_dtype": "unet",
    "transformer_weight_dtype": "transformer",
    "text_encoder_weight_dtype": "text_encoder",
    "text_encoder_2_weight_dtype": "text_encoder_2",
    "vae_weight_dtype": "vae",
}

# Mission 129 section 10/14: text_encoder_2_weight_dtype is deliberately
# excluded from this set — a genuinely incompatible value for this field
# (e.g. configured while the current architecture is SD15) no longer
# raises OneTrainerConfigError, it is silently omitted from emission
# instead (see the dtype accumulation loop below), same M128-style
# "no raise, just omit" pattern already used for stop-training.
# unet_weight_dtype/transformer_weight_dtype keep the original raise-based
# gating unchanged — a structurally different problem (their own
# mutually-exclusive _draft mechanism in the UI), deliberately out of
# scope for Mission 129 (MISSION_129.md section 14). text_encoder_weight_
# dtype/vae_weight_dtype are valid for every architecture Toolkit exposes
# and were never actually gated by this check to begin with.
_DTYPE_FIELDS_STILL_RAISING_ON_INCOMPATIBLE_ARCHITECTURE = frozenset(
    {
        "unet_weight_dtype",
        "transformer_weight_dtype",
        "text_encoder_weight_dtype",
        "vae_weight_dtype",
    }
)

# Mission 124 section 2.D: a twin table to _DTYPE_FIELDS_BY_ARCHITECTURE
# above, deliberately never merged into it (renaming/generalizing that
# existing, already-tested constant risked breaking anything enumerating
# it by name) — same validation algorithm, applied to a second table of
# data, exactly the precedent already set by _OPTIMIZER_STRUCTURED_SUBKEYS
# existing alongside _STRUCTURED_CONFIG_KEYS below. text_encoder_train is
# valid for every architecture Toolkit exposes (SD15 has exactly one Text
# Encoder, confirmed in modules/model/StableDiffusionModel.py); only
# text_encoder_2_train is architecture-gated, mirroring
# text_encoder_2_weight_dtype's own SD15 exclusion exactly.
#
# Mission 129 section 10: this table no longer feeds a raise-based check —
# text_encoder_2_train configured while architecture-incompatible (SD15)
# is silently omitted from emission instead (same M128-style pattern as
# stop-training), never an OneTrainerConfigError. text_encoder_train never
# actually triggered that raise to begin with (valid for every
# architecture), so this change has no effect on it whatsoever.
_TRAIN_FIELDS_BY_ARCHITECTURE = {
    "SD15": frozenset({"text_encoder_train"}),
    "SDXL": frozenset({"text_encoder_train", "text_encoder_2_train"}),
    "FLUX": frozenset({"text_encoder_train", "text_encoder_2_train"}),
}

# Mission 124: translation from each Toolkit train field name to the
# real nested OneTrainer component key it maps to — the exact same
# component keys _DTYPE_FIELD_TO_COMPONENT_KEY above already uses for
# text_encoder/text_encoder_2, since a Training configuring both a
# weight_dtype and a train value for the same component must produce a
# single merged nested object, never two independent writes to the same
# key (see build_training_config()'s component_configs accumulation
# below).
_TRAIN_FIELD_TO_COMPONENT_KEY = {
    "text_encoder_train": "text_encoder",
    "text_encoder_2_train": "text_encoder_2",
}

# Mission 128 section 6/11: a fourth table, jumelle of
# _TRAIN_FIELDS_BY_ARCHITECTURE above — never merged into it (same
# precedent as Mission 124 section 2.D / Mission 126 section 3.2).
# text_encoder_stop_training_mode is valid for every architecture
# Toolkit exposes (SD15 has exactly one Text Encoder); only
# text_encoder_2_stop_training_mode is architecture-gated, mirroring
# text_encoder_2_train's own SD15 exclusion exactly.
_STOP_TRAINING_FIELDS_BY_ARCHITECTURE = {
    "SD15": frozenset({"text_encoder_stop_training_mode"}),
    "SDXL": frozenset({"text_encoder_stop_training_mode", "text_encoder_2_stop_training_mode"}),
    "FLUX": frozenset({"text_encoder_stop_training_mode", "text_encoder_2_stop_training_mode"}),
}

# Mission 128: translation from each Toolkit stop-training mode field
# name to the real nested OneTrainer component key it maps to — the
# exact same component keys _DTYPE_FIELD_TO_COMPONENT_KEY/
# _TRAIN_FIELD_TO_COMPONENT_KEY above already use for
# text_encoder/text_encoder_2, so weight_dtype/train/stop_training_after
# for the same component always land in a single merged nested object.
_STOP_TRAINING_FIELD_TO_COMPONENT_KEY = {
    "text_encoder_stop_training_mode": "text_encoder",
    "text_encoder_2_stop_training_mode": "text_encoder_2",
}

# Mission 128 section 3/6: the real values of OneTrainer's own TimeUnit
# enum that this mission actually exposes — confirmed directly against
# modules/util/enum/TimeUnit.py. Deliberately excludes "ALWAYS" (no
# Toolkit product need identified — see MISSION_128.md section 4) and
# "SECOND"/"MINUTE"/"HOUR" (excluded by OneTrainer's own official UI
# for this exact field via supports_time_units=False, confirmed
# MISSION_128.md section 3.2/5). Same first-value-validation precedent
# as _GRADIENT_CHECKPOINTING_VALUES above.
_STOP_TRAINING_MODE_VALUES = frozenset({"NEVER", "EPOCH", "STEP"})

# Mission 126 section 3.2/2.9: a third table, jumelle of
# _DTYPE_FIELDS_BY_ARCHITECTURE/_TRAIN_FIELDS_BY_ARCHITECTURE above —
# never merged into them (same precedent as Mission 124 section 2.D).
# timestep_distribution/dynamic_timestep_shifting/timestep_shift are
# confirmed, by direct reading of OneTrainer's own modelSetup code
# (BaseFluxSetup.py/ModelSetupNoiseMixin.py), to be consumed only by
# flow-matching architectures — never referenced by
# BaseStableDiffusionSetup.py/BaseStableDiffusionXLSetup.py. FLUX is the
# only flow-matching architecture this project currently supports, so
# SD15/SDXL get an empty frozenset: any of the three fields configured
# for either architecture is rejected the same way transformer_weight_dtype
# is rejected for SD15 today.
#
# Mission 129 section 10/12: "rejected" above describes the pre-M129
# behavior only. This table no longer feeds a raise-based check — any of
# the three fields configured while architecture-incompatible (SD15/SDXL)
# is now silently omitted from emission instead (same M128-style pattern
# as stop-training), never an OneTrainerConfigError. The three fields'
# own interactions with each other (e.g. dynamic_timestep_shifting=True
# making timestep_shift a runtime no-op) are entirely unchanged — this
# table only ever gated architecture, never one field against another.
_FLOW_MATCHING_FIELDS_BY_ARCHITECTURE = {
    "SD15": frozenset(),
    "SDXL": frozenset(),
    "FLUX": frozenset(
        {
            "timestep_distribution",
            "dynamic_timestep_shifting",
            "timestep_shift",
        }
    ),
}

# Mission 127 section 3/8: the real values of OneTrainer's own
# GradientCheckpointingMethod enum — confirmed directly against
# modules/util/enum/GradientCheckpointingMethod.py. Unlike every
# *_weight_dtype field (which forwards any string unvalidated, confirmed
# Mission 126 section 7), this is the first field in this module to
# validate its own value rather than just its field name/architecture —
# gradient_checkpointing is generic to every architecture (the gating
# `config.gradient_checkpointing.enabled()` exists identically in all 3
# real setup files), so no per-architecture table is needed here, only a
# value check.
_GRADIENT_CHECKPOINTING_VALUES = frozenset({"OFF", "ON", "CPU_OFFLOADED"})

# Mission 124 section 2.E: layer_filter_preset (OneTrainer's own Tkinter-
# only UI convenience) has zero effect on the headless training path
# Toolkit actually uses (confirmed: scripts/train_remote.py hydrates
# TrainConfig directly from the plain config dict, with no resolution of
# layer_filter_preset anywhere in that path) — only the real, engine-
# consumed layer_filter (a comma-separated substring/regex pattern list)
# and layer_filter_regex fields have any effect. This table translates
# Toolkit's one functional discriminant ("ATTN_MLP") into that real pair,
# confirmed directly against each architecture's own LAYER_PRESETS dict
# (modules/modelSetup/BaseStableDiffusionSetup.py/
# BaseStableDiffusionXLSetup.py: {"attn-mlp": ["attentions"]};
# BaseFluxSetup.py: {"attn-mlp": ["attn", "ff.net"]}), each joined with
# "," exactly as OneTrainer's own UI callback does
# (modules/util/ui/components.py::preset_set_layer_choice()). FLUX's own
# official LoRA preset does not configure this at all (transformer
# trained in full) — "ATTN_MLP" for FLUX is a capability this project
# offers, never a reproduction of an official OneTrainer recommendation;
# this must stay true in any UI copy or documentation referencing it.
_LORA_LAYER_FILTER_TRANSLATION = {
    "ATTN_MLP": {
        "SD15": {"layer_filter": "attentions", "layer_filter_regex": False},
        "SDXL": {"layer_filter": "attentions", "layer_filter_regex": False},
        "FLUX": {"layer_filter": "attn,ff.net", "layer_filter_regex": False},
    },
}


class OneTrainerConfigError(Exception):
    """Raised when this module is asked to build a config it cannot express."""


def build_training_config(
    architecture: str,
    base_model_source: str,
    resolution: int,
    epochs: int,
    learning_rate: float,
    lora_rank: int,
    lora_alpha: float,
    output_model_destination: str,
    concept_name: str,
    concept_path: str,
    batch_size: int = 0,
    gradient_accumulation_steps: int = 0,
    learning_rate_scheduler: str = "",
    train_dtype: str = "",
    gradient_checkpointing_mode: str = "",
    unet_weight_dtype: str = "",
    transformer_weight_dtype: str = "",
    text_encoder_weight_dtype: str = "",
    text_encoder_2_weight_dtype: str = "",
    vae_weight_dtype: str = "",
    optimizer: str = "",
    optimizer_extra_overrides: Optional[dict] = None,
    text_encoder_train: Optional[bool] = None,
    text_encoder_2_train: Optional[bool] = None,
    text_encoder_stop_training_mode: str = "",
    text_encoder_stop_training_after: Optional[int] = None,
    text_encoder_2_stop_training_mode: str = "",
    text_encoder_2_stop_training_after: Optional[int] = None,
    lora_layer_filter: str = "",
    timestep_distribution: str = "",
    dynamic_timestep_shifting: Optional[bool] = None,
    timestep_shift: Optional[float] = None,
    extra_overrides: Optional[dict] = None,
) -> dict:
    """
    Returns a dict directly json.dump()-able into a file consumable by
    OneTrainer's own `scripts/train.py --config-path` (Mission 097
    section 3.1) — never executed by this function or by anything it
    calls; building the dict is the entire contract here.

    architecture must be one of TrainingManager's TRAINING_ARCHITECTURE_*
    constants ("SD15"/"SDXL"/"FLUX") — anything else raises
    OneTrainerConfigError explicitly, never a silent fallback to some
    arbitrary architecture.

    training_method is always "LORA" — never a parameter, this module
    (and this mission) supports no other OneTrainer training method.

    concepts (Mission 097 section 3.2): embedded directly as a single-
    element list under the "concepts" key — confirmed in
    modules/dataLoader/mixin/DataLoaderMgdsMixin.py that OneTrainer only
    ever falls back to reading concept_file_name from disk when
    "concepts" is absent/null, so no second file is ever needed. Each
    concept dict here is deliberately minimal ("name"/"path" only) —
    confirmed in modules/util/config/BaseConfig.py's from_dict() that a
    partial concept dict is merged onto ConceptConfig.default_values()
    exactly like the outer TrainConfig itself is, so every other
    ConceptConfig field (image/text augmentation, balancing, seed, ...)
    safely keeps OneTrainer's own default — never duplicated here.

    resolution (an int in this Domain, Mission 096 precedent) is
    converted to OneTrainer's own string representation here — the one
    and only place that conversion happens, confirmed against the real
    literal "512"/"1024"/"768" observed in OneTrainer's own shipped
    presets.

    output_model_destination/concept_path are expected to already be
    absolute, fully-resolved paths (TrainingManager's own
    responsibility, derived from Workspace.root + training_id — see
    MISSION_097.md section 3.6) — this function never resolves or
    validates them, only forwards them verbatim.

    Mission 120: batch_size/gradient_accumulation_steps/
    learning_rate_scheduler are optional, structured, Toolkit-generic-
    or-OneTrainer-typed parameters — each omitted from the returned
    dict at its own "not configured" sentinel (0/0/""), letting
    OneTrainer's own real default apply exactly as it did before this
    mission (never a new Toolkit-imposed default, see MISSION_120.md
    section 4/8).

    Mission 121: train_dtype/unet_weight_dtype/transformer_weight_dtype/
    text_encoder_weight_dtype/text_encoder_2_weight_dtype/
    vae_weight_dtype follow the exact same "not configured" sentinel
    contract ("") — omitted from the returned dict when empty, never
    injecting a Toolkit-imposed default. train_dtype is forwarded as a
    flat top-level key; each *_weight_dtype field, when configured, is
    translated into the real nested OneTrainer shape
    ({"<component>": {"weight_dtype": <value>}}) — never a flat key —
    confirmed compatible with OneTrainer's own partial-dict merge
    (BaseConfig.from_dict(), same precedent as `concepts` above: every
    other field of that component's TrainModelPartConfig keeps its own
    OneTrainer default, never duplicated here).

    Raises OneTrainerConfigError, naming the architecture and the
    offending field(s), if any *_weight_dtype field is configured for a
    component that does not exist for the selected architecture (see
    _DTYPE_FIELDS_BY_ARCHITECTURE — e.g. transformer_weight_dtype for
    "SD15", which has no transformer). This validation happens at this
    translation boundary, never only in the UI, so a hand-edited
    project.json or a future direct caller is protected exactly like a
    normal UI-driven Training (MISSION_121.md section 3.3).

    Mission 122: optimizer/optimizer_extra_overrides follow the same
    "not configured" sentinel contract — no "optimizer" key is added to
    the returned dict when both optimizer == "" and
    optimizer_extra_overrides is empty, letting OneTrainer's own real
    default (ADAMW) apply exactly as it did before this mission. When
    either is non-empty, they are combined into the real nested shape
    ({"optimizer": {"optimizer": <value>, **optimizer_extra_overrides}})
    — confirmed compatible with OneTrainer's own partial-dict merge,
    same precedent as the dtype fields above. optimizer_extra_overrides
    is a second, narrower escape hatch than the global extra_overrides
    below — scoped to this nested object only, so that reserving
    "optimizer" globally (see below) never blocks any of OneTrainer's
    real optimizer hyperparameters not yet modeled as a structured
    parameter here (MISSION_122.md section 3.3). Raises
    OneTrainerConfigError if optimizer_extra_overrides itself contains
    the "optimizer" key (see _OPTIMIZER_STRUCTURED_SUBKEYS) — the
    discriminant would otherwise have two conflicting sources of truth
    within its own object.

    extra_overrides (Mission 120) is a plain dict of additional raw
    OneTrainer config keys, merged on top of everything else this
    function already sets — the escape hatch for any real OneTrainer
    setting not yet modeled as a structured parameter here. Raises
    OneTrainerConfigError, naming the offending key(s), before merging
    anything, if it contains any key from _PROTECTED_CONFIG_KEYS
    (internal paths/values TrainingManager always computes and writes
    last — never overridable) or _STRUCTURED_CONFIG_KEYS (a key this
    function already sets from a structured parameter above — never two
    sources of truth for the same value). Never a silent overwrite in
    either direction.

    Mission 122: a legacy extra_overrides["optimizer"] (legal before
    this mission, since "optimizer" was not yet in
    _STRUCTURED_CONFIG_KEYS) is rejected with a dedicated, actionable
    message distinct from the generic _STRUCTURED_CONFIG_KEYS message —
    naming the now-reserved root key and pointing at
    OneTrainerOptimizerSettings.extra_overrides as the new location for
    any nested optimizer parameter. Never migrated automatically (see
    MISSION_122.md section 3.4).

    Mission 124: text_encoder_train/text_encoder_2_train follow the
    same "not configured" sentinel contract as every dtype field above,
    except the sentinel is None instead of "" (a bool has no natural
    empty-string equivalent — MISSION_124.md section 6). Raises
    OneTrainerConfigError, naming the architecture, if
    text_encoder_2_train is configured for "SD15" (see
    _TRAIN_FIELDS_BY_ARCHITECTURE) — same validation timing and style
    as the dtype fields, never only a UI-side restriction. When either
    a dtype field and/or a train field is configured for the same
    OneTrainer component (e.g. text_encoder_weight_dtype and
    text_encoder_train together), both land in a single nested object
    ({"text_encoder": {"weight_dtype": ..., "train": ...}}) — never two
    independent assignments to the same config[component_key], which
    would silently let whichever runs second discard the other
    (MISSION_124.md section 2.B).

    lora_layer_filter (Mission 124) is a Toolkit-facing functional
    intent ("" = not configured, "ATTN_MLP" the only real value so
    far) — never the literal OneTrainer-resolved pattern string. "" is
    omitted entirely (OneTrainer's own default: every layer trained).
    A configured value is resolved through _LORA_LAYER_FILTER_TRANSLATION
    into the real, per-architecture layer_filter/layer_filter_regex
    pair — layer_filter_preset itself is deliberately never written:
    it only affects OneTrainer's own Tkinter UI, with zero effect on
    the headless scripts/train_remote.py path this project actually
    uses (confirmed empirically, MISSION_124.md section 2.E). "ATTN_MLP"
    on "FLUX" is a capability this project offers, never a reproduction
    of FLUX's own official LoRA preset (which does not configure any
    layer filter at all).

    Mission 126: timestep_distribution/dynamic_timestep_shifting/
    timestep_shift are flat top-level keys (unlike the dtype/train
    fields above, never nested under a component object) — confirmed
    directly against OneTrainer's own modelSetup code that these three
    fields are consumed only by flow-matching architectures (FLUX here).
    Raises OneTrainerConfigError, naming the architecture, if any of the
    three is configured for "SD15"/"SDXL" (see
    _FLOW_MATCHING_FIELDS_BY_ARCHITECTURE) — same validation timing and
    style as the dtype/train fields above, never only a UI-side
    restriction. "" / None / None mean "not configured" and are omitted
    entirely, letting OneTrainer's own real defaults
    (UNIFORM/False/1.0) apply exactly as before this mission.

    Each of the three is translated strictly independently — never a
    condition cross-checking one against another. In particular,
    timestep_shift is written whenever it is configured, regardless of
    dynamic_timestep_shifting's own value: OneTrainer itself ignores
    timestep_shift at runtime when dynamic_timestep_shifting=True (its
    own resolution-dependent value is used instead), but that is a fact
    of the engine's own execution, never reproduced here as a Toolkit-
    side field suppression (MISSION_126.md section 2.8/7).

    Mission 127: gradient_checkpointing_mode follows the same "not
    configured" sentinel contract as train_dtype ("" omitted, letting
    OneTrainer's own real default — ON — apply exactly as it did before
    this mission). Unlike every *_weight_dtype field, a configured value
    is validated against _GRADIENT_CHECKPOINTING_VALUES — the real,
    exhaustive set of OneTrainer's own GradientCheckpointingMethod
    values — raising OneTrainerConfigError on anything else, never a
    silent pass-through and never a case-correction. This is a flat
    top-level key (like the flow-matching fields above), valid
    identically for every architecture this project supports (confirmed
    MISSION_127.md section 3.1: the same `.enabled()` gate exists in all
    3 real setup files) — no per-architecture table is needed, unlike
    the dtype/train/flow-matching fields.

    Mission 128: text_encoder_stop_training_mode/
    text_encoder_stop_training_after (and their text_encoder_2_
    counterparts) follow the same "not configured" sentinel contract as
    text_encoder_train/text_encoder_2_train above ("" / None omitted,
    letting OneTrainer's own real default — 30/EPOCH — apply exactly as
    it did before this mission). Architecture compatibility is checked
    against _STOP_TRAINING_FIELDS_BY_ARCHITECTURE, but — deliberately
    UNLIKE every dtype/train/flow-matching field above — an incompatible-
    but-configured field (text_encoder_2_stop_training_mode configured
    while architecture is "SD15") is never raised as an error: it is
    silently excluded from the built config instead (see
    MISSION_128.md section 10). This is an intentional product decision,
    not an oversight — this mission's own UI persists a Text Encoder 2
    duration configured under SDXL/FLUX in the Domain even while the
    Training is temporarily switched to SD1.5, so a config legitimately
    built from that Domain state while on SD1.5 must never fail just
    because that now-inapplicable value is still sitting there. A
    configured mode is also validated
    against _STOP_TRAINING_MODE_VALUES (the same first-value-validation
    style as gradient_checkpointing_mode) and against its own paired
    *_after value: "" or "NEVER" require *_after to be None (never a
    numeric value with no effect), "EPOCH"/"STEP" require *_after to be
    a real int >= 1 — never a bool (bool is a subclass of int in
    Python; checked via `type(value) is int`, never bare `isinstance`),
    never 0 or negative, never silently corrected. "NEVER" is written
    as `stop_training_after_unit` alone — `stop_training_after` is
    deliberately never written alongside it (MISSION_128.md section 9),
    since OneTrainer ignores that value unconditionally under NEVER.
    When configured, the mode/after pair merges into the exact same
    nested component object as weight_dtype/train for that component —
    never a fourth independent assignment that could silently discard
    an earlier one (same accumulator as Mission 124 section 2.B).
    """
    model_type = _MODEL_TYPE_BY_ARCHITECTURE.get(architecture)
    if model_type is None:
        raise OneTrainerConfigError(
            f"Unsupported training architecture: {architecture!r} "
            f"(expected one of {sorted(_MODEL_TYPE_BY_ARCHITECTURE)})"
        )

    config = {
        # Mission 097: mandatory — see _AUDITED_CONFIG_VERSION's own
        # comment above for why an absent "__version" would instead
        # make the installed TrainConfig replay every historical
        # migration against this deliberately minimal dict and crash.
        "__version": _AUDITED_CONFIG_VERSION,
        "training_method": "LORA",
        "model_type": model_type,
        "base_model_name": base_model_source,
        "resolution": str(resolution),
        "epochs": epochs,
        "learning_rate": learning_rate,
        "lora_rank": lora_rank,
        "lora_alpha": lora_alpha,
        "output_model_format": "SAFETENSORS",
        "output_model_destination": output_model_destination,
        "concepts": [
            {
                "name": concept_name,
                "path": concept_path,
            }
        ],
    }

    # Mission 120 section 3.2/4: 0 is never a legitimate batch size or
    # accumulation step count in OneTrainer's own TrainConfig, and ""
    # is never one of LearningRateScheduler's own real enum values —
    # each is therefore only added when the caller actually configured
    # it, never unconditionally.
    if batch_size:
        config["batch_size"] = batch_size
    if gradient_accumulation_steps:
        config["gradient_accumulation_steps"] = gradient_accumulation_steps
    if learning_rate_scheduler:
        config["learning_rate_scheduler"] = learning_rate_scheduler

    # Mission 121 section 3.3: architecture/component validation, always
    # active regardless of the caller (UI, a hand-edited project.json,
    # or any future direct caller) — never only a UI-side restriction.
    dtype_fields = {
        "unet_weight_dtype": unet_weight_dtype,
        "transformer_weight_dtype": transformer_weight_dtype,
        "text_encoder_weight_dtype": text_encoder_weight_dtype,
        "text_encoder_2_weight_dtype": text_encoder_2_weight_dtype,
        "vae_weight_dtype": vae_weight_dtype,
    }
    allowed_dtype_fields = _DTYPE_FIELDS_BY_ARCHITECTURE.get(architecture, frozenset())
    # Mission 129 section 10/14: only the fields in
    # _DTYPE_FIELDS_STILL_RAISING_ON_INCOMPATIBLE_ARCHITECTURE can trigger
    # this raise — text_encoder_2_weight_dtype configured-but-incompatible
    # is never an error here (see the dtype accumulation loop below,
    # which silently omits it instead).
    incompatible_fields = sorted(
        field_name
        for field_name, value in dtype_fields.items()
        if value
        and field_name not in allowed_dtype_fields
        and field_name in _DTYPE_FIELDS_STILL_RAISING_ON_INCOMPATIBLE_ARCHITECTURE
    )
    if incompatible_fields:
        raise OneTrainerConfigError(
            f"The following dtype field(s) are not valid for architecture "
            f"{architecture!r}: {incompatible_fields} — this architecture only "
            f"has these components: {sorted(allowed_dtype_fields)}"
        )

    # Mission 124 section 2.D / Mission 129 section 10: text_encoder_train
    # is valid for every architecture Toolkit exposes and never triggered
    # this check to begin with — text_encoder_2_train configured-but-
    # incompatible (e.g. SD15) is never an error, only silently omitted
    # from emission below (see the train accumulation loop), same
    # M128-style pattern as stop-training. allowed_train_fields is still
    # computed here — consumed only by that accumulation loop now, no
    # raise is associated with it any longer.
    train_fields = {
        "text_encoder_train": text_encoder_train,
        "text_encoder_2_train": text_encoder_2_train,
    }
    allowed_train_fields = _TRAIN_FIELDS_BY_ARCHITECTURE.get(architecture, frozenset())

    # Mission 128 section 6/10/11: deliberately NOT the same
    # raise-on-incompatibility algorithm as the dtype/train fields above
    # — see MISSION_128.md section 10 for the documented product
    # decision. text_encoder_2_stop_training_mode/_after are allowed to
    # stay configured in the Domain while the current architecture is
    # SD15 (a Training temporarily switched away from SDXL/FLUX and back
    # must never lose this configuration — see the UI's own persistence
    # contract in src/ui/pages/training_page.py). Value/coherence
    # validation below still applies unconditionally (a genuinely
    # invalid mode/after combination is never excused by architecture),
    # but a validly-configured, merely inapplicable field is silently
    # excluded from the built config instead of raising — computed here,
    # consumed by both the coherence loop below and the accumulation
    # loop further down.
    allowed_stop_training_fields = _STOP_TRAINING_FIELDS_BY_ARCHITECTURE.get(
        architecture, frozenset()
    )

    # Mission 126 section 3.2/2.9 / Mission 129 section 10/12: all three
    # flow-matching fields configured-but-incompatible (SD15/SDXL) are
    # never an error here any longer — silently omitted from emission
    # below instead (see the flow-matching emission block further down),
    # same M128-style pattern as stop-training. allowed_flow_matching_
    # fields is still computed here — consumed only by that emission
    # block now, no raise is associated with it any longer.
    allowed_flow_matching_fields = _FLOW_MATCHING_FIELDS_BY_ARCHITECTURE.get(
        architecture, frozenset()
    )

    # Mission 121 section 3.2/3.4: "" is never one of DataType's own
    # real enum values — train_dtype is forwarded as a flat top-level
    # key when configured.
    if train_dtype:
        config["train_dtype"] = train_dtype

    # Mission 127 section 3/8: the first field-value validation in this
    # module (every *_weight_dtype field above accepts any string
    # unvalidated, confirmed Mission 126 section 7) — gradient_checkpointing
    # is generic to every architecture, so this is a plain value check,
    # never an architecture-gating table. No case-correction, no silent
    # fallback: an unrecognized non-empty value is always a hard error.
    if gradient_checkpointing_mode:
        if gradient_checkpointing_mode not in _GRADIENT_CHECKPOINTING_VALUES:
            raise OneTrainerConfigError(
                f"Unsupported gradient_checkpointing_mode: {gradient_checkpointing_mode!r} "
                f"(expected one of {sorted(_GRADIENT_CHECKPOINTING_VALUES)} or \"\")"
            )
        config["gradient_checkpointing"] = gradient_checkpointing_mode

    # Mission 128 section 3/6/7: mode/after coherence validation, one
    # component at a time — never corrected silently. A bool is a
    # Python subclass of int (isinstance(True, int) is True), so an
    # explicit `type(value) is int` check is used instead of bare
    # isinstance() to make sure True/False can never pass as a real
    # stop_training_after value.
    stop_training_pairs = {
        "text_encoder_stop_training_mode": (
            text_encoder_stop_training_mode,
            text_encoder_stop_training_after,
            "text_encoder_stop_training_after",
        ),
        "text_encoder_2_stop_training_mode": (
            text_encoder_2_stop_training_mode,
            text_encoder_2_stop_training_after,
            "text_encoder_2_stop_training_after",
        ),
    }
    for mode_field_name, (mode, after, after_field_name) in stop_training_pairs.items():
        if not mode and after is None:
            continue
        if mode and mode not in _STOP_TRAINING_MODE_VALUES:
            raise OneTrainerConfigError(
                f"Unsupported {mode_field_name}: {mode!r} "
                f"(expected one of {sorted(_STOP_TRAINING_MODE_VALUES)} or \"\")"
            )
        if mode in ("", "NEVER"):
            if after is not None:
                raise OneTrainerConfigError(
                    f"{after_field_name} must not be set when {mode_field_name} is "
                    f"{mode!r} — OneTrainer ignores a numeric value in that case"
                )
        else:
            # mode is "EPOCH" or "STEP" here.
            if after is None or type(after) is not int or after < 1:
                raise OneTrainerConfigError(
                    f"{after_field_name} must be an int >= 1 when {mode_field_name} "
                    f"is {mode!r}, got {after!r}"
                )

    # Mission 124 section 2.B: dtype and train fields for the same
    # OneTrainer component (e.g. text_encoder_weight_dtype and
    # text_encoder_train) must land in a single merged nested object —
    # accumulated here by component key, never assigned independently,
    # which would let whichever loop ran last silently discard the
    # other's contribution to the same config[component_key].
    component_configs: dict = {}
    # Mission 129 section 10: the membership check below is a no-op for
    # unet_weight_dtype/transformer_weight_dtype/text_encoder_weight_dtype/
    # vae_weight_dtype (already guaranteed compatible by the raise above,
    # otherwise this line would never be reached) — it only has a real
    # effect for text_encoder_2_weight_dtype, which reaches here even when
    # architecture-incompatible (no raise for it any longer) and is now
    # correctly excluded from emission in that case.
    for field_name, value in dtype_fields.items():
        if value and field_name in allowed_dtype_fields:
            component_key = _DTYPE_FIELD_TO_COMPONENT_KEY[field_name]
            component_configs.setdefault(component_key, {})["weight_dtype"] = value
    # Mission 129 section 10: same reasoning as the dtype loop above,
    # applied to allowed_train_fields — a no-op for text_encoder_train
    # (always allowed), the real gate for text_encoder_2_train.
    for field_name, value in train_fields.items():
        if value is not None and field_name in allowed_train_fields:
            component_key = _TRAIN_FIELD_TO_COMPONENT_KEY[field_name]
            component_configs.setdefault(component_key, {})["train"] = value
    # Mission 128 section 8/9: same accumulator as the two loops above —
    # stop_training_after/stop_training_after_unit merge into the exact
    # same nested component object, never a separate assignment that
    # could discard weight_dtype/train already staged for it. "NEVER"
    # writes the unit alone (mode/after coherence already validated
    # above guarantees after is None whenever mode is "" or "NEVER").
    for mode_field_name, (mode, after, _after_field_name) in stop_training_pairs.items():
        if mode and mode_field_name in allowed_stop_training_fields:
            component_key = _STOP_TRAINING_FIELD_TO_COMPONENT_KEY[mode_field_name]
            component_dict = component_configs.setdefault(component_key, {})
            if after is not None:
                component_dict["stop_training_after"] = after
            component_dict["stop_training_after_unit"] = mode
    for component_key, component_dict in component_configs.items():
        config[component_key] = component_dict

    # Mission 124 section 2.E: lora_layer_filter is a Toolkit-facing
    # functional intent, never the literal OneTrainer-resolved pattern
    # — resolved per architecture via _LORA_LAYER_FILTER_TRANSLATION.
    # "" (not configured) adds neither key, preserving OneTrainer's own
    # default (every layer trained) exactly as before this mission.
    # layer_filter_preset itself is deliberately never written: it has
    # no effect whatsoever on the headless path this project uses.
    if lora_layer_filter:
        per_architecture_translation = _LORA_LAYER_FILTER_TRANSLATION.get(lora_layer_filter)
        if per_architecture_translation is None:
            raise OneTrainerConfigError(
                f"Unsupported lora_layer_filter: {lora_layer_filter!r} (expected "
                f"one of {sorted(_LORA_LAYER_FILTER_TRANSLATION)} or \"\")"
            )
        layer_filter_translation = per_architecture_translation.get(architecture)
        if layer_filter_translation is None:
            raise OneTrainerConfigError(
                f"lora_layer_filter {lora_layer_filter!r} has no known translation "
                f"for architecture {architecture!r}"
            )
        config.update(layer_filter_translation)

    # Mission 126 section 2.8/7: flat top-level keys, each translated
    # strictly independently of the other two — never a condition
    # cross-checking one field's value against another's. timestep_shift
    # is written whenever it is configured, even when
    # dynamic_timestep_shifting=True (OneTrainer itself ignores
    # timestep_shift at runtime in that case — an engine execution fact,
    # never reproduced here as a Toolkit-side field suppression).
    #
    # Mission 129 section 10/12: each condition below now also requires
    # architecture membership (allowed_flow_matching_fields) — on FLUX
    # this is always true for a configured field (unchanged behavior); on
    # SD15/SDXL a configured-but-incompatible field is silently excluded
    # instead of having already raised above. dynamic_timestep_shifting's
    # own sentinel check (`is not None`) is evaluated independently of
    # this membership check, so an explicit False is never mistaken for
    # "not configured" by either condition.
    if timestep_distribution and "timestep_distribution" in allowed_flow_matching_fields:
        config["timestep_distribution"] = timestep_distribution
    if (
        dynamic_timestep_shifting is not None
        and "dynamic_timestep_shifting" in allowed_flow_matching_fields
    ):
        config["dynamic_timestep_shifting"] = dynamic_timestep_shifting
    if timestep_shift is not None and "timestep_shift" in allowed_flow_matching_fields:
        config["timestep_shift"] = timestep_shift

    # Mission 122 section 3.2/3.3: optimizer_extra_overrides is a second
    # escape hatch, scoped to the optimizer object only — never the
    # global extra_overrides below. Its only reserved sub-key is
    # "optimizer" itself (_OPTIMIZER_STRUCTURED_SUBKEYS), so any other
    # real OneTrainer optimizer hyperparameter stays legal there.
    optimizer_extra_overrides = optimizer_extra_overrides or {}

    optimizer_subkey_hits = sorted(
        _OPTIMIZER_STRUCTURED_SUBKEYS & optimizer_extra_overrides.keys()
    )
    if optimizer_subkey_hits:
        raise OneTrainerConfigError(
            f"optimizer_extra_overrides cannot redefine keys already set by "
            f"the structured optimizer field: {optimizer_subkey_hits} — edit "
            f"the corresponding field instead"
        )

    optimizer_object = {}
    if optimizer:
        optimizer_object["optimizer"] = optimizer
    if optimizer_extra_overrides:
        optimizer_object.update(optimizer_extra_overrides)
    if optimizer_object:
        config["optimizer"] = optimizer_object

    extra_overrides = extra_overrides or {}

    protected_hits = sorted(_PROTECTED_CONFIG_KEYS & extra_overrides.keys())
    if protected_hits:
        raise OneTrainerConfigError(
            f"extra_overrides cannot set internal keys controlled by "
            f"AI Studio Toolkit: {protected_hits}"
        )

    # Mission 122 section 3.4: a legacy extra_overrides["optimizer"] was
    # legal before this mission ("optimizer" was not yet in
    # _STRUCTURED_CONFIG_KEYS) — rejected here, before the generic
    # _STRUCTURED_CONFIG_KEYS check below, with a dedicated actionable
    # message naming the now-reserved root key and the new location for
    # any nested optimizer parameter. Never migrated automatically.
    if "optimizer" in extra_overrides:
        raise OneTrainerConfigError(
            "extra_overrides['optimizer'] is now managed by structured "
            "optimizer settings — this root key is reserved. Move any "
            "nested optimizer parameter to "
            "OneTrainerOptimizerSettings.extra_overrides "
            "(Training.onetrainer_settings.optimizer_settings.extra_overrides) "
            "instead."
        )

    structured_hits = sorted(_STRUCTURED_CONFIG_KEYS & extra_overrides.keys())
    if structured_hits:
        raise OneTrainerConfigError(
            f"extra_overrides cannot redefine keys already set by a "
            f"structured Training/OneTrainerSettings field: {structured_hits} "
            f"— edit the corresponding field instead"
        )

    config.update(extra_overrides)

    return config
