"""
Integration coverage for the Model lifecycle, exercising ModelManager,
Workspace.models, EventBus and the real DashboardPage/CharactersPage/
ImagesPage/ModelsPage widgets together — the same wiring MainWindow
uses. Also covers the Model domain object's own to_dict()/from_dict()
round-trip and default-value behavior directly, since Model is a new
entity introduced this mission.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.core.event_bus import EventBus
from src.domain.model import Model
from src.domain.workspace import Workspace
from src.infrastructure.storage.workspace_storage import WorkspaceStorage, WorkspaceStorageError
from src.managers.workspace_manager import (
    WorkspaceManager,
    WorkspaceManagerError,
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
from src.managers.model_manager import (
    ModelManager,
    MODEL_CREATED,
    MODEL_SELECTED,
    MODEL_DELETED,
)
from src.ui.pages.dashboard_page import DashboardPage
from src.ui.pages.characters_page import CharactersPage
from src.ui.pages.images_page import ImagesPage
from src.ui.pages.models_page import ModelsPage

WORKSPACE_EVENTS = (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_SAVED, WORKSPACE_CLOSED)
CHARACTER_EVENTS = (CHARACTER_CREATED, CHARACTER_SELECTED, CHARACTER_DELETED)
MODEL_EVENTS = (MODEL_CREATED, MODEL_SELECTED, MODEL_DELETED)

_app = QApplication.instance() or QApplication([])


class ModelRoundTripTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "ModelProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        model_manager = ModelManager(workspace_manager, event_bus=event_bus)

        dashboard = DashboardPage()
        characters_page = CharactersPage(character_manager, workspace_manager)
        images = ImagesPage(workspace_manager)
        models_page = ModelsPage(model_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, dashboard.update_project)
            event_bus.subscribe(event_name, images.update_images)
            event_bus.subscribe(event_name, characters_page.update_characters)
            event_bus.subscribe(event_name, models_page.update_models)

        # Deliberately NOT subscribing models_page to CHARACTER_* events —
        # Model is Workspace-owned, mirrors main_window.py's real wiring.
        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, characters_page.update_characters)

        for event_name in MODEL_EVENTS:
            event_bus.subscribe(event_name, models_page.update_models)

        return (
            event_bus, workspace_manager, character_manager, model_manager,
            dashboard, characters_page, images, models_page,
        )

    def test_model_domain_object_roundtrip_and_defaults(self):

        # Default values.
        model = Model()
        self.assertEqual(model.model_id, "")
        self.assertEqual(model.name, "")
        self.assertEqual(model.file_path, "")
        self.assertEqual(model.to_dict(), {"model_id": "", "name": "", "file_path": ""})

        # Round-trip without loss of information.
        original = Model(model_id="abc", name="SDXL Base", file_path="C:/models/sdxl.safetensors")
        restored = Model.from_dict(original.to_dict())
        self.assertEqual(original, restored)

        # Missing key -> default, consistent with every other Domain object.
        self.assertEqual(Model.from_dict({}), Model())
        self.assertEqual(Model.from_dict({"name": "Only Name"}).file_path, "")

        # Workspace.models: mixed list[dict|str|None] -> only dict entries
        # survive, same defensive-compatibility principle as
        # Character.datasets/loras/prompts.
        mixed = Workspace.from_dict({
            "models": [
                {"name": "M1"},
                "ancien format",
                None,
                {"name": "M2"},
            ]
        })
        self.assertEqual(len(mixed.models), 2)
        self.assertTrue(all(isinstance(m, Model) for m in mixed.models))
        self.assertEqual([m.name for m in mixed.models], ["M1", "M2"])

    def test_full_create_select_edit_save_close_reopen_cycle(self):

        (event_bus, workspace_manager, character_manager, model_manager,
         dashboard, characters_page, images, models_page) = self._wire()

        workspace_manager.create(self.folder)

        model = model_manager.create("SDXL Base")
        model_manager.select(model.model_id)
        changed = model_manager.update_file_path("C:/models/sdxl_base.safetensors")
        self.assertTrue(changed)

        self.assertEqual(
            models_page.file_path_edit.text(),
            "C:/models/sdxl_base.safetensors",
        )

        workspace_manager.close()

        self.assertIsNone(model_manager.active_model_id)
        self.assertEqual(models_page.model_list.count(), 0)

        # Reopen with a second _wire() call — fresh instances, simulating
        # a real application restart rather than reusing in-memory state.
        (event_bus_2, workspace_manager_2, character_manager_2, model_manager_2,
         dashboard_2, characters_page_2, images_2, models_page_2) = self._wire()

        workspace_manager_2.open(self.folder)

        # Runtime-only per Mission 002-006 decisions: active_model_id
        # does not survive a restart. No character selection is involved
        # here at all — Model is Workspace-owned.
        self.assertIsNone(model_manager_2.active_model_id)

        self.assertEqual(len(model_manager_2.models), 1)
        restored_model = model_manager_2.models[0]
        self.assertEqual(restored_model.name, "SDXL Base")
        self.assertEqual(restored_model.file_path, "C:/models/sdxl_base.safetensors")

    def test_update_file_path_is_idempotent(self):

        event_bus, workspace_manager, character_manager, model_manager = self._wire()[:4]
        workspace_manager.create(self.folder)
        model = model_manager.create("SDXL Base")
        model_manager.select(model.model_id)

        events_seen = []
        for event_name in MODEL_EVENTS:
            event_bus.subscribe(event_name, lambda payload, name=event_name: events_seen.append(name))

        # No active model at all: False, no save().
        model_manager.active_model_id = None
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertFalse(model_manager.update_file_path("irrelevant"))
            save_spy.assert_not_called()

        model_manager.select(model.model_id)
        events_seen.clear()  # select() above legitimately publishes model.selected

        # First real change: True, save() called, no model.* event.
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertTrue(model_manager.update_file_path("C:/models/a.safetensors"))
            save_spy.assert_called_once()
        self.assertEqual(model_manager.active_model.file_path, "C:/models/a.safetensors")
        self.assertEqual(events_seen, [])

        # Identical value again: False, save() NOT called, no model.* event.
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertFalse(model_manager.update_file_path("C:/models/a.safetensors"))
            save_spy.assert_not_called()
        self.assertEqual(events_seen, [])

        # Empty string is a legitimate value ("no file yet"): a real
        # change from a non-empty value, so True + save().
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertTrue(model_manager.update_file_path(""))
            save_spy.assert_called_once()
        self.assertEqual(model_manager.active_model.file_path, "")

    def test_update_name_is_idempotent(self):

        event_bus, workspace_manager, character_manager, model_manager = self._wire()[:4]
        workspace_manager.create(self.folder)
        model = model_manager.create("SDXL Base")
        model_manager.select(model.model_id)
        model_manager.update_file_path("C:/models/sdxl.safetensors")

        events_seen = []
        for event_name in MODEL_EVENTS:
            event_bus.subscribe(event_name, lambda payload, name=event_name: events_seen.append(name))

        # No active model at all: False, no save().
        model_manager.active_model_id = None
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertFalse(model_manager.update_name("irrelevant"))
            save_spy.assert_not_called()

        model_manager.select(model.model_id)
        events_seen.clear()

        # First real change: True, save() called, no model.* event, id and
        # file_path both untouched.
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertTrue(model_manager.update_name("SDXL Base Renamed"))
            save_spy.assert_called_once()
        self.assertEqual(model_manager.active_model.name, "SDXL Base Renamed")
        self.assertEqual(model_manager.active_model.model_id, model.model_id)
        self.assertEqual(model_manager.active_model.file_path, "C:/models/sdxl.safetensors")
        self.assertEqual(events_seen, [])

        # Identical value again: False, save() NOT called.
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertFalse(model_manager.update_name("SDXL Base Renamed"))
            save_spy.assert_not_called()

        # Empty string is a legitimate value, not rejected/stripped by the
        # Manager — same convention as CharacterManager.update(name=...).
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertTrue(model_manager.update_name(""))
            save_spy.assert_called_once()
        self.assertEqual(model_manager.active_model.name, "")

    def test_rename_persists_after_close_reopen(self):

        _, workspace_manager, character_manager, model_manager = self._wire()[:4]
        workspace_manager.create(self.folder)
        model = model_manager.create("SDXL Base")
        original_id = model.model_id
        model_manager.select(model.model_id)
        model_manager.update_file_path("C:/models/sdxl.safetensors")
        model_manager.update_name("SDXL Base Renamed")

        _, workspace_manager_2, character_manager_2, model_manager_2 = self._wire()[:4]
        workspace_manager_2.open(self.folder)

        self.assertEqual(len(model_manager_2.models), 1)
        restored = model_manager_2.models[0]
        self.assertEqual(restored.model_id, original_id)
        self.assertEqual(restored.name, "SDXL Base Renamed")
        self.assertEqual(restored.file_path, "C:/models/sdxl.safetensors")

    def test_delete_active_model_resets_selection_and_persists(self):

        _, workspace_manager, character_manager, model_manager = self._wire()[:4]
        workspace_manager.create(self.folder)

        keep = model_manager.create("Keep")
        drop = model_manager.create("Drop")
        model_manager.select(drop.model_id)

        result = model_manager.delete(drop.model_id)
        self.assertTrue(result)
        self.assertIsNone(model_manager.active_model_id)
        self.assertIsNone(model_manager.active_model)
        self.assertEqual([m.name for m in model_manager.models], ["Keep"])

        # Persists: reopening shows only the surviving model.
        _, workspace_manager_2, character_manager_2, model_manager_2 = self._wire()[:4]
        workspace_manager_2.open(self.folder)
        self.assertEqual([m.name for m in model_manager_2.models], ["Keep"])

    def test_model_manager_context_reset_on_workspace_change_only(self):

        _, workspace_manager, character_manager, model_manager = self._wire()[:4]
        workspace_manager.create(self.folder)

        model = model_manager.create("SDXL Base")
        model_manager.select(model.model_id)
        self.assertEqual(model_manager.active_model_id, model.model_id)

        # A character switch must NEVER reset active_model_id — Model has
        # no relationship to the active character at all, unlike Dataset/
        # LoRA/Prompt. This is the inverted invariant specific to Model.
        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)
        self.assertEqual(
            model_manager.active_model_id, model.model_id,
            "a character switch must never affect active_model_id (Model is Workspace-owned)",
        )

        kai = character_manager.create("Kai")
        character_manager.select(kai.character_id)
        character_manager.delete(kai.character_id)
        self.assertEqual(model_manager.active_model_id, model.model_id)

        # A workspace close still resets it.
        workspace_manager.close()
        self.assertIsNone(model_manager.active_model_id)

    def test_models_page_rebuilds_on_relevant_events(self):

        (_, workspace_manager, character_manager, model_manager,
         _dashboard, _characters_page, _images, models_page) = self._wire()

        workspace_manager.create(self.folder)
        self.assertEqual(models_page.model_list.count(), 0)

        model = model_manager.create("SDXL Base")
        self.assertEqual(models_page.model_list.count(), 1)

        model_manager.select(model.model_id)
        model_manager.update_file_path("C:/models/a.safetensors")
        # update_file_path() only publishes workspace.saved — this is what
        # ModelsPage's subscription to it must catch.
        self.assertEqual(models_page.file_path_edit.text(), "C:/models/a.safetensors")

        # Character activity must never rebuild ModelsPage's data away.
        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)
        self.assertEqual(models_page.model_list.count(), 1)
        self.assertEqual(models_page.file_path_edit.text(), "C:/models/a.safetensors")

        workspace_manager.close()
        self.assertEqual(models_page.model_list.count(), 0)
        self.assertEqual(models_page.file_path_edit.text(), "")

    def test_no_duplicate_subscriptions_between_wire_calls(self):

        wired_1 = self._wire()
        wired_2 = self._wire()

        for obj_1, obj_2 in zip(wired_1, wired_2):
            self.assertIsNot(obj_1, obj_2)

        event_bus_1, event_bus_2 = wired_1[0], wired_2[0]

        # 4 subscribers registered directly by _wire() (dashboard, images,
        # characters_page, models_page) + CharacterManager's two own
        # internal subscriptions (active_character_id reset, and
        # Mission 026's principal-Character auto-creation) + ModelManager's
        # own internal reset subscription = 7, on EACH bus independently.
        self.assertEqual(len(event_bus_1._subscribers[WORKSPACE_CREATED]), 7)
        self.assertEqual(len(event_bus_2._subscribers[WORKSPACE_CREATED]), 7)
        self.assertTrue(
            set(event_bus_1._subscribers[WORKSPACE_CREATED]).isdisjoint(
                event_bus_2._subscribers[WORKSPACE_CREATED]
            )
        )

    def test_dashboard_and_images_unaffected_by_model_events(self):

        (_, workspace_manager, character_manager, model_manager,
         dashboard, _characters_page, images, _models_page) = self._wire()

        workspace_manager.create(self.folder)

        before_dashboard = dashboard.projectCard.value.text()
        before_images_count = images.list_widget.count()

        model_manager.create("SDXL Base")

        self.assertEqual(dashboard.projectCard.value.text(), before_dashboard)
        self.assertEqual(images.list_widget.count(), before_images_count)


class ModelsPageSortTest(unittest.TestCase):
    """
    Mission 051: ModelsPage.model_list is now sorted by name, case-
    insensitive, always active — same pattern already established by
    Mission 048 for ImagesPage/DatasetsPage. Workspace.models (Domain)
    must never be reordered.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "ModelSortProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        model_manager = ModelManager(workspace_manager, event_bus=event_bus)
        models_page = ModelsPage(model_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, models_page.update_models)
        for event_name in MODEL_EVENTS:
            event_bus.subscribe(event_name, models_page.update_models)

        return event_bus, workspace_manager, model_manager, models_page

    def test_display_order_is_alphabetical_case_insensitive(self):

        _, workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)

        for name in ("Zebra", "mango", "Apple", "banana", "Cherry"):
            model_manager.create(name)

        displayed = [
            models_page.model_list.item(i).text()
            for i in range(models_page.model_list.count())
        ]
        self.assertEqual(displayed, ["Apple", "banana", "Cherry", "mango", "Zebra"])

    def test_domain_collection_keeps_insertion_order(self):

        _, workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)

        for name in ("Zebra", "mango", "Apple"):
            model_manager.create(name)

        self.assertEqual(
            [m.name for m in workspace_manager.current_workspace.models],
            ["Zebra", "mango", "Apple"],
        )

    def test_sort_is_stable_for_identical_names(self):

        _, workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)

        first = model_manager.create("Same")
        second = model_manager.create("Same")

        displayed_ids = [
            models_page.model_list.item(i).data(Qt.UserRole)
            for i in range(models_page.model_list.count())
        ]
        self.assertEqual(displayed_ids, [first.model_id, second.model_id])

    def test_selection_targets_correct_model_despite_display_reorder(self):

        _, workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)

        zebra = model_manager.create("Zebra")
        apple = model_manager.create("Apple")

        model_manager.select(apple.model_id)
        model_manager.update_file_path("C:/models/apple.safetensors")

        # "Apple" now displays at position 0, ahead of "Zebra" — confirm
        # the correct model's file_path is reflected, not positional.
        self.assertEqual(models_page.model_list.item(0).text(), "Apple")
        self.assertEqual(
            models_page.file_path_edit.text(), "C:/models/apple.safetensors"
        )

        model_manager.select(zebra.model_id)
        self.assertEqual(models_page.file_path_edit.text(), "")

    def test_refresh_after_second_creation_resorts_entire_list(self):

        _, workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)

        model_manager.create("Mango")
        model_manager.create("Zebra")
        model_manager.create("Apple")

        displayed = [
            models_page.model_list.item(i).text()
            for i in range(models_page.model_list.count())
        ]
        self.assertEqual(displayed, ["Apple", "Mango", "Zebra"])


