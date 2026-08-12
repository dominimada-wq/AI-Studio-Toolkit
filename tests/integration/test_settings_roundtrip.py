"""
Integration coverage for the Workspace Settings lifecycle, exercising
SettingsManager, Workspace.settings, EventBus and the real
DashboardPage/ImagesPage/SettingsPage widgets together — the same
wiring MainWindow uses. Also covers the Settings domain object's own
to_dict()/from_dict() round-trip and default-value behavior directly,
since Settings is a new entity introduced this mission.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from src.core.event_bus import EventBus
from src.domain.settings import Settings
from src.domain.workspace import Workspace
from src.managers.workspace_manager import (
    WorkspaceManager,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_SAVED,
    WORKSPACE_CLOSED,
)
from src.managers.settings_manager import SettingsManager
from src.managers.application_settings_manager import (
    ApplicationSettingsManager,
    APPLICATION_SETTINGS_UPDATED,
)
from src.ui.pages.dashboard_page import DashboardPage
from src.ui.pages.images_page import ImagesPage
from src.ui.pages.settings_page import SettingsPage

WORKSPACE_EVENTS = (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_SAVED, WORKSPACE_CLOSED)

_app = QApplication.instance() or QApplication([])


class SettingsRoundTripTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "SettingsProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        settings_manager = SettingsManager(workspace_manager)
        # Isolated from the Workspace folder on purpose: ApplicationSettings
        # is a separate, machine-local persistence tier.
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "AppSettings",
            event_bus=event_bus,
        )

        dashboard = DashboardPage()
        images = ImagesPage(workspace_manager)
        settings_page = SettingsPage(settings_manager, application_settings_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, dashboard.update_project)
            event_bus.subscribe(event_name, images.update_images)
            event_bus.subscribe(event_name, settings_page.update_settings)

        event_bus.subscribe(
            APPLICATION_SETTINGS_UPDATED, settings_page.update_application_settings
        )

        return (
            event_bus, workspace_manager, settings_manager,
            dashboard, images, settings_page, application_settings_manager,
        )

    def test_settings_domain_object_roundtrip_and_defaults(self):

        # Default values.
        settings = Settings()
        self.assertEqual(settings.theme, "")
        self.assertEqual(settings.language, "")
        self.assertEqual(settings.to_dict(), {"theme": "", "language": ""})

        # Round-trip without loss of information.
        original = Settings(theme="dark", language="fr-FR")
        restored = Settings.from_dict(original.to_dict())
        self.assertEqual(original, restored)

        # Missing key -> default, consistent with every other Domain object.
        self.assertEqual(Settings.from_dict({}), Settings())

        # Partial dict -> only the given key is set, the rest defaults.
        self.assertEqual(Settings.from_dict({"theme": "dark"}), Settings(theme="dark", language=""))

        # Unknown key ignored, known keys preserved exactly.
        self.assertEqual(
            Settings.from_dict({"theme": "dark", "language": "fr", "unknown": "ignored"}),
            Settings(theme="dark", language="fr"),
        )

        # "" is a real, preserved value — not collapsed or treated as absent.
        self.assertEqual(Settings.from_dict({"theme": ""}).theme, "")
        self.assertEqual(Settings(theme="My Custom Theme").theme, "My Custom Theme")

    def test_workspace_settings_compatibility_and_roundtrip(self):

        self.assertEqual(Workspace().settings, Settings())
        self.assertEqual(Workspace().to_dict()["settings"], {"theme": "", "language": ""})

        cases = [
            ("absent", {}, Settings()),
            ("settings = {}", {"settings": {}}, Settings()),
            ("settings = null", {"settings": None}, Settings()),
            ("settings = []", {"settings": []}, Settings()),
            ("settings = \"\"", {"settings": ""}, Settings()),
            ("settings = 42", {"settings": 42}, Settings()),
            ("settings = {'theme': 'dark'}", {"settings": {"theme": "dark"}}, Settings(theme="dark")),
            (
                "settings = {'theme': 'dark', 'language': 'fr'}",
                {"settings": {"theme": "dark", "language": "fr"}},
                Settings(theme="dark", language="fr"),
            ),
            (
                "old machine-local keys",
                {"settings": {"python_path": "C:/Python", "comfyui_path": "C:/ComfyUI", "onetrainer_path": "C:/OneTrainer"}},
                Settings(),
            ),
            (
                "unknown key alongside a known one",
                {"settings": {"theme": "dark", "unknown": "value"}},
                Settings(theme="dark"),
            ),
        ]

        for label, data, expected in cases:
            self.assertEqual(Workspace.from_dict(data).settings, expected, label)

        # Positive real round-trip with populated values, and confirmation
        # that no other Workspace field is disturbed by the conversion.
        original = Workspace(
            name="MyProject",
            settings=Settings(theme="My Custom Theme", language="fr-FR"),
        )
        restored = Workspace.from_dict(original.to_dict())

        self.assertEqual(restored.settings, Settings(theme="My Custom Theme", language="fr-FR"))
        self.assertEqual(restored.name, original.name)
        self.assertEqual(restored.images, original.images)
        self.assertEqual(restored.datasets, original.datasets)
        self.assertEqual(restored.models, original.models)
        self.assertEqual(restored.workflows, original.workflows)
        self.assertEqual(restored.loras, original.loras)
        self.assertEqual(restored.training, original.training)
        self.assertEqual(restored.characters, original.characters)

    def test_settings_manager_without_workspace(self):

        workspace_manager = WorkspaceManager()
        settings_manager = SettingsManager(workspace_manager)

        self.assertEqual(settings_manager.settings, Settings())

        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            result = settings_manager.update(theme="dark")
            self.assertFalse(result)
            save_spy.assert_not_called()

        # Architectural proof, not an implementation-detail lock-in: this
        # Manager takes no event_bus at all — its constructor has a single
        # parameter — so there is nothing for it to publish or subscribe
        # to. Verified by construction, not by inspecting private state.
        self.assertEqual(SettingsManager.__init__.__code__.co_argcount, 2)  # self, workspace_manager

    def test_settings_manager_update_is_idempotent_and_atomic(self):

        _, workspace_manager, settings_manager = self._wire()[:3]
        workspace_manager.create(self.folder)

        # No arguments at all: no-op.
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertFalse(settings_manager.update())
            save_spy.assert_not_called()

        # theme alone.
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertTrue(settings_manager.update(theme="dark"))
            save_spy.assert_called_once()
        self.assertEqual(settings_manager.settings.theme, "dark")
        self.assertEqual(settings_manager.settings.language, "")

        # language alone.
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertTrue(settings_manager.update(language="fr"))
            save_spy.assert_called_once()
        self.assertEqual(settings_manager.settings.theme, "dark")
        self.assertEqual(settings_manager.settings.language, "fr")

        # Identical values: no-op, exactly 0 save().
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertFalse(settings_manager.update(theme="dark", language="fr"))
            save_spy.assert_not_called()

        # Both fields simultaneously, both differ: exactly 1 save() for
        # the whole batch, both values correctly applied.
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertTrue(settings_manager.update(theme="light", language="fr-FR"))
            save_spy.assert_called_once()
        self.assertEqual(settings_manager.settings.theme, "light")
        self.assertEqual(settings_manager.settings.language, "fr-FR")

        # One field identical, one field different: still exactly 1
        # save() for the whole call, both fields end up correct.
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertTrue(settings_manager.update(theme="light", language="en"))
            save_spy.assert_called_once()
        self.assertEqual(settings_manager.settings.theme, "light")
        self.assertEqual(settings_manager.settings.language, "en")

        # "" is a real value, distinct from "not provided" (None).
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            self.assertTrue(settings_manager.update(theme=""))
            save_spy.assert_called_once()
        self.assertEqual(settings_manager.settings.theme, "")
        self.assertEqual(settings_manager.settings.language, "en")

    def test_settings_persist_across_close_and_reopen(self):

        _, workspace_manager, settings_manager = self._wire()[:3]
        workspace_manager.create(self.folder)

        settings_manager.update(theme="dark", language="fr-FR")
        workspace_manager.close()

        # Reopen with a fully independent stack — real disk round-trip,
        # never the closed instance above.
        _, workspace_manager_2, settings_manager_2 = self._wire()[:3]
        workspace_manager_2.open(self.folder)

        self.assertEqual(settings_manager_2.settings.theme, "dark")
        self.assertEqual(settings_manager_2.settings.language, "fr-FR")

    def test_settings_isolated_between_workspaces(self):

        folder_a = self.folder / "A"
        folder_b = self.folder / "B"

        _, workspace_manager_a, settings_manager_a = self._wire()[:3]
        workspace_manager_a.create(folder_a)
        settings_manager_a.update(theme="dark", language="fr")

        _, workspace_manager_b, settings_manager_b = self._wire()[:3]
        workspace_manager_b.create(folder_b)
        settings_manager_b.update(theme="light", language="en")

        self.assertEqual(settings_manager_a.settings.theme, "dark")
        self.assertEqual(settings_manager_a.settings.language, "fr")
        self.assertEqual(settings_manager_b.settings.theme, "light")
        self.assertEqual(settings_manager_b.settings.language, "en")

        # Reopen A independently: still "dark"/"fr", unaffected by B.
        _, workspace_manager_a2, settings_manager_a2 = self._wire()[:3]
        workspace_manager_a2.open(folder_a)
        self.assertEqual(settings_manager_a2.settings.theme, "dark")
        self.assertEqual(settings_manager_a2.settings.language, "fr")

        # Reopen B independently: still "light"/"en", unaffected by A.
        _, workspace_manager_b2, settings_manager_b2 = self._wire()[:3]
        workspace_manager_b2.open(folder_b)
        self.assertEqual(settings_manager_b2.settings.theme, "light")
        self.assertEqual(settings_manager_b2.settings.language, "en")

    def test_settings_operations_do_not_mutate_other_workspace_collections(self):

        _, workspace_manager, settings_manager = self._wire()[:3]
        workspace_manager.create(self.folder)

        workspace = workspace_manager.current_workspace
        characters_before = [c.to_dict() for c in workspace.characters]
        models_before = [m.to_dict() for m in workspace.models]
        workflows_before = [w.to_dict() for w in workspace.workflows]
        datasets_before = list(workspace.datasets)
        loras_before = list(workspace.loras)
        training_before = dict(workspace.training)
        images_before = list(workspace.images)

        settings_manager.update(theme="dark", language="fr-FR")

        self.assertEqual([c.to_dict() for c in workspace.characters], characters_before)
        self.assertEqual([m.to_dict() for m in workspace.models], models_before)
        self.assertEqual([w.to_dict() for w in workspace.workflows], workflows_before)
        self.assertEqual(workspace.datasets, datasets_before)
        self.assertEqual(workspace.loras, loras_before)
        self.assertEqual(workspace.training, training_before)
        self.assertEqual(workspace.images, images_before)

    def test_settings_page_reflects_workspace_lifecycle(self):

        (event_bus, workspace_manager, settings_manager,
         _dashboard, _images, settings_page, _application_settings_manager) = self._wire()

        # No workspace: empty and disabled.
        self.assertEqual(settings_page.theme_edit.text(), "")
        self.assertEqual(settings_page.language_edit.text(), "")
        self.assertFalse(settings_page.theme_edit.isEnabled())
        self.assertFalse(settings_page.language_edit.isEnabled())
        self.assertFalse(settings_page.save_button.isEnabled())

        # Workspace opened: enabled, defaults shown.
        workspace_manager.create(self.folder)
        self.assertTrue(settings_page.theme_edit.isEnabled())
        self.assertTrue(settings_page.language_edit.isEnabled())
        self.assertTrue(settings_page.save_button.isEnabled())
        self.assertEqual(settings_page.theme_edit.text(), "")

        # Save button drives SettingsManager, real persistence.
        settings_page.theme_edit.setText("dark")
        settings_page.language_edit.setText("fr")
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            settings_page.save_settings()
            save_spy.assert_called_once()
        self.assertEqual(settings_manager.settings.theme, "dark")
        self.assertEqual(settings_manager.settings.language, "fr")

        # Clicking Save again with identical field values: no extra save.
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            settings_page.save_settings()
            save_spy.assert_not_called()

        # Unsaved edit, then a different workspace opens: draft discarded,
        # fields reflect the new workspace instead.
        settings_page.theme_edit.setText("UNSAVED_DRAFT")
        workspace_manager.create(self.folder / "Other")
        self.assertNotEqual(settings_page.theme_edit.text(), "UNSAVED_DRAFT")
        self.assertEqual(settings_page.theme_edit.text(), "")

        # Closing: empty and disabled again.
        workspace_manager.close()
        self.assertEqual(settings_page.theme_edit.text(), "")
        self.assertEqual(settings_page.language_edit.text(), "")
        self.assertFalse(settings_page.theme_edit.isEnabled())
        self.assertFalse(settings_page.language_edit.isEnabled())
        self.assertFalse(settings_page.save_button.isEnabled())

    def test_no_duplicate_subscriptions_between_wire_calls(self):

        wired_1 = self._wire()
        wired_2 = self._wire()

        for obj_1, obj_2 in zip(wired_1, wired_2):
            self.assertIsNot(obj_1, obj_2)

        event_bus_1, event_bus_2 = wired_1[0], wired_2[0]
        settings_page_1, settings_page_2 = wired_1[5], wired_2[5]

        for event_name in WORKSPACE_EVENTS:
            self.assertIn(settings_page_1.update_settings, event_bus_1._subscribers[event_name])
            count = sum(
                1 for cb in event_bus_1._subscribers[event_name]
                if cb == settings_page_1.update_settings
            )
            self.assertEqual(count, 1)

        self.assertTrue(
            set(event_bus_1._subscribers[WORKSPACE_CREATED]).isdisjoint(
                event_bus_2._subscribers[WORKSPACE_CREATED]
            )
        )

        # Settings has no CHARACTER_*/DATASET_*/TRAINING_*/MODEL_*/WORKFLOW_*
        # events to subscribe to in the first place — nothing to assert
        # beyond what _wire() itself already demonstrates: only the 4
        # WORKSPACE_* events carry the subscription.


if __name__ == "__main__":
    unittest.main()
