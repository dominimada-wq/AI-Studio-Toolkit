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
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QListWidget

from src.core.event_bus import EventBus
from src.infrastructure.storage.workspace_storage import WorkspaceStorageError
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
from src.ui.pages.lora_page import LoRAPage, NO_THUMBNAIL_MESSAGE, UNAVAILABLE_MESSAGE

WORKSPACE_EVENTS = (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_SAVED, WORKSPACE_CLOSED)
CHARACTER_EVENTS = (CHARACTER_CREATED, CHARACTER_SELECTED, CHARACTER_DELETED)
LORA_EVENTS = (LORA_CREATED, LORA_SELECTED, LORA_DELETED)

_app = QApplication.instance() or QApplication([])


def _make_png(path: str, width: int = 4, height: int = 4) -> None:
    pixmap = QPixmap(width, height)
    pixmap.fill()
    assert pixmap.save(path, "PNG")


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
        characters_page = CharactersPage(character_manager, workspace_manager)
        images = ImagesPage(workspace_manager)
        lora_page = LoRAPage(lora_manager, workspace_manager)

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

    def test_metadata_fiche_disabled_without_active_lora(self):

        (_, workspace_manager, character_manager, lora_manager,
         _dashboard, _characters_page, _images, lora_page) = self._wire()

        workspace_manager.create(self.folder)
        character_manager.create("Aria")

        self.assertEqual(lora_page.engine_edit.text(), "")
        self.assertEqual(lora_page.architecture_edit.text(), "")
        self.assertEqual(lora_page.trigger_word_edit.text(), "")
        self.assertEqual(lora_page.version_edit.text(), "")
        self.assertEqual(lora_page.thumbnail_label.text(), NO_THUMBNAIL_MESSAGE)
        self.assertFalse(lora_page.choose_thumbnail_button.isEnabled())
        self.assertFalse(lora_page.save_metadata_button.isEnabled())

    def test_metadata_fiche_populated_on_selection_and_switch(self):

        (_, workspace_manager, character_manager, lora_manager,
         _dashboard, _characters_page, _images, lora_page) = self._wire()

        workspace_manager.create(self.folder)
        character_manager.create("Aria")

        style_a = lora_manager.create("StyleA")
        lora_manager.update(
            style_a.lora_id,
            engine="ComfyUI",
            architecture="SDXL",
            trigger_word="stylea_trigger",
            version="1.0",
        )
        style_b = lora_manager.create("StyleB")
        lora_manager.update(style_b.lora_id, engine="Fooocus")

        lora_manager.select(style_a.lora_id)
        self.assertTrue(lora_page.choose_thumbnail_button.isEnabled())
        self.assertTrue(lora_page.save_metadata_button.isEnabled())
        self.assertEqual(lora_page.engine_edit.text(), "ComfyUI")
        self.assertEqual(lora_page.architecture_edit.text(), "SDXL")
        self.assertEqual(lora_page.trigger_word_edit.text(), "stylea_trigger")
        self.assertEqual(lora_page.version_edit.text(), "1.0")

        lora_manager.select(style_b.lora_id)
        self.assertEqual(lora_page.engine_edit.text(), "Fooocus")
        self.assertEqual(lora_page.architecture_edit.text(), "")
        self.assertEqual(lora_page.trigger_word_edit.text(), "")
        self.assertEqual(lora_page.version_edit.text(), "")

    def test_save_metadata_button_persists_the_four_fields(self):

        (_, workspace_manager, character_manager, lora_manager,
         _dashboard, _characters_page, _images, lora_page) = self._wire()

        workspace_manager.create(self.folder)
        character_manager.create("Aria")
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)

        lora_page.engine_edit.setText("ComfyUI")
        lora_page.architecture_edit.setText("SDXL")
        lora_page.trigger_word_edit.setText("mytrigger")
        lora_page.version_edit.setText("2.1")

        lora_page.save_metadata()

        self.assertEqual(lora_manager.active_lora.engine, "ComfyUI")
        self.assertEqual(lora_manager.active_lora.architecture, "SDXL")
        self.assertEqual(lora_manager.active_lora.trigger_word, "mytrigger")
        self.assertEqual(lora_manager.active_lora.version, "2.1")

    def test_choose_thumbnail_copies_file_and_updates_preview(self):

        (_, workspace_manager, character_manager, lora_manager,
         _dashboard, _characters_page, _images, lora_page) = self._wire()

        workspace_manager.create(self.folder)
        character_manager.create("Aria")
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)

        source_path = str(Path(self.tmp_dir) / "external_thumb.png")
        _make_png(source_path)

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileName",
            return_value=(source_path, ""),
        ):
            lora_page.choose_thumbnail()

        expected_folder = self.folder / "models" / "loras" / lora.lora_id
        self.assertTrue(expected_folder.is_dir())
        self.assertEqual(lora_manager.active_lora.thumbnail, str(expected_folder / "external_thumb.png"))
        self.assertTrue(Path(source_path).exists())
        self.assertFalse(lora_page.thumbnail_label.pixmap().isNull())

    def test_thumbnail_preview_shows_fallback_for_missing_file(self):

        (_, workspace_manager, character_manager, lora_manager,
         _dashboard, _characters_page, _images, lora_page) = self._wire()

        workspace_manager.create(self.folder)
        character_manager.create("Aria")
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)

        lora_manager.active_lora.thumbnail = str(Path(self.tmp_dir) / "does_not_exist.png")
        lora_page.update_loras()

        self.assertEqual(lora_page.thumbnail_label.text(), UNAVAILABLE_MESSAGE)

    def test_choose_thumbnail_failure_keeps_previous_value_and_warns(self):

        (_, workspace_manager, character_manager, lora_manager,
         _dashboard, _characters_page, _images, lora_page) = self._wire()

        workspace_manager.create(self.folder)
        character_manager.create("Aria")
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)

        good_source = str(Path(self.tmp_dir) / "good.png")
        _make_png(good_source)
        lora_manager.set_thumbnail(lora.lora_id, good_source)
        previous_thumbnail = lora_manager.active_lora.thumbnail

        missing_source = str(Path(self.tmp_dir) / "does_not_exist_source.png")

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileName",
            return_value=(missing_source, ""),
        ), patch("src.ui.pages.lora_page.QMessageBox.warning") as mock_warning:
            lora_page.choose_thumbnail()
            mock_warning.assert_called_once()

        self.assertEqual(lora_manager.active_lora.thumbnail, previous_thumbnail)

    # --- Mission 050: "Retirer les fichiers sélectionnés" ---

    def test_files_list_uses_extended_selection(self):

        (_, _workspace_manager, _character_manager, _lora_manager,
         _dashboard, _characters_page, _images, lora_page) = self._wire()

        self.assertEqual(lora_page.files_list.selectionMode(), QListWidget.ExtendedSelection)

    def test_remove_files_button_disabled_without_selection(self):

        (_, workspace_manager, character_manager, lora_manager,
         _dashboard, _characters_page, _images, lora_page) = self._wire()

        workspace_manager.create(self.folder)
        character_manager.create("Aria")
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        lora_manager.add_files(["a.safetensors"])

        self.assertFalse(lora_page.remove_files_button.isEnabled())

    def test_remove_files_button_enabled_with_selection(self):

        (_, workspace_manager, character_manager, lora_manager,
         _dashboard, _characters_page, _images, lora_page) = self._wire()

        workspace_manager.create(self.folder)
        character_manager.create("Aria")
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        lora_manager.add_files(["a.safetensors"])

        lora_page.files_list.item(0).setSelected(True)

        self.assertTrue(lora_page.remove_files_button.isEnabled())

    def test_remove_files_button_enabled_with_multiple_selection(self):

        (_, workspace_manager, character_manager, lora_manager,
         _dashboard, _characters_page, _images, lora_page) = self._wire()

        workspace_manager.create(self.folder)
        character_manager.create("Aria")
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        lora_manager.add_files(["a.safetensors", "b.safetensors"])

        lora_page.files_list.item(0).setSelected(True)
        lora_page.files_list.item(1).setSelected(True)

        self.assertTrue(lora_page.remove_files_button.isEnabled())

    def test_remove_selected_files_removes_from_active_lora(self):

        (_, workspace_manager, character_manager, lora_manager,
         _dashboard, _characters_page, _images, lora_page) = self._wire()

        workspace_manager.create(self.folder)
        character_manager.create("Aria")
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        lora_manager.add_files(["a.safetensors", "b.safetensors"])

        lora_page.files_list.item(0).setSelected(True)
        lora_page.remove_selected_files()

        self.assertEqual(lora_manager.active_lora.files, ["b.safetensors"])
        self.assertEqual(
            [lora_page.files_list.item(i).text() for i in range(lora_page.files_list.count())],
            ["b.safetensors"],
        )

    def test_remove_selected_files_removes_multiple_in_one_operation(self):

        (_, workspace_manager, character_manager, lora_manager,
         _dashboard, _characters_page, _images, lora_page) = self._wire()

        workspace_manager.create(self.folder)
        character_manager.create("Aria")
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        lora_manager.add_files(["a.safetensors", "b.safetensors", "c.safetensors"])

        lora_page.files_list.item(0).setSelected(True)
        lora_page.files_list.item(2).setSelected(True)
        lora_page.remove_selected_files()

        self.assertEqual(lora_manager.active_lora.files, ["b.safetensors"])

    def test_remove_selected_files_with_no_selection_is_a_noop(self):

        (_, workspace_manager, character_manager, lora_manager,
         _dashboard, _characters_page, _images, lora_page) = self._wire()

        workspace_manager.create(self.folder)
        character_manager.create("Aria")
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        lora_manager.add_files(["a.safetensors"])

        lora_page.remove_selected_files()

        self.assertEqual(lora_manager.active_lora.files, ["a.safetensors"])

    def test_files_list_empty_after_removing_last_entry(self):

        (_, workspace_manager, character_manager, lora_manager,
         _dashboard, _characters_page, _images, lora_page) = self._wire()

        workspace_manager.create(self.folder)
        character_manager.create("Aria")
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        lora_manager.add_files(["a.safetensors"])

        lora_page.files_list.item(0).setSelected(True)
        lora_page.remove_selected_files()

        self.assertEqual(lora_page.files_list.count(), 0)
        self.assertFalse(lora_page.remove_files_button.isEnabled())
        self.assertEqual(lora_manager.active_lora.files, [])

    def test_switching_active_lora_updates_files_list_and_button_state(self):

        (_, workspace_manager, character_manager, lora_manager,
         _dashboard, _characters_page, _images, lora_page) = self._wire()

        workspace_manager.create(self.folder)
        character_manager.create("Aria")
        style_a = lora_manager.create("StyleA")
        lora_manager.select(style_a.lora_id)
        lora_manager.add_files(["a.safetensors"])
        style_b = lora_manager.create("StyleB")

        lora_manager.select(style_b.lora_id)

        self.assertEqual(lora_page.files_list.count(), 0)
        self.assertFalse(lora_page.remove_files_button.isEnabled())

    def test_remove_selected_files_leaves_metadata_and_thumbnail_intact(self):

        (_, workspace_manager, character_manager, lora_manager,
         _dashboard, _characters_page, _images, lora_page) = self._wire()

        workspace_manager.create(self.folder)
        character_manager.create("Aria")
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        lora_manager.add_files(["a.safetensors", "b.safetensors"])
        lora_manager.update(lora.lora_id, engine="ComfyUI", trigger_word="mytrigger")
        thumb_source = str(Path(self.tmp_dir) / "thumb.png")
        _make_png(thumb_source)
        thumbnail = lora_manager.set_thumbnail(lora.lora_id, thumb_source)

        lora_page.files_list.item(0).setSelected(True)
        lora_page.remove_selected_files()

        self.assertEqual(lora_page.engine_edit.text(), "ComfyUI")
        self.assertEqual(lora_page.trigger_word_edit.text(), "mytrigger")
        self.assertEqual(lora_manager.active_lora.thumbnail, thumbnail)
        self.assertFalse(lora_page.thumbnail_label.pixmap().isNull())


