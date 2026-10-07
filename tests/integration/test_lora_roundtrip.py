"""
Integration coverage for the LoRA lifecycle, exercising LoRAManager,
Character.loras, Workspace persistence, EventBus and the real
DashboardPage/CharactersPage/ImagesPage/LoRAPage widgets together —
the same wiring MainWindow uses.
"""

import contextlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QListWidget, QMessageBox, QStackedWidget

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
from src.managers.workspace_lifecycle import create_workspace_with_default_character
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
from tests.integration._qt_dialog_safety_net import (
    UnexpectedDialogError,
    assert_dialog_guard_intercepts_promptly,
    start_dialog_guard,
    stop_dialog_guard,
)

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
        # characters_page, lora_page) + LoRAManager's own internal reset
        # subscription = 5, on EACH bus independently. Mission 137:
        # CharacterManager no longer subscribes anything to
        # WORKSPACE_CREATED — Mission 026's principal-Character
        # auto-creation is now an explicit call made by
        # workspace_lifecycle.create_workspace_with_default_character(),
        # and active_character_id's reset-on-workspace-switch no longer
        # needs to react to CREATED specifically (see
        # CharacterManager.__init__'s own comment for why).
        self.assertEqual(len(event_bus_1._subscribers[WORKSPACE_CREATED]), 5)
        self.assertEqual(len(event_bus_2._subscribers[WORKSPACE_CREATED]), 5)
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
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)
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
        # but here the Workspace is open with zero Character. Mission
        # 137: WorkspaceManager.create() alone no longer auto-creates a
        # Character, so this state is reached directly.
        workspace_manager, character_manager, lora_manager = self._wire()
        workspace_manager.create(self.folder)
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

    def _assert_blank_library_path_blocks_import(self, blank_value):
        # Mission 104: lora_library_path is still "" or "   " at this
        # point -- the library is empty, so ApplicationSettingsManager's
        # own lock (Mission 087) never fires; only
        # resolve_lora_library_root() must stop the import here.
        self.application_settings_manager.update(lora_library_path=blank_value)

        received = []
        self.event_bus.subscribe(LORA_LIBRARY_IMPORTED, lambda data: received.append(data))

        cwd_before = set(os.listdir(os.getcwd()))

        with patch.object(
            self.lora_library_manager, "import_lora"
        ) as import_mock, patch(
            "src.ui.pages.lora_page.QMessageBox.critical"
        ) as critical_mock, patch(
            "src.ui.pages.lora_page.QMessageBox.information"
        ) as information_mock:
            self.lora_page.add_to_central_library()

        import_mock.assert_not_called()
        self.assertEqual(received, [])
        information_mock.assert_not_called()
        critical_mock.assert_called_once()
        self.assertIn("pas configurée", critical_mock.call_args[0][2])
        self.assertEqual(self.lora_library_manager.list_loras(), [])
        self.assertEqual(set(os.listdir(os.getcwd())), cwd_before)

    def test_empty_library_path_blocks_import(self):
        self._assert_blank_library_path_blocks_import("")

    def test_blank_library_path_blocks_import(self):
        self._assert_blank_library_path_blocks_import("   ")

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

    # --- Mission 092: direct import from disk ---

    def _write_source_file(self, filename, content=b"weights"):
        path = Path(self.tmp_dir) / filename
        path.write_bytes(content)
        return path

    def test_import_from_disk_creates_new_entry_and_copies_files(self):
        source = self._write_source_file("mylora.safetensors")

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileNames",
            return_value=([str(source)], ""),
        ), patch(
            "src.ui.pages.lora_page.QInputDialog.getText",
            return_value=("Direct Import", True),
        ):
            self.lora_page.import_to_library_from_disk()

        loras = self.lora_library_manager.list_loras()
        self.assertEqual(len(loras), 1)
        lora = loras[0]
        self.assertEqual(lora.name, "Direct Import")
        self.assertEqual(len(lora.files), 1)
        self.assertTrue(Path(lora.files[0]).exists())
        self.assertEqual(Path(lora.files[0]).read_bytes(), b"weights")
        self.assertTrue(str(Path(lora.files[0])).startswith(str(self.library_root)))
        # Source untouched.
        self.assertTrue(source.exists())
        self.assertEqual(source.read_bytes(), b"weights")
        # No Character/Workspace mutation whatsoever.
        self.assertEqual(self.lora_manager.loras, [])
        with open(self.folder / "project.json", encoding="utf-8") as f:
            project_json = json.load(f)
        self.assertNotIn("Direct Import", json.dumps(project_json))

    def test_import_from_disk_selects_and_loads_the_new_entry(self):
        source = self._write_source_file("mylora.safetensors")

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileNames",
            return_value=([str(source)], ""),
        ), patch(
            "src.ui.pages.lora_page.QInputDialog.getText",
            return_value=("Direct Import", True),
        ):
            self.lora_page.import_to_library_from_disk()

        lora = self.lora_library_manager.list_loras()[0]
        self.assertEqual(self.lora_page.library_list.count(), 1)
        self.assertEqual(
            self.lora_page.library_list.currentItem().data(Qt.UserRole), lora.lora_id
        )
        self.assertEqual(self.lora_page._loaded_library_lora_id, lora.lora_id)
        self.assertEqual(self.lora_page.library_name_edit.text(), "Direct Import")
        self.assertEqual(self.lora_page.library_engine_edit.text(), "")
        self.assertTrue(self.lora_page.delete_from_library_button.isEnabled())
        self.assertFalse(self.lora_page._library_metadata_dirty)

    def test_import_from_disk_cancel_file_dialog_is_a_strict_no_op(self):
        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileNames",
            return_value=([], ""),
        ), patch("src.ui.pages.lora_page.QInputDialog.getText") as input_mock:
            self.lora_page.import_to_library_from_disk()

        input_mock.assert_not_called()
        self.assertEqual(self.lora_library_manager.list_loras(), [])
        self.assertEqual(self.lora_page.library_list.count(), 0)

    def test_import_from_disk_cancel_name_dialog_is_a_strict_no_op(self):
        source = self._write_source_file("mylora.safetensors")

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileNames",
            return_value=([str(source)], ""),
        ), patch(
            "src.ui.pages.lora_page.QInputDialog.getText",
            return_value=("", False),
        ):
            self.lora_page.import_to_library_from_disk()

        self.assertEqual(self.lora_library_manager.list_loras(), [])
        self.assertEqual(self.lora_page.library_list.count(), 0)

    def test_import_from_disk_empty_name_after_strip_is_a_strict_no_op(self):
        source = self._write_source_file("mylora.safetensors")

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileNames",
            return_value=([str(source)], ""),
        ), patch(
            "src.ui.pages.lora_page.QInputDialog.getText",
            return_value=("   ", True),
        ):
            self.lora_page.import_to_library_from_disk()

        self.assertEqual(self.lora_library_manager.list_loras(), [])

    def test_import_from_disk_twice_with_same_source_creates_two_independent_entries(self):
        source = self._write_source_file("shared.safetensors")

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileNames",
            return_value=([str(source)], ""),
        ), patch(
            "src.ui.pages.lora_page.QInputDialog.getText",
            return_value=("First", True),
        ):
            self.lora_page.import_to_library_from_disk()

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileNames",
            return_value=([str(source)], ""),
        ), patch(
            "src.ui.pages.lora_page.QInputDialog.getText",
            return_value=("Second", True),
        ):
            self.lora_page.import_to_library_from_disk()

        loras = self.lora_library_manager.list_loras()
        self.assertEqual(len(loras), 2)
        self.assertNotEqual(loras[0].lora_id, loras[1].lora_id)
        self.assertNotEqual(Path(loras[0].files[0]).parent, Path(loras[1].files[0]).parent)
        self.assertEqual(self.lora_page.library_list.count(), 2)

    def test_import_from_disk_copy_failure_shows_error_and_creates_no_entry(self):
        missing_source = Path(self.tmp_dir) / "does_not_exist.safetensors"

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileNames",
            return_value=([str(missing_source)], ""),
        ), patch(
            "src.ui.pages.lora_page.QInputDialog.getText",
            return_value=("Broken", True),
        ), patch("src.ui.pages.lora_page.QMessageBox.critical") as critical_mock:
            self.lora_page.import_to_library_from_disk()

        self.assertTrue(critical_mock.called)
        self.assertEqual(self.lora_library_manager.list_loras(), [])
        self.assertEqual(self.lora_page.library_list.count(), 0)

    def test_import_from_disk_persistence_failure_shows_error_and_creates_no_entry(self):
        source = self._write_source_file("mylora.safetensors")

        with patch.object(
            LoRALibraryStorage, "save", side_effect=LoRALibraryStorageError("disk full")
        ), patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileNames",
            return_value=([str(source)], ""),
        ), patch(
            "src.ui.pages.lora_page.QInputDialog.getText",
            return_value=("Broken", True),
        ), patch("src.ui.pages.lora_page.QMessageBox.critical") as critical_mock:
            self.lora_page.import_to_library_from_disk()

        self.assertTrue(critical_mock.called)
        self.assertEqual(self.lora_library_manager.list_loras(), [])
        self.assertEqual(self.lora_page.library_list.count(), 0)

    def _assert_blank_library_path_blocks_import_from_disk(self, blank_value):
        # Mission 104: library is still empty at this point in the
        # test, so ApplicationSettingsManager's own lock never fires.
        self.application_settings_manager.update(lora_library_path=blank_value)
        source = self._write_source_file("mylora.safetensors")

        received = []
        self.event_bus.subscribe(LORA_LIBRARY_IMPORTED, lambda data: received.append(data))
        cwd_before = set(os.listdir(os.getcwd()))

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileNames",
            return_value=([str(source)], ""),
        ), patch(
            "src.ui.pages.lora_page.QInputDialog.getText",
            return_value=("Direct Import", True),
        ), patch.object(
            self.lora_library_manager, "import_lora"
        ) as import_mock, patch(
            "src.ui.pages.lora_page.QMessageBox.critical"
        ) as critical_mock, patch(
            "src.ui.pages.lora_page.QMessageBox.information"
        ) as information_mock:
            self.lora_page.import_to_library_from_disk()

        import_mock.assert_not_called()
        self.assertEqual(received, [])
        information_mock.assert_not_called()
        critical_mock.assert_called_once()
        self.assertIn("pas configurée", critical_mock.call_args[0][2])
        self.assertEqual(self.lora_library_manager.list_loras(), [])
        self.assertEqual(self.lora_page.library_list.count(), 0)
        self.assertEqual(set(os.listdir(os.getcwd())), cwd_before)

    def test_empty_library_path_blocks_import_from_disk(self):
        self._assert_blank_library_path_blocks_import_from_disk("")

    def test_blank_library_path_blocks_import_from_disk(self):
        self._assert_blank_library_path_blocks_import_from_disk("   ")

    def test_import_from_disk_dirty_guard_cancel_aborts_before_file_dialog(self):
        self._import_entry("Existing")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("Dirty")

        with patch.object(
            self.lora_page, "_confirm_discard_library_metadata_before_switch",
            return_value=QMessageBox.Cancel,
        ), patch("src.ui.pages.lora_page.QFileDialog.getOpenFileNames") as file_dialog_mock:
            self.lora_page.import_to_library_from_disk()

        file_dialog_mock.assert_not_called()
        self.assertEqual(len(self.lora_library_manager.list_loras()), 1)
        self.assertTrue(self.lora_page._library_metadata_dirty)
        self.assertEqual(self.lora_page.library_engine_edit.text(), "Dirty")

    def test_import_from_disk_dirty_guard_discard_proceeds_without_persisting_draft(self):
        entry = self._import_entry("Existing")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("Dirty")
        source = self._write_source_file("mylora.safetensors")

        with patch.object(
            self.lora_page, "_confirm_discard_library_metadata_before_switch",
            return_value=QMessageBox.Discard,
        ), patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileNames",
            return_value=([str(source)], ""),
        ), patch(
            "src.ui.pages.lora_page.QInputDialog.getText",
            return_value=("Direct Import", True),
        ):
            self.lora_page.import_to_library_from_disk()

        # The discarded draft was never persisted.
        self.assertEqual(self.lora_library_manager.get(entry.lora_id).engine, "ComfyUI")
        loras = self.lora_library_manager.list_loras()
        self.assertEqual(len(loras), 2)
        new_lora = next(l for l in loras if l.lora_id != entry.lora_id)
        self.assertEqual(self.lora_page._loaded_library_lora_id, new_lora.lora_id)
        self.assertFalse(self.lora_page._library_metadata_dirty)

    def test_import_from_disk_dirty_guard_save_persists_previous_entry_then_imports(self):
        entry = self._import_entry("Existing")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("SavedBeforeImport")
        source = self._write_source_file("mylora.safetensors")

        with patch.object(
            self.lora_page, "_confirm_discard_library_metadata_before_switch",
            return_value=QMessageBox.Save,
        ), patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileNames",
            return_value=([str(source)], ""),
        ), patch(
            "src.ui.pages.lora_page.QInputDialog.getText",
            return_value=("Direct Import", True),
        ):
            self.lora_page.import_to_library_from_disk()

        self.assertEqual(self.lora_library_manager.get(entry.lora_id).engine, "SavedBeforeImport")
        loras = self.lora_library_manager.list_loras()
        self.assertEqual(len(loras), 2)
        new_lora = next(l for l in loras if l.lora_id != entry.lora_id)
        self.assertEqual(self.lora_page._loaded_library_lora_id, new_lora.lora_id)
        self.assertFalse(self.lora_page._library_metadata_dirty)

    def test_import_from_disk_dirty_guard_save_failure_aborts_import_entirely(self):
        self._import_entry("Existing")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("WillFail")

        with patch.object(LoRALibraryStorage, "save", side_effect=LoRALibraryStorageError("disk full")), \
                patch.object(
                    self.lora_page, "_confirm_discard_library_metadata_before_switch",
                    return_value=QMessageBox.Save,
                ), \
                patch("src.ui.pages.lora_page.QFileDialog.getOpenFileNames") as file_dialog_mock, \
                patch("src.ui.pages.lora_page.QMessageBox.critical") as critical_mock:
            self.lora_page.import_to_library_from_disk()

        self.assertTrue(critical_mock.called)
        file_dialog_mock.assert_not_called()
        self.assertEqual(len(self.lora_library_manager.list_loras()), 1)
        self.assertTrue(self.lora_page._library_metadata_dirty)
        self.assertEqual(self.lora_page.library_engine_edit.text(), "WillFail")

    def test_import_to_library_button_always_enabled(self):
        # Mission 092: no active-entry precondition, unlike
        # save_library_metadata_button/delete_from_library_button.
        self.assertTrue(self.lora_page.import_to_library_button.isEnabled())
        self._import_entry("Existing")
        self.lora_page.update_central_library()
        self.assertTrue(self.lora_page.import_to_library_button.isEnabled())

    # --- Mission 093: central library thumbnail selector ---

    def test_choose_library_thumbnail_button_disabled_without_selection(self):
        self._import_entry("Existing")
        self.lora_page.update_central_library()
        self.assertFalse(self.lora_page.choose_library_thumbnail_button.isEnabled())

    def test_choose_library_thumbnail_button_enabled_once_an_entry_is_selected(self):
        self._import_entry("Existing", with_thumbnail=False)
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.assertTrue(self.lora_page.choose_library_thumbnail_button.isEnabled())

    def test_choose_library_thumbnail_with_no_selection_is_a_no_op(self):
        with patch("src.ui.pages.lora_page.QFileDialog.getOpenFileName") as file_dialog_mock:
            self.lora_page.choose_library_thumbnail()

        file_dialog_mock.assert_not_called()

    def test_choose_library_thumbnail_first_thumbnail_copies_file_and_refreshes_preview(self):
        entry = self._import_entry("Existing", with_thumbnail=False)
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        source = str(Path(self.tmp_dir) / "new_thumb.png")
        _make_png(source)

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileName",
            return_value=(source, ""),
        ):
            self.lora_page.choose_library_thumbnail()

        stored = self.lora_library_manager.get(entry.lora_id)
        self.assertTrue(stored.thumbnail)
        self.assertTrue(Path(stored.thumbnail).exists())
        self.assertEqual(self.lora_page._loaded_library_lora_id, entry.lora_id)
        self.assertFalse(self.lora_page.library_thumbnail_label.pixmap().isNull())

    def test_choose_library_thumbnail_replacement_deletes_previous_owned_file(self):
        entry = self._import_entry("Existing")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        previous_thumbnail = self.lora_library_manager.get(entry.lora_id).thumbnail

        new_source = str(Path(self.tmp_dir) / "replacement_thumb.png")
        _make_png(new_source)

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileName",
            return_value=(new_source, ""),
        ):
            self.lora_page.choose_library_thumbnail()

        stored = self.lora_library_manager.get(entry.lora_id)
        self.assertNotEqual(stored.thumbnail, previous_thumbnail)
        self.assertFalse(Path(previous_thumbnail).exists())
        self.assertTrue(Path(stored.thumbnail).exists())

    def test_choose_library_thumbnail_cancel_file_dialog_is_a_strict_no_op(self):
        entry = self._import_entry("Existing")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        previous_thumbnail = self.lora_library_manager.get(entry.lora_id).thumbnail

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileName",
            return_value=("", ""),
        ):
            self.lora_page.choose_library_thumbnail()

        self.assertEqual(self.lora_library_manager.get(entry.lora_id).thumbnail, previous_thumbnail)

    def test_choose_library_thumbnail_copy_failure_shows_error_and_preserves_previous_value(self):
        entry = self._import_entry("Existing")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        previous_thumbnail = self.lora_library_manager.get(entry.lora_id).thumbnail

        missing_source = str(Path(self.tmp_dir) / "does_not_exist.png")

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileName",
            return_value=(missing_source, ""),
        ), patch("src.ui.pages.lora_page.QMessageBox.critical") as critical_mock:
            self.lora_page.choose_library_thumbnail()

        critical_mock.assert_called_once()
        self.assertEqual(self.lora_library_manager.get(entry.lora_id).thumbnail, previous_thumbnail)

    def test_choose_library_thumbnail_persistence_failure_shows_error_and_rolls_back(self):
        entry = self._import_entry("Existing")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        previous_thumbnail = self.lora_library_manager.get(entry.lora_id).thumbnail

        new_source = str(Path(self.tmp_dir) / "will_fail_thumb.png")
        _make_png(new_source)

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileName",
            return_value=(new_source, ""),
        ), patch("src.ui.pages.lora_page.QMessageBox.critical") as critical_mock, patch.object(
            LoRALibraryStorage, "save", side_effect=LoRALibraryStorageError("disk full")
        ):
            self.lora_page.choose_library_thumbnail()

        critical_mock.assert_called_once()
        stored = self.lora_library_manager.get(entry.lora_id)
        self.assertEqual(stored.thumbnail, previous_thumbnail)
        self.assertTrue(Path(previous_thumbnail).exists())

    def _assert_blank_library_path_blocks_thumbnail(self, blank_value):
        # Mission 104: ApplicationSettingsManager's own lock (Mission
        # 087) refuses lora_library_path="" once the library already
        # has an entry -- reachable only through a Manager built
        # without the lock wired (unlike main_window.py's real
        # wiring), used here purely to reach and verify the defensive
        # guard at this fourth call site.
        entry = self._import_entry("Existing", with_thumbnail=False)

        unlocked_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "unlocked_app_settings",
        )
        unlocked_settings_manager.update(lora_library_path=blank_value)
        page = LoRAPage(
            self.lora_manager, self.workspace_manager, self.lora_library_manager,
            unlocked_settings_manager,
        )
        page.update_central_library()
        page.library_list.setCurrentRow(0)

        source = str(Path(self.tmp_dir) / "new_thumb.png")
        _make_png(source)

        received = []
        self.event_bus.subscribe(LORA_LIBRARY_UPDATED, lambda data: received.append(data))
        cwd_before = set(os.listdir(os.getcwd()))

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileName",
            return_value=(source, ""),
        ), patch.object(
            self.lora_library_manager, "set_thumbnail"
        ) as set_thumbnail_mock, patch(
            "src.ui.pages.lora_page.QMessageBox.critical"
        ) as critical_mock:
            page.choose_library_thumbnail()

        set_thumbnail_mock.assert_not_called()
        self.assertEqual(received, [])
        critical_mock.assert_called_once()
        self.assertIn("pas configurée", critical_mock.call_args[0][2])
        self.assertEqual(self.lora_library_manager.get(entry.lora_id).thumbnail, "")
        self.assertEqual(set(os.listdir(os.getcwd())), cwd_before)

    def test_empty_library_path_blocks_choose_library_thumbnail(self):
        self._assert_blank_library_path_blocks_thumbnail("")

    def test_blank_library_path_blocks_choose_library_thumbnail(self):
        self._assert_blank_library_path_blocks_thumbnail("   ")

    def test_choose_library_thumbnail_cleanup_failure_shows_warning_but_keeps_new_thumbnail(self):
        entry = self._import_entry("Existing")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        new_source = str(Path(self.tmp_dir) / "cleanup_failure_thumb.png")
        _make_png(new_source)

        with patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileName",
            return_value=(new_source, ""),
        ), patch("src.ui.pages.lora_page.QMessageBox.critical") as critical_mock, patch(
            "src.ui.pages.lora_page.QMessageBox.warning"
        ) as warning_mock, patch.object(
            Path, "unlink", side_effect=PermissionError("locked")
        ):
            self.lora_page.choose_library_thumbnail()

        critical_mock.assert_not_called()
        warning_mock.assert_called_once()
        stored = self.lora_library_manager.get(entry.lora_id)
        self.assertTrue(Path(stored.thumbnail).exists())
        self.assertEqual(Path(stored.thumbnail).read_bytes(), Path(new_source).read_bytes())

    def test_choose_library_thumbnail_dirty_guard_cancel_aborts_before_file_dialog(self):
        self._import_entry("Existing")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("UnsavedDraft")

        with patch.object(
            self.lora_page, "_confirm_discard_library_metadata_before_switch",
            return_value=QMessageBox.Cancel,
        ), patch("src.ui.pages.lora_page.QFileDialog.getOpenFileName") as file_dialog_mock:
            self.lora_page.choose_library_thumbnail()

        file_dialog_mock.assert_not_called()
        self.assertTrue(self.lora_page._library_metadata_dirty)
        self.assertEqual(self.lora_page.library_engine_edit.text(), "UnsavedDraft")

    def test_choose_library_thumbnail_dirty_guard_discard_proceeds_without_persisting_draft(self):
        entry = self._import_entry("Existing", engine="OriginalEngine")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("DiscardedDraft")

        source = str(Path(self.tmp_dir) / "discard_thumb.png")
        _make_png(source)

        with patch.object(
            self.lora_page, "_confirm_discard_library_metadata_before_switch",
            return_value=QMessageBox.Discard,
        ), patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileName",
            return_value=(source, ""),
        ):
            self.lora_page.choose_library_thumbnail()

        self.assertEqual(self.lora_library_manager.get(entry.lora_id).engine, "OriginalEngine")
        self.assertTrue(self.lora_library_manager.get(entry.lora_id).thumbnail)
        self.assertFalse(self.lora_page._library_metadata_dirty)
        self.assertEqual(self.lora_page.library_engine_edit.text(), "OriginalEngine")

    def test_choose_library_thumbnail_dirty_guard_save_persists_draft_then_changes_thumbnail(self):
        entry = self._import_entry("Existing", engine="OriginalEngine")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("SavedBeforeThumbnail")

        source = str(Path(self.tmp_dir) / "save_then_thumb.png")
        _make_png(source)

        with patch.object(
            self.lora_page, "_confirm_discard_library_metadata_before_switch",
            return_value=QMessageBox.Save,
        ), patch(
            "src.ui.pages.lora_page.QFileDialog.getOpenFileName",
            return_value=(source, ""),
        ):
            self.lora_page.choose_library_thumbnail()

        stored = self.lora_library_manager.get(entry.lora_id)
        self.assertEqual(stored.engine, "SavedBeforeThumbnail")
        self.assertTrue(stored.thumbnail)
        self.assertFalse(self.lora_page._library_metadata_dirty)
        self.assertEqual(self.lora_page._loaded_library_lora_id, entry.lora_id)

    def test_choose_library_thumbnail_dirty_guard_save_failure_aborts_before_file_dialog(self):
        self._import_entry("Existing")
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        self.lora_page.library_engine_edit.setText("WillFailToSave")

        with patch.object(LoRALibraryStorage, "save", side_effect=LoRALibraryStorageError("disk full")), \
                patch.object(
                    self.lora_page, "_confirm_discard_library_metadata_before_switch",
                    return_value=QMessageBox.Save,
                ), \
                patch("src.ui.pages.lora_page.QFileDialog.getOpenFileName") as file_dialog_mock, \
                patch("src.ui.pages.lora_page.QMessageBox.critical") as critical_mock:
            self.lora_page.choose_library_thumbnail()

        critical_mock.assert_called_once()
        file_dialog_mock.assert_not_called()
        self.assertTrue(self.lora_page._library_metadata_dirty)
        self.assertEqual(self.lora_page.library_engine_edit.text(), "WillFailToSave")


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
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

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
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

        for name in ("Zebra", "mango", "Apple"):
            lora_manager.create(name)

        principal = character_manager.principal_character
        self.assertEqual(
            [l.name for l in principal.loras],
            ["Zebra", "mango", "Apple"],
        )

    def test_sort_is_stable_for_identical_names(self):

        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

        first = lora_manager.create("Same")
        second = lora_manager.create("Same")

        displayed_ids = [
            lora_page.lora_list.item(i).data(Qt.UserRole)
            for i in range(lora_page.lora_list.count())
        ]
        self.assertEqual(displayed_ids, [first.lora_id, second.lora_id])

    def test_selection_targets_correct_lora_and_preserves_files_metadata_thumbnail(self):

        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

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
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

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
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)

        lora_page.name_edit.setText("StyleA Renamed")
        lora_page.name_edit.editingFinished.emit()

        self.assertEqual(lora_manager.active_lora.name, "StyleA Renamed")
        self.assertEqual(lora_manager.active_lora.lora_id, lora.lora_id)
        self.assertTrue(lora_page.lora_list.item(0).text().startswith("StyleA Renamed"))

    def test_rename_preserves_files_metadata_and_thumbnail(self):

        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

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
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

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
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

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
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)
        lora_manager.create("StyleA")

        lora_page.name_edit.setText("Whatever")
        lora_page.name_edit.editingFinished.emit()

        principal = character_manager.principal_character
        self.assertEqual([l.name for l in principal.loras], ["StyleA"])

    def test_rename_does_not_regress_add_remove_files_save_metadata_or_thumbnail(self):

        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

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
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

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
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

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
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

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
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

        mock_cls = self._confirm_delete(accept=True)

        lora_page.delete_lora()

        mock_cls.assert_not_called()

    def test_delete_confirmed_removes_lora(self):
        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)

        self._confirm_delete(accept=True)

        lora_page.delete_lora()

        self.assertIsNone(lora_manager.active_lora_id)
        self.assertEqual(lora_manager.loras, [])

    def test_delete_cancelled_calls_neither_manager_nor_mutates_state(self):
        _, workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

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
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

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
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

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
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

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

        return workspace_manager, character_manager, lora_manager, lora_page

    def test_disabled_before_any_workspace(self):
        _, _, _, lora_page = self._wire()
        self.assertFalse(lora_page.delete_button.isEnabled())

    def test_disabled_with_no_selection_then_enabled_on_select(self):
        workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)

        self.assertFalse(lora_page.delete_button.isEnabled())

        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)

        self.assertTrue(lora_page.delete_button.isEnabled())

    def test_deselecting_disables_delete_button(self):
        workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        self.assertTrue(lora_page.delete_button.isEnabled())

        lora_page.lora_list.setCurrentItem(None)

        self.assertFalse(lora_page.delete_button.isEnabled())

    def test_delete_button_stays_consistent_after_list_rebuild(self):
        workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)
        lora_a = lora_manager.create("StyleA")
        lora_manager.select(lora_a.lora_id)
        self.assertTrue(lora_page.delete_button.isEnabled())

        # LORA_CREATED triggers update_loras() -> a full list rebuild,
        # while the active selection itself is untouched.
        lora_manager.create("StyleB")

        self.assertTrue(lora_page.delete_button.isEnabled())
        self.assertEqual(lora_page.lora_list.currentItem().data(Qt.UserRole), lora_a.lora_id)

    def test_disabled_after_workspace_closed(self):
        workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)
        lora = lora_manager.create("StyleA")
        lora_manager.select(lora.lora_id)
        self.assertTrue(lora_page.delete_button.isEnabled())

        workspace_manager.close()

        self.assertFalse(lora_page.delete_button.isEnabled())

    def test_disabled_after_deleting_the_selected_lora(self):
        workspace_manager, character_manager, lora_manager, lora_page = self._wire()
        create_workspace_with_default_character(workspace_manager, character_manager, self.folder)
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


