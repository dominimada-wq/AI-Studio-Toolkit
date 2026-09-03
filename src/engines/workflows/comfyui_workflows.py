"""
Mission 023: pure ComfyUI workflow (API-format graph) construction —
plain functions returning dict, no HTTP, no knowledge of submit/poll/
download. Moved out of comfyui_engine.py so that a second graph
(img2img) can exist alongside the original txt2img one without mixing
graph-construction knowledge into the transport layer, and without
that knowledge ever leaking into GenerationManager/InferencePage.

Deliberately minimal: plain functions only — no Workflow class, no
registry, no plugin system, no DSL. Justified only by the concrete
need of this mission (two graphs); not an anticipation of future
mechanisms (IP-Adapter, ControlNet), which would each get their own
function here only once a real need for them is decided. LoRA is the
one exception (Mission 059, _apply_lora()): a native ComfyUI node
(LoraLoader) applied to a server-discovered name, never a Workspace
LoRA.files entry — see ApplicationSettings.comfyui_lora_name's own
docstring for why that mapping does not exist.
"""

import random
from typing import Optional

DEMO_CHECKPOINT_NAME = "v1-5-pruned-emaonly.safetensors"

# Mission 096: the exact literals build_txt2img_workflow()/
# build_img2img_workflow() already hardcoded since Mission 012/023 —
# turned into named defaults so both builders stay byte-for-byte
# compatible for any caller that does not pass these new parameters
# (see the four DEFAULT_* consumers below and MISSION_096.md section 11).
DEFAULT_WIDTH = 512
DEFAULT_HEIGHT = 512
DEFAULT_STEPS = 20
DEFAULT_CFG = 8
DEFAULT_SAMPLER_NAME = "euler"
DEFAULT_SCHEDULER = "normal"
DEFAULT_NEGATIVE_PROMPT = "text, watermark"

# Mission 023: the one and only place denoise is defined for the img2img
# workflow — never duplicated, never exposed above build_img2img_workflow()
# (not by ComfyUIEngine.generate_image(), not by GenerationManager.generate(),
# not by InferencePage). 0.75 is the commonly documented ComfyUI community
# middle-ground default: low enough that the reference's influence stays
# visually observable (needed to actually prove, including during the manual
# smoke test, that the mechanism works), high enough that the text prompt
# still has a real effect on the result (a much lower denoise would produce
# a near-copy of the reference, making the prompt's influence inconclusive
# to observe).
DEFAULT_IMG2IMG_DENOISE = 0.75


def _apply_lora(workflow: dict, lora_name: str, lora_strength: float) -> dict:
    """
    Mission 059: inserts a native LoraLoader node ("11") between
    CheckpointLoaderSimple ("4") and every consumer of its model/clip
    outputs, when lora_name is non-empty. Never touches vae — LoraLoader
    only ever outputs MODEL/CLIP, so every "vae": ["4", 2] input is left
    exactly as CheckpointLoaderSimple wired it.

    Called last by both build_txt2img_workflow()/build_img2img_workflow(),
    after their own graph is fully built with node "4" as the sole
    model/clip source — this function only rewires the two edges
    ("3".model, "6"/"7".clip) that reference "4" for model/clip, it does
    not know or care about the rest of the graph's shape (img2img's
    VAEEncode vs txt2img's EmptyLatentImage, the reference LoadImage
    node, ...). A single combined strength is applied to both
    strength_model/strength_clip — the node itself keeps them distinct,
    but no current need justifies two separate user-facing values (see
    ApplicationSettings.comfyui_lora_strength).

    lora_name empty/falsy: workflow is returned completely untouched,
    same object, no new key — the byte-for-byte compatibility guarantee
    lives here, in one place, rather than being duplicated as an
    early-return in each builder.
    """
    if not lora_name:
        return workflow

    workflow["11"] = {
        "class_type": "LoraLoader",
        "inputs": {
            "model": ["4", 0],
            "clip": ["4", 1],
            "lora_name": lora_name,
            "strength_model": lora_strength,
            "strength_clip": lora_strength,
        },
    }
    workflow["3"]["inputs"]["model"] = ["11", 0]
    workflow["6"]["inputs"]["clip"] = ["11", 1]
    workflow["7"]["inputs"]["clip"] = ["11", 1]

    return workflow