class ModelsPageRenameTest(unittest.TestCase):
    """
    Mission 052: ModelsPage.name_edit allows renaming the active model
    in place (editingFinished -> ModelManager.update_name()). Renaming
    must never change model_id/file_path, and must interact correctly
    with Mission 051's alphabetical sort — selection stays on the same
    model by id despite any display reorder the rename triggers.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "ModelRenameProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        model_manager = ModelManager(workspace_manager, event_bus=event_bus)
        models_page = ModelsPage(model_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, models_page.update_models)
        for event_name in MODEL_EVENTS:
            event_bus.subscribe(event_name, models_page.update_models)

        return event_bus, workspace_manager, model_manager, models_page

    def test_rename_via_widget_updates_manager_display_and_preserves_file_path(self):

        _, workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)

        model = model_manager.create("SDXL Base")
        model_manager.select(model.model_id)
        model_manager.update_file_path("C:/models/sdxl.safetensors")

        models_page.name_edit.setText("SDXL Base Renamed")
        models_page.name_edit.editingFinished.emit()

        self.assertEqual(model_manager.active_model.name, "SDXL Base Renamed")
        self.assertEqual(model_manager.active_model.model_id, model.model_id)
        self.assertEqual(model_manager.active_model.file_path, "C:/models/sdxl.safetensors")
        self.assertEqual(models_page.model_list.item(0).text(), "SDXL Base Renamed")
        self.assertEqual(models_page.file_path_edit.text(), "C:/models/sdxl.safetensors")

    def test_rename_moving_entity_to_front_keeps_correct_selection(self):

        _, workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)

        mango = model_manager.create("Mango")
        zebra = model_manager.create("Zebra")
        model_manager.select(zebra.model_id)
        model_manager.update_file_path("C:/models/zebra.safetensors")

        models_page.name_edit.setText("Apple")
        models_page.name_edit.editingFinished.emit()

        displayed = [
            models_page.model_list.item(i).text()
            for i in range(models_page.model_list.count())
        ]
        self.assertEqual(displayed, ["Apple", "Mango"])
        self.assertEqual(models_page.model_list.item(0).data(Qt.UserRole), zebra.model_id)
        self.assertEqual(model_manager.active_model_id, zebra.model_id)
        self.assertEqual(models_page.file_path_edit.text(), "C:/models/zebra.safetensors")

    def test_rename_moving_entity_to_back_keeps_correct_selection(self):

        _, workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)

        apple = model_manager.create("Apple")
        mango = model_manager.create("Mango")
        model_manager.select(apple.model_id)
        model_manager.update_file_path("C:/models/apple.safetensors")

        models_page.name_edit.setText("Zzz")
        models_page.name_edit.editingFinished.emit()

        displayed = [
            models_page.model_list.item(i).text()
            for i in range(models_page.model_list.count())
        ]
        self.assertEqual(displayed, ["Mango", "Zzz"])
        self.assertEqual(models_page.model_list.item(1).data(Qt.UserRole), apple.model_id)
        self.assertEqual(model_manager.active_model_id, apple.model_id)
        self.assertEqual(models_page.file_path_edit.text(), "C:/models/apple.safetensors")

    def test_rename_with_no_active_model_is_a_no_op(self):

        _, workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)
        model_manager.create("SDXL Base")

        # Nothing selected: name_edit is empty, editingFinished must not
        # crash or create/rename anything.
        models_page.name_edit.setText("Whatever")
        models_page.name_edit.editingFinished.emit()

        self.assertEqual(
            [m.name for m in workspace_manager.current_workspace.models],
            ["SDXL Base"],
        )

    def test_rename_persists_after_close_reopen_via_ui(self):

        _, workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)

        model = model_manager.create("SDXL Base")
        model_manager.select(model.model_id)

        models_page.name_edit.setText("SDXL Base Renamed")
        models_page.name_edit.editingFinished.emit()

        workspace_manager.close()

        _, workspace_manager_2, model_manager_2, models_page_2 = self._wire()
        workspace_manager_2.open(self.folder)

        self.assertEqual(len(model_manager_2.models), 1)
        self.assertEqual(model_manager_2.models[0].model_id, model.model_id)
        self.assertEqual(model_manager_2.models[0].name, "SDXL Base Renamed")
        self.assertEqual(models_page_2.model_list.item(0).text(), "SDXL Base Renamed")

    def test_rename_save_failure_shows_error_and_restores_widget_to_previous_name(self):

        _, workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)

        model = model_manager.create("SDXL Base")
        model_manager.select(model.model_id)

        models_page.name_edit.setText("SDXL Base Renamed")
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.models_page.QMessageBox.critical") as critical_mock:
            models_page.name_edit.editingFinished.emit()

        self.assertTrue(critical_mock.called)
        self.assertEqual(model.name, "SDXL Base")
        self.assertEqual(models_page.name_edit.text(), "SDXL Base")
        self.assertEqual(models_page.model_list.item(0).text(), "SDXL Base")

    def test_retry_after_rename_save_failure_actually_renames(self):

        _, workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)

        model = model_manager.create("SDXL Base")
        model_manager.select(model.model_id)

        models_page.name_edit.setText("SDXL Base Renamed")
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.models_page.QMessageBox.critical"):
            models_page.name_edit.editingFinished.emit()

        models_page.name_edit.setText("SDXL Base Renamed")
        models_page.name_edit.editingFinished.emit()

        self.assertEqual(model.name, "SDXL Base Renamed")
        self.assertEqual(models_page.model_list.item(0).text(), "SDXL Base Renamed")


class ModelsPageFilePathPersistenceFailureTest(unittest.TestCase):
    """
    Mission 070: browse_file() -> update_file_path(). Unlike name_edit,
    file_path_edit is never written directly by this handler (only by
    update_models()'s own refresh on a successful save()) — so on a
    save() failure it was never showing the rejected value in the first
    place. Only the error needs surfacing here.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "ModelFilePathProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        model_manager = ModelManager(workspace_manager, event_bus=event_bus)
        models_page = ModelsPage(model_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, models_page.update_models)
        for event_name in MODEL_EVENTS:
            event_bus.subscribe(event_name, models_page.update_models)

        return event_bus, workspace_manager, model_manager, models_page

    def test_browse_file_save_failure_shows_error_and_never_shows_the_rejected_path(self):

        _, workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)

        model = model_manager.create("SDXL Base")
        model_manager.select(model.model_id)

        with patch(
            "src.ui.pages.models_page.QFileDialog.getOpenFileName",
            return_value=("C:/models/rejected.safetensors", ""),
        ), patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.models_page.QMessageBox.critical") as critical_mock:
            models_page.browse_file()

        self.assertTrue(critical_mock.called)
        self.assertEqual(model.file_path, "")
        self.assertEqual(models_page.file_path_edit.text(), "")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertEqual(on_disk["models"][0]["file_path"], "")

    def test_retry_after_browse_file_save_failure_actually_persists(self):

        _, workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)

        model = model_manager.create("SDXL Base")
        model_manager.select(model.model_id)

        with patch(
            "src.ui.pages.models_page.QFileDialog.getOpenFileName",
            return_value=("C:/models/sdxl.safetensors", ""),
        ), patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.models_page.QMessageBox.critical"):
            models_page.browse_file()

        with patch(
            "src.ui.pages.models_page.QFileDialog.getOpenFileName",
            return_value=("C:/models/sdxl.safetensors", ""),
        ):
            models_page.browse_file()

        self.assertEqual(model.file_path, "C:/models/sdxl.safetensors")
        self.assertEqual(models_page.file_path_edit.text(), "C:/models/sdxl.safetensors")