class LoRAPageComfyUIExposureTest(unittest.TestCase):
    """
    Mission 095: the central-library tab's "Exposer à ComfyUI" action
    (LoRALibraryManager.expose_to_comfyui()) and the delete flow's
    mandatory unexpose-first orchestration (MISSION_095.md §5.5) — real
    hardlinks on a real temp directory, never mocked for the nominal
    cases, mirroring LoRAPageCentralLibraryTabTest's own setUp() wiring.
    """

    def setUp(self):
        # Mission 095: this class exercises expose_selected_to_comfyui(),
        # a new production code path that constructs a real QMessageBox
        # on success — armed here as defense in depth (Missions 091/094's
        # established per-class pattern) so that any test in this class
        # that accidentally omits its own QMessageBox patch fails fast
        # and cleanly instead of blocking on a real dialog.
        self.dialog_guard = start_dialog_guard()
        self.addCleanup(stop_dialog_guard, self.dialog_guard)

        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"
        self.library_root = Path(self.tmp_dir) / "CentralLibrary"
        self.expose_root = Path(self.tmp_dir) / "ComfyUISharedLoras"
        self.expose_root.mkdir()

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
        self.application_settings_manager.update(
            lora_library_path=str(self.library_root),
            comfyui_lora_expose_path=str(self.expose_root),
        )

        self.lora_page = LoRAPage(
            self.lora_manager, self.workspace_manager, self.lora_library_manager, self.application_settings_manager
        )
        self.event_bus.subscribe(LORA_LIBRARY_IMPORTED, self.lora_page.update_central_library)
        self.event_bus.subscribe(LORA_LIBRARY_DELETED, self.lora_page.update_central_library)
        self.event_bus.subscribe(LORA_LIBRARY_UPDATED, self.lora_page.update_central_library)

        self.workspace_manager.create(self.folder)
        self.character_manager.create("Aria")

    def _import_entry(self, name="StyleA"):
        source_file = Path(self.tmp_dir) / f"{name}_weights.safetensors"
        source_file.write_bytes(b"weights")
        return self.lora_library_manager.import_lora(
            name=name, file_paths=[str(source_file)], library_root=self.library_root,
        )

    def _confirm_delete_from_library(self, accept: bool):
        # Same established pattern as LoRAPageCentralLibraryTabTest.
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

    def test_expose_button_disabled_with_no_selection_enabled_once_selected(self):
        self._import_entry()
        self.lora_page.update_central_library()

        self.assertFalse(self.lora_page.expose_to_comfyui_button.isEnabled())

        self.lora_page.library_list.setCurrentRow(0)

        self.assertTrue(self.lora_page.expose_to_comfyui_button.isEnabled())

    def test_expose_creates_a_real_hardlink_and_shows_confirmation(self):
        entry = self._import_entry()
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        with patch("src.ui.pages.lora_page.QMessageBox") as mock_cls:
            self.lora_page.expose_selected_to_comfyui()

        mock_cls.information.assert_called_once()
        mock_cls.critical.assert_not_called()

        alias_path = self.expose_root / "AIStudioToolkit" / f"StyleA__{entry.lora_id}.safetensors"
        self.assertTrue(alias_path.is_file())
        self.assertTrue(os.path.samefile(alias_path, entry.files[0]))

    def test_expose_with_no_selection_is_a_no_op(self):
        with patch("src.ui.pages.lora_page.QMessageBox") as mock_cls:
            self.lora_page.expose_selected_to_comfyui()

        mock_cls.assert_not_called()

    def test_expose_shows_error_when_expose_path_is_not_configured(self):
        self.application_settings_manager.update(comfyui_lora_expose_path="")
        self._import_entry()
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        with patch("src.ui.pages.lora_page.QMessageBox") as mock_cls:
            self.lora_page.expose_selected_to_comfyui()

        mock_cls.critical.assert_called_once()

    def test_expose_shows_warning_when_stale_alias_cleanup_fails(self):
        self._import_entry()
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        with patch("src.ui.pages.lora_page.QMessageBox"):
            self.lora_page.expose_selected_to_comfyui()
        lora_id = self.lora_page.library_list.item(0).data(Qt.UserRole)
        self.lora_library_manager.update(lora_id, name="Renamed")
        # update() published LORA_LIBRARY_UPDATED synchronously, which
        # update_central_library() (subscribed) handled by fully
        # rebuilding library_list — no metadata draft was dirty at the
        # time, so selection was reset. Re-select before exposing again.
        self.lora_page.library_list.setCurrentRow(0)

        with patch.object(Path, "unlink", side_effect=OSError("locked")):
            with patch("src.ui.pages.lora_page.QMessageBox") as mock_cls:
                self.lora_page.expose_selected_to_comfyui()

        mock_cls.warning.assert_called_once()
        mock_cls.critical.assert_not_called()

    def test_delete_of_a_never_exposed_entry_still_works_unchanged(self):
        # Non-regression: MISSION_095.md's unexpose-first guard must never
        # affect an entry that was never exposed to ComfyUI.
        entry = self._import_entry()
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        self._confirm_delete_from_library(accept=True)
        self.lora_page.delete_from_library()

        self.assertEqual(self.lora_library_manager.list_loras(), [])

    def test_delete_of_an_exposed_entry_removes_the_alias_first(self):
        entry = self._import_entry()
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        with patch("src.ui.pages.lora_page.QMessageBox"):
            self.lora_page.expose_selected_to_comfyui()

        alias_path = self.expose_root / "AIStudioToolkit" / f"StyleA__{entry.lora_id}.safetensors"
        self.assertTrue(alias_path.is_file())

        self._confirm_delete_from_library(accept=True)
        self.lora_page.delete_from_library()

        self.assertEqual(self.lora_library_manager.list_loras(), [])
        self.assertFalse(alias_path.exists())

    def test_delete_is_refused_when_unexpose_fails_and_the_entry_survives(self):
        entry = self._import_entry()
        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)
        with patch("src.ui.pages.lora_page.QMessageBox"):
            self.lora_page.expose_selected_to_comfyui()

        alias_path = self.expose_root / "AIStudioToolkit" / f"StyleA__{entry.lora_id}.safetensors"
        self.assertTrue(alias_path.is_file())

        self._confirm_delete_from_library(accept=True)

        with patch.object(
            self.lora_library_manager, "unexpose_from_comfyui",
            side_effect=LoRALibraryError("locked by another process"),
        ):
            with patch.object(self.lora_library_manager, "delete") as delete_mock:
                self.lora_page.delete_from_library()
                delete_mock.assert_not_called()

        # Nothing was touched: the entry, its file and the alias all
        # survive exactly as before the refused deletion attempt.
        self.assertEqual(len(self.lora_library_manager.list_loras()), 1)
        self.assertTrue(alias_path.is_file())
        self.assertTrue(Path(entry.files[0]).is_file())

    def test_dialog_guard_converts_a_genuinely_unexpected_dialog_into_a_clean_failure(self):
        """
        Mission 095: dedicated proof that the guard armed in setUp()
        above actually works in this class — mirrors the established
        proof pattern from Missions 091/094
        (test_qt_dialog_safety_net.py::QtDialogSafetyNetTest,
        MainWindowInferencePendingResultGuardTest). A real, deliberately
        unmocked QMessageBox must produce a fast, clean
        UnexpectedDialogError — never a block requiring human
        intervention, which is exactly the failure mode this test class
        itself hit once during Mission 095's own development before this
        guard was armed here (see MISSION_095.md).
        """

        def trigger():
            QMessageBox.warning(
                self.lora_page, "Mission 095 Test Title", "Mission 095 Test Text"
            )
            stop_dialog_guard(self.dialog_guard)

        exception = assert_dialog_guard_intercepts_promptly(self, trigger)
        self.assertIn("Mission 095 Test Title", str(exception))


