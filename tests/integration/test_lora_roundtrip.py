"""
Integration coverage for the LoRA lifecycle, exercising LoRAManager,
Character.loras, Workspace persistence, EventBus and the real
DashboardPage/CharactersPage/ImagesPage/LoRAPage widgets together —
the same wiring MainWindow uses.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QListWidget, QMessageBox

from src.core.event_bus import EventBus
from src.infrastructure.storage.workspace_storage import WorkspaceStorage, WorkspaceStorageError
from src.infrastructure.storage.lora_library_storage import (
    LoRALibraryStorage,
    LoRALibraryStorageError,
)
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
from src.managers.lora_manager import (
    LoRAManager,
    LORA_CREATED,
    LORA_SELECTED,
    LORA_DELETED,
)
from src.managers.lora_library_manager import (
    LoRALibraryManager,
    LoRALibraryError,
    LORA_LIBRARY_IMPORTED,
    LORA_LIBRARY_DELETED,
    LORA_LIBRARY_UPDATED,
)
from src.managers.application_settings_manager import ApplicationSettingsManager
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

        lora_library_manager = LoRALibraryManager(storage_directory=Path(self.tmp_dir) / "lora_library")
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings",
            lora_library_manager=lora_library_manager,
        )

        dashboard = DashboardPage()
        characters_page = CharactersPage(character_manager, workspace_manager)
        images = ImagesPage(workspace_manager)
        lora_page = LoRAPage(lora_manager, workspace_manager, lora_library_manager, application_settings_manager)

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
        self.assertTrue(result.deleted)
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

    def test_choose_thumbnail_save_failure_shows_error_and_keeps_previous_value(self):

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

        new_source = str(Path(self.tmp_dir) / "new.png")
        _make_png(new_source)

        # Mission 067: set_thumbnail() now restores the previous
        # thumbnail and compensates the newly created copy before
        # re-raising WorkspaceManagerError on a save() failure.
        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileName",
            return_value=(new_source, ""),
        ), patch("src.ui.pages.lora_page.QMessageBox") as mock_cls, patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ):
            lora_page.choose_thumbnail()

        mock_cls.critical.assert_called_once()
        mock_cls.warning.assert_not_called()
        self.assertEqual(lora_manager.active_lora.thumbnail, previous_thumbnail)
        self.assertTrue(Path(previous_thumbnail).exists())

    def test_choose_thumbnail_cleanup_failure_warns_but_keeps_new_thumbnail_active(self):

        (_, workspace_manager, character_manager, lora_manager,
         _dashboard, _characters_page, _images, lora_page) = self._wire()

        workspace_manager.create(self.folder)
        character_manager.create("Aria")
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)

        first_source = str(Path(self.tmp_dir) / "first.png")
        _make_png(first_source)
        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileName",
            return_value=(first_source, ""),
        ):
            lora_page.choose_thumbnail()

        second_source = str(Path(self.tmp_dir) / "second.png")
        _make_png(second_source)

        # Mission 080: the new thumbnail is successfully copied and
        # persisted — only the best-effort cleanup of the now-superseded
        # previous file fails, which must never be presented as a
        # failure of the thumbnail change itself.
        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileName",
            return_value=(second_source, ""),
        ), patch("src.ui.pages.lora_page.QMessageBox") as mock_cls, patch.object(
            Path, "unlink", side_effect=PermissionError("locked")
        ):
            lora_page.choose_thumbnail()

        mock_cls.critical.assert_not_called()
        mock_cls.warning.assert_called_once()
        expected_folder = self.folder / "models" / "loras" / lora.lora_id
        self.assertEqual(
            lora_manager.active_lora.thumbnail, str(expected_folder / "second.png")
        )
        self.assertFalse(lora_page.thumbnail_label.pixmap().isNull())

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
        self.assertEqual(lora_manager.active_lora.thumbnail, thumbnail.thumbnail)
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
        self.assertEqual(result.thumbnail, str(expected_folder / "external.png"))
        self.assertEqual(lora.thumbnail, result.thumbnail)
        self.assertTrue((expected_folder / "external.png").exists())
        self.assertTrue(Path(source).exists())
        self.assertFalse(result.cleanup_failed)
        self.assertIsNone(result.residual_path)

    def test_set_thumbnail_reuses_source_already_internal(self):
        workspace_manager, _, lora_manager, lora = self._create_lora()

        source = str(Path(self.tmp_dir) / "external.png")
        _make_png(source)
        first = lora_manager.set_thumbnail(lora.lora_id, source)

        # Mission 080: reusing the LoRA's own current thumbnail path as
        # the new source is a pure passthrough (old == new after
        # resolution) — no cleanup must ever be attempted in this case.
        second = lora_manager.set_thumbnail(lora.lora_id, first.thumbnail)

        self.assertEqual(second.thumbnail, first.thumbnail)
        self.assertFalse(second.cleanup_failed)
        self.assertTrue(Path(first.thumbnail).exists())

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

    # --- Mission 067: rollback + compensation on a save() failure ---

    def test_set_thumbnail_save_failure_restores_old_value_and_deletes_new_copy(self):
        workspace_manager, _, lora_manager, lora = self._create_lora()

        good_source = str(Path(self.tmp_dir) / "good.png")
        _make_png(good_source)
        old_thumbnail = lora_manager.set_thumbnail(lora.lora_id, good_source).thumbnail

        new_source = str(Path(self.tmp_dir) / "new.png")
        _make_png(new_source)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                lora_manager.set_thumbnail(lora.lora_id, new_source)

        self.assertEqual(lora.thumbnail, old_thumbnail)
        self.assertTrue(Path(old_thumbnail).exists())
        expected_new_copy = self.folder / "models" / "loras" / lora.lora_id / "new.png"
        self.assertFalse(expected_new_copy.exists())
        # The source handed to set_thumbnail() is never touched either way.
        self.assertTrue(Path(new_source).exists())

    def test_set_thumbnail_save_failure_with_a_passthrough_source_never_deletes_it(self):
        workspace_manager, _, lora_manager, lora = self._create_lora()

        source = str(Path(self.tmp_dir) / "external.png")
        _make_png(source)
        first_thumbnail = lora_manager.set_thumbnail(lora.lora_id, source).thumbnail

        # Re-using the already-internal thumbnail path itself is a pure
        # passthrough — copy_into_workspace() returns it unchanged.
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                lora_manager.set_thumbnail(lora.lora_id, first_thumbnail)

        self.assertEqual(lora.thumbnail, first_thumbnail)
        self.assertTrue(Path(first_thumbnail).exists())

    def test_set_thumbnail_cleanup_failure_preserves_the_original_persistence_error(self):
        workspace_manager, _, lora_manager, lora = self._create_lora()

        source = str(Path(self.tmp_dir) / "new.png")
        _make_png(source)

        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ), patch.object(Path, "unlink", side_effect=PermissionError("locked")):
            with self.assertRaises(WorkspaceManagerError) as ctx:
                lora_manager.set_thumbnail(lora.lora_id, source)

        message = str(ctx.exception)
        self.assertIn("disk full", message)
        self.assertIn("orphaned", message)
        self.assertEqual(lora.thumbnail, "")

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

        self.assertEqual(restored.thumbnail, result.thumbnail)
        self.assertTrue(Path(restored.thumbnail).exists())

    def test_set_thumbnail_replacement_deletes_previous_owned_file(self):
        """
        Mission 080: replacing an owned thumbnail (one actually copied
        into this LoRA's own private folder by a prior set_thumbnail()
        call) must delete the now-superseded file once the new one is
        durably persisted — this is the deliberate, intended behavior
        change introduced by this mission (this test replaces the old
        test_set_thumbnail_replacement_does_not_delete_previous_file,
        which asserted the exact opposite).
        """
        workspace_manager, _, lora_manager, lora = self._create_lora()

        first_source = str(Path(self.tmp_dir) / "first.png")
        _make_png(first_source)
        first_result = lora_manager.set_thumbnail(lora.lora_id, first_source)

        second_source = str(Path(self.tmp_dir) / "second.png")
        _make_png(second_source)
        second_result = lora_manager.set_thumbnail(lora.lora_id, second_source)

        self.assertNotEqual(first_result.thumbnail, second_result.thumbnail)
        self.assertFalse(Path(first_result.thumbnail).exists())
        self.assertTrue(Path(second_result.thumbnail).exists())
        self.assertEqual(lora.thumbnail, second_result.thumbnail)
        self.assertFalse(second_result.cleanup_failed)
        self.assertIsNone(second_result.residual_path)


class LoRAManagerThumbnailCleanupTest(unittest.TestCase):
    """
    Mission 080: once a new thumbnail has been durably persisted by
    set_thumbnail(), the now-superseded previous file is deleted — but
    only if it is demonstrably owned by this LoRA's own private folder
    (workspace_root/models/loras/<lora_id>/). copy_into_workspace()'s
    passthrough branch (see LoRAManagerMetadataTest above) can leave
    lora.thumbnail pointing anywhere else under workspace_root —
    images/, another LoRA's own folder, etc. — none of which this
    Manager may ever delete. The M067 transactional contract (rollback
    + new-copy compensation on a save() failure) is entirely unmodified
    by this mission and remains covered by LoRAManagerMetadataTest's own
    tests; this class only covers the new post-success cleanup step.
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

    def test_first_thumbnail_has_nothing_to_clean_up(self):
        workspace_manager, _, lora_manager, lora = self._create_lora()

        source = str(Path(self.tmp_dir) / "first.png")
        _make_png(source)

        result = lora_manager.set_thumbnail(lora.lora_id, source)

        self.assertFalse(result.cleanup_failed)
        self.assertIsNone(result.residual_path)
        self.assertTrue(Path(result.thumbnail).exists())

    def test_replacement_deletes_previous_owned_file_and_persists_new_one_in_project_json(self):
        workspace_manager, _, lora_manager, lora = self._create_lora()

        first_source = str(Path(self.tmp_dir) / "first.png")
        _make_png(first_source)
        first_result = lora_manager.set_thumbnail(lora.lora_id, first_source)

        second_source = str(Path(self.tmp_dir) / "second.png")
        _make_png(second_source)
        second_result = lora_manager.set_thumbnail(lora.lora_id, second_source)

        self.assertFalse(Path(first_result.thumbnail).exists())
        self.assertTrue(Path(second_result.thumbnail).exists())
        self.assertFalse(second_result.cleanup_failed)
        self.assertIsNone(second_result.residual_path)

        with open(self.folder / "project.json", encoding="utf-8") as f:
            raw = json.load(f)
        persisted_lora = next(
            entry
            for character in raw["characters"]
            for entry in character["loras"]
            if entry["lora_id"] == lora.lora_id
        )
        self.assertEqual(persisted_lora["thumbnail"], second_result.thumbnail)

    def test_cleanup_failure_after_successful_save_reports_residual_without_raising(self):
        workspace_manager, _, lora_manager, lora = self._create_lora()

        first_source = str(Path(self.tmp_dir) / "first.png")
        _make_png(first_source)
        first_result = lora_manager.set_thumbnail(lora.lora_id, first_source)

        second_source = str(Path(self.tmp_dir) / "second.png")
        _make_png(second_source)

        with patch.object(Path, "unlink", side_effect=PermissionError("locked")):
            second_result = lora_manager.set_thumbnail(lora.lora_id, second_source)

        # The functional mutation already fully succeeded — the new
        # thumbnail is active and persisted — regardless of the cleanup
        # outcome below.
        self.assertEqual(lora.thumbnail, second_result.thumbnail)
        self.assertTrue(Path(second_result.thumbnail).exists())
        self.assertTrue(second_result.cleanup_failed)
        self.assertEqual(second_result.residual_path, first_result.thumbnail)
        # The old file was never actually deleted (unlink was patched to
        # fail, not to succeed) — still there, exactly as cleanup_failed
        # promises.
        self.assertTrue(Path(first_result.thumbnail).exists())

    def test_old_owned_file_already_missing_is_treated_as_already_clean(self):
        workspace_manager, _, lora_manager, lora = self._create_lora()

        first_source = str(Path(self.tmp_dir) / "first.png")
        _make_png(first_source)
        first_result = lora_manager.set_thumbnail(lora.lora_id, first_source)

        # Simulates the old file having already disappeared by some
        # other means (manual deletion, external tool, ...) before the
        # replacement happens.
        Path(first_result.thumbnail).unlink()

        second_source = str(Path(self.tmp_dir) / "second.png")
        _make_png(second_source)
        second_result = lora_manager.set_thumbnail(lora.lora_id, second_source)

        self.assertFalse(second_result.cleanup_failed)
        self.assertIsNone(second_result.residual_path)
        self.assertTrue(Path(second_result.thumbnail).exists())

    def test_replacement_never_deletes_a_passthrough_file_outside_owned_folder(self):
        workspace_manager, _, lora_manager, lora = self._create_lora()

        # A file genuinely internal to the Workspace, but nowhere near
        # this LoRA's own private folder — e.g. an image reachable from
        # the gallery. Handing it directly to set_thumbnail() reproduces
        # exactly how copy_into_workspace()'s passthrough branch can
        # leave lora.thumbnail pointing at it, with no copy ever made.
        gallery_path = workspace_manager.current_workspace.root / "images" / "gallery.png"
        gallery_path.parent.mkdir(parents=True, exist_ok=True)
        _make_png(str(gallery_path))

        first_result = lora_manager.set_thumbnail(lora.lora_id, str(gallery_path))
        self.assertEqual(first_result.thumbnail, str(gallery_path.resolve()))

        second_source = str(Path(self.tmp_dir) / "second.png")
        _make_png(second_source)
        second_result = lora_manager.set_thumbnail(lora.lora_id, second_source)

        self.assertTrue(gallery_path.exists())
        self.assertFalse(second_result.cleanup_failed)
        self.assertIsNone(second_result.residual_path)
        self.assertTrue(Path(second_result.thumbnail).exists())

    def test_replacement_never_deletes_a_file_owned_by_another_lora(self):
        workspace_manager, character_manager, lora_manager, lora_a = self._create_lora()
        lora_b = lora_manager.create("StyleB")

        b_source = str(Path(self.tmp_dir) / "b_thumb.png")
        _make_png(b_source)
        b_result = lora_manager.set_thumbnail(lora_b.lora_id, b_source)

        # Passthrough: a's thumbnail is pointed directly at b's own
        # private copy (reachable in practice via a file dialog browsing
        # straight into the project folder).
        first_result = lora_manager.set_thumbnail(lora_a.lora_id, b_result.thumbnail)
        self.assertEqual(first_result.thumbnail, b_result.thumbnail)

        a_new_source = str(Path(self.tmp_dir) / "a_new.png")
        _make_png(a_new_source)
        second_result = lora_manager.set_thumbnail(lora_a.lora_id, a_new_source)

        self.assertTrue(Path(b_result.thumbnail).exists())
        self.assertEqual(lora_b.thumbnail, b_result.thumbnail)
        self.assertFalse(second_result.cleanup_failed)
        self.assertIsNone(second_result.residual_path)


