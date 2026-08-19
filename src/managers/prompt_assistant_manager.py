"""
PromptAssistantManager coordinates a single "assist" request against an
AIBackend (Mission 030's structural contract) — mirrors GenerationManager's
shape exactly (Mission 013): Qt-free, one blocking call, a single
transient `busy` flag as the only state, no Domain collection, no
active_id, no history. Never imports OllamaEngine or any concrete
provider — only src.engines.ai_backend.AIBackend — so a future provider
swap, or a future PromptsPage consumer (Mission 031's Option C long-term
direction: a single shared Prompt Assistant service, never duplicated
AI logic between pages), never touches this file.

Text construction (how a user's request and an optional existing prompt
become the single string sent to AIBackend.generate_text()) lives here,
deliberately deterministic and testable — never left to the UI or to
the provider itself, the same discipline GenerationManager already
applies to reference_strength -> denoise.
"""

from src.engines.ai_backend import AIBackend, AIBackendError


class PromptAssistantError(Exception):
    """
    Normalizes AIBackendError and "a request is already in progress"
    into a single Manager-level exception type — same pattern
    GenerationError already uses to wrap ComfyUIEngineError/OSError.
    """


class PromptAssistantManager:

    def __init__(self, ai_backend: AIBackend, model_name: str):
        self._ai_backend = ai_backend
        self._model_name = model_name
        self._busy = False

    @property
    def busy(self) -> bool:
        return self._busy

    def assist(self, request_text: str, existing_prompt: str = "") -> str:
        """
        existing_prompt="" -> "Create" intent: request_text alone is
        turned into a prompt-creation instruction. existing_prompt
        non-empty -> "Improve" intent: existing_prompt is sent as an
        explicit base, request_text as the improvement instruction —
        the caller (PromptAssistantDialog) decides which intent
        applies by choosing whether to pass existing_prompt; this
        method never guesses an intent from content.

        Raises PromptAssistantError if a request is already in
        progress, or if AIBackend.generate_text() raises
        AIBackendError.
        """

        if self._busy:
            raise PromptAssistantError("A prompt assist request is already in progress")

        combined_text = self._build_combined_text(request_text, existing_prompt)

        self._busy = True
        try:
            return self._ai_backend.generate_text(combined_text, model=self._model_name)
        except AIBackendError as error:
            raise PromptAssistantError(str(error)) from error
        finally:
            self._busy = False

    @staticmethod
    def _build_combined_text(request_text: str, existing_prompt: str) -> str:
        if existing_prompt.strip():
            return (
                "Prompt existant à améliorer :\n"
                f"{existing_prompt}\n\n"
                "Instruction d'amélioration :\n"
                f"{request_text}"
            )
        return f"Crée un prompt d'image à partir de cette demande :\n{request_text}"
