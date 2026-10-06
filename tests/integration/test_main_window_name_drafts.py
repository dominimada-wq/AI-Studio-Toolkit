"""
Mission 171 — unsaved rename drafts (PromptsPage / LoRAPage / TrainingPage name_edit) through the REAL MainWindow wiring.

Only the interactions that need the real MainWindow live here (toolbar Save, File menu); every other scenario is covered
by page-level fixtures in test_prompt_roundtrip.py / test_lora_roundtrip.py / test_training_roundtrip.py.

Two families, kept apart on purpose:
  - MainWindowNameDraftRegressionTest : failed before the correction (observable behaviour only — runnable on old code).
  - MainWindowNameDraftInvariantTest  : already true before the correction and must stay true.

Environment bound: the focus observations behind these scenarios were made with Qt's offscreen platform plugin and
synthetic QTest mouse events — in that environment the toolbar's QToolButton has focusPolicy NoFocus (a click does not move
the focus, so editingFinished does not run before the save) and opening a menu popup removes the focus from the field
(editingFinished runs before the menu action). They are observations of the tested environment, not a universal statement
about the order of focus events; the assertions below therefore only state what must never happen (a lost draft).

Isolation: LOCALAPPDATA is redirected to a throw-away folder before MainWindow() is built (ApplicationSettings and the
LoRA library never touch the real machine-local files); every Workspace lives in a throw-away folder; dialogs are mocked
and the mocks outlive the window release (cleanups run last-in first-out); the window is closed and released by the fixture.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from src.infrastructure.storage.workspace_storage import WorkspaceStorage
from src.managers.workspace_lifecycle import create_workspace_with_default_character
from src.ui.main_window import MainWindow

_app = QApplication.instance() or QApplication([])


class _MainWindowNameDraftCase(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        env_patch = patch.dict(os.environ, {"LOCALAPPDATA": str(Path(self.tmp_dir) / "localappdata")})
        env_patch.start()
        self.addCleanup(env_patch.stop)

        self.unexpected_dialogs = []
        self._dialog_patches = [
            patch.object(QMessageBox, name, side_effect=self._on_dialog)
            for name in ("critical", "warning", "information", "question")
        ]
        self._dialog_patches.append(patch.object(QMessageBox, "exec", new=lambda box, *a, **k: self._on_dialog(box)))
        for dialog_patch in self._dialog_patches:
            dialog_patch.start()
            self.addCleanup(dialog_patch.stop)

        self.update_name_calls = 0
        self.persist_calls = 0
        self._real_save = WorkspaceStorage.save
        save_patch = patch.object(WorkspaceStorage, "save", new=staticmethod(self._counting_save))
        save_patch.start()
        self.addCleanup(save_patch.stop)

        self.window = MainWindow()
        # Registered after the patches: runs before them (the dialog mocks stay installed until the window is released).
        self.addCleanup(self._release_window)
        self.window.show()
        self.window.activateWindow()
        QApplication.processEvents()

        create_workspace_with_default_character(
            self.window.workspace_manager, self.window.character_manager, Path(self.tmp_dir) / "NameDraftProject"
        )
        window = self.window
        self.prompt_a = window.prompt_manager.create("PromptAlpha")
        window.prompt_manager.create("PromptBeta")
        window.prompt_manager.select(self.prompt_a.prompt_id)
        self.lora_a = window.lora_manager.create("LoraAlpha")
        window.lora_manager.create("LoraBeta")
        window.lora_manager.select(self.lora_a.lora_id)
        dataset = window.dataset_manager.create("Portraits")
        self.training_a = window.training_manager.create("TrainAlpha", dataset.dataset_id)
        window.training_manager.create("TrainBeta", dataset.dataset_id)
        window.training_manager.select(self.training_a.training_id)

        for manager in (window.prompt_manager, window.lora_manager, window.training_manager):
            real_update_name = manager.update_name

            def counted_update_name(*args, _real=real_update_name, **kwargs):
                self.update_name_calls += 1
                return _real(*args, **kwargs)

            manager.update_name = counted_update_name

        self.pages = {
            "prompts": (
                window.prompts_page, window.prompts_page.prompt_list,
                lambda: next(p["name"] for p in window.prompt_manager.list_prompts() if p["prompt_id"] == self.prompt_a.prompt_id),
            ),
            "lora": (
                window.lora_page, window.lora_page.lora_list,
                lambda: next(l["name"] for l in window.lora_manager.list_loras() if l["lora_id"] == self.lora_a.lora_id),
            ),
            "training": (
                window.training_page, window.training_page.training_list,
                lambda: next(t["name"] for t in window.training_manager.list_trainings() if t["training_id"] == self.training_a.training_id),
            ),
        }
        self.reset_counters()

    def tearDown(self):
        self.assertEqual(self.unexpected_dialogs, [], "an unexpected dialog was opened")

    # --- fixture plumbing -------------------------------------------------------------------------------------

    def _on_dialog(self, *args, **kwargs):
        self.unexpected_dialogs.append(args)
        return QMessageBox.Discard

    def _counting_save(self, folder, data):
        self.persist_calls += 1
        return self._real_save(folder, data)

    def _release_window(self):
        self.window.menu.file_menu.hide()
        self.window.close()
        self.window.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QApplication.processEvents()

    def reset_counters(self):
        self.update_name_calls = 0
        self.persist_calls = 0

    # --- real input -------------------------------------------------------------------------------------------

    def open_page_and_type_draft(self, key, text):
        page, _list_widget, _persisted = self.pages[key]
        self.window.stack.setCurrentWidget(page)
        QApplication.processEvents()
        page.name_edit.setFocus()
        QApplication.processEvents()
        self.assertTrue(page.name_edit.hasFocus(), "the name field must really hold the focus")
        page.name_edit.selectAll()
        QTest.keyClicks(page.name_edit, text)
        QApplication.processEvents()
        return page

    def lose_focus(self, key):
        page, list_widget, _persisted = self.pages[key]
        list_widget.setFocus()
        QApplication.processEvents()
        self.assertFalse(page.name_edit.hasFocus())

    def click_toolbar_save(self):
        button = self.window.toolbar.widgetForAction(self.window.toolbar.action_save)
        QTest.mouseClick(button, Qt.LeftButton, Qt.NoModifier, button.rect().center())
        QApplication.processEvents()

    def click_file_menu_save(self):
        menubar = self.window.menu
        QTest.mouseClick(menubar, Qt.LeftButton, Qt.NoModifier, menubar.actionGeometry(menubar.file_menu.menuAction()).center())
        QApplication.processEvents()
        if not menubar.file_menu.isVisible():
            self.skipTest("the File menu popup is not shown in this environment")
        menu = menubar.file_menu
        QTest.mouseClick(menu, Qt.LeftButton, Qt.NoModifier, menu.actionGeometry(menubar.action_save_project).center())
        QApplication.processEvents()


class MainWindowNameDraftRegressionTest(_MainWindowNameDraftCase):
    """Behaviour that failed before Mission 171 (observable behaviour only): a toolbar Save click erased the draft."""

    def _toolbar_save_keeps_the_draft(self, key):
        draft = "Draft Through Toolbar"
        page = self.open_page_and_type_draft(key, draft)
        persisted_name = self.pages[key][2]
        before = persisted_name()
        self.reset_counters()

        self.click_toolbar_save()

        self.assertEqual(self.window.statusBar().currentMessage(), "Projet sauvegardé")
        self.assertGreaterEqual(self.persist_calls, 1)
        self.assertEqual(page.name_edit.text(), draft)

        self.lose_focus(key)

        self.assertEqual(persisted_name(), draft)
        self.assertNotEqual(before, draft)

    def test_toolbar_save_click_keeps_a_prompt_name_draft(self):
        self._toolbar_save_keeps_the_draft("prompts")

    def test_toolbar_save_click_keeps_a_lora_name_draft(self):
        self._toolbar_save_keeps_the_draft("lora")

    def test_toolbar_save_click_keeps_a_training_name_draft(self):
        self._toolbar_save_keeps_the_draft("training")


class MainWindowNameDraftInvariantTest(_MainWindowNameDraftCase):
    """Behaviour already true before Mission 171: File > Sauvegarder never loses a name draft (environment-bounded)."""

    def _file_menu_save_never_loses_the_draft(self, key):
        draft = "Draft Through Menu"
        page = self.open_page_and_type_draft(key, draft)
        persisted_name = self.pages[key][2]
        self.reset_counters()

        self.click_file_menu_save()

        self.assertEqual(self.window.statusBar().currentMessage(), "Projet sauvegardé")
        self.assertEqual(page.name_edit.text(), draft)

        self.lose_focus(key)

        self.assertEqual(persisted_name(), draft)
        self.assertEqual(page.name_edit.text(), draft)

    def test_file_menu_save_never_loses_a_prompt_name_draft(self):
        self._file_menu_save_never_loses_the_draft("prompts")

    def test_file_menu_save_never_loses_a_lora_name_draft(self):
        self._file_menu_save_never_loses_the_draft("lora")

    def test_file_menu_save_never_loses_a_training_name_draft(self):
        self._file_menu_save_never_loses_the_draft("training")


if __name__ == "__main__":
    unittest.main()