class LoRAPageForgeAndMultiEngineExposureTest(unittest.TestCase):
    """
    Mission 135: LoRAPage.delete_from_library()'s multi-engine
    desexposition orchestration (MISSION_135.md §2.4) — both ComfyUI and
    Forge are configured here so partial-failure and both-engines
    scenarios can be exercised directly, extending
    LoRAPageComfyUIExposureTest above (which only configures ComfyUI and
    therefore never reaches Forge or the two-engines-at-once cases).
    Forge exposure has no dedicated UI button (unlike ComfyUI's "Exposer
    à ComfyUI") — it is only ever created implicitly at generation time
    by InferencePage — so tests establish an existing Forge alias
    directly via LoRALibraryManager.expose_to_forge(), exactly as
    InferencePage itself would.
    """

    def setUp(self):
        self.dialog_guard = start_dialog_guard()
        self.addCleanup(stop_dialog_guard, self.dialog_guard)

        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"
        self.library_root = Path(self.tmp_dir) / "CentralLibrary"
        self.comfyui_expose_root = Path(self.tmp_dir) / "ComfyUISharedLoras"
        self.comfyui_expose_root.mkdir()
        self.forge_expose_root = Path(self.tmp_dir) / "ForgeSharedLoras"
        self.forge_expose_root.mkdir()

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
        self.application_settings_manager.update(
            lora_library_path=str(self.library_root),
            comfyui_lora_expose_path=str(self.comfyui_expose_root),
            forge_lora_expose_path=str(self.forge_expose_root),
        )

        self.lora_page = LoRAPage(
            self.lora_manager, self.workspace_manager, self.lora_library_manager, self.application_settings_manager
        )
        self.event_bus.subscribe(LORA_LIBRARY_IMPORTED, self.lora_page.update_central_library)
        self.event_bus.subscribe(LORA_LIBRARY_DELETED, self.lora_page.update_central_library)
        self.event_bus.subscribe(LORA_LIBRARY_UPDATED, self.lora_page.update_central_library)

        self.workspace_manager.create(self.folder)
        self.character_manager.create("Aria")

    def _import_entry(self, name="StyleA"):
        source_file = Path(self.tmp_dir) / f"{name}_weights.safetensors"
        source_file.write_bytes(b"weights")
        return self.lora_library_manager.import_lora(
            name=name, file_paths=[str(source_file)], library_root=self.library_root,
        )

    def _confirm_delete_from_library(self, accept: bool):
        # Same established pattern as LoRAPageComfyUIExposureTest above.
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

    def test_delete_of_forge_only_exposed_entry_removes_the_alias_first(self):
        entry = self._import_entry()
        result = self.lora_library_manager.expose_to_forge(entry, self.forge_expose_root)
        alias_path = self.forge_expose_root / result.alias_name.replace("\\", "/")
        self.assertTrue(alias_path.is_file())

        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        self._confirm_delete_from_library(accept=True)
        self.lora_page.delete_from_library()

        self.assertEqual(self.lora_library_manager.list_loras(), [])
        self.assertFalse(alias_path.exists())

    def test_delete_of_entry_exposed_to_both_engines_removes_both_aliases(self):
        entry = self._import_entry()
        comfyui_result = self.lora_library_manager.expose_to_comfyui(entry, self.comfyui_expose_root)
        forge_result = self.lora_library_manager.expose_to_forge(entry, self.forge_expose_root)
        comfyui_alias = self.comfyui_expose_root / comfyui_result.alias_name.replace("\\", "/")
        forge_alias = self.forge_expose_root / forge_result.alias_name.replace("\\", "/")

        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        self._confirm_delete_from_library(accept=True)
        self.lora_page.delete_from_library()

        self.assertEqual(self.lora_library_manager.list_loras(), [])
        self.assertFalse(comfyui_alias.exists())
        self.assertFalse(forge_alias.exists())

    def test_delete_is_refused_when_forge_unexpose_fails_and_entry_survives(self):
        entry = self._import_entry()
        self.lora_library_manager.expose_to_forge(entry, self.forge_expose_root)

        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        self._confirm_delete_from_library(accept=True)

        with patch.object(
            self.lora_library_manager, "unexpose_from_forge",
            side_effect=LoRALibraryError("locked by another process"),
        ):
            with patch.object(self.lora_library_manager, "delete") as delete_mock:
                self.lora_page.delete_from_library()
                delete_mock.assert_not_called()

        self.assertEqual(len(self.lora_library_manager.list_loras()), 1)
        self.assertTrue(Path(entry.files[0]).is_file())

    def test_delete_still_attempts_forge_when_comfyui_unexpose_fails_first(self):
        # Mission 135 IMPORTANT: Forge must never be short-circuited just
        # because ComfyUI failed first — both are always attempted.
        entry = self._import_entry()
        self.lora_library_manager.expose_to_comfyui(entry, self.comfyui_expose_root)
        forge_result = self.lora_library_manager.expose_to_forge(entry, self.forge_expose_root)
        forge_alias = self.forge_expose_root / forge_result.alias_name.replace("\\", "/")
        self.assertTrue(forge_alias.is_file())

        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        self._confirm_delete_from_library(accept=True)

        with patch.object(
            self.lora_library_manager, "unexpose_from_comfyui",
            side_effect=LoRALibraryError("locked by another process"),
        ):
            with patch.object(self.lora_library_manager, "delete") as delete_mock:
                self.lora_page.delete_from_library()
                delete_mock.assert_not_called()

        # Forge was attempted independently despite the earlier ComfyUI
        # failure, and its alias was genuinely removed — the canonical
        # entry itself still survives untouched (delete() never called).
        self.assertFalse(forge_alias.exists())
        self.assertEqual(len(self.lora_library_manager.list_loras()), 1)

    def test_delete_is_refused_with_both_diagnostics_when_both_engines_fail(self):
        entry = self._import_entry()
        self.lora_library_manager.expose_to_comfyui(entry, self.comfyui_expose_root)
        self.lora_library_manager.expose_to_forge(entry, self.forge_expose_root)

        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        mock_cls = self._confirm_delete_from_library(accept=True)

        with patch.object(
            self.lora_library_manager, "unexpose_from_comfyui",
            side_effect=LoRALibraryError("ComfyUI alias locked"),
        ):
            with patch.object(
                self.lora_library_manager, "unexpose_from_forge",
                side_effect=LoRALibraryError("Forge alias locked"),
            ):
                with patch.object(self.lora_library_manager, "delete") as delete_mock:
                    self.lora_page.delete_from_library()
                    delete_mock.assert_not_called()

        # A single aggregated diagnostic identifies both failing engines
        # — never masking one behind the other, never two stacked
        # QMessageBoxes.
        mock_cls.critical.assert_called_once()
        message = mock_cls.critical.call_args[0][2]
        self.assertIn("ComfyUI", message)
        self.assertIn("ComfyUI alias locked", message)
        self.assertIn("Forge", message)
        self.assertIn("Forge alias locked", message)

        self.assertEqual(len(self.lora_library_manager.list_loras()), 1)

    def test_partial_desexposition_is_recoverable_on_a_later_retry(self):
        # Mission 135: no rollback of an already-removed alias — a
        # partial desexposition (ComfyUI already gone, Forge still
        # failing) must leave the canonical entry intact and safely
        # retryable, converging to full deletion once the underlying
        # Forge issue is resolved.
        entry = self._import_entry()
        comfyui_result = self.lora_library_manager.expose_to_comfyui(entry, self.comfyui_expose_root)
        comfyui_alias = self.comfyui_expose_root / comfyui_result.alias_name.replace("\\", "/")
        self.lora_library_manager.expose_to_forge(entry, self.forge_expose_root)

        self.lora_page.update_central_library()
        self.lora_page.library_list.setCurrentRow(0)

        self._confirm_delete_from_library(accept=True)
        with patch.object(
            self.lora_library_manager, "unexpose_from_forge",
            side_effect=LoRALibraryError("locked by another process"),
        ):
            self.lora_page.delete_from_library()

        # First attempt: ComfyUI alias genuinely removed, Forge failed,
        # canonical entry survives.
        self.assertFalse(comfyui_alias.exists())
        self.assertEqual(len(self.lora_library_manager.list_loras()), 1)

        # Second attempt, Forge no longer failing: ComfyUI unexpose is
        # now a natural no-op (already gone), Forge succeeds, deletion
        # completes.
        self.lora_page.library_list.setCurrentRow(0)
        self._confirm_delete_from_library(accept=True)
        self.lora_page.delete_from_library()

        self.assertEqual(self.lora_library_manager.list_loras(), [])



