"""
Integration coverage for the Prompt lifecycle, exercising
PromptManager, Character.prompts, Workspace persistence, EventBus and
the real DashboardPage/CharactersPage/ImagesPage/PromptsPage widgets
together — the same wiring MainWindow uses.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from src.core.event_bus import EventBus
from src.domain.character import Character
from src.managers.workspace_manager import (
    WorkspaceManager,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_SAVED,
    WORKSPACE_CLOSED,
)
from src.managers.character_manager import (
    CharacterManager,
    CHARACTER_CREATED,
    CHARACTER_SELECTED,
    CHARACTER_DELETED,
)
from src.managers.prompt_manager import (
    PromptManager,
    PROMPT_CREATED,
    PROMPT_SELECTED,
    PROMPT_DELETED,
)
from src.ui.pages.dashboard_page import DashboardPage
from src.ui.pages.characters_page import CharactersPage
from src.ui.pages.images_page import ImagesPage
from src.ui.pages.prompts_page import PromptsPage

WORKSPACE_EVENTS = (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_SAVED, WORKSPACE_CLOSED)
CHARACTER_EVENTS = (CHARACTER_CREATED, CHARACTER_SELECTED, CHARACTER_DELETED)
PROMPT_EVENTS = (PROMPT_CREATED, PROMPT_SELECTED, PROMPT_DELETED)

_app = QApplication.instance() or QApplication([])


class PromptRoundTripTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "PromptProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        prompt_manager = PromptManager(character_manager, workspace_manager, event_bus=event_bus)

        dashboard = DashboardPage()
        characters_page = CharactersPage(character_manager)
        images = ImagesPage(workspace_manager)
        # Mission 032: PromptAssistantManager is a MagicMock here — this
        # file exercises PromptsPage against real Workspace/Character/
        # Prompt Managers, but never the Assistant call itself (see
        # PromptsPagePromptAssistantTest below, and
        # test_assistant_result_does_not_persist_until_explicit_save
        # further down, which patches PromptAssistantDialog directly).
        prompts_page = PromptsPage(prompt_manager, MagicMock(), character_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, dashboard.update_project)
            event_bus.subscribe(event_name, images.update_images)
            event_bus.subscribe(event_name, characters_page.update_characters)
            event_bus.subscribe(event_name, prompts_page.update_prompts)

        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, characters_page.update_characters)
            event_bus.subscribe(event_name, prompts_page.update_prompts)

        for event_name in PROMPT_EVENTS:
            event_bus.subscribe(event_name, prompts_page.update_prompts)

        return (
            event_bus, workspace_manager, character_manager, prompt_manager,
            dashboard, characters_page, images, prompts_page,
        )

    def test_full_create_select_edit_save_close_reopen_cycle(self):

        (event_bus, workspace_manager, character_manager, prompt_manager,
         dashboard, characters_page, images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)

        master = prompt_manager.create("Master")
        prompt_manager.select(master.prompt_id)
        changed = prompt_manager.update_text("a beautiful character, cinematic lighting")
        self.assertTrue(changed)

        self.assertEqual(
            prompts_page.text_edit.toPlainText(),
            "a beautiful character, cinematic lighting",
        )

        workspace_manager.close()

        self.assertIsNone(prompt_manager.active_prompt_id)
        self.assertEqual(prompts_page.prompt_list.count(), 0)

        # Reopen with a second _wire() call — fresh instances, simulating
        # a real application restart rather than reusing in-memory state.
        (event_bus_2, workspace_manager_2, character_manager_2, prompt_manager_2,
         dashboard_2, characters_page_2, images_2, prompts_page_2) = self._wire()

        workspace_manager_2.open(self.folder)

        # Runtime-only per Mission 002/003/004/005 decisions: neither
        # active_character_id nor active_prompt_id survive a restart.
        # Checked BEFORE selecting anything below — selecting now would
        # trivially make this assertion pass for the wrong reason.
        self.assertIsNone(character_manager_2.active_character_id)
        self.assertIsNone(prompt_manager_2.active_prompt_id)

        # Mission 026: the reopened workspace also holds its auto-created
        # principal Character — retrieve "Aria" explicitly by name (the
        # Character these Prompts actually belong to), not by list index.
        restored_character = next(
            c for c in character_manager_2.characters if c.name == "Aria"
        )
        character_manager_2.select(restored_character.character_id)

        self.assertEqual(len(prompt_manager_2.prompts), 1)
        restored_prompt = prompt_manager_2.prompts[0]
        self.assertEqual(restored_prompt.name, "Master")
        self.assertEqual(restored_prompt.text, "a beautiful character, cinematic lighting")

    def test_update_text_is_idempotent(self):

        event_bus, workspace_manager, character_manager, prompt_manager = self._wire()[:4]
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        prompt = prompt_manager.create("Master")
        prompt_manager.select(prompt.prompt_id)

        events_seen = []
        for event_name in PROMPT_EVENTS:
            event_bus.subscribe(event_name, lambda payload, name=event_name: events_seen.append(name))

        # No active prompt at all: False, no save().
        prompt_manager.active_prompt_id = None
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertFalse(prompt_manager.update_text("irrelevant"))
            save_spy.assert_not_called()

        prompt_manager.select(prompt.prompt_id)
        events_seen.clear()  # select() above legitimately publishes prompt.selected

        # First real change: True, save() called, no prompt.* event.
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertTrue(prompt_manager.update_text("first version"))
            save_spy.assert_called_once()
        self.assertEqual(prompt_manager.active_prompt.text, "first version")
        self.assertEqual(events_seen, [])

        # Identical text again: False, save() NOT called, no prompt.* event.
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertFalse(prompt_manager.update_text("first version"))
            save_spy.assert_not_called()
        self.assertEqual(prompt_manager.active_prompt.text, "first version")
        self.assertEqual(events_seen, [])

        # Real change again: True, save() called, still no prompt.* event.
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertTrue(prompt_manager.update_text("second version"))
            save_spy.assert_called_once()
        self.assertEqual(prompt_manager.active_prompt.text, "second version")
        self.assertEqual(events_seen, [])

    def test_delete_active_prompt_resets_selection_and_persists(self):

        _, workspace_manager, character_manager, prompt_manager = self._wire()[:4]
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        keep = prompt_manager.create("Keep")
        drop = prompt_manager.create("Drop")
        prompt_manager.select(drop.prompt_id)

        result = prompt_manager.delete(drop.prompt_id)
        self.assertTrue(result)
        self.assertIsNone(prompt_manager.active_prompt_id)
        self.assertIsNone(prompt_manager.active_prompt)
        self.assertEqual([p.name for p in prompt_manager.prompts], ["Keep"])

        # Persists: reopening shows only the surviving prompt.
        _, workspace_manager_2, character_manager_2, prompt_manager_2 = self._wire()[:4]
        workspace_manager_2.open(self.folder)
        # Mission 026: retrieve "Aria" explicitly by name rather than by
        # list index (the reopened workspace also holds its auto-created
        # principal Character).
        restored_character = next(
            c for c in character_manager_2.characters if c.name == "Aria"
        )
        character_manager_2.select(restored_character.character_id)
        self.assertEqual([p.name for p in prompt_manager_2.prompts], ["Keep"])

    def test_prompt_manager_context_reset_on_character_and_workspace_change(self):

        _, workspace_manager, character_manager, prompt_manager = self._wire()[:4]
        workspace_manager.create(self.folder)

        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)
        prompt = prompt_manager.create("Master")
        prompt_manager.select(prompt.prompt_id)
        self.assertEqual(prompt_manager.active_prompt_id, prompt.prompt_id)

        # Switching the active character must reset active_prompt_id —
        # the new character's prompt list is unrelated.
        kai = character_manager.create("Kai")
        character_manager.select(kai.character_id)
        self.assertIsNone(prompt_manager.active_prompt_id)

        # Re-select Aria and her prompt, then confirm a workspace close
        # also resets it.
        character_manager.select(aria.character_id)
        prompt_manager.select(prompt.prompt_id)
        self.assertIsNotNone(prompt_manager.active_prompt_id)

        workspace_manager.close()
        self.assertIsNone(prompt_manager.active_prompt_id)

    def test_prompts_page_rebuilds_on_relevant_events(self):

        (_, workspace_manager, character_manager, prompt_manager,
         _dashboard, _characters_page, _images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        self.assertEqual(prompts_page.prompt_list.count(), 0)

        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        prompt = prompt_manager.create("Master")
        self.assertEqual(prompts_page.prompt_list.count(), 1)

        prompt_manager.select(prompt.prompt_id)
        prompt_manager.update_text("a beautiful character")
        # update_text() only publishes workspace.saved — this is what
        # PromptsPage's subscription to it must catch.
        self.assertEqual(prompts_page.text_edit.toPlainText(), "a beautiful character")

        workspace_manager.close()
        self.assertEqual(prompts_page.prompt_list.count(), 0)
        self.assertEqual(prompts_page.text_edit.toPlainText(), "")

    def test_no_duplicate_subscriptions_between_wire_calls(self):

        wired_1 = self._wire()
        wired_2 = self._wire()

        for obj_1, obj_2 in zip(wired_1, wired_2):
            self.assertIsNot(obj_1, obj_2)

        event_bus_1, event_bus_2 = wired_1[0], wired_2[0]

        # 4 subscribers registered directly by _wire() (dashboard, images,
        # characters_page, prompts_page) + CharacterManager's two own
        # internal subscriptions (active_character_id reset, and
        # Mission 026's principal-Character auto-creation) +
        # PromptManager's own internal reset subscription = 7, on EACH
        # bus independently.
        self.assertEqual(len(event_bus_1._subscribers[WORKSPACE_CREATED]), 7)
        self.assertEqual(len(event_bus_2._subscribers[WORKSPACE_CREATED]), 7)
        self.assertTrue(
            set(event_bus_1._subscribers[WORKSPACE_CREATED]).isdisjoint(
                event_bus_2._subscribers[WORKSPACE_CREATED]
            )
        )

    def test_create_with_text_does_not_select_or_affect_prompts_page_selection(self):
        """
        Mission 031 (InferencePage's "Enregistrer dans Prompts",
        pre-implementation verification 2): create(name, text=...) must
        set the text immediately without ever calling select() — an
        already-selected/displayed Prompt in PromptsPage must remain
        untouched.
        """
        (_, workspace_manager, character_manager, prompt_manager,
         _dashboard, _characters_page, _images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        first = prompt_manager.create("First")
        prompt_manager.select(first.prompt_id)
        self.assertEqual(prompts_page.prompt_list.currentItem().data(Qt.UserRole), first.prompt_id)

        second = prompt_manager.create("Second", text="a fox in a forest")

        self.assertEqual(second.text, "a fox in a forest")
        # active_prompt_id/PromptsPage's current selection must remain
        # exactly "First" — creating "Second" must never select it.
        self.assertEqual(prompt_manager.active_prompt_id, first.prompt_id)
        self.assertEqual(prompts_page.prompt_list.currentItem().data(Qt.UserRole), first.prompt_id)

    @patch("src.ui.pages.prompts_page.PromptAssistantDialog")
    def test_assistant_result_does_not_persist_until_explicit_save(self, mock_dialog_class):
        """
        Mission 032: "Utiliser ce texte" must never call
        PromptManager.update_text()/persist anything by itself — the
        Prompt Domain object must remain exactly as it was until
        "Enregistrer le texte" is clicked explicitly, verified here
        against a real PromptManager/Character/Workspace, not mocked
        ones (PromptAssistantDialog itself is mocked — its own behavior
        is already covered by test_prompt_assistant_dialog.py).
        """
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.Accepted
        mock_dialog.result_text = "a fox, golden hour"
        mock_dialog_class.return_value = mock_dialog

        (_, workspace_manager, character_manager, prompt_manager,
         _dashboard, _characters_page, _images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        prompt = prompt_manager.create("Master")
        prompt_manager.select(prompt.prompt_id)
        prompt_manager.update_text("original text")

        # Simulates an unsaved manual edit made in the editor before
        # opening the Assistant.
        prompts_page.text_edit.setPlainText("original text, edited")

        prompts_page.assistant_button.click()

        # existing_prompt passed to the dialog must be the edited,
        # unsaved editor text — never the persisted Domain value.
        _, kwargs = mock_dialog_class.call_args
        self.assertEqual(kwargs["existing_prompt"], "original text, edited")

        self.assertEqual(prompts_page.text_edit.toPlainText(), "a fox, golden hour")
        # No automatic persistence: the Domain Prompt is untouched.
        self.assertEqual(prompt_manager.active_prompt.text, "original text")

        # The existing explicit save mechanism still works afterward.
        prompts_page.save_button.click()
        self.assertEqual(prompt_manager.active_prompt.text, "a fox, golden hour")

    def test_dashboard_and_images_unaffected_by_prompt_events(self):

        (_, workspace_manager, character_manager, prompt_manager,
         dashboard, _characters_page, images, _prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        before_dashboard = dashboard.projectCard.value.text()
        before_images_count = images.list_widget.count()

        prompt_manager.create("Master")

        self.assertEqual(dashboard.projectCard.value.text(), before_dashboard)
        self.assertEqual(images.list_widget.count(), before_images_count)


class PromptCreationWithoutManualCharacterSelectionTest(unittest.TestCase):
    """
    Mission 029 regression: same defect as LoRAManager (see
    test_lora_roundtrip.py's LoRACreationWithoutManualCharacter
    SelectionTest), reproduced for PromptManager. Also proves that
    update_text() — which continues to depend on PromptManager's own
    active_prompt_id/select(), an entity-level selection mechanism
    entirely independent from CharacterManager.active_character
    (Mission 029 audit category 2, deliberately untouched) — still
    works correctly after the same reopen sequence.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        prompt_manager = PromptManager(character_manager, workspace_manager, event_bus=event_bus)
        return workspace_manager, character_manager, prompt_manager

    def test_prompt_lifecycle_survives_reopen_without_manual_character_selection(self):

        # 1. Create a fresh Workspace, attach a Prompt with text, close.
        workspace_manager, character_manager, prompt_manager = self._wire()
        workspace_manager.create(self.folder)
        principal = character_manager.principal_character

        existing = prompt_manager.create("Portrait")
        self.assertIsNotNone(existing)
        prompt_manager.select(existing.prompt_id)
        prompt_manager.update_text("Initial text")

        workspace_manager.close()

        # 2. Reopen — exactly the sequence that leaves active_character_id
        # at None (WORKSPACE_OPENED resets it, and nothing re-selects it,
        # since CharactersPage no longer calls select() at all).
        workspace_manager, character_manager, prompt_manager = self._wire()
        workspace_manager.open(self.folder)

        self.assertIsNone(character_manager.active_character_id)
        self.assertIsNotNone(character_manager.principal_character)
        self.assertEqual(
            character_manager.principal_character.character_id,
            principal.character_id,
        )

        # 3. The Prompt created before the reopen must still be visible,
        # with its saved text.
        prompts = prompt_manager.prompts
        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0].name, "Portrait")
        self.assertEqual(prompts[0].text, "Initial text")

        # 4. Entity-level selection/edit (category 2) must still work
        # unchanged — select() and update_text() never depended on
        # CharacterManager.active_character in the first place.
        prompt_manager.select(prompts[0].prompt_id)
        self.assertTrue(prompt_manager.update_text("Updated text"))
        self.assertEqual(prompt_manager.active_prompt.text, "Updated text")

        # 5. Creating a new Prompt must succeed, and must be genuinely
        # attached to the same principal Character — not merely non-None.
        second = prompt_manager.create("Second")
        self.assertIsNotNone(second)
        self.assertIn(second, character_manager.principal_character.prompts)
        self.assertEqual(len(prompt_manager.prompts), 2)

        # 6. Deleting must succeed too.
        self.assertTrue(prompt_manager.delete(existing.prompt_id))
        self.assertEqual(len(prompt_manager.prompts), 1)

        # 7. Persistence: close and reopen again, confirm only the
        # surviving Prompt remains.
        workspace_manager.close()
        workspace_manager, character_manager, prompt_manager = self._wire()
        workspace_manager.open(self.folder)

        self.assertIsNone(character_manager.active_character_id)
        final = prompt_manager.prompts
        self.assertEqual(len(final), 1)
        self.assertEqual(final[0].name, "Second")


