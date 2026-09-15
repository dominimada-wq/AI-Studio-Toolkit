"""
Real-widget coverage for Mission 017 — Dashboard Actions Wiring.
DashboardPage's newProjectButton/openProjectButton/importImagesButton
are exercised by real clicks through a real MainWindow, proving the
same observable outcome as calling MainWindow.new_project()/
open_project()/ImagesPage.import_images() directly (see
test_main_window_new_project.py/test_images_page.py) — not merely that
a .connect() line exists. NewProjectDialog and the relevant QFileDialog
entry points are patched throughout: a real modal exec()/native picker
would block the test process (same lesson as Missions 014/015/016's
modal dialogs).

trainingButton (pre-Mission-124 correction) is exercised the same way:
a real click navigates to the real TrainingPage via Sidebar.select_page(),
never creating a Training itself.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QDialog

from src.ui.main_window import MainWindow

_app = QApplication.instance() or QApplication([])


class DashboardPageTest(unittest.TestCase):

    def setUp(self):
        self.window = MainWindow()
        self.addCleanup(self.window.close)

        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    @staticmethod
    def _mock_new_project_dialog(accepted, target_path=None):
        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Accepted if accepted else QDialog.Rejected
        dialog.target_path = target_path
        return dialog

    # --- newProjectButton ---

    def test_new_project_button_accepted_calls_workspace_manager_create(self):
        target_path = Path(self.tmp_dir) / "DashboardProject"
        dialog = self._mock_new_project_dialog(accepted=True, target_path=target_path)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(self.window.workspace_manager, "create") as create_mock:
            self.window.dashboard_page.newProjectButton.click()

            create_mock.assert_called_once_with(target_path)

    def test_new_project_button_cancelled_never_calls_create(self):
        dialog = self._mock_new_project_dialog(accepted=False)

        with patch("src.ui.main_window.NewProjectDialog", return_value=dialog), \
                patch.object(self.window.workspace_manager, "create") as create_mock:
            self.window.dashboard_page.newProjectButton.click()

            create_mock.assert_not_called()

    # --- openProjectButton ---

    def test_open_project_button_calls_workspace_manager_open(self):
        with patch(
            "src.ui.main_window.QFileDialog.getExistingDirectory",
            return_value=self.tmp_dir,
        ), patch.object(self.window.workspace_manager, "open") as open_mock:
            open_mock.return_value = MagicMock()

            self.window.dashboard_page.openProjectButton.click()

            open_mock.assert_called_once_with(self.tmp_dir)

    # --- importImagesButton ---

    def test_import_images_button_actually_adds_the_image_to_the_workspace(self):
        project_folder = Path(self.tmp_dir) / "DashboardImportProject"
        self.window.workspace_manager.create(project_folder)

        image_path = str(Path(self.tmp_dir) / "picture.png")
        Path(image_path).write_bytes(b"fake-png-bytes")

        with patch(
            "src.ui.pages.images_page.QFileDialog.getOpenFileNames",
            return_value=([image_path], ""),
        ), patch("src.ui.pages.images_page.QMessageBox.information"):
            self.window.dashboard_page.importImagesButton.click()

        images = self.window.workspace_manager.current_workspace.images
        self.assertEqual(len(images), 1)
        # Mission 028: add_images() now physically copies the source
        # into <workspace_root>/images/ rather than referencing it.
        self.assertEqual(
            images[0].file_path,
            str(project_folder / "images" / "picture.png"),
        )
        self.assertTrue(Path(image_path).exists(), "external source must remain untouched")

    # --- trainingButton ---
    # Pre-Mission-124 correction: Training is real since Missions 100-105
    # (see test_main_window_training_to_inference.py for the same
    # sidebar.select_page()/stack.currentWidget() assertion pattern
    # reused here), so the button is no longer disabled — it now
    # navigates to TrainingPage exactly like the existing Training->
    # Inference handoff navigates to InferencePage, without ever
    # creating a Training itself.

    def test_training_button_is_enabled(self):
        self.assertTrue(self.window.dashboard_page.trainingButton.isEnabled())

    def test_training_button_has_no_stale_unavailability_tooltip(self):
        tooltip = self.window.dashboard_page.trainingButton.toolTip()

        self.assertEqual(tooltip, "")

    def test_training_button_navigates_to_training_page(self):
        self.assertIsNot(self.window.stack.currentWidget(), self.window.training_page)

        self.window.dashboard_page.trainingButton.click()

        self.assertIs(self.window.stack.currentWidget(), self.window.training_page)

    def test_training_button_never_creates_a_training(self):
        with patch.object(self.window.training_manager, "create") as create_mock:
            self.window.dashboard_page.trainingButton.click()

            create_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
