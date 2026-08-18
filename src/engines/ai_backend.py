"""
Minimal structural contract for a future "AI Studio Toolkit -> AI
backend" boundary (Mission 030), so that a future feature never depends
on a specific provider (Ollama, or any later local/cloud backend)
directly — the same separation ComfyUIEngine already gives generation
via GenerationManager. Deliberately text-only and two methods: nothing
here anticipates chat/message history, vision, streaming, or any
provider-specific configuration (model discovery details, request
shape) — all of that lives in each concrete provider module
(src/engines/ollama_engine.py for the first one).
"""

from typing import NamedTuple, Protocol, runtime_checkable


class AIModelInfo(NamedTuple):
    """
    Deliberately minimal — only what every backend can report today.
    Additive by construction (NamedTuple, same pattern as ImportResult/
    CollisionInfo in workspace_manager.py): a future capability field
    (e.g. vision support) can be appended without breaking any existing
    attribute-based consumer. No such field exists yet because Ollama's
    model-listing endpoint does not reliably expose it (see
    docs/missions/MISSION_030.md section 3.4) — a documented limitation,
    not an oversight.
    """

    name: str


class AIBackendError(Exception):
    """
    Common error type every AIBackend implementation raises for any
    communication/protocol failure — a future consumer catches this
    single type regardless of which provider is configured, the same
    way GenerationManager normalizes ComfyUIEngineError/OSError into
    its own GenerationError today.
    """


@runtime_checkable
class AIBackend(Protocol):
    """
    Structural contract (typing.Protocol — no inheritance required,
    same zero-ceremony spirit as ComfyUIEngine having no base class). A
    provider satisfies this Protocol simply by implementing both
    methods with this exact signature; nothing needs to import or
    subclass AIBackend to work.
    """

    def list_models(self) -> list[AIModelInfo]:
        """Returns the models currently available on this backend."""

    def generate_text(self, prompt: str, model: str) -> str:
        """Sends a single text prompt, returns the backend's full text response."""