class PromptsPagePromptAssistantTest(unittest.TestCase):
    """
    Mission 032: "Assistant IA" in PromptsPage, reusing Mission 031's
    PromptAssistantManager/PromptAssistantDialog unchanged. A
    lightweight setUp — unlike PromptRoundTripTest above, none of these
    tests exercise real Workspace/Character/Prompt persistence, only
    mocked Managers and the real PromptsPage widgets — mirrors
    InferencePagePromptAssistantTest (test_inference_page.py).
    """

    def setUp(self):
        self.prompt_manager = MagicMock()
        self.prompt_manager.active_prompt_id = None
        self.prompt_assistant_manager = MagicMock()
        # Mission 034: no identity by default in this lightweight suite
        # — individual tests below opt into a real Character where the
        # CharacterContext resolution itself is under test.
        self.character_manager = MagicMock()
        self.character_manager.principal_character = None

        self.page = PromptsPage(
            self.prompt_manager, self.prompt_assistant_manager, self.character_manager
        )

    def test_assistant_button_present_and_always_enabled(self):
        self.assertTrue(hasattr(self.page, "assistant_button"))
        self.assertTrue(self.page.assistant_button.isEnabled())

    @patch("src.ui.pages.prompts_page.PromptAssistantDialog")
    def test_no_active_prompt_dialog_receives_empty_existing_prompt(self, mock_dialog_class):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.Rejected
        mock_dialog_class.return_value = mock_dialog

        self.prompt_manager.active_prompt_id = None
        # Stray unsaved text with no Prompt selected must still be
        # ignored — "Améliorer" must never be offered in this case.
        self.page.text_edit.setPlainText("some stray unsaved text")
        self.page.assistant_button.click()

        self.assertEqual(mock_dialog_class.call_args[0][0], self.prompt_assistant_manager)
        _, kwargs = mock_dialog_class.call_args
        self.assertEqual(kwargs["existing_prompt"], "")

    @patch("src.ui.pages.prompts_page.PromptAssistantDialog")
    def test_no_character_dialog_receives_none_context(self, mock_dialog_class):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.Rejected
        mock_dialog_class.return_value = mock_dialog

        self.character_manager.principal_character = None
        self.page.assistant_button.click()

        _, kwargs = mock_dialog_class.call_args
        self.assertIsNone(kwargs["character_context"])

    @patch("src.ui.pages.prompts_page.PromptAssistantDialog")
    def test_character_with_identity_dialog_receives_the_resolved_context(self, mock_dialog_class):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.Rejected
        mock_dialog_class.return_value = mock_dialog

        self.character_manager.principal_character = Character(character_lock="frizzy red hair")
        self.page.assistant_button.click()

        _, kwargs = mock_dialog_class.call_args
        self.assertEqual(kwargs["character_context"].character_lock, "frizzy red hair")

    @patch("src.ui.pages.prompts_page.PromptAssistantDialog")
    def test_character_with_no_usable_identity_dialog_receives_none_context(self, mock_dialog_class):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.Rejected
        mock_dialog_class.return_value = mock_dialog

        self.character_manager.principal_character = Character()
        self.page.assistant_button.click()

        _, kwargs = mock_dialog_class.call_args
        self.assertIsNone(kwargs["character_context"])

    @patch("src.ui.pages.prompts_page.PromptAssistantDialog")
    def test_active_prompt_dialog_receives_current_editor_text(self, mock_dialog_class):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.Rejected
        mock_dialog_class.return_value = mock_dialog

        self.prompt_manager.active_prompt_id = "prompt-1"
        self.page.text_edit.setPlainText("a red fox, cinematic")
        self.page.assistant_button.click()

        _, kwargs = mock_dialog_class.call_args
        self.assertEqual(kwargs["existing_prompt"], "a red fox, cinematic")

    @patch("src.ui.pages.prompts_page.PromptAssistantDialog")
    def test_active_prompt_unsaved_edit_used_as_base_never_re_read_from_manager(self, mock_dialog_class):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.Rejected
        mock_dialog_class.return_value = mock_dialog

        self.prompt_manager.active_prompt_id = "prompt-1"
        # The Manager's own active_prompt.text is never consulted by
        # PromptsPage here — only text_edit's current content is.
        self.prompt_manager.active_prompt = MagicMock(text="the old saved version")
        self.page.text_edit.setPlainText("edited but not yet saved")
        self.page.assistant_button.click()

        _, kwargs = mock_dialog_class.call_args
        self.assertEqual(kwargs["existing_prompt"], "edited but not yet saved")
        self.prompt_manager.update_text.assert_not_called()

    @patch("src.ui.pages.prompts_page.PromptAssistantDialog")
    def test_assistant_result_replaces_editor_text_without_saving(self, mock_dialog_class):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.Accepted
        mock_dialog.result_text = "a red fox, golden hour, cinematic"
        mock_dialog_class.return_value = mock_dialog

        self.prompt_manager.active_prompt_id = "prompt-1"
        self.page.text_edit.setPlainText("a red fox")
        self.page.assistant_button.click()

        self.assertEqual(self.page.text_edit.toPlainText(), "a red fox, golden hour, cinematic")
        self.prompt_manager.update_text.assert_not_called()
        self.prompt_manager.create.assert_not_called()

    @patch("src.ui.pages.prompts_page.PromptAssistantDialog")
    def test_assistant_rejected_leaves_editor_text_unchanged(self, mock_dialog_class):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.Rejected
        mock_dialog.result_text = None
        mock_dialog_class.return_value = mock_dialog

        self.prompt_manager.active_prompt_id = "prompt-1"
        self.page.text_edit.setPlainText("a red fox")
        self.page.assistant_button.click()

        self.assertEqual(self.page.text_edit.toPlainText(), "a red fox")

    def test_save_text_still_works_after_assistant_module_change(self):
        # Non-regression: the pre-existing explicit save mechanism must
        # remain entirely untouched by Mission 032's addition.
        self.prompt_manager.active_prompt_id = "prompt-1"
        self.page.text_edit.setPlainText("a saved prompt")
        self.page.save_button.click()

        self.prompt_manager.update_text.assert_called_once_with("a saved prompt")


