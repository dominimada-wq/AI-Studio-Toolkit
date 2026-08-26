"""
Integration coverage for the Prompt lifecycle, exercising
PromptManager, Character.prompts, Workspace persistence, EventBus and
the real DashboardPage/CharactersPage/ImagesPage/PromptsPage widgets
together — the same wiring MainWindow uses.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from src.core.event_bus import EventBus
from src.domain.character import Character
from src.infrastructure.storage.workspace_storage import WorkspaceStorage, WorkspaceStorageError
from src.managers.workspace_manager import (
    WorkspaceManager,
    WorkspaceManagerError,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_SAVED,
    WORKSPACE_CLOSED,
    WORKSPACE_RENAMED,
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
        characters_page = CharactersPage(character_manager, workspace_manager)
        images = ImagesPage(workspace_manager)
        # Mission 032: PromptAssistantManager is a MagicMock here — this
        # file exercises PromptsPage against real Workspace/Character/
        # Prompt Managers, but never the Assistant call itself (see
        # PromptsPagePromptAssistantTest below, and
        # test_assistant_result_does_not_persist_until_explicit_save
        # further down, which patches PromptAssistantDialog directly).
        prompts_page = PromptsPage(prompt_manager, MagicMock(), character_manager, workspace_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, dashboard.update_project)
            event_bus.subscribe(event_name, images.update_images)
            event_bus.subscribe(event_name, characters_page.update_characters)

        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, characters_page.update_characters)

        # Mission 038: PromptsPage splits its EventBus wiring exactly like
        # MainWindow now does (see main_window.py) — update_prompts() only
        # for the events where an unsaved draft must be preserved by
        # default (WORKSPACE_SAVED/RENAMED, CHARACTER_CREATED, plus its
        # own PROMPT_* events below); reset_for_context_change() is the
        # sole handler for the 5 events that are a genuine Workspace/
        # Character context reset, so the dirty-draft protection never
        # depends on subscriber ordering between the two methods.
        event_bus.subscribe(WORKSPACE_SAVED, prompts_page.update_prompts)
        event_bus.subscribe(WORKSPACE_RENAMED, prompts_page.update_prompts)
        event_bus.subscribe(CHARACTER_CREATED, prompts_page.update_prompts)

        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            event_bus.subscribe(event_name, prompts_page.reset_for_context_change)

        for event_name in (CHARACTER_SELECTED, CHARACTER_DELETED):
            event_bus.subscribe(event_name, prompts_page.reset_for_context_change)

        for event_name in PROMPT_EVENTS:
            event_bus.subscribe(event_name, prompts_page.update_prompts)

        return (
            event_bus, workspace_manager, character_manager, prompt_manager,
            dashboard, characters_page, images, prompts_page,
        )

    @staticmethod
    def _item_for_prompt(prompts_page, prompt_id):
        for i in range(prompts_page.prompt_list.count()):
            item = prompts_page.prompt_list.item(i)
            if item.data(Qt.UserRole) == prompt_id:
                return item
        return None

    def test_full_create_select_edit_save_close_reopen_cycle(self):

        (event_bus, workspace_manager, character_manager, prompt_manager,
         dashboard, characters_page, images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)

        master = prompt_manager.create("Master")
        prompt_manager.select(master.prompt_id)
        # Mission 038: update_text() called directly here (bypassing
        # PromptsPage.save_text()) only publishes workspace.saved, with
        # active_prompt_id unchanged — Category A, text_edit must stay
        # exactly as PromptsPage last set it (still "" from the select()
        # above), not reloaded from the Manager. Persistence itself is
        # verified below via the reopened prompt_manager_2, independent
        # of what PromptsPage's own editor happens to display.
        changed = prompt_manager.update_text("a beautiful character, cinematic lighting")
        self.assertTrue(changed)

        self.assertEqual(prompts_page.text_edit.toPlainText(), "")

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

    def test_update_name_is_idempotent(self):

        event_bus, workspace_manager, character_manager, prompt_manager = self._wire()[:4]
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        prompt = prompt_manager.create("Master")
        prompt_manager.select(prompt.prompt_id)
        prompt_manager.update_text("original text")

        events_seen = []
        for event_name in PROMPT_EVENTS:
            event_bus.subscribe(event_name, lambda payload, name=event_name: events_seen.append(name))

        # No active prompt at all: False, no save().
        prompt_manager.active_prompt_id = None
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertFalse(prompt_manager.update_name("irrelevant"))
            save_spy.assert_not_called()

        prompt_manager.select(prompt.prompt_id)
        events_seen.clear()

        # First real change: True, save() called, no prompt.* event, id
        # and text both untouched.
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertTrue(prompt_manager.update_name("Master Renamed"))
            save_spy.assert_called_once()
        self.assertEqual(prompt_manager.active_prompt.name, "Master Renamed")
        self.assertEqual(prompt_manager.active_prompt.prompt_id, prompt.prompt_id)
        self.assertEqual(prompt_manager.active_prompt.text, "original text")
        self.assertEqual(events_seen, [])

        # Identical value again: False, save() NOT called.
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertFalse(prompt_manager.update_name("Master Renamed"))
            save_spy.assert_not_called()

        # Empty string is a legitimate value, not rejected/stripped by the
        # Manager — same convention as CharacterManager.update(name=...)/
        # ModelManager.update_name()/WorkflowManager.update_name()/
        # LoRAManager.update_name() (Mission 052).
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertTrue(prompt_manager.update_name(""))
            save_spy.assert_called_once()
        self.assertEqual(prompt_manager.active_prompt.name, "")

    def test_rename_persists_after_close_reopen(self):

        _, workspace_manager, character_manager, prompt_manager = self._wire()[:4]
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        prompt = prompt_manager.create("Master")
        original_id = prompt.prompt_id
        prompt_manager.select(prompt.prompt_id)
        prompt_manager.update_text("original text")
        prompt_manager.update_name("Master Renamed")

        workspace_manager.close()

        _, workspace_manager_2, character_manager_2, prompt_manager_2 = self._wire()[:4]
        workspace_manager_2.open(self.folder)

        restored_character = next(
            c for c in character_manager_2.characters if c.name == "Aria"
        )
        character_manager_2.select(restored_character.character_id)

        self.assertEqual(len(prompt_manager_2.prompts), 1)
        restored = prompt_manager_2.prompts[0]
        self.assertEqual(restored.prompt_id, original_id)
        self.assertEqual(restored.name, "Master Renamed")
        self.assertEqual(restored.text, "original text")

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
        self.assertEqual(prompts_page.text_edit.toPlainText(), "")

        # Mission 038: update_text() only publishes workspace.saved, and
        # active_prompt_id does not change — text_edit must now be left
        # exactly as PromptsPage last set it (Category A: a refresh must
        # never overwrite text_edit when the loaded Prompt is unchanged),
        # not reloaded from the Manager, even though the same Prompt's
        # persisted text did change.
        prompt_manager.update_text("a beautiful character")
        self.assertEqual(prompts_page.text_edit.toPlainText(), "")

        workspace_manager.close()
        self.assertEqual(prompts_page.prompt_list.count(), 0)
        self.assertEqual(prompts_page.text_edit.toPlainText(), "")

    def test_no_duplicate_subscriptions_between_wire_calls(self):

        wired_1 = self._wire()
        wired_2 = self._wire()

        for obj_1, obj_2 in zip(wired_1, wired_2):
            self.assertIsNot(obj_1, obj_2)

        event_bus_1, event_bus_2 = wired_1[0], wired_2[0]

        # 4 subscribers registered directly by _wire() for WORKSPACE_CREATED
        # (dashboard, images, characters_page, prompts_page.reset_for_
        # context_change — Mission 038) + CharacterManager's two own
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

    @patch("src.ui.pages.prompts_page.QInputDialog.getText")
    def test_save_as_new_prompt_without_active_prompt_creates_and_selects_it(self, mock_get_text):
        """
        Mission 035: with no Prompt active (e.g. a fresh Assistant IA
        draft), "Enregistrer comme nouveau Prompt..." must create a new
        Prompt from the text currently visible, then explicitly select
        it — otherwise the synchronous PROMPT_CREATED refresh would
        wipe text_edit back to "" since no Prompt would yet match
        active_prompt_id.
        """
        mock_get_text.return_value = ("Draft", True)

        (_, workspace_manager, character_manager, prompt_manager,
         _dashboard, _characters_page, _images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        self.assertIsNone(prompt_manager.active_prompt_id)
        prompts_page.text_edit.setPlainText("a fox in a forest, golden hour")

        prompts_page.save_as_new_prompt_button.click()

        self.assertEqual(len(prompt_manager.prompts), 1)
        new_prompt = prompt_manager.prompts[0]
        self.assertEqual(new_prompt.name, "Draft")
        self.assertEqual(new_prompt.text, "a fox in a forest, golden hour")

        self.assertEqual(prompt_manager.active_prompt_id, new_prompt.prompt_id)
        self.assertEqual(
            prompts_page.prompt_list.currentItem().data(Qt.UserRole), new_prompt.prompt_id
        )
        # The editor must still show the same text after the
        # PROMPT_CREATED -> PROMPT_SELECTED refresh — not wiped to "".
        self.assertEqual(
            prompts_page.text_edit.toPlainText(), "a fox in a forest, golden hour"
        )

    @patch("src.ui.pages.prompts_page.QInputDialog.getText")
    def test_save_as_new_prompt_with_active_prompt_leaves_original_untouched(self, mock_get_text):
        """
        Mission 035: with a Prompt already active, "Enregistrer comme
        nouveau Prompt..." must never modify it — it always creates a
        distinct new Prompt from the text currently visible (possibly
        edited but not yet saved), which becomes the selection
        afterward instead of the original.
        """
        mock_get_text.return_value = ("Variant", True)

        (_, workspace_manager, character_manager, prompt_manager,
         _dashboard, _characters_page, _images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        original = prompt_manager.create("Original")
        prompt_manager.select(original.prompt_id)
        prompt_manager.update_text("original text")

        prompts_page.text_edit.setPlainText("original text, edited but not saved")

        prompts_page.save_as_new_prompt_button.click()

        # The original Prompt is strictly untouched.
        self.assertEqual(
            next(p for p in prompt_manager.prompts if p.name == "Original").text,
            "original text",
        )

        self.assertEqual(len(prompt_manager.prompts), 2)
        new_prompt = next(p for p in prompt_manager.prompts if p.name == "Variant")
        self.assertEqual(new_prompt.text, "original text, edited but not saved")

        # The new Prompt becomes the selection, not the original.
        self.assertEqual(prompt_manager.active_prompt_id, new_prompt.prompt_id)

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

    def test_dirty_draft_preserved_across_non_destructive_refresh(self):
        """
        Mission 038, Category A: WORKSPACE_SAVED, WORKSPACE_RENAMED and
        PROMPT_CREATED (without a select()) must never overwrite a dirty
        draft — active_prompt_id does not change in any of these three
        cases, only update_prompts()'s list rebuild runs.
        """
        (_, workspace_manager, character_manager, prompt_manager,
         _dashboard, _characters_page, _images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        prompt = prompt_manager.create("Master")
        prompt_manager.select(prompt.prompt_id)

        prompts_page.text_edit.setPlainText("a red fox, unsaved edit")
        self.assertTrue(prompts_page._dirty)

        # WORKSPACE_SAVED, unrelated to this exact edit.
        workspace_manager.save()
        self.assertEqual(prompts_page.text_edit.toPlainText(), "a red fox, unsaved edit")
        self.assertTrue(prompts_page._dirty)

        # WORKSPACE_RENAMED.
        workspace_manager.rename("PromptProjectRenamed")
        self.assertEqual(prompts_page.text_edit.toPlainText(), "a red fox, unsaved edit")
        self.assertTrue(prompts_page._dirty)

        # PROMPT_CREATED without select() — active_prompt_id stays on
        # the first Prompt.
        prompt_manager.create("Second")
        self.assertEqual(prompts_page.text_edit.toPlainText(), "a red fox, unsaved edit")
        self.assertTrue(prompts_page._dirty)
        self.assertEqual(prompts_page.prompt_list.count(), 2)

    def test_prompt_switch_with_dirty_draft_save_choice(self):

        (_, workspace_manager, character_manager, prompt_manager,
         _dashboard, _characters_page, _images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        first = prompt_manager.create("First")
        second = prompt_manager.create("Second")
        prompt_manager.select(first.prompt_id)

        prompts_page.text_edit.setPlainText("first, unsaved edit")
        second_item = self._item_for_prompt(prompts_page, second.prompt_id)

        with patch("src.ui.pages.prompts_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Save
            prompts_page.prompt_list.setCurrentItem(second_item)

        self.assertEqual(
            next(p for p in prompt_manager.prompts if p.name == "First").text,
            "first, unsaved edit",
        )
        self.assertEqual(prompt_manager.active_prompt_id, second.prompt_id)
        self.assertFalse(prompts_page._dirty)

    def test_prompt_switch_with_dirty_draft_discard_choice(self):

        (_, workspace_manager, character_manager, prompt_manager,
         _dashboard, _characters_page, _images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        first = prompt_manager.create("First")
        second = prompt_manager.create("Second")
        prompt_manager.select(first.prompt_id)

        prompts_page.text_edit.setPlainText("first, unsaved edit")
        second_item = self._item_for_prompt(prompts_page, second.prompt_id)

        with patch("src.ui.pages.prompts_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Discard
            prompts_page.prompt_list.setCurrentItem(second_item)

        self.assertEqual(
            next(p for p in prompt_manager.prompts if p.name == "First").text, ""
        )
        self.assertEqual(prompt_manager.active_prompt_id, second.prompt_id)
        self.assertFalse(prompts_page._dirty)

    def test_prompt_switch_with_dirty_draft_cancel_choice_restores_selection(self):
        """
        Mission 038: Annuler must never call PromptManager.select() at
        all — the Manager's active_prompt_id stays untouched, and the
        widget's own native selection (already changed by Qt before
        on_prompt_selection_changed ran) is reverted back to the
        previous item, with prompt_list signals blocked to avoid
        recursively re-entering the same handler.
        """
        (_, workspace_manager, character_manager, prompt_manager,
         _dashboard, _characters_page, _images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        first = prompt_manager.create("First")
        second = prompt_manager.create("Second")
        prompt_manager.select(first.prompt_id)

        prompts_page.text_edit.setPlainText("first, unsaved edit")
        second_item = self._item_for_prompt(prompts_page, second.prompt_id)

        with patch.object(
            type(prompt_manager), "select", wraps=prompt_manager.select
        ) as select_spy, patch("src.ui.pages.prompts_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Cancel
            prompts_page.prompt_list.setCurrentItem(second_item)
            select_spy.assert_not_called()

        self.assertEqual(prompt_manager.active_prompt_id, first.prompt_id)
        self.assertEqual(
            prompts_page.prompt_list.currentItem().data(Qt.UserRole), first.prompt_id
        )
        self.assertEqual(prompts_page.text_edit.toPlainText(), "first, unsaved edit")
        self.assertTrue(prompts_page._dirty)

    def test_prompt_switch_with_dirty_draft_save_choice_persistence_failure(self):
        """
        Mission 070: a Save choice whose update_text() raises
        WorkspaceManagerError must produce exactly the same outcome as
        Cancel above — select() never called, visual selection reverted
        to `previous` via the identical blockSignals/setCurrentItem
        mechanism — plus an explicit error message and a rolled-back
        Prompt.text (no phantom mutation, no silent later persistence).
        """
        (_, workspace_manager, character_manager, prompt_manager,
         _dashboard, _characters_page, _images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        first = prompt_manager.create("First", text="original text")
        second = prompt_manager.create("Second")
        prompt_manager.select(first.prompt_id)

        prompts_page.text_edit.setPlainText("first, unsaved edit")
        second_item = self._item_for_prompt(prompts_page, second.prompt_id)

        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(
            type(prompt_manager), "select", wraps=prompt_manager.select
        ) as select_spy, patch("src.ui.pages.prompts_page.QMessageBox") as mock_message_box, \
                patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            mock_message_box.return_value.exec.return_value = mock_message_box.Save
            prompts_page.prompt_list.setCurrentItem(second_item)
            select_spy.assert_not_called()

        self.assertTrue(mock_message_box.critical.called)
        self.assertEqual(prompt_manager.active_prompt_id, first.prompt_id)
        self.assertEqual(prompts_page._loaded_prompt_id, first.prompt_id)
        self.assertEqual(
            prompts_page.prompt_list.currentItem().data(Qt.UserRole), first.prompt_id
        )
        self.assertEqual(prompts_page.text_edit.toPlainText(), "first, unsaved edit")
        self.assertTrue(prompts_page._dirty)
        self.assertEqual(first.text, "original text")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_prompt_switch_with_dirty_draft_save_choice_persistence_failure_then_retry(self):
        (_, workspace_manager, character_manager, prompt_manager,
         _dashboard, _characters_page, _images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        first = prompt_manager.create("First", text="original text")
        second = prompt_manager.create("Second")
        prompt_manager.select(first.prompt_id)

        prompts_page.text_edit.setPlainText("first, unsaved edit")
        second_item = self._item_for_prompt(prompts_page, second.prompt_id)

        with patch("src.ui.pages.prompts_page.QMessageBox") as mock_message_box, \
                patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            mock_message_box.return_value.exec.return_value = mock_message_box.Save
            prompts_page.prompt_list.setCurrentItem(second_item)

        # Disk is fixed now — retrying the exact same switch must be a
        # genuine new attempt, not neutralized by update_text()'s own
        # idempotence guard (the Domain was rolled back to "original
        # text", so "first, unsaved edit" no longer matches it).
        with patch("src.ui.pages.prompts_page.QMessageBox") as mock_message_box_2:
            mock_message_box_2.return_value.exec.return_value = mock_message_box_2.Save
            prompts_page.prompt_list.setCurrentItem(second_item)

        self.assertEqual(first.text, "first, unsaved edit")
        self.assertEqual(prompt_manager.active_prompt_id, second.prompt_id)
        self.assertFalse(prompts_page._dirty)

        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        first_on_disk = next(p for p in aria["prompts"] if p["name"] == "First")
        self.assertEqual(first_on_disk["text"], "first, unsaved edit")

    def test_prompt_switch_without_dirty_draft_selects_immediately_no_dialog(self):

        (_, workspace_manager, character_manager, prompt_manager,
         _dashboard, _characters_page, _images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        first = prompt_manager.create("First")
        second = prompt_manager.create("Second")
        prompt_manager.select(first.prompt_id)

        self.assertFalse(prompts_page._dirty)
        second_item = self._item_for_prompt(prompts_page, second.prompt_id)

        with patch("src.ui.pages.prompts_page.QMessageBox") as mock_message_box:
            prompts_page.prompt_list.setCurrentItem(second_item)
            mock_message_box.assert_not_called()

        self.assertEqual(prompt_manager.active_prompt_id, second.prompt_id)

    def test_delete_dirty_prompt_cancel_keeps_prompt_and_draft(self):

        (_, workspace_manager, character_manager, prompt_manager,
         _dashboard, _characters_page, _images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        prompt_manager.select(prompt_manager.create("Master").prompt_id)
        prompts_page.text_edit.setPlainText("unsaved edit")

        with patch("src.ui.pages.prompts_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Cancel
            prompts_page.delete_prompt()

        self.assertEqual(len(prompt_manager.prompts), 1)
        self.assertEqual(prompts_page.text_edit.toPlainText(), "unsaved edit")
        self.assertTrue(prompts_page._dirty)

    def test_delete_dirty_prompt_confirm_deletes_and_clears_draft(self):

        (_, workspace_manager, character_manager, prompt_manager,
         _dashboard, _characters_page, _images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        prompt_manager.select(prompt_manager.create("Master").prompt_id)
        prompts_page.text_edit.setPlainText("unsaved edit")

        with patch("src.ui.pages.prompts_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Discard
            prompts_page.delete_prompt()

        self.assertEqual(len(prompt_manager.prompts), 0)
        self.assertEqual(prompts_page.text_edit.toPlainText(), "")
        self.assertFalse(prompts_page._dirty)

    def test_delete_non_dirty_prompt_unchanged_no_dialog(self):

        (_, workspace_manager, character_manager, prompt_manager,
         _dashboard, _characters_page, _images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        prompt_manager.select(prompt_manager.create("Master").prompt_id)
        self.assertFalse(prompts_page._dirty)

        with patch("src.ui.pages.prompts_page.QMessageBox") as mock_message_box:
            prompts_page.delete_prompt()
            mock_message_box.assert_not_called()

        self.assertEqual(len(prompt_manager.prompts), 0)

    @patch("src.ui.pages.prompts_page.QInputDialog.getText")
    def test_create_prompt_preserves_dirty_draft(self, mock_get_text):
        mock_get_text.return_value = ("New Empty Prompt", True)

        (_, workspace_manager, character_manager, prompt_manager,
         _dashboard, _characters_page, _images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        existing = prompt_manager.create("Existing")
        prompt_manager.select(existing.prompt_id)
        prompts_page.text_edit.setPlainText("unsaved edit")

        prompts_page.create_prompt()

        # active_prompt_id unchanged (create_prompt() never selects), so
        # the draft and dirty state must survive — only the list gains
        # an entry.
        self.assertEqual(prompt_manager.active_prompt_id, existing.prompt_id)
        self.assertEqual(prompts_page.text_edit.toPlainText(), "unsaved edit")
        self.assertTrue(prompts_page._dirty)
        self.assertEqual(prompts_page.prompt_list.count(), 2)

    def test_reset_for_context_change_clears_dirty_draft_on_workspace_close(self):

        (_, workspace_manager, character_manager, prompt_manager,
         _dashboard, _characters_page, _images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        prompt_manager.select(prompt_manager.create("Master").prompt_id)
        prompts_page.text_edit.setPlainText("unsaved edit")
        self.assertTrue(prompts_page._dirty)

        workspace_manager.close()

        self.assertEqual(prompts_page.text_edit.toPlainText(), "")
        self.assertFalse(prompts_page._dirty)
        self.assertIsNone(prompts_page._loaded_prompt_id)
        self.assertEqual(prompts_page.prompt_list.count(), 0)

    def test_reset_for_context_change_clears_dirty_draft_with_no_prompt_selected(self):
        """
        Mission 038: the exact edge case that requires
        reset_for_context_change() to be the sole handler for these 5
        events rather than layered on top of update_prompts()'s own
        active_prompt_id vs _loaded_prompt_id comparison — with no
        Prompt selected at all, both sides are already None before the
        Workspace switch, which a comparison-only approach would
        wrongly read as "nothing changed".
        """
        (_, workspace_manager, character_manager, prompt_manager,
         _dashboard, _characters_page, _images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        self.assertIsNone(prompt_manager.active_prompt_id)
        self.assertIsNone(prompts_page._loaded_prompt_id)

        prompts_page.text_edit.setPlainText("stray unsaved draft, no prompt selected")
        self.assertTrue(prompts_page._dirty)

        workspace_manager.close()

        self.assertEqual(prompts_page.text_edit.toPlainText(), "")
        self.assertFalse(prompts_page._dirty)

    def test_reset_for_context_change_on_character_selected_and_deleted(self):

        (_, workspace_manager, character_manager, prompt_manager,
         _dashboard, _characters_page, _images, prompts_page) = self._wire()

        workspace_manager.create(self.folder)
        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)

        prompt_manager.select(prompt_manager.create("Master").prompt_id)
        prompts_page.text_edit.setPlainText("unsaved edit")

        kai = character_manager.create("Kai")
        character_manager.select(kai.character_id)

        self.assertEqual(prompts_page.text_edit.toPlainText(), "")
        self.assertFalse(prompts_page._dirty)
        self.assertEqual(prompts_page.prompt_list.count(), 0)

        prompts_page.text_edit.setPlainText("kai's own unsaved draft")
        self.assertTrue(prompts_page._dirty)

        character_manager.delete(kai.character_id)

        self.assertEqual(prompts_page.text_edit.toPlainText(), "")
        self.assertFalse(prompts_page._dirty)

    def test_update_prompts_never_subscribed_to_context_reset_events(self):

        (event_bus, workspace_manager, character_manager, prompt_manager,
         _dashboard, _characters_page, _images, prompts_page) = self._wire()

        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            self.assertNotIn(
                prompts_page.update_prompts, event_bus._subscribers[event_name]
            )
            self.assertIn(
                prompts_page.reset_for_context_change, event_bus._subscribers[event_name]
            )

        for event_name in (CHARACTER_SELECTED, CHARACTER_DELETED):
            self.assertNotIn(
                prompts_page.update_prompts, event_bus._subscribers[event_name]
            )
            self.assertIn(
                prompts_page.reset_for_context_change, event_bus._subscribers[event_name]
            )


class PromptManagerScalarRollbackTest(unittest.TestCase):
    """
    Mission 070: PromptManager.update_text()/update_name() roll back
    their respective scalar to its previous value if save() fails —
    single-scalar Domain-only mutations, no filesystem involved, so a
    local rollback is sufficient.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.prompt_manager = PromptManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.prompt = self.prompt_manager.create("Master", text="original text")
        self.prompt_manager.select(self.prompt.prompt_id)

    def test_update_text_save_failure_restores_previous_text_on_same_object(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.prompt_manager.update_text("edited text")

        self.assertEqual(self.prompt.text, "original text")
        self.assertIs(self.prompt_manager.active_prompt, self.prompt)

    def test_update_text_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.prompt_manager.update_text("edited text")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_update_text_save_failure_publishes_no_success_event(self):
        received = []
        self.event_bus.subscribe(WORKSPACE_SAVED, lambda payload: received.append(payload))

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.prompt_manager.update_text("edited text")

        self.assertEqual(received, [])

    def test_retry_of_the_same_previously_rejected_text_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.prompt_manager.update_text("edited text")

        # Domain was rolled back to "original text" — retrying the exact
        # same "edited text" value must not be short-circuited by the
        # idempotence guard, since it no longer matches.
        result = self.prompt_manager.update_text("edited text")

        self.assertTrue(result)
        self.assertEqual(self.prompt.text, "edited text")
        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        self.assertEqual(aria["prompts"][0]["text"], "edited text")

    def test_update_name_save_failure_restores_previous_name_on_same_object(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.prompt_manager.update_name("Master Renamed")

        self.assertEqual(self.prompt.name, "Master")
        self.assertIs(self.prompt_manager.active_prompt, self.prompt)

    def test_update_name_save_failure_never_touches_text(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.prompt_manager.update_name("Master Renamed")

        self.assertEqual(self.prompt.text, "original text")

    def test_retry_of_the_same_previously_rejected_name_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.prompt_manager.update_name("Master Renamed")

        result = self.prompt_manager.update_name("Master Renamed")

        self.assertTrue(result)
        self.assertEqual(self.prompt.name, "Master Renamed")


class PromptManagerDeleteRollbackTest(unittest.TestCase):
    """
    Mission 071: PromptManager.delete() rolls back the in-memory removal
    (and active_prompt_id) if save() fails — Domain-only mutation, no
    filesystem involved, so the rollback is a simple local re-insertion
    at the original index. Mirrors DatasetManager.delete()/
    LoRAManager.delete()/ModelManager.delete()/TrainingManager.delete()/
    WorkflowManager.delete() (Mission 068), a family this method was
    inadvertently left out of — Prompt carries no extra business guard
    (unlike Dataset's is_referenced_by_training()), so there is nothing
    else to preserve here.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.prompt_manager = PromptManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.prompt_a = self.prompt_manager.create("Alpha")
        self.prompt_b = self.prompt_manager.create("Beta")
        self.prompt_c = self.prompt_manager.create("Gamma")
        self.prompt_manager.select(self.prompt_b.prompt_id)

    def test_delete_succeeds_normally_when_save_works(self):
        result = self.prompt_manager.delete(self.prompt_b.prompt_id)

        self.assertTrue(result)
        self.assertEqual(
            [p.prompt_id for p in self.prompt_manager.prompts],
            [self.prompt_a.prompt_id, self.prompt_c.prompt_id],
        )
        self.assertIsNone(self.prompt_manager.active_prompt_id)

    def test_delete_save_failure_restores_object_at_original_index(self):
        received = []
        self.event_bus.subscribe(PROMPT_DELETED, lambda payload: received.append(payload))

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.prompt_manager.delete(self.prompt_b.prompt_id)

        prompts = self.prompt_manager.prompts
        self.assertEqual(
            [p.prompt_id for p in prompts],
            [self.prompt_a.prompt_id, self.prompt_b.prompt_id, self.prompt_c.prompt_id],
        )
        # Same object, not a recreated equivalent.
        self.assertIs(prompts[1], self.prompt_b)
        self.assertEqual(received, [])

    def test_delete_save_failure_restores_active_prompt_id(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.prompt_manager.delete(self.prompt_b.prompt_id)

        self.assertEqual(self.prompt_manager.active_prompt_id, self.prompt_b.prompt_id)

    def test_delete_save_failure_never_touches_an_unrelated_active_id(self):
        self.prompt_manager.select(self.prompt_a.prompt_id)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.prompt_manager.delete(self.prompt_b.prompt_id)

        self.assertEqual(self.prompt_manager.active_prompt_id, self.prompt_a.prompt_id)

    def test_delete_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.prompt_manager.delete(self.prompt_b.prompt_id)

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_after_save_failure_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.prompt_manager.delete(self.prompt_b.prompt_id)

        result = self.prompt_manager.delete(self.prompt_b.prompt_id)

        self.assertTrue(result)
        self.assertEqual(
            [p.prompt_id for p in self.prompt_manager.prompts],
            [self.prompt_a.prompt_id, self.prompt_c.prompt_id],
        )

        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        self.assertEqual(
            sorted(p["prompt_id"] for p in aria["prompts"]),
            sorted([self.prompt_a.prompt_id, self.prompt_c.prompt_id]),
        )


class PromptsPageConfirmContextChangeTest(unittest.TestCase):
    """
    Mission 069: PromptsPage.confirm_context_change() — called by
    MainWindow.new_project()/open_project() before the Workspace switch
    that would otherwise let reset_for_context_change() silently discard
    an unsaved draft (those events fire only after current_workspace has
    already been replaced, too late for a genuine Save or Cancel).
    Reuses _confirm_discard_before_switch()'s existing Save/Discard/
    Cancel dialog verbatim.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "PromptProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        prompt_manager = PromptManager(character_manager, workspace_manager, event_bus=event_bus)
        prompts_page = PromptsPage(prompt_manager, MagicMock(), character_manager, workspace_manager)
        return workspace_manager, character_manager, prompt_manager, prompts_page

    def _make_dirty_prompt(self, workspace_manager, character_manager, prompt_manager, prompts_page):
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        prompt = prompt_manager.create("Master", text="original")
        prompt_manager.select(prompt.prompt_id)
        prompts_page.text_edit.setPlainText("original edited, not saved")
        self.assertTrue(prompts_page._dirty)
        return prompt

    def test_no_dirty_draft_returns_true_without_any_dialog(self):
        _, _, _, prompts_page = self._wire()

        with patch.object(prompts_page, "_confirm_discard_before_switch") as confirm_mock:
            result = prompts_page.confirm_context_change()

        self.assertTrue(result)
        confirm_mock.assert_not_called()

    def test_save_choice_persists_into_the_old_workspace_and_returns_true(self):
        workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        prompt = self._make_dirty_prompt(workspace_manager, character_manager, prompt_manager, prompts_page)

        with patch.object(
            prompts_page, "_confirm_discard_before_switch", return_value=QMessageBox.Save
        ):
            result = prompts_page.confirm_context_change()

        self.assertTrue(result)
        self.assertFalse(prompts_page._dirty)
        self.assertEqual(prompt.text, "original edited, not saved")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        self.assertEqual(aria["prompts"][0]["text"], "original edited, not saved")

    def test_discard_choice_never_persists_and_returns_true(self):
        workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        prompt = self._make_dirty_prompt(workspace_manager, character_manager, prompt_manager, prompts_page)

        with patch.object(
            prompts_page, "_confirm_discard_before_switch", return_value=QMessageBox.Discard
        ):
            result = prompts_page.confirm_context_change()

        self.assertTrue(result)
        self.assertEqual(prompt.text, "original")

    def test_cancel_choice_returns_false_and_leaves_everything_unchanged(self):
        workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        prompt = self._make_dirty_prompt(workspace_manager, character_manager, prompt_manager, prompts_page)

        with patch.object(
            prompts_page, "_confirm_discard_before_switch", return_value=QMessageBox.Cancel
        ):
            result = prompts_page.confirm_context_change()

        self.assertFalse(result)
        self.assertTrue(prompts_page._dirty)
        self.assertEqual(prompt.text, "original")
        self.assertEqual(prompts_page.text_edit.toPlainText(), "original edited, not saved")
        self.assertEqual(prompt_manager.active_prompt_id, prompt.prompt_id)
        self.assertEqual(workspace_manager.current_workspace.root, self.folder)

    def test_save_failure_shows_critical_message_returns_false_and_keeps_dirty(self):
        # Note: at the time M069 shipped, PromptManager.update_text() had
        # a pre-existing, out-of-scope gap (mutated prompt.text in memory
        # before save(), no rollback) — Mission 070 has since closed that
        # gap at the Domain level, so this test now also asserts the
        # in-memory Prompt.text itself, not just project.json.
        workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        prompt = self._make_dirty_prompt(workspace_manager, character_manager, prompt_manager, prompts_page)

        with patch.object(
            prompts_page, "_confirm_discard_before_switch", return_value=QMessageBox.Save
        ), patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ), patch("src.ui.pages.prompts_page.QMessageBox.critical") as critical_mock:
            result = prompts_page.confirm_context_change()

        self.assertFalse(result)
        critical_mock.assert_called_once()
        self.assertTrue(prompts_page._dirty)
        self.assertEqual(prompts_page.text_edit.toPlainText(), "original edited, not saved")
        self.assertEqual(prompt.text, "original")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        self.assertEqual(aria["prompts"][0]["text"], "original")


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

    def test_create_prompt_without_open_workspace_shows_no_project_warning(self):
        # Mission 036: PromptsPage.create_prompt() must distinguish "no
        # Workspace open" from "Workspace open, zero Character" (see the
        # sibling test below) — both make PromptManager.create() return
        # None.
        workspace_manager, character_manager, prompt_manager = self._wire()
        prompts_page = PromptsPage(prompt_manager, MagicMock(), character_manager, workspace_manager)

        with patch(
            "src.ui.pages.prompts_page.QInputDialog.getText",
            return_value=("Portrait", True),
        ), patch("src.ui.pages.prompts_page.QMessageBox.warning") as mock_warning:
            prompts_page.create_prompt()
            mock_warning.assert_called_once_with(
                prompts_page,
                "Aucun projet ouvert",
                "Ouvrez ou créez un projet avant de créer un prompt."
            )

    def test_create_prompt_with_open_workspace_and_no_character_shows_personnage_warning(self):
        # Sibling of the test above: same None from PromptManager.
        # create(), but here the Workspace is open with zero Character.
        workspace_manager, character_manager, prompt_manager = self._wire()
        workspace_manager.create(self.folder)
        principal = character_manager.characters[0]
        character_manager.delete(principal.character_id)
        prompts_page = PromptsPage(prompt_manager, MagicMock(), character_manager, workspace_manager)

        with patch(
            "src.ui.pages.prompts_page.QInputDialog.getText",
            return_value=("Portrait", True),
        ), patch("src.ui.pages.prompts_page.QMessageBox.warning") as mock_warning:
            prompts_page.create_prompt()
            mock_warning.assert_called_once_with(
                prompts_page,
                "Aucun personnage",
                "Ce projet ne possède aucun personnage — créez-en un depuis Characters avant de créer un prompt."
            )


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
        self.workspace_manager = MagicMock()
        self.workspace_manager.opened = True

        self.page = PromptsPage(
            self.prompt_manager, self.prompt_assistant_manager, self.character_manager,
            self.workspace_manager,
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

    @patch("src.ui.pages.prompts_page.PromptAssistantDialog")
    def test_assistant_result_marks_editor_dirty(self, mock_dialog_class):
        # Mission 038: "Utiliser ce texte" must mark the editor dirty,
        # unlike a programmatic reload from update_prompts()/
        # reset_for_context_change() — the user must still click
        # "Enregistrer le texte" explicitly afterward.
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.Accepted
        mock_dialog.result_text = "a red fox, golden hour"
        mock_dialog_class.return_value = mock_dialog

        self.prompt_manager.active_prompt_id = "prompt-1"
        self.assertFalse(self.page._dirty)

        self.page.assistant_button.click()

        self.assertTrue(self.page._dirty)

    def test_save_text_clears_dirty_flag(self):
        self.prompt_manager.active_prompt_id = "prompt-1"
        self.prompt_manager.update_text.return_value = True
        self.page.text_edit.setPlainText("a saved prompt")
        self.assertTrue(self.page._dirty)

        self.page.save_button.click()

        self.assertFalse(self.page._dirty)

    def test_save_text_clears_dirty_flag_even_when_idempotent(self):
        # Mission 038: update_text() returning False (text already
        # matches the persisted value) still satisfies the UI's save
        # intent — dirty must be cleared regardless of the return value.
        self.prompt_manager.active_prompt_id = "prompt-1"
        self.prompt_manager.update_text.return_value = False
        self.page.text_edit.setPlainText("already saved text")
        self.assertTrue(self.page._dirty)

        self.page.save_button.click()

        self.assertFalse(self.page._dirty)


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
        self.workspace_manager = MagicMock()
        self.workspace_manager.opened = True

        self.page = PromptsPage(
            self.prompt_manager, self.prompt_assistant_manager, self.character_manager,
            self.workspace_manager,
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


class PromptsPageSaveAsNewPromptTest(unittest.TestCase):
    """
    Mission 035: "Enregistrer comme nouveau Prompt..." button in
    PromptsPage — covers PromptsPage's own local behaviour (button
    state, dialog interaction, exact Manager calls) against mocked
    Managers, mirroring PromptsPageSendToInferenceTest above.
    """

    def setUp(self):
        self.prompt_manager = MagicMock()
        self.prompt_manager.active_prompt_id = None
        self.prompt_assistant_manager = MagicMock()
        self.character_manager = MagicMock()
        self.character_manager.principal_character = None
        self.workspace_manager = MagicMock()
        self.workspace_manager.opened = True

        self.page = PromptsPage(
            self.prompt_manager, self.prompt_assistant_manager, self.character_manager,
            self.workspace_manager,
        )

    def test_button_present_and_disabled_when_editor_empty(self):
        self.assertTrue(hasattr(self.page, "save_as_new_prompt_button"))
        self.assertFalse(self.page.save_as_new_prompt_button.isEnabled())

    def test_button_disabled_when_editor_whitespace_only(self):
        self.page.text_edit.setPlainText("   \n\t  ")
        self.assertFalse(self.page.save_as_new_prompt_button.isEnabled())

    def test_button_enabled_when_text_present(self):
        self.page.text_edit.setPlainText("a red fox, cinematic")
        self.assertTrue(self.page.save_as_new_prompt_button.isEnabled())

    def test_button_enabled_regardless_of_active_prompt(self):
        # Mission 035: unlike save_button (which requires an active
        # Prompt), this button only ever depends on the editor's
        # content — it is meaningful both with and without a Prompt
        # currently selected.
        self.prompt_manager.active_prompt_id = "prompt-1"
        self.page.text_edit.setPlainText("a red fox")
        self.assertTrue(self.page.save_as_new_prompt_button.isEnabled())

    def test_button_disabled_again_after_text_cleared(self):
        self.page.text_edit.setPlainText("some text")
        self.assertTrue(self.page.save_as_new_prompt_button.isEnabled())

        self.page.text_edit.setPlainText("")
        self.assertFalse(self.page.save_as_new_prompt_button.isEnabled())

    @patch("src.ui.pages.prompts_page.QInputDialog.getText")
    def test_click_creates_via_prompt_manager_with_current_text_and_selects_it(self, mock_get_text):
        mock_get_text.return_value = ("My New Prompt", True)
        self.prompt_manager.create.return_value = MagicMock(prompt_id="new-id")

        self.page.text_edit.setPlainText("a red fox, cinematic")
        self.page.save_as_new_prompt_button.click()

        self.prompt_manager.create.assert_called_once_with("My New Prompt", text="a red fox, cinematic")
        # Mission 035 verification: unlike InferencePage's
        # "Enregistrer dans Prompts" (Mission 031), PromptsPage's own
        # action must select the Prompt it just created.
        self.prompt_manager.select.assert_called_once_with("new-id")
        self.prompt_manager.update_text.assert_not_called()

    @patch("src.ui.pages.prompts_page.QInputDialog.getText")
    def test_click_with_active_prompt_never_calls_update_text_and_selects_the_new_one(self, mock_get_text):
        mock_get_text.return_value = ("Variant", True)
        self.prompt_manager.create.return_value = MagicMock(prompt_id="variant-id")
        self.prompt_manager.active_prompt_id = "prompt-1"

        self.page.text_edit.setPlainText("edited but not yet saved")
        self.page.save_as_new_prompt_button.click()

        self.prompt_manager.create.assert_called_once_with("Variant", text="edited but not yet saved")
        # Never updates whatever Prompt was already active.
        self.prompt_manager.update_text.assert_not_called()
        # Selects the newly created Prompt, not the one already active.
        self.prompt_manager.select.assert_called_once_with("variant-id")

    @patch("src.ui.pages.prompts_page.QInputDialog.getText")
    def test_cancelled_dialog_does_not_create(self, mock_get_text):
        mock_get_text.return_value = ("", False)

        self.page.text_edit.setPlainText("a red fox")
        self.page.save_as_new_prompt_button.click()

        self.prompt_manager.create.assert_not_called()
        self.prompt_manager.select.assert_not_called()

    @patch("src.ui.pages.prompts_page.QInputDialog.getText")
    def test_blank_name_does_not_create(self, mock_get_text):
        mock_get_text.return_value = ("   ", True)

        self.page.text_edit.setPlainText("a red fox")
        self.page.save_as_new_prompt_button.click()

        self.prompt_manager.create.assert_not_called()

    @patch("src.ui.pages.prompts_page.QMessageBox.warning")
    @patch("src.ui.pages.prompts_page.QInputDialog.getText")
    def test_no_principal_character_shows_warning_and_does_not_select(self, mock_get_text, mock_warning):
        # Mission 036: Workspace open (self.workspace_manager.opened is
        # True by default in setUp), zero Character — must show "Aucun
        # personnage", not "Aucun projet ouvert" (see the sibling test
        # below for the other cause of the same None).
        mock_get_text.return_value = ("My New Prompt", True)
        self.prompt_manager.create.return_value = None

        self.page.text_edit.setPlainText("a red fox")
        self.page.save_as_new_prompt_button.click()

        mock_warning.assert_called_once_with(
            self.page,
            "Aucun personnage",
            "Ce projet ne possède aucun personnage — créez-en un depuis Characters avant de créer un prompt."
        )
        self.prompt_manager.select.assert_not_called()

    @patch("src.ui.pages.prompts_page.QMessageBox.warning")
    @patch("src.ui.pages.prompts_page.QInputDialog.getText")
    def test_no_open_workspace_shows_no_project_warning_and_does_not_select(self, mock_get_text, mock_warning):
        # Mission 036: distinguishes "no Workspace open at all" from the
        # sibling test above ("Workspace open, zero Character") — both
        # make PromptManager.create() return None.
        mock_get_text.return_value = ("My New Prompt", True)
        self.prompt_manager.create.return_value = None
        self.workspace_manager.opened = False

        self.page.text_edit.setPlainText("a red fox")
        self.page.save_as_new_prompt_button.click()

        mock_warning.assert_called_once_with(
            self.page,
            "Aucun projet ouvert",
            "Ouvrez ou créez un projet avant de créer un prompt."
        )
        self.prompt_manager.select.assert_not_called()


class PromptsPageSortTest(unittest.TestCase):
    """
    Mission 051: PromptsPage.prompt_list is now sorted by name, case-
    insensitive, always active — same pattern as Mission 048. The sort
    is applied only inside _refresh_prompt_list(), never touching
    text_edit/dirty state; Character.prompts (Domain) must never be
    reordered.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "PromptSortProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        prompt_manager = PromptManager(character_manager, workspace_manager, event_bus=event_bus)
        prompts_page = PromptsPage(prompt_manager, MagicMock(), character_manager, workspace_manager)

        event_bus.subscribe(WORKSPACE_SAVED, prompts_page.update_prompts)
        event_bus.subscribe(WORKSPACE_RENAMED, prompts_page.update_prompts)
        event_bus.subscribe(CHARACTER_CREATED, prompts_page.update_prompts)

        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            event_bus.subscribe(event_name, prompts_page.reset_for_context_change)

        for event_name in (CHARACTER_SELECTED, CHARACTER_DELETED):
            event_bus.subscribe(event_name, prompts_page.reset_for_context_change)

        for event_name in PROMPT_EVENTS:
            event_bus.subscribe(event_name, prompts_page.update_prompts)

        return event_bus, workspace_manager, character_manager, prompt_manager, prompts_page

    def test_display_order_is_alphabetical_case_insensitive(self):

        _, workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)

        for name in ("Zebra", "mango", "Apple", "banana", "Cherry"):
            prompt_manager.create(name)

        displayed = [
            prompts_page.prompt_list.item(i).text()
            for i in range(prompts_page.prompt_list.count())
        ]
        self.assertEqual(displayed, ["Apple", "banana", "Cherry", "mango", "Zebra"])

    def test_domain_collection_keeps_insertion_order(self):

        _, workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)

        for name in ("Zebra", "mango", "Apple"):
            prompt_manager.create(name)

        principal = character_manager.principal_character
        self.assertEqual(
            [p.name for p in principal.prompts],
            ["Zebra", "mango", "Apple"],
        )

    def test_sort_is_stable_for_identical_names(self):

        _, workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)

        first = prompt_manager.create("Same")
        second = prompt_manager.create("Same")

        displayed_ids = [
            prompts_page.prompt_list.item(i).data(Qt.UserRole)
            for i in range(prompts_page.prompt_list.count())
        ]
        self.assertEqual(displayed_ids, [first.prompt_id, second.prompt_id])

    def test_selection_targets_correct_prompt_despite_display_reorder(self):

        _, workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)

        zebra = prompt_manager.create("Zebra", text="zebra text")
        apple = prompt_manager.create("Apple", text="apple text")

        prompt_manager.select(apple.prompt_id)

        # "Apple" now displays at position 0, ahead of "Zebra" — confirm
        # the correct prompt's text is loaded, not positional.
        self.assertEqual(prompts_page.prompt_list.item(0).text(), "Apple")
        self.assertEqual(prompts_page.text_edit.toPlainText(), "apple text")

        prompt_manager.select(zebra.prompt_id)
        self.assertEqual(prompts_page.text_edit.toPlainText(), "zebra text")

    def test_refresh_after_second_creation_resorts_entire_list(self):

        _, workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)

        prompt_manager.create("Mango")
        prompt_manager.create("Zebra")
        prompt_manager.create("Apple")

        displayed = [
            prompts_page.prompt_list.item(i).text()
            for i in range(prompts_page.prompt_list.count())
        ]
        self.assertEqual(displayed, ["Apple", "Mango", "Zebra"])

    def test_sorted_display_does_not_disturb_dirty_state_or_editor(self):
        # Mission 051 must remain a pure Presentation-order change:
        # editing text_edit for the active Prompt, then triggering a
        # non-destructive refresh (WORKSPACE_SAVED via save_text()) must
        # still preserve normal dirty-state behavior, unaffected by the
        # new sort.
        _, workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)

        prompt_manager.create("Zebra")
        apple = prompt_manager.create("Apple")
        prompt_manager.select(apple.prompt_id)

        prompts_page.text_edit.setPlainText("apple text edited")
        self.assertTrue(prompts_page._dirty)

        prompts_page.save_text()
        self.assertFalse(prompts_page._dirty)
        self.assertEqual(prompt_manager.active_prompt.text, "apple text edited")

        # The list remains sorted after the save-triggered refresh.
        displayed = [
            prompts_page.prompt_list.item(i).text()
            for i in range(prompts_page.prompt_list.count())
        ]
        self.assertEqual(displayed, ["Apple", "Zebra"])


class PromptsPageRenameTest(unittest.TestCase):
    """
    Mission 053: PromptsPage.name_edit allows renaming the active
    prompt in place (editingFinished -> PromptManager.update_name()),
    immediately, independently of text_edit's dirty-state (Mission
    038). Renaming must never change prompt_id/text, must never
    disturb an unsaved draft, and must interact correctly with Mission
    051's alphabetical sort — selection stays on the same prompt by id
    despite any display reorder the rename triggers.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "PromptRenameProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        prompt_manager = PromptManager(character_manager, workspace_manager, event_bus=event_bus)
        prompts_page = PromptsPage(prompt_manager, MagicMock(), character_manager, workspace_manager)

        event_bus.subscribe(WORKSPACE_SAVED, prompts_page.update_prompts)
        event_bus.subscribe(WORKSPACE_RENAMED, prompts_page.update_prompts)
        event_bus.subscribe(CHARACTER_CREATED, prompts_page.update_prompts)

        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            event_bus.subscribe(event_name, prompts_page.reset_for_context_change)

        for event_name in (CHARACTER_SELECTED, CHARACTER_DELETED):
            event_bus.subscribe(event_name, prompts_page.reset_for_context_change)

        for event_name in PROMPT_EVENTS:
            event_bus.subscribe(event_name, prompts_page.update_prompts)

        return event_bus, workspace_manager, character_manager, prompt_manager, prompts_page

    def test_rename_via_widget_updates_manager_display_and_preserves_text(self):

        _, workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)

        prompt = prompt_manager.create("Master", text="original text")
        prompt_manager.select(prompt.prompt_id)

        prompts_page.name_edit.setText("Master Renamed")
        prompts_page.name_edit.editingFinished.emit()

        self.assertEqual(prompt_manager.active_prompt.name, "Master Renamed")
        self.assertEqual(prompt_manager.active_prompt.prompt_id, prompt.prompt_id)
        self.assertEqual(prompt_manager.active_prompt.text, "original text")
        self.assertEqual(prompts_page.prompt_list.item(0).text(), "Master Renamed")
        self.assertEqual(prompts_page.text_edit.toPlainText(), "original text")

    def test_rename_moving_entity_to_front_keeps_correct_selection(self):

        _, workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)

        mango = prompt_manager.create("Mango")
        zebra = prompt_manager.create("Zebra", text="zebra text")
        prompt_manager.select(zebra.prompt_id)

        prompts_page.name_edit.setText("Apple")
        prompts_page.name_edit.editingFinished.emit()

        displayed = [
            prompts_page.prompt_list.item(i).text()
            for i in range(prompts_page.prompt_list.count())
        ]
        self.assertEqual(displayed, ["Apple", "Mango"])
        self.assertEqual(prompts_page.prompt_list.item(0).data(Qt.UserRole), zebra.prompt_id)
        self.assertEqual(prompt_manager.active_prompt_id, zebra.prompt_id)
        self.assertEqual(prompts_page.text_edit.toPlainText(), "zebra text")

    def test_rename_moving_entity_to_back_keeps_correct_selection(self):

        _, workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)

        apple = prompt_manager.create("Apple", text="apple text")
        mango = prompt_manager.create("Mango")
        prompt_manager.select(apple.prompt_id)

        prompts_page.name_edit.setText("Zzz")
        prompts_page.name_edit.editingFinished.emit()

        displayed = [
            prompts_page.prompt_list.item(i).text()
            for i in range(prompts_page.prompt_list.count())
        ]
        self.assertEqual(displayed, ["Mango", "Zzz"])
        self.assertEqual(prompts_page.prompt_list.item(1).data(Qt.UserRole), apple.prompt_id)
        self.assertEqual(prompt_manager.active_prompt_id, apple.prompt_id)
        self.assertEqual(prompts_page.text_edit.toPlainText(), "apple text")

    def test_rename_with_no_active_prompt_is_a_no_op(self):

        _, workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)
        prompt_manager.create("Master")

        prompts_page.name_edit.setText("Whatever")
        prompts_page.name_edit.editingFinished.emit()

        principal = character_manager.principal_character
        self.assertEqual([p.name for p in principal.prompts], ["Master"])

    def test_rename_with_unsaved_text_preserves_dirty_state_and_draft(self):
        # The scenario explicitly required by the contract: an unsaved
        # edit in text_edit must survive a rename untouched — dirty
        # stays True, the draft stays visible, and save_text() must
        # still work normally afterward.
        _, workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)

        zebra = prompt_manager.create("Zebra", text="zebra saved text")
        apple = prompt_manager.create("Apple", text="apple saved text")
        prompt_manager.select(apple.prompt_id)

        prompts_page.text_edit.setPlainText("apple text edited but not saved")
        self.assertTrue(prompts_page._dirty)

        # Rename "Apple" -> "Zzz", moving it to the back of the sorted list.
        prompts_page.name_edit.setText("Zzz")
        prompts_page.name_edit.editingFinished.emit()

        # The unsaved draft and dirty flag must be completely untouched.
        self.assertTrue(prompts_page._dirty)
        self.assertEqual(
            prompts_page.text_edit.toPlainText(), "apple text edited but not saved"
        )
        # The persisted text is still the pre-rename saved value — the
        # rename never touched text at all.
        self.assertEqual(prompt_manager.active_prompt.text, "apple saved text")
        self.assertEqual(prompt_manager.active_prompt.name, "Zzz")

        displayed = [
            prompts_page.prompt_list.item(i).text()
            for i in range(prompts_page.prompt_list.count())
        ]
        self.assertEqual(displayed, ["Zebra", "Zzz"])
        self.assertEqual(prompt_manager.active_prompt_id, apple.prompt_id)

        # save_text() still works normally afterward.
        prompts_page.save_text()
        self.assertFalse(prompts_page._dirty)
        self.assertEqual(
            prompt_manager.active_prompt.text, "apple text edited but not saved"
        )

    def test_rename_persists_after_close_reopen_via_ui(self):

        _, workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)

        prompt = prompt_manager.create("Master", text="original text")
        prompt_manager.select(prompt.prompt_id)

        prompts_page.name_edit.setText("Master Renamed")
        prompts_page.name_edit.editingFinished.emit()

        workspace_manager.close()

        _, workspace_manager_2, character_manager_2, prompt_manager_2, prompts_page_2 = self._wire()
        workspace_manager_2.open(self.folder)

        self.assertEqual(len(prompt_manager_2.prompts), 1)
        self.assertEqual(prompt_manager_2.prompts[0].prompt_id, prompt.prompt_id)
        self.assertEqual(prompt_manager_2.prompts[0].name, "Master Renamed")
        self.assertEqual(prompt_manager_2.prompts[0].text, "original text")
        self.assertEqual(prompts_page_2.prompt_list.item(0).text(), "Master Renamed")

    def test_rename_save_failure_shows_error_and_restores_widget_to_previous_name(self):

        _, workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)

        prompt = prompt_manager.create("Master", text="original text")
        prompt_manager.select(prompt.prompt_id)

        prompts_page.name_edit.setText("Master Renamed")
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.prompts_page.QMessageBox.critical") as critical_mock:
            prompts_page.name_edit.editingFinished.emit()

        self.assertTrue(critical_mock.called)
        self.assertEqual(prompt.name, "Master")
        self.assertEqual(prompts_page.name_edit.text(), "Master")
        self.assertEqual(prompts_page.prompt_list.item(0).text(), "Master")

    def test_retry_after_rename_save_failure_actually_renames(self):

        _, workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)

        prompt = prompt_manager.create("Master", text="original text")
        prompt_manager.select(prompt.prompt_id)

        prompts_page.name_edit.setText("Master Renamed")
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.prompts_page.QMessageBox.critical"):
            prompts_page.name_edit.editingFinished.emit()

        prompts_page.name_edit.setText("Master Renamed")
        prompts_page.name_edit.editingFinished.emit()

        self.assertEqual(prompt.name, "Master Renamed")
        self.assertEqual(prompts_page.prompt_list.item(0).text(), "Master Renamed")


