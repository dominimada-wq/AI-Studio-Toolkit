"""
Minimal HTTP client for a local or remote Ollama instance's own API
(GET /api/tags, POST /api/generate — see
github.com/ollama/ollama/blob/main/docs/api.md), verified against the
official documentation during Mission 030's specification. Structurally
satisfies src.engines.ai_backend.AIBackend without inheriting from it —
same zero-ceremony spirit as ComfyUIEngine.

base_url defaults to Ollama's own documented default local port
(11434) because that is Mission 030's verified use case, not because
the class assumes locality — the same protocol applies to any
reachable Ollama instance, local or remote (never requires
ollama_path/a local installation).

Deliberately text-only, non-streaming (POST /api/generate with
"stream": false), and does not use POST /api/chat — no message/
conversation history exists in this codebase yet to justify it. Model
capability (text vs vision) is not detected: Ollama's /api/tags does
not reliably expose it (only a separate GET /api/show, per model,
does) — see docs/missions/MISSION_030.md section 3.4 for the full
rationale. This module is deliberately the only place that knows any
of the above; src.engines.ai_backend stays entirely Ollama-agnostic.
"""

import json
import urllib.error
import urllib.request

from src.engines.ai_backend import AIBackendError, AIModelInfo


class OllamaEngine:
    """
    Generic Ollama protocol client (Infrastructure layer), structurally
    satisfying AIBackend. Imports nothing from the Domain layer and
    returns no Domain object — only plain str/AIModelInfo data, per
    CLAUDE.md's "Infrastructure ignorant le Domain" rule.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout: float = 30.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def list_models(self) -> list[AIModelInfo]:
        """
        GET /api/tags — the models currently present on this Ollama
        instance (never a scan of any local folder by AI Studio Toolkit
        itself, same principle already retained for ComfyUIEngine.
        list_checkpoints() in Mission 025: ask the running server,
        never guess its filesystem layout).

        Raises AIBackendError if the response carries no usable
        "models" list. Each individual entry is filtered defensively
        (must be a dict with a non-empty str "name") rather than
        raising for one malformed entry — same discipline already used
        by list_checkpoints()'s non-string-entry filtering.
        """
        try:
            request = urllib.request.Request(f"{self._base_url}/api/tags", method="GET")
            data = self._request_json(request)
        except ValueError as error:
            # urllib.request.Request() itself raises a bare ValueError
            # (not URLError/OSError) for a structurally invalid URL
            # (e.g. an empty/malformed base_url) — before
            # _request_json()/urlopen() is ever reached. Same per-caller
            # placement as ComfyUIEngine.list_checkpoints()/list_loras().
            raise AIBackendError(f"Ollama base URL is invalid: {self._base_url!r}") from error

        models = data.get("models")
        if not isinstance(models, list):
            raise AIBackendError(f"Ollama's /api/tags response has no models list: {data}")

        return [
            AIModelInfo(name=entry["name"])
            for entry in models
            if isinstance(entry, dict) and isinstance(entry.get("name"), str) and entry["name"]
        ]

    def generate_text(self, prompt: str, model: str) -> str:
        """
        POST /api/generate with {"model": model, "prompt": prompt,
        "stream": false} — a single non-streaming call, returning one
        complete JSON response rather than a fragment stream (Mission
        030's explicit choice to keep this first fondation simply
        testable). Returns the "response" field verbatim.

        Raises AIBackendError if the response carries no usable
        "response" string — if Ollama's response instead carries a
        str "error" field (e.g. unknown model), that message is
        included in the raised exception.
        """
        body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")

        try:
            request = urllib.request.Request(
                f"{self._base_url}/api/generate",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            data = self._request_json(request)
        except ValueError as error:
            # Same asymmetry as list_models() above: Request() itself
            # raises a bare ValueError for a structurally invalid URL,
            # before _request_json()/urlopen() is ever reached.
            raise AIBackendError(f"Ollama base URL is invalid: {self._base_url!r}") from error

        response_text = data.get("response")
        if isinstance(response_text, str):
            return response_text

        error_message = data.get("error")
        if isinstance(error_message, str) and error_message:
            raise AIBackendError(f"Ollama returned an error: {error_message}")

        raise AIBackendError(f"Ollama's /api/generate response has no text: {data}")

    def _request_json(self, request: urllib.request.Request) -> dict:
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            raw = error.read()
        except (urllib.error.URLError, OSError) as error:
            raise AIBackendError(f"Ollama server unreachable at {self._base_url}: {error}") from error

        try:
            return json.loads(raw)
        except json.JSONDecodeError as error:
            raise AIBackendError(f"Ollama returned an invalid response: {raw!r}") from error
