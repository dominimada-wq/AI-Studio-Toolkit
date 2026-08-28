"""
Real-widget coverage for ImagesPage: the existing "Importer des
images" flow (Workspace.images, unchanged) plus Mission 015's enlarged
preview wiring (double-click and the "Voir en grand" button, both
opening the same ImagePreviewDialog). ImagePreviewDialog.exec() is
patched throughout — a real modal exec() would block the test process
(same lesson as Mission 014's QMessageBox hang) — these tests validate
the wiring, not the dialog itself (see test_image_preview_dialog.py
for that).

Mission 019 extends this file with the icon-mode gallery: thumbnails,
short filename label, full-path tooltip, and Qt.UserRole as the sole
source of truth for file_path (item.text() is presentation only, never
read by _on_item_double_clicked/_on_enlarge_clicked anymore).

Mission 028: WorkspaceManager.add_images() now physically copies each
source into <workspace_root>/images/ instead of merely referencing it
— every fixture below distinguishes the external source it hands to
add_images() from the internal copy path the app actually renders
(read back from Workspace.images after the call), since the two are
no longer the same string. Tests that specifically exercise a
file the widget cannot load (missing/invalid content) now write a
real-but-unloadable file rather than a genuinely non-existent path —
add_images() itself now requires the source to exist (Mission 028
copies it), so a source that was never on disk can no longer become a
persisted Image at all; a real file with unparsable bytes exercises
the exact same QPixmap-load-failure/fallback-icon path.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QListWidget

from src.core.event_bus import EventBus
from src.domain.image import Image
from src.infrastructure.storage.workspace_storage import WorkspaceStorage, WorkspaceStorageError
from src.managers.character_manager import CharacterManager
from src.managers.dataset_manager import DatasetManager
from src.managers.workspace_manager import WorkspaceManager, WORKSPACE_CREATED, WORKSPACE_SAVED
from src.ui.pages.images_page import ImagesPage

_app = QApplication.instance() or QApplication([])


def _make_png(path: str, width: int = 4, height: int = 4) -> None:
    pixmap = QPixmap(width, height)
    pixmap.fill()
    assert pixmap.save(path, "PNG")


class ImagesPageTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "ImagesProject"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.workspace_manager.create(self.folder)

        self.page = ImagesPage(self.workspace_manager)

        for event_name in (WORKSPACE_CREATED, WORKSPACE_SAVED):
            self.event_bus.subscribe(event_name, self.page.update_images)

        # self.image_path is the external source handed to add_images();
        # self.internal_image_path is the internal copy the app actually
        # renders afterward (Mission 028) — the two are deliberately
        # different paths on disk.
        self.image_path = str(Path(self.tmp_dir) / "existing.png")
        Path(self.image_path).write_bytes(b"fake-png-bytes")
        self.workspace_manager.add_images([self.image_path])
        self.internal_image_path = self.workspace_manager.current_workspace.images[0].file_path

    # --- Selection -> button state ---

    def test_enlarge_button_disabled_without_selection(self):
        self.assertIsNone(self.page.list_widget.currentItem())
        self.assertFalse(self.page.enlarge_button.isEnabled())

    def test_enlarge_button_enabled_once_an_item_is_selected(self):
        self.page.list_widget.setCurrentRow(0)

        self.assertTrue(self.page.enlarge_button.isEnabled())

    # --- Button / double-click both open the same dialog ---

    @patch("src.ui.pages.images_page.ImagePreviewDialog")
    def test_enlarge_button_opens_the_selected_file_path(self, mock_dialog_cls):
        self.page.list_widget.setCurrentRow(0)

        self.page.enlarge_button.click()

        mock_dialog_cls.assert_called_once_with(self.internal_image_path, parent=self.page)
        mock_dialog_cls.return_value.exec.assert_called_once()

    @patch("src.ui.pages.images_page.ImagePreviewDialog")
    def test_double_click_opens_the_same_file_path(self, mock_dialog_cls):
        item = self.page.list_widget.item(0)

        self.page._on_item_double_clicked(item)

        mock_dialog_cls.assert_called_once_with(self.internal_image_path, parent=self.page)
        mock_dialog_cls.return_value.exec.assert_called_once()

    @patch("src.ui.pages.images_page.ImagePreviewDialog")
    def test_enlarge_button_with_no_selection_is_a_no_op(self, mock_dialog_cls):
        self.page.enlarge_button.click()

        mock_dialog_cls.assert_not_called()

    # --- Missing file: dialog is still opened, no Domain mutation ---

    @patch("src.ui.pages.images_page.ImagePreviewDialog")
    def test_missing_file_opens_dialog_without_mutating_domain(self, mock_dialog_cls):
        # Deletes the internal copy (the file the app actually
        # references after import) — deleting self.image_path (the
        # external source) would no longer be relevant post-Mission-028,
        # since the app never depends on it again once copied.
        Path(self.internal_image_path).unlink()
        self.page.list_widget.setCurrentRow(0)

        self.page.enlarge_button.click()

        mock_dialog_cls.assert_called_once_with(self.internal_image_path, parent=self.page)
        self.assertEqual(len(self.workspace_manager.current_workspace.images), 1)
        self.assertEqual(
            self.workspace_manager.current_workspace.images[0].file_path,
            self.internal_image_path,
        )

    # --- Consultation is read-only ---

    # --- Refresh (WORKSPACE_SAVED) preserves a still-valid selection (Mission 082) ---

    def test_refresh_after_adding_another_image_preserves_previous_selection(self):
        # Mission 082: a WORKSPACE_SAVED rebuild (here, another import)
        # must preserve a selection whose underlying item still exists —
        # this used to be silently wiped by every rebuild, even one
        # unrelated to the selected item itself. Superseded the previous
        # (opposite) assertion this test made pre-Mission-082.
        self.page.list_widget.setCurrentRow(0)
        self.assertTrue(self.page.enlarge_button.isEnabled())

        second_path = str(Path(self.tmp_dir) / "second.png")
        Path(second_path).write_bytes(b"fake-png-bytes-2")
        self.workspace_manager.add_images([second_path])

        self.assertIsNotNone(self.page.list_widget.currentItem())
        self.assertEqual(self.page.list_widget.currentItem().data(Qt.UserRole), self.internal_image_path)
        self.assertTrue(self.page.enlarge_button.isEnabled())
        # The newly added image must never be selected artificially.
        self.assertEqual(len(self.page.list_widget.selectedItems()), 1)

    def test_refresh_with_no_prior_selection_leaves_button_disabled(self):
        self.assertFalse(self.page.enlarge_button.isEnabled())

        second_path = str(Path(self.tmp_dir) / "second_b.png")
        Path(second_path).write_bytes(b"fake-png-bytes-2")
        self.workspace_manager.add_images([second_path])

        self.assertIsNone(self.page.list_widget.currentItem())
        self.assertFalse(self.page.enlarge_button.isEnabled())

    # Mission 082: test_selecting_again_after_refresh_re_enables_the_button
    # removed — it exercised re-selecting after a refresh-induced wipe
    # that no longer happens; superseded by
    # test_refresh_after_adding_another_image_preserves_previous_selection
    # above and by ImagesPageSelectionPreservationTest below.

    # --- Repeated consultation ---

    @patch("src.ui.pages.images_page.ImagePreviewDialog")
    def test_enlarge_button_opened_twice_in_a_row_opens_dialog_each_time(self, mock_dialog_cls):
        self.page.list_widget.setCurrentRow(0)

        self.page.enlarge_button.click()
        self.page.enlarge_button.click()

        self.assertEqual(mock_dialog_cls.call_count, 2)
        mock_dialog_cls.assert_called_with(self.internal_image_path, parent=self.page)
        self.assertEqual(mock_dialog_cls.return_value.exec.call_count, 2)
        self.assertEqual(len(self.workspace_manager.current_workspace.images), 1)

    @patch("src.ui.pages.images_page.ImagePreviewDialog")
    def test_consultation_never_calls_add_images_or_save(self, mock_dialog_cls):
        with patch.object(
            self.workspace_manager, "add_images", wraps=self.workspace_manager.add_images
        ) as add_images_spy, patch.object(
            self.workspace_manager, "save", wraps=self.workspace_manager.save
        ) as save_spy:
            self.page.list_widget.setCurrentRow(0)
            self.page.enlarge_button.click()

            item = self.page.list_widget.item(0)
            self.page._on_item_double_clicked(item)

            add_images_spy.assert_not_called()
            save_spy.assert_not_called()

        self.assertEqual(len(self.workspace_manager.current_workspace.images), 1)

    # --- Mission 019: icon-mode gallery ---

    def test_list_widget_uses_icon_mode(self):
        self.assertEqual(self.page.list_widget.viewMode(), QListWidget.IconMode)

    def test_valid_image_item_has_icon_short_label_tooltip_and_user_role(self):
        real_image_path = str(Path(self.tmp_dir) / "real.png")
        _make_png(real_image_path)

        self.workspace_manager.add_images([real_image_path])
        internal_real_path = self.workspace_manager.current_workspace.images[-1].file_path

        item = self.page.list_widget.item(self.page.list_widget.count() - 1)

        self.assertFalse(item.icon().isNull())
        self.assertEqual(item.text(), "real.png")
        self.assertEqual(item.toolTip(), internal_real_path)
        self.assertEqual(item.data(Qt.UserRole), internal_real_path)

    def test_missing_file_item_still_created_with_fallback_icon_and_user_role(self):
        # Mission 028: add_images() now requires the source to exist on
        # disk (it is physically copied) — a genuinely non-existent
        # source can no longer become a persisted Image at all. A real
        # file with unparsable content exercises the exact same
        # QPixmap-load-failure/fallback-icon path a missing file used
        # to, without contradicting the new copy contract.
        broken_source = str(Path(self.tmp_dir) / "does_not_exist.png")
        Path(broken_source).write_bytes(b"not a real png")

        self.workspace_manager.add_images([broken_source])
        internal_path = self.workspace_manager.current_workspace.images[-1].file_path

        # Mission 048: the gallery is now sorted by filename, so the
        # just-added item is no longer guaranteed to land at the last
        # position ("does_not_exist.png" sorts before "existing.png") —
        # located by identity (Qt.UserRole) instead, same pattern as
        # test_delete_confirmed_for_external_image_removes_reference_but_keeps_file
        # below.
        item = next(
            self.page.list_widget.item(i)
            for i in range(self.page.list_widget.count())
            if self.page.list_widget.item(i).data(Qt.UserRole) == internal_path
        )

        self.assertIsNotNone(item)
        self.assertFalse(item.icon().isNull())
        self.assertEqual(item.text(), "does_not_exist.png")
        self.assertEqual(item.toolTip(), internal_path)
        self.assertEqual(item.data(Qt.UserRole), internal_path)

    def test_invalid_non_image_file_item_still_created_with_fallback_icon(self):
        invalid_path = str(Path(self.tmp_dir) / "invalid.png")
        Path(invalid_path).write_bytes(b"this is definitely not a png")

        self.workspace_manager.add_images([invalid_path])
        internal_path = self.workspace_manager.current_workspace.images[-1].file_path

        item = self.page.list_widget.item(self.page.list_widget.count() - 1)

        self.assertIsNotNone(item)
        self.assertFalse(item.icon().isNull())
        self.assertEqual(item.data(Qt.UserRole), internal_path)

    def test_missing_file_gallery_item_still_opens_preview_and_supports_selection(self):
        broken_source = str(Path(self.tmp_dir) / "gone.png")
        Path(broken_source).write_bytes(b"not a real png either")

        self.workspace_manager.add_images([broken_source])
        internal_path = self.workspace_manager.current_workspace.images[-1].file_path

        last_row = self.page.list_widget.count() - 1
        self.page.list_widget.setCurrentRow(last_row)

        self.assertTrue(self.page.enlarge_button.isEnabled())

        with patch("src.ui.pages.images_page.ImagePreviewDialog") as mock_dialog_cls:
            self.page.enlarge_button.click()
            mock_dialog_cls.assert_called_once_with(internal_path, parent=self.page)

    def test_multiple_images_each_item_has_its_own_user_role(self):
        second_path = str(Path(self.tmp_dir) / "multi_second.png")
        third_path = str(Path(self.tmp_dir) / "multi_third.png")
        _make_png(second_path)
        _make_png(third_path)

        self.workspace_manager.add_images([second_path, third_path])
        internal_paths = {
            image.file_path for image in self.workspace_manager.current_workspace.images
        }

        roles = {
            self.page.list_widget.item(i).data(Qt.UserRole)
            for i in range(self.page.list_widget.count())
        }

        self.assertEqual(roles, internal_paths)

    # --- Mission 046: "Supprimer" ---

    def _confirm_delete(self, accept: bool):
        """
        Patches QMessageBox so that delete_selected_images()'s
        confirmation dialog is answered programmatically — accept=True
        clicks the labeled accept button, accept=False clicks
        "Annuler" — without ever showing a real modal.
        """
        patcher = patch("src.ui.pages.images_page.QMessageBox")
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

    def test_list_widget_uses_extended_selection(self):
        self.assertEqual(self.page.list_widget.selectionMode(), QListWidget.ExtendedSelection)

    def test_delete_button_disabled_without_selection(self):
        self.assertFalse(self.page.delete_button.isEnabled())

    def test_delete_button_enabled_with_single_selection(self):
        self.page.list_widget.item(0).setSelected(True)

        self.assertTrue(self.page.delete_button.isEnabled())

    def test_delete_button_enabled_with_multiple_selection(self):
        second_path = str(Path(self.tmp_dir) / "second.png")
        _make_png(second_path)
        self.workspace_manager.add_images([second_path])

        self.page.list_widget.item(0).setSelected(True)
        self.page.list_widget.item(1).setSelected(True)

        self.assertTrue(self.page.delete_button.isEnabled())

    def test_delete_with_no_selection_is_a_no_op(self):
        mock_cls = self._confirm_delete(accept=True)

        self.page.delete_selected_images()

        mock_cls.assert_not_called()

    def test_delete_confirmed_for_internal_image_deletes_file_and_removes_reference(self):
        self._confirm_delete(accept=True)
        self.page.list_widget.item(0).setSelected(True)

        self.page.delete_selected_images()

        self.assertFalse(Path(self.internal_image_path).exists())
        self.assertEqual(self.workspace_manager.current_workspace.images, [])
        # Refreshed solely via the pre-existing WORKSPACE_SAVED wiring —
        # no manual update_images() call anywhere in this test.
        self.assertEqual(self.page.list_widget.count(), 0)

    def test_delete_cancelled_leaves_everything_unchanged(self):
        self._confirm_delete(accept=False)
        self.page.list_widget.item(0).setSelected(True)

        self.page.delete_selected_images()

        self.assertTrue(Path(self.internal_image_path).exists())
        self.assertEqual(len(self.workspace_manager.current_workspace.images), 1)
        self.assertEqual(self.page.list_widget.count(), 1)

    def test_delete_confirmed_for_external_image_removes_reference_but_keeps_file(self):
        external_path = str(Path(self.tmp_dir) / "outside.png")
        Path(external_path).write_bytes(b"external-bytes")
        self.workspace_manager.current_workspace.images.append(
            Image(image_id="ext-1", file_path=external_path)
        )
        self.workspace_manager.save()
        self.page.update_images(self.workspace_manager.current_workspace.to_dict())

        self._confirm_delete(accept=True)
        item = next(
            self.page.list_widget.item(i)
            for i in range(self.page.list_widget.count())
            if self.page.list_widget.item(i).data(Qt.UserRole) == external_path
        )
        item.setSelected(True)

        self.page.delete_selected_images()

        self.assertTrue(Path(external_path).exists())
        internal_paths = {
            image.file_path for image in self.workspace_manager.current_workspace.images
        }
        self.assertNotIn(external_path, internal_paths)

    def test_delete_mixed_selection_deletes_internal_and_only_removes_external_reference(self):
        external_path = str(Path(self.tmp_dir) / "outside_mixed.png")
        Path(external_path).write_bytes(b"external-bytes")
        self.workspace_manager.current_workspace.images.append(
            Image(image_id="ext-2", file_path=external_path)
        )
        self.workspace_manager.save()
        self.page.update_images(self.workspace_manager.current_workspace.to_dict())

        self._confirm_delete(accept=True)
        for i in range(self.page.list_widget.count()):
            self.page.list_widget.item(i).setSelected(True)

        self.page.delete_selected_images()

        self.assertFalse(Path(self.internal_image_path).exists())
        self.assertTrue(Path(external_path).exists())
        self.assertEqual(self.workspace_manager.current_workspace.images, [])

    def test_delete_blocked_when_image_is_referenced_by_a_dataset(self):
        # CharacterManager only auto-creates the principal Character in
        # response to WORKSPACE_CREATED — already published by setUp()
        # before this Manager existed, so the Character is created
        # explicitly here instead of relying on that auto-creation.
        character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset_manager = DatasetManager(
            character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)
        dataset_manager.add_images([self.internal_image_path])

        mock_cls = self._confirm_delete(accept=True)
        self.page.list_widget.item(0).setSelected(True)

        self.page.delete_selected_images()

        mock_cls.warning.assert_called_once()
        mock_cls.return_value.exec.assert_not_called()
        self.assertTrue(Path(self.internal_image_path).exists())
        self.assertEqual(len(self.workspace_manager.current_workspace.images), 1)
        self.assertEqual(len(dataset_manager.active_dataset.images), 1)

    # --- Mission 066: persistence-first remove_images() failure modes ---

    def test_delete_confirmed_but_save_fails_shows_error_and_deletes_nothing(self):
        mock_cls = self._confirm_delete(accept=True)
        self.page.list_widget.item(0).setSelected(True)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            self.page.delete_selected_images()

        mock_cls.critical.assert_called_once()
        mock_cls.warning.assert_not_called()
        self.assertTrue(Path(self.internal_image_path).exists())
        self.assertEqual(len(self.workspace_manager.current_workspace.images), 1)
        # No WORKSPACE_SAVED was published — the list was never rebuilt.
        self.assertEqual(self.page.list_widget.count(), 1)

    def test_delete_confirmed_but_unlink_fails_shows_warning_and_still_persists_removal(self):
        mock_cls = self._confirm_delete(accept=True)
        self.page.list_widget.item(0).setSelected(True)

        real_unlink = Path.unlink

        def flaky_unlink(self_path, *args, **kwargs):
            if self_path == Path(self.internal_image_path):
                raise PermissionError("simulated: locked by another process")
            return real_unlink(self_path, *args, **kwargs)

        with patch.object(Path, "unlink", flaky_unlink):
            self.page.delete_selected_images()

        mock_cls.warning.assert_called_once()
        mock_cls.critical.assert_not_called()
        # unlink() failed -> the file is orphaned, still physically present...
        self.assertTrue(Path(self.internal_image_path).exists())
        # ...but the project no longer references it, and the gallery
        # reflects that persisted removal via the existing WORKSPACE_SAVED
        # wiring, exactly as a fully successful deletion would.
        self.assertEqual(self.workspace_manager.current_workspace.images, [])
        self.assertEqual(self.page.list_widget.count(), 0)


class ImagesPageCollisionDialogTest(unittest.TestCase):
    """
    Mission 028 second smoke test: import_images() no longer lets a
    naming collision resolve silently — it must show
    ImportCollisionDialog exactly once per import operation (never
    once per colliding file) whenever
    WorkspaceManager.preview_collisions() finds anything, and never at
    all otherwise. ImportCollisionDialog.exec() is patched throughout
    — a real modal exec() would block the test process (same lesson as
    every other dialog in this project).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "ImagesProject"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.workspace_manager.create(self.folder)

        self.page = ImagesPage(self.workspace_manager)
        for event_name in (WORKSPACE_CREATED, WORKSPACE_SAVED):
            self.event_bus.subscribe(event_name, self.page.update_images)

        self.external_dir = Path(self.tmp_dir) / "External"
        self.external_dir.mkdir()

    def _external(self, name, content=b"fake-bytes"):
        path = self.external_dir / name
        path.write_bytes(content)
        return str(path)

    def _select(self, files):
        return patch(
            "src.ui.pages.images_page.QFileDialog.getOpenFileNames",
            return_value=(files, ""),
        )

    def test_no_dialog_shown_when_nothing_collides(self):
        with self._select([self._external("photo.png")]), \
                patch("src.ui.pages.images_page.ImportCollisionDialog") as dialog_cls, \
                patch("src.ui.pages.images_page.QMessageBox.information"):
            self.page.import_images()

            dialog_cls.assert_not_called()

        self.assertEqual(len(self.workspace_manager.current_workspace.images), 1)

    def test_dialog_shown_exactly_once_for_multiple_collisions(self):
        # Two independent collisions in the same batch must still
        # produce a single dialog, not one per colliding file.
        self.workspace_manager.add_images([self._external("a.png"), self._external("b.png")])
        colliding_a = self._external("a.png", b"different-a")
        colliding_b = self._external("b.png", b"different-b")

        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Rejected
        with self._select([colliding_a, colliding_b]), \
                patch(
                    "src.ui.pages.images_page.ImportCollisionDialog", return_value=dialog
                ) as dialog_cls:
            self.page.import_images()

            dialog_cls.assert_called_once()

    def test_cancelling_the_dialog_aborts_the_whole_import(self):
        self.workspace_manager.add_images([self._external("photo.png")])
        colliding_source = self._external("photo.png", b"different")

        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Rejected
        with self._select([colliding_source]), \
                patch("src.ui.pages.images_page.ImportCollisionDialog", return_value=dialog):
            self.page.import_images()

        self.assertEqual(len(self.workspace_manager.current_workspace.images), 1)

    def test_rename_decision_is_applied_verbatim(self):
        self.workspace_manager.add_images([self._external("photo.png")])
        colliding_source = self._external("photo.png", b"different")

        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Accepted
        dialog.decisions.return_value = {colliding_source: "my_custom_name.png"}
        with self._select([colliding_source]), \
                patch("src.ui.pages.images_page.ImportCollisionDialog", return_value=dialog), \
                patch("src.ui.pages.images_page.QMessageBox.information"):
            self.page.import_images()

        images = self.workspace_manager.current_workspace.images
        self.assertEqual(len(images), 2)
        self.assertEqual(
            images[-1].file_path, str(self.folder / "images" / "my_custom_name.png")
        )

    def test_skip_decision_never_imports_that_file(self):
        self.workspace_manager.add_images([self._external("photo.png")])
        colliding_source = self._external("photo.png", b"different")

        dialog = MagicMock()
        dialog.exec.return_value = QDialog.Accepted
        dialog.decisions.return_value = {colliding_source: None}
        with self._select([colliding_source]), \
                patch("src.ui.pages.images_page.ImportCollisionDialog", return_value=dialog), \
                patch("src.ui.pages.images_page.QMessageBox.information") as info_mock:
            self.page.import_images()

        self.assertEqual(len(self.workspace_manager.current_workspace.images), 1)
        info_mock.assert_called_once()
        message = info_mock.call_args.args[2]
        self.assertIn("Aucune nouvelle image importée", message)

    def test_bypassing_the_ui_still_falls_back_to_the_silent_non_destructive_auto_suffix(self):
        # A caller that bypasses the UI entirely (tests, programmatic
        # use) still gets the original silent auto-suffix from
        # WorkspaceStorage.copy_into_workspace() itself — the
        # architect's explicit instruction was to keep this primitive,
        # only the UI-driven import flow now asks first.
        self.workspace_manager.add_images([self._external("photo.png")])
        self.workspace_manager.add_images([self._external("photo.png", b"other")])

        self.assertTrue((self.folder / "images" / "photo_1.png").exists())


