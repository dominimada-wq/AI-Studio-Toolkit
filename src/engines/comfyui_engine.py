"""
Minimal HTTP client for a ComfyUI instance's own API (POST /prompt,
GET /history/{id}, GET /view — see
docs.comfy.org/development/comfyui-server/comms_routes). ComfyUIEngine
only speaks this generic protocol: submit an opaque API-format
workflow dict, wait for its result, download a named output. It never
inspects or assumes what a workflow's nodes do internally — a local
checkpoint, a LoRA, or a cloud-backed node such as a Gemini/GPT Image
wrapper — because ComfyUI's own execution API makes no such
distinction either (confirmed in Mission 012's architectural audit and
its local/cloud supplement). This is what keeps the boundary
"AI Studio Toolkit -> ComfyUI" rather than
"AI Studio Toolkit -> a particular model/provider".

base_url defaults to a local instance (127.0.0.1:8188) because that is
Mission 012's verified use case, not because the class assumes
locality — the same protocol applies to any reachable ComfyUI
instance, local or remote.

No WebSocket: progress is observed by polling GET /history/{prompt_id}
until the result appears or a timeout elapses, avoiding a dependency
on a WebSocket client library for this first mission.
"""

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Optional

DEMO_CHECKPOINT_NAME = "v1-5-pruned-emaonly.safetensors"


