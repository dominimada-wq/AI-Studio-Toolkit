"""
Single-responsibility helper: counts the content tokens of caption lines with
the two SDXL CLIP tokenizers OneTrainer's supported SDXL training path uses.

It is launched as its own OS process with OneTrainer's own Python interpreter
(<onetrainer_path>/venv/Scripts/python.exe) — never imported by, and never run
inside, AI Studio Toolkit's main PySide6 process, which has neither
`transformers` nor `tokenizers`. Same boundary as onetrainer_cancel_helper.py.

Contract (protocol 1):
- stdin: one UTF-8 JSON object {"protocol": 1, "lines": ["...", ...]}.
- stdout: one ASCII JSON object, always, even on failure (exit code 0):
  {"protocol": 1, "ok": true, "tokenizers": [...], "results": [...], "meta": {...}}
  or {"protocol": 1, "ok": false, "error": "..."}.
- "tokenizers" has one entry per SDXL tokenizer, in order (`tokenizer`,
  `tokenizer_2`), each carrying its source (repo id, snapshot revision,
  subfolder), class, `model_max_length`, the number of special tokens added per
  sequence, the resulting content limit, or an `error` string when it could not
  be loaded or failed a compatibility check (then it is never used for counts).
- "results" has one entry per input line, each holding one count per tokenizer
  (null for a tokenizer with an error): content tokens, special tokens, and,
  only when the line exceeds the content limit, the text kept and the text
  truncated, both reconstructed by DECODING the tokens (they are normalized by
  the tokenizer — lower case, collapsed spaces — and may differ from the
  original characters; they are not slices of the original text).

What it never does: no network access (offline flags are forced before any
import and every load uses `local_files_only=True`), no model or weight
loading, no GPU use (CUDA is hidden from the process and `torch` is never
imported by this file), no write on disk, no change to any OneTrainer file.

Tokenizer source. OneTrainer builds an SDXL pipeline from a single-file
checkpoint with `StableDiffusionXLPipeline.from_single_file(...)`
(modules/modelLoader/stableDiffusionXL/StableDiffusionXLModelLoader.py,
`__load_safetensors`). In OneTrainer's bundled diffusers
(src/diffusers/src/diffusers/loaders/single_file_utils.py,
DIFFUSERS_DEFAULT_PIPELINE_PATHS["xl_base"]) the pipeline configuration of an
SDXL base checkpoint is "stabilityai/stable-diffusion-xl-base-1.0", whose
`tokenizer` and `tokenizer_2` subfolders hold the `CLIPTokenizer` files. They are
loaded here with the same class (`transformers.CLIPTokenizer`) from the local
Hugging Face cache snapshot of that repository. If the cache has no such
snapshot, nothing else is substituted: the tokenizers are reported with an
error and the caller shows "non vérifiable".
"""

import json
import os
import sys

PROTOCOL = 1

SOURCE_REPO_ID = "stabilityai/stable-diffusion-xl-base-1.0"
SOURCE_SUBFOLDERS = ("tokenizer", "tokenizer_2")
EXPECTED_MODEL_MAX_LENGTH = 77


def _force_offline_cpu_environment() -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["TOKENIZERS_PARALLELISM"] = "false"


def _emit(payload: dict) -> None:
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=True).encode("ascii"))
    sys.stdout.buffer.flush()


def _resolve_snapshot(repo_id: str):
    """Local cache snapshot of `repo_id` (tokenizer subfolders only), never the network."""
    from huggingface_hub import snapshot_download

    path = snapshot_download(
        repo_id,
        local_files_only=True,
        allow_patterns=[f"{subfolder}/*" for subfolder in SOURCE_SUBFOLDERS],
    )
    return path