# ---------------------------------------------------------------------------------------------------------------------
# Mission 171 — LoRAPage.name_edit: protection of an unsaved rename draft.
#
# Same three families as PromptsPage (kept apart on purpose):
#   - LoRAPageNameDraftRegressionTest : failed before the correction (observable behaviour only; runnable on old code).
#   - LoRAPageNameDraftInvariantTest  : already true before the correction and must stay true (runnable on old code).
#   - LoRAPageNameEditorContractTest  : the new contract itself (reads the private rename-editor state).
# Mission 171 left the LoRA metadata draft (candidate B) uncorrected and asserted nothing about it; Mission 172 corrected it
# (see the Mission 172 section below). The coexistence test here only covers the refreshes and the successful name commit.
# ---------------------------------------------------------------------------------------------------------------------

class _LoRANameDraftCase(unittest.TestCase):
    """
    Shared fixture: real EventBus/Managers wired exactly like MainWindow's split (general refreshes -> update_loras(),
    context resets -> reset_for_context_change()), one Workspace with two LoRAs, the page shown and active. Counts
    LoRAManager.update_name() calls (and the ids it receives), Workspace persistence and failure dialogs separately.
    Dialog mocks are installed first so that they outlive the widget release (cleanups run last-in first-out).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "NameDraftProject"

        self.critical_calls = []
        self.critical_hook = None
        self.unexpected_dialogs = []
        self._dialog_patches = [
            patch.object(QMessageBox, "critical", side_effect=self._on_critical),
            patch.object(QMessageBox, "warning", side_effect=self._on_unexpected_dialog),
            patch.object(QMessageBox, "information", side_effect=self._on_unexpected_dialog),
            patch.object(QMessageBox, "exec", new=lambda box, *a, **k: self._on_unexpected_dialog(box)),
        ]
        for dialog_patch in self._dialog_patches:
            dialog_patch.start()
            self.addCleanup(dialog_patch.stop)

        self.update_name_calls = 0
        self.update_name_args = []
        self.persist_calls = 0
        self.fail_persist = False
        self._real_save = WorkspaceStorage.save
        save_patch = patch.object(WorkspaceStorage, "save", new=staticmethod(self._counting_save))
        save_patch.start()
        self.addCleanup(save_patch.stop)

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.lora_manager = LoRAManager(self.character_manager, self.workspace_manager, event_bus=self.event_bus)
        self.lora_library_manager = LoRALibraryManager(storage_directory=Path(self.tmp_dir) / "lora_library")
        self.application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings",
            lora_library_manager=self.lora_library_manager,
        )

        real_update_name = self.lora_manager.update_name

        def counted_update_name(*args, **kwargs):
            self.update_name_calls += 1
            self.update_name_args.append(args)
            return real_update_name(*args, **kwargs)

        self.lora_manager.update_name = counted_update_name

        self.page = LoRAPage(
            self.lora_manager, self.workspace_manager, self.lora_library_manager, self.application_settings_manager
        )
        self.page.show()
        self.page.activateWindow()
        QApplication.processEvents()
        # Registered after the dialog/persistence patches: runs before them.
        self.addCleanup(self._release_page)

        for event_name in (WORKSPACE_SAVED, WORKSPACE_RENAMED, CHARACTER_CREATED):
            self.event_bus.subscribe(event_name, self.page.update_loras)
        for event_name in LORA_EVENTS:
            self.event_bus.subscribe(event_name, self.page.update_loras)
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED, CHARACTER_SELECTED, CHARACTER_DELETED):
            self.event_bus.subscribe(event_name, self.page.reset_for_context_change)

        create_workspace_with_default_character(self.workspace_manager, self.character_manager, self.folder)
        self.lora_a = self.lora_manager.create("LoraAlpha")
        self.lora_b = self.lora_manager.create("LoraBeta")
        self.lora_manager.select(self.lora_a.lora_id)
        self.reset_counters()

    def tearDown(self):
        self.assertEqual(self.unexpected_dialogs, [], "an unexpected dialog was opened")

    # --- fixture plumbing -------------------------------------------------------------------------------------

    def _on_critical(self, *args, **kwargs):
        self.critical_calls.append(args)
        if self.critical_hook is not None:
            self.critical_hook()

    def _on_unexpected_dialog(self, *args, **kwargs):
        self.unexpected_dialogs.append(args)
        return QMessageBox.Cancel

    def _counting_save(self, folder, data):
        self.persist_calls += 1
        if self.fail_persist:
            raise WorkspaceStorageError("forced persistence failure")
        return self._real_save(folder, data)

    def _release_page(self):
        self.page.hide()
        self.page.close()
        self.page.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QApplication.processEvents()

    def reset_counters(self):
        self.update_name_calls = 0
        self.update_name_args.clear()
        self.persist_calls = 0
        self.critical_calls.clear()

    # --- real input -------------------------------------------------------------------------------------------

    def type_draft(self, text):
        self.page.name_edit.setFocus()
        QApplication.processEvents()
        self.assertTrue(self.page.name_edit.hasFocus(), "the name field must really hold the focus")
        self.page.name_edit.selectAll()
        QTest.keyClicks(self.page.name_edit, text)
        QApplication.processEvents()

    def lose_focus(self):
        self.page.lora_list.setFocus()
        QApplication.processEvents()
        self.assertFalse(self.page.name_edit.hasFocus())

    def click_lora(self, lora_id):
        for row in range(self.page.lora_list.count()):
            item = self.page.lora_list.item(row)
            if item.data(Qt.UserRole) == lora_id:
                QTest.mouseClick(
                    self.page.lora_list.viewport(), Qt.LeftButton, Qt.NoModifier,
                    self.page.lora_list.visualItemRect(item).center(),
                )
                QApplication.processEvents()
                return
        self.fail("LoRA not found in the list")

    def persisted_name(self, lora_id):
        return next(l["name"] for l in self.lora_manager.list_loras() if l["lora_id"] == lora_id)

    def listed_names(self):
        return [self.page.lora_list.item(row).text() for row in range(self.page.lora_list.count())]


class LoRAPageNameDraftRegressionTest(_LoRANameDraftCase):
    """Behaviours that failed before Mission 171 (observable behaviour only)."""

    def test_draft_with_focus_survives_repeated_workspace_saved_then_blur_commits_once(self):
        self.type_draft("Draft Name")
        self.reset_counters()

        for _ in range(3):
            self.workspace_manager.save()
        QApplication.processEvents()

        self.assertEqual(self.page.name_edit.text(), "Draft Name")
        self.assertEqual(self.update_name_calls, 0)
        self.assertEqual(self.persisted_name(self.lora_a.lora_id), "LoraAlpha")

        persisted_before_blur = self.persist_calls
        self.lose_focus()

        self.assertEqual(self.persisted_name(self.lora_a.lora_id), "Draft Name")
        self.assertEqual(self.update_name_calls, 1)
        self.assertEqual(self.persist_calls - persisted_before_blur, 1)

    def test_draft_survives_workspace_renamed_and_commits_to_the_same_lora(self):
        self.type_draft("Draft Across Rename")
        old_workspace = self.workspace_manager.current_workspace

        self.workspace_manager.rename("NameDraftProjectRenamed")
        QApplication.processEvents()

        self.assertIsNot(self.workspace_manager.current_workspace, old_workspace)
        self.assertEqual(self.page.name_edit.text(), "Draft Across Rename")

        self.lose_focus()

        self.assertEqual(self.lora_manager.active_lora_id, self.lora_a.lora_id)
        self.assertEqual(self.persisted_name(self.lora_a.lora_id), "Draft Across Rename")
        self.assertEqual(self.persisted_name(self.lora_b.lora_id), "LoraBeta")

    def test_forced_reentrancy_during_failure_dialog_counts_one_update_one_persistence_one_dialog(self):
        self.type_draft("Rejected Name")
        self.reset_counters()
        self.fail_persist = True
        fired = []

        def second_commit_while_the_dialog_is_open():
            if not fired:
                fired.append(True)
                self.page.name_edit.editingFinished.emit()

        self.critical_hook = second_commit_while_the_dialog_is_open
        self.page.name_edit.editingFinished.emit()
        self.fail_persist = False

        self.assertEqual(self.update_name_calls, 1)
        self.assertEqual(self.persist_calls, 1)
        self.assertEqual(len(self.critical_calls), 1)
        self.assertEqual(self.page.name_edit.text(), "LoraAlpha")
        self.assertEqual(self.persisted_name(self.lora_a.lora_id), "LoraAlpha")

    def test_name_draft_coexists_with_the_metadata_draft_through_refreshes_and_a_name_commit(self):
        self.page.engine_edit.setText("META-DRAFT")
        self.type_draft("Name Draft")
        self.assertTrue(self.page._metadata_dirty)

        self.lora_manager.create("LoraGamma")   # LORA_CREATED without any selection change
        self.workspace_manager.save()
        QApplication.processEvents()

        self.assertEqual(self.page.name_edit.text(), "Name Draft")
        self.assertEqual(self.page.engine_edit.text(), "META-DRAFT")
        self.assertTrue(self.page._metadata_dirty)

        self.lose_focus()

        self.assertEqual(self.persisted_name(self.lora_a.lora_id), "Name Draft")
        self.assertEqual(self.page.engine_edit.text(), "META-DRAFT")
        self.assertTrue(self.page._metadata_dirty)
        self.assertEqual(self.lora_manager.active_lora.engine, "")


class LoRAPageNameDraftInvariantTest(_LoRANameDraftCase):
    """Behaviours already true before Mission 171, which must stay true (observable behaviour only)."""

    def test_focused_but_unmodified_field_follows_an_external_rename_and_a_reverted_draft_is_refreshable(self):
        self.page.name_edit.setFocus()
        QApplication.processEvents()

        self.lora_manager.update_name(self.lora_a.lora_id, "ExternalRename")
        self.assertEqual(self.page.name_edit.text(), "ExternalRename")

        self.type_draft("TEMP")
        self.page.name_edit.setText("ExternalRename")   # back to the text the field was loaded with
        self.lora_manager.update_name(self.lora_a.lora_id, "ExternalRename2")

        self.assertEqual(self.page.name_edit.text(), "ExternalRename2")

    def test_programmatic_selection_change_never_transfers_the_draft_and_a_late_blur_writes_nothing(self):
        self.type_draft("Draft For Alpha")
        self.reset_counters()

        self.lora_manager.select(self.lora_b.lora_id)
        QApplication.processEvents()

        self.assertEqual(self.page.name_edit.text(), "LoraBeta")

        self.page.name_edit.editingFinished.emit()   # the blur that arrives afterwards

        self.assertEqual(self.persist_calls, 0)
        self.assertEqual(self.persisted_name(self.lora_a.lora_id), "LoraAlpha")
        self.assertEqual(self.persisted_name(self.lora_b.lora_id), "LoraBeta")

    def test_real_click_on_another_lora_commits_the_draft_to_the_first_one_then_shows_the_second(self):
        self.type_draft("Committed By Click")
        self.reset_counters()

        self.click_lora(self.lora_b.lora_id)

        self.assertEqual(self.persisted_name(self.lora_a.lora_id), "Committed By Click")
        self.assertEqual(self.lora_manager.active_lora_id, self.lora_b.lora_id)
        self.assertEqual(self.page.name_edit.text(), "LoraBeta")
        self.assertEqual(self.update_name_calls, 1)
        self.assertEqual(self.persist_calls, 1)

    def test_workspace_close_and_reopen_never_resurrect_a_draft(self):
        self.type_draft("Draft Before Close")

        self.workspace_manager.close()
        self.assertEqual(self.page.name_edit.text(), "")

        self.workspace_manager.open(self.folder)
        self.assertEqual(self.page.name_edit.text(), "")

        self.reset_counters()
        self.page.name_edit.editingFinished.emit()
        self.assertEqual(self.update_name_calls, 0)
        self.assertEqual(self.persist_calls, 0)

        self.lora_manager.select(self.lora_a.lora_id)
        self.assertEqual(self.page.name_edit.text(), "LoraAlpha")

    def test_deleting_the_active_lora_clears_the_editor_and_a_blur_writes_nothing(self):
        self.type_draft("Draft Of A Deleted LoRA")

        self.lora_manager.delete(self.lora_a.lora_id)
        QApplication.processEvents()
        self.assertEqual(self.page.name_edit.text(), "")

        self.reset_counters()
        self.page.name_edit.editingFinished.emit()
        self.assertEqual(self.update_name_calls, 0)
        self.assertEqual(self.persist_calls, 0)

    def test_successful_commit_updates_editor_and_list_and_a_later_refresh_or_no_op_changes_nothing(self):
        self.type_draft("Committed Name")
        self.reset_counters()

        self.page.name_edit.editingFinished.emit()

        self.assertEqual((self.update_name_calls, self.persist_calls, len(self.critical_calls)), (1, 1, 0))
        self.assertEqual(self.page.name_edit.text(), "Committed Name")
        self.assertTrue(any(name.startswith("Committed Name") for name in self.listed_names()))

        self.reset_counters()
        self.workspace_manager.save()
        self.assertEqual(self.page.name_edit.text(), "Committed Name")
        self.assertEqual(self.update_name_calls, 0)

        self.reset_counters()
        self.page.name_edit.editingFinished.emit()   # same text again: idempotent no-op
        self.assertEqual(self.persist_calls, 0)

    def test_failed_commit_restores_the_previous_name_in_the_domain_and_in_the_editor(self):
        self.type_draft("Rejected Name")
        self.reset_counters()
        self.fail_persist = True

        self.page.name_edit.editingFinished.emit()
        self.fail_persist = False

        self.assertEqual((self.update_name_calls, self.persist_calls, len(self.critical_calls)), (1, 1, 1))
        self.assertEqual(self.persisted_name(self.lora_a.lora_id), "LoraAlpha")
        self.assertEqual(self.page.name_edit.text(), "LoraAlpha")

    def test_enter_then_real_focus_loss_persists_once(self):
        self.type_draft("Entered Name")
        self.reset_counters()

        QTest.keyClick(self.page.name_edit, Qt.Key_Return)
        QApplication.processEvents()
        self.lose_focus()

        self.assertEqual(self.persist_calls, 1)
        self.assertEqual(self.persisted_name(self.lora_a.lora_id), "Entered Name")


class LoRAPageNameEditorContractTest(_LoRANameDraftCase):
    """The Mission 171 contract itself: reads the private rename-editor state (not runnable on the previous code)."""

    def test_owner_id_that_differs_from_the_active_lora_triggers_no_manager_call_and_reloads_the_editor(self):
        self.page._name_editor_owner_id = "some-other-id"
        self.page.name_edit.setText("SHOULD-NOT-BE-WRITTEN")
        self.reset_counters()

        self.page.name_edit.editingFinished.emit()

        self.assertEqual(self.update_name_calls, 0)
        self.assertEqual(self.persist_calls, 0)
        self.assertEqual(self.page.name_edit.text(), "LoraAlpha")
        self.assertEqual(self.page._name_editor_owner_id, self.lora_a.lora_id)

    def test_loaded_value_and_owner_are_rebased_after_a_successful_commit(self):
        self.assertEqual(self.page._name_editor_owner_id, self.lora_a.lora_id)
        self.assertEqual(self.page._name_editor_loaded_value, "LoraAlpha")

        self.type_draft("Rebased Name")
        self.page.name_edit.editingFinished.emit()

        self.assertEqual(self.page._name_editor_loaded_value, "Rebased Name")
        self.assertEqual(self.page._name_editor_owner_id, self.lora_a.lora_id)

    def test_the_verified_owner_id_is_what_the_manager_receives(self):
        self.type_draft("By Owner Id")
        self.reset_counters()

        self.page.name_edit.editingFinished.emit()

        self.assertEqual(self.update_name_args, [(self.lora_a.lora_id, "By Owner Id")])

    def test_reentrancy_flag_is_held_during_the_dialog_and_released_afterwards(self):
        self.type_draft("Rejected Name")
        self.fail_persist = True
        seen = []
        self.critical_hook = lambda: seen.append(self.page._renaming_in_progress)

        self.page.name_edit.editingFinished.emit()
        self.fail_persist = False

        self.assertEqual(seen, [True])
        self.assertFalse(self.page._renaming_in_progress)
        self.assertEqual(self.page._name_editor_loaded_value, "LoraAlpha")
        self.assertEqual(self.page._name_editor_owner_id, self.lora_a.lora_id)

    def test_failure_resync_is_the_general_refresh_after_the_dialog_and_under_the_reentrancy_flag(self):
        # Mission 172 — deliberate replacement of test_force_refresh_stays_on_the_failure_path_after_the_dialog_and_under_the_
        # reentrancy_flag, which pinned the forced refresh on this branch. The failed rename now re-reads the Domain through
        # the general refresh update_loras() (never the forced one), still after the dialog and while the guard is held. On
        # success no such direct call follows the Manager call: the refresh seen there is the synchronous one delivered
        # through WORKSPACE_SAVED (guard held, before any dialog), observed separately instead of being asserted away.
        direct_refreshes, forced_refreshes, saved_events = [], [], []
        real_update_loras = self.page.update_loras
        real_force_refresh = self.page._force_refresh_lora

        def update_spy(*args, **kwargs):
            direct_refreshes.append((self.page._renaming_in_progress, len(self.critical_calls)))
            return real_update_loras(*args, **kwargs)

        def force_spy():
            forced_refreshes.append((self.page._renaming_in_progress, len(self.critical_calls)))
            return real_force_refresh()

        self.page.update_loras = update_spy       # direct calls only: the EventBus keeps the original bound method
        self.page._force_refresh_lora = force_spy
        self.event_bus.subscribe(
            WORKSPACE_SAVED,
            lambda payload=None: saved_events.append((self.page._renaming_in_progress, len(self.critical_calls))),
        )
        self.type_draft("Rejected Name")
        self.fail_persist = True

        self.page.name_edit.editingFinished.emit()
        self.fail_persist = False

        self.assertEqual(direct_refreshes, [(True, 1)])   # once, flag still held, dialog already shown
        self.assertEqual(forced_refreshes, [])
        self.assertEqual(saved_events, [])                # nothing was persisted, so no event
        self.assertFalse(self.page._renaming_in_progress)
        self.assertEqual(self.page.name_edit.text(), "LoraAlpha")

        direct_refreshes.clear()
        saved_events.clear()
        self.critical_calls.clear()
        self.type_draft("Accepted Name")
        self.page.name_edit.editingFinished.emit()

        self.assertEqual(direct_refreshes, [])            # no direct call once the Manager has returned...
        self.assertEqual(saved_events, [(True, 0)])       # ...the refresh came synchronously via WORKSPACE_SAVED, guard held
        self.assertEqual(forced_refreshes, [])
        self.assertFalse(self.page._renaming_in_progress)

    def test_reconciliation_failure_propagates_releases_the_flag_and_does_not_block_a_later_commit(self):
        self.type_draft("Draft Before Failure")
        real_reload = self.page._reload_name_editor

        def exploding_reload():
            raise RuntimeError("reconciliation failure")

        self.page._reload_name_editor = exploding_reload
        with self.assertRaises(RuntimeError):
            self.page.rename_lora()
        self.page._reload_name_editor = real_reload

        self.assertFalse(self.page._renaming_in_progress)

        self.reset_counters()
        self.page.name_edit.setText("Second Attempt")
        self.page.rename_lora()
        self.assertEqual(self.update_name_calls, 1)
        self.assertEqual(self.persisted_name(self.lora_a.lora_id), "Second Attempt")

    def test_context_reset_resynchronises_the_editor_even_with_a_draft(self):
        self.type_draft("Draft Before Reset")

        self.workspace_manager.close()

        self.assertIsNone(self.page._name_editor_owner_id)
        self.assertEqual(self.page._name_editor_loaded_value, "")
        self.assertEqual(self.page.name_edit.text(), "")



# ---------------------------------------------------------------------------------------------------------------------
# Mission 172 — LoRAPage: an unsaved METADATA draft (engine / architecture / trigger_word / version) survives the failure
# of ANOTHER operation (rename, file import, file removal); the resync those operations need is kept.
#
# Three families, kept apart on purpose:
#   - LoRAPageMetadataDraftRegressionTest : failed on the previous code (observable behaviour only; runnable on old code).
#   - LoRAPageMetadataDraftInvariantTest  : already true before the correction and must stay true (runnable on old code).
#   - LoRAPageFailureResyncContractTest   : the new contract itself (private state and helper calls — not a proof of the
#                                           user-visible defect, and not runnable as such on the previous code).
# Out of scope and unchanged: the failure of save_metadata(), the failed Save of confirm_context_change() and of
# add_to_central_library(), the explicit "Ignorer" choice and the context resets keep the forced refresh (see the
# invariants and the contract tests below, and LoRAPageMetadataPersistenceFailureTest / LoRAPageAddToCentralLibraryTest).
# Environment bound: real Qt events through the offscreen platform plugin; the focus order observed there (a real click or a
# real blur validates the name field first) is not asserted for other platforms.
# ---------------------------------------------------------------------------------------------------------------------

METADATA_FIELDS = ("engine", "architecture", "trigger_word", "version")
DRAFT_VALUES = {
    "engine": "DraftEngine",
    "architecture": "DraftArchitecture",
    "trigger_word": "DraftTrigger",
    "version": "DraftVersion",
}
EMPTY_METADATA = {field: "" for field in METADATA_FIELDS}
EXTERNAL_FILES = ["fileA.safetensors", "fileB.safetensors", "fileC.safetensors"]
FAILING_OPERATIONS = ("rename", "import", "remove")


class _LoRAMetadataDraftCase(_LoRANameDraftCase):
    """
    Fixture of the Mission 171 name-draft tests (real EventBus/Managers wired like MainWindow, dialog mocks installed first
    and outliving the widget release), plus: three external file references on the active LoRA, a recorder for the page's own
    dirty-state guard dialog (answer configurable), and real-input helpers.
    """

    def setUp(self):
        super().setUp()
        self.guard_dialogs = []
        self.guard_answer = QMessageBox.Cancel
        # Started after the Mission 171 dialog mocks, so it is stopped before them: the widget release still runs
        # under a dialog mock.
        guard_patch = patch.object(QMessageBox, "exec", new=lambda box, *a, **k: self._on_guard_dialog(box))
        guard_patch.start()
        self.addCleanup(guard_patch.stop)

        self.lora_manager.add_files(list(EXTERNAL_FILES))
        QApplication.processEvents()
        self.reset_counters()

    def _on_guard_dialog(self, box):
        self.guard_dialogs.append(box.text())
        return self.guard_answer

    # --- observation helpers ------------------------------------------------------------------------------------

    def widget_for(self, field):
        return {
            "engine": self.page.engine_edit,
            "architecture": self.page.architecture_edit,
            "trigger_word": self.page.trigger_word_edit,
            "version": self.page.version_edit,
        }[field]

    def metadata_texts(self):
        return {field: self.widget_for(field).text() for field in METADATA_FIELDS}

    def domain_metadata(self, lora=None):
        lora = lora or self.lora_a
        return {field: getattr(lora, field) for field in METADATA_FIELDS}

    def domain_state(self):
        lora = self.lora_a
        return {"name": lora.name, "files": list(lora.files), "thumbnail": lora.thumbnail, **self.domain_metadata(lora)}

    def project_json(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            return json.load(f)

    def persisted_metadata(self, lora_id):
        for character in self.project_json()["characters"]:
            for lora in character["loras"]:
                if lora["lora_id"] == lora_id:
                    return {field: lora[field] for field in METADATA_FIELDS}
        self.fail("LoRA not found in project.json")

    def state_before(self):
        return {"domain": self.domain_state(), "json": self.project_json()}

    def draft_is_pending(self):
        """True when the page still holds an unsaved metadata draft: asked through the page's own public guard, answered
        Cancel (so nothing is saved or discarded); the guard dialog this question may open is not counted."""
        shown_before = len(self.guard_dialogs)
        answer_before, self.guard_answer = self.guard_answer, QMessageBox.Cancel
        try:
            return self.page.confirm_context_change() is False
        finally:
            self.guard_answer = answer_before
            del self.guard_dialogs[shown_before:]

    def selected_files(self):
        return sorted(item.text() for item in self.page.files_list.selectedItems())

    def listed_files(self):
        return [self.page.files_list.item(row).text() for row in range(self.page.files_list.count())]

    # --- real input ---------------------------------------------------------------------------------------------

    def type_into(self, edit, text):
        edit.setFocus()
        QApplication.processEvents()
        self.assertTrue(edit.hasFocus(), "the field must really hold the focus")
        edit.selectAll()
        QTest.keyClicks(edit, text)
        QApplication.processEvents()

    def type_metadata(self, values=None):
        for field, value in (values or DRAFT_VALUES).items():
            self.type_into(self.widget_for(field), value)

    def click_button(self, button):
        QTest.mouseClick(button, Qt.LeftButton, Qt.NoModifier, button.rect().center())
        QApplication.processEvents()

    def click_file(self, row, modifier=Qt.NoModifier):
        item = self.page.files_list.item(row)
        QTest.mouseClick(
            self.page.files_list.viewport(), Qt.LeftButton, modifier, self.page.files_list.visualItemRect(item).center()
        )
        QApplication.processEvents()

    def select_files(self, *rows):
        self.click_file(rows[0])
        for row in rows[1:]:
            self.click_file(row, Qt.ControlModifier)

    def arrange(self, draft):
        """A metadata draft (optional) and two selected files (fileA, fileC) on the active LoRA, through real input."""
        if draft:
            self.type_metadata()
        self.select_files(0, 2)
        self.assertEqual(self.selected_files(), ["fileA.safetensors", "fileC.safetensors"])

    def fail_operation(self, operation):
        """Runs one of the three operations through its real path while persistence is rejected: a real blur of the name
        field (rename), a real click on the import button (file dialog answered with one new file), a real click on the
        removal button (the selection must already exist)."""
        self.fail_persist = True
        try:
            if operation == "rename":
                self.type_into(self.page.name_edit, "RejectedName")
                self.lose_focus()
            elif operation == "import":
                with patch("src.ui.pages.lora_page.QFileDialog.getOpenFileNames", return_value=(["fileD.safetensors"], "")):
                    self.click_button(self.page.import_files_button)
            elif operation == "remove":
                self.click_button(self.page.remove_files_button)
            else:
                raise ValueError(operation)
        finally:
            self.fail_persist = False
        QApplication.processEvents()

    def assert_rolled_back(self, before):
        """The operation itself failed cleanly: one persistence attempt, one dialog, Domain and project.json unchanged."""
        self.assertEqual(len(self.critical_calls), 1)
        self.assertEqual(self.persist_calls, 1)
        self.assertEqual(self.domain_state(), before["domain"])
        self.assertEqual(self.project_json(), before["json"])


class LoRAPageMetadataDraftRegressionTest(_LoRAMetadataDraftCase):
    """Behaviours that failed before Mission 172 (observable behaviour only)."""

    def _draft_survives(self, operation):
        self.arrange(draft=True)
        self.reset_counters()
        before = self.state_before()

        self.fail_operation(operation)

        self.assert_rolled_back(before)
        self.assertEqual(self.metadata_texts(), DRAFT_VALUES)
        self.assertTrue(self.draft_is_pending())
        self.assertEqual(self.domain_metadata(), EMPTY_METADATA)   # nothing of the draft was written
        if operation == "rename":
            self.assertEqual(self.page.name_edit.text(), "LoraAlpha")   # the rejected name itself is still restored

    def test_metadata_draft_survives_a_failed_rename(self):
        self._draft_survives("rename")

    def test_metadata_draft_survives_a_failed_file_import(self):
        self._draft_survives("import")

    def test_metadata_draft_survives_a_failed_file_removal(self):
        self._draft_survives("remove")

    def _single_field_draft_survives_then_saves(self, operation):
        for field in METADATA_FIELDS:
            with self.subTest(operation=operation, field=field):
                typed = f"typed-{operation}-{field}"
                values_before = self.domain_metadata()
                self.type_into(self.widget_for(field), typed)
                self.select_files(0, 2)
                self.reset_counters()
                before = self.state_before()

                self.fail_operation(operation)

                self.assert_rolled_back(before)
                self.assertEqual(self.metadata_texts(), {**values_before, field: typed})
                self.assertTrue(self.draft_is_pending())

                self.click_button(self.page.save_metadata_button)   # the kept draft is genuinely usable afterwards

                self.assertEqual(self.domain_metadata()[field], typed)
                self.assertEqual(self.persisted_metadata(self.lora_a.lora_id), self.domain_metadata())
                self.assertFalse(self.draft_is_pending())

    def test_each_metadata_field_draft_survives_a_failed_rename_and_can_be_saved_afterwards(self):
        self._single_field_draft_survives_then_saves("rename")

    def test_each_metadata_field_draft_survives_a_failed_import_and_can_be_saved_afterwards(self):
        self._single_field_draft_survives_then_saves("import")

    def test_each_metadata_field_draft_survives_a_failed_removal_and_can_be_saved_afterwards(self):
        self._single_field_draft_survives_then_saves("remove")

    def _selection_survives(self, operation):
        self.arrange(draft=False)
        self.reset_counters()
        before = self.state_before()

        self.fail_operation(operation)

        self.assert_rolled_back(before)
        self.assertEqual(self.selected_files(), ["fileA.safetensors", "fileC.safetensors"])
        self.assertTrue(self.page.remove_files_button.isEnabled())
        self.assertEqual(self.listed_files(), EXTERNAL_FILES)

    def test_file_selection_survives_a_failed_rename(self):
        self._selection_survives("rename")

    def test_file_selection_survives_a_failed_file_import(self):
        self._selection_survives("import")

    def test_file_selection_survives_a_failed_file_removal(self):
        self._selection_survives("remove")

    def test_a_failed_removal_can_be_retried_without_selecting_the_files_again(self):
        self.arrange(draft=False)
        self.fail_operation("remove")
        self.reset_counters()

        self.click_button(self.page.remove_files_button)

        self.assertEqual(self.lora_a.files, ["fileB.safetensors"])
        self.assertEqual(self.listed_files(), ["fileB.safetensors"])
        self.assertEqual((self.persist_calls, len(self.critical_calls)), (1, 0))

    def _name_draft_survives_a_failed_operation(self, operation):
        """A name draft is kept when ANOTHER operation fails. The name field is left holding the focus and the operation is
        called directly, so the focus order is not involved: with a real click on the button the offscreen platform moves
        the focus first and the name is validated before the operation (observed there, not asserted elsewhere)."""
        self.select_files(0, 2)
        self.type_into(self.page.name_edit, "PendingName")
        self.reset_counters()
        before = self.state_before()

        self.fail_persist = True
        try:
            if operation == "import":
                with patch("src.ui.pages.lora_page.QFileDialog.getOpenFileNames", return_value=(["fileD.safetensors"], "")):
                    self.page.import_files()
            else:
                self.page.remove_selected_files()
        finally:
            self.fail_persist = False

        self.assert_rolled_back(before)
        self.assertEqual(self.update_name_calls, 0)
        self.assertEqual(self.page.name_edit.text(), "PendingName")
        self.assertEqual(self.persisted_name(self.lora_a.lora_id), "LoraAlpha")

    def test_name_draft_survives_a_failed_file_import(self):
        self._name_draft_survives_a_failed_operation("import")

    def test_name_draft_survives_a_failed_file_removal(self):
        self._name_draft_survives_a_failed_operation("remove")

    def _click_on_another_entry_after_a_failed_rename(self, answer):
        """A real click on the other entry: the focus change validates the name first (it fails), then the page's own guard
        must still be consulted for the metadata draft before the selection changes."""
        self.arrange(draft=True)
        self.type_into(self.page.name_edit, "RejectedName")
        self.guard_answer = answer
        self.reset_counters()
        self.guard_dialogs.clear()
        before = self.state_before()

        self.fail_persist = True
        try:
            self.click_lora(self.lora_b.lora_id)
        finally:
            self.fail_persist = False

        self.assert_rolled_back(before)
        self.assertEqual(len(self.guard_dialogs), 1)
        self.assertIn("non enregistrées", self.guard_dialogs[0])
        self.assertEqual(self.domain_metadata(), EMPTY_METADATA)   # the draft was never written
        self.assertEqual(self.persisted_name(self.lora_a.lora_id), "LoraAlpha")

    def test_clicking_another_entry_after_a_failed_rename_asks_the_guard_and_cancel_keeps_the_draft(self):
        self._click_on_another_entry_after_a_failed_rename(QMessageBox.Cancel)

        self.assertEqual(self.lora_manager.active_lora_id, self.lora_a.lora_id)
        self.assertEqual(self.metadata_texts(), DRAFT_VALUES)
        self.assertEqual(self.page.name_edit.text(), "LoraAlpha")
        self.assertTrue(self.draft_is_pending())

    def test_clicking_another_entry_after_a_failed_rename_asks_the_guard_and_discard_switches_cleanly(self):
        self._click_on_another_entry_after_a_failed_rename(QMessageBox.Discard)

        self.assertEqual(self.lora_manager.active_lora_id, self.lora_b.lora_id)
        self.assertEqual(self.metadata_texts(), self.domain_metadata(self.lora_b))
        self.assertEqual(self.page.name_edit.text(), "LoraBeta")
        self.assertFalse(self.draft_is_pending())


class LoRAPageMetadataDraftInvariantTest(_LoRAMetadataDraftCase):
    """Behaviours already true before Mission 172, which must stay true (observable behaviour only)."""

    def _no_draft_is_consistent_with_the_domain(self, operation):
        self.arrange(draft=False)
        self.reset_counters()
        before = self.state_before()

        self.fail_operation(operation)

        self.assert_rolled_back(before)
        self.assertEqual(self.metadata_texts(), EMPTY_METADATA)
        self.assertFalse(self.draft_is_pending())
        self.assertEqual(self.listed_files(), EXTERNAL_FILES)

    def test_after_a_failed_rename_without_a_draft_the_fields_are_the_domain_values(self):
        self._no_draft_is_consistent_with_the_domain("rename")

    def test_after_a_failed_import_without_a_draft_the_fields_are_the_domain_values(self):
        self._no_draft_is_consistent_with_the_domain("import")

    def test_after_a_failed_removal_without_a_draft_the_fields_are_the_domain_values(self):
        self._no_draft_is_consistent_with_the_domain("remove")

    def _domain_change_during_the_dialog_is_followed_without_a_draft(self, operation):
        self.arrange(draft=False)
        self.reset_counters()
        self.critical_hook = lambda: setattr(self.lora_a, "engine", "DomainChangedDuringDialog")   # no event published

        self.fail_operation(operation)

        self.assertEqual(self.metadata_texts(), {**EMPTY_METADATA, "engine": "DomainChangedDuringDialog"})
        self.assertFalse(self.draft_is_pending())

    def test_a_domain_change_during_a_failed_rename_dialog_is_followed_when_there_is_no_draft(self):
        self._domain_change_during_the_dialog_is_followed_without_a_draft("rename")

    def test_a_domain_change_during_a_failed_import_dialog_is_followed_when_there_is_no_draft(self):
        self._domain_change_during_the_dialog_is_followed_without_a_draft("import")

    def test_a_domain_change_during_a_failed_removal_dialog_is_followed_when_there_is_no_draft(self):
        self._domain_change_during_the_dialog_is_followed_without_a_draft("remove")

    def _context_change_during_the_dialog(self, operation, change):
        second_character = self.character_manager.create("Second") if change == "select_other_character" else None
        self.arrange(draft=True)
        self.reset_counters()
        fired = []

        def change_context_while_the_dialog_is_open():
            if fired:
                return
            fired.append(True)
            if change == "select_other_lora":
                self.lora_manager.select(self.lora_b.lora_id)
            elif change == "delete_lora":
                self.fail_persist = False    # the deletion itself must be able to persist
                try:
                    self.lora_manager.delete(self.lora_a.lora_id)
                finally:
                    self.fail_persist = True
            elif change == "select_other_character":
                self.character_manager.select(second_character.character_id)
            elif change == "close_workspace":
                self.workspace_manager.close()

        self.critical_hook = change_context_while_the_dialog_is_open
        self.fail_operation(operation)

        self.assertEqual(fired, [True])
        self.assertEqual(len(self.critical_calls), 1)
        active = self.lora_manager.active_lora
        self.assertEqual(self.metadata_texts(), EMPTY_METADATA if active is None else self.domain_metadata(active))
        for value in DRAFT_VALUES.values():
            self.assertNotIn(value, self.metadata_texts().values())   # the old draft is never resurrected
        self.assertFalse(self.draft_is_pending())
        self.assertEqual(self.page.name_edit.text(), "" if active is None else active.name)

    def test_selecting_another_lora_during_a_failed_rename_dialog_never_resurrects_the_draft(self):
        self._context_change_during_the_dialog("rename", "select_other_lora")

    def test_selecting_another_lora_during_a_failed_import_dialog_never_resurrects_the_draft(self):
        self._context_change_during_the_dialog("import", "select_other_lora")

    def test_selecting_another_lora_during_a_failed_removal_dialog_never_resurrects_the_draft(self):
        self._context_change_during_the_dialog("remove", "select_other_lora")

    def test_deleting_the_lora_during_a_failed_rename_dialog_never_resurrects_the_draft(self):
        self._context_change_during_the_dialog("rename", "delete_lora")

    def test_deleting_the_lora_during_a_failed_import_dialog_never_resurrects_the_draft(self):
        self._context_change_during_the_dialog("import", "delete_lora")

    def test_deleting_the_lora_during_a_failed_removal_dialog_never_resurrects_the_draft(self):
        self._context_change_during_the_dialog("remove", "delete_lora")

    def test_selecting_another_character_during_a_failed_rename_dialog_never_resurrects_the_draft(self):
        self._context_change_during_the_dialog("rename", "select_other_character")

    def test_selecting_another_character_during_a_failed_import_dialog_never_resurrects_the_draft(self):
        self._context_change_during_the_dialog("import", "select_other_character")

    def test_selecting_another_character_during_a_failed_removal_dialog_never_resurrects_the_draft(self):
        self._context_change_during_the_dialog("remove", "select_other_character")

    def test_closing_the_workspace_during_a_failed_rename_dialog_never_resurrects_the_draft(self):
        self._context_change_during_the_dialog("rename", "close_workspace")

    def test_closing_the_workspace_during_a_failed_import_dialog_never_resurrects_the_draft(self):
        self._context_change_during_the_dialog("import", "close_workspace")

    def test_closing_the_workspace_during_a_failed_removal_dialog_never_resurrects_the_draft(self):
        self._context_change_during_the_dialog("remove", "close_workspace")

    def test_a_successful_removal_keeps_the_metadata_draft_and_drops_only_the_removed_files(self):
        self.arrange(draft=True)
        self.reset_counters()

        self.click_button(self.page.remove_files_button)

        self.assertEqual((self.persist_calls, len(self.critical_calls)), (1, 0))
        self.assertEqual(self.lora_a.files, ["fileB.safetensors"])
        self.assertEqual(self.listed_files(), ["fileB.safetensors"])
        self.assertEqual(self.selected_files(), [])
        self.assertEqual(self.metadata_texts(), DRAFT_VALUES)
        self.assertTrue(self.draft_is_pending())

    # --- out of scope, unchanged: the failure of the metadata save itself keeps its forced resync ------------------

    def test_a_failed_metadata_save_still_gives_way_to_the_restored_values(self):
        self.arrange(draft=True)
        self.reset_counters()
        self.fail_persist = True

        self.click_button(self.page.save_metadata_button)
        self.fail_persist = False

        self.assertEqual((self.persist_calls, len(self.critical_calls)), (1, 1))
        self.assertEqual(self.metadata_texts(), EMPTY_METADATA)
        self.assertEqual(self.domain_metadata(), EMPTY_METADATA)
        self.assertFalse(self.draft_is_pending())

    def test_a_failed_save_in_the_context_change_guard_still_resyncs_and_refuses_the_change(self):
        self.arrange(draft=True)
        self.reset_counters()
        self.guard_answer = QMessageBox.Save
        self.fail_persist = True

        proceed = self.page.confirm_context_change()
        self.fail_persist = False

        self.assertFalse(proceed)
        self.assertEqual((self.persist_calls, len(self.critical_calls)), (1, 1))
        self.assertEqual(self.metadata_texts(), EMPTY_METADATA)
        self.assertFalse(self.draft_is_pending())


class LoRAPageFailureResyncContractTest(_LoRAMetadataDraftCase):
    """The Mission 172 contract itself: which refresh each failure branch calls, and the private state it leaves. Reads the
    private state and spies on the page's helpers — kept apart from the behavioural families above."""

    def setUp(self):
        super().setUp()
        self.direct_refreshes = []     # direct calls of update_loras() by the page itself (the EventBus keeps the original)
        self.forced_refreshes = []
        real_update_loras = self.page.update_loras
        real_force_refresh = self.page._force_refresh_lora

        def update_spy(*args, **kwargs):
            self.direct_refreshes.append((self.page._renaming_in_progress, len(self.critical_calls)))
            return real_update_loras(*args, **kwargs)

        def force_spy():
            self.forced_refreshes.append((self.page._renaming_in_progress, len(self.critical_calls)))
            return real_force_refresh()

        self.page.update_loras = update_spy
        self.page._force_refresh_lora = force_spy

    def test_each_failure_branch_uses_the_general_refresh_once_after_the_dialog_and_never_the_forced_one(self):
        expected_flag = {"rename": True, "import": False, "remove": False}   # the rename guard stays held until the end
        for operation in FAILING_OPERATIONS:
            with self.subTest(operation=operation):
                self.direct_refreshes.clear()
                self.forced_refreshes.clear()
                self.select_files(0, 2)
                self.reset_counters()

                self.fail_operation(operation)

                self.assertEqual(self.direct_refreshes, [(expected_flag[operation], 1)])   # once, after the one dialog
                self.assertEqual(self.forced_refreshes, [])

    def test_private_dirty_state_and_loaded_identity_follow_the_draft_after_each_failure(self):
        for operation in FAILING_OPERATIONS:
            for draft in (True, False):
                with self.subTest(operation=operation, draft=draft):
                    self.page.update_loras()                         # known clean starting point (no pending draft)
                    if draft:
                        self.type_metadata({"engine": f"draft-{operation}"})
                    self.select_files(0, 2)

                    self.fail_operation(operation)

                    self.assertEqual(self.page._metadata_dirty, draft)
                    self.assertEqual(self.page._loaded_lora_id, self.lora_a.lora_id)
                    self.assertEqual(self.page._name_editor_owner_id, self.lora_a.lora_id)
                    self.assertEqual(self.page._name_editor_loaded_value, "LoraAlpha")
                    self.assertFalse(self.page._renaming_in_progress)
                    self.page._force_refresh_lora()                  # back to a clean state for the next case

    def test_the_forced_refresh_stays_on_the_paths_outside_this_mission(self):
        self.arrange(draft=True)
        self.reset_counters()
        self.fail_persist = True
        self.click_button(self.page.save_metadata_button)
        self.fail_persist = False
        self.assertEqual(self.forced_refreshes, [(False, 1)])          # failed metadata save

        self.forced_refreshes.clear()
        self.type_metadata()
        self.guard_answer = QMessageBox.Save
        self.reset_counters()
        self.fail_persist = True
        self.page.confirm_context_change()
        self.fail_persist = False
        self.assertEqual(self.forced_refreshes, [(False, 1)])          # failed Save of the context-change guard

        self.forced_refreshes.clear()
        self.type_metadata()
        self.reset_counters()
        self.fail_persist = True
        self.page.add_to_central_library()
        self.fail_persist = False
        self.assertEqual(self.forced_refreshes, [(False, 1)])          # failed Save before the central import

        self.forced_refreshes.clear()
        self.workspace_manager.close()
        self.assertEqual(len(self.forced_refreshes), 1)                # context reset

    def test_a_failure_during_the_rename_resync_still_releases_the_reentrancy_flag(self):
        self.type_into(self.page.name_edit, "Draft Before Failure")

        def exploding_update_loras(*args, **kwargs):
            raise RuntimeError("resync failure")

        self.page.update_loras = exploding_update_loras
        self.fail_persist = True
        with self.assertRaises(RuntimeError):
            self.page.rename_lora()
        self.fail_persist = False

        self.assertFalse(self.page._renaming_in_progress)
        self.assertEqual(self.page.name_edit.text(), "LoraAlpha")    # the final reconciliation still ran
        self.assertEqual(self.persisted_name(self.lora_a.lora_id), "LoraAlpha")