class ImagesPageImportPersistenceFailureTest(unittest.TestCase):
    """
    Mission 067: add_images() now rollbacks Workspace.images and
    compensates any newly created copy on a save() failure — this
    class covers import_images() intercepting that WorkspaceManagerError
    instead of letting it propagate unhandled.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "ImagesProject"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.workspace_manager.create(self.folder)

        self.page = ImagesPage(self.workspace_manager)
        for event_name in (WORKSPACE_CREATED, WORKSPACE_SAVED):
            self.event_bus.subscribe(event_name, self.page.update_images)

        self.external_dir = Path(self.tmp_dir) / "External"
        self.external_dir.mkdir()
        self.source = str(self.external_dir / "photo.png")
        Path(self.source).write_bytes(b"fake-bytes")

    def _select(self):
        return patch(
            "src.ui.pages.images_page.QFileDialog.getOpenFileNames",
            return_value=([self.source], ""),
        )

    def test_save_failure_shows_error_and_imports_nothing(self):
        with self._select(), \
                patch("src.ui.pages.images_page.QMessageBox") as mock_cls, \
                patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            self.page.import_images()

        mock_cls.critical.assert_called_once()
        self.assertEqual(self.workspace_manager.current_workspace.images, [])
        self.assertFalse((self.folder / "images" / "photo.png").exists())
        self.assertTrue(Path(self.source).exists())
        self.assertEqual(self.page.list_widget.count(), 0)

    def test_retry_after_save_failure_actually_imports(self):
        with self._select(), \
                patch("src.ui.pages.images_page.QMessageBox"), \
                patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            self.page.import_images()

        with self._select(), patch("src.ui.pages.images_page.QMessageBox.information"):
            self.page.import_images()

        self.assertEqual(len(self.workspace_manager.current_workspace.images), 1)
        self.assertEqual(self.page.list_widget.count(), 1)


class ImagesPageGallerySortTest(unittest.TestCase):
    """
    Mission 048: the gallery is now sorted by Path(file_path).name,
    case-insensitively, always on — purely a Presentation-layer display
    order, Workspace.images itself is never reordered.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "ImagesProject"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.workspace_manager.create(self.folder)

        self.page = ImagesPage(self.workspace_manager)

        for event_name in (WORKSPACE_CREATED, WORKSPACE_SAVED):
            self.event_bus.subscribe(event_name, self.page.update_images)

        self.workspace_manager.current_workspace.images.clear()

    def _add(self, name: str, content: bytes = b"fake-png-bytes") -> str:
        path = str(Path(self.tmp_dir) / name)
        Path(path).write_bytes(content)
        self.workspace_manager.add_images([path])
        return self.workspace_manager.current_workspace.images[-1].file_path

    def test_gallery_sorted_alphabetically_by_filename(self):
        self._add("zebra.png")
        self._add("apple.png")
        self._add("mango.png")

        texts = [self.page.list_widget.item(i).text() for i in range(self.page.list_widget.count())]

        self.assertEqual(texts, ["apple.png", "mango.png", "zebra.png"])

    def test_sort_is_case_insensitive(self):
        self._add("Banana.png")
        self._add("apple.png")
        self._add("Cherry.png")

        texts = [self.page.list_widget.item(i).text() for i in range(self.page.list_widget.count())]

        self.assertEqual(texts, ["apple.png", "Banana.png", "Cherry.png"])

    def test_sort_is_stable_for_equal_keys_after_case_normalization(self):
        # Two files sharing the exact same displayed name (case included),
        # living under different source folders — the same sort key after
        # normalization must never reorder them relative to each other.
        first = str(Path(self.tmp_dir) / "dirA" / "shot.png")
        second = str(Path(self.tmp_dir) / "dirB" / "shot.png")
        Path(first).parent.mkdir(parents=True, exist_ok=True)
        Path(second).parent.mkdir(parents=True, exist_ok=True)
        Path(first).write_bytes(b"first")
        Path(second).write_bytes(b"second")

        self.workspace_manager.add_images([first])
        internal_first = self.workspace_manager.current_workspace.images[-1].file_path
        self.workspace_manager.add_images([second])
        internal_second = self.workspace_manager.current_workspace.images[-1].file_path

        roles = [self.page.list_widget.item(i).data(Qt.UserRole) for i in range(self.page.list_widget.count())]

        self.assertEqual(roles, [internal_first, internal_second])

    def test_domain_order_unchanged_after_display_sort(self):
        self._add("zebra.png")
        self._add("apple.png")

        # Workspace.images (Domain) must keep insertion order regardless
        # of the sorted display order in list_widget.
        domain_names = [
            Path(image.file_path).name
            for image in self.workspace_manager.current_workspace.images
        ]
        self.assertEqual(domain_names, ["zebra.png", "apple.png"])

        displayed_names = [self.page.list_widget.item(i).text() for i in range(self.page.list_widget.count())]
        self.assertEqual(displayed_names, ["apple.png", "zebra.png"])

    def test_gallery_resorts_after_workspace_saved_refresh(self):
        self._add("zebra.png")

        texts_before = [self.page.list_widget.item(i).text() for i in range(self.page.list_widget.count())]
        self.assertEqual(texts_before, ["zebra.png"])

        # A later WORKSPACE_SAVED (triggered here by add_images()) must
        # re-sort the whole gallery, not just append the new item.
        self._add("apple.png")

        texts_after = [self.page.list_widget.item(i).text() for i in range(self.page.list_widget.count())]
        self.assertEqual(texts_after, ["apple.png", "zebra.png"])

    def test_selection_and_preview_still_work_after_reordering(self):
        self._add("existing.png")
        internal_first_alpha = self._add("aardvark.png")

        # "aardvark.png" sorts before "existing.png" — its display
        # position (0) now differs from its insertion position (1).
        texts = [self.page.list_widget.item(i).text() for i in range(self.page.list_widget.count())]
        self.assertEqual(texts, ["aardvark.png", "existing.png"])

        self.page.list_widget.setCurrentRow(0)
        with patch("src.ui.pages.images_page.ImagePreviewDialog") as mock_dialog_cls:
            self.page.enlarge_button.click()

        mock_dialog_cls.assert_called_once_with(internal_first_alpha, parent=self.page)

    # --- Mission 049: "Date du fichier (plus récent d'abord)" ---

    def _set_mtime(self, path: str, timestamp: float) -> None:
        os.utime(path, (timestamp, timestamp))

    def test_date_sort_orders_by_mtime_descending(self):
        old_path = self._add("old.png")
        self._set_mtime(old_path, 1000)
        new_path = self._add("new.png")
        self._set_mtime(new_path, 2000)

        self.page.sort_combo.setCurrentIndex(1)

        texts = [self.page.list_widget.item(i).text() for i in range(self.page.list_widget.count())]
        self.assertEqual(texts, ["new.png", "old.png"])

    def test_date_sort_works_for_external_file(self):
        internal_path = self._add("internal.png")
        self._set_mtime(internal_path, 1000)

        external_path = str(Path(self.tmp_dir) / "external.png")
        _make_png(external_path)
        self._set_mtime(external_path, 2000)
        self.workspace_manager.current_workspace.images.append(
            Image(image_id="ext-1", file_path=external_path)
        )
        self.workspace_manager.save()

        self.page.sort_combo.setCurrentIndex(1)

        texts = [self.page.list_widget.item(i).text() for i in range(self.page.list_widget.count())]
        self.assertEqual(texts, ["external.png", "internal.png"])

    def test_missing_file_sorts_last_in_date_mode(self):
        present_path = self._add("present.png")
        self._set_mtime(present_path, 1000)

        missing_path = str(Path(self.tmp_dir) / "missing.png")
        self.workspace_manager.current_workspace.images.append(
            Image(image_id="missing-1", file_path=missing_path)
        )
        self.workspace_manager.save()

        self.page.sort_combo.setCurrentIndex(1)

        texts = [self.page.list_widget.item(i).text() for i in range(self.page.list_widget.count())]
        self.assertEqual(texts, ["present.png", "missing.png"])

    def test_multiple_missing_files_preserve_relative_order_in_date_mode(self):
        missing_a = str(Path(self.tmp_dir) / "missing_a.png")
        missing_b = str(Path(self.tmp_dir) / "missing_b.png")
        self.workspace_manager.current_workspace.images.append(
            Image(image_id="ma", file_path=missing_a)
        )
        self.workspace_manager.current_workspace.images.append(
            Image(image_id="mb", file_path=missing_b)
        )
        self.workspace_manager.save()

        self.page.sort_combo.setCurrentIndex(1)

        texts = [self.page.list_widget.item(i).text() for i in range(self.page.list_widget.count())]
        self.assertEqual(texts, ["missing_a.png", "missing_b.png"])

    def test_equal_mtime_files_preserve_relative_order_in_date_mode(self):
        first = self._add("first.png")
        second = self._add("second.png")
        self._set_mtime(first, 5000)
        self._set_mtime(second, 5000)

        self.page.sort_combo.setCurrentIndex(1)

        texts = [self.page.list_widget.item(i).text() for i in range(self.page.list_widget.count())]
        self.assertEqual(texts, ["first.png", "second.png"])

    def test_switching_criterion_back_to_name_restores_name_order(self):
        self._add("zebra.png")
        self._add("apple.png")

        self.page.sort_combo.setCurrentIndex(1)
        self.page.sort_combo.setCurrentIndex(0)

        texts = [self.page.list_widget.item(i).text() for i in range(self.page.list_widget.count())]
        self.assertEqual(texts, ["apple.png", "zebra.png"])

    def test_sort_criterion_survives_workspace_saved_refresh(self):
        old_path = self._add("old.png")
        self._set_mtime(old_path, 1000)

        self.page.sort_combo.setCurrentIndex(1)

        new_path = self._add("new.png")
        self._set_mtime(new_path, 2000)

        # add_images() triggers WORKSPACE_SAVED -> update_images() again;
        # the combo must still read "date", never silently reset.
        self.assertEqual(self.page.sort_combo.currentData(), "date")
        texts = [self.page.list_widget.item(i).text() for i in range(self.page.list_widget.count())]
        self.assertEqual(texts, ["new.png", "old.png"])

    def test_domain_order_unchanged_in_date_mode(self):
        self._add("zebra.png")
        self._add("apple.png")

        self.page.sort_combo.setCurrentIndex(1)

        domain_names = [
            Path(image.file_path).name
            for image in self.workspace_manager.current_workspace.images
        ]
        self.assertEqual(domain_names, ["zebra.png", "apple.png"])