class LoRAManagerMetadataTest(unittest.TestCase):
    """
    Mission 047: LoRAManager.update() (text metadata, idempotent, same
    contract as CharacterManager.update()) and LoRAManager.set_thumbnail()
    (real file I/O, copies an external source into
    <workspace_root>/models/loras/<lora_id>/ via
    WorkspaceStorage.copy_into_workspace() — the same primitive already
    reused by add_images()/add_files(), never touching LoRA.files).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        lora_manager = LoRAManager(character_manager, workspace_manager, event_bus=event_bus)
        return workspace_manager, character_manager, lora_manager

    def _create_lora(self):
        workspace_manager, character_manager, lora_manager = self._wire()
        workspace_manager.create(self.folder)
        character_manager.create("Aria")
        lora = lora_manager.create("StyleA")
        return workspace_manager, character_manager, lora_manager, lora

    def test_update_mutates_changed_fields_and_persists(self):
        workspace_manager, _, lora_manager, lora = self._create_lora()

        result = lora_manager.update(
            lora.lora_id,
            engine="ComfyUI",
            architecture="SDXL",
            trigger_word="mytrigger",
            version="1.0",
        )

        self.assertTrue(result)
        self.assertEqual(lora.engine, "ComfyUI")
        self.assertEqual(lora.architecture, "SDXL")
        self.assertEqual(lora.trigger_word, "mytrigger")
        self.assertEqual(lora.version, "1.0")

    def test_update_is_idempotent_when_values_unchanged(self):
        _, _, lora_manager, lora = self._create_lora()

        lora_manager.update(lora.lora_id, engine="ComfyUI")

        self.assertFalse(lora_manager.update(lora.lora_id, engine="ComfyUI"))

    def test_update_none_leaves_field_untouched(self):
        _, _, lora_manager, lora = self._create_lora()

        lora_manager.update(lora.lora_id, engine="ComfyUI", version="1.0")
        result = lora_manager.update(lora.lora_id, engine="ComfyUI2", version=None)

        self.assertTrue(result)
        self.assertEqual(lora.engine, "ComfyUI2")
        self.assertEqual(lora.version, "1.0")

    def test_update_empty_string_is_a_legitimate_value(self):
        _, _, lora_manager, lora = self._create_lora()

        lora_manager.update(lora.lora_id, engine="ComfyUI")
        result = lora_manager.update(lora.lora_id, engine="")

        self.assertTrue(result)
        self.assertEqual(lora.engine, "")

    def test_update_unknown_lora_returns_false(self):
        _, _, lora_manager, _ = self._create_lora()

        self.assertFalse(lora_manager.update("does-not-exist", engine="ComfyUI"))

    def test_update_persists_after_close_and_reopen(self):
        workspace_manager, _, lora_manager, lora = self._create_lora()
        lora_manager.update(lora.lora_id, engine="ComfyUI", trigger_word="mytrigger")
        workspace_manager.close()

        workspace_manager_2, character_manager_2, lora_manager_2 = self._wire()
        workspace_manager_2.open(self.folder)
        restored = next(l for l in lora_manager_2.loras if l.name == "StyleA")

        self.assertEqual(restored.engine, "ComfyUI")
        self.assertEqual(restored.trigger_word, "mytrigger")

    def test_set_thumbnail_copies_external_file_into_workspace(self):
        workspace_manager, _, lora_manager, lora = self._create_lora()

        source = str(Path(self.tmp_dir) / "external.png")
        _make_png(source)

        result = lora_manager.set_thumbnail(lora.lora_id, source)

        expected_folder = self.folder / "models" / "loras" / lora.lora_id
        self.assertEqual(result, str(expected_folder / "external.png"))
        self.assertEqual(lora.thumbnail, result)
        self.assertTrue((expected_folder / "external.png").exists())
        self.assertTrue(Path(source).exists())

    def test_set_thumbnail_reuses_source_already_internal(self):
        workspace_manager, _, lora_manager, lora = self._create_lora()

        source = str(Path(self.tmp_dir) / "external.png")
        _make_png(source)
        first = lora_manager.set_thumbnail(lora.lora_id, source)

        second = lora_manager.set_thumbnail(lora.lora_id, first)

        self.assertEqual(second, first)

    def test_set_thumbnail_leaves_lora_files_untouched(self):
        workspace_manager, _, lora_manager, lora = self._create_lora()
        lora_manager.select(lora.lora_id)
        lora_manager.add_files(["external_ref.safetensors"])

        source = str(Path(self.tmp_dir) / "external.png")
        _make_png(source)
        lora_manager.set_thumbnail(lora.lora_id, source)

        self.assertEqual(lora.files, ["external_ref.safetensors"])

    def test_set_thumbnail_failure_leaves_previous_value_untouched(self):
        workspace_manager, _, lora_manager, lora = self._create_lora()

        good_source = str(Path(self.tmp_dir) / "good.png")
        _make_png(good_source)
        lora_manager.set_thumbnail(lora.lora_id, good_source)
        previous = lora.thumbnail

        with patch(
            "src.managers.lora_manager.WorkspaceStorage.copy_into_workspace",
            side_effect=WorkspaceStorageError("boom"),
        ):
            result = lora_manager.set_thumbnail(lora.lora_id, "irrelevant.png")

        self.assertIsNone(result)
        self.assertEqual(lora.thumbnail, previous)

    def test_set_thumbnail_unknown_lora_returns_none(self):
        workspace_manager, _, lora_manager, _ = self._create_lora()

        source = str(Path(self.tmp_dir) / "external.png")
        _make_png(source)

        self.assertIsNone(lora_manager.set_thumbnail("does-not-exist", source))

    def test_set_thumbnail_persists_after_close_and_reopen(self):
        workspace_manager, _, lora_manager, lora = self._create_lora()

        source = str(Path(self.tmp_dir) / "external.png")
        _make_png(source)
        result = lora_manager.set_thumbnail(lora.lora_id, source)

        workspace_manager.close()

        workspace_manager_2, character_manager_2, lora_manager_2 = self._wire()
        workspace_manager_2.open(self.folder)
        restored = next(l for l in lora_manager_2.loras if l.name == "StyleA")

        self.assertEqual(restored.thumbnail, result)
        self.assertTrue(Path(restored.thumbnail).exists())

    def test_set_thumbnail_replacement_does_not_delete_previous_file(self):
        workspace_manager, _, lora_manager, lora = self._create_lora()

        first_source = str(Path(self.tmp_dir) / "first.png")
        _make_png(first_source)
        first_result = lora_manager.set_thumbnail(lora.lora_id, first_source)

        second_source = str(Path(self.tmp_dir) / "second.png")
        _make_png(second_source)
        second_result = lora_manager.set_thumbnail(lora.lora_id, second_source)

        self.assertNotEqual(first_result, second_result)
        self.assertTrue(Path(first_result).exists())
        self.assertTrue(Path(second_result).exists())
        self.assertEqual(lora.thumbnail, second_result)


class LoRAManagerRenameTest(unittest.TestCase):
    """
    Mission 052: LoRAManager.update_name(lora_id, name) — sibling of
    update(), targets a LoRA by lora_id explicitly (this Manager's
    existing convention). Strictly idempotent, same contract as
    CharacterManager.update()/ModelManager.update_name()/
    WorkflowManager.update_name(). Must never touch files, Metadata
    (engine/architecture/trigger_word/version) or thumbnail.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        lora_manager = LoRAManager(character_manager, workspace_manager, event_bus=event_bus)
        return workspace_manager, character_manager, lora_manager

    def _create_lora_with_files_and_metadata(self):
        workspace_manager, character_manager, lora_manager = self._wire()
        workspace_manager.create(self.folder)
        character_manager.create("Aria")
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        lora_manager.add_files(["external_ref.safetensors"])
        lora_manager.update(
            lora.lora_id,
            engine="ComfyUI",
            architecture="SDXL",
            trigger_word="mytrigger",
            version="1.0",
        )
        return workspace_manager, character_manager, lora_manager, lora

    def test_rename_mutates_name_and_persists(self):
        workspace_manager, _, lora_manager, lora = self._create_lora_with_files_and_metadata()

        result = lora_manager.update_name(lora.lora_id, "StyleA Renamed")

        self.assertTrue(result)
        self.assertEqual(lora.name, "StyleA Renamed")

    def test_rename_is_idempotent_when_name_unchanged(self):
        _, _, lora_manager, lora = self._create_lora_with_files_and_metadata()

        lora_manager.update_name(lora.lora_id, "StyleA Renamed")

        with patch.object(WorkspaceManager, "save") as save_spy:
            self.assertFalse(lora_manager.update_name(lora.lora_id, "StyleA Renamed"))
            save_spy.assert_not_called()

    def test_rename_saves_only_when_a_real_mutation_happens(self):
        workspace_manager, _, lora_manager, lora = self._create_lora_with_files_and_metadata()

        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertTrue(lora_manager.update_name(lora.lora_id, "StyleA Renamed"))
            save_spy.assert_called_once()

    def test_rename_preserves_id_and_other_properties(self):
        _, _, lora_manager, lora = self._create_lora_with_files_and_metadata()
        original_id = lora.lora_id

        lora_manager.update_name(lora.lora_id, "StyleA Renamed")

        self.assertEqual(lora.lora_id, original_id)
        self.assertEqual(lora.files, ["external_ref.safetensors"])
        self.assertEqual(lora.engine, "ComfyUI")
        self.assertEqual(lora.architecture, "SDXL")
        self.assertEqual(lora.trigger_word, "mytrigger")
        self.assertEqual(lora.version, "1.0")

    def test_rename_empty_string_is_a_legitimate_value(self):
        _, _, lora_manager, lora = self._create_lora_with_files_and_metadata()

        result = lora_manager.update_name(lora.lora_id, "")

        self.assertTrue(result)
        self.assertEqual(lora.name, "")

    def test_rename_unknown_lora_returns_false(self):
        _, _, lora_manager, _ = self._create_lora_with_files_and_metadata()

        self.assertFalse(lora_manager.update_name("does-not-exist", "New Name"))

    def test_rename_persists_after_close_and_reopen(self):
        workspace_manager, _, lora_manager, lora = self._create_lora_with_files_and_metadata()
        original_id = lora.lora_id
        lora_manager.update_name(lora.lora_id, "StyleA Renamed")
        workspace_manager.close()

        workspace_manager_2, character_manager_2, lora_manager_2 = self._wire()
        workspace_manager_2.open(self.folder)
        restored = next(l for l in lora_manager_2.loras if l.lora_id == original_id)

        self.assertEqual(restored.name, "StyleA Renamed")
        self.assertEqual(restored.files, ["external_ref.safetensors"])
        self.assertEqual(restored.engine, "ComfyUI")