# ---------------------------------------------------------------------------
# Mission 173 — LoRAPage, "Exposer à ComfyUI": an OSError met by an inspection or by the
# creation of the exposure subfolder must reach the user as the page's existing error
# dialog. Real LoRAPage, real managers, a real mouse click, a dialog recorder (no dialog
# can open), and a temporary sys.excepthook (restored by the patch) that captures any
# exception a slot lets escape. Errors are simulated on the exact primitive (os.stat on
# the expose root, os.mkdir on the subfolder) with real delegation elsewhere; no ACL is
# ever changed by a test.
# ---------------------------------------------------------------------------

_EXPOSURE_REAL_OS_STAT = os.stat
_EXPOSURE_REAL_OS_MKDIR = os.mkdir


def _exposure_is_path_like(value):
    return isinstance(value, (str, bytes, os.PathLike))


def _exposure_failing_stat(target, nth, error, raised):
    key = os.path.normcase(str(target))
    calls = []

    def wrapper(path, *args, **kwargs):
        if _exposure_is_path_like(path) and os.path.normcase(os.fspath(path)) == key:
            calls.append(path)
            if len(calls) == nth:
                raised.append(error)
                raise error
        return _EXPOSURE_REAL_OS_STAT(path, *args, **kwargs)

    return wrapper


