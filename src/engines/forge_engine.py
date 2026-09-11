"""
Mission 107: minimal HTTP client for a Stable Diffusion WebUI Forge
instance's own native REST API (POST /sdapi/v1/txt2img, POST
/sdapi/v1/img2img, GET /sdapi/v1/sd-models, /sdapi/v1/loras,
/sdapi/v1/samplers, /sdapi/v1/schedulers — confirmed by reading the
installed Forge's own modules/api/api.py,
extensions-builtin/sd_forge_lora/scripts/lora_script.py, and
modules/processing.py directly, MISSION_107.md section 1/3). Mirrors
ComfyUIEngine's own shape (src/engines/comfyui_engine.py) closely
enough that GenerationManager can address either one interchangeably
— it never assumes Forge is running locally, never launches or
configures Forge itself, and never activates --api (a prerequisite
the architect must satisfy manually, exactly like ComfyUI/OneTrainer).

LoRA (MISSION_107.md section 3.2): Forge's txt2img/img2img request
models carry no dedicated LoRA field — a LoRA is applied through the
`<lora:name:strength>` syntax appended to the prompt itself (the
stable, universal A1111/Forge-ecosystem convention, confirmed by the
absence of any lora field in the installed Forge's own
modules/api/models.py, and by re_lora = re.compile("<lora:([^:]+):")
in its own lora_script.py). This module is the only place that syntax
is ever constructed — no caller of this module ever builds it itself.

Checkpoint (Mission 107, per the architect's explicit constraint on
this mission): a per-call checkpoint is applied via the request's own
native override_settings={"sd_model_checkpoint": ...} mechanism,
together with override_settings_restore_afterwards=True (Forge's own
default) — confirmed directly in the installed Forge's own
modules/processing.py::process_images(), whose own docstring reads
"applies settings overrides (if any) before processing images, then
restores settings as applicable": stored_opts captures the prior
in-memory values of exactly the overridden keys before calling
set_config(p.override_settings, ..., save_config=False), and restores
them via set_config(stored_opts, save_config=False) in a `finally`
block once p.override_settings_restore_afterwards is true. Both
set_config() calls use save_config=False — this mechanism never
touches Forge's persisted options file, and never reaches
/sdapi/v1/options, which would durably change the running instance's
global checkpoint beyond this one request.

Reference images (img2img): reference_image is a dict returned by
upload_image() — deliberately the same two-call shape as
ComfyUIEngine (upload_image() then generate_image(reference_image=...))
even though Forge's own API needs no real upload step: init_images is
sent inline, base64-encoded, in the same request as everything else.
upload_image() here only validates the local file and wraps its path;
no network call happens until generate_image() itself.

denoise (MISSION_107.md section 3.3/3.4): verified equivalent to
ComfyUIEngine's own `denoise` concept — both compute
t_enc = int(strength * steps), the same historical Stable Diffusion
img2img algorithm (confirmed by reading the installed Forge's own
modules/sd_samplers_common.py). Because the two engines' native wire
protocols name this concept differently (ComfyUI's KSampler field is
"denoise"; Forge's own request field is "denoising_strength"), and
GenerationManager must never branch on which concrete engine it is
talking to, generate_image()'s own Python parameter here is named
`denoise` — identically to ComfyUIEngine's own parameter — so
GenerationManager can forward reference_strength under one common
keyword regardless of target engine. This method alone translates
that common name into Forge's own native "denoising_strength" wire
field in the JSON payload sent to Forge.
"""
import base64
import json
import ntpath
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Optional

DEFAULT_WIDTH = 512
DEFAULT_HEIGHT = 512
DEFAULT_STEPS = 20
DEFAULT_CFG = 8
# Forge/A1111's own naming convention ("Euler", capitalized) — distinct
# from ComfyUIEngine's "euler" (see comfyui_workflows.py), confirmed as
# the API model's own default (modules/api/models.py, StableDiffusion
# TxtToImgProcessingAPI's "sampler_index" additional field default).
DEFAULT_SAMPLER_NAME = "Euler"
# None (not a string): Forge's own dataclass default is `scheduler:
# str = None`, letting Forge resolve a scheduler from sampler_name
# itself (modules/processing.py) — a hardcoded string here would
# actively override that auto-resolution for every caller that never
# meant to force one.
DEFAULT_SCHEDULER = None
DEFAULT_NEGATIVE_PROMPT = "text, watermark"
# Forge's own dataclass default (modules/processing.py,
# StableDiffusionProcessingImg2Img.denoising_strength) — identical
# value to ComfyUIEngine's own DEFAULT_IMG2IMG_DENOISE, corroborating
# the semantic equivalence verified in MISSION_107.md section 3.3.
DEFAULT_IMG2IMG_DENOISING_STRENGTH = 0.75


