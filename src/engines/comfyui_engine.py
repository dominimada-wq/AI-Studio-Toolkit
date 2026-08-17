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
import mimetypes
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Optional

# Mission 023: graph construction (node IDs, class_type, connections)
# lives in src/engines/workflows/ — this module only re-exports the
# names that were historically importable from here
# (DEMO_CHECKPOINT_NAME, and build_demo_workflow renamed
# build_txt2img_workflow), so existing import sites keep working, and
# adds build_img2img_workflow for generate_image()'s new reference
# path below. Neither this import nor generate_image() give
# ComfyUIEngine's transport primitives (submit/wait_for_result/
# download_output/upload_image) any knowledge of graph content.
from src.engines.workflows.comfyui_workflows import (
    DEFAULT_IMG2IMG_DENOISE,
    DEMO_CHECKPOINT_NAME,
    build_img2img_workflow,
    build_txt2img_workflow,
)


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

    def upload_image(self, file_path: str, subfolder: str = "", overwrite: bool = False) -> dict:
        """
        POST /upload/image — uploads a local file to the ComfyUI instance
        so it becomes referenceable by a future workflow's LoadImage node
        (Mission 021: transport only, no workflow node is built here).

        Pure transport primitive: this method knows nothing about why a
        file is being uploaded — a portrait, a character reference sheet,
        a clothing image, an environment, a pose, or any other future
        role — that decision belongs to a future orchestration layer, not
        to ComfyUIEngine. No upload-related state is kept on self, so
        calling this method once, twice, or N times for N independent
        local images is always safe — nothing here assumes a single
        reference image, and nothing needs to change here to support
        that future need.

        type is deliberately not exposed as a parameter: it is always
        sent as "input", the only directory a LoadImage node reads from
        — the one value with a real, already-motivated consumer today.
        Extending this additively (an optional type_ parameter) remains
        possible later if "output"/"temp" become genuinely needed, same
        pattern as checkpoint_name being added to generate_image() in
        Mission 013.

        Raises FileNotFoundError/OSError uncaught if file_path does not
        exist or cannot be read — a local filesystem precondition, not a
        ComfyUI protocol error, same convention already used by
        download_output() for output_directory. Raises
        ComfyUIEngineError for any network/HTTP/JSON failure (via
        _request_json(), unchanged), or if a syntactically valid JSON
        response does not carry the three fields (non-empty str "name",
        str "subfolder", non-empty str "type") ComfyUI's own upload
        contract always returns together on success — verified against
        server.py's image_upload(): resp = {"name": ..., "subfolder":
        ..., "type": ...}.
        """
        image_bytes = Path(file_path).read_bytes()
        filename = Path(file_path).name
        content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

        boundary = uuid.uuid4().hex

        body = bytearray()
        body += f"--{boundary}\r\n".encode("utf-8")
        body += (
            f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
        body += image_bytes
        body += b"\r\n"

        for field_name, field_value in (("type", "input"), ("subfolder", subfolder)):
            body += f"--{boundary}\r\n".encode("utf-8")
            body += f'Content-Disposition: form-data; name="{field_name}"\r\n\r\n'.encode("utf-8")
            body += f"{field_value}\r\n".encode("utf-8")

        if overwrite:
            body += f"--{boundary}\r\n".encode("utf-8")
            body += 'Content-Disposition: form-data; name="overwrite"\r\n\r\n'.encode("utf-8")
            body += "true\r\n".encode("utf-8")

        body += f"--{boundary}--\r\n".encode("utf-8")

        request = urllib.request.Request(
            f"{self._base_url}/upload/image",
            data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )

        data = self._request_json(request)

        name = data.get("name")
        response_subfolder = data.get("subfolder")
        response_type = data.get("type")

        valid = (
            isinstance(name, str) and name
            and isinstance(response_subfolder, str)
            and isinstance(response_type, str) and response_type
        )
        if not valid:
            raise ComfyUIEngineError(f"ComfyUI upload response is structurally invalid: {data}")

        return {"name": name, "subfolder": response_subfolder, "type": response_type}

    def generate_image(
        self,
        prompt_text: str,
        output_directory: str,
        checkpoint_name: str = DEMO_CHECKPOINT_NAME,
        reference_image: Optional[dict] = None,
        denoise: float = DEFAULT_IMG2IMG_DENOISE,
    ) -> str:
        """
        Convenience method — chooses which graph to submit based on
        reference_image, waits for it, downloads the first image found
        in the result. Built entirely on
        submit()/wait_for_result()/download_output() via
        _submit_and_download(): each graph's shape (checkpoint,
        sampler, nodes...) belongs to build_txt2img_workflow()/
        build_img2img_workflow(), never to ComfyUIEngine's generic
        contract.

        checkpoint_name defaults to build_txt2img_workflow()'s own
        default but is exposed here (Mission 013) because a real
        integration demonstrated the need: a given ComfyUI installation
        is not guaranteed to have a checkpoint under that exact default
        name (confirmed empirically — see Mission 012's post-release
        smoke test). This stays an additive, backward-compatible
        parameter; it does not turn checkpoint_name into a property of
        ComfyUIEngine's generic contract (submit/wait_for_result/
        download_output remain untouched and still know nothing about
        checkpoints).

        reference_image (Mission 023) is None by default — omitting it
        (or passing None explicitly) reproduces the exact txt2img path
        that existed before this mission, byte-for-byte. When provided,
        it must be the exact dict upload_image() returned for the
        reference to use — this method passes it straight into
        build_img2img_workflow() without inspecting it; only that
        function's _load_image_input() knows how to turn it into a
        LoadImage node input.

        denoise (Mission 024) is only meaningful when reference_image is
        provided — it is simply unused on the txt2img path, ignored
        rather than validated. Defaults to build_img2img_workflow()'s
        own DEFAULT_IMG2IMG_DENOISE, so a caller that never overrides it
        reproduces Mission 023's behavior byte-for-byte. This is the one
        point where a caller-facing "reference strength" concept is
        named denoise — GenerationManager forwards it under this exact
        keyword without knowing anything about ComfyUI's graph format.
        """
        if reference_image is None:
            workflow = build_txt2img_workflow(prompt_text, checkpoint_name=checkpoint_name)
        else:
            workflow = build_img2img_workflow(
                prompt_text, reference_image, checkpoint_name=checkpoint_name, denoise=denoise
            )

        return self._submit_and_download(workflow, output_directory)

    def _submit_and_download(self, workflow: dict, output_directory: str) -> str:
        """
        Shared submit -> wait -> download sequence, extracted in
        Mission 023 so both the txt2img and img2img paths of
        generate_image() run through the exact same transport/error
        handling without duplicating it. Knows nothing about a
        workflow's content (node IDs, class_type) beyond treating it as
        the opaque dict submit() already expects — the choice of which
        graph to build stays entirely in generate_image().
        """
        client_id = str(uuid.uuid4())

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