class LoRAManagerRemoveFilesTest(unittest.TestCase):
    """
    Mission 050: LoRAManager.remove_files() — symmetric to add_files()
    (exact string equality, never a resolved/normalized path
    comparison, since LoRA.files is never copied). Never touches the
    physical file, never touches name/engine/architecture/
    trigger_word/version/thumbnail.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        lora_manager = LoRAManager(character_manager, workspace_manager, event_bus=event_bus)
        return workspace_manager, character_manager, lora_manager

    def _create_lora_with_files(self, filenames):
        workspace_manager, character_manager, lora_manager = self._wire()
        workspace_manager.create(self.folder)
        character_manager.create("Aria")
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        paths = []
        for name in filenames:
            path = str(Path(self.tmp_dir) / name)
            Path(path).write_bytes(b"fake-lora-weights")
            paths.append(path)
        lora_manager.add_files(paths)
        return workspace_manager, character_manager, lora_manager, lora, paths

    def test_remove_files_removes_a_single_file(self):
        _, _, lora_manager, lora, paths = self._create_lora_with_files(
            ["a.safetensors", "b.safetensors"]
        )

        removed = lora_manager.remove_files([paths[0]])

        self.assertEqual(removed, 1)
        self.assertEqual(lora.files, [paths[1]])

    def test_remove_files_removes_multiple_files_in_one_operation(self):
        _, _, lora_manager, lora, paths = self._create_lora_with_files(
            ["a.safetensors", "b.safetensors", "c.safetensors"]
        )

        removed = lora_manager.remove_files([paths[0], paths[2]])

        self.assertEqual(removed, 2)
        self.assertEqual(lora.files, [paths[1]])

    def test_remove_files_unknown_path_returns_zero_and_does_not_save(self):
        workspace_manager, _, lora_manager, lora, paths = self._create_lora_with_files(
            ["a.safetensors"]
        )

        with patch.object(
            workspace_manager, "save", wraps=workspace_manager.save
        ) as mock_save:
            removed = lora_manager.remove_files(["does-not-exist.safetensors"])

            self.assertEqual(removed, 0)
            mock_save.assert_not_called()

        self.assertEqual(lora.files, paths)

    def test_remove_files_saves_only_if_mutation_occurred(self):
        workspace_manager, _, lora_manager, lora, paths = self._create_lora_with_files(
            ["a.safetensors", "b.safetensors"]
        )

        with patch.object(
            workspace_manager, "save", wraps=workspace_manager.save
        ) as mock_save:
            removed = lora_manager.remove_files([paths[0]])

            self.assertEqual(removed, 1)
            mock_save.assert_called_once()

    def test_remove_files_removing_last_entry_leaves_empty_list(self):
        _, _, lora_manager, lora, paths = self._create_lora_with_files(["a.safetensors"])

        removed = lora_manager.remove_files(paths)

        self.assertEqual(removed, 1)
        self.assertEqual(lora.files, [])

    def test_remove_files_without_active_lora_returns_zero(self):
        workspace_manager, character_manager, lora_manager = self._wire()
        workspace_manager.create(self.folder)
        character_manager.create("Aria")
        lora_manager.create("StyleA")
        # No select() — no active LoRA.

        self.assertEqual(lora_manager.remove_files(["anything.safetensors"]), 0)

    def test_remove_files_does_not_touch_physical_file(self):
        _, _, lora_manager, lora, paths = self._create_lora_with_files(["a.safetensors"])

        lora_manager.remove_files([paths[0]])

        self.assertTrue(Path(paths[0]).exists())
        self.assertEqual(Path(paths[0]).read_bytes(), b"fake-lora-weights")

    def test_remove_files_leaves_metadata_and_thumbnail_untouched(self):
        workspace_manager, _, lora_manager, lora, paths = self._create_lora_with_files(
            ["a.safetensors", "b.safetensors"]
        )
        lora_manager.update(
            lora.lora_id,
            engine="ComfyUI",
            architecture="SDXL",
            trigger_word="mytrigger",
            version="1.0",
        )
        thumb_source = str(Path(self.tmp_dir) / "thumb.png")
        Path(thumb_source).write_bytes(b"fake-png")
        thumbnail = lora_manager.set_thumbnail(lora.lora_id, thumb_source)

        lora_manager.remove_files([paths[0]])

        self.assertEqual(lora.engine, "ComfyUI")
        self.assertEqual(lora.architecture, "SDXL")
        self.assertEqual(lora.trigger_word, "mytrigger")
        self.assertEqual(lora.version, "1.0")
        self.assertEqual(lora.thumbnail, thumbnail)

    def test_remove_files_persists_after_close_and_reopen(self):
        workspace_manager, _, lora_manager, lora, paths = self._create_lora_with_files(
            ["a.safetensors", "b.safetensors"]
        )
        lora_manager.update(lora.lora_id, engine="ComfyUI")

        lora_manager.remove_files([paths[0]])
        workspace_manager.close()

        workspace_manager_2, _, lora_manager_2 = self._wire()
        workspace_manager_2.open(self.folder)
        restored = next(l for l in lora_manager_2.loras if l.name == "StyleA")

        self.assertEqual(restored.files, [paths[1]])
        self.assertEqual(restored.engine, "ComfyUI")


class LoRACreationWithoutManualCharacterSelectionTest(unittest.TestCase):
    """
    Mission 029 regression: LoRAManager used to depend on
    CharacterManager.active_character — exactly the defect diagnosed
    and fixed in DatasetManager during Mission 028 (see
    test_dataset_roundtrip.py's DatasetCreationWithoutManualCharacter
    SelectionTest). Since Mission 026 hid the multi-character selection
    UI, CharactersPage never calls select() at all anymore — only
    *reads* principal_character — so active_character_id stays None for
    the entire session on any Workspace opened via WORKSPACE_OPENED.
    Reproduces the real sequence: create a Workspace, attach a LoRA,
    close, reopen, never call CharacterManager.select(), then prove the
    existing LoRA is still visible, that a newly created LoRA is
    genuinely attached to the same principal Character (not merely that
    create() returns non-None), and that the whole cycle survives a
    second close/reopen.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        lora_manager = LoRAManager(character_manager, workspace_manager, event_bus=event_bus)
        return workspace_manager, character_manager, lora_manager

    def test_lora_lifecycle_survives_reopen_without_manual_character_selection(self):

        # 1. Create a fresh Workspace (auto-creates/selects the
        # principal Character, Mission 026), attach a LoRA, then close.
        workspace_manager, character_manager, lora_manager = self._wire()
        workspace_manager.create(self.folder)
        principal = character_manager.principal_character

        existing = lora_manager.create("Style A")
        self.assertIsNotNone(existing)

        workspace_manager.close()

        # 2. Reopen — exactly the sequence that leaves active_character_id
        # at None (WORKSPACE_OPENED resets it, and nothing re-selects it,
        # since CharactersPage no longer calls select() at all).
        workspace_manager, character_manager, lora_manager = self._wire()
        workspace_manager.open(self.folder)

        self.assertIsNone(character_manager.active_character_id)
        self.assertIsNotNone(character_manager.principal_character)
        self.assertEqual(
            character_manager.principal_character.character_id,
            principal.character_id,
        )

        # 3. The LoRA created before the reopen must still be visible.
        loras = lora_manager.loras
        self.assertEqual(len(loras), 1)
        self.assertEqual(loras[0].name, "Style A")

        # 4. Creating a new LoRA must succeed, and must be genuinely
        # attached to the same principal Character — not merely non-None.
        second = lora_manager.create("Style B")
        self.assertIsNotNone(second)
        self.assertIn(second, character_manager.principal_character.loras)
        self.assertEqual(len(lora_manager.loras), 2)

        # 5. Deleting must succeed too.
        self.assertTrue(lora_manager.delete(existing.lora_id))
        self.assertEqual(len(lora_manager.loras), 1)

        # 6. Persistence: close and reopen again, confirm only the
        # surviving LoRA remains.
        workspace_manager.close()
        workspace_manager, character_manager, lora_manager = self._wire()
        workspace_manager.open(self.folder)

        self.assertIsNone(character_manager.active_character_id)
        final = lora_manager.loras
        self.assertEqual(len(final), 1)
        self.assertEqual(final[0].name, "Style B")

    def test_create_lora_without_open_workspace_shows_no_project_warning(self):
        # Mission 036: LoRAPage.create_lora() must distinguish "no
        # Workspace open" from "Workspace open, zero Character" (see the
        # sibling test below) — both make LoRAManager.create() return
        # None.
        workspace_manager, _, lora_manager = self._wire()
        lora_page = LoRAPage(lora_manager, workspace_manager)

        with patch(
            "src.ui.pages.lora_page.QInputDialog.getText",
            return_value=("Style A", True),
        ), patch("src.ui.pages.lora_page.QMessageBox.warning") as mock_warning:
            lora_page.create_lora()
            mock_warning.assert_called_once_with(
                lora_page,
                "Aucun projet ouvert",
                "Ouvrez ou créez un projet avant de créer une LoRA."
            )

    def test_create_lora_with_open_workspace_and_no_character_shows_personnage_warning(self):
        # Sibling of the test above: same None from LoRAManager.create(),
        # but here the Workspace is open with zero Character.
        workspace_manager, character_manager, lora_manager = self._wire()
        workspace_manager.create(self.folder)
        principal = character_manager.characters[0]
        character_manager.delete(principal.character_id)
        lora_page = LoRAPage(lora_manager, workspace_manager)

        with patch(
            "src.ui.pages.lora_page.QInputDialog.getText",
            return_value=("Style A", True),
        ), patch("src.ui.pages.lora_page.QMessageBox.warning") as mock_warning:
            lora_page.create_lora()
            mock_warning.assert_called_once_with(
                lora_page,
                "Aucun personnage",
                "Ce projet ne possède aucun personnage — créez-en un depuis Characters avant de créer une LoRA."
            )