class ImagesPageSelectionPreservationTest(unittest.TestCase):
    """
    Mission 082: list_widget.selectedItems()/currentItem() must survive
    a rebuild (update_images(), subscribed to WORKSPACE_CREATED/OPENED/
    SAVED/CLOSED/RENAMED) whenever the underlying item is still present
    — identity is Qt.UserRole (the internal file_path). No cross-
    Workspace guard is needed here (each Workspace copies its images
    under its own root, see images_page.py's own comment) — unlike
    DatasetsPage.images_list/LoRAPage.files_list, both covered
    separately in their own test files.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "ImagesProject"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.workspace_manager.create(self.folder)

        self.page = ImagesPage(self.workspace_manager)

        for event_name in (WORKSPACE_CREATED, WORKSPACE_SAVED):
            self.event_bus.subscribe(event_name, self.page.update_images)

        self.paths = []
        for name in ("a.png", "b.png", "c.png"):
            path = str(Path(self.tmp_dir) / name)
            Path(path).write_bytes(b"fake-png-bytes")
            self.workspace_manager.add_images([path])
            self.paths.append(self.workspace_manager.current_workspace.images[-1].file_path)

    def _select(self, *paths, current=None):
        for i in range(self.page.list_widget.count()):
            item = self.page.list_widget.item(i)
            if item.data(Qt.UserRole) in paths:
                item.setSelected(True)
            if current is not None and item.data(Qt.UserRole) == current:
                self.page.list_widget.setCurrentItem(item)

    def _selected_paths(self):
        return {item.data(Qt.UserRole) for item in self.page.list_widget.selectedItems()}

    def test_refresh_without_content_change_preserves_full_selection(self):
        self._select(self.paths[0], self.paths[1], current=self.paths[0])

        self.workspace_manager.save()  # unrelated refresh — no content change

        self.assertEqual(self._selected_paths(), {self.paths[0], self.paths[1]})

    def test_restoring_current_item_does_not_disturb_the_restored_selection(self):
        # Mission 082: the exact regression QItemSelectionModel.NoUpdate
        # is meant to prevent — a plain setCurrentItem() call would
        # otherwise collapse the just-restored multi-selection.
        self._select(self.paths[0], self.paths[1], self.paths[2], current=self.paths[0])

        self.workspace_manager.save()

        self.assertEqual(self._selected_paths(), {self.paths[0], self.paths[1], self.paths[2]})
        self.assertIsNotNone(self.page.list_widget.currentItem())
        self.assertEqual(self.page.list_widget.currentItem().data(Qt.UserRole), self.paths[0])

    def test_current_item_restored_when_it_still_exists(self):
        self._select(self.paths[0], current=self.paths[0])

        self.workspace_manager.save()

        self.assertIsNotNone(self.page.list_widget.currentItem())
        self.assertEqual(self.page.list_widget.currentItem().data(Qt.UserRole), self.paths[0])
        self.assertTrue(self.page.enlarge_button.isEnabled())

    def test_adding_a_new_image_preserves_previous_selection_without_selecting_the_new_one(self):
        self._select(self.paths[0], self.paths[1])

        new_path = str(Path(self.tmp_dir) / "d.png")
        Path(new_path).write_bytes(b"fake-png-bytes")
        self.workspace_manager.add_images([new_path])
        internal_new_path = self.workspace_manager.current_workspace.images[-1].file_path

        self.assertEqual(self._selected_paths(), {self.paths[0], self.paths[1]})
        self.assertNotIn(internal_new_path, self._selected_paths())

    def test_removing_one_selected_item_keeps_the_surviving_selection(self):
        self._select(self.paths[0], self.paths[1], self.paths[2], current=self.paths[0])

        self.workspace_manager.remove_images([self.paths[0]])

        self.assertEqual(self._selected_paths(), {self.paths[1], self.paths[2]})

    def test_removing_the_current_item_leaves_current_item_none_without_arbitrary_replacement(self):
        self._select(self.paths[0], current=self.paths[0])

        self.workspace_manager.remove_images([self.paths[0]])

        self.assertIsNone(self.page.list_widget.currentItem())
        self.assertFalse(self.page.enlarge_button.isEnabled())

    def test_removing_all_selected_items_empties_selection_and_disables_buttons(self):
        self._select(self.paths[0], self.paths[1], self.paths[2], current=self.paths[0])

        self.workspace_manager.remove_images(list(self.paths))

        self.assertEqual(self._selected_paths(), set())
        self.assertIsNone(self.page.list_widget.currentItem())
        self.assertFalse(self.page.delete_button.isEnabled())
        self.assertFalse(self.page.enlarge_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
