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

# Mission 039: application-specific markers, chosen to make an accidental
# collision with ordinary prompt content (comma-separated descriptive
# phrases, never this literal token shape) effectively impossible. The
# instruction block below is built from these same constants so the text
# asked of the model and the text _extract_final_prompt() looks for can
# never drift apart.
PROMPT_DELIMITER_START = "@@AISTUDIO_PROMPT_START@@"
PROMPT_DELIMITER_END = "@@AISTUDIO_PROMPT_END@@"

OUTPUT_CONTRACT_BLOCK = (
    "[INSTRUCTIONS DE SORTIE — à respecter strictement]\n"
    "Réponds uniquement avec le prompt final demandé : aucune explication, aucune\n"
    "analyse, aucun préambule, aucun commentaire avant ou après.\n"
    "N'utilise aucun bloc Markdown pour entourer ta réponse.\n"
    "Encadre exclusivement le prompt final entre ces deux marqueurs exacts,\n"
    "chacun sur sa propre ligne, sans rien ajouter d'autre autour :\n"
    f"{PROMPT_DELIMITER_START}\n"
    "(le prompt final ici)\n"
    f"{PROMPT_DELIMITER_END}"
)


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

        character_context=None (Mission 034 default) -> no identity
        block/[DEMANDE ACTUELLE] label is added to the backend text
        (Mission 034 guarantee, still exact) — Mission 039's output-
        contract block is appended regardless. A CharacterContext is
        only ever prepended when the caller explicitly passes one
        (PromptAssistantDialog's checkbox, never on by default) — this
        method never resolves a Character itself, it only ever receives
        an already-built snapshot.

        Raises PromptAssistantError if a request is already in
        progress, or if AIBackend.generate_text() raises
        AIBackendError.
        """

        if self._busy:
            raise PromptAssistantError("A prompt assist request is already in progress")

        combined_text = self._build_combined_text(request_text, existing_prompt, character_context)

        self._busy = True
        try:
            raw_response = self._ai_backend.generate_text(combined_text, model=self._model_name)
        except AIBackendError as error:
            raise PromptAssistantError(str(error)) from error
        finally:
            self._busy = False

        return self._extract_final_prompt(raw_response)

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
            # Mission 034 non-regression guarantee (no [DEMANDE ACTUELLE]
            # label, no identity block) still holds here — the only
            # addition below is Mission 039's output-contract block,
            # appended identically regardless of this branch.
            base_text = request_block
        else:
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

            base_text = f"{identity_block}\n\n[DEMANDE ACTUELLE]\n{request_block}"

        # Mission 039: appended exactly once here, so Créer/Améliorer and
        # with/without CharacterContext all share the same single
        # instruction — never duplicated per branch.
        return f"{base_text}\n\n{OUTPUT_CONTRACT_BLOCK}"

    @staticmethod
    def _extract_final_prompt(response: str) -> str:
        """
        Mission 039: deterministic extraction only — never a guess at
        which part of the response is the prompt. Extraction applies
        only when exactly one valid, non-empty delimiter pair is found;
        every other case (absent, one-sided, reversed, multiple, or an
        empty/whitespace-only interior) falls back to the full raw
        response, peripherally stripped.
        """

        if (
            response.count(PROMPT_DELIMITER_START) == 1
            and response.count(PROMPT_DELIMITER_END) == 1
        ):
            start_index = response.index(PROMPT_DELIMITER_START) + len(PROMPT_DELIMITER_START)
            end_index = response.index(PROMPT_DELIMITER_END)
            if start_index <= end_index:
                extracted = response[start_index:end_index].strip()
                if extracted:
                    return extracted

        return response.strip()
