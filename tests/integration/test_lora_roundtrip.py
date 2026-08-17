"""
Integration coverage for the LoRA lifecycle, exercising LoRAManager,
Character.loras, Workspace persistence, EventBus and the real
DashboardPage/CharactersPage/ImagesPage/LoRAPage widgets together —
the same wiring MainWindow uses.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

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
from src.managers.lora_manager import (
    LoRAManager,
    LORA_CREATED,
    LORA_SELECTED,
    LORA_DELETED,
)
from src.ui.pages.dashboard_page import DashboardPage
from src.ui.pages.characters_page import CharactersPage
from src.ui.pages.images_page import ImagesPage
from src.ui.pages.lora_page import LoRAPage

WORKSPACE_EVENTS = (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_SAVED, WORKSPACE_CLOSED)
CHARACTER_EVENTS = (CHARACTER_CREATED, CHARACTER_SELECTED, CHARACTER_DELETED)
LORA_EVENTS = (LORA_CREATED, LORA_SELECTED, LORA_DELETED)

_app = QApplication.instance() or QApplication([])


class LoRARoundTripTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "LoRAProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        lora_manager = LoRAManager(character_manager, workspace_manager, event_bus=event_bus)

        dashboard = DashboardPage()
        characters_page = CharactersPage(character_manager)
        images = ImagesPage(workspace_manager)
        lora_page = LoRAPage(lora_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, dashboard.update_project)
            event_bus.subscribe(event_name, images.update_images)
            event_bus.subscribe(event_name, characters_page.update_characters)
            event_bus.subscribe(event_name, lora_page.update_loras)

        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, characters_page.update_characters)
            event_bus.subscribe(event_name, lora_page.update_loras)

        for event_name in LORA_EVENTS:
            event_bus.subscribe(event_name, lora_page.update_loras)

        return (
            event_bus, workspace_manager, character_manager, lora_manager,
            dashboard, characters_page, images, lora_page,
        )

    def test_full_create_select_import_save_close_reopen_cycle(self):

        (event_bus, workspace_manager, character_manager, lora_manager,
         dashboard, characters_page, images, lora_page) = self._wire()

        workspace_manager.create(self.folder)
        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)

        style = lora_manager.create("StyleA")
        lora_manager.select(style.lora_id)
        added = lora_manager.add_files(["ref1.safetensors", "ref2.safetensors"])
        self.assertEqual(added, 2)

        self.assertEqual(
            [lora_page.files_list.item(i).text()
             for i in range(lora_page.files_list.count())],
            ["ref1.safetensors", "ref2.safetensors"],
        )

        workspace_manager.save()
        workspace_manager.close()

        self.assertIsNone(lora_manager.active_lora_id)
        self.assertEqual(lora_page.lora_list.count(), 0)

        # Reopen with a second _wire() call — fresh instances, simulating
        # a real application restart rather than reusing in-memory state.
        (event_bus_2, workspace_manager_2, character_manager_2, lora_manager_2,
         dashboard_2, characters_page_2, images_2, lora_page_2) = self._wire()

        workspace_manager_2.open(self.folder)

        # Runtime-only per Mission 002/003/004 decisions: neither
        # active_character_id nor active_lora_id survive a restart.
        # Checked BEFORE selecting anything below — selecting now would
        # trivially make this assertion pass for the wrong reason.
        self.assertIsNone(character_manager_2.active_character_id)
        self.assertIsNone(lora_manager_2.active_lora_id)

        # Mission 026: the reopened workspace also holds its auto-created
        # principal Character — retrieve "Aria" explicitly by name (the
        # Character these LoRAs actually belong to), not by list index.
        restored_character = next(
            c for c in character_manager_2.characters if c.name == "Aria"
        )
        character_manager_2.select(restored_character.character_id)

        self.assertEqual(len(lora_manager_2.loras), 1)
        restored_lora = lora_manager_2.loras[0]
        self.assertEqual(restored_lora.name, "StyleA")
        self.assertEqual(restored_lora.files, ["ref1.safetensors", "ref2.safetensors"])

    def test_add_files_preserves_order_and_dedups(self):

        _, workspace_manager, character_manager, lora_manager = self._wire()[:4]
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)

        added1 = lora_manager.add_files(["a.safetensors", "b.safetensors", "c.safetensors"])
        self.assertEqual(added1, 3)
        self.assertEqual(lora_manager.active_lora.files, ["a.safetensors", "b.safetensors", "c.safetensors"])

        # Dedup across separate calls, arrival order preserved for new ones.
        added2 = lora_manager.add_files(["b.safetensors", "d.safetensors", "a.safetensors", "e.safetensors"])
        self.assertEqual(added2, 2)
        self.assertEqual(
            lora_manager.active_lora.files,
            ["a.safetensors", "b.safetensors", "c.safetensors", "d.safetensors", "e.safetensors"],
        )

        # Dedup within a single call, first-seen order preserved.
        lora2 = lora_manager.create("StyleB")
        lora_manager.select(lora2.lora_id)
        added3 = lora_manager.add_files(["x.bin", "y.bin", "x.bin", "z.bin", "y.bin"])
        self.assertEqual(added3, 3)
        self.assertEqual(lora_manager.active_lora.files, ["x.bin", "y.bin", "z.bin"])

    def test_delete_active_lora_resets_selection_and_persists(self):

        _, workspace_manager, character_manager, lora_manager = self._wire()[:4]
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        keep = lora_manager.create("Keep")
        drop = lora_manager.create("Drop")
        lora_manager.select(drop.lora_id)

        result = lora_manager.delete(drop.lora_id)
        self.assertTrue(result)
        self.assertIsNone(lora_manager.active_lora_id)
        self.assertIsNone(lora_manager.active_lora)
        self.assertEqual([l.name for l in lora_manager.loras], ["Keep"])

        # Persists: reopening shows only the surviving LoRA.
        _, workspace_manager_2, character_manager_2, lora_manager_2 = self._wire()[:4]
        workspace_manager_2.open(self.folder)
        # Mission 026: retrieve "Aria" explicitly by name rather than by
        # list index (the reopened workspace also holds its auto-created
        # principal Character).
        restored_character = next(
            c for c in character_manager_2.characters if c.name == "Aria"
        )
        character_manager_2.select(restored_character.character_id)
        self.assertEqual([l.name for l in lora_manager_2.loras], ["Keep"])

    def test_lora_manager_context_reset_on_character_and_workspace_change(self):

        _, workspace_manager, character_manager, lora_manager = self._wire()[:4]
        workspace_manager.create(self.folder)

        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        self.assertEqual(lora_manager.active_lora_id, lora.lora_id)

        # Switching the active character must reset active_lora_id — the
        # new character's LoRA list is unrelated.
        kai = character_manager.create("Kai")
        character_manager.select(kai.character_id)
        self.assertIsNone(lora_manager.active_lora_id)

        # Re-select Aria and her LoRA, then confirm a workspace close also
        # resets it.
        character_manager.select(aria.character_id)
        lora_manager.select(lora.lora_id)
        self.assertIsNotNone(lora_manager.active_lora_id)

        workspace_manager.close()
        self.assertIsNone(lora_manager.active_lora_id)

    def test_lora_page_rebuilds_on_relevant_events(self):

        (_, workspace_manager, character_manager, lora_manager,
         _dashboard, _characters_page, _images, lora_page) = self._wire()

        workspace_manager.create(self.folder)
        self.assertEqual(lora_page.lora_list.count(), 0)

        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        lora = lora_manager.create("StyleA")
        self.assertEqual(lora_page.lora_list.count(), 1)

        lora_manager.select(lora.lora_id)
        lora_manager.add_files(["a.safetensors"])
        # add_files() only publishes workspace.saved — this is what
        # LoRAPage's subscription to it must catch.
        self.assertEqual(lora_page.files_list.count(), 1)

        workspace_manager.close()
        self.assertEqual(lora_page.lora_list.count(), 0)
        self.assertEqual(lora_page.files_list.count(), 0)

    def test_no_duplicate_subscriptions_between_wire_calls(self):

        wired_1 = self._wire()
        wired_2 = self._wire()

        for obj_1, obj_2 in zip(wired_1, wired_2):
            self.assertIsNot(obj_1, obj_2)

        event_bus_1, event_bus_2 = wired_1[0], wired_2[0]

        # 4 subscribers registered directly by _wire() (dashboard, images,
        # characters_page, lora_page) + CharacterManager's two own
        # internal subscriptions (active_character_id reset, and
        # Mission 026's principal-Character auto-creation) + LoRAManager's
        # own internal reset subscription = 7, on EACH bus independently.
        self.assertEqual(len(event_bus_1._subscribers[WORKSPACE_CREATED]), 7)
        self.assertEqual(len(event_bus_2._subscribers[WORKSPACE_CREATED]), 7)
        self.assertTrue(
            set(event_bus_1._subscribers[WORKSPACE_CREATED]).isdisjoint(
                event_bus_2._subscribers[WORKSPACE_CREATED]
            )
        )

    def test_dashboard_and_images_unaffected_by_lora_events(self):

        (_, workspace_manager, character_manager, lora_manager,
         dashboard, _characters_page, images, _lora_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        before_dashboard = dashboard.projectCard.value.text()
        before_images_count = images.list_widget.count()

        lora_manager.create("StyleA")

        self.assertEqual(dashboard.projectCard.value.text(), before_dashboard)
        self.assertEqual(images.list_widget.count(), before_images_count)


if __name__ == "__main__":
    unittest.main()