def build_txt2img_workflow(
    prompt_text: str,
    checkpoint_name: str = DEMO_CHECKPOINT_NAME,
    lora_name: str = "",
    lora_strength: float = 1.0,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    steps: int = DEFAULT_STEPS,
    cfg: float = DEFAULT_CFG,
    sampler_name: str = DEFAULT_SAMPLER_NAME,
    scheduler: str = DEFAULT_SCHEDULER,
    seed: Optional[int] = None,
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
) -> dict:
    """
    Mission 012's original demonstration workflow (ComfyUI API format),
    a minimal local checkpoint-based txt2img graph — extended in
    Mission 096 with real generation parameters (width/height/steps/
    cfg/sampler_name/scheduler/seed/negative_prompt) while keeping every
    call site that does not pass them byte-for-byte identical to the
    pre-Mission-096 output (DEFAULT_* constants above reproduce the
    exact literals this function hardcoded since Mission 012/023). Same
    node IDs, same class_type values, same connections as before —
    only the "3"/"5"/"7" node's *inputs* now come from parameters
    instead of literals. This stays a detail of the txt2img convenience
    path, not a property of ComfyUIEngine's generic contract: the
    transport primitives (submit / wait_for_result / download_output /
    upload_image) never reference checkpoint_name, SDXL, FLUX, or any
    other model/provider concept. checkpoint_name is exposed as a
    parameter specifically so a manual test against a real ComfyUI
    instance can point at whatever checkpoint is actually installed
    there.

    lora_name/lora_strength (Mission 059): see _apply_lora() above.
    lora_name="" (default) reproduces this function's pre-Mission-059
    output byte-for-byte.

    seed (Mission 096) stays Optional[int] = None so that a caller who
    never passes it keeps getting a fresh random.randint(0, 2**32 - 1)
    on every call, exactly as before — this is what
    test_seed_is_randomized_between_calls (Mission 012) already asserts
    and must keep asserting unmodified. InferencePage (the only real
    caller that needs to know/display the seed actually used) resolves
    a concrete int itself before calling down, in both its "random" and
    "fixed" modes — see MISSION_096.md section 5. This function's own
    internal fallback is preserved as a courtesy for any other caller
    (tests included) that does not care about that value.

    batch_size intentionally stays a literal 1, not a parameter — see
    MISSION_096.md section 7 (the Accept/Reject/Regenerate pending-result
    contract is structurally single-result; multi-image is documented
    there as a separate future extension, not started here).
    """
    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "cfg": cfg,
                "denoise": 1,
                "latent_image": ["5", 0],
                "model": ["4", 0],
                "negative": ["7", 0],
                "positive": ["6", 0],
                "sampler_name": sampler_name,
                "scheduler": scheduler,
                "seed": seed if seed is not None else random.randint(0, 2**32 - 1),
                "steps": steps,
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint_name},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"batch_size": 1, "height": height, "width": width},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["4", 1], "text": prompt_text},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["4", 1], "text": negative_prompt},
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "AIStudioToolkit", "images": ["8", 0]},
        },
    }

    return _apply_lora(workflow, lora_name, lora_strength)


def _load_image_input(reference_image: dict) -> str:
    """
    Translates the dict ComfyUIEngine.upload_image() (Mission 021)
    returns — {"name", "subfolder", "type"} — into the single string
    value ComfyUI's LoadImage node expects for its "image" input:
    "subfolder/name" when the upload has a subfolder, or just "name"
    at the input root (ComfyUI's own convention for referencing an
    uploaded file). This is the one place that translation happens —
    GenerationManager passes the upload result through unexamined; it
    never constructs this string itself.
    """
    name = reference_image["name"]
    subfolder = reference_image.get("subfolder", "")
    return f"{subfolder}/{name}" if subfolder else name


def build_img2img_workflow(
    prompt_text: str,
    reference_image: dict,
    checkpoint_name: str = DEMO_CHECKPOINT_NAME,
    denoise: float = DEFAULT_IMG2IMG_DENOISE,
    lora_name: str = "",
    lora_strength: float = 1.0,
    steps: int = DEFAULT_STEPS,
    cfg: float = DEFAULT_CFG,
    sampler_name: str = DEFAULT_SAMPLER_NAME,
    scheduler: str = DEFAULT_SCHEDULER,
    seed: Optional[int] = None,
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
) -> dict:
    """
    Mission 023's first non-txt2img graph — native ComfyUI core nodes
    only, no custom node, no IP-Adapter, no ControlNet: LoadImage ->
    VAEEncode feeds KSampler's latent_image (replacing
    build_txt2img_workflow()'s EmptyLatentImage entirely — no width/
    height/batch_size parameter exists here, deliberately, ComfyUI
    derives the latent's dimensions from the loaded image itself), sampled
    with denoise < 1 so the reference's composition/content carries into
    the result while the prompt still has room to act, then decoded and
    saved exactly like the txt2img graph.

    Node IDs "3"/"4"/"6"/"7"/"8"/"9" are deliberately identical in role
    to build_txt2img_workflow()'s — only "5" is repurposed
    (EmptyLatentImage -> VAEEncode) and "10" (LoadImage) is added — so
    the two graphs stay maximally easy to compare side by side.

    reference_image is the exact dict returned by
    ComfyUIEngine.upload_image() — passed through by the caller
    (GenerationManager) without being interpreted; only this function
    knows how to turn it into a LoadImage input (see
    _load_image_input()).

    lora_name/lora_strength (Mission 059): see _apply_lora() above —
    same mechanism as build_txt2img_workflow(), entirely independent of
    the reference/pose_composition mechanism (Mission 021/023/056):
    node "11" is inserted (or not) after this graph's own "3"/"4"/"6"/
    "7" are built, exactly as it would be for txt2img, "10" (LoadImage)
    is never touched either way.

    steps/cfg/sampler_name/scheduler/seed/negative_prompt (Mission 096):
    same KSampler/CLIPTextEncode node shape as build_txt2img_workflow(),
    same DEFAULT_* compatibility guarantee, same seed fallback contract
    (see that function's own docstring) — width/height are deliberately
    absent from this signature, not merely defaulted, per this
    function's own longstanding "no width/height/batch_size to set"
    contract above.
    """
    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "cfg": cfg,
                "denoise": denoise,
                "latent_image": ["5", 0],
                "model": ["4", 0],
                "negative": ["7", 0],
                "positive": ["6", 0],
                "sampler_name": sampler_name,
                "scheduler": scheduler,
                "seed": seed if seed is not None else random.randint(0, 2**32 - 1),
                "steps": steps,
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint_name},
        },
        "5": {
            "class_type": "VAEEncode",
            "inputs": {"pixels": ["10", 0], "vae": ["4", 2]},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["4", 1], "text": prompt_text},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["4", 1], "text": negative_prompt},
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "AIStudioToolkit", "images": ["8", 0]},
        },
        "10": {
            "class_type": "LoadImage",
            "inputs": {"image": _load_image_input(reference_image)},
        },
    }

    return _apply_lora(workflow, lora_name, lora_strength)
