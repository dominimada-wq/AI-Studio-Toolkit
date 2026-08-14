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
        self.assertEqual(images[0].file_path, image_path)

    # --- trainingButton ---

    def test_training_button_is_disabled(self):
        self.assertFalse(self.window.dashboard_page.trainingButton.isEnabled())

    def test_training_button_tooltip_explains_unavailability(self):
        tooltip = self.window.dashboard_page.trainingButton.toolTip()

        self.assertIn("entraînement", tooltip.lower())
        self.assertIn("non disponible", tooltip.lower())


if __name__ == "__main__":
    unittest.main()