class LoRAPageSortTest(unittest.TestCase):
    """
    Mission 051: LoRAPage.lora_list is now sorted by name, case-
    insensitive, always active — same pattern as Mission 048. Only
    lora_list is concerned — LoRA.files (Mission 050) and its
    files_list widget are untouched, as are Metadata/thumbnail
    (Mission 047). Character.loras (Domain) must never be reordered.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "LoRASortProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        lora_manager = LoRAManager(character_manager, workspace_manager, event_bus=event_bus)
        lora_page = LoRAPage(lora_manager, workspace_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, lora_page.update_loras)
        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, lora_page.update_loras)
        for event_name in LORA_EVENTS:
            event_bus.subscribe(event_name, lora_page.update_loras)

        return event_bus, workspace_manager, character_manager, lora_manager, lora_page

    def test_display_order_is_alphabetical_case_insensitive(self):

        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)

        for name in ("Zebra", "mango", "Apple", "banana", "Cherry"):
            lora_manager.create(name)

        displayed = [
            lora_page.lora_list.item(i).text()
            for i in range(lora_page.lora_list.count())
        ]
        # Item text includes the file count suffix (e.g. "Apple (0 fichier(s))")
        # — match on the name prefix, not the full label.
        names = [text.split(" (")[0] for text in displayed]
        self.assertEqual(names, ["Apple", "banana", "Cherry", "mango", "Zebra"])

    def test_domain_collection_keeps_insertion_order(self):

        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)

        for name in ("Zebra", "mango", "Apple"):
            lora_manager.create(name)

        principal = character_manager.principal_character
        self.assertEqual(
            [l.name for l in principal.loras],
            ["Zebra", "mango", "Apple"],
        )

    def test_sort_is_stable_for_identical_names(self):

        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)

        first = lora_manager.create("Same")
        second = lora_manager.create("Same")

        displayed_ids = [
            lora_page.lora_list.item(i).data(Qt.UserRole)
            for i in range(lora_page.lora_list.count())
        ]
        self.assertEqual(displayed_ids, [first.lora_id, second.lora_id])

    def test_selection_targets_correct_lora_and_preserves_files_metadata_thumbnail(self):

        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)

        zebra = lora_manager.create("Zebra")
        apple = lora_manager.create("Apple")

        lora_manager.select(apple.lora_id)
        lora_manager.add_files(["C:/loras/apple.safetensors"])
        lora_manager.update(apple.lora_id, engine="ComfyUI", trigger_word="apple_trigger")

        # "Apple" now displays at position 0, ahead of "Zebra" — confirm
        # the correct LoRA's files/metadata are reflected, not positional.
        self.assertTrue(lora_page.lora_list.item(0).text().startswith("Apple"))
        self.assertEqual(
            [lora_page.files_list.item(i).text() for i in range(lora_page.files_list.count())],
            ["C:/loras/apple.safetensors"],
        )
        self.assertEqual(lora_page.engine_edit.text(), "ComfyUI")
        self.assertEqual(lora_page.trigger_word_edit.text(), "apple_trigger")

        lora_manager.select(zebra.lora_id)
        self.assertEqual(lora_page.files_list.count(), 0)
        self.assertEqual(lora_page.engine_edit.text(), "")
        self.assertEqual(lora_page.trigger_word_edit.text(), "")

    def test_refresh_after_second_creation_resorts_entire_list(self):

        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)

        lora_manager.create("Mango")
        lora_manager.create("Zebra")
        lora_manager.create("Apple")

        displayed = [
            lora_page.lora_list.item(i).text().split(" (")[0]
            for i in range(lora_page.lora_list.count())
        ]
        self.assertEqual(displayed, ["Apple", "Mango", "Zebra"])


class LoRAPageRenameTest(unittest.TestCase):
    """
    Mission 052: LoRAPage.name_edit allows renaming the active LoRA in
    place (editingFinished -> LoRAManager.update_name()), immediately,
    independently of the "Enregistrer les métadonnées" button (Mission
    047) which stays reserved for engine/architecture/trigger_word/
    version. Renaming must never touch files_list/LoRA.files, Metadata
    or thumbnail, and must interact correctly with Mission 051's
    alphabetical sort — selection stays on the same LoRA by id despite
    any display reorder the rename triggers.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "LoRARenameProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        lora_manager = LoRAManager(character_manager, workspace_manager, event_bus=event_bus)
        lora_page = LoRAPage(lora_manager, workspace_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, lora_page.update_loras)
        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, lora_page.update_loras)
        for event_name in LORA_EVENTS:
            event_bus.subscribe(event_name, lora_page.update_loras)

        return event_bus, workspace_manager, character_manager, lora_manager, lora_page

    def test_rename_via_widget_updates_manager_and_display(self):

        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)

        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)

        lora_page.name_edit.setText("StyleA Renamed")
        lora_page.name_edit.editingFinished.emit()

        self.assertEqual(lora_manager.active_lora.name, "StyleA Renamed")
        self.assertEqual(lora_manager.active_lora.lora_id, lora.lora_id)
        self.assertTrue(lora_page.lora_list.item(0).text().startswith("StyleA Renamed"))

    def test_rename_preserves_files_metadata_and_thumbnail(self):

        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)

        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        lora_manager.add_files(["C:/loras/style_a.safetensors"])
        lora_manager.update(lora.lora_id, engine="ComfyUI", trigger_word="mytrigger")
        source = str(Path(self.tmp_dir) / "external.png")
        _make_png(source)
        lora_manager.set_thumbnail(lora.lora_id, source)
        thumbnail_before = lora.thumbnail

        lora_page.name_edit.setText("StyleA Renamed")
        lora_page.name_edit.editingFinished.emit()

        self.assertEqual(lora.files, ["C:/loras/style_a.safetensors"])
        self.assertEqual(lora.engine, "ComfyUI")
        self.assertEqual(lora.trigger_word, "mytrigger")
        self.assertEqual(lora.thumbnail, thumbnail_before)
        self.assertEqual(
            [lora_page.files_list.item(i).text() for i in range(lora_page.files_list.count())],
            ["C:/loras/style_a.safetensors"],
        )
        self.assertEqual(lora_page.engine_edit.text(), "ComfyUI")
        self.assertEqual(lora_page.trigger_word_edit.text(), "mytrigger")

    def test_rename_moving_entity_to_front_keeps_correct_selection(self):

        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)

        mango = lora_manager.create("Mango")
        zebra = lora_manager.create("Zebra")
        lora_manager.select(zebra.lora_id)
        lora_manager.add_files(["C:/loras/zebra.safetensors"])

        lora_page.name_edit.setText("Apple")
        lora_page.name_edit.editingFinished.emit()

        displayed = [
            lora_page.lora_list.item(i).text().split(" (")[0]
            for i in range(lora_page.lora_list.count())
        ]
        self.assertEqual(displayed, ["Apple", "Mango"])
        self.assertEqual(lora_page.lora_list.item(0).data(Qt.UserRole), zebra.lora_id)
        self.assertEqual(lora_manager.active_lora_id, zebra.lora_id)
        self.assertEqual(
            [lora_page.files_list.item(i).text() for i in range(lora_page.files_list.count())],
            ["C:/loras/zebra.safetensors"],
        )

    def test_rename_moving_entity_to_back_keeps_correct_selection(self):

        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)

        apple = lora_manager.create("Apple")
        mango = lora_manager.create("Mango")
        lora_manager.select(apple.lora_id)
        lora_manager.add_files(["C:/loras/apple.safetensors"])

        lora_page.name_edit.setText("Zzz")
        lora_page.name_edit.editingFinished.emit()

        displayed = [
            lora_page.lora_list.item(i).text().split(" (")[0]
            for i in range(lora_page.lora_list.count())
        ]
        self.assertEqual(displayed, ["Mango", "Zzz"])
        self.assertEqual(lora_page.lora_list.item(1).data(Qt.UserRole), apple.lora_id)
        self.assertEqual(lora_manager.active_lora_id, apple.lora_id)
        self.assertEqual(
            [lora_page.files_list.item(i).text() for i in range(lora_page.files_list.count())],
            ["C:/loras/apple.safetensors"],
        )

    def test_rename_with_no_active_lora_is_a_no_op(self):

        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)
        lora_manager.create("StyleA")

        lora_page.name_edit.setText("Whatever")
        lora_page.name_edit.editingFinished.emit()

        principal = character_manager.principal_character
        self.assertEqual([l.name for l in principal.loras], ["StyleA"])

    def test_rename_does_not_regress_add_remove_files_save_metadata_or_thumbnail(self):

        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)

        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)

        lora_page.name_edit.setText("StyleA Renamed")
        lora_page.name_edit.editingFinished.emit()

        # add_files() still works after a rename.
        added = lora_manager.add_files(["C:/loras/a.safetensors", "C:/loras/b.safetensors"])
        self.assertEqual(added, 2)
        self.assertEqual(
            [lora_page.files_list.item(i).text() for i in range(lora_page.files_list.count())],
            ["C:/loras/a.safetensors", "C:/loras/b.safetensors"],
        )

        # remove_files() still works after a rename.
        removed = lora_manager.remove_files(["C:/loras/a.safetensors"])
        self.assertEqual(removed, 1)
        self.assertEqual(lora.files, ["C:/loras/b.safetensors"])

        # save_metadata() (Mission 047 button) still works after a rename.
        lora_page.engine_edit.setText("ComfyUI")
        lora_page.architecture_edit.setText("SDXL")
        lora_page.trigger_word_edit.setText("mytrigger")
        lora_page.version_edit.setText("1.0")
        lora_page.save_metadata()
        self.assertEqual(lora.engine, "ComfyUI")
        self.assertEqual(lora.architecture, "SDXL")
        self.assertEqual(lora.trigger_word, "mytrigger")
        self.assertEqual(lora.version, "1.0")

        # set_thumbnail() still works after a rename.
        source = str(Path(self.tmp_dir) / "external.png")
        _make_png(source)
        result = lora_manager.set_thumbnail(lora.lora_id, source)
        self.assertIsNotNone(result)
        self.assertEqual(lora.thumbnail, result)

        # Name change itself survived all of the above.
        self.assertEqual(lora.name, "StyleA Renamed")

    def test_rename_persists_after_close_reopen_via_ui(self):

        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)

        lora = lora_manager.create("StyleA")
        original_id = lora.lora_id
        lora_manager.select(lora.lora_id)

        lora_page.name_edit.setText("StyleA Renamed")
        lora_page.name_edit.editingFinished.emit()

        workspace_manager.close()

        _, workspace_manager_2, character_manager_2, lora_manager_2, lora_page_2 = self._wire()
        workspace_manager_2.open(self.folder)

        restored = next(l for l in lora_manager_2.loras if l.lora_id == original_id)
        self.assertEqual(restored.name, "StyleA Renamed")
        self.assertTrue(lora_page_2.lora_list.item(0).text().startswith("StyleA Renamed"))


