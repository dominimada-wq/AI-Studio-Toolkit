"""
Integration coverage for the Workspace create/open/save/close cycle,
exercising WorkspaceManager, WorkspaceStorage and EventBus together
with the real DashboardPage/ImagesPage widgets — the same wiring
MainWindow uses (see src/ui/main_window.py).
"""

import json
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
from src.ui.pages.dashboard_page import DashboardPage
from src.ui.pages.images_page import ImagesPage

WORKSPACE_EVENTS = (
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_SAVED,
    WORKSPACE_CLOSED,
)

# A QApplication instance is required before any QWidget can be created.
_app = QApplication.instance() or QApplication([])


class WorkspaceRoundTripTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "RoundTripProject"

    def _wire(self, event_bus, workspace_manager):
        dashboard = DashboardPage()
        images = ImagesPage(workspace_manager)

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, dashboard.update_project)
            event_bus.subscribe(event_name, images.update_images)

        return dashboard, images

    def test_full_create_import_save_close_reopen_cycle(self):

        event_bus = EventBus()
        manager = WorkspaceManager(event_bus=event_bus)
        dashboard, images = self._wire(event_bus, manager)

        # 1. Create
        manager.create(self.folder)
        self.assertEqual(dashboard.projectCard.value.text(), self.folder.name)
        self.assertEqual(dashboard.imagesCard.value.text(), "0")

        # 2. Import images
        added = manager.add_images(["ref1.png", "ref2.png"])
        self.assertEqual(added, 2)
        self.assertEqual(
            [images.list_widget.item(i).text() for i in range(images.list_widget.count())],
            ["ref1.png", "ref2.png"],
        )
        self.assertEqual(dashboard.imagesCard.value.text(), "2")

        # 3. Save
        manager.save()

        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertEqual(
            [image["file_path"] for image in on_disk["images"]],
            ["ref1.png", "ref2.png"],
        )
        self.assertTrue(all(image["image_id"] for image in on_disk["images"]))

        # 4. Close
        manager.close()
        self.assertIsNone(manager.current_workspace)
        self.assertEqual(dashboard.projectCard.value.text(), "Aucun")
        self.assertEqual(images.list_widget.count(), 0)

        # 5. Reopen — fresh manager/event_bus/pages, simulating a real
        # application restart rather than reusing in-memory state.
        event_bus_2 = EventBus()
        manager_2 = WorkspaceManager(event_bus=event_bus_2)
        dashboard_2, images_2 = self._wire(event_bus_2, manager_2)

        workspace = manager_2.open(self.folder)
        self.assertIsNotNone(workspace)
        self.assertEqual(
            [image.file_path for image in workspace.images],
            ["ref1.png", "ref2.png"],
        )

        # 6. Dashboard and ImagesPage reflect the restored data
        self.assertEqual(dashboard_2.projectCard.value.text(), self.folder.name)
        self.assertEqual(dashboard_2.imagesCard.value.text(), "2")
        self.assertEqual(
            [images_2.list_widget.item(i).text() for i in range(images_2.list_widget.count())],
            ["ref1.png", "ref2.png"],
        )

    def test_failed_open_does_not_close_current_workspace(self):
        """
        Business rule: attempting to open an invalid folder must never
        close the workspace that is currently open. Regression test for
        a bug found during manual testing of Commit 6 and fixed in
        Commit 8 (WorkspaceManager.open() used to unconditionally reset
        current_workspace to None whenever the target folder had no
        project.json, even with a valid workspace already open).
        """

        event_bus = EventBus()
        manager = WorkspaceManager(event_bus=event_bus)
        manager.create(self.folder)

        invalid_folder = Path(self.tmp_dir) / "NoProjectJsonHere"
        invalid_folder.mkdir()

        result = manager.open(invalid_folder)

        self.assertIsNone(result)
        self.assertIsNotNone(manager.current_workspace)
        self.assertEqual(manager.current_workspace.name, self.folder.name)


if __name__ == "__main__":
    unittest.main()