def _load_tokenizer(snapshot_path: str, subfolder: str) -> dict:
    """Returns a dict describing one tokenizer: either usable (`tokenizer` set) or with an `error`."""
    info = {
        "name": subfolder,
        "repo_id": SOURCE_REPO_ID,
        "subfolder": subfolder,
        "revision": os.path.basename(snapshot_path),
        "class": None,
        "model_max_length": None,
        "special_tokens_per_sequence": None,
        "content_limit": None,
        "error": None,
        "tokenizer": None,
    }
    try:
        from transformers import CLIPTokenizer

        tokenizer = CLIPTokenizer.from_pretrained(
            snapshot_path, subfolder=subfolder, local_files_only=True
        )
        info["class"] = type(tokenizer).__name__
        info["model_max_length"] = int(tokenizer.model_max_length)
        if info["model_max_length"] != EXPECTED_MODEL_MAX_LENGTH:
            info["error"] = (
                f"unexpected model_max_length {info['model_max_length']} "
                f"(expected {EXPECTED_MODEL_MAX_LENGTH})"
            )
            return info
        with_special = len(tokenizer("", add_special_tokens=True, truncation=False)["input_ids"])
        without_special = len(tokenizer("", add_special_tokens=False, truncation=False)["input_ids"])
        special = with_special - without_special
        if without_special != 0 or special < 0:
            info["error"] = "the empty text does not tokenize to special tokens only"
            return info
        info["special_tokens_per_sequence"] = special
        info["content_limit"] = info["model_max_length"] - special
        if info["content_limit"] <= 0:
            info["error"] = "no room left for content tokens"
            return info
        info["tokenizer"] = tokenizer
    except Exception as exc:  # noqa: BLE001 — reported, never raised: the caller shows "non verifiable"
        info["error"] = f"{type(exc).__name__}: {exc}"
    return info


def _count_line(info: dict, line: str) -> dict:
    tokenizer = info["tokenizer"]
    content_ids = tokenizer(line, add_special_tokens=False, truncation=False)["input_ids"]
    with_special = tokenizer(line, add_special_tokens=True, truncation=False)["input_ids"]
    content_tokens = len(content_ids)
    special_tokens = len(with_special) - content_tokens
    limit = info["content_limit"]
    result = {
        "content_tokens": content_tokens,
        "special_tokens": special_tokens,
        "over": content_tokens > limit,
        "kept_text": None,
        "truncated_text": None,
    }
    if result["over"]:
        result["kept_text"] = tokenizer.decode(content_ids[:limit], skip_special_tokens=True)
        result["truncated_text"] = tokenizer.decode(content_ids[limit:], skip_special_tokens=True)
    return result


def main() -> int:
    _force_offline_cpu_environment()
    try:
        request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        if request.get("protocol") != PROTOCOL:
            raise ValueError(f"unsupported protocol {request.get('protocol')!r}")
        lines = request["lines"]
        if not isinstance(lines, list) or not all(isinstance(line, str) for line in lines):
            raise ValueError("`lines` must be a list of strings")
    except Exception as exc:  # noqa: BLE001
        _emit({"protocol": PROTOCOL, "ok": False, "error": f"invalid request: {exc}"})
        return 0

    try:
        snapshot_path = _resolve_snapshot(SOURCE_REPO_ID)
    except Exception as exc:  # noqa: BLE001
        message = f"{type(exc).__name__}: {exc}"
        tokenizers = [
            {
                "name": subfolder, "repo_id": SOURCE_REPO_ID, "subfolder": subfolder,
                "revision": None, "class": None, "model_max_length": None,
                "special_tokens_per_sequence": None, "content_limit": None,
                "error": f"no local cache snapshot of {SOURCE_REPO_ID}: {message}",
            }
            for subfolder in SOURCE_SUBFOLDERS
        ]
        _emit({
            "protocol": PROTOCOL, "ok": True, "tokenizers": tokenizers,
            "results": [{"counts": [None] * len(tokenizers)} for _ in lines], "meta": _meta(),
        })
        return 0

    infos = [_load_tokenizer(snapshot_path, subfolder) for subfolder in SOURCE_SUBFOLDERS]
    results = []
    for line in lines:
        counts = []
        for info in infos:
            if info["tokenizer"] is None:
                counts.append(None)
                continue
            try:
                counts.append(_count_line(info, line))
            except Exception as exc:  # noqa: BLE001 — this one line stays "non verifiable"
                counts.append({"error": f"{type(exc).__name__}: {exc}"})
        results.append({"counts": counts})

    public_infos = [{key: value for key, value in info.items() if key != "tokenizer"} for info in infos]
    _emit({"protocol": PROTOCOL, "ok": True, "tokenizers": public_infos, "results": results, "meta": _meta()})
    return 0


def _meta() -> dict:
    meta = {"python": sys.version.split()[0], "transformers": None, "torch_imported": "torch" in sys.modules,
            "cuda_initialized": False}
    try:
        import transformers

        meta["transformers"] = transformers.__version__
    except Exception:  # noqa: BLE001
        pass
    torch = sys.modules.get("torch")
    meta["torch_imported"] = torch is not None
    if torch is not None:
        try:
            meta["cuda_initialized"] = bool(torch.cuda.is_initialized())
        except Exception:  # noqa: BLE001
            meta["cuda_initialized"] = False
    return meta


if __name__ == "__main__":
    sys.exit(main())