class ForgeEngineError(Exception):
    """Raised on any Forge protocol/communication failure."""


class ForgeEngine:
    """
    Generic Forge/A1111 protocol client (Infrastructure layer). Imports
    nothing from the Domain layer and returns no Domain object — only
    plain str/dict data, per CLAUDE.md's "Infrastructure ignorant le
    Domain" rule, same convention as ComfyUIEngine.

    base_url defaults to a local instance (127.0.0.1:7860, Forge's own
    default port) because that mirrors ComfyUIEngine's own "verified
    local use case, not an assumption of locality" precedent — the
    same protocol applies to any reachable Forge instance with --api
    enabled, local or remote.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:7860", timeout: float = 120.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def list_checkpoints(self, timeout: Optional[float] = None) -> list:
        """
        GET /sdapi/v1/sd-models — asks the running Forge instance which
        checkpoints it actually has loaded/discoverable, never a list
        hardcoded in this codebase (same discovery discipline as
        ComfyUIEngine.list_checkpoints()). Returns each entry's "title"
        field — the identifier Forge's own checkpoint_aliases mapping
        (modules/processing.py) accepts for override_settings.
        sd_model_checkpoint, and the conventional identifier used
        throughout the A1111/Forge ecosystem for this exact purpose.
        """
        data = self._request_json("GET", "/sdapi/v1/sd-models", timeout=timeout)

        if not isinstance(data, list):
            raise ForgeEngineError(f"Forge's checkpoint list is not a list: {data!r}")

        try:
            return [item["title"] for item in data]
        except (KeyError, TypeError) as error:
            raise ForgeEngineError(
                f"Forge's checkpoint list has an unexpected shape: {data!r}"
            ) from error

    def list_loras(self, timeout: Optional[float] = None) -> list:
        """
        GET /sdapi/v1/loras — served by Forge's own built-in
        sd_forge_lora extension (extensions-builtin/sd_forge_lora/
        scripts/lora_script.py::get_loras()). Returns each entry's
        "name" field — the exact identifier the <lora:name:strength>
        prompt syntax expects (confirmed by that same extension's own
        re_lora = re.compile("<lora:([^:]+):") pattern).
        """
        data = self._request_json("GET", "/sdapi/v1/loras", timeout=timeout)

        if not isinstance(data, list):
            raise ForgeEngineError(f"Forge's LoRA list is not a list: {data!r}")

        try:
            return [item["name"] for item in data]
        except (KeyError, TypeError) as error:
            raise ForgeEngineError(
                f"Forge's LoRA list has an unexpected shape: {data!r}"
            ) from error

    def check_connection(self, timeout: Optional[float] = None) -> bool:
        """
        Mission 112: same rationale as ComfyUIEngine.check_connection() —
        a thin wrapper around list_checkpoints(), reusing its existing
        GET /sdapi/v1/sd-models call and structural response validation
        rather than a new HTTP path or a bare port/socket test. Returns
        True on any structurally valid response, including an empty
        checkpoint list. On failure, ForgeEngineError propagates
        unchanged, never swallowed into a bare False.
        """
        self.list_checkpoints(timeout=timeout)
        return True

    def list_samplers(self, timeout: Optional[float] = None) -> list:
        """
        GET /sdapi/v1/samplers — the sampler_name values this Forge
        instance's own API actually accepts (modules/api/api.py::
        get_samplers()), never a list hardcoded in this codebase.
        """
        data = self._request_json("GET", "/sdapi/v1/samplers", timeout=timeout)

        if not isinstance(data, list):
            raise ForgeEngineError(f"Forge's sampler list is not a list: {data!r}")

        try:
            return [item["name"] for item in data]
        except (KeyError, TypeError) as error:
            raise ForgeEngineError(
                f"Forge's sampler list has an unexpected shape: {data!r}"
            ) from error

    def list_schedulers(self, timeout: Optional[float] = None) -> list:
        """
        GET /sdapi/v1/schedulers — same discovery convention as
        list_samplers() above (modules/api/api.py::get_schedulers()).
        """
        data = self._request_json("GET", "/sdapi/v1/schedulers", timeout=timeout)

        if not isinstance(data, list):
            raise ForgeEngineError(f"Forge's scheduler list is not a list: {data!r}")

        try:
            return [item["name"] for item in data]
        except (KeyError, TypeError) as error:
            raise ForgeEngineError(
                f"Forge's scheduler list has an unexpected shape: {data!r}"
            ) from error

    def upload_image(self, file_path: str) -> dict:
        """
        No network call — Forge's own img2img API takes the reference
        inline (init_images, base64-encoded in the same request as
        everything else), unlike ComfyUI's separate /upload/image
        endpoint. This method exists only so GenerationManager can
        call upload_image() then generate_image(reference_image=...)
        identically regardless of which engine it targets (see this
        module's own docstring) — it validates the local file and
        wraps its path for generate_image() to encode later.

        Raises FileNotFoundError/OSError uncaught if file_path does not
        exist or cannot be read — a local filesystem precondition, not
        a Forge protocol error, same convention already used by
        ComfyUIEngine.upload_image().
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(file_path)
        return {"path": str(path)}

    def generate_image(
        self,
        prompt_text: str,
        output_directory: str,
        checkpoint_name: Optional[str] = None,
        reference_image: Optional[dict] = None,
        denoise: float = DEFAULT_IMG2IMG_DENOISING_STRENGTH,
        lora_name: str = "",
        lora_strength: float = 1.0,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        steps: int = DEFAULT_STEPS,
        cfg: float = DEFAULT_CFG,
        sampler_name: str = DEFAULT_SAMPLER_NAME,
        scheduler: Optional[str] = DEFAULT_SCHEDULER,
        seed: Optional[int] = None,
        negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
    ) -> str:
        """
        Chooses /sdapi/v1/txt2img or /sdapi/v1/img2img based on
        reference_image, exactly like ComfyUIEngine.generate_image()
        chooses which graph to submit — a caller that never passes
        reference_image gets the txt2img path unchanged.

        checkpoint_name (None by default, meaning "use whatever Forge
        is currently configured with") is applied via
        override_settings/override_settings_restore_afterwards — see
        this module's own docstring for the exact restoration
        guarantee, verified against Forge's real installed source.

        lora_name="" (ComfyUIEngine's own "no LoRA" convention,
        mirrored here) never appends any <lora:...> syntax to the
        prompt.

        reference_image must be the exact dict upload_image() returned
        — this method never inspects it beyond reading "path".

        denoise (Mission 107, per the architect's explicit correction to
        this mission's first draft): named identically to
        ComfyUIEngine.generate_image()'s own "denoise" parameter — never
        "denoising_strength" — precisely so GenerationManager can
        forward reference_strength under one common keyword regardless
        of which concrete engine it targets, with zero per-engine
        branching on its own side. This method is the one place that
        translates it into Forge's own native wire field name
        ("denoising_strength" in the JSON payload below) — the Python
        parameter name and the wire protocol's field name are
        deliberately decoupled.
        """
        prompt = self._apply_lora_syntax(prompt_text, lora_name, lora_strength)

        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "seed": -1 if seed is None else seed,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": cfg,
            "sampler_name": sampler_name,
        }

        if scheduler:
            payload["scheduler"] = scheduler

        if checkpoint_name:
            payload["override_settings"] = {"sd_model_checkpoint": checkpoint_name}
            payload["override_settings_restore_afterwards"] = True

        if reference_image is not None:
            endpoint = "/sdapi/v1/img2img"
            payload["init_images"] = [self._encode_reference(reference_image)]
            payload["denoising_strength"] = denoise
        else:
            endpoint = "/sdapi/v1/txt2img"

        data = self._request_json("POST", endpoint, payload=payload)

        if not isinstance(data, dict):
            raise ForgeEngineError(f"Forge's generation response is not an object: {data!r}")

        images = data.get("images")
        if not images:
            raise ForgeEngineError(f"Forge response contains no image output: {data!r}")

        return self._save_image(images[0], output_directory)

    def _apply_lora_syntax(self, prompt_text: str, lora_name: str, lora_strength: float) -> str:
        if not lora_name:
            return prompt_text
        return f"{prompt_text} <lora:{self._forge_lora_tag_name(lora_name)}:{lora_strength}>"

    @staticmethod
    def _forge_lora_tag_name(lora_name: str) -> str:
        """
        Mission 108 real-smoke correction: LoRALibraryManager's own
        alias_name (e.g. "AIStudioToolkit\\my_lora__<uuid>.safetensors")
        is the relative-path-with-extension convention ComfyUI's native
        LoraLoader node expects — verified working in production since
        Mission 095/102. Forge's own <lora:name:weight> prompt syntax
        does NOT share that convention: verified directly against the
        installed Forge's own extra_networks_lora.py (the tag's name is
        used byte-for-byte, never normalized) and networks.py's
        process_network_files() (every discovered LoRA is keyed
        exclusively by `os.path.splitext(os.path.basename(filename))[0]`
        — the bare filename, no subfolder, no extension — regardless of
        how deep it actually sits under --lora-dir, since Forge scans
        recursively). A first real smoke against a live Forge server
        confirmed this mismatch empirically: the API call still
        succeeded (Forge silently skips an unresolved network rather
        than raising), but the returned image's own embedded metadata
        never carried a "Lora hashes: ..." line, proving the LoRA was
        never actually applied.

        This is therefore the one, minimal translation Forge needs,
        confined entirely to this engine (never GenerationManager/
        InferencePage/LoRALibraryManager, which keep passing the same
        alias_name unchanged for ComfyUI's own, already-correct use).
        Explicit normalization rather than relying on ntpath.basename()
        alone to also transparently accept "/" as a separator (an
        alias_name never actually contains one today, but a defensive,
        explicit "/" -> "\\" pass first keeps this correct regardless):
        """
        normalized = lora_name.replace("/", "\\")
        return ntpath.splitext(ntpath.basename(normalized))[0]

    def _encode_reference(self, reference_image: dict) -> str:
        path = Path(reference_image["path"])
        try:
            image_bytes = path.read_bytes()
        except OSError as error:
            raise ForgeEngineError(f"Could not read reference image {path}: {error}") from error
        return base64.b64encode(image_bytes).decode("ascii")

    def _save_image(self, encoded: str, output_directory: str) -> str:
        # Defensive: this installation's own encode_pil_to_base64()
        # (modules/api/api.py) never emits a data URI prefix, only raw
        # base64 — but decode_base64_to_image() in that same file
        # explicitly tolerates one on the way in, so a future Forge
        # version or a differently configured instance returning one
        # on the way out is not treated as a malformed response here.
        if encoded.startswith("data:image/"):
            encoded = encoded.split(",", 1)[1]

        try:
            image_bytes = base64.b64decode(encoded)
        except (ValueError, TypeError) as error:
            raise ForgeEngineError(f"Forge returned an invalid base64 image: {error}") from error

        extension = self._guess_image_extension(image_bytes)
        destination = Path(output_directory) / f"{uuid.uuid4().hex}.{extension}"

        with open(destination, "wb") as file:
            file.write(image_bytes)

        return str(destination)

    @staticmethod
    def _guess_image_extension(image_bytes: bytes) -> str:
        if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        if image_bytes.startswith(b"\xff\xd8"):
            return "jpg"
        if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            return "webp"
        # opts.samples_format defaults to "png" in Forge itself
        # (modules/api/api.py::encode_pil_to_base64) — used only as a
        # last resort when the bytes match none of the signatures
        # actually checked above.
        return "png"

    def _request_json(
        self, method: str, path: str, payload: Optional[dict] = None, timeout: Optional[float] = None
    ) -> dict:
        effective_timeout = timeout if timeout is not None else self._timeout

        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            f"{self._base_url}{path}", data=body, headers=headers, method=method
        )

        try:
            with urllib.request.urlopen(request, timeout=effective_timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            raw = error.read()
            raise ForgeEngineError(
                f"Forge returned HTTP {error.code} for {path}: {self._extract_error_detail(raw)}"
            ) from error
        except (urllib.error.URLError, OSError) as error:
            raise ForgeEngineError(f"Forge server unreachable at {self._base_url}: {error}") from error

        try:
            return json.loads(raw)
        except json.JSONDecodeError as error:
            raise ForgeEngineError(f"Forge returned an invalid response for {path}: {raw!r}") from error

    @staticmethod
    def _extract_error_detail(raw: bytes):
        # FastAPI's own standard error body shape is {"detail": ...}
        # (Forge's API is FastAPI-based, modules/api/api.py) — surfaced
        # verbatim when present so a caller sees Forge's actual reason,
        # never just a bare HTTP status code.
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if isinstance(data, dict) and "detail" in data:
            return data["detail"]
        return data