class LoRAManagerMetadataRollbackTest(unittest.TestCase):
    """
    Mission 073: LoRAManager.update() rolls back all four text-metadata
    fields (engine/architecture/trigger_word/version) to their exact
    previous values on the same LoRA instance if save() fails — no
    event is published either before or after this mission (update()
    never had one, same as CharacterManager.update()), so the "no
    success event on failure" requirement is verified as a standing
    invariant rather than a behavior newly introduced here.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.lora_manager = LoRAManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.lora = self.lora_manager.create("StyleA")
        self.lora_manager.update(
            self.lora.lora_id,
            engine="ComfyUI",
            architecture="SDXL",
            trigger_word="mytrigger",
            version="1.0",
        )
        # A second, unrelated LoRA — used to verify a failed update() on
        # the first one never touches it.
        self.other_lora = self.lora_manager.create("StyleB")
        self.lora_manager.update(self.other_lora.lora_id, engine="Kohya", version="2.0")

    def test_update_succeeds_normally_when_save_works(self):
        result = self.lora_manager.update(
            self.lora.lora_id,
            engine="ComfyUI2",
            architecture="SD1.5",
            trigger_word="newtrigger",
            version="2.0",
        )

        self.assertTrue(result)
        self.assertEqual(self.lora.engine, "ComfyUI2")
        self.assertEqual(self.lora.architecture, "SD1.5")
        self.assertEqual(self.lora.trigger_word, "newtrigger")
        self.assertEqual(self.lora.version, "2.0")

    def test_update_save_failure_restores_all_four_fields_on_same_object(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.update(
                    self.lora.lora_id,
                    engine="ComfyUI2",
                    architecture="SD1.5",
                    trigger_word="newtrigger",
                    version="2.0",
                )

        self.assertEqual(self.lora.engine, "ComfyUI")
        self.assertEqual(self.lora.architecture, "SDXL")
        self.assertEqual(self.lora.trigger_word, "mytrigger")
        self.assertEqual(self.lora.version, "1.0")
        # Same object, not a recreated equivalent.
        self.assertIs(self.lora_manager._find(self.lora.lora_id), self.lora)

    def test_update_save_failure_restores_a_single_changed_field_too(self):
        # A rollback proven only on the multi-field case could hide a
        # bug affecting a single-field update — covered explicitly.
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.update(self.lora.lora_id, engine="ComfyUI2")

        self.assertEqual(self.lora.engine, "ComfyUI")
        self.assertEqual(self.lora.architecture, "SDXL")
        self.assertEqual(self.lora.trigger_word, "mytrigger")
        self.assertEqual(self.lora.version, "1.0")

    def test_update_save_failure_publishes_no_event(self):
        received = []
        for event_name in (LORA_CREATED, LORA_SELECTED, LORA_DELETED):
            self.event_bus.subscribe(event_name, lambda payload: received.append(payload))

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.update(self.lora.lora_id, engine="ComfyUI2")

        self.assertEqual(received, [])

    def test_update_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.update(
                    self.lora.lora_id,
                    engine="ComfyUI2",
                    architecture="SD1.5",
                    trigger_word="newtrigger",
                    version="2.0",
                )

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_update_save_failure_never_touches_an_unrelated_lora(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.update(
                    self.lora.lora_id,
                    engine="ComfyUI2",
                    architecture="SD1.5",
                    trigger_word="newtrigger",
                    version="2.0",
                )

        self.assertEqual(self.other_lora.engine, "Kohya")
        self.assertEqual(self.other_lora.version, "2.0")

    def test_retry_after_save_failure_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.update(
                    self.lora.lora_id,
                    engine="ComfyUI2",
                    architecture="SD1.5",
                    trigger_word="newtrigger",
                    version="2.0",
                )

        result = self.lora_manager.update(
            self.lora.lora_id,
            engine="ComfyUI2",
            architecture="SD1.5",
            trigger_word="newtrigger",
            version="2.0",
        )

        self.assertTrue(result)
        self.assertEqual(self.lora.engine, "ComfyUI2")
        self.assertEqual(self.lora.architecture, "SD1.5")
        self.assertEqual(self.lora.trigger_word, "newtrigger")
        self.assertEqual(self.lora.version, "2.0")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        stored = next(l for l in aria["loras"] if l["lora_id"] == self.lora.lora_id)
        self.assertEqual(stored["engine"], "ComfyUI2")
        self.assertEqual(stored["version"], "2.0")


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


class LoRAManagerCreateRollbackTest(unittest.TestCase):
    """
    Mission 072: LoRAManager.create() rolls back the in-memory append
    (the same LoRA instance just constructed) if save() fails — mirrors
    DatasetManager.create()'s rollback contract.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.lora_manager = LoRAManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.existing_lora = self.lora_manager.create("StyleA")

    def test_create_succeeds_normally_when_save_works(self):
        lora = self.lora_manager.create("StyleB")

        self.assertIsNotNone(lora)
        self.assertEqual(
            [l.lora_id for l in self.lora_manager.loras],
            [self.existing_lora.lora_id, lora.lora_id],
        )

    def test_create_save_failure_removes_the_phantom_lora(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.create("StyleB")

        self.assertEqual(
            [l.lora_id for l in self.lora_manager.loras],
            [self.existing_lora.lora_id],
        )

    def test_create_save_failure_publishes_no_success_event(self):
        received = []
        self.event_bus.subscribe(LORA_CREATED, lambda payload: received.append(payload))

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.create("StyleB")

        self.assertEqual(received, [])

    def test_create_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.create("StyleB")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_after_create_failure_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.create("StyleB")

        lora = self.lora_manager.create("StyleB")

        self.assertIsNotNone(lora)
        self.assertEqual(
            [l.lora_id for l in self.lora_manager.loras],
            [self.existing_lora.lora_id, lora.lora_id],
        )

        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        self.assertEqual(
            sorted(l["lora_id"] for l in aria["loras"]),
            sorted([self.existing_lora.lora_id, lora.lora_id]),
        )

    def test_create_save_failure_does_not_affect_a_preexisting_unrelated_lora(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.create("StyleB")

        loras = self.lora_manager.loras
        self.assertEqual(len(loras), 1)
        self.assertIs(loras[0], self.existing_lora)


class LoRAPageCreatePersistenceFailureTest(unittest.TestCase):
    """
    Mission 072: LoRAPage.create_lora() catches WorkspaceManagerError
    around lora_manager.create() and shows QMessageBox.critical().
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.lora_manager = LoRAManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.lora_library_manager = LoRALibraryManager(storage_directory=Path(self.tmp_dir) / "lora_library")
        self.application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings",
            lora_library_manager=self.lora_library_manager,
        )
        self.lora_page = LoRAPage(
            self.lora_manager, self.workspace_manager, self.lora_library_manager, self.application_settings_manager
        )
        for event_name in LORA_EVENTS:
            self.event_bus.subscribe(event_name, self.lora_page.update_loras)

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

    def test_create_failure_shows_error_and_lora_list_stays_empty(self):
        with patch(
            "src.ui.pages.lora_page.QInputDialog.getText",
            return_value=("StyleA", True),
        ), patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.lora_page.QMessageBox.critical") as mock_critical:
            self.lora_page.create_lora()

        self.assertTrue(mock_critical.called)
        self.assertEqual(self.lora_manager.loras, [])
        self.assertEqual(self.lora_page.lora_list.count(), 0)

    def test_create_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch(
            "src.ui.pages.lora_page.QInputDialog.getText",
            return_value=("StyleA", True),
        ), patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.lora_page.QMessageBox.critical"):
            self.lora_page.create_lora()

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_after_create_failure_actually_creates(self):
        with patch(
            "src.ui.pages.lora_page.QInputDialog.getText",
            return_value=("StyleA", True),
        ), patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.lora_page.QMessageBox.critical"):
            self.lora_page.create_lora()

        with patch(
            "src.ui.pages.lora_page.QInputDialog.getText",
            return_value=("StyleA", True),
        ):
            self.lora_page.create_lora()

        self.assertEqual(len(self.lora_manager.loras), 1)
        self.assertEqual(self.lora_page.lora_list.count(), 1)


class LoRAManagerRenameRollbackTest(unittest.TestCase):
    """
    Mission 070: LoRAManager.update_name() rolls back LoRA.name to its
    previous value if save() fails — a single-scalar Domain-only
    mutation, no filesystem involved, so a local rollback is sufficient.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.lora_manager = LoRAManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.lora = self.lora_manager.create("StyleA")
        self.lora_manager.select(self.lora.lora_id)

    def test_update_name_succeeds_normally_when_save_works(self):
        result = self.lora_manager.update_name(self.lora.lora_id, "StyleA Renamed")

        self.assertTrue(result)
        self.assertEqual(self.lora.name, "StyleA Renamed")

    def test_update_name_save_failure_restores_previous_name_on_same_object(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.update_name(self.lora.lora_id, "StyleA Renamed")

        self.assertEqual(self.lora.name, "StyleA")
        self.assertIs(self.lora_manager.active_lora, self.lora)

    def test_update_name_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.update_name(self.lora.lora_id, "StyleA Renamed")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_of_the_same_previously_rejected_name_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.update_name(self.lora.lora_id, "StyleA Renamed")

        result = self.lora_manager.update_name(self.lora.lora_id, "StyleA Renamed")

        self.assertTrue(result)
        self.assertEqual(self.lora.name, "StyleA Renamed")
        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        self.assertEqual(aria["loras"][0]["name"], "StyleA Renamed")


class LoRAManagerAddFilesRollbackTest(unittest.TestCase):
    """
    Mission 076: LoRAManager.add_files() rolls back lora.files to the
    exact previous list object if save() fails — no filesystem involved
    (LoRA.files only ever holds external path references, never copied),
    no dedicated event published, no other state touched.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.lora_manager = LoRAManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.lora = self.lora_manager.create("StyleA")
        self.lora_manager.select(self.lora.lora_id)
        self.lora_manager.add_files(["a.safetensors", "b.safetensors"])

    def test_add_files_succeeds_normally_when_save_works(self):
        added = self.lora_manager.add_files(["c.safetensors", "d.safetensors"])

        self.assertEqual(added, 2)
        self.assertEqual(self.lora.files, ["a.safetensors", "b.safetensors", "c.safetensors", "d.safetensors"])

    def test_add_files_save_failure_restores_exact_list_with_multiple_entries(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.add_files(["c.safetensors", "d.safetensors"])

        self.assertEqual(self.lora.files, ["a.safetensors", "b.safetensors"])
        self.assertIs(self.lora_manager.active_lora, self.lora)

    def test_add_files_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.add_files(["c.safetensors"])

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_add_files_save_failure_publishes_no_success_event(self):
        received = []
        self.event_bus.subscribe(WORKSPACE_SAVED, lambda payload: received.append(payload))

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.add_files(["c.safetensors"])

        self.assertEqual(received, [])

    def test_add_files_save_failure_does_not_affect_another_lora(self):
        other_lora = self.lora_manager.create("StyleB")
        self.lora_manager.select(other_lora.lora_id)
        self.lora_manager.add_files(["z.safetensors"])
        self.lora_manager.select(self.lora.lora_id)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.add_files(["c.safetensors"])

        self.assertEqual(other_lora.files, ["z.safetensors"])

    def test_add_files_save_failure_only_removes_what_this_call_actually_added(self):
        # new_paths dedups against lora.files as it stood before this
        # call — a failed attempt must retract exactly those new
        # entries, never touch the pre-existing ones, and never leave
        # duplicates behind if retried.
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.add_files(["a.safetensors", "c.safetensors", "d.safetensors"])

        self.assertEqual(self.lora.files, ["a.safetensors", "b.safetensors"])

    def test_retry_after_add_files_failure_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.add_files(["c.safetensors", "d.safetensors"])

        added = self.lora_manager.add_files(["c.safetensors", "d.safetensors"])

        self.assertEqual(added, 2)
        self.assertEqual(self.lora.files, ["a.safetensors", "b.safetensors", "c.safetensors", "d.safetensors"])
        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        self.assertEqual(
            aria["loras"][0]["files"],
            ["a.safetensors", "b.safetensors", "c.safetensors", "d.safetensors"],
        )


class LoRAManagerRemoveFilesRollbackTest(unittest.TestCase):
    """
    Mission 076: LoRAManager.remove_files() rolls back lora.files to the
    exact previous list object if save() fails — symmetric to
    LoRAManagerAddFilesRollbackTest.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.lora_manager = LoRAManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.lora = self.lora_manager.create("StyleA")
        self.lora_manager.select(self.lora.lora_id)
        self.lora_manager.add_files(["a.safetensors", "b.safetensors", "c.safetensors"])

    def test_remove_files_succeeds_normally_when_save_works(self):
        removed = self.lora_manager.remove_files(["a.safetensors", "c.safetensors"])

        self.assertEqual(removed, 2)
        self.assertEqual(self.lora.files, ["b.safetensors"])

    def test_remove_files_save_failure_restores_exact_list_with_multiple_entries(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.remove_files(["a.safetensors", "c.safetensors"])

        self.assertEqual(self.lora.files, ["a.safetensors", "b.safetensors", "c.safetensors"])
        self.assertIs(self.lora_manager.active_lora, self.lora)

    def test_remove_files_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.remove_files(["b.safetensors"])

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_remove_files_save_failure_publishes_no_success_event(self):
        received = []
        self.event_bus.subscribe(WORKSPACE_SAVED, lambda payload: received.append(payload))

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.remove_files(["a.safetensors"])

        self.assertEqual(received, [])

    def test_remove_files_save_failure_does_not_affect_another_lora(self):
        other_lora = self.lora_manager.create("StyleB")
        self.lora_manager.select(other_lora.lora_id)
        self.lora_manager.add_files(["z.safetensors"])
        self.lora_manager.select(self.lora.lora_id)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.remove_files(["a.safetensors"])

        self.assertEqual(other_lora.files, ["z.safetensors"])

    def test_remove_files_save_failure_preserves_preexisting_duplicate_entries(self):
        # LoRA.files can contain the same path twice (add_files() only
        # dedups against its own arrival batch and current content — a
        # hand-edited project.json could still carry a duplicate) — the
        # rollback must restore both instances exactly.
        self.lora.files.append("a.safetensors")
        original = list(self.lora.files)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.remove_files(["a.safetensors"])

        self.assertEqual(self.lora.files, original)

    def test_retry_after_remove_files_failure_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.remove_files(["a.safetensors", "c.safetensors"])

        removed = self.lora_manager.remove_files(["a.safetensors", "c.safetensors"])

        self.assertEqual(removed, 2)
        self.assertEqual(self.lora.files, ["b.safetensors"])
        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        self.assertEqual(aria["loras"][0]["files"], ["b.safetensors"])


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
        self.assertEqual(lora.thumbnail, thumbnail.thumbnail)

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
        self.assertTrue(lora_manager.delete(existing.lora_id).deleted)
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
        lora_library_manager = LoRALibraryManager(storage_directory=Path(self.tmp_dir) / "lora_library")
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings",
            lora_library_manager=lora_library_manager,
        )
        lora_page = LoRAPage(lora_manager, workspace_manager, lora_library_manager, application_settings_manager)

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
        lora_library_manager = LoRALibraryManager(storage_directory=Path(self.tmp_dir) / "lora_library")
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings",
            lora_library_manager=lora_library_manager,
        )
        lora_page = LoRAPage(lora_manager, workspace_manager, lora_library_manager, application_settings_manager)

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


class LoRAPageMetadataPersistenceFailureTest(unittest.TestCase):
    """
    Mission 073: LoRAPage.save_metadata() catches WorkspaceManagerError
    around lora_manager.update() and shows QMessageBox.critical() — on
    failure the four metadata widgets are resynced to the restored
    (previous) Domain values by calling update_loras(), the same idiom
    already established by DatasetsPage.rename_dataset() (Mission 070):
    the widgets must never keep showing the rejected new values, they
    must reflect exactly what was actually persisted.
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
        lora_library_manager = LoRALibraryManager(storage_directory=Path(self.tmp_dir) / "lora_library")
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings",
            lora_library_manager=lora_library_manager,
        )
        lora_page = LoRAPage(lora_manager, workspace_manager, lora_library_manager, application_settings_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, lora_page.update_loras)
        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, lora_page.update_loras)
        for event_name in LORA_EVENTS:
            event_bus.subscribe(event_name, lora_page.update_loras)

        return event_bus, workspace_manager, character_manager, lora_manager, lora_page

    def _prepare(self):
        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        lora_manager.update(
            lora.lora_id,
            engine="ComfyUI",
            architecture="SDXL",
            trigger_word="mytrigger",
            version="1.0",
        )
        lora_page.update_loras()
        return workspace_manager, lora_manager, lora_page, lora

    def test_save_metadata_failure_shows_error_and_lora_stays_visible(self):
        workspace_manager, lora_manager, lora_page, lora = self._prepare()

        lora_page.engine_edit.setText("ComfyUI2")
        lora_page.architecture_edit.setText("SD1.5")
        lora_page.trigger_word_edit.setText("newtrigger")
        lora_page.version_edit.setText("2.0")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.lora_page.QMessageBox.critical") as critical_mock:
            lora_page.save_metadata()

        self.assertTrue(critical_mock.called)
        self.assertEqual(lora_page.lora_list.count(), 1)
        self.assertIsNotNone(lora_page.lora_list.currentItem())
        self.assertEqual(lora_page.lora_list.currentItem().data(Qt.UserRole), lora.lora_id)

    def test_save_metadata_failure_restores_domain_and_resyncs_widgets_to_old_values(self):
        workspace_manager, lora_manager, lora_page, lora = self._prepare()

        lora_page.engine_edit.setText("ComfyUI2")
        lora_page.architecture_edit.setText("SD1.5")
        lora_page.trigger_word_edit.setText("newtrigger")
        lora_page.version_edit.setText("2.0")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.lora_page.QMessageBox.critical"):
            lora_page.save_metadata()

        # Domain rolled back to the pre-attempt values.
        self.assertEqual(lora.engine, "ComfyUI")
        self.assertEqual(lora.architecture, "SDXL")
        self.assertEqual(lora.trigger_word, "mytrigger")
        self.assertEqual(lora.version, "1.0")
        # Widgets resynced to those same restored values — never left
        # showing the rejected, now-phantom input.
        self.assertEqual(lora_page.engine_edit.text(), "ComfyUI")
        self.assertEqual(lora_page.architecture_edit.text(), "SDXL")
        self.assertEqual(lora_page.trigger_word_edit.text(), "mytrigger")
        self.assertEqual(lora_page.version_edit.text(), "1.0")

    def test_save_metadata_failure_leaves_project_json_unchanged(self):
        workspace_manager, lora_manager, lora_page, lora = self._prepare()

        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        lora_page.engine_edit.setText("ComfyUI2")
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.lora_page.QMessageBox.critical"):
            lora_page.save_metadata()

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_after_save_metadata_failure_actually_persists(self):
        workspace_manager, lora_manager, lora_page, lora = self._prepare()

        lora_page.engine_edit.setText("ComfyUI2")
        lora_page.architecture_edit.setText("SD1.5")
        lora_page.trigger_word_edit.setText("newtrigger")
        lora_page.version_edit.setText("2.0")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.lora_page.QMessageBox.critical"):
            lora_page.save_metadata()

        # Genuine retry: the user re-types the same values and saves again.
        lora_page.engine_edit.setText("ComfyUI2")
        lora_page.architecture_edit.setText("SD1.5")
        lora_page.trigger_word_edit.setText("newtrigger")
        lora_page.version_edit.setText("2.0")
        lora_page.save_metadata()

        self.assertEqual(lora.engine, "ComfyUI2")
        self.assertEqual(lora.architecture, "SD1.5")
        self.assertEqual(lora.trigger_word, "newtrigger")
        self.assertEqual(lora.version, "2.0")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        stored = next(l for l in aria["loras"] if l["lora_id"] == lora.lora_id)
        self.assertEqual(stored["engine"], "ComfyUI2")
        self.assertEqual(stored["version"], "2.0")


class LoRAPageAddToCentralLibraryTest(unittest.TestCase):
    """
    Mission 088: LoRAPage.add_to_central_library() — copies the active
    Character-scoped LoRA into the Application-level central library
    posed by Mission 087. A one-way, independent copy: no association
    back to Character.loras, no hash/deduplication.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"
        self.library_root = Path(self.tmp_dir) / "CentralLibrary"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.lora_manager = LoRAManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.lora_library_manager = LoRALibraryManager(
            storage_directory=Path(self.tmp_dir) / "lora_library"
        )
        self.application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings",
            lora_library_manager=self.lora_library_manager,
        )
        self.application_settings_manager.update(lora_library_path=str(self.library_root))

        self.lora_page = LoRAPage(
            self.lora_manager, self.workspace_manager, self.lora_library_manager, self.application_settings_manager
        )

        self.workspace_manager.create(self.folder)
        self.character_manager.create("Aria")

        self.lora = self.lora_manager.create("StyleA")
        self.lora_manager.select(self.lora.lora_id)
        self.lora_page.update_loras()

        self.source_file = Path(self.tmp_dir) / "external_weights.safetensors"
        self.source_file.write_bytes(b"weights")
        self.lora_manager.add_files([str(self.source_file)])

        self.thumb_source = str(Path(self.tmp_dir) / "external_thumb.png")
        _make_png(self.thumb_source)
        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileName",
            return_value=(self.thumb_source, ""),
        ):
            self.lora_page.choose_thumbnail()

        self.lora_page.engine_edit.setText("ComfyUI")
        self.lora_page.architecture_edit.setText("SDXL")
        self.lora_page.trigger_word_edit.setText("mytrigger")
        self.lora_page.version_edit.setText("2.1")
        self.lora_page.save_metadata()

    def test_button_disabled_without_active_lora(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        lora_manager = LoRAManager(character_manager, workspace_manager, event_bus=event_bus)
        lora_library_manager = LoRALibraryManager(storage_directory=Path(self.tmp_dir) / "other_library")
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "other_app_settings",
            lora_library_manager=lora_library_manager,
        )
        fresh_page = LoRAPage(lora_manager, workspace_manager, lora_library_manager, application_settings_manager)

        self.assertFalse(fresh_page.add_to_library_button.isEnabled())

    def test_button_enabled_after_selecting_a_lora(self):
        self.assertTrue(self.lora_page.add_to_library_button.isEnabled())

    def test_import_creates_central_entry_with_files_metadata_and_thumbnail(self):
        with patch("src.ui.pages.lora_page.QMessageBox.information") as info_mock:
            self.lora_page.add_to_central_library()

        entries = self.lora_library_manager.list_loras()
        self.assertEqual(len(entries), 1)
        entry = entries[0]

        self.assertEqual(entry.name, "StyleA")
        self.assertEqual(len(entry.files), 1)
        self.assertTrue(Path(entry.files[0]).exists())
        self.assertEqual(Path(entry.files[0]).read_bytes(), b"weights")
        self.assertEqual(Path(entry.files[0]).parent, self.library_root / entry.lora_id)

        self.assertNotEqual(entry.thumbnail, "")
        self.assertTrue(Path(entry.thumbnail).exists())

        self.assertEqual(entry.engine, "ComfyUI")
        self.assertEqual(entry.architecture, "SDXL")
        self.assertEqual(entry.trigger_word, "mytrigger")
        self.assertEqual(entry.version, "2.1")

        info_mock.assert_called_once()

    def test_import_multiple_files(self):
        second_source = Path(self.tmp_dir) / "extra_metadata.json"
        second_source.write_bytes(b'{"rank": 32}')
        self.lora_manager.add_files([str(second_source)])

        with patch("src.ui.pages.lora_page.QMessageBox.information"):
            self.lora_page.add_to_central_library()

        entry = self.lora_library_manager.list_loras()[0]
        self.assertEqual(len(entry.files), 2)

    def test_import_without_thumbnail(self):
        second_lora = self.lora_manager.create("StyleNoThumb")
        self.lora_manager.select(second_lora.lora_id)
        no_thumb_source = Path(self.tmp_dir) / "no_thumb_weights.safetensors"
        no_thumb_source.write_bytes(b"weights-2")
        self.lora_manager.add_files([str(no_thumb_source)])
        self.lora_page.update_loras()

        with patch("src.ui.pages.lora_page.QMessageBox.information"):
            self.lora_page.add_to_central_library()

        entry = next(e for e in self.lora_library_manager.list_loras() if e.name == "StyleNoThumb")
        self.assertEqual(entry.thumbnail, "")

    def test_import_missing_file_shows_error_and_creates_no_entry(self):
        self.source_file.unlink()

        with patch("src.ui.pages.lora_page.QMessageBox.critical") as critical_mock:
            self.lora_page.add_to_central_library()

        self.assertTrue(critical_mock.called)
        self.assertEqual(self.lora_library_manager.list_loras(), [])

    def test_import_missing_thumbnail_file_fails_entire_import(self):
        # Mission 088 contract: a declared-but-vanished thumbnail fails
        # the whole import (same all-or-nothing transaction as any
        # other file) — no silent tolerance, even though the weight
        # file is perfectly valid.
        Path(self.lora_manager.active_lora.thumbnail).unlink()

        with patch("src.ui.pages.lora_page.QMessageBox.critical") as critical_mock:
            self.lora_page.add_to_central_library()

        self.assertTrue(critical_mock.called)
        self.assertEqual(self.lora_library_manager.list_loras(), [])

    def test_persistence_failure_shows_error_and_creates_no_entry(self):
        with patch.object(
            LoRALibraryStorage, "save", side_effect=LoRALibraryStorageError("disk full")
        ), patch("src.ui.pages.lora_page.QMessageBox.critical") as critical_mock:
            self.lora_page.add_to_central_library()

        self.assertTrue(critical_mock.called)
        self.assertEqual(self.lora_library_manager.list_loras(), [])

    def test_repeated_import_creates_two_independent_entries(self):
        with patch("src.ui.pages.lora_page.QMessageBox.information"):
            self.lora_page.add_to_central_library()
            self.lora_page.add_to_central_library()

        entries = self.lora_library_manager.list_loras()
        self.assertEqual(len(entries), 2)
        self.assertNotEqual(entries[0].lora_id, entries[1].lora_id)
        self.assertNotEqual(Path(entries[0].files[0]).parent, Path(entries[1].files[0]).parent)
        for entry in entries:
            self.assertTrue(Path(entry.files[0]).exists())

    def test_source_files_and_thumbnail_unchanged_after_import(self):
        original_files = list(self.lora_manager.active_lora.files)
        original_thumbnail = self.lora_manager.active_lora.thumbnail

        with patch("src.ui.pages.lora_page.QMessageBox.information"):
            self.lora_page.add_to_central_library()

        self.assertEqual(self.lora_manager.active_lora.files, original_files)
        self.assertEqual(self.lora_manager.active_lora.thumbnail, original_thumbnail)
        for file_path in original_files:
            self.assertTrue(Path(file_path).exists())
        self.assertTrue(Path(original_thumbnail).exists())

    def test_dirty_metadata_cancel_aborts_import_and_keeps_draft(self):
        self.lora_page.engine_edit.setText("DirtyDraft")

        with patch.object(
            self.lora_page, "_confirm_discard_metadata_before_switch", return_value=QMessageBox.Cancel
        ):
            self.lora_page.add_to_central_library()

        self.assertEqual(self.lora_library_manager.list_loras(), [])
        self.assertTrue(self.lora_page._metadata_dirty)
        self.assertEqual(self.lora_page.engine_edit.text(), "DirtyDraft")

    def test_dirty_metadata_save_persists_then_imports_synchronized_values(self):
        self.lora_page.engine_edit.setText("DirtySavedValue")

        with patch.object(
            self.lora_page, "_confirm_discard_metadata_before_switch", return_value=QMessageBox.Save
        ), patch("src.ui.pages.lora_page.QMessageBox.information"):
            self.lora_page.add_to_central_library()

        self.assertFalse(self.lora_page._metadata_dirty)
        self.assertEqual(self.lora_manager.active_lora.engine, "DirtySavedValue")
        entry = self.lora_library_manager.list_loras()[0]
        self.assertEqual(entry.engine, "DirtySavedValue")

    def test_dirty_metadata_discard_restores_fields_then_imports_persisted_values(self):
        self.lora_page.engine_edit.setText("DirtyDiscardedValue")

        with patch.object(
            self.lora_page, "_confirm_discard_metadata_before_switch", return_value=QMessageBox.Discard
        ), patch("src.ui.pages.lora_page.QMessageBox.information"):
            self.lora_page.add_to_central_library()

        self.assertFalse(self.lora_page._metadata_dirty)
        self.assertEqual(self.lora_page.engine_edit.text(), "ComfyUI")
        self.assertEqual(self.lora_manager.active_lora.engine, "ComfyUI")
        entry = self.lora_library_manager.list_loras()[0]
        self.assertEqual(entry.engine, "ComfyUI")

    def test_dirty_metadata_save_failure_cancels_import_and_keeps_no_stale_draft(self):
        self.lora_page.engine_edit.setText("WillFailToSave")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch.object(
                    self.lora_page, "_confirm_discard_metadata_before_switch", return_value=QMessageBox.Save
                ), \
                patch("src.ui.pages.lora_page.QMessageBox.critical") as critical_mock:
            self.lora_page.add_to_central_library()

        self.assertTrue(critical_mock.called)
        self.assertEqual(self.lora_library_manager.list_loras(), [])
        self.assertFalse(self.lora_page._metadata_dirty)
        self.assertEqual(self.lora_page.engine_edit.text(), "ComfyUI")


