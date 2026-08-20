"""
Coverage for src/managers/prompt_assistant_manager.py — Mission 031.
AIBackend is mocked throughout (MagicMock satisfying the Protocol): no
network access, no real Ollama instance.
"""

import inspect
import typing
import unittest
from unittest.mock import MagicMock

from src.domain.character import Character
from src.engines.ai_backend import AIBackendError
from src.managers.prompt_assistant_manager import (
    OUTPUT_CONTRACT_BLOCK,
    PROMPT_DELIMITER_END,
    PROMPT_DELIMITER_START,
    CharacterContext,
    PromptAssistantError,
    PromptAssistantManager,
)


class PromptAssistantManagerCreateIntentTest(unittest.TestCase):

    def test_assist_without_existing_prompt_sends_a_create_instruction(self):
        backend = MagicMock()
        backend.generate_text.return_value = "a fox in a forest, cinematic lighting"

        manager = PromptAssistantManager(backend, model_name="llama3.2:3b")
        result = manager.assist("a fox in a forest")

        self.assertEqual(result, "a fox in a forest, cinematic lighting")
        backend.generate_text.assert_called_once_with(
            "Crée un prompt d'image à partir de cette demande :\na fox in a forest"
            f"\n\n{OUTPUT_CONTRACT_BLOCK}",
            model="llama3.2:3b",
        )

    def test_assist_with_blank_existing_prompt_is_treated_as_create(self):
        backend = MagicMock()
        backend.generate_text.return_value = "result"

        manager = PromptAssistantManager(backend, model_name="llama3.2:3b")
        manager.assist("a fox", existing_prompt="   ")

        backend.generate_text.assert_called_once_with(
            "Crée un prompt d'image à partir de cette demande :\na fox"
            f"\n\n{OUTPUT_CONTRACT_BLOCK}",
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
            "make it more cinematic"
            f"\n\n{OUTPUT_CONTRACT_BLOCK}",
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


class CharacterContextFromCharacterTest(unittest.TestCase):
    """Mission 034: the single Character -> CharacterContext conversion point."""

    def test_none_character_returns_none(self):
        self.assertIsNone(CharacterContext.from_character(None))

    def test_full_character_produces_all_four_fields(self):
        character = Character(
            character_lock="frizzy red hair, green eyes, freckles",
            trigger_token="sks_amy",
            description="A young woman with a warm smile",
            personality="Confident and playful",
            bio="Grew up in a small coastal town",
            interests="Sailing, painting",
        )

        context = CharacterContext.from_character(character)

        self.assertEqual(context.character_lock, "frizzy red hair, green eyes, freckles")
        self.assertEqual(context.trigger_token, "sks_amy")
        self.assertEqual(context.description, "A young woman with a warm smile")
        self.assertEqual(context.personality, "Confident and playful")

    def test_partial_character_leaves_unset_fields_blank(self):
        character = Character(character_lock="frizzy red hair", trigger_token="", description="", personality="")

        context = CharacterContext.from_character(character)

        self.assertEqual(context.character_lock, "frizzy red hair")
        self.assertEqual(context.trigger_token, "")
        self.assertEqual(context.description, "")
        self.assertEqual(context.personality, "")

    def test_all_four_retained_fields_blank_returns_none(self):
        character = Character(
            character_lock="",
            trigger_token="",
            description="",
            personality="",
            bio="Grew up in a small coastal town",
            interests="Sailing",
        )

        self.assertIsNone(CharacterContext.from_character(character))

    def test_whitespace_only_fields_are_treated_as_blank(self):
        character = Character(character_lock="   ", trigger_token="\n", description="\t", personality=" ")

        self.assertIsNone(CharacterContext.from_character(character))

    def test_bio_is_never_read(self):
        character = Character(character_lock="lock", bio="should never appear anywhere")

        context = CharacterContext.from_character(character)

        self.assertNotIn("should never appear anywhere", context)
        self.assertFalse(hasattr(context, "bio"))

    def test_interests_is_never_read(self):
        character = Character(character_lock="lock", interests="should never appear anywhere")

        context = CharacterContext.from_character(character)

        self.assertNotIn("should never appear anywhere", context)
        self.assertFalse(hasattr(context, "interests"))


class PromptAssistantManagerNoContextRegressionTest(unittest.TestCase):
    """
    Mission 034: character_context defaults to None -> no identity
    block/[DEMANDE ACTUELLE] label is ever added, still exactly true
    below. Mission 039 changes the literal backend text regardless of
    context (its whole purpose is the newly appended output-contract
    block) — these tests assert the Mission-034-scoped guarantee only,
    not byte-for-byte identity with text predating Mission 039.
    """

    def test_create_intent_without_context_has_no_identity_block(self):
        backend = MagicMock()
        backend.generate_text.return_value = "result"

        manager = PromptAssistantManager(backend, model_name="llama3.2:3b")
        manager.assist("a fox in a forest")

        backend.generate_text.assert_called_once_with(
            "Crée un prompt d'image à partir de cette demande :\na fox in a forest"
            f"\n\n{OUTPUT_CONTRACT_BLOCK}",
            model="llama3.2:3b",
        )

    def test_improve_intent_without_context_has_no_identity_block(self):
        backend = MagicMock()
        backend.generate_text.return_value = "result"

        manager = PromptAssistantManager(backend, model_name="llama3.2:3b")
        manager.assist("make it more cinematic", existing_prompt="a fox in a forest")

        backend.generate_text.assert_called_once_with(
            "Prompt existant à améliorer :\n"
            "a fox in a forest\n\n"
            "Instruction d'amélioration :\n"
            "make it more cinematic"
            f"\n\n{OUTPUT_CONTRACT_BLOCK}",
            model="llama3.2:3b",
        )

    def test_no_identity_block_or_demande_actuelle_label_leaks_in_without_context(self):
        text = PromptAssistantManager._build_combined_text("a fox", "", None)

        self.assertNotIn("[IDENTITÉ CANONIQUE", text)
        self.assertNotIn("[DEMANDE ACTUELLE]", text)
        self.assertEqual(
            text,
            "Crée un prompt d'image à partir de cette demande :\na fox"
            f"\n\n{OUTPUT_CONTRACT_BLOCK}",
        )


class PromptAssistantManagerWithContextTest(unittest.TestCase):
    """Mission 034: character_context prepends an explicit identity block."""

    def test_identity_block_precedes_demande_actuelle_block(self):
        context = CharacterContext(character_lock="lock", trigger_token="tok")

        text = PromptAssistantManager._build_combined_text("a fox", "", context)

        identity_index = text.index("[IDENTITÉ CANONIQUE")
        demande_index = text.index("[DEMANDE ACTUELLE]")
        self.assertLess(identity_index, demande_index)

    def test_character_lock_and_trigger_token_are_the_first_two_identity_lines(self):
        context = CharacterContext(
            character_lock="lock value",
            trigger_token="tok value",
            description="desc value",
            personality="pers value",
        )

        text = PromptAssistantManager._build_combined_text("a fox", "", context)
        lines = text.split("\n")

        self.assertIn("Character Lock : lock value", lines[1])
        self.assertIn("tok value", lines[2])
        self.assertIn("Trigger token", lines[2])

    def test_trigger_token_is_transmitted_exactly_once(self):
        context = CharacterContext(trigger_token="sks_amy")

        text = PromptAssistantManager._build_combined_text("a fox", "", context)

        self.assertEqual(text.count("sks_amy"), 1)

    def test_description_and_personality_are_conditional(self):
        context = CharacterContext(character_lock="lock only")

        text = PromptAssistantManager._build_combined_text("a fox", "", context)

        self.assertNotIn("Description :", text)
        self.assertNotIn("Personnalité :", text)

    def test_no_empty_field_line_within_the_identity_block(self):
        # A blank line intentionally separates [IDENTITÉ CANONIQUE] from
        # [DEMANDE ACTUELLE] (see the format in MISSION_034.md section
        # 4.5) — this test only checks that no *field* line (e.g.
        # "Description : ") is ever emitted with an empty value, not
        # that the text contains zero blank lines anywhere.
        context = CharacterContext(character_lock="lock", description="desc")

        text = PromptAssistantManager._build_combined_text("a fox", "", context)
        identity_block = text.split("\n\n")[0]

        for line in identity_block.split("\n"):
            self.assertNotEqual(line.strip(), "")

    def test_full_context_produces_all_four_labelled_lines(self):
        context = CharacterContext(
            character_lock="lock",
            trigger_token="tok",
            description="desc",
            personality="pers",
        )

        text = PromptAssistantManager._build_combined_text("a fox", "", context)

        self.assertIn("Character Lock : lock", text)
        self.assertIn("tok", text)
        self.assertIn("Description : desc", text)
        self.assertIn("Personnalité : pers", text)

    def test_improve_intent_request_block_still_used_verbatim_after_identity_block(self):
        context = CharacterContext(character_lock="lock")

        text = PromptAssistantManager._build_combined_text(
            "make it more cinematic", "a fox in a forest", context
        )

        self.assertIn(
            "Prompt existant à améliorer :\n"
            "a fox in a forest\n\n"
            "Instruction d'amélioration :\n"
            "make it more cinematic",
            text,
        )

    def test_assist_forwards_context_through_to_build_combined_text(self):
        backend = MagicMock()
        backend.generate_text.return_value = "result"
        context = CharacterContext(character_lock="lock")

        manager = PromptAssistantManager(backend, model_name="llama3.2:3b")
        manager.assist("a fox", character_context=context)

        sent_text = backend.generate_text.call_args[0][0]
        self.assertIn("[IDENTITÉ CANONIQUE", sent_text)


class PromptAssistantManagerCharacterDependencyArchitectureTest(unittest.TestCase):
    """
    Mission 034: PromptAssistantManager (the class) never touches
    Character — only CharacterContext.from_character() does, isolated
    in the same module (see docs/missions/MISSION_034.md section 4.1).
    """

    def test_manager_methods_never_take_character_as_a_parameter_or_return_type(self):
        # Checks actual type annotations (not source text — "Character
        # Lock : ..." is a display label, not a reference to the
        # Character class, and must not make this test fail).
        for name in ("assist", "_build_combined_text"):
            attr = inspect.getattr_static(PromptAssistantManager, name)
            func = attr.__func__ if isinstance(attr, staticmethod) else attr
            hints = typing.get_type_hints(func)
            for hint_name, hint in hints.items():
                self.assertIsNot(
                    hint, Character, f"{name}'s {hint_name} annotation unexpectedly is Character"
                )

    def test_manager_has_no_qt_import(self):
        import src.managers.prompt_assistant_manager as module

        source = inspect.getsource(module)
        self.assertNotIn("PySide6", source)


class PromptAssistantManagerOutputContractInstructionTest(unittest.TestCase):
    """Mission 039: the output-contract block is appended exactly once, identically for Créer/Améliorer and with/without CharacterContext."""

    def test_output_contract_present_in_create_mode(self):
        text = PromptAssistantManager._build_combined_text("a fox", "", None)

        self.assertIn(OUTPUT_CONTRACT_BLOCK, text)
        self.assertEqual(text.count(PROMPT_DELIMITER_START), 1)
        self.assertEqual(text.count(PROMPT_DELIMITER_END), 1)

    def test_output_contract_present_in_improve_mode(self):
        text = PromptAssistantManager._build_combined_text(
            "make it more cinematic", "a fox in a forest", None
        )

        self.assertIn(OUTPUT_CONTRACT_BLOCK, text)
        self.assertEqual(text.count(PROMPT_DELIMITER_START), 1)
        self.assertEqual(text.count(PROMPT_DELIMITER_END), 1)

    def test_output_contract_present_exactly_once_with_character_context(self):
        context = CharacterContext(character_lock="lock")

        text = PromptAssistantManager._build_combined_text("a fox", "", context)

        self.assertEqual(text.count(OUTPUT_CONTRACT_BLOCK), 1)

    def test_output_contract_block_comes_after_demande_actuelle_when_context_present(self):
        context = CharacterContext(character_lock="lock")

        text = PromptAssistantManager._build_combined_text("a fox", "", context)

        identity_index = text.index("[IDENTITÉ CANONIQUE")
        demande_index = text.index("[DEMANDE ACTUELLE]")
        contract_index = text.index("[INSTRUCTIONS DE SORTIE")
        self.assertLess(identity_index, demande_index)
        self.assertLess(demande_index, contract_index)


class PromptAssistantManagerExtractFinalPromptTest(unittest.TestCase):
    """Mission 039: deterministic extraction/fallback contract of _extract_final_prompt()."""

    def test_valid_pair_returns_only_the_interior_content(self):
        response = (
            f"{PROMPT_DELIMITER_START}\na fox in a forest, cinematic lighting\n{PROMPT_DELIMITER_END}"
        )

        result = PromptAssistantManager._extract_final_prompt(response)

        self.assertEqual(result, "a fox in a forest, cinematic lighting")

    def test_whitespace_around_delimiters_is_trimmed(self):
        response = (
            f"  \n{PROMPT_DELIMITER_START}   \n  a fox in a forest  \n   {PROMPT_DELIMITER_END}\n  "
        )

        result = PromptAssistantManager._extract_final_prompt(response)

        self.assertEqual(result, "a fox in a forest")

    def test_no_delimiter_falls_back_to_stripped_raw_response(self):
        response = "  Voici votre prompt : a fox in a forest  "

        result = PromptAssistantManager._extract_final_prompt(response)

        self.assertEqual(result, "Voici votre prompt : a fox in a forest")

    def test_start_delimiter_only_falls_back(self):
        response = f"{PROMPT_DELIMITER_START}\na fox in a forest"

        result = PromptAssistantManager._extract_final_prompt(response)

        self.assertEqual(result, response.strip())

    def test_end_delimiter_only_falls_back(self):
        response = f"a fox in a forest\n{PROMPT_DELIMITER_END}"

        result = PromptAssistantManager._extract_final_prompt(response)

        self.assertEqual(result, response.strip())

    def test_multiple_pairs_fall_back(self):
        response = (
            f"{PROMPT_DELIMITER_START}\nfirst\n{PROMPT_DELIMITER_END}\n\n"
            f"{PROMPT_DELIMITER_START}\nsecond\n{PROMPT_DELIMITER_END}"
        )

        result = PromptAssistantManager._extract_final_prompt(response)

        self.assertEqual(result, response.strip())

    def test_reversed_delimiters_fall_back(self):
        response = f"{PROMPT_DELIMITER_END}\na fox in a forest\n{PROMPT_DELIMITER_START}"

        result = PromptAssistantManager._extract_final_prompt(response)

        self.assertEqual(result, response.strip())

    def test_multiline_interior_content_is_preserved(self):
        response = (
            f"{PROMPT_DELIMITER_START}\n"
            "a fox in a forest,\ncinematic lighting,\ngolden hour\n"
            f"{PROMPT_DELIMITER_END}"
        )

        result = PromptAssistantManager._extract_final_prompt(response)

        self.assertEqual(result, "a fox in a forest,\ncinematic lighting,\ngolden hour")

    def test_markdown_inside_delimited_content_is_never_stripped(self):
        response = (
            f"{PROMPT_DELIMITER_START}\n"
            "**a fox** in a forest, # golden hour\n"
            f"{PROMPT_DELIMITER_END}"
        )

        result = PromptAssistantManager._extract_final_prompt(response)

        self.assertEqual(result, "**a fox** in a forest, # golden hour")

    def test_empty_content_between_valid_delimiters_falls_back(self):
        response = f"Voici le résultat :\n{PROMPT_DELIMITER_START}\n   \n{PROMPT_DELIMITER_END}"

        result = PromptAssistantManager._extract_final_prompt(response)

        self.assertEqual(result, response.strip())


class PromptAssistantManagerAssistExtractionIntegrationTest(unittest.TestCase):
    """Mission 039: assist() applies extraction/fallback to whatever AIBackend returns."""

    def test_assist_returns_only_delimited_content_when_backend_respects_the_contract(self):
        backend = MagicMock()
        backend.generate_text.return_value = (
            f"Bien sûr, voici votre prompt :\n{PROMPT_DELIMITER_START}\n"
            f"a fox in a forest\n{PROMPT_DELIMITER_END}"
        )

        manager = PromptAssistantManager(backend, model_name="llama3.2:3b")
        result = manager.assist("a fox in a forest")

        self.assertEqual(result, "a fox in a forest")

    def test_assist_returns_full_stripped_response_when_backend_ignores_the_contract(self):
        backend = MagicMock()
        backend.generate_text.return_value = "  a fox in a forest, no delimiters at all  "

        manager = PromptAssistantManager(backend, model_name="llama3.2:3b")
        result = manager.assist("a fox in a forest")

        self.assertEqual(result, "a fox in a forest, no delimiters at all")

    def test_ai_backend_error_never_reaches_extraction(self):
        backend = MagicMock()
        backend.generate_text.side_effect = AIBackendError("Ollama server unreachable")

        manager = PromptAssistantManager(backend, model_name="llama3.2:3b")

        with self.assertRaises(PromptAssistantError):
            manager.assist("a fox")


if __name__ == "__main__":
    unittest.main()