class PromptsPageSaveTextPersistenceFailureTest(unittest.TestCase):
    """
    Mission 070: PromptsPage.save_text() ("Enregistrer le texte" button)
    -> PromptManager.update_text(). A third real call site for
    update_text(), distinct from on_prompt_selection_changed() (Prompt
    -> Prompt switch) and confirm_context_change() (M069, New/Open
    Project) — must also surface WorkspaceManagerError explicitly and
    never leave a phantom mutation behind.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "PromptSaveTextProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        prompt_manager = PromptManager(character_manager, workspace_manager, event_bus=event_bus)
        prompts_page = PromptsPage(prompt_manager, MagicMock(), character_manager, workspace_manager)

        event_bus.subscribe(WORKSPACE_SAVED, prompts_page.update_prompts)
        event_bus.subscribe(WORKSPACE_RENAMED, prompts_page.update_prompts)
        event_bus.subscribe(CHARACTER_CREATED, prompts_page.update_prompts)
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            event_bus.subscribe(event_name, prompts_page.reset_for_context_change)
        for event_name in (CHARACTER_SELECTED, CHARACTER_DELETED):
            event_bus.subscribe(event_name, prompts_page.reset_for_context_change)
        for event_name in PROMPT_EVENTS:
            event_bus.subscribe(event_name, prompts_page.update_prompts)

        return event_bus, workspace_manager, character_manager, prompt_manager, prompts_page

    def test_save_text_failure_shows_error_and_leaves_no_phantom_mutation(self):
        _, workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        prompt = prompt_manager.create("Master", text="original text")
        prompt_manager.select(prompt.prompt_id)

        prompts_page.text_edit.setPlainText("edited but not saved")
        self.assertTrue(prompts_page._dirty)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.prompts_page.QMessageBox.critical") as critical_mock:
            prompts_page.save_text()

        self.assertTrue(critical_mock.called)
        self.assertTrue(prompts_page._dirty)
        self.assertEqual(prompts_page.text_edit.toPlainText(), "edited but not saved")
        self.assertEqual(prompt.text, "original text")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        self.assertEqual(aria["prompts"][0]["text"], "original text")

    def test_retry_after_save_text_failure_actually_saves(self):
        _, workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        prompt = prompt_manager.create("Master", text="original text")
        prompt_manager.select(prompt.prompt_id)

        prompts_page.text_edit.setPlainText("edited but not saved")
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.prompts_page.QMessageBox.critical"):
            prompts_page.save_text()

        prompts_page.save_text()

        self.assertFalse(prompts_page._dirty)
        self.assertEqual(prompt.text, "edited but not saved")
        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        self.assertEqual(aria["prompts"][0]["text"], "edited but not saved")


class PromptsPageDeletePersistenceFailureTest(unittest.TestCase):
    """
    Mission 071: PromptsPage.delete_prompt() -> PromptManager.delete().
    A save() failure must surface a QMessageBox.critical() and leave the
    Prompt exactly as it was — present, selected and unmodified in
    prompt_list — since PROMPT_DELETED is never published in that case
    and the row was therefore never removed. Mirrors the established
    Manager-failure Presentation idiom already used by
    PromptsPageRenameTest/PromptsPageSaveTextPersistenceFailureTest
    (Mission 070).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "PromptDeleteFailureProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        prompt_manager = PromptManager(character_manager, workspace_manager, event_bus=event_bus)
        prompts_page = PromptsPage(prompt_manager, MagicMock(), character_manager, workspace_manager)

        event_bus.subscribe(WORKSPACE_SAVED, prompts_page.update_prompts)
        event_bus.subscribe(WORKSPACE_RENAMED, prompts_page.update_prompts)
        event_bus.subscribe(CHARACTER_CREATED, prompts_page.update_prompts)
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            event_bus.subscribe(event_name, prompts_page.reset_for_context_change)
        for event_name in (CHARACTER_SELECTED, CHARACTER_DELETED):
            event_bus.subscribe(event_name, prompts_page.reset_for_context_change)
        for event_name in PROMPT_EVENTS:
            event_bus.subscribe(event_name, prompts_page.update_prompts)

        return event_bus, workspace_manager, character_manager, prompt_manager, prompts_page

    def test_delete_failure_shows_error_and_leaves_prompt_present_and_selected(self):
        _, workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)

        prompt = prompt_manager.create("Master", text="original text")
        prompt_manager.select(prompt.prompt_id)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.prompts_page.QMessageBox.critical") as critical_mock:
            prompts_page.delete_prompt()

        self.assertTrue(critical_mock.called)
        self.assertEqual(prompt_manager.prompts, [prompt])
        self.assertEqual(prompt_manager.active_prompt_id, prompt.prompt_id)
        self.assertEqual(prompts_page.prompt_list.count(), 1)
        self.assertEqual(prompts_page.prompt_list.item(0).data(Qt.UserRole), prompt.prompt_id)
        self.assertTrue(prompts_page.delete_button.isEnabled())

    def test_delete_failure_leaves_project_json_unchanged(self):
        _, workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)

        prompt_manager.create("Master", text="original text")
        prompt_manager.select(prompt_manager.prompts[0].prompt_id)

        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.prompts_page.QMessageBox.critical"):
            prompts_page.delete_prompt()

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_after_delete_failure_actually_deletes(self):
        _, workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)

        prompt = prompt_manager.create("Master", text="original text")
        prompt_manager.select(prompt.prompt_id)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.prompts_page.QMessageBox.critical"):
            prompts_page.delete_prompt()

        prompts_page.delete_prompt()

        self.assertEqual(prompt_manager.prompts, [])
        self.assertIsNone(prompt_manager.active_prompt_id)
        self.assertEqual(prompts_page.prompt_list.count(), 0)
        self.assertFalse(prompts_page.delete_button.isEnabled())
        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertEqual(on_disk["characters"][0]["prompts"], [])

    def test_delete_failure_with_unsaved_draft_preserves_dirty_state_and_draft(self):
        # Discard is chosen in delete_prompt()'s own inline dirty
        # confirmation (Mission 038 — a plain Discard/Cancel QMessageBox
        # built directly in this method, distinct from the shared
        # Save/Discard/Cancel _confirm_discard_before_switch() used by
        # on_prompt_selection_changed()/confirm_context_change()),
        # authorizing the deletion attempt itself — which then fails.
        # The unsaved draft text and dirty flag must survive, since
        # update_prompts() (which would normally clear them) is never
        # triggered by a failed delete().
        _, workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)

        prompt = prompt_manager.create("Master", text="original text")
        prompt_manager.select(prompt.prompt_id)

        prompts_page.text_edit.setPlainText("edited but not saved")
        self.assertTrue(prompts_page._dirty)

        with patch("src.ui.pages.prompts_page.QMessageBox") as mock_message_box, \
                patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            mock_message_box.return_value.exec.return_value = mock_message_box.Discard
            prompts_page.delete_prompt()

        self.assertTrue(mock_message_box.critical.called)
        self.assertTrue(prompts_page._dirty)
        self.assertEqual(prompts_page.text_edit.toPlainText(), "edited but not saved")
        self.assertEqual(prompt_manager.prompts, [prompt])
        self.assertEqual(prompt_manager.active_prompt_id, prompt.prompt_id)