class LoRAPageCentralLibraryTabTest(unittest.TestCase):
    """
    Mission 089: LoRAPage's "Bibliothèque centrale" tab — a purely
    Application-level, read-only consultation + deletion view over
    LoRALibraryManager, strictly separate from the "Personnage" tab's
    LoRAManager-backed data.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"
        self.library_root = Path(self.tmp_dir) / "CentralLibrary"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.lora_manager = LoRAManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.lora_library_manager = LoRALibraryManager(
            storage_directory=Path(self.tmp_dir) / "lora_library", event_bus=self.event_bus
        )
        self.application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings",
            lora_library_manager=self.lora_library_manager,
        )
        self.application_settings_manager.update(lora_library_path=str(self.library_root))

        self.lora_page = LoRAPage(
            self.lora_manager, self.workspace_manager, self.lora_library_manager, self.application_settings_manager
        )
        # Mission 089/090 wiring, mirrored from main_window.py: only these
        # three events ever refresh the central-library tab.
        self.event_bus.subscribe(LORA_LIBRARY_IMPORTED, self.lora_page.update_central_library)
        self.event_bus.subscribe(LORA_LIBRARY_DELETED, self.lora_page.update_central_library)
        self.event_bus.subscribe(LORA_LIBRARY_UPDATED, self.lora_page.update_central_library)

        self.workspace_manager.create(self.folder)
        self.character_manager.create("Aria")

    def _import_entry(self, name, with_thumbnail=True, engine="ComfyUI", architecture="SDXL",
                       trigger_word="mytrigger", version="1.0"):
        source_file = Path(self.tmp_dir) / f"{name}_weights.safetensors"
        source_file.write_bytes(b"weights")
        thumbnail_path = None
        if with_thumbnail:
            thumbnail_path = str(Path(self.tmp_dir) / f"{name}_thumb.png")
            _make_png(thumbnail_path)
        return self.lora_library_manager.import_lora(
            name=name,
            file_paths=[str(source_file)],
            library_root=self.library_root,
            thumbnail_path=thumbnail_path,
            engine=engine,
            architecture=architecture,
            trigger_word=trigger_word,
            version=version,
        )

    def test_tab_widget_has_two_tabs_in_the_right_order(self):
        self.assertEqual(self.lora_page.tab_widget.count(), 2)
        self.assertEqual(self.lora_page.tab_widget.tabText(0), "Personnage")
        self.assertEqual(self.lora_page.tab_widget.tabText(1), "Bibliothèque centrale")

    def test_character_tab_widgets_remain_present_and_parented_under_the_first_tab(self):
        # Mission 089 is a structural move only — every widget name the
        # test suite/production code already depends on must still
        # resolve to the same object, now living inside the first tab.
        character_tab = self.lora_page.tab_widget.widget(0)
        self.assertIsNotNone(character_tab)
        self.assertTrue(character_tab.isAncestorOf(self.lora_page.lora_list))
        self.assertTrue(character_tab.isAncestorOf(self.lora_page.engine_edit))
        self.assertTrue(character_tab.isAncestorOf(self.lora_page.add_to_library_button))

    def test_empty_library_shows_no_entries(self):
        self.assertEqual(self.lora_page.library_list.count(), 0)
        self.assertFalse(self.lora_page.delete_from_library_button.isEnabled())

    def test_single_entry_displays_name_and_file_count(self):
        self._import_entry("StyleA")
        self.lora_page.update_central_library()

        self.assertEqual(self.lora_page.library_list.count(), 1)
        self.assertEqual(self.lora_page.library_list.item(0).text(), "StyleA (1 fichier(s))")

    def test_multiple_entries_are_sorted_alphabetically_case_insensitively(self):
        self._import_entry("zebra")
        self._import_entry("Alpha")
        self._import_entry("mango")
        self.lora_page.update_central_library()

        names = [self.lora_page.library_list.item(i).text() for i in range(3)]
        self.assertEqual(names, [
            "Alpha (1 fichier(s))",
            "mango (1 fichier(s))",
            "zebra (1 fichier(s))",
        ])

    def test_selecting_entry_shows_name_and_all_four_metadata_fields(self):
        self._import_entry(
            "StyleA", engine="ComfyUI", architecture="SDXL", trigger_word="mytrigger", version="2.1"
        )
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        self.assertEqual(self.lora_page.library_name_edit.text(), "StyleA")
        self.assertEqual(self.lora_page.library_engine_edit.text(), "ComfyUI")
        self.assertEqual(self.lora_page.library_architecture_edit.text(), "SDXL")
        self.assertEqual(self.lora_page.library_trigger_word_edit.text(), "mytrigger")
        self.assertEqual(self.lora_page.library_version_edit.text(), "2.1")

    def test_thumbnail_displayed_when_present(self):
        self._import_entry("StyleA", with_thumbnail=True)
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        self.assertIsNotNone(self.lora_page.library_thumbnail_label.pixmap())
        self.assertFalse(self.lora_page.library_thumbnail_label.pixmap().isNull())

    def test_no_thumbnail_shows_placeholder_message(self):
        self._import_entry("StyleA", with_thumbnail=False)
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        self.assertEqual(self.lora_page.library_thumbnail_label.text(), NO_THUMBNAIL_MESSAGE)

    def test_thumbnail_with_missing_file_shows_unavailable_without_crash(self):
        entry = self._import_entry("StyleA", with_thumbnail=True)
        Path(entry.thumbnail).unlink()
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        self.assertEqual(self.lora_page.library_thumbnail_label.text(), UNAVAILABLE_MESSAGE)

    def test_selecting_an_entry_enables_delete_button(self):
        self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        self.assertTrue(self.lora_page.delete_from_library_button.isEnabled())

    def test_deselecting_disables_delete_button(self):
        self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_list.setCurrentItem(None)

        self.assertFalse(self.lora_page.delete_from_library_button.isEnabled())
        self.assertEqual(self.lora_page.library_engine_edit.text(), "")

    def _confirm_delete_from_library(self, accept: bool):
        # Mission 089: mirrors LoRAManagerPhysicalDeletionTest._confirm_delete()
        # — the established pattern in this file for a plain (non
        # Save/Discard/Cancel) two-button QMessageBox confirmation: patch
        # the whole class, give addButton() two distinct sentinels in the
        # exact order delete_from_library() calls it (Supprimer, Annuler),
        # and make clickedButton() return whichever sentinel corresponds
        # to the simulated user choice.
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

    def test_cancel_confirmation_deletes_nothing(self):
        entry = self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        self._confirm_delete_from_library(accept=False)

        with patch.object(self.lora_library_manager, "delete") as delete_mock:
            self.lora_page.delete_from_library()
            delete_mock.assert_not_called()

        self.assertEqual(len(self.lora_library_manager.list_loras()), 1)
        self.assertEqual(self.lora_library_manager.list_loras()[0].lora_id, entry.lora_id)

    def test_confirmed_delete_removes_entry_from_registry_and_disk(self):
        entry = self._import_entry("StyleA")
        entry_folder = Path(entry.files[0]).parent
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        self._confirm_delete_from_library(accept=True)

        self.lora_page.delete_from_library()

        self.assertEqual(self.lora_library_manager.list_loras(), [])
        self.assertFalse(entry_folder.exists())
        self.assertEqual(self.lora_page.library_list.count(), 0)
        self.assertFalse(self.lora_page.delete_from_library_button.isEnabled())
        self.assertEqual(self.lora_page.library_engine_edit.text(), "")

    def test_delete_manager_error_shows_critical_and_keeps_entry(self):
        entry = self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        mock_cls = self._confirm_delete_from_library(accept=True)

        with patch.object(LoRALibraryStorage, "save", side_effect=LoRALibraryStorageError("disk full")):
            self.lora_page.delete_from_library()

        mock_cls.critical.assert_called_once()
        self.assertEqual(len(self.lora_library_manager.list_loras()), 1)
        self.assertEqual(self.lora_library_manager.list_loras()[0].lora_id, entry.lora_id)

    def test_delete_cleanup_failed_keeps_deletion_and_warns(self):
        self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        mock_cls = self._confirm_delete_from_library(accept=True)

        with patch.object(WorkspaceStorage, "delete_folder", side_effect=WorkspaceStorageError("locked")):
            self.lora_page.delete_from_library()

        mock_cls.warning.assert_called_once()
        self.assertEqual(self.lora_library_manager.list_loras(), [])

    def test_import_via_add_to_central_library_appears_automatically_via_event(self):
        self.lora = self.lora_manager.create("StyleA")
        self.lora_manager.select(self.lora.lora_id)
        self.lora_page.update_loras()
        source_file = Path(self.tmp_dir) / "external_weights.safetensors"
        source_file.write_bytes(b"weights")
        self.lora_manager.add_files([str(source_file)])

        self.assertEqual(self.lora_page.library_list.count(), 0)

        with patch("src.ui.pages.lora_page.QMessageBox.information"):
            self.lora_page.add_to_central_library()

        self.assertEqual(self.lora_page.library_list.count(), 1)
        self.assertEqual(self.lora_page.library_list.item(0).text(), "StyleA (1 fichier(s))")

    def test_delete_updates_view_via_event(self):
        self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.assertEqual(self.lora_page.library_list.count(), 1)

        # Direct Manager call — same event LORA_LIBRARY_DELETED as a real
        # confirmed UI deletion, without the modal dialog.
        entry = self.lora_library_manager.list_loras()[0]
        self.lora_library_manager.delete(entry.lora_id, self.library_root)

        self.assertEqual(self.lora_page.library_list.count(), 0)

    def test_workspace_and_character_events_never_affect_the_central_library_tab(self):
        self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.assertEqual(self.lora_page.library_list.count(), 1)

        second_folder = Path(self.tmp_dir) / "SecondProject"
        self.workspace_manager.create(second_folder)
        self.character_manager.create("Nova")
        self.workspace_manager.rename("Renamed")
        self.workspace_manager.close()

        self.assertEqual(self.lora_page.library_list.count(), 1)
        self.assertEqual(self.lora_page.library_list.item(0).text(), "StyleA (1 fichier(s))")

    # --- Mission 090: central-library entry editing ---

    def test_selecting_entry_disables_save_button_by_default(self):
        self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        self.assertFalse(self.lora_page.save_library_metadata_button.isEnabled())

    def test_typing_in_any_field_enables_save_button(self):
        self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        self.lora_page.library_trigger_word_edit.setText("changed")

        self.assertTrue(self.lora_page.save_library_metadata_button.isEnabled())

    def test_save_button_disabled_after_successful_save(self):
        self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_version_edit.setText("9.9")

        self.lora_page.save_library_metadata()

        self.assertFalse(self.lora_page._library_metadata_dirty)
        self.assertFalse(self.lora_page.save_library_metadata_button.isEnabled())

    def test_save_button_disabled_after_save_failure_rollback(self):
        self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_version_edit.setText("9.9")

        with patch.object(LoRALibraryStorage, "save", side_effect=LoRALibraryStorageError("disk full")), \
                patch("src.ui.pages.lora_page.QMessageBox.critical") as critical_mock:
            self.lora_page.save_library_metadata()

        self.assertTrue(critical_mock.called)
        self.assertFalse(self.lora_page._library_metadata_dirty)
        self.assertFalse(self.lora_page.save_library_metadata_button.isEnabled())
        self.assertEqual(self.lora_page.library_version_edit.text(), "1.0")

    def test_save_library_metadata_persists_single_field_change(self):
        entry = self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_trigger_word_edit.setText("newtrigger")

        self.lora_page.save_library_metadata()

        self.assertEqual(self.lora_library_manager.get(entry.lora_id).trigger_word, "newtrigger")

    def test_save_library_metadata_persists_all_five_fields_and_updates_list_row(self):
        entry = self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        self.lora_page.library_name_edit.setText("RenamedStyle")
        self.lora_page.library_engine_edit.setText("Kohya")
        self.lora_page.library_architecture_edit.setText("Flux")
        self.lora_page.library_trigger_word_edit.setText("newtrigger")
        self.lora_page.library_version_edit.setText("2.0")

        self.lora_page.save_library_metadata()

        stored = self.lora_library_manager.get(entry.lora_id)
        self.assertEqual(stored.name, "RenamedStyle")
        self.assertEqual(stored.engine, "Kohya")
        self.assertEqual(stored.architecture, "Flux")
        self.assertEqual(stored.trigger_word, "newtrigger")
        self.assertEqual(stored.version, "2.0")
        self.assertEqual(self.lora_page.library_list.count(), 1)
        self.assertEqual(self.lora_page.library_list.item(0).text(), "RenamedStyle (1 fichier(s))")
        self.assertEqual(self.lora_page.library_list.currentItem().data(Qt.UserRole), entry.lora_id)

    def test_save_library_metadata_no_effective_change_is_a_silent_no_op(self):
        self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        # Mission 090 subtle case: typed away, then reverted to the exact
        # original value before ever clicking Save.
        self.lora_page.library_engine_edit.setText("Different")
        self.lora_page.library_engine_edit.setText("ComfyUI")

        events = []
        self.event_bus.subscribe(LORA_LIBRARY_UPDATED, lambda payload: events.append(payload))

        self.lora_page.save_library_metadata()

        self.assertEqual(events, [])
        self.assertFalse(self.lora_page._library_metadata_dirty)
        self.assertFalse(self.lora_page.save_library_metadata_button.isEnabled())

    def test_save_library_metadata_failure_shows_critical_and_restores_previous_values(self):
        entry = self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("WillFail")

        with patch.object(LoRALibraryStorage, "save", side_effect=LoRALibraryStorageError("disk full")), \
                patch("src.ui.pages.lora_page.QMessageBox.critical") as critical_mock:
            self.lora_page.save_library_metadata()

        self.assertTrue(critical_mock.called)
        self.assertEqual(self.lora_page.library_engine_edit.text(), "ComfyUI")
        self.assertEqual(self.lora_library_manager.get(entry.lora_id).engine, "ComfyUI")

    def test_save_library_metadata_with_no_selection_is_a_no_op(self):
        self.lora_page.save_library_metadata()

    def test_switching_selection_while_dirty_cancel_keeps_draft_and_selection(self):
        alpha = self._import_entry("Alpha")
        self._import_entry("Zebra")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("DirtyDraft")

        with patch.object(
            self.lora_page, "_confirm_discard_library_metadata_before_switch",
            return_value=QMessageBox.Cancel,
        ):
            self.lora_page.library_list.setCurrentRow(1)

        self.assertTrue(self.lora_page._library_metadata_dirty)
        self.assertEqual(self.lora_page.library_engine_edit.text(), "DirtyDraft")
        self.assertEqual(self.lora_page._loaded_library_lora_id, alpha.lora_id)
        self.assertEqual(self.lora_page.library_list.currentItem().data(Qt.UserRole), alpha.lora_id)

    def test_switching_selection_while_dirty_discard_abandons_draft_and_loads_new_entry(self):
        self._import_entry("Alpha")
        zebra = self._import_entry("Zebra")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("DirtyDraft")

        with patch.object(
            self.lora_page, "_confirm_discard_library_metadata_before_switch",
            return_value=QMessageBox.Discard,
        ):
            self.lora_page.library_list.setCurrentRow(1)

        self.assertFalse(self.lora_page._library_metadata_dirty)
        self.assertEqual(self.lora_page._loaded_library_lora_id, zebra.lora_id)
        self.assertEqual(self.lora_page.library_name_edit.text(), "Zebra")
        self.assertEqual(self.lora_library_manager.get(zebra.lora_id).engine, "ComfyUI")

    def test_switching_selection_while_dirty_save_persists_then_loads_new_entry(self):
        alpha = self._import_entry("Alpha")
        zebra = self._import_entry("Zebra")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("SavedBeforeSwitch")

        with patch.object(
            self.lora_page, "_confirm_discard_library_metadata_before_switch",
            return_value=QMessageBox.Save,
        ):
            self.lora_page.library_list.setCurrentRow(1)

        self.assertEqual(self.lora_library_manager.get(alpha.lora_id).engine, "SavedBeforeSwitch")
        self.assertFalse(self.lora_page._library_metadata_dirty)
        self.assertEqual(self.lora_page._loaded_library_lora_id, zebra.lora_id)
        self.assertEqual(self.lora_page.library_name_edit.text(), "Zebra")
        self.assertEqual(self.lora_page.library_list.currentItem().data(Qt.UserRole), zebra.lora_id)

    def test_switching_selection_while_dirty_save_failure_keeps_previous_selection_and_draft(self):
        alpha = self._import_entry("Alpha")
        self._import_entry("Zebra")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("WillFail")

        with patch.object(LoRALibraryStorage, "save", side_effect=LoRALibraryStorageError("disk full")), \
                patch.object(
                    self.lora_page, "_confirm_discard_library_metadata_before_switch",
                    return_value=QMessageBox.Save,
                ), \
                patch("src.ui.pages.lora_page.QMessageBox.critical") as critical_mock:
            self.lora_page.library_list.setCurrentRow(1)

        self.assertTrue(critical_mock.called)
        self.assertTrue(self.lora_page._library_metadata_dirty)
        self.assertEqual(self.lora_page._loaded_library_lora_id, alpha.lora_id)
        self.assertEqual(self.lora_page.library_list.currentItem().data(Qt.UserRole), alpha.lora_id)
        self.assertEqual(self.lora_page.library_engine_edit.text(), "WillFail")

    def test_delete_confirmation_mentions_unsaved_changes_when_editing_that_entry(self):
        self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("Dirty")

        mock_cls = self._confirm_delete_from_library(accept=False)
        self.lora_page.delete_from_library()

        message = mock_cls.return_value.setText.call_args[0][0]
        self.assertIn("non enregistrées", message)

    def test_delete_confirmation_is_plain_when_not_dirty(self):
        self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        mock_cls = self._confirm_delete_from_library(accept=False)
        self.lora_page.delete_from_library()

        message = mock_cls.return_value.setText.call_args[0][0]
        self.assertNotIn("non enregistrées", message)

    def test_deleting_the_currently_edited_entry_clears_dirty_state_and_panel(self):
        self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("Dirty")

        self._confirm_delete_from_library(accept=True)
        self.lora_page.delete_from_library()

        self.assertFalse(self.lora_page._library_metadata_dirty)
        self.assertIsNone(self.lora_page._loaded_library_lora_id)
        self.assertEqual(self.lora_page.library_name_edit.text(), "")
        self.assertFalse(self.lora_page.save_library_metadata_button.isEnabled())

    def test_unrelated_import_event_while_dirty_preserves_draft_and_updates_list(self):
        self._import_entry("Alpha")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("DirtyDraft")

        self._import_entry("Beta")

        self.assertTrue(self.lora_page._library_metadata_dirty)
        self.assertEqual(self.lora_page.library_engine_edit.text(), "DirtyDraft")
        self.assertEqual(self.lora_page.library_list.count(), 2)
        self.assertEqual(self.lora_page.library_list.currentItem().text(), "Alpha (1 fichier(s))")

    def test_unrelated_delete_event_while_dirty_preserves_draft_and_updates_list(self):
        self._import_entry("Alpha")
        other = self._import_entry("Beta")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("DirtyDraft")

        self.lora_library_manager.delete(other.lora_id, self.library_root)

        self.assertTrue(self.lora_page._library_metadata_dirty)
        self.assertEqual(self.lora_page.library_engine_edit.text(), "DirtyDraft")
        self.assertEqual(self.lora_page.library_list.count(), 1)
        self.assertEqual(self.lora_page.library_list.currentItem().text(), "Alpha (1 fichier(s))")

    def test_confirm_library_context_change_not_dirty_returns_true_without_dialog(self):
        self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        with patch.object(
            self.lora_page, "_confirm_discard_library_metadata_before_switch"
        ) as dialog_mock:
            result = self.lora_page.confirm_library_context_change()

        self.assertTrue(result)
        dialog_mock.assert_not_called()

    def test_confirm_library_context_change_cancel_returns_false_and_keeps_draft(self):
        self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("Dirty")

        with patch.object(
            self.lora_page, "_confirm_discard_library_metadata_before_switch",
            return_value=QMessageBox.Cancel,
        ):
            result = self.lora_page.confirm_library_context_change()

        self.assertFalse(result)
        self.assertTrue(self.lora_page._library_metadata_dirty)

    def test_confirm_library_context_change_discard_returns_true_and_clears_draft(self):
        entry = self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("Dirty")

        with patch.object(
            self.lora_page, "_confirm_discard_library_metadata_before_switch",
            return_value=QMessageBox.Discard,
        ):
            result = self.lora_page.confirm_library_context_change()

        self.assertTrue(result)
        self.assertFalse(self.lora_page._library_metadata_dirty)
        self.assertEqual(self.lora_library_manager.get(entry.lora_id).engine, "ComfyUI")

    def test_confirm_library_context_change_save_returns_true_and_persists(self):
        entry = self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("SavedOnClose")

        with patch.object(
            self.lora_page, "_confirm_discard_library_metadata_before_switch",
            return_value=QMessageBox.Save,
        ):
            result = self.lora_page.confirm_library_context_change()

        self.assertTrue(result)
        self.assertFalse(self.lora_page._library_metadata_dirty)
        self.assertEqual(self.lora_library_manager.get(entry.lora_id).engine, "SavedOnClose")

    def test_confirm_library_context_change_save_failure_returns_false_and_keeps_draft(self):
        self._import_entry("StyleA")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("WillFail")

        with patch.object(LoRALibraryStorage, "save", side_effect=LoRALibraryStorageError("disk full")), \
                patch.object(
                    self.lora_page, "_confirm_discard_library_metadata_before_switch",
                    return_value=QMessageBox.Save,
                ), \
                patch("src.ui.pages.lora_page.QMessageBox.critical") as critical_mock:
            result = self.lora_page.confirm_library_context_change()

        self.assertFalse(result)
        self.assertTrue(critical_mock.called)
        self.assertTrue(self.lora_page._library_metadata_dirty)


class LoRAPageFilesPersistenceFailureTest(unittest.TestCase):
    """
    Mission 076: LoRAPage.import_files()/remove_selected_files() catch
    WorkspaceManagerError around add_files()/remove_files() and show
    QMessageBox.critical() — files_list is resynced to the restored
    (previous) Domain state via update_loras(), the same idiom already
    established by LoRAPageMetadataPersistenceFailureTest (Mission 073).
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
        lora_library_manager = LoRALibraryManager(storage_directory=Path(self.tmp_dir) / "lora_library")
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings",
            lora_library_manager=lora_library_manager,
        )
        lora_page = LoRAPage(lora_manager, workspace_manager, lora_library_manager, application_settings_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, lora_page.update_loras)
        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, lora_page.update_loras)
        for event_name in LORA_EVENTS:
            event_bus.subscribe(event_name, lora_page.update_loras)

        return event_bus, workspace_manager, character_manager, lora_manager, lora_page

    def _prepare(self, existing_files=("a.safetensors", "b.safetensors")):
        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        if existing_files:
            lora_manager.add_files(list(existing_files))
        lora_page.update_loras()
        return workspace_manager, lora_manager, lora_page, lora

    def test_import_files_failure_shows_error_and_adds_nothing(self):
        workspace_manager, lora_manager, lora_page, lora = self._prepare()

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileNames",
            return_value=(["c.safetensors"], ""),
        ), patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.lora_page.QMessageBox.critical") as critical_mock:
            lora_page.import_files()

        self.assertTrue(critical_mock.called)
        self.assertEqual(lora.files, ["a.safetensors", "b.safetensors"])
        self.assertEqual(
            [lora_page.files_list.item(i).text() for i in range(lora_page.files_list.count())],
            ["a.safetensors", "b.safetensors"],
        )

    def test_import_files_failure_leaves_project_json_unchanged(self):
        workspace_manager, lora_manager, lora_page, lora = self._prepare()

        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileNames",
            return_value=(["c.safetensors"], ""),
        ), patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.lora_page.QMessageBox.critical"):
            lora_page.import_files()

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_after_import_files_failure_actually_imports(self):
        workspace_manager, lora_manager, lora_page, lora = self._prepare()

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileNames",
            return_value=(["c.safetensors"], ""),
        ), patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.lora_page.QMessageBox.critical"):
            lora_page.import_files()

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileNames",
            return_value=(["c.safetensors"], ""),
        ), patch("src.ui.pages.lora_page.QMessageBox.information"):
            lora_page.import_files()

        self.assertEqual(lora.files, ["a.safetensors", "b.safetensors", "c.safetensors"])
        self.assertEqual(
            [lora_page.files_list.item(i).text() for i in range(lora_page.files_list.count())],
            ["a.safetensors", "b.safetensors", "c.safetensors"],
        )

    def test_remove_selected_files_failure_shows_error_and_removes_nothing(self):
        workspace_manager, lora_manager, lora_page, lora = self._prepare(
            existing_files=("a.safetensors", "b.safetensors", "c.safetensors")
        )
        lora_page.files_list.item(0).setSelected(True)
        lora_page.files_list.item(2).setSelected(True)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.lora_page.QMessageBox.critical") as critical_mock:
            lora_page.remove_selected_files()

        self.assertTrue(critical_mock.called)
        self.assertEqual(lora.files, ["a.safetensors", "b.safetensors", "c.safetensors"])
        self.assertEqual(
            [lora_page.files_list.item(i).text() for i in range(lora_page.files_list.count())],
            ["a.safetensors", "b.safetensors", "c.safetensors"],
        )

    def test_remove_selected_files_failure_leaves_project_json_unchanged(self):
        workspace_manager, lora_manager, lora_page, lora = self._prepare()
        lora_page.files_list.item(0).setSelected(True)

        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.lora_page.QMessageBox.critical"):
            lora_page.remove_selected_files()

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_after_remove_selected_files_failure_actually_removes(self):
        workspace_manager, lora_manager, lora_page, lora = self._prepare()
        lora_page.files_list.item(0).setSelected(True)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.lora_page.QMessageBox.critical"):
            lora_page.remove_selected_files()

        lora_page.files_list.item(0).setSelected(True)
        lora_page.remove_selected_files()

        self.assertEqual(lora.files, ["b.safetensors"])
        self.assertEqual(
            [lora_page.files_list.item(i).text() for i in range(lora_page.files_list.count())],
            ["b.safetensors"],
        )
        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        self.assertEqual(aria["loras"][0]["files"], ["b.safetensors"])


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
        lora_library_manager = LoRALibraryManager(storage_directory=Path(self.tmp_dir) / "lora_library")
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings",
            lora_library_manager=lora_library_manager,
        )
        lora_page = LoRAPage(lora_manager, workspace_manager, lora_library_manager, application_settings_manager)

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
        lora_library_manager = LoRALibraryManager(storage_directory=Path(self.tmp_dir) / "lora_library")
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings",
            lora_library_manager=lora_library_manager,
        )
        lora_page = LoRAPage(lora_manager, workspace_manager, lora_library_manager, application_settings_manager)

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
        self.assertEqual(lora.thumbnail, result.thumbnail)

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

    def test_rename_save_failure_shows_error_and_restores_widget_to_previous_name(self):

        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)

        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)

        lora_page.name_edit.setText("StyleA Renamed")
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.lora_page.QMessageBox.critical") as critical_mock:
            lora_page.name_edit.editingFinished.emit()

        self.assertTrue(critical_mock.called)
        self.assertEqual(lora.name, "StyleA")
        self.assertEqual(lora_page.name_edit.text(), "StyleA")
        self.assertTrue(lora_page.lora_list.item(0).text().startswith("StyleA"))
        self.assertFalse(lora_page.lora_list.item(0).text().startswith("StyleA Renamed"))

    def test_retry_after_rename_save_failure_actually_renames(self):

        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)

        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)

        lora_page.name_edit.setText("StyleA Renamed")
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.lora_page.QMessageBox.critical"):
            lora_page.name_edit.editingFinished.emit()

        lora_page.name_edit.setText("StyleA Renamed")
        lora_page.name_edit.editingFinished.emit()

        self.assertEqual(lora.name, "StyleA Renamed")
        self.assertTrue(lora_page.lora_list.item(0).text().startswith("StyleA Renamed"))


