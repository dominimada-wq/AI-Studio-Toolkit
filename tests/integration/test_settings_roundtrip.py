"""
Integration coverage for the Workspace Settings lifecycle, exercising
SettingsManager, Workspace.settings, EventBus and the real
DashboardPage/ImagesPage/SettingsPage widgets together — the same
wiring MainWindow uses. Also covers the Settings domain object's own
to_dict()/from_dict() round-trip and default-value behavior directly,
since Settings is a new entity introduced this mission.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from src.core.event_bus import EventBus
from src.domain.settings import Settings
from src.domain.workspace import Workspace
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
from src.managers.character_manager import CharacterManager
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

        # Mission 078: settings_page.update_settings() is subscribed only
        # to WORKSPACE_SAVED/WORKSPACE_RENAMED (preserves an unsaved
        # theme/language draft across an unrelated save elsewhere) —
        # WORKSPACE_CREATED/OPENED/CLOSED are a genuine context change,
        # handled exclusively by reset_for_context_change(), which always
        # discards any draft. Same split as PromptsPage (Mission 038).
        event_bus.subscribe(WORKSPACE_SAVED, settings_page.update_settings)
        event_bus.subscribe(WORKSPACE_RENAMED, settings_page.update_settings)
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            event_bus.subscribe(event_name, settings_page.reset_for_context_change)

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
        self.assertEqual(restored.models, original.models)
        self.assertEqual(restored.workflows, original.workflows)
        self.assertEqual(restored.characters, original.characters)
        # Mission 057 removed the vestigial Workspace.datasets/.loras/
        # .training fields these assertions used to check.

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
        images_before = list(workspace.images)

        settings_manager.update(theme="dark", language="fr-FR")

        self.assertEqual([c.to_dict() for c in workspace.characters], characters_before)
        self.assertEqual([m.to_dict() for m in workspace.models], models_before)
        self.assertEqual([w.to_dict() for w in workspace.workflows], workflows_before)
        self.assertEqual(workspace.images, images_before)
        # Mission 057 removed the vestigial Workspace.datasets/.loras/
        # .training fields these assertions used to check.

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

        # Mission 078: update_settings() only carries WORKSPACE_SAVED (the
        # only event this specific test's _wire() also imports/exercises
        # via that name — WORKSPACE_RENAMED is covered separately above)
        # ; WORKSPACE_CREATED/OPENED/CLOSED now carry
        # reset_for_context_change() instead.
        for event_name, method_name in (
            (WORKSPACE_SAVED, "update_settings"),
            (WORKSPACE_CREATED, "reset_for_context_change"),
            (WORKSPACE_OPENED, "reset_for_context_change"),
            (WORKSPACE_CLOSED, "reset_for_context_change"),
        ):
            method_1 = getattr(settings_page_1, method_name)
            self.assertIn(method_1, event_bus_1._subscribers[event_name])
            count = sum(
                1 for cb in event_bus_1._subscribers[event_name] if cb == method_1
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


class SettingsManagerUpdateRollbackTest(unittest.TestCase):
    """
    Mission 077: SettingsManager.update() rolls back settings.theme/
    settings.language to their exact previous values, on the same
    Settings instance, if save() fails — no filesystem involved, no
    dedicated event published (SettingsManager takes no event_bus at
    all — WORKSPACE_SAVED is WorkspaceManager's own event, never
    published if its save() raises), no other Workspace state touched.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.settings_manager = SettingsManager(self.workspace_manager)

        self.workspace_manager.create(self.folder)
        self.settings_manager.update(theme="light", language="en")
        self.settings = self.workspace_manager.current_workspace.settings

    def test_update_succeeds_normally_when_save_works(self):
        result = self.settings_manager.update(theme="dark", language="fr")

        self.assertTrue(result)
        self.assertEqual(self.settings.theme, "dark")
        self.assertEqual(self.settings.language, "fr")

    def test_update_theme_only_on_success(self):
        self.settings_manager.update(theme="dark")

        self.assertEqual(self.settings.theme, "dark")
        self.assertEqual(self.settings.language, "en")

    def test_update_language_only_on_success(self):
        self.settings_manager.update(language="fr")

        self.assertEqual(self.settings.theme, "light")
        self.assertEqual(self.settings.language, "fr")

    def test_update_both_theme_and_language_simultaneously_on_success(self):
        self.settings_manager.update(theme="dark", language="fr")

        self.assertEqual(self.settings.theme, "dark")
        self.assertEqual(self.settings.language, "fr")

    def test_update_save_failure_raises_workspace_manager_error(self):
        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.settings_manager.update(theme="dark", language="fr")

    def test_update_save_failure_restores_exact_previous_values_both_fields(self):
        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.settings_manager.update(theme="dark", language="fr")

        self.assertEqual(self.settings.theme, "light")
        self.assertEqual(self.settings.language, "en")

    def test_update_save_failure_restores_exact_previous_value_theme_only(self):
        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.settings_manager.update(theme="dark")

        self.assertEqual(self.settings.theme, "light")
        self.assertEqual(self.settings.language, "en")

    def test_update_save_failure_restores_exact_previous_value_language_only(self):
        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.settings_manager.update(language="fr")

        self.assertEqual(self.settings.theme, "light")
        self.assertEqual(self.settings.language, "en")

    def test_update_save_failure_keeps_the_same_settings_instance(self):
        settings_before = self.workspace_manager.current_workspace.settings

        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.settings_manager.update(theme="dark", language="fr")

        self.assertIs(self.workspace_manager.current_workspace.settings, settings_before)

    def test_update_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.settings_manager.update(theme="dark", language="fr")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)

        self.assertEqual(before, after)
        self.assertEqual(after["settings"]["theme"], "light")
        self.assertEqual(after["settings"]["language"], "en")

    def test_update_save_failure_publishes_no_event(self):
        publish_calls = []
        self.event_bus.publish = lambda *args, **kwargs: publish_calls.append((args, kwargs))

        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.settings_manager.update(theme="dark", language="fr")

        self.assertEqual(publish_calls, [])

    def test_update_save_failure_does_not_mutate_unrelated_workspace_state(self):
        character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        character = character_manager.create("Aria")
        workspace = self.workspace_manager.current_workspace
        characters_before = [c.to_dict() for c in workspace.characters]
        images_before = list(workspace.images)

        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.settings_manager.update(theme="dark", language="fr")

        self.assertEqual([c.to_dict() for c in workspace.characters], characters_before)
        self.assertEqual(workspace.images, images_before)

    def test_retry_after_update_failure_is_a_genuine_new_attempt(self):
        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.settings_manager.update(theme="dark", language="fr")

        self.assertEqual(self.settings.theme, "light")

        result = self.settings_manager.update(theme="dark", language="fr")

        self.assertTrue(result)
        self.assertEqual(self.settings.theme, "dark")
        self.assertEqual(self.settings.language, "fr")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertEqual(on_disk["settings"]["theme"], "dark")
        self.assertEqual(on_disk["settings"]["language"], "fr")

    def test_unrelated_later_save_no_longer_persists_previously_rejected_values(self):
        """
        Mission 077's core non-regression test: reproduces, as a permanent
        automated test, the exact scenario empirically demonstrated during
        the pre-mission audit — a rejected settings value used to survive
        in memory and get silently persisted by a later, completely
        unrelated successful save(). This must no longer happen.
        """
        character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)

        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.settings_manager.update(theme="dark-rejected")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)
        self.assertEqual(before["settings"]["theme"], "light")

        # A totally unrelated, successful mutation elsewhere in the Domain.
        character_manager.create("Someone Else")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(after["settings"]["theme"], "light")
        self.assertNotEqual(after["settings"]["theme"], "dark-rejected")