class PromptsPageSendToInferenceTest(unittest.TestCase):
    """
    Mission 033: "Envoyer vers Inference" button in PromptsPage. Only
    covers PromptsPage's own local behaviour (button state, signal
    emission with the exact editor text) — the collision/confirmation/
    navigation logic lives in MainWindow, see
    test_main_window_prompts_to_inference.py.
    """

    def setUp(self):
        self.prompt_manager = MagicMock()
        self.prompt_manager.active_prompt_id = None
        self.prompt_assistant_manager = MagicMock()
        self.character_manager = MagicMock()
        self.character_manager.principal_character = None

        self.page = PromptsPage(
            self.prompt_manager, self.prompt_assistant_manager, self.character_manager
        )

    def test_button_present_and_disabled_when_editor_empty(self):
        self.assertTrue(hasattr(self.page, "send_to_inference_button"))
        self.assertFalse(self.page.send_to_inference_button.isEnabled())

    def test_button_disabled_when_editor_whitespace_only(self):
        self.page.text_edit.setPlainText("   \n\t  ")
        self.assertFalse(self.page.send_to_inference_button.isEnabled())

    def test_button_enabled_when_text_present(self):
        self.page.text_edit.setPlainText("a red fox, cinematic")
        self.assertTrue(self.page.send_to_inference_button.isEnabled())

    def test_button_enabled_with_free_text_and_no_active_prompt(self):
        self.prompt_manager.active_prompt_id = None
        self.page.text_edit.setPlainText("stray unsaved text")
        self.assertTrue(self.page.send_to_inference_button.isEnabled())

    def test_button_disabled_again_after_text_cleared(self):
        self.page.text_edit.setPlainText("some text")
        self.assertTrue(self.page.send_to_inference_button.isEnabled())

        self.page.text_edit.setPlainText("")
        self.assertFalse(self.page.send_to_inference_button.isEnabled())

    def test_click_emits_signal_with_exact_visible_text(self):
        received = []
        self.page.send_to_inference_requested.connect(received.append)

        self.page.text_edit.setPlainText("a red fox,  cinematic\nnight")
        self.page.send_to_inference_button.click()

        self.assertEqual(received, ["a red fox,  cinematic\nnight"])

    def test_click_uses_unsaved_editor_text_not_persisted_prompt(self):
        received = []
        self.page.send_to_inference_requested.connect(received.append)

        self.prompt_manager.active_prompt_id = "prompt-1"
        self.prompt_manager.active_prompt = MagicMock(text="the old saved version")
        self.page.text_edit.setPlainText("edited but not yet saved")
        self.page.send_to_inference_button.click()

        self.assertEqual(received, ["edited but not yet saved"])

    def test_click_never_saves_or_creates_a_prompt(self):
        self.page.text_edit.setPlainText("a red fox")
        self.page.send_to_inference_button.click()

        self.prompt_manager.update_text.assert_not_called()
        self.prompt_manager.create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