class LoRAManagerDeleteRollbackTest(unittest.TestCase):
    """
    Mission 068: LoRAManager.delete() rolls back the in-memory removal
    (and active_lora_id) if save() fails — Domain-only mutation (the
    physical files under files/thumbnail are never touched by delete()),
    so the rollback is a simple local re-insertion at the original
    index, never a full Workspace snapshot.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.lora_manager = LoRAManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        self.character_manager.create("Aria")

        self.lora_a = self.lora_manager.create("Alpha")
        self.lora_b = self.lora_manager.create("Beta")
        self.lora_c = self.lora_manager.create("Gamma")
        self.lora_manager.select(self.lora_b.lora_id)

    def test_delete_succeeds_normally_when_save_works(self):
        result = self.lora_manager.delete(self.lora_b.lora_id)

        self.assertTrue(result.deleted)
        self.assertFalse(result.cleanup_failed)
        self.assertIsNone(result.residual_path)
        self.assertEqual(
            [l.lora_id for l in self.lora_manager.loras],
            [self.lora_a.lora_id, self.lora_c.lora_id],
        )
        self.assertIsNone(self.lora_manager.active_lora_id)

    def test_delete_save_failure_restores_object_at_original_index(self):
        received = []
        self.event_bus.subscribe(LORA_DELETED, lambda payload: received.append(payload))

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.delete(self.lora_b.lora_id)

        loras = self.lora_manager.loras
        self.assertEqual(
            [l.lora_id for l in loras],
            [self.lora_a.lora_id, self.lora_b.lora_id, self.lora_c.lora_id],
        )
        self.assertIs(loras[1], self.lora_b)
        self.assertEqual(received, [])

    def test_delete_save_failure_restores_active_lora_id(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.delete(self.lora_b.lora_id)

        self.assertEqual(self.lora_manager.active_lora_id, self.lora_b.lora_id)

    def test_delete_save_failure_never_touches_an_unrelated_active_id(self):
        self.lora_manager.select(self.lora_a.lora_id)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.delete(self.lora_b.lora_id)

        self.assertEqual(self.lora_manager.active_lora_id, self.lora_a.lora_id)

    def test_delete_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.delete(self.lora_b.lora_id)

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_after_save_failure_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.delete(self.lora_b.lora_id)

        result = self.lora_manager.delete(self.lora_b.lora_id)

        self.assertTrue(result.deleted)
        self.assertEqual(
            [l.lora_id for l in self.lora_manager.loras],
            [self.lora_a.lora_id, self.lora_c.lora_id],
        )


class LoRAManagerPhysicalDeletionTest(unittest.TestCase):
    """
    Mission 075: LoRAManager.delete() now also transactionally removes
    the LoRA's private folder (models/loras/<id>/) — created lazily
    only by set_thumbnail(), never containing any of LoRA.files (those
    are external references, never copied). Covers the folder-move/
    persist/permanent-delete pipeline with real files on disk,
    independently of the pre-existing Domain-only rollback already
    covered by LoRAManagerDeleteRollbackTest (which never touches the
    filesystem, since its lora_b never receives a thumbnail).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"
        self.source_dir = Path(self.tmp_dir) / "External"
        self.source_dir.mkdir()

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.lora_manager = LoRAManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        self.character_manager.create("Aria")

        self.lora = self.lora_manager.create("Style A")
        self.lora_manager.select(self.lora.lora_id)

        self.thumbnail_source = self.source_dir / "thumb.png"
        self.thumbnail_source.write_bytes(b"fake png data")

    def _lora_folder(self):
        return self.folder / "models" / "loras" / self.lora.lora_id

    def test_delete_with_no_physical_folder_is_unaffected(self):
        # Never got a thumbnail -> no folder was ever created.
        result = self.lora_manager.delete(self.lora.lora_id)

        self.assertTrue(result.deleted)
        self.assertFalse(result.cleanup_failed)
        self.assertFalse((self.folder / ".trash").exists())

    def test_delete_removes_the_physical_folder_entirely(self):
        self.lora_manager.set_thumbnail(self.lora.lora_id, str(self.thumbnail_source))
        lora_folder = self._lora_folder()
        self.assertTrue(lora_folder.exists())

        result = self.lora_manager.delete(self.lora.lora_id)

        self.assertTrue(result.deleted)
        self.assertFalse(result.cleanup_failed)
        self.assertFalse(lora_folder.exists())
        trash_root = self.folder / ".trash"
        self.assertTrue(not trash_root.exists() or list(trash_root.iterdir()) == [])

    def test_delete_never_touches_files_referenced_externally(self):
        # LoRA.files holds external references only — never copied into
        # the private folder, and must never be affected by its deletion.
        external_file = self.source_dir / "model.safetensors"
        external_file.write_bytes(b"weights")
        self.lora_manager.add_files([str(external_file)])
        self.lora_manager.set_thumbnail(self.lora.lora_id, str(self.thumbnail_source))

        self.lora_manager.delete(self.lora.lora_id)

        self.assertTrue(external_file.exists())

    def test_delete_failure_to_move_folder_aborts_before_any_mutation(self):
        self.lora_manager.set_thumbnail(self.lora.lora_id, str(self.thumbnail_source))
        lora_folder = self._lora_folder()

        with patch.object(
            WorkspaceStorage, "rename_folder",
            side_effect=WorkspaceStorageError("locked by another process"),
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.delete(self.lora.lora_id)

        self.assertTrue(lora_folder.exists())
        self.assertEqual(
            [l.lora_id for l in self.lora_manager.loras],
            [self.lora.lora_id],
        )

    def test_delete_save_failure_restores_folder_to_its_original_location_with_content(self):
        self.lora_manager.set_thumbnail(self.lora.lora_id, str(self.thumbnail_source))
        lora_folder = self._lora_folder()
        original_contents = [p.name for p in lora_folder.iterdir()]

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.delete(self.lora.lora_id)

        self.assertTrue(lora_folder.exists())
        self.assertEqual([p.name for p in lora_folder.iterdir()], original_contents)
        self.assertEqual(
            [l.lora_id for l in self.lora_manager.loras],
            [self.lora.lora_id],
        )
        # .trash/ itself (an empty staging directory) may still exist —
        # only its content, the actually moved folder, must be gone.
        trash_root = self.folder / ".trash"
        self.assertTrue(not trash_root.exists() or list(trash_root.iterdir()) == [])

    def test_delete_double_failure_still_restores_domain_and_reports_manual_recovery(self):
        self.lora_manager.set_thumbnail(self.lora.lora_id, str(self.thumbnail_source))
        lora_folder = self._lora_folder()
        original_contents = [p.name for p in lora_folder.iterdir()]
        other = self.lora_manager.create("Unrelated")

        original_rename_folder = WorkspaceStorage.rename_folder
        call_count = {"n": 0}

        def flaky_rename_folder(old_root, new_root):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return original_rename_folder(old_root, new_root)
            raise WorkspaceStorageError("still locked by another process")

        with patch.object(WorkspaceStorage, "rename_folder", side_effect=flaky_rename_folder), \
                patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError) as ctx:
                self.lora_manager.delete(self.lora.lora_id)

        loras = self.lora_manager.loras
        self.assertEqual(
            [l.lora_id for l in loras],
            [self.lora.lora_id, other.lora_id],
        )
        self.assertIs(loras[0], self.lora)

        self.assertFalse(lora_folder.exists())
        trash_root = self.folder / ".trash"
        residual = list(trash_root.iterdir())
        self.assertEqual(len(residual), 1)
        self.assertEqual([p.name for p in residual[0].iterdir()], original_contents)

        self.assertEqual(len(self.lora_manager.loras), 2)

        message = str(ctx.exception)
        self.assertIn(str(residual[0]), message)
        self.assertIn(str(lora_folder), message)
        self.assertIn("restored", message)

    def test_delete_permanent_cleanup_failure_never_rolls_back_the_persisted_deletion(self):
        self.lora_manager.set_thumbnail(self.lora.lora_id, str(self.thumbnail_source))
        lora_folder = self._lora_folder()

        with patch.object(WorkspaceStorage, "delete_folder", side_effect=WorkspaceStorageError("locked")):
            result = self.lora_manager.delete(self.lora.lora_id)

        self.assertTrue(result.deleted)
        self.assertTrue(result.cleanup_failed)
        self.assertIsNotNone(result.residual_path)
        self.assertFalse(lora_folder.exists())
        self.assertEqual(self.lora_manager.loras, [])
        self.assertTrue(Path(result.residual_path).exists())

    def test_delete_never_touches_an_unrelated_loras_folder(self):
        self.lora_manager.set_thumbnail(self.lora.lora_id, str(self.thumbnail_source))
        other = self.lora_manager.create("Unrelated")
        other_thumb = self.source_dir / "other_thumb.png"
        other_thumb.write_bytes(b"other data")
        self.lora_manager.select(other.lora_id)
        self.lora_manager.set_thumbnail(other.lora_id, str(other_thumb))
        other_folder = self.folder / "models" / "loras" / other.lora_id

        self.lora_manager.delete(self.lora.lora_id)

        self.assertTrue(other_folder.exists())

    def test_retry_after_move_failure_is_a_genuine_new_attempt(self):
        self.lora_manager.set_thumbnail(self.lora.lora_id, str(self.thumbnail_source))
        lora_folder = self._lora_folder()

        with patch.object(
            WorkspaceStorage, "rename_folder",
            side_effect=WorkspaceStorageError("locked by another process"),
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.lora_manager.delete(self.lora.lora_id)

        result = self.lora_manager.delete(self.lora.lora_id)

        self.assertTrue(result.deleted)
        self.assertFalse(lora_folder.exists())
        self.assertEqual(self.lora_manager.loras, [])

    def test_trash_folder_names_never_collide_across_attempts(self):
        self.lora_manager.set_thumbnail(self.lora.lora_id, str(self.thumbnail_source))

        with patch.object(WorkspaceStorage, "delete_folder", side_effect=WorkspaceStorageError("locked")):
            first = self.lora_manager.delete(self.lora.lora_id)

        self.assertTrue(first.deleted)
        self.assertTrue(first.cleanup_failed)
        first_residual = Path(first.residual_path)
        self.assertTrue(first_residual.exists())

        second_lora = self.lora_manager.create("Style B")
        self.lora_manager.select(second_lora.lora_id)
        second_thumb = self.source_dir / "second_thumb.png"
        second_thumb.write_bytes(b"second data")
        self.lora_manager.set_thumbnail(second_lora.lora_id, str(second_thumb))

        second = self.lora_manager.delete(second_lora.lora_id)

        self.assertTrue(second.deleted)
        self.assertFalse(second.cleanup_failed)
        self.assertTrue(first_residual.exists())


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
        lora_library_manager = LoRALibraryManager(storage_directory=Path(self.tmp_dir) / "lora_library")
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings",
            lora_library_manager=lora_library_manager,
        )
        lora_page = LoRAPage(lora_manager, workspace_manager, lora_library_manager, application_settings_manager)

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

    def test_delete_confirmed_save_failure_shows_error_and_keeps_the_lora(self):
        """
        Mission 068: LoRAManager.delete() rolls back the Domain removal
        (and active_lora_id) before re-raising on a save() failure — the
        Page must intercept WorkspaceManagerError, inform the user, and
        never present the deletion as successful.
        """
        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)

        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)

        mock_cls = self._confirm_delete(accept=True)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            lora_page.delete_lora()

        mock_cls.critical.assert_called_once()
        self.assertEqual(lora_manager.active_lora_id, lora.lora_id)
        self.assertEqual(len(lora_manager.loras), 1)
        self.assertIs(lora_manager.loras[0], lora)

    def test_retry_after_save_failure_actually_deletes(self):
        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)

        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)

        self._confirm_delete(accept=True)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            lora_page.delete_lora()

        self._confirm_delete(accept=True)
        lora_page.delete_lora()

        self.assertIsNone(lora_manager.active_lora_id)
        self.assertEqual(lora_manager.loras, [])

    def test_delete_confirmed_shows_warning_when_cleanup_fails(self):
        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)

        source_dir = Path(self.tmp_dir) / "External"
        source_dir.mkdir()
        thumbnail_source = source_dir / "thumb.png"
        thumbnail_source.write_bytes(b"fake png data")

        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        lora_manager.set_thumbnail(lora.lora_id, str(thumbnail_source))

        mock_cls = self._confirm_delete(accept=True)

        with patch.object(WorkspaceStorage, "delete_folder", side_effect=WorkspaceStorageError("locked")):
            lora_page.delete_lora()

        mock_cls.warning.assert_called_once()
        mock_cls.critical.assert_not_called()
        self.assertEqual(lora_manager.loras, [])


