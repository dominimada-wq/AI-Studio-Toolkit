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
        "unet",
        "transformer",
        "text_encoder",
        "text_encoder_2",
        "vae",
    }
)

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
    unet_weight_dtype: str = "",
    transformer_weight_dtype: str = "",
    text_encoder_weight_dtype: str = "",
    text_encoder_2_weight_dtype: str = "",
    vae_weight_dtype: str = "",
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
    incompatible_fields = sorted(
        field_name
        for field_name, value in dtype_fields.items()
        if value and field_name not in allowed_dtype_fields
    )
    if incompatible_fields:
        raise OneTrainerConfigError(
            f"The following dtype field(s) are not valid for architecture "
            f"{architecture!r}: {incompatible_fields} — this architecture only "
            f"has these components: {sorted(allowed_dtype_fields)}"
        )

    # Mission 121 section 3.2/3.4: "" is never one of DataType's own
    # real enum values — train_dtype is forwarded as a flat top-level
    # key when configured; each *_weight_dtype field, when configured,
    # is translated into the real nested OneTrainer component shape.
    if train_dtype:
        config["train_dtype"] = train_dtype
    for field_name, value in dtype_fields.items():
        if value:
            component_key = _DTYPE_FIELD_TO_COMPONENT_KEY[field_name]
            config[component_key] = {"weight_dtype": value}

    extra_overrides = extra_overrides or {}

    protected_hits = sorted(_PROTECTED_CONFIG_KEYS & extra_overrides.keys())
    if protected_hits:
        raise OneTrainerConfigError(
            f"extra_overrides cannot set internal keys controlled by "
            f"AI Studio Toolkit: {protected_hits}"
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
