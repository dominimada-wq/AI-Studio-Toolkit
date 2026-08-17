"""
Integration coverage for the Model lifecycle, exercising ModelManager,
Workspace.models, EventBus and the real DashboardPage/CharactersPage/
ImagesPage/ModelsPage widgets together — the same wiring MainWindow
uses. Also covers the Model domain object's own to_dict()/from_dict()
round-trip and default-value behavior directly, since Model is a new
entity introduced this mission.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from src.core.event_bus import EventBus
from src.domain.model import Model
from src.domain.workspace import Workspace
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
        characters_page = CharactersPage(character_manager)
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


if __name__ == "__main__":
    unittest.main()
