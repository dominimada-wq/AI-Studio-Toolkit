"""
PromptAssistantWorker runs PromptAssistantManager.assist() off the Qt
main thread — exact structural mirror of GenerationWorker (Mission
013/030): the only piece of this vertical that knows about Qt
threading, PromptAssistantManager itself stays Qt-free.

Both success and failure are translated into signals; no exception ever
crosses the thread boundary uncaught — PromptAssistantManager already
normalizes AIBackendError into PromptAssistantError, and the broad
except below is a last-resort safety net for anything else.
"""

from typing import Optional

from PySide6.QtCore import QObject, Signal

from src.managers.prompt_assistant_manager import (
    CharacterContext,
    PromptAssistantError,
    PromptAssistantManager,
)


class PromptAssistantWorker(QObject):

    finished = Signal(str)  # proposed prompt text
    failed = Signal(str)  # error message

    def __init__(
        self,
        prompt_assistant_manager: PromptAssistantManager,
        request_text: str,
        existing_prompt: str = "",
        character_context: Optional[CharacterContext] = None,
    ):
        super().__init__()
        self._prompt_assistant_manager = prompt_assistant_manager
        self._request_text = request_text
        self._existing_prompt = existing_prompt
        # Mission 034: a snapshot already resolved by the caller before
        # this worker was even constructed — this worker never resolves
        # Character/CharacterManager itself, never receives either, and
        # never re-resolves identity while the request is in flight.
        self._character_context = character_context

    def run(self) -> None:
        try:
            result = self._prompt_assistant_manager.assist(
                self._request_text,
                existing_prompt=self._existing_prompt,
                character_context=self._character_context,
            )
        except PromptAssistantError as error:
            self.failed.emit(str(error))
            return
        except Exception as error:  # last-resort safety net — must never cross the thread boundary
            self.failed.emit(str(error))
            return

        self.finished.emit(result)