def _exposure_failing_mkdir(target, error, raised):
    key = os.path.normcase(str(target))

    def wrapper(path, *args, **kwargs):
        if _exposure_is_path_like(path) and os.path.normcase(os.fspath(path)) == key:
            raised.append(error)
            raise error
        return _EXPOSURE_REAL_OS_MKDIR(path, *args, **kwargs)

    return wrapper


class _LoRAPageExposureFailureCase(unittest.TestCase):
    """LoRAPageComfyUIExposureTest's wiring, shown and driven by a real click on the expose button."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"
        self.library_root = Path(self.tmp_dir) / "CentralLibrary"
        self.expose_root = Path(self.tmp_dir) / "ComfyUISharedLoras"
        self.expose_root.mkdir()
        self.subfolder = self.expose_root / "AIStudioToolkit"

        self.critical_calls = []
        self.information_calls = []
        self.unexpected_dialogs = []
        self.injections = []
        for name, handler in (
            ("critical", self._on_critical),
            ("information", self._on_information),
            ("warning", self._on_unexpected_dialog),
            ("question", self._on_unexpected_dialog),
        ):
            dialog_patch = patch.object(QMessageBox, name, side_effect=handler)
            dialog_patch.start()
            self.addCleanup(dialog_patch.stop)

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.lora_manager = LoRAManager(self.character_manager, self.workspace_manager, event_bus=self.event_bus)
        self.lora_library_manager = LoRALibraryManager(
            storage_directory=Path(self.tmp_dir) / "lora_library", event_bus=self.event_bus
        )
        self.application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings",
            lora_library_manager=self.lora_library_manager,
        )
        self.application_settings_manager.update(
            lora_library_path=str(self.library_root),
            comfyui_lora_expose_path=str(self.expose_root),
        )

        self.page = LoRAPage(
            self.lora_manager, self.workspace_manager, self.lora_library_manager, self.application_settings_manager
        )
        # Registered after the dialog patches and the temp folder: runs before them.
        self.addCleanup(self._release_page)
        for event_name in (LORA_LIBRARY_IMPORTED, LORA_LIBRARY_DELETED, LORA_LIBRARY_UPDATED):
            self.event_bus.subscribe(event_name, self.page.update_central_library)

        self.workspace_manager.create(self.folder)
        self.character_manager.create("Aria")

        source_file = Path(self.tmp_dir) / "StyleA_weights.safetensors"
        source_file.write_bytes(b"weights")
        self.entry = self.lora_library_manager.import_lora(
            name="StyleA", file_paths=[str(source_file)], library_root=self.library_root,
        )
        self.page.update_central_library()
        self.page.library_list.setCurrentRow(0)
        self.page.show()
        self._reveal(self.page.expose_to_comfyui_button)
        QApplication.processEvents()
        self.assertTrue(self.page.expose_to_comfyui_button.isVisible())
        self.assertTrue(self.page.expose_to_comfyui_button.isEnabled())

    def tearDown(self):
        self.assertEqual(self.unexpected_dialogs, [], "an unexpected dialog was opened")

    # --- fixture plumbing -------------------------------------------------------------------------------------

    def _on_critical(self, *args, **kwargs):
        self.critical_calls.append(args)

    def _on_information(self, *args, **kwargs):
        self.information_calls.append(args)

    def _on_unexpected_dialog(self, *args, **kwargs):
        self.unexpected_dialogs.append(args)
        return QMessageBox.Cancel

    def _release_page(self):
        self.page.hide()
        self.page.close()
        self.page.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QApplication.processEvents()

    @staticmethod
    def _reveal(widget):
        node = widget
        while node.parent() is not None:
            parent = node.parent()
            if isinstance(parent, QStackedWidget):
                parent.setCurrentWidget(node)
            node = parent

    # --- faults and the real click ----------------------------------------------------------------------------

    def injected_error(self):
        return PermissionError(13, "Access is denied (injected)")

    def mkdir_fault(self):
        return patch("os.mkdir", _exposure_failing_mkdir(self.subfolder, self.injected_error(), self.injections))

    def root_inspection_fault(self):
        return patch(
            "os.stat", _exposure_failing_stat(self.expose_root, 1, self.injected_error(), self.injections)
        )

    def occupy_subfolder_name(self):
        self.subfolder.write_bytes(b"occupant of the exposure subfolder name")
        return contextlib.nullcontext()

    def click_expose(self, fault):
        """One real click on the expose button; returns the exceptions any slot let escape."""
        captured = []
        with patch("sys.excepthook", lambda exc_type, exc, tb: captured.append(exc)):
            with fault:
                QTest.mouseClick(self.page.expose_to_comfyui_button, Qt.LeftButton)
                QApplication.processEvents()
        return captured

    def page_state(self):
        return {
            "selected_rows": sorted(self.page.library_list.row(item) for item in self.page.library_list.selectedItems()),
            "button_enabled": self.page.expose_to_comfyui_button.isEnabled(),
            "subfolder_exists": self.subfolder.exists(),
            "occupant": self.subfolder.read_bytes() if self.subfolder.is_file() else None,
            "aliases": sorted(p.name for p in self.subfolder.iterdir()) if self.subfolder.is_dir() else None,
        }


class LoRAPageExposureFailureRegressionTest(_LoRAPageExposureFailureCase):
    """Behavioural: before the change the slot raised and the user saw nothing; now one error dialog is shown."""

    def assert_single_error_dialog(self, captured, expected_text):
        self.assertEqual(captured, [])                         # no exception escaped from the slot
        self.assertEqual(len(self.critical_calls), 1)
        self.assertEqual(self.information_calls, [])
        _, title, text = self.critical_calls[0][:3]
        self.assertEqual(title, "Erreur")
        self.assertTrue(text.startswith("Impossible d'exposer cette entrée à ComfyUI : "))
        self.assertIn(expected_text, text)

    def test_a_failed_subfolder_creation_shows_one_error_dialog_and_no_slot_exception(self):
        captured = self.click_expose(self.mkdir_fault())
        self.assertEqual(len(self.injections), 1)
        self.assert_single_error_dialog(captured, "Could not create the ComfyUI exposure folder")

    def test_a_failed_inspection_of_the_expose_root_shows_one_error_dialog_and_no_slot_exception(self):
        captured = self.click_expose(self.root_inspection_fault())
        self.assertEqual(len(self.injections), 1)
        self.assert_single_error_dialog(captured, "Could not inspect the configured ComfyUI exposure path")

    def test_a_subfolder_creation_conflict_shows_one_error_dialog_and_no_slot_exception(self):
        captured = self.click_expose(self.occupy_subfolder_name())
        self.assert_single_error_dialog(captured, "the path already exists")


class LoRAPageExposureFailureInvariantTest(_LoRAPageExposureFailureCase):
    """Already true before the change: the page and the filesystem are left as they were; the success path is unchanged."""

    def test_a_failed_exposure_leaves_the_selection_the_button_and_the_filesystem_as_they_were(self):
        for situation in ("mkdir", "root_inspection", "conflict"):
            with self.subTest(situation=situation):
                self.critical_calls.clear()
                fault = {
                    "mkdir": self.mkdir_fault,
                    "root_inspection": self.root_inspection_fault,
                    "conflict": self.occupy_subfolder_name,       # builds the occupant before the state is read
                }[situation]()
                before = self.page_state()
                self.click_expose(fault)
                self.assertEqual(self.page_state(), before)
                if situation == "conflict":
                    self.subfolder.unlink()

    def test_a_real_click_still_exposes_the_entry_and_confirms_when_nothing_fails(self):
        captured = self.click_expose(contextlib.nullcontext())

        self.assertEqual(captured, [])
        self.assertEqual(self.critical_calls, [])
        self.assertEqual(len(self.information_calls), 1)
        self.assertIn("est désormais exposée à ComfyUI", self.information_calls[0][2])
        alias_path = self.subfolder / f"StyleA__{self.entry.lora_id}.safetensors"
        self.assertTrue(alias_path.is_file())
        self.assertTrue(os.path.samefile(alias_path, self.entry.files[0]))



if __name__ == "__main__":
    unittest.main()
