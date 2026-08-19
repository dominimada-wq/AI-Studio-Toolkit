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

from typing import NamedTuple, Optional

from src.domain.character import Character
from src.engines.ai_backend import AIBackend, AIBackendError


class PromptAssistantError(Exception):
    """
    Normalizes AIBackendError and "a request is already in progress"
    into a single Manager-level exception type — same pattern
    GenerationError already uses to wrap ComfyUIEngineError/OSError.
    """


class CharacterContext(NamedTuple):
    """
    Mission 034: the minimal, explicit subset of Character's identity
    fields the Prompt Assistant is allowed to know about — deliberately
    narrower than Character itself, colocated here (same spirit as
    AIModelInfo/AIBackendError living next to AIBackend in
    ai_backend.py) so this is the one and only place PromptAssistantManager
    ever touches src.domain.character. bio/personality's cousin
    `interests` are excluded on purpose (see from_character() below) —
    no field is added here in anticipation of a future need.
    """

    character_lock: str = ""
    trigger_token: str = ""
    description: str = ""
    personality: str = ""

    @classmethod
    def from_character(cls, character: Optional[Character]) -> Optional["CharacterContext"]:
        """
        The single Character -> CharacterContext conversion point in
        the whole codebase (Mission 034 architecture decision, see
        docs/missions/MISSION_034.md section 4.1). Deliberately never
        reads character.bio/character.interests. Returns None both
        when character is None and when all four retained fields are
        blank after stripping — a caller only ever needs to check for
        None, never inspect individual fields to decide whether the
        result is usable.
        """

        if character is None:
            return None

        context = cls(
            character_lock=character.character_lock.strip(),
            trigger_token=character.trigger_token.strip(),
            description=character.description.strip(),
            personality=character.personality.strip(),
        )

        if not any(context):
            return None

        return context


class PromptAssistantManager:

    def __init__(self, ai_backend: AIBackend, model_name: str):
        self._ai_backend = ai_backend
        self._model_name = model_name
        self._busy = False

    @property
    def busy(self) -> bool:
        return self._busy

    def assist(
        self,
        request_text: str,
        existing_prompt: str = "",
        character_context: Optional[CharacterContext] = None,
    ) -> str:
        """
        existing_prompt="" -> "Create" intent: request_text alone is
        turned into a prompt-creation instruction. existing_prompt
        non-empty -> "Improve" intent: existing_prompt is sent as an
        explicit base, request_text as the improvement instruction —
        the caller (PromptAssistantDialog) decides which intent
        applies by choosing whether to pass existing_prompt; this
        method never guesses an intent from content.

        character_context=None (Mission 034 default) -> the backend
        text is built exactly as before Mission 034, unchanged byte
        for byte. A CharacterContext is only ever prepended when the
        caller explicitly passes one (PromptAssistantDialog's checkbox,
        never on by default) — this method never resolves a Character
        itself, it only ever receives an already-built snapshot.

        Raises PromptAssistantError if a request is already in
        progress, or if AIBackend.generate_text() raises
        AIBackendError.
        """

        if self._busy:
            raise PromptAssistantError("A prompt assist request is already in progress")

        combined_text = self._build_combined_text(request_text, existing_prompt, character_context)

        self._busy = True
        try:
            return self._ai_backend.generate_text(combined_text, model=self._model_name)
        except AIBackendError as error:
            raise PromptAssistantError(str(error)) from error
        finally:
            self._busy = False

    @staticmethod
    def _build_combined_text(
        request_text: str,
        existing_prompt: str,
        character_context: Optional[CharacterContext] = None,
    ) -> str:
        if existing_prompt.strip():
            request_block = (
                "Prompt existant à améliorer :\n"
                f"{existing_prompt}\n\n"
                "Instruction d'amélioration :\n"
                f"{request_text}"
            )
        else:
            request_block = f"Crée un prompt d'image à partir de cette demande :\n{request_text}"

        if character_context is None:
            # Mission 034 non-regression guarantee: no [DEMANDE ACTUELLE]
            # label, no identity block — byte-for-byte the same text
            # this method already produced before Mission 034 existed.
            return request_block

        identity_lines = ["[IDENTITÉ CANONIQUE DU PERSONNAGE — priorité absolue, ne jamais contredire]"]
        if character_context.character_lock:
            identity_lines.append(f"Character Lock : {character_context.character_lock}")
        if character_context.trigger_token:
            identity_lines.append(
                "Trigger token à inclure littéralement dans le prompt final : "
                f"{character_context.trigger_token}"
            )
        if character_context.description:
            identity_lines.append(f"Description : {character_context.description}")
        if character_context.personality:
            identity_lines.append(f"Personnalité : {character_context.personality}")

        identity_block = "\n".join(identity_lines)

        return f"{identity_block}\n\n[DEMANDE ACTUELLE]\n{request_block}"