class ModelManagerScalarRollbackTest(unittest.TestCase):
    """
    Mission 070: ModelManager.update_name()/update_file_path() roll
    back their respective scalar to its previous value if save() fails
    — single-scalar Domain-only mutations, no filesystem involved, so a
    local rollback is sufficient.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.model_manager = ModelManager(self.workspace_manager, event_bus=self.event_bus)

        self.workspace_manager.create(self.folder)
        self.model = self.model_manager.create("SDXL Base")
        self.model_manager.select(self.model.model_id)
        self.model_manager.update_file_path("C:/models/sdxl.safetensors")

    def test_update_name_save_failure_restores_previous_name_on_same_object(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.model_manager.update_name("SDXL Base Renamed")

        self.assertEqual(self.model.name, "SDXL Base")
        self.assertIs(self.model_manager.active_model, self.model)

    def test_update_name_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.model_manager.update_name("SDXL Base Renamed")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_of_the_same_previously_rejected_name_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.model_manager.update_name("SDXL Base Renamed")

        result = self.model_manager.update_name("SDXL Base Renamed")

        self.assertTrue(result)
        self.assertEqual(self.model.name, "SDXL Base Renamed")

    def test_update_file_path_save_failure_restores_previous_path_on_same_object(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.model_manager.update_file_path("C:/models/rejected.safetensors")

        self.assertEqual(self.model.file_path, "C:/models/sdxl.safetensors")
        self.assertIs(self.model_manager.active_model, self.model)

    def test_update_file_path_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.model_manager.update_file_path("C:/models/rejected.safetensors")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_of_the_same_previously_rejected_file_path_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.model_manager.update_file_path("C:/models/rejected.safetensors")

        result = self.model_manager.update_file_path("C:/models/rejected.safetensors")

        self.assertTrue(result)
        self.assertEqual(self.model.file_path, "C:/models/rejected.safetensors")

    def test_update_name_save_failure_never_touches_file_path(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.model_manager.update_name("SDXL Base Renamed")

        self.assertEqual(self.model.file_path, "C:/models/sdxl.safetensors")


class ModelManagerDeleteRollbackTest(unittest.TestCase):
    """
    Mission 068: ModelManager.delete() rolls back the in-memory removal
    (and active_model_id) if save() fails — Domain-only mutation, so the
    rollback is a simple local re-insertion at the original index, never
    a full Workspace snapshot.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.model_manager = ModelManager(self.workspace_manager, event_bus=self.event_bus)

        self.workspace_manager.create(self.folder)

        self.model_a = self.model_manager.create("Alpha")
        self.model_b = self.model_manager.create("Beta")
        self.model_c = self.model_manager.create("Gamma")
        self.model_manager.select(self.model_b.model_id)

    def test_delete_succeeds_normally_when_save_works(self):
        result = self.model_manager.delete(self.model_b.model_id)

        self.assertTrue(result)
        self.assertEqual(
            [m.model_id for m in self.model_manager.models],
            [self.model_a.model_id, self.model_c.model_id],
        )
        self.assertIsNone(self.model_manager.active_model_id)

    def test_delete_save_failure_restores_object_at_original_index(self):
        received = []
        self.event_bus.subscribe(MODEL_DELETED, lambda payload: received.append(payload))

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.model_manager.delete(self.model_b.model_id)

        models = self.model_manager.models
        self.assertEqual(
            [m.model_id for m in models],
            [self.model_a.model_id, self.model_b.model_id, self.model_c.model_id],
        )
        self.assertIs(models[1], self.model_b)
        self.assertEqual(received, [])

    def test_delete_save_failure_restores_active_model_id(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.model_manager.delete(self.model_b.model_id)

        self.assertEqual(self.model_manager.active_model_id, self.model_b.model_id)

    def test_delete_save_failure_never_touches_an_unrelated_active_id(self):
        self.model_manager.select(self.model_a.model_id)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.model_manager.delete(self.model_b.model_id)

        self.assertEqual(self.model_manager.active_model_id, self.model_a.model_id)

    def test_delete_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.model_manager.delete(self.model_b.model_id)

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_after_save_failure_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.model_manager.delete(self.model_b.model_id)

        result = self.model_manager.delete(self.model_b.model_id)

        self.assertTrue(result)
        self.assertEqual(
            [m.model_id for m in self.model_manager.models],
            [self.model_a.model_id, self.model_c.model_id],
        )


class ModelsPageDeleteConfirmationTest(unittest.TestCase):
    """
    Mission 062: ModelsPage.delete_model() now confirms before deleting,
    mirroring ImagesPage.delete_selected_images()'s established
    QMessageBox pattern (Mission 046) — Cancel is the safe default.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "ModelDeleteProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        model_manager = ModelManager(workspace_manager, event_bus=event_bus)
        models_page = ModelsPage(model_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, models_page.update_models)
        for event_name in MODEL_EVENTS:
            event_bus.subscribe(event_name, models_page.update_models)

        return event_bus, workspace_manager, model_manager, models_page

    def _confirm_delete(self, accept: bool):
        patcher = patch("src.ui.pages.models_page.QMessageBox")
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
        _, workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)

        mock_cls = self._confirm_delete(accept=True)

        models_page.delete_model()

        mock_cls.assert_not_called()

    def test_delete_confirmed_removes_model(self):
        _, workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)

        model = model_manager.create("SDXL Base")
        model_manager.select(model.model_id)

        self._confirm_delete(accept=True)

        models_page.delete_model()

        self.assertIsNone(model_manager.active_model_id)
        self.assertEqual(model_manager.models, [])

    def test_delete_cancelled_calls_neither_manager_nor_mutates_state(self):
        _, workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)

        model = model_manager.create("SDXL Base")
        model_manager.select(model.model_id)

        self._confirm_delete(accept=False)

        with patch.object(model_manager, "delete") as delete_mock:
            models_page.delete_model()
            delete_mock.assert_not_called()

        self.assertEqual(model_manager.active_model_id, model.model_id)
        self.assertEqual(len(model_manager.models), 1)

    def test_delete_confirmed_save_failure_shows_error_and_keeps_the_model(self):
        """
        Mission 068: ModelManager.delete() rolls back the Domain removal
        (and active_model_id) before re-raising on a save() failure —
        the Page must intercept WorkspaceManagerError, inform the user,
        and never present the deletion as successful.
        """
        _, workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)

        model = model_manager.create("SDXL Base")
        model_manager.select(model.model_id)

        mock_cls = self._confirm_delete(accept=True)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            models_page.delete_model()

        mock_cls.critical.assert_called_once()
        self.assertEqual(model_manager.active_model_id, model.model_id)
        self.assertEqual(len(model_manager.models), 1)
        self.assertIs(model_manager.models[0], model)

    def test_retry_after_save_failure_actually_deletes(self):
        _, workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)

        model = model_manager.create("SDXL Base")
        model_manager.select(model.model_id)

        self._confirm_delete(accept=True)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            models_page.delete_model()

        self._confirm_delete(accept=True)
        models_page.delete_model()

        self.assertIsNone(model_manager.active_model_id)
        self.assertEqual(model_manager.models, [])


class ModelsPageDeleteButtonStateTest(unittest.TestCase):
    """
    Mission 063: "Supprimer" must always reflect whether there is
    currently a valid selection to act on, mirroring ImagesPage's
    established delete_button.setEnabled() pattern (Mission 046) —
    never a silent no-op behind an always-clickable button.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "ModelButtonStateProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        model_manager = ModelManager(workspace_manager, event_bus=event_bus)
        models_page = ModelsPage(model_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, models_page.update_models)
        for event_name in MODEL_EVENTS:
            event_bus.subscribe(event_name, models_page.update_models)

        return workspace_manager, model_manager, models_page

    def test_disabled_before_any_workspace(self):
        _, _, models_page = self._wire()
        self.assertFalse(models_page.delete_button.isEnabled())

    def test_disabled_with_no_selection_then_enabled_on_select(self):
        workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)

        self.assertFalse(models_page.delete_button.isEnabled())

        model = model_manager.create("SDXL Base")
        model_manager.select(model.model_id)

        self.assertTrue(models_page.delete_button.isEnabled())

    def test_deselecting_disables_delete_button(self):
        workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)
        model = model_manager.create("SDXL Base")
        model_manager.select(model.model_id)
        self.assertTrue(models_page.delete_button.isEnabled())

        models_page.model_list.setCurrentItem(None)

        self.assertFalse(models_page.delete_button.isEnabled())

    def test_delete_button_stays_consistent_after_list_rebuild(self):
        workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)
        model_a = model_manager.create("SDXL Base")
        model_manager.select(model_a.model_id)
        self.assertTrue(models_page.delete_button.isEnabled())

        # MODEL_CREATED triggers update_models() -> a full list rebuild,
        # while the active selection itself is untouched.
        model_manager.create("SD1.5 Base")

        self.assertTrue(models_page.delete_button.isEnabled())
        self.assertEqual(models_page.model_list.currentItem().data(Qt.UserRole), model_a.model_id)

    def test_disabled_after_workspace_closed(self):
        workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)
        model = model_manager.create("SDXL Base")
        model_manager.select(model.model_id)
        self.assertTrue(models_page.delete_button.isEnabled())

        workspace_manager.close()

        self.assertFalse(models_page.delete_button.isEnabled())

    def test_disabled_after_deleting_the_selected_model(self):
        workspace_manager, model_manager, models_page = self._wire()
        workspace_manager.create(self.folder)
        model = model_manager.create("SDXL Base")
        model_manager.select(model.model_id)
        self.assertTrue(models_page.delete_button.isEnabled())

        # MODEL_DELETED triggers update_models() -> the button must be
        # recomputed from the resulting (now empty) selection.
        model_manager.delete(model.model_id)

        self.assertFalse(models_page.delete_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