class LoRAPageDeleteButtonStateTest(unittest.TestCase):
    """
    Mission 063: "Supprimer" must always reflect whether there is
    currently a valid selection to act on, mirroring ImagesPage's
    established delete_button.setEnabled() pattern (Mission 046) —
    never a silent no-op behind an always-clickable button.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "LoRAButtonStateProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        lora_manager = LoRAManager(character_manager, workspace_manager, event_bus=event_bus)
        lora_library_manager = LoRALibraryManager(storage_directory=Path(self.tmp_dir) / "lora_library")
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings",
            lora_library_manager=lora_library_manager,
        )
        lora_page = LoRAPage(lora_manager, workspace_manager, lora_library_manager, application_settings_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, lora_page.update_loras)
        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, lora_page.update_loras)
        for event_name in LORA_EVENTS:
            event_bus.subscribe(event_name, lora_page.update_loras)

        return workspace_manager, lora_manager, lora_page

    def test_disabled_before_any_workspace(self):
        _, _, lora_page = self._wire()
        self.assertFalse(lora_page.delete_button.isEnabled())

    def test_disabled_with_no_selection_then_enabled_on_select(self):
        workspace_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)

        self.assertFalse(lora_page.delete_button.isEnabled())

        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)

        self.assertTrue(lora_page.delete_button.isEnabled())

    def test_deselecting_disables_delete_button(self):
        workspace_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        self.assertTrue(lora_page.delete_button.isEnabled())

        lora_page.lora_list.setCurrentItem(None)

        self.assertFalse(lora_page.delete_button.isEnabled())

    def test_delete_button_stays_consistent_after_list_rebuild(self):
        workspace_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)
        lora_a = lora_manager.create("StyleA")
        lora_manager.select(lora_a.lora_id)
        self.assertTrue(lora_page.delete_button.isEnabled())

        # LORA_CREATED triggers update_loras() -> a full list rebuild,
        # while the active selection itself is untouched.
        lora_manager.create("StyleB")

        self.assertTrue(lora_page.delete_button.isEnabled())
        self.assertEqual(lora_page.lora_list.currentItem().data(Qt.UserRole), lora_a.lora_id)

    def test_disabled_after_workspace_closed(self):
        workspace_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        self.assertTrue(lora_page.delete_button.isEnabled())

        workspace_manager.close()

        self.assertFalse(lora_page.delete_button.isEnabled())

    def test_disabled_after_deleting_the_selected_lora(self):
        workspace_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        self.assertTrue(lora_page.delete_button.isEnabled())

        # LORA_DELETED triggers update_loras() -> the button must be
        # recomputed from the resulting (now empty) selection.
        lora_manager.delete(lora.lora_id)

        self.assertFalse(lora_page.delete_button.isEnabled())


class LoRAPageDirtyStateTest(unittest.TestCase):
    """
    Mission 078: LoRAPage.update_loras() used to unconditionally overwrite
    the 4 metadata widgets (engine/architecture/trigger_word/version) on
    every WORKSPACE_SAVED/RENAMED/CREATED/OPENED/CLOSED and
    CHARACTER_*/LORA_* event — an unsaved draft was silently destroyed by
    any unrelated mutation elsewhere in the app (empirically reproduced
    during the post-Mission-077 audit, engine_edit scenario). This mirrors
    the exact bug class already fixed for PromptsPage by Mission 038: a
    local _metadata_dirty flag + _loaded_lora_id comparison now preserves
    a genuine draft across a non-destructive refresh, discards it on a
    real LoRA switch or Workspace context change, and never breaks the
    Mission 073/076 failure-resync contracts. name_edit/files_list/
    thumbnail are unaffected — they have no draft of their own and keep
    refreshing unconditionally, exactly as before this mission.
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
        lora_library_manager = LoRALibraryManager(storage_directory=Path(self.tmp_dir) / "lora_library")
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings",
            lora_library_manager=lora_library_manager,
        )
        lora_page = LoRAPage(lora_manager, workspace_manager, lora_library_manager, application_settings_manager)

        # Mission 078: same split as the real main_window.py wiring.
        for event_name in (WORKSPACE_SAVED, WORKSPACE_RENAMED):
            event_bus.subscribe(event_name, lora_page.update_loras)
        event_bus.subscribe(CHARACTER_CREATED, lora_page.update_loras)
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            event_bus.subscribe(event_name, lora_page.reset_for_context_change)
        for event_name in (CHARACTER_SELECTED, CHARACTER_DELETED):
            event_bus.subscribe(event_name, lora_page.reset_for_context_change)
        for event_name in LORA_EVENTS:
            event_bus.subscribe(event_name, lora_page.update_loras)

        return event_bus, workspace_manager, character_manager, lora_manager, lora_page

    def _prepare(self):
        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        workspace_manager.create(self.folder)
        character_manager.create("Aria")
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        return workspace_manager, character_manager, lora_manager, lora_page, lora

    def test_dirty_engine_draft_preserved_across_unrelated_workspace_saved(self):
        """
        Mission 078's core non-regression test: reproduces, as a
        permanent automated test, the exact engine_edit scenario
        empirically demonstrated during the post-Mission-077 audit — an
        unrelated mutation elsewhere (here, creating a second Character)
        must never wipe an unsaved metadata draft.
        """
        workspace_manager, character_manager, lora_manager, lora_page, lora = self._prepare()

        lora_page.engine_edit.setText("DRAFT ENGINE NOT SAVED YET")
        self.assertTrue(lora_page._metadata_dirty)

        character_manager.create("SecondCharacter")

        self.assertEqual(lora_page.engine_edit.text(), "DRAFT ENGINE NOT SAVED YET")
        self.assertTrue(lora_page._metadata_dirty)

    def test_multiple_dirty_metadata_fields_preserved_simultaneously(self):
        workspace_manager, character_manager, lora_manager, lora_page, lora = self._prepare()

        lora_page.engine_edit.setText("Draft engine")
        lora_page.architecture_edit.setText("Draft arch")
        lora_page.trigger_word_edit.setText("draft_trigger")
        lora_page.version_edit.setText("9.9")

        character_manager.create("SecondCharacter")

        self.assertEqual(lora_page.engine_edit.text(), "Draft engine")
        self.assertEqual(lora_page.architecture_edit.text(), "Draft arch")
        self.assertEqual(lora_page.trigger_word_edit.text(), "draft_trigger")
        self.assertEqual(lora_page.version_edit.text(), "9.9")

    def test_successful_save_clears_dirty_and_persists(self):
        workspace_manager, character_manager, lora_manager, lora_page, lora = self._prepare()

        lora_page.engine_edit.setText("ComfyUI")
        lora_page.save_metadata()

        self.assertFalse(lora_page._metadata_dirty)
        self.assertEqual(lora.engine, "ComfyUI")

    def test_failed_save_still_resyncs_and_clears_dirty_per_mission_073_contract(self):
        workspace_manager, character_manager, lora_manager, lora_page, lora = self._prepare()
        lora_manager.update(lora.lora_id, engine="ComfyUI")

        lora_page.engine_edit.setText("Rejected engine")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.lora_page.QMessageBox.critical"):
            lora_page.save_metadata()

        self.assertEqual(lora_page.engine_edit.text(), "ComfyUI")
        self.assertFalse(lora_page._metadata_dirty)

    def test_non_dirty_refresh_reflects_external_manager_mutation(self):
        workspace_manager, character_manager, lora_manager, lora_page, lora = self._prepare()

        lora_manager.update(lora.lora_id, engine="Changed elsewhere")

        self.assertEqual(lora_page.engine_edit.text(), "Changed elsewhere")
        self.assertFalse(lora_page._metadata_dirty)

    def test_programmatic_refresh_never_sets_false_dirty_state(self):
        workspace_manager, character_manager, lora_manager, lora_page, lora = self._prepare()

        self.assertFalse(lora_page._metadata_dirty)
        character_manager.create("SecondCharacter")
        self.assertFalse(lora_page._metadata_dirty)
        lora_page.update_loras()
        self.assertFalse(lora_page._metadata_dirty)

    def test_real_context_change_discards_dirty_draft(self):
        workspace_manager, character_manager, lora_manager, lora_page, lora = self._prepare()

        lora_page.engine_edit.setText("Draft lost on workspace close.")
        self.assertTrue(lora_page._metadata_dirty)

        workspace_manager.close()

        self.assertEqual(lora_page.engine_edit.text(), "")
        self.assertFalse(lora_page._metadata_dirty)

    def test_switching_lora_selection_with_dirty_draft_save_choice(self):
        workspace_manager, character_manager, lora_manager, lora_page, lora = self._prepare()
        other = lora_manager.create("StyleB")

        lora_page.engine_edit.setText("Draft for StyleA")
        other_item = next(
            lora_page.lora_list.item(i) for i in range(lora_page.lora_list.count())
            if lora_page.lora_list.item(i).data(Qt.UserRole) == other.lora_id
        )

        with patch("src.ui.pages.lora_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Save
            lora_page.lora_list.setCurrentItem(other_item)

        self.assertEqual(lora.engine, "Draft for StyleA")
        self.assertEqual(lora_manager.active_lora_id, other.lora_id)
        self.assertFalse(lora_page._metadata_dirty)
        # The new LoRA's own (empty) metadata is shown, never StyleA's.
        self.assertEqual(lora_page.engine_edit.text(), "")

    def test_switching_lora_selection_with_dirty_draft_discard_choice(self):
        workspace_manager, character_manager, lora_manager, lora_page, lora = self._prepare()
        other = lora_manager.create("StyleB")

        lora_page.engine_edit.setText("Draft for StyleA")
        other_item = next(
            lora_page.lora_list.item(i) for i in range(lora_page.lora_list.count())
            if lora_page.lora_list.item(i).data(Qt.UserRole) == other.lora_id
        )

        with patch("src.ui.pages.lora_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Discard
            lora_page.lora_list.setCurrentItem(other_item)

        self.assertEqual(lora.engine, "")
        self.assertEqual(lora_manager.active_lora_id, other.lora_id)
        self.assertFalse(lora_page._metadata_dirty)

    def test_switching_lora_selection_with_dirty_draft_cancel_choice_restores_selection(self):
        workspace_manager, character_manager, lora_manager, lora_page, lora = self._prepare()
        other = lora_manager.create("StyleB")

        lora_page.engine_edit.setText("Draft for StyleA")
        other_item = next(
            lora_page.lora_list.item(i) for i in range(lora_page.lora_list.count())
            if lora_page.lora_list.item(i).data(Qt.UserRole) == other.lora_id
        )

        with patch.object(
            type(lora_manager), "select", wraps=lora_manager.select
        ) as select_spy, patch("src.ui.pages.lora_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Cancel
            lora_page.lora_list.setCurrentItem(other_item)
            select_spy.assert_not_called()

        self.assertEqual(lora_manager.active_lora_id, lora.lora_id)
        self.assertEqual(
            lora_page.lora_list.currentItem().data(Qt.UserRole), lora.lora_id
        )
        self.assertEqual(lora_page.engine_edit.text(), "Draft for StyleA")
        self.assertTrue(lora_page._metadata_dirty)

    def test_delete_lora_with_dirty_draft_shows_adapted_warning_and_deletes_on_confirm(self):
        workspace_manager, character_manager, lora_manager, lora_page, lora = self._prepare()

        lora_page.engine_edit.setText("Draft about to be lost")

        with patch("src.ui.pages.lora_page.QMessageBox") as mock_message_box:
            mock_box_instance = mock_message_box.return_value
            mock_box_instance.addButton.side_effect = lambda text, role: text
            mock_box_instance.clickedButton.return_value = "Supprimer"
            lora_page.delete_lora()

        self.assertEqual(len(lora_manager.loras), 0)
        # Text passed to setText() must mention the lost metadata.
        shown_text = mock_box_instance.setText.call_args[0][0]
        self.assertIn("métadonnées", shown_text)

    def test_confirm_context_change_without_dirty_draft_returns_true_no_dialog(self):
        workspace_manager, character_manager, lora_manager, lora_page, lora = self._prepare()

        with patch("src.ui.pages.lora_page.QMessageBox") as mock_message_box:
            self.assertTrue(lora_page.confirm_context_change())
            mock_message_box.assert_not_called()

    def test_confirm_context_change_save_choice_persists_and_returns_true(self):
        workspace_manager, character_manager, lora_manager, lora_page, lora = self._prepare()

        lora_page.engine_edit.setText("Saved before switching project.")

        with patch("src.ui.pages.lora_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Save
            self.assertTrue(lora_page.confirm_context_change())

        self.assertFalse(lora_page._metadata_dirty)
        self.assertEqual(lora.engine, "Saved before switching project.")

    def test_confirm_context_change_save_failure_resyncs_and_returns_false(self):
        workspace_manager, character_manager, lora_manager, lora_page, lora = self._prepare()
        lora_manager.update(lora.lora_id, engine="ComfyUI")

        lora_page.engine_edit.setText("Rejected on switch.")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.lora_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Save
            self.assertFalse(lora_page.confirm_context_change())

        self.assertTrue(mock_message_box.critical.called)
        self.assertEqual(lora_page.engine_edit.text(), "ComfyUI")
        self.assertFalse(lora_page._metadata_dirty)

    def test_retry_after_confirm_context_change_save_failure_actually_persists(self):
        workspace_manager, character_manager, lora_manager, lora_page, lora = self._prepare()

        lora_page.engine_edit.setText("Rejected on switch.")
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.lora_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Save
            lora_page.confirm_context_change()

        lora_page.engine_edit.setText("Recovered.")
        lora_page.save_metadata()

        self.assertEqual(lora.engine, "Recovered.")
        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        stored = next(
            l
            for c in on_disk["characters"]
            for l in c["loras"]
            if l["lora_id"] == lora.lora_id
        )
        self.assertEqual(stored["engine"], "Recovered.")


class LoRAPageFilesSelectionPreservationTest(unittest.TestCase):
    """
    Mission 082: files_list.selectedItems() (identity = item.text(), no
    Qt.UserRole set on this list) must survive a same-LoRA rebuild
    (update_loras(), e.g. an unrelated WORKSPACE_SAVED) — guarded by the
    existing _loaded_lora_id (Mission 078). currentItem() is
    deliberately never restored — nothing on files_list reads it.
    reset_for_context_change()/_force_refresh_lora() must never restore
    a selection, mirroring their existing "always reset, never a stale
    draft" contract for the metadata fields.

    Uses the real MainWindow-equivalent event routing (WORKSPACE_SAVED/
    RENAMED + CHARACTER_CREATED + LORA_CREATED/SELECTED/DELETED go to
    update_loras(); WORKSPACE_CREATED/OPENED/CLOSED + CHARACTER_SELECTED/
    DELETED go to reset_for_context_change()) rather than
    LoRARoundTripTest._wire()'s simplified routing — required to
    exercise the update_loras()/_force_refresh_lora() split this Mission
    relies on.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "LoRASelectionProject"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.lora_manager = LoRAManager(self.character_manager, self.workspace_manager, event_bus=self.event_bus)
        self.lora_library_manager = LoRALibraryManager(storage_directory=Path(self.tmp_dir) / "lora_library")
        self.application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings",
            lora_library_manager=self.lora_library_manager,
        )

        self.lora_page = LoRAPage(
            self.lora_manager, self.workspace_manager, self.lora_library_manager, self.application_settings_manager
        )

        for event_name in (WORKSPACE_SAVED, WORKSPACE_RENAMED):
            self.event_bus.subscribe(event_name, self.lora_page.update_loras)
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            self.event_bus.subscribe(event_name, self.lora_page.reset_for_context_change)
        self.event_bus.subscribe(CHARACTER_CREATED, self.lora_page.update_loras)
        for event_name in (CHARACTER_SELECTED, CHARACTER_DELETED):
            self.event_bus.subscribe(event_name, self.lora_page.reset_for_context_change)
        for event_name in LORA_EVENTS:
            self.event_bus.subscribe(event_name, self.lora_page.update_loras)

        self.workspace_manager.create(self.folder)
        self.character_manager.create("Aria")
        self.lora = self.lora_manager.create("StyleA")
        self.lora_manager.select(self.lora.lora_id)

        self.files = ["a.safetensors", "b.safetensors", "c.safetensors"]
        self.lora_manager.add_files(self.files)

    def _select(self, *texts):
        for i in range(self.lora_page.files_list.count()):
            item = self.lora_page.files_list.item(i)
            if item.text() in texts:
                item.setSelected(True)

    def _selected_texts(self):
        return {item.text() for item in self.lora_page.files_list.selectedItems()}

    def test_refresh_without_content_change_preserves_full_selection(self):
        self._select("a.safetensors", "b.safetensors")

        self.workspace_manager.save()  # unrelated refresh, same active LoRA

        self.assertEqual(self._selected_texts(), {"a.safetensors", "b.safetensors"})

    def test_adding_a_new_file_preserves_previous_selection_without_selecting_the_new_one(self):
        self._select("a.safetensors", "b.safetensors")

        self.lora_manager.add_files(["d.safetensors"])

        self.assertEqual(self._selected_texts(), {"a.safetensors", "b.safetensors"})
        self.assertNotIn("d.safetensors", self._selected_texts())

    def test_removing_one_selected_file_keeps_the_surviving_selection(self):
        self._select("a.safetensors", "b.safetensors", "c.safetensors")

        self.lora_manager.remove_files(["a.safetensors"])

        self.assertEqual(self._selected_texts(), {"b.safetensors", "c.safetensors"})

    def test_removing_all_selected_files_empties_selection_and_disables_button(self):
        self._select("a.safetensors", "b.safetensors", "c.safetensors")

        self.lora_manager.remove_files(self.files)

        self.assertEqual(self._selected_texts(), set())
        self.assertFalse(self.lora_page.remove_files_button.isEnabled())

    def test_switching_to_a_different_lora_never_transfers_selection_even_with_a_shared_file(self):
        # Mission 082 critical regression: LoRA.files only ever holds
        # external references (never copied) — two different LoRAs can
        # legitimately reference the exact same external file. A naive
        # identity-only restoration would incorrectly cross-select it in
        # LoRA B just because it was selected in LoRA A.
        shared_file = str(Path(self.tmp_dir) / "shared.safetensors")
        Path(shared_file).write_text("shared")
        self.lora_manager.add_files([shared_file])  # into StyleA (currently active)

        style_b = self.lora_manager.create("StyleB")
        self.lora_manager.select(style_b.lora_id)
        self.lora_manager.add_files([shared_file])  # same shared file, also in StyleB

        self.lora_manager.select(self.lora.lora_id)  # back to StyleA
        self._select(shared_file)
        self.assertIn(shared_file, self._selected_texts())

        self.lora_manager.select(style_b.lora_id)  # the genuine A -> B switch under test

        self.assertEqual(self._selected_texts(), set())

    def test_reset_for_context_change_never_restores_a_stale_selection(self):
        # A genuine Workspace/Character context reset must always start
        # from an empty selection, even though it also routes through
        # _load_non_metadata_details() — mirrors the metadata fields'
        # own "always reset" contract for these 5 events.
        self._select("a.safetensors")
        self.assertEqual(self._selected_texts(), {"a.safetensors"})

        self.character_manager.create("Second")
        second_character = next(c for c in self.character_manager.characters if c.name == "Second")
        self.character_manager.select(second_character.character_id)

        self.assertEqual(self.lora_page.files_list.count(), 0)
        self.assertEqual(self._selected_texts(), set())


if __name__ == "__main__":
    unittest.main()