class SettingsPagePersistenceFailureTest(unittest.TestCase):
    """
    Mission 077: SettingsPage.save_settings() already caught
    WorkspaceManagerError since Mission 055 (QMessageBox.critical()) —
    this class only adds coverage for the new resync behavior:
    theme_edit/language_edit must reflect the rolled-back Domain values
    after a failure, not the rejected ones just typed, and the fields
    must remain enabled for a genuine retry.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.settings_manager = SettingsManager(self.workspace_manager)
        self.application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "AppSettings",
            event_bus=self.event_bus,
        )
        self.settings_page = SettingsPage(self.settings_manager, self.application_settings_manager)

        # Mission 078: split subscription — see SettingsRoundTripTest._wire().
        self.event_bus.subscribe(WORKSPACE_SAVED, self.settings_page.update_settings)
        self.event_bus.subscribe(WORKSPACE_RENAMED, self.settings_page.update_settings)
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            self.event_bus.subscribe(event_name, self.settings_page.reset_for_context_change)

        self.workspace_manager.create(self.folder)
        self.settings_manager.update(theme="light", language="en")

    def test_save_settings_failure_shows_critical_error(self):
        self.settings_page.theme_edit.setText("dark-rejected")
        self.settings_page.language_edit.setText("fr-rejected")

        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ), patch("src.ui.pages.settings_page.QMessageBox") as mock_box:
            self.settings_page.save_settings()

        self.assertTrue(mock_box.critical.called)

    def test_save_settings_failure_resyncs_fields_to_rolled_back_domain_state(self):
        self.settings_page.theme_edit.setText("dark-rejected")
        self.settings_page.language_edit.setText("fr-rejected")

        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ), patch("src.ui.pages.settings_page.QMessageBox"):
            self.settings_page.save_settings()

        self.assertEqual(self.settings_page.theme_edit.text(), "light")
        self.assertEqual(self.settings_page.language_edit.text(), "en")
        self.assertEqual(self.settings_manager.settings.theme, "light")
        self.assertEqual(self.settings_manager.settings.language, "en")

    def test_save_settings_failure_leaves_fields_enabled_for_retry(self):
        self.settings_page.theme_edit.setText("dark-rejected")

        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ), patch("src.ui.pages.settings_page.QMessageBox"):
            self.settings_page.save_settings()

        self.assertTrue(self.settings_page.theme_edit.isEnabled())
        self.assertTrue(self.settings_page.language_edit.isEnabled())
        self.assertTrue(self.settings_page.save_button.isEnabled())

    def test_save_settings_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        self.settings_page.theme_edit.setText("dark-rejected")

        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ), patch("src.ui.pages.settings_page.QMessageBox"):
            self.settings_page.save_settings()

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_after_save_settings_failure_actually_persists(self):
        self.settings_page.theme_edit.setText("dark-rejected")

        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ), patch("src.ui.pages.settings_page.QMessageBox"):
            self.settings_page.save_settings()

        self.settings_page.theme_edit.setText("dark")
        self.settings_page.save_settings()

        self.assertEqual(self.settings_manager.settings.theme, "dark")
        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertEqual(on_disk["settings"]["theme"], "dark")


class SettingsPageDirtyStateTest(unittest.TestCase):
    """
    Mission 078: SettingsPage.update_settings() used to unconditionally
    overwrite theme_edit/language_edit on every WORKSPACE_SAVED/RENAMED/
    CREATED/OPENED/CLOSED event — an unsaved draft was silently destroyed
    by any unrelated mutation elsewhere in the app (empirically
    reproduced during the post-Mission-077 audit, theme_edit scenario).
    This mirrors the exact bug class already fixed for PromptsPage by
    Mission 038: a local _dirty flag now preserves a genuine draft across
    a non-destructive refresh (WORKSPACE_SAVED/RENAMED), while a genuine
    Workspace context change (reset_for_context_change(), subscribed to
    WORKSPACE_CREATED/OPENED/CLOSED) still unconditionally discards it —
    and the Mission 077 rollback-on-failure contract is never broken:
    a rejected value must never be shown or later silently persisted.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.settings_manager = SettingsManager(self.workspace_manager)
        self.application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "AppSettings",
            event_bus=self.event_bus,
        )
        self.settings_page = SettingsPage(self.settings_manager, self.application_settings_manager)

        # Mission 078: same split as the real main_window.py wiring.
        self.event_bus.subscribe(WORKSPACE_SAVED, self.settings_page.update_settings)
        self.event_bus.subscribe(WORKSPACE_RENAMED, self.settings_page.update_settings)
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            self.event_bus.subscribe(event_name, self.settings_page.reset_for_context_change)

        self.workspace_manager.create(self.folder)

    def test_dirty_theme_draft_preserved_across_unrelated_workspace_saved(self):
        """
        Mission 078's core non-regression test: reproduces, as a
        permanent automated test, the exact theme_edit scenario
        empirically demonstrated during the post-Mission-077 audit — an
        unrelated mutation elsewhere (here, creating a Character) must
        never wipe an unsaved theme/language draft.
        """
        self.settings_page.theme_edit.setText("DRAFT THEME NOT SAVED YET")
        self.assertTrue(self.settings_page._dirty)

        self.character_manager.create("Aria")

        self.assertEqual(self.settings_page.theme_edit.text(), "DRAFT THEME NOT SAVED YET")
        self.assertTrue(self.settings_page._dirty)

    def test_both_dirty_fields_preserved_simultaneously(self):
        self.settings_page.theme_edit.setText("draft-theme")
        self.settings_page.language_edit.setText("draft-lang")

        self.character_manager.create("Aria")

        self.assertEqual(self.settings_page.theme_edit.text(), "draft-theme")
        self.assertEqual(self.settings_page.language_edit.text(), "draft-lang")

    def test_successful_save_clears_dirty_and_persists(self):
        self.settings_page.theme_edit.setText("dark")
        self.settings_page.save_settings()

        self.assertFalse(self.settings_page._dirty)
        self.assertEqual(self.settings_manager.settings.theme, "dark")

    def test_failed_save_still_resyncs_and_clears_dirty_per_mission_077_contract(self):
        self.settings_manager.update(theme="light")

        self.settings_page.theme_edit.setText("dark-rejected")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.settings_page.QMessageBox"):
            self.settings_page.save_settings()

        self.assertEqual(self.settings_page.theme_edit.text(), "light")
        self.assertFalse(self.settings_page._dirty)

    def test_non_dirty_refresh_reflects_external_manager_mutation(self):
        self.settings_manager.update(theme="changed-elsewhere")

        self.assertEqual(self.settings_page.theme_edit.text(), "changed-elsewhere")
        self.assertFalse(self.settings_page._dirty)

    def test_programmatic_refresh_never_sets_false_dirty_state(self):
        self.assertFalse(self.settings_page._dirty)

        self.character_manager.create("Aria")
        self.assertFalse(self.settings_page._dirty)

        self.settings_page.update_settings()
        self.assertFalse(self.settings_page._dirty)

    def test_real_context_change_discards_dirty_draft(self):
        self.settings_page.theme_edit.setText("draft lost on workspace close")
        self.assertTrue(self.settings_page._dirty)

        self.workspace_manager.close()

        self.assertEqual(self.settings_page.theme_edit.text(), "")
        self.assertFalse(self.settings_page._dirty)
        self.assertFalse(self.settings_page.theme_edit.isEnabled())

    def test_unrelated_later_save_no_longer_persists_previously_rejected_theme(self):
        """
        Mission 078 + Mission 077 combined non-regression: a rejected
        theme must never leak into project.json even once the dirty-
        state protection is layered on top of Mission 077's rollback.
        """
        self.settings_manager.update(theme="light")

        self.settings_page.theme_edit.setText("dark-rejected")
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.settings_page.QMessageBox"):
            self.settings_page.save_settings()

        # Unrelated later save, real success this time.
        self.character_manager.create("Aria")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertEqual(on_disk["settings"]["theme"], "light")

    def test_confirm_context_change_without_dirty_draft_returns_true_no_dialog(self):
        with patch("src.ui.pages.settings_page.QMessageBox") as mock_message_box:
            self.assertTrue(self.settings_page.confirm_context_change())
            mock_message_box.assert_not_called()

    def test_confirm_context_change_save_choice_persists_and_returns_true(self):
        self.settings_page.theme_edit.setText("saved-before-switch")

        with patch("src.ui.pages.settings_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Save
            self.assertTrue(self.settings_page.confirm_context_change())

        self.assertFalse(self.settings_page._dirty)
        self.assertEqual(self.settings_manager.settings.theme, "saved-before-switch")

    def test_confirm_context_change_discard_choice_returns_true_without_persisting(self):
        self.settings_page.theme_edit.setText("should-be-discarded")

        with patch("src.ui.pages.settings_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Discard
            self.assertTrue(self.settings_page.confirm_context_change())

        self.assertFalse(self.settings_page._dirty)
        self.assertEqual(self.settings_manager.settings.theme, "")

    def test_confirm_context_change_cancel_choice_returns_false_keeps_dirty(self):
        self.settings_page.theme_edit.setText("still-editing")

        with patch("src.ui.pages.settings_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Cancel
            self.assertFalse(self.settings_page.confirm_context_change())

        self.assertTrue(self.settings_page._dirty)
        self.assertEqual(self.settings_manager.settings.theme, "")

    def test_confirm_context_change_save_failure_resyncs_and_returns_false(self):
        self.settings_manager.update(theme="light")

        self.settings_page.theme_edit.setText("rejected-on-switch")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.settings_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Save
            self.assertFalse(self.settings_page.confirm_context_change())

        self.assertTrue(mock_message_box.critical.called)
        self.assertEqual(self.settings_page.theme_edit.text(), "light")
        self.assertFalse(self.settings_page._dirty)

    def test_retry_after_confirm_context_change_save_failure_actually_persists(self):
        self.settings_page.theme_edit.setText("rejected-on-switch")
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.settings_page.QMessageBox") as mock_message_box:
            mock_message_box.return_value.exec.return_value = mock_message_box.Save
            self.settings_page.confirm_context_change()

        self.settings_page.theme_edit.setText("recovered")
        self.settings_page.save_settings()

        self.assertEqual(self.settings_manager.settings.theme, "recovered")
        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertEqual(on_disk["settings"]["theme"], "recovered")


if __name__ == "__main__":
    unittest.main()