class PromptsPageDeleteButtonStateTest(unittest.TestCase):
    """
    Mission 063: "Supprimer" must always reflect whether there is
    currently a valid selection to act on, mirroring ImagesPage's
    established delete_button.setEnabled() pattern (Mission 046) —
    never a silent no-op behind an always-clickable button. Unlike the
    other 5 CRUD pages, PromptsPage's selection can also be reverted by
    the Mission 038 dirty-draft guard (on_prompt_selection_changed's
    Cancel branch) — the button must follow whichever selection is
    actually in effect afterward, not the switch attempt itself.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "PromptButtonStateProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        prompt_manager = PromptManager(character_manager, workspace_manager, event_bus=event_bus)
        prompts_page = PromptsPage(prompt_manager, MagicMock(), character_manager, workspace_manager)

        event_bus.subscribe(WORKSPACE_SAVED, prompts_page.update_prompts)
        event_bus.subscribe(WORKSPACE_RENAMED, prompts_page.update_prompts)
        event_bus.subscribe(CHARACTER_CREATED, prompts_page.update_prompts)

        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            event_bus.subscribe(event_name, prompts_page.reset_for_context_change)

        for event_name in (CHARACTER_SELECTED, CHARACTER_DELETED):
            event_bus.subscribe(event_name, prompts_page.reset_for_context_change)

        for event_name in PROMPT_EVENTS:
            event_bus.subscribe(event_name, prompts_page.update_prompts)

        return workspace_manager, character_manager, prompt_manager, prompts_page

    def test_disabled_before_any_workspace(self):
        _, _, _, prompts_page = self._wire()
        self.assertFalse(prompts_page.delete_button.isEnabled())

    def test_disabled_with_no_selection_then_enabled_on_select(self):
        workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)

        self.assertFalse(prompts_page.delete_button.isEnabled())

        prompt = prompt_manager.create("Master")
        prompt_manager.select(prompt.prompt_id)

        self.assertTrue(prompts_page.delete_button.isEnabled())

    def test_deselecting_disables_delete_button(self):
        workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)
        prompt = prompt_manager.create("Master")
        prompt_manager.select(prompt.prompt_id)
        self.assertTrue(prompts_page.delete_button.isEnabled())

        prompts_page.prompt_list.setCurrentItem(None)

        self.assertFalse(prompts_page.delete_button.isEnabled())

    def test_delete_button_stays_consistent_after_list_rebuild(self):
        workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)
        prompt_a = prompt_manager.create("Master")
        prompt_manager.select(prompt_a.prompt_id)
        self.assertTrue(prompts_page.delete_button.isEnabled())

        # PROMPT_CREATED triggers update_prompts() -> _refresh_prompt_list()
        # rebuilds the list (a non-destructive refresh from text_edit's
        # point of view, since active_prompt_id is unchanged) — the
        # button must stay correct regardless.
        prompt_manager.create("Secondary")

        self.assertTrue(prompts_page.delete_button.isEnabled())
        self.assertEqual(
            prompts_page.prompt_list.currentItem().data(Qt.UserRole), prompt_a.prompt_id
        )

    def test_disabled_after_workspace_closed(self):
        workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)
        prompt = prompt_manager.create("Master")
        prompt_manager.select(prompt.prompt_id)
        self.assertTrue(prompts_page.delete_button.isEnabled())

        workspace_manager.close()

        self.assertFalse(prompts_page.delete_button.isEnabled())

    def test_disabled_after_deleting_the_selected_prompt(self):
        workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)
        prompt = prompt_manager.create("Master")
        prompt_manager.select(prompt.prompt_id)
        self.assertTrue(prompts_page.delete_button.isEnabled())

        # PROMPT_DELETED triggers update_prompts() -> the button must be
        # recomputed from the resulting (now empty) selection. Not
        # dirty here, so delete_prompt() shows no confirmation at all.
        prompts_page.delete_prompt()

        self.assertFalse(prompts_page.delete_button.isEnabled())

    def test_switch_cancelled_while_dirty_keeps_button_enabled_on_reverted_selection(self):
        workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)
        first = prompt_manager.create("First", text="first text")
        prompt_manager.create("Second")
        prompt_manager.select(first.prompt_id)
        self.assertTrue(prompts_page.delete_button.isEnabled())

        prompts_page.text_edit.setPlainText("unsaved edit")
        self.assertTrue(prompts_page._dirty)

        second_item = prompts_page.prompt_list.item(1)
        with patch.object(
            prompts_page, "_confirm_discard_before_switch", return_value=QMessageBox.Cancel
        ):
            prompts_page.prompt_list.setCurrentItem(second_item)

        # Reverted to `first` (still selected) — the button must follow
        # that reverted selection, not the cancelled switch attempt.
        self.assertEqual(prompt_manager.active_prompt_id, first.prompt_id)
        self.assertTrue(prompts_page.delete_button.isEnabled())

    def test_switch_cancelled_while_dirty_with_no_prior_selection_disables_button(self):
        workspace_manager, character_manager, prompt_manager, prompts_page = self._wire()
        workspace_manager.create(self.folder)
        prompt_manager.create("Only")

        # A draft typed with nothing selected yet — text_edit is never
        # disabled (see PromptsPage docstring), so this is reachable.
        prompts_page.text_edit.setPlainText("unsaved draft")
        self.assertTrue(prompts_page._dirty)
        self.assertFalse(prompts_page.delete_button.isEnabled())

        only_item = prompts_page.prompt_list.item(0)
        with patch.object(
            prompts_page, "_confirm_discard_before_switch", return_value=QMessageBox.Cancel
        ):
            prompts_page.prompt_list.setCurrentItem(only_item)

        # Reverted to no selection (`previous` was None) — select() is
        # never called, and the button must reflect that.
        self.assertIsNone(prompt_manager.active_prompt_id)
        self.assertFalse(prompts_page.delete_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
