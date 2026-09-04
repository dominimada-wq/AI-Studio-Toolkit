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
    """
    model_type = _MODEL_TYPE_BY_ARCHITECTURE.get(architecture)
    if model_type is None:
        raise OneTrainerConfigError(
            f"Unsupported training architecture: {architecture!r} "
            f"(expected one of {sorted(_MODEL_TYPE_BY_ARCHITECTURE)})"
        )

    return {
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
