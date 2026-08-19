"""
Coverage for src/managers/prompt_assistant_manager.py — Mission 031.
AIBackend is mocked throughout (MagicMock satisfying the Protocol): no
network access, no real Ollama instance.
"""

import unittest
from unittest.mock import MagicMock

from src.engines.ai_backend import AIBackendError
from src.managers.prompt_assistant_manager import PromptAssistantError, PromptAssistantManager


class PromptAssistantManagerCreateIntentTest(unittest.TestCase):

    def test_assist_without_existing_prompt_sends_a_create_instruction(self):
        backend = MagicMock()
        backend.generate_text.return_value = "a fox in a forest, cinematic lighting"

        manager = PromptAssistantManager(backend, model_name="llama3.2:3b")
        result = manager.assist("a fox in a forest")

        self.assertEqual(result, "a fox in a forest, cinematic lighting")
        backend.generate_text.assert_called_once_with(
            "Crée un prompt d'image à partir de cette demande :\na fox in a forest",
            model="llama3.2:3b",
        )

    def test_assist_with_blank_existing_prompt_is_treated_as_create(self):
        backend = MagicMock()
        backend.generate_text.return_value = "result"

        manager = PromptAssistantManager(backend, model_name="llama3.2:3b")
        manager.assist("a fox", existing_prompt="   ")

        backend.generate_text.assert_called_once_with(
            "Crée un prompt d'image à partir de cette demande :\na fox",
            model="llama3.2:3b",
        )


class PromptAssistantManagerImproveIntentTest(unittest.TestCase):

    def test_assist_with_existing_prompt_sends_an_improve_instruction(self):
        backend = MagicMock()
        backend.generate_text.return_value = "a fox in a forest, golden hour, 85mm"

        manager = PromptAssistantManager(backend, model_name="llama3.2:3b")
        result = manager.assist("make it more cinematic", existing_prompt="a fox in a forest")

        self.assertEqual(result, "a fox in a forest, golden hour, 85mm")
        backend.generate_text.assert_called_once_with(
            "Prompt existant à améliorer :\n"
            "a fox in a forest\n\n"
            "Instruction d'amélioration :\n"
            "make it more cinematic",
            model="llama3.2:3b",
        )


class PromptAssistantManagerModelNameTest(unittest.TestCase):

    def test_model_name_is_never_hardcoded(self):
        backend = MagicMock()
        backend.generate_text.return_value = "result"

        manager = PromptAssistantManager(backend, model_name="mistral:latest")
        manager.assist("a fox")

        _, kwargs = backend.generate_text.call_args
        self.assertEqual(kwargs["model"], "mistral:latest")


class PromptAssistantManagerErrorHandlingTest(unittest.TestCase):

    def test_ai_backend_error_is_normalized_into_prompt_assistant_error(self):
        backend = MagicMock()
        backend.generate_text.side_effect = AIBackendError("Ollama server unreachable")

        manager = PromptAssistantManager(backend, model_name="llama3.2:3b")

        with self.assertRaises(PromptAssistantError) as context:
            manager.assist("a fox")

        self.assertIn("Ollama server unreachable", str(context.exception))

    def test_busy_flag_is_reset_after_a_failed_call(self):
        backend = MagicMock()
        backend.generate_text.side_effect = AIBackendError("unreachable")

        manager = PromptAssistantManager(backend, model_name="llama3.2:3b")

        with self.assertRaises(PromptAssistantError):
            manager.assist("a fox")

        self.assertFalse(manager.busy)

    def test_concurrent_call_is_refused(self):
        backend = MagicMock()

        manager = PromptAssistantManager(backend, model_name="llama3.2:3b")
        manager._busy = True  # simulates a call already in progress

        with self.assertRaises(PromptAssistantError):
            manager.assist("a fox")

        backend.generate_text.assert_not_called()


if __name__ == "__main__":
    unittest.main()
