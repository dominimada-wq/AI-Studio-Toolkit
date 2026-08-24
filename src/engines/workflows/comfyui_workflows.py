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

DEMO_CHECKPOINT_NAME = "v1-5-pruned-emaonly.safetensors"

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
) -> dict:
    """
    Mission 012's fixed demonstration workflow (ComfyUI API format) —
    a minimal, local checkpoint-based txt2img graph, structurally
    similar to ComfyUI's own published basic_api_example.py. Moved
    here unchanged in Mission 023 (renamed from build_demo_workflow()
    for naming symmetry with build_img2img_workflow() below) — same
    node IDs, same class_type values, same connections, same defaults.
    This is a detail of the txt2img convenience path, not a property
    of ComfyUIEngine's generic contract: the transport primitives
    (submit / wait_for_result / download_output / upload_image) never
    reference checkpoint_name, SDXL, FLUX, or any other model/provider
    concept. checkpoint_name is exposed as a parameter specifically so
    a manual test against a real ComfyUI instance can point at
    whatever checkpoint is actually installed there.

    lora_name/lora_strength (Mission 059): see _apply_lora() above.
    lora_name="" (default) reproduces this function's pre-Mission-059
    output byte-for-byte.
    """
    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "cfg": 8,
                "denoise": 1,
                "latent_image": ["5", 0],
                "model": ["4", 0],
                "negative": ["7", 0],
                "positive": ["6", 0],
                "sampler_name": "euler",
                "scheduler": "normal",
                "seed": random.randint(0, 2**32 - 1),
                "steps": 20,
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint_name},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"batch_size": 1, "height": 512, "width": 512},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["4", 1], "text": prompt_text},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["4", 1], "text": "text, watermark"},
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
) -> dict:
    """
    Mission 023's first non-txt2img graph — native ComfyUI core nodes
    only, no custom node, no IP-Adapter, no ControlNet: LoadImage ->
    VAEEncode feeds KSampler's latent_image (replacing
    build_txt2img_workflow()'s EmptyLatentImage entirely — no width/
    height/batch_size to set, ComfyUI derives the latent's dimensions
    from the loaded image itself), sampled with denoise < 1 so the
    reference's composition/content carries into the result while the
    prompt still has room to act, then decoded and saved exactly like
    the txt2img graph.

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
    """
    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "cfg": 8,
                "denoise": denoise,
                "latent_image": ["5", 0],
                "model": ["4", 0],
                "negative": ["7", 0],
                "positive": ["6", 0],
                "sampler_name": "euler",
                "scheduler": "normal",
                "seed": random.randint(0, 2**32 - 1),
                "steps": 20,
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
            "inputs": {"clip": ["4", 1], "text": "text, watermark"},
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
