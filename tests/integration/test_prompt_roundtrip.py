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
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from src.core.event_bus import EventBus
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
        prompts_page = PromptsPage(prompt_manager)

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

        restored_character = character_manager_2.characters[0]
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
        character_manager_2.select(character_manager_2.characters[0].character_id)
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
        # characters_page, prompts_page) + CharacterManager's own internal
        # reset subscription + PromptManager's own internal reset
        # subscription = 6, on EACH bus independently.
        self.assertEqual(len(event_bus_1._subscribers[WORKSPACE_CREATED]), 6)
        self.assertEqual(len(event_bus_2._subscribers[WORKSPACE_CREATED]), 6)
        self.assertTrue(
            set(event_bus_1._subscribers[WORKSPACE_CREATED]).isdisjoint(
                event_bus_2._subscribers[WORKSPACE_CREATED]
            )
        )

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


if __name__ == "__main__":
    unittest.main()