class LoRAPageDeleteConfirmationTest(unittest.TestCase):
    """
    Mission 062: LoRAPage.delete_lora() now confirms before deleting,
    mirroring ImagesPage.delete_selected_images()'s established
    QMessageBox pattern (Mission 046) — Cancel is the safe default.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "LoRADeleteProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        lora_manager = LoRAManager(character_manager, workspace_manager, event_bus=event_bus)
        lora_page = LoRAPage(lora_manager, workspace_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, lora_page.update_loras)
        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, lora_page.update_loras)
        for event_name in LORA_EVENTS:
            event_bus.subscribe(event_name, lora_page.update_loras)

        return event_bus, workspace_manager, character_manager, lora_manager, lora_page

    def _confirm_delete(self, accept: bool):
        patcher = patch("src.ui.pages.lora_page.QMessageBox")
        mock_cls = patcher.start()
        self.addCleanup(patcher.stop)

        accept_sentinel = object()
        cancel_sentinel = object()
        box_instance = mock_cls.return_value
        box_instance.addButton.side_effect = [accept_sentinel, cancel_sentinel]
        box_instance.clickedButton.return_value = (
            accept_sentinel if accept else cancel_sentinel
        )

        return mock_cls

    def test_delete_with_no_selection_is_a_no_op(self):
        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)

        mock_cls = self._confirm_delete(accept=True)

        lora_page.delete_lora()

        mock_cls.assert_not_called()

    def test_delete_confirmed_removes_lora(self):
        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)

        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)

        self._confirm_delete(accept=True)

        lora_page.delete_lora()

        self.assertIsNone(lora_manager.active_lora_id)
        self.assertEqual(lora_manager.loras, [])

    def test_delete_cancelled_calls_neither_manager_nor_mutates_state(self):
        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)

        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)

        self._confirm_delete(accept=False)

        with patch.object(lora_manager, "delete") as delete_mock:
            lora_page.delete_lora()
            delete_mock.assert_not_called()

        self.assertEqual(lora_manager.active_lora_id, lora.lora_id)
        self.assertEqual(len(lora_manager.loras), 1)


if __name__ == "__main__":
    unittest.main()