def build_demo_workflow(prompt_text: str, checkpoint_name: str = DEMO_CHECKPOINT_NAME) -> dict:
    """
    Mission 012's fixed demonstration workflow (ComfyUI API format) —
    a minimal, local checkpoint-based txt2img graph, structurally
    similar to ComfyUI's own published basic_api_example.py. This is a
    detail of the Mission 012 demonstration, not a property of
    ComfyUIEngine: the engine's generic primitives (submit /
    wait_for_result / download_output) never reference
    checkpoint_name, SDXL, FLUX, or any other model/provider concept.
    checkpoint_name is exposed as a parameter specifically so a manual
    test against a real ComfyUI instance can point at whatever
    checkpoint is actually installed there, without touching
    ComfyUIEngine itself.
    """
    return {
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


class ComfyUIEngineError(Exception):
    """Raised on any ComfyUI protocol/communication failure."""


class ComfyUIEngine:
    """
    Generic ComfyUI protocol client (Infrastructure layer). Imports
    nothing from the Domain layer and returns no Domain object — only
    plain str/dict data, per CLAUDE.md's "Infrastructure ignorant le
    Domain" rule. The caller (a future Manager) decides what to do
    with the returned file path, including whether/how it becomes a
    Domain Image — that ownership decision is deliberately not made
    here (Mission 011's Workspace.images/Dataset.images pools require
    an active Workspace/Dataset context this class does not have).
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8188", timeout: float = 120.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def submit(self, workflow: dict, client_id: str) -> str:
        """
        POST /prompt with {"prompt": workflow, "client_id": client_id}
        — the exact body ComfyUI's API expects. Returns the prompt_id
        ComfyUI assigns to this submission. Raises ComfyUIEngineError
        if the server is unreachable, the response is not valid JSON,
        or ComfyUI rejects the workflow (no prompt_id in the
        response — e.g. a validation error).
        """
        body = json.dumps({"prompt": workflow, "client_id": client_id}).encode("utf-8")
        request = urllib.request.Request(
            f"{self._base_url}/prompt",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        data = self._request_json(request)

        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise ComfyUIEngineError(f"ComfyUI rejected the workflow: {data}")

        return prompt_id

    def wait_for_result(self, prompt_id: str, poll_interval: float = 1.0) -> dict:
        """
        Polls GET /history/{prompt_id} until ComfyUI reports at least
        one exploitable image output for this prompt, or self._timeout
        (set at construction) elapses. An entry with no "outputs", an
        empty "outputs", a node with no "images", an empty "images"
        list, or an image reference missing a usable "filename" are
        all treated as not-yet-exploitable and keep polling — not as
        success. Returns the "outputs" mapping (node_id -> node output
        dict) exactly as ComfyUI's history entry contains it, once
        exploitable. Raises ComfyUIEngineError on timeout or on any
        communication/protocol failure.
        """
        deadline = time.monotonic() + self._timeout

        while True:
            request = urllib.request.Request(f"{self._base_url}/history/{prompt_id}", method="GET")
            data = self._request_json(request)

            entry = data.get(prompt_id)
            if entry and entry.get("outputs") and self._first_image_reference(entry["outputs"]) is not None:
                return entry["outputs"]

            if time.monotonic() >= deadline:
                raise ComfyUIEngineError(f"Timed out waiting for ComfyUI result for prompt {prompt_id}")

            time.sleep(poll_interval)

    def download_output(self, filename: str, subfolder: str, type_: str, output_directory: str) -> str:
        """
        GET /view?filename=&subfolder=&type= — the exact query
        parameters ComfyUI's /view endpoint expects — and writes the
        returned bytes into output_directory. Returns the written
        file's path. Raises ComfyUIEngineError on any communication
        failure; a missing/unwritable output_directory raises the
        normal OSError, left uncaught (a local filesystem precondition,
        not a ComfyUI protocol error).
        """
        query = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": type_})
        request = urllib.request.Request(f"{self._base_url}/view?{query}", method="GET")

        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                image_bytes = response.read()
        except urllib.error.HTTPError as error:
            raise ComfyUIEngineError(f"ComfyUI returned HTTP {error.code} for /view ({filename})") from error
        except (urllib.error.URLError, OSError) as error:
            raise ComfyUIEngineError(f"ComfyUI server unreachable at {self._base_url}: {error}") from error

        destination = str(Path(output_directory) / filename)
        with open(destination, "wb") as file:
            file.write(image_bytes)

        return destination

    def generate_image(self, prompt_text: str, output_directory: str) -> str:
        """
        Convenience method demonstrating Mission 012's first real
        operation — submits build_demo_workflow(prompt_text), waits
        for it, downloads the first image found in the result. Built
        entirely on submit()/wait_for_result()/download_output(): the
        demo workflow's shape (checkpoint, sampler...) belongs to
        build_demo_workflow(), not to ComfyUIEngine's generic contract.
        """
        client_id = str(uuid.uuid4())
        workflow = build_demo_workflow(prompt_text)

        prompt_id = self.submit(workflow, client_id)
        outputs = self.wait_for_result(prompt_id)

        image_reference = self._first_image_reference(outputs)
        if image_reference is None:
            raise ComfyUIEngineError(f"ComfyUI result for prompt {prompt_id} contains no image output")

        return self.download_output(
            image_reference["filename"],
            image_reference.get("subfolder", ""),
            image_reference.get("type", "output"),
            output_directory,
        )

    @staticmethod
    def _first_image_reference(outputs: dict) -> Optional[dict]:
        """
        Returns the first structurally exploitable image reference
        found across all node outputs (any node, regardless of which
        one produced it — generic across workflows/providers), or None
        if outputs contains no node with a non-empty "images" list
        whose first entry carries a usable (non-empty str) "filename".
        A reference missing "filename" is not exploitable — download
        cannot proceed without it — so it is skipped rather than
        returned.
        """
        for node_output in outputs.values():
            images = node_output.get("images")
            if images and isinstance(images[0], dict) and images[0].get("filename"):
                return images[0]
        return None

    def _request_json(self, request: urllib.request.Request) -> dict:
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            raw = error.read()
        except (urllib.error.URLError, OSError) as error:
            raise ComfyUIEngineError(f"ComfyUI server unreachable at {self._base_url}: {error}") from error

        try:
            return json.loads(raw)
        except json.JSONDecodeError as error:
            raise ComfyUIEngineError(f"ComfyUI returned an invalid response: {raw!r}") from error
