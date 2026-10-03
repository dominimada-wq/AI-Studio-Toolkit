from pathlib import Path

from PySide6.QtCore import Qt, QSize, QItemSelectionModel
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QTextEdit,
    QDialog,
    QInputDialog,
    QFileDialog,
    QMessageBox,
)

from src.managers.workspace_manager import WorkspaceManagerError
from src.ui.dialogs.image_preview_dialog import ImagePreviewDialog
from src.ui.dialogs.import_collision_dialog import ImportCollisionDialog
from src.ui.dialogs.select_images_dialog import SelectImagesDialog
from src.ui.thumbnails import load_thumbnail_icon, file_mtime_sort_key

THUMBNAIL_SIZE = QSize(128, 128)
GRID_SIZE = QSize(150, 170)


class DatasetsPage(QWidget):

    def __init__(self, dataset_manager, workspace_manager):
        super().__init__()

        self.dataset_manager = dataset_manager
        # Mission 036: source of authority for "no Workspace open" vs
        # "Workspace open without a principal Character" — see
        # create_dataset() below.
        self.workspace_manager = workspace_manager

        # Mission 082: tracks which Dataset's images images_list
        # currently displays — None once no Dataset is active (no
        # Workspace open, no Dataset selected, active Dataset just
        # deleted). Read at the top of update_datasets() (before this
        # call's own active_dataset_id is known to have changed or not)
        # and reassigned at the end of every call — the sole way to tell
        # "same Dataset, unrelated refresh" from "genuine switch to a
        # different Dataset" apart, since dataset_list.currentItem() has
        # already moved to the new item by the time a real click's
        # currentItemChanged handler (and everything it triggers, up to
        # this method) runs. Same role as LoRAPage._loaded_lora_id
        # (Mission 078), reused here for a different purpose: gating
        # images_list's selection restoration (Mission 082), not a
        # dirty-state draft.
        self._displayed_dataset_id = None

        # Mission 098: which image's caption is currently loaded in
        # caption_edit (an image_id, from Qt.UserRole + 1 on the
        # corresponding images_list item — never the file_path, which
        # is not a reliable per-image identity, see MISSION_098.md
        # section 4). None when no image is selected/no Dataset active.
        # _caption_dirty mirrors LoRAPage._metadata_dirty's exact role.
        self._caption_loaded_image_id = None
        self._caption_dirty = False

        # Mission 165: name_edit is a commit-on-blur field (editingFinished
        # only, no Save button) — update_datasets() used to overwrite it
        # unconditionally, silently discarding an in-progress rename on any
        # unrelated WORKSPACE_SAVED/RENAMED. These three states track what
        # name_edit was last loaded for (identity + value), from which a
        # real draft is derived by direct comparison, plus a reentrancy
        # guard for rename_dataset(). Strictly independent from the
        # _caption_* state above: the two drafts never share a flag, an
        # identity or a guard.
        self._name_editor_owner_id = None
        self._name_editor_loaded_value = ""
        self._renaming_in_progress = False

        layout = QVBoxLayout(self)

        title = QLabel("Datasets")
        title.setStyleSheet("font-size:24px;font-weight:bold;")
        layout.addWidget(title)

        dataset_buttons = QHBoxLayout()

        self.new_button = QPushButton("Nouveau dataset")
        self.new_button.clicked.connect(self.create_dataset)

        self.delete_button = QPushButton("Supprimer")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_dataset)

        dataset_buttons.addWidget(self.new_button)
        dataset_buttons.addWidget(self.delete_button)

        layout.addLayout(dataset_buttons)

        self.dataset_list = QListWidget()
        self.dataset_list.currentItemChanged.connect(self.on_dataset_selection_changed)

        layout.addWidget(self.dataset_list)

        # Mission 054: renaming is an immediate-commit edit, independent
        # of dataset_list's ordering and of the images_list/sort_combo
        # below — mirrors ModelsPage.name_edit/PromptsPage.name_edit.
        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self.rename_dataset)

        layout.addWidget(self.name_edit)

        import_buttons = QHBoxLayout()

        self.import_images_button = QPushButton("Importer des images")
        self.import_images_button.clicked.connect(self.import_images)

        self.add_from_gallery_button = QPushButton("Ajouter depuis Images…")
        self.add_from_gallery_button.clicked.connect(self.add_images_from_gallery)

        import_buttons.addWidget(self.import_images_button)
        import_buttons.addWidget(self.add_from_gallery_button)

        layout.addLayout(import_buttons)

        sort_row = QHBoxLayout()

        sort_label = QLabel("Trier par :")

        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Nom (A → Z)", "name")
        self.sort_combo.addItem("Date du fichier (plus récent d'abord)", "date")
        self.sort_combo.currentIndexChanged.connect(self._on_sort_criterion_changed)

        sort_row.addWidget(sort_label)
        sort_row.addWidget(self.sort_combo)

        layout.addLayout(sort_row)

        self.images_list = QListWidget()
        self.images_list.setViewMode(QListWidget.IconMode)
        self.images_list.setResizeMode(QListWidget.Adjust)
        self.images_list.setMovement(QListWidget.Static)
        self.images_list.setWordWrap(True)
        self.images_list.setIconSize(THUMBNAIL_SIZE)
        self.images_list.setGridSize(GRID_SIZE)
        # Mission 045: ExtendedSelection lets "Retirer du dataset" act on
        # several images at once — enlarge_button/double-click keep
        # operating on currentItem() alone (Qt's own notion of the
        # focused item, well-defined regardless of how many items are
        # selected), unchanged single-image preview semantics.
        self.images_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.images_list.itemSelectionChanged.connect(self._update_enlarge_button_state)
        self.images_list.itemDoubleClicked.connect(self._on_image_item_double_clicked)
        self.images_list.currentItemChanged.connect(self.on_image_selection_changed)

        layout.addWidget(self.images_list)

        enlarge_buttons = QHBoxLayout()

        self.enlarge_button = QPushButton("Voir en grand")
        self.enlarge_button.setEnabled(False)
        self.enlarge_button.clicked.connect(self._on_enlarge_clicked)

        self.remove_from_dataset_button = QPushButton("Retirer du dataset")
        self.remove_from_dataset_button.setEnabled(False)
        self.remove_from_dataset_button.clicked.connect(self.remove_selected_images_from_dataset)

        enlarge_buttons.addWidget(self.enlarge_button)
        enlarge_buttons.addWidget(self.remove_from_dataset_button)

        layout.addLayout(enlarge_buttons)

        # Mission 098: caption of the image currently selected in
        # images_list — mirrors LoRAPage's metadata panel pattern
        # (dirty flag + explicit Save button), scoped to a single field.
        caption_label = QLabel("Caption de l'image sélectionnée :")
        layout.addWidget(caption_label)

        self.caption_edit = QTextEdit()
        self.caption_edit.setEnabled(False)
        self.caption_edit.textChanged.connect(self._on_caption_changed)

        layout.addWidget(self.caption_edit)

        self.save_caption_button = QPushButton("Enregistrer la caption")
        self.save_caption_button.setEnabled(False)
        self.save_caption_button.clicked.connect(self.save_caption)

        layout.addWidget(self.save_caption_button)

    def create_dataset(self):

        name, ok = QInputDialog.getText(self, "Nouveau dataset", "Nom :")

        if not ok or not name.strip():
            return

        try:
            dataset = self.dataset_manager.create(name.strip())
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer le nouveau dataset dans le projet : {exc}\n"
                "Le dataset n'a pas été créé."
            )
            return

        if dataset is None:
            # Mission 028 smoke test fix: DatasetManager.create() now
            # follows the Workspace's principal Character (Mission 026),
            # not a manual selection the hidden multi-character UI no
            # longer offers a way to make — this can now only fire for
            # the genuine edge case of a Workspace with zero Character
            # at all (e.g. its only Character was deleted via the
            # still-functional internal multi-character CRUD).
            if not self.workspace_manager.opened:
                QMessageBox.warning(
                    self,
                    "Aucun projet ouvert",
                    "Ouvrez ou créez un projet avant de créer un dataset."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Aucun personnage",
                    "Ce projet ne possède aucun personnage — créez-en un depuis Characters avant de créer un dataset."
                )

    def rename_dataset(self):

        if self._renaming_in_progress:
            # Mission 165: reentrant call — e.g. a second editingFinished
            # firing while QMessageBox.critical()'s nested event loop is
            # still running below. No new Manager call, no new dialog, no
            # extra reconciliation: the in-flight call below remains
            # solely responsible for the final state.
            return

        active_dataset = self.dataset_manager.active_dataset

        if active_dataset is None or self._name_editor_owner_id != active_dataset.dataset_id:
            # Mission 165: nothing active, or name_edit's content was
            # loaded for a different Dataset than the one currently
            # active — never send this text to update_name() for the
            # wrong (or no) target. Existence is checked on the object
            # itself, never inferred from active_dataset_id alone.
            self._reload_name_editor()
            return

        self._renaming_in_progress = True
        try:
            # Mission 070: update_name() rolls back Dataset.name before
            # re-raising on a save() failure.
            try:
                self.dataset_manager.update_name(self.name_edit.text())
            except WorkspaceManagerError as exc:
                QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Impossible d'enregistrer le renommage dans le projet : {exc}\n"
                    "Le nom précédent a été restauré."
                )
        finally:
            # Mission 165: reconciles name_edit with whatever is now
            # canonical — success, idempotent no-op, or the rolled-back
            # previous name on failure — regardless of focus. Never
            # re-derived from a value captured for an earlier context.
            try:
                self._reload_name_editor()
            finally:
                self._renaming_in_progress = False

    def _reload_name_editor(self):
        active_dataset = self.dataset_manager.active_dataset
        if active_dataset is None:
            self._name_editor_owner_id = None
            self._name_editor_loaded_value = ""
        else:
            self._name_editor_owner_id = active_dataset.dataset_id
            self._name_editor_loaded_value = active_dataset.name
        self.name_edit.setText(self._name_editor_loaded_value)

    def _has_unsaved_name_draft(self, active_dataset) -> bool:
        return (
            active_dataset is not None
            and self._name_editor_owner_id == active_dataset.dataset_id
            and self.name_edit.text() != self._name_editor_loaded_value
        )

    def delete_dataset(self):

        item = self.dataset_list.currentItem()

        if item is None:
            return

        dataset_id = item.data(Qt.UserRole)

        # Mission 062: the existing "used by a Training" guard must run
        # before any confirmation is shown — a deletion that is going to
        # be refused outright must never first ask "are you sure?",
        # which would misleadingly imply it could succeed.
        if self.dataset_manager.is_referenced_by_training(dataset_id):
            QMessageBox.warning(
                self,
                "Dataset utilisé",
                "Impossible de supprimer ce dataset : il est utilisé par une ou plusieurs sessions d'entraînement."
            )
            return

        # Mission 160: enriches this same, already-existing destructive
        # confirmation rather than adding a second dialog — deleting the
        # active Dataset always destroys dataset.entries (the caption's
        # only storage) along with it, so a Save option would be exactly
        # as misleading here as it was for _confirm_discard_caption_
        # before_removal() (Mission 159). _caption_dirty can only be True
        # while an image of the currently active Dataset is loaded (the
        # Dataset-switch guard above never lets it survive a switch to a
        # different Dataset), so this Dataset is always the one the
        # dirty caption actually belongs to — no image_id/ownership
        # comparison is needed, unlike Mission 159's removed-set check.
        text = (
            f"Supprimer le dataset « {item.text()} » ? Cette action est "
            "irréversible. Les images provenant de la galerie Images y "
            "resteront ; les images importées directement dans ce dataset "
            "seront supprimées avec lui."
        )
        if self._caption_dirty:
            text += (
                " L'image actuellement sélectionnée possède des "
                "modifications de caption non enregistrées : ces "
                "modifications seront également perdues si la suppression "
                "est confirmée."
            )

        box = QMessageBox(self)
        box.setWindowTitle("Supprimer le dataset ?")
        box.setText(text)
        delete_button = box.addButton("Supprimer", QMessageBox.AcceptRole)
        cancel_button = box.addButton("Annuler", QMessageBox.RejectRole)
        box.setDefaultButton(cancel_button)
        box.exec()

        if box.clickedButton() is not delete_button:
            return

        # Mission 068: delete() rolls back the Domain removal (and
        # active_dataset_id) before re-raising on a save() failure — the
        # dataset stays exactly where it was, so no refresh is needed
        # here beyond informing the user.
        try:
            result = self.dataset_manager.delete(dataset_id)
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer la suppression dans le projet : {exc}\n"
                "Le dataset n'a pas été supprimé."
            )
            return

        # Mission 075: a successful deletion can still leave its private
        # folder only partially cleaned up on disk (best-effort, never
        # rolled back) — a non-blocking warning, never presented as a
        # failure of the deletion itself, which already succeeded.
        if result.cleanup_failed:
            QMessageBox.warning(
                self,
                "Suppression partielle",
                "Le dataset a été supprimé du projet, mais certains fichiers "
                "associés n'ont pas pu être supprimés du disque (dossier "
                f"résiduel : {result.residual_path})."
            )

    def on_dataset_selection_changed(self, current, previous):
        """
        Mission 158: guards a genuine change of which Dataset's images
        (and, transitively, whichever image's caption is currently
        loaded) is being displayed — mirrors on_image_selection_changed()'s
        exact Save/Discard/Cancel contract, one level up. DatasetManager.
        select() publishes DATASET_SELECTED synchronously, itself wired
        to update_datasets() (main_window.py) — so the dirty-draft check
        below must run strictly before select() is ever called, never
        after.
        """

        # Mission 063: "Supprimer" must always reflect whether there is
        # currently something to delete — set regardless of any early
        # return below, unlike dataset_manager.select() itself.
        self.delete_button.setEnabled(current is not None)

        if current is None:
            return

        # Mission 158: captured now, before any Manager call below can
        # reentrantly trigger update_datasets() -> dataset_list.clear(),
        # which deletes the underlying C++ QListWidgetItem `current`
        # wraps. Same precedent as LoRAPage.on_lora_selection_changed()/
        # PromptsPage.
        target_dataset_id = current.data(Qt.UserRole)

        if self._caption_dirty:
            choice = self._confirm_discard_caption_before_switch()

            if choice == QMessageBox.Cancel:
                # DatasetManager.select() is never called — active_dataset_id
                # stays untouched. Revert the widget's own native selection
                # (already changed by Qt before this handler ran) back to
                # `previous`, with signals blocked to avoid recursively
                # re-entering this same handler.
                self.dataset_list.blockSignals(True)
                self.dataset_list.setCurrentItem(previous)
                self.dataset_list.blockSignals(False)
                self.delete_button.setEnabled(previous is not None)
                return

            if choice == QMessageBox.Save:
                if not self._save_caption_or_report_error():
                    self.dataset_list.blockSignals(True)
                    self.dataset_list.setCurrentItem(previous)
                    self.dataset_list.blockSignals(False)
                    self.delete_button.setEnabled(previous is not None)
                    return

            self._caption_dirty = False

        self.dataset_manager.select(target_dataset_id)

    def import_images(self):

        if self.dataset_manager.active_dataset_id is None:
            QMessageBox.warning(
                self,
                "Aucun dataset sélectionné",
                "Sélectionnez un dataset avant d'importer des images."
            )
            return

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Sélectionner des images",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )

        if not files:
            return

        # Mission 028 (second smoke test): same collision UX as
        # ImagesPage.import_images() — see its comment for the full
        # rationale.
        collisions = self.dataset_manager.preview_collisions(files)
        ui_skipped = []
        renames = {}

        if collisions:
            dialog = ImportCollisionDialog(collisions, parent=self)
            if dialog.exec() != QDialog.Accepted:
                return

            for source, choice in dialog.decisions().items():
                if choice is None:
                    ui_skipped.append(source)
                else:
                    renames[source] = choice

            files = [f for f in files if f not in ui_skipped]

        # Mission 067: add_images() rollbacks dataset.images and
        # compensates any newly created copy before re-raising on a
        # save() failure — a retry with the same selection is a
        # genuine new attempt.
        # Mission 098: detect_caption_sidecars=True only here — this is
        # a disk import, where a same-name .txt next to a source image
        # is a well-established captioning convention. Never passed by
        # add_images_from_gallery() below (Workspace gallery images have
        # no such established sidecar contract).
        try:
            result = self.dataset_manager.add_images(
                files, renames=renames, detect_caption_sidecars=True
            )
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer l'import dans le projet : {exc}\n"
                "Aucune image n'a été importée."
            )
            return

        self._show_import_result(result, ui_skipped=ui_skipped)

    def add_images_from_gallery(self):

        if self.dataset_manager.active_dataset_id is None:
            QMessageBox.warning(
                self,
                "Aucun dataset sélectionné",
                "Sélectionnez un dataset avant d'importer des images."
            )
            return

        image_paths = [
            image.file_path for image in self.workspace_manager.current_workspace.images
        ]

        if not image_paths:
            QMessageBox.information(
                self,
                "Galerie Images vide",
                "Aucune image dans la galerie Images."
            )
            return

        dialog = SelectImagesDialog(image_paths, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return

        selected_paths = dialog.selected_paths()
        if not selected_paths:
            return

        try:
            result = self.dataset_manager.add_images(selected_paths)
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer l'import dans le projet : {exc}\n"
                "Aucune image n'a été importée."
            )
            return

        self._show_import_result(result)

    def _show_import_result(self, result, ui_skipped=None):

        all_skipped = list(ui_skipped or []) + list(result.skipped)

        if result.failed:
            failed_names = ", ".join(Path(p).name for p in result.failed)
            message = f"{result.added} image(s) importée(s)."
            if all_skipped:
                message += f" {len(all_skipped)} ignorée(s) ou déjà présente(s)."
            message += f" {len(result.failed)} échec(s) : {failed_names}."
            QMessageBox.warning(self, "Import partiellement réussi", message)
        elif result.added == 0:
            QMessageBox.information(
                self,
                "Import terminé",
                "Aucune nouvelle image importée (ignorée(s) ou déjà présente(s))."
            )
        elif all_skipped:
            QMessageBox.information(
                self,
                "Import terminé",
                f"{result.added} image(s) importée(s), "
                f"{len(all_skipped)} ignorée(s) ou déjà présente(s)."
            )
        else:
            QMessageBox.information(
                self,
                "Import terminé",
                f"{result.added} image(s) importée(s)."
            )

    def update_datasets(self, _payload=None):

        datasets = self.dataset_manager.list_datasets()
        active_dataset_id = self.dataset_manager.active_dataset_id

        # Mission 082: captured before anything below can change what
        # this call will end up displaying — see _displayed_dataset_id's
        # own comment in __init__. A genuine Dataset A -> B switch must
        # never carry over images_list's selection, even though the two
        # Datasets can legitimately share the same image file_path (no
        # copy — "Ajouter depuis Images…" references the same Workspace
        # image); only a same-Dataset refresh (e.g. an unrelated
        # WORKSPACE_SAVED) may restore it.
        #
        # Mission 167: the selection and the current item are captured and
        # restored by image_id (Qt.UserRole + 1 — the very identity the
        # caption panel already tracks through _caption_loaded_image_id),
        # never by file_path: a Workspace rename remaps every internal
        # file_path, so a file_path key would match nothing afterwards and
        # silently drop the selection, and with it the caption draft
        # attached to the selected image. The rebuilt Workspace keeps the
        # serialized image_id values, which are unique within a Dataset's
        # own Image pool. Invalid or duplicated ids (a hand-edited
        # project.json) are deliberately not handled here.
        same_dataset = active_dataset_id is not None and active_dataset_id == self._displayed_dataset_id
        previously_selected_image_ids = set()
        previously_current_image_id = None
        if same_dataset:
            previously_selected_image_ids = {
                item.data(Qt.UserRole + 1) for item in self.images_list.selectedItems()
            }
            current_image_item = self.images_list.currentItem()
            if current_image_item is not None:
                previously_current_image_id = current_image_item.data(Qt.UserRole + 1)

        self.dataset_list.blockSignals(True)
        self.dataset_list.clear()

        active_images = []
        active_entries = {}

        for dataset in datasets:

            item = QListWidgetItem(
                f"{dataset['name']} ({len(dataset['images'])} image(s))"
            )
            item.setData(Qt.UserRole, dataset["dataset_id"])

            self.dataset_list.addItem(item)

            if dataset["dataset_id"] == active_dataset_id:
                self.dataset_list.setCurrentItem(item)
                active_images = dataset["images"]
                active_entries = dataset["entries"]

        self.dataset_list.blockSignals(False)
        # Mission 063: blockSignals() above suppresses currentItemChanged,
        # so setCurrentItem()/clear() never reach on_dataset_selection_changed()
        # during a rebuild — the button's state must be recomputed here.
        self.delete_button.setEnabled(self.dataset_list.currentItem() is not None)

        # Mission 165: an unrelated refresh (any WORKSPACE_SAVED elsewhere
        # in the Workspace, WORKSPACE_RENAMED, CHARACTER_CREATED,
        # DATASET_CREATED, a sort change...) must never overwrite an
        # in-progress, still-unsaved edit of name_edit for the SAME active
        # Dataset. Preservation requires the active object to genuinely
        # exist, its identity to match what name_edit was last loaded
        # for, and the displayed text to still differ from that loaded
        # value — never inferred from focus. Entirely separate from the
        # caption draft handled by _refresh_caption_panel_for_current_
        # selection() further below.
        if not self._has_unsaved_name_draft(self.dataset_manager.active_dataset):
            self._reload_name_editor()

        self.images_list.blockSignals(True)
        self.images_list.clear()

        if self.sort_combo.currentData() == "date":
            sorted_images = sorted(
                active_images,
                key=lambda image: file_mtime_sort_key(image["file_path"]),
                reverse=True,
            )
        else:
            sorted_images = sorted(
                active_images,
                key=lambda image: Path(image["file_path"]).name.lower(),
            )
        for image in sorted_images:
            self.images_list.addItem(
                self._build_image_item(
                    image["file_path"], image["image_id"], image["image_id"] in active_entries
                )
            )

        restored_current_item = None
        for i in range(self.images_list.count()):
            item = self.images_list.item(i)
            image_id = item.data(Qt.UserRole + 1)
            if image_id in previously_selected_image_ids:
                item.setSelected(True)
            if image_id == previously_current_image_id:
                restored_current_item = item

        if restored_current_item is not None:
            # NoUpdate: setCurrentItem()'s default selection command would
            # otherwise disturb the selectedItems() just restored above —
            # see MISSION_082.md for the empirical proof.
            self.images_list.setCurrentItem(restored_current_item, QItemSelectionModel.NoUpdate)

        self.images_list.blockSignals(False)
        self._update_enlarge_button_state()
        # Mission 098: blockSignals() above suppresses currentItemChanged
        # too, so a genuine switch away from the previously loaded image
        # (a real Dataset switch, or the previously selected image being
        # removed) is never caught by on_image_selection_changed() during
        # this rebuild — synchronized explicitly here instead. Never
        # prompts to save/discard: by the time this runs, the rebuild has
        # already happened and there is nothing left to revert.
        self._refresh_caption_panel_for_current_selection()

        self._displayed_dataset_id = active_dataset_id

    def _on_sort_criterion_changed(self):
        self.update_datasets()

    def _build_image_item(self, file_path, image_id, has_caption=False):
        item = QListWidgetItem()
        item.setIcon(load_thumbnail_icon(file_path, THUMBNAIL_SIZE, self.style()))
        text = Path(file_path).name
        if has_caption:
            text += " [caption]"
        item.setText(text)
        item.setToolTip(file_path)
        item.setData(Qt.UserRole, file_path)
        item.setData(Qt.UserRole + 1, image_id)
        return item

    def _update_enlarge_button_state(self):
        self.enlarge_button.setEnabled(self.images_list.currentItem() is not None)
        # Mission 045: "Retirer du dataset" follows the same has-a-
        # selection state as "Voir en grand" — no second source of
        # truth introduced for image-selection gating in this Page.
        self.remove_from_dataset_button.setEnabled(bool(self.images_list.selectedItems()))

    def _on_image_item_double_clicked(self, item):
        self._open_image_preview(item.data(Qt.UserRole))

    def _on_enlarge_clicked(self):
        item = self.images_list.currentItem()
        if item is None:
            return
        self._open_image_preview(item.data(Qt.UserRole))

    def _open_image_preview(self, file_path):
        ImagePreviewDialog(file_path, parent=self).exec()

    def remove_selected_images_from_dataset(self):

        selected_items = self.images_list.selectedItems()
        selected_paths = [item.data(Qt.UserRole) for item in selected_items]

        if not selected_paths:
            return

        # Mission 159: guards a genuine destruction of the currently
        # edited caption's draft — the image it belongs to (identified
        # by _caption_loaded_image_id, never by file_path) is about to
        # be removed from the Dataset. Runs before any Manager call,
        # unlike on_dataset_selection_changed()'s guard above: clicking
        # this button never itself changes images_list's own selection/
        # current state, so Cancel needs no blockSignals()/selection
        # restoration — a plain return leaves everything untouched.
        removed_image_ids = {item.data(Qt.UserRole + 1) for item in selected_items}
        abandoned_dirty_image_id = None
        if self._caption_dirty and self._caption_loaded_image_id in removed_image_ids:
            if not self._confirm_discard_caption_before_removal():
                return
            # The draft is explicitly abandoned by the user's own
            # choice here — never saved (see the helper's own
            # docstring for why Save would be misleading in this
            # context). Both flags are cleared together, mirroring
            # _save_caption_or_report_error()'s own pairing. Captured
            # for the except branch below: if remove_images() ends up
            # failing, this is the one image whose editor content may
            # need an explicit resync (see that branch's own comment).
            abandoned_dirty_image_id = self._caption_loaded_image_id
            self._caption_dirty = False
            self.save_caption_button.setEnabled(False)

        # Mission 076: remove_images() rolls back dataset.images before
        # re-raising on a save() failure — WORKSPACE_SAVED is not
        # published on failure, so update_datasets() must be called
        # explicitly to resync images_list on the restored Domain state.
        try:
            self.dataset_manager.remove_images(selected_paths)
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer la suppression dans le projet : {exc}\n"
                "Aucune image n'a été retirée du dataset."
            )
            self.update_datasets()
            # Mission 159: update_datasets() alone is not enough here —
            # the failed removal means this image's identity never
            # actually changed, so _refresh_caption_panel_for_current_
            # selection()'s own identity short-circuit (unmodified,
            # same principle as every other refresh in this Page) skips
            # reloading it. Without this, caption_edit would keep
            # showing the already-abandoned draft while _caption_dirty
            # reads False — a clean flag must always correspond to
            # what's actually persisted. DatasetManager.remove_images()'s
            # own rollback (Mission 076) has already restored
            # dataset.entries to its exact pre-removal state by this
            # point, so this reload always shows the real, canonical
            # persisted caption — never the abandoned text.
            if abandoned_dirty_image_id is not None:
                self._load_caption_into_editor(abandoned_dirty_image_id)

    def on_image_selection_changed(self, current, previous):
        """
        Mission 098: guards a genuine change of which image's caption is
        being edited — mirrors LoRAPage.on_lora_selection_changed()'s
        exact Save/Discard/Cancel contract (Mission 078), scoped to
        images_list instead of lora_list. Never fires during
        update_datasets()'s own rebuild (blockSignals there) — that path
        is handled separately by _refresh_caption_panel_for_current_selection().
        """

        new_image_id = current.data(Qt.UserRole + 1) if current is not None else None

        if new_image_id == self._caption_loaded_image_id:
            return

        if self._caption_dirty:
            choice = self._confirm_discard_caption_before_switch()

            if choice == QMessageBox.Cancel:
                # Mission 078 precedent: Qt already moved currentItem()
                # before this handler ran — revert it back to `previous`
                # with signals blocked to avoid recursively re-entering
                # this same handler.
                self.images_list.blockSignals(True)
                self.images_list.setCurrentItem(previous)
                self.images_list.blockSignals(False)
                return

            if choice == QMessageBox.Save:
                if not self._save_caption_or_report_error():
                    self.images_list.blockSignals(True)
                    self.images_list.setCurrentItem(previous)
                    self.images_list.blockSignals(False)
                    return

        self._load_caption_into_editor(new_image_id)

    def _confirm_discard_caption_before_switch(self):
        box = QMessageBox(self)
        box.setWindowTitle("Modifications non enregistrées")
        box.setText(
            "La caption de l'image actuelle contient des modifications "
            "non enregistrées. Que souhaitez-vous faire ?"
        )
        box.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        box.setButtonText(QMessageBox.Save, "Enregistrer")
        box.setButtonText(QMessageBox.Discard, "Ignorer les modifications")
        box.setButtonText(QMessageBox.Cancel, "Annuler")
        box.setDefaultButton(QMessageBox.Cancel)
        return box.exec()

    def _confirm_discard_caption_before_removal(self) -> bool:
        """
        Mission 159: distinct from _confirm_discard_caption_before_switch()
        above — that helper's Save option has no lasting effect here.
        DatasetManager.remove_images() deletes dataset.entries[image_id]
        for every image actually removed, so a Save right before Remove
        would be immediately undone by the removal itself a moment
        later; offering it would be misleading. This dialog is
        therefore Discard/Cancel only, mirroring delete_dataset()'s own
        two-button AcceptRole/RejectRole confirmation pattern (the
        default-Cancel convention already used throughout this Page)
        rather than _confirm_discard_caption_before_switch()'s
        three-way Save/Discard/Cancel standard buttons — there is no
        third choice to offer.
        """
        box = QMessageBox(self)
        box.setWindowTitle("Modifications non enregistrées")
        box.setText(
            "L'image actuellement sélectionnée possède des modifications "
            "de caption non enregistrées. Retirer cette image du dataset "
            "fera perdre ces modifications. Continuer ?"
        )
        remove_button = box.addButton("Retirer quand même", QMessageBox.AcceptRole)
        cancel_button = box.addButton("Annuler", QMessageBox.RejectRole)
        box.setDefaultButton(cancel_button)
        box.exec()
        return box.clickedButton() is remove_button

    def confirm_context_change(self) -> bool:
        """
        Mission 158: same role as LoRAPage.confirm_context_change() —
        called by MainWindow before a Workspace/Character context change
        (new_project()/open_project()/closeEvent()) that would otherwise
        let reset_for_context_change() silently discard an unsaved
        caption draft, too late for a genuine Save or Cancel. Never
        resets the editor itself — that is reset_for_context_change()'s
        job, invoked afterward once the actual context change has
        already happened.
        """
        if not self._caption_dirty:
            return True

        choice = self._confirm_discard_caption_before_switch()

        if choice == QMessageBox.Cancel:
            return False

        if choice == QMessageBox.Save:
            if not self._save_caption_or_report_error():
                return False

        self._caption_dirty = False
        return True

    def reset_for_context_change(self, _payload=None):
        """
        Mission 158: subscribed by MainWindow to WORKSPACE_CREATED/
        OPENED/CLOSED and CHARACTER_SELECTED/CHARACTER_DELETED — never
        to update_datasets()'s own non-destructive events (WORKSPACE_
        SAVED/RENAMED, CHARACTER_CREATED, DATASET_CREATED/SELECTED/
        DELETED). Mirrors LoRAPage.reset_for_context_change(): the sole,
        unconditional Presentation path for these events. By the time
        this runs, confirm_context_change() has already resolved any
        dirty draft (or there was none to begin with) — update_datasets()
        alone already correctly resyncs _caption_dirty/
        _caption_loaded_image_id/the editor/the Save button/the Dataset
        and image selections from the now-current Domain state, so
        nothing is duplicated here.

        CHARACTER_SELECTED/CHARACTER_DELETED are currently unreachable
        from any live UI path — CharactersPage.list_widget (the only
        production caller of CharacterManager.select()/delete()) has
        been setVisible(False) since Mission 026's "1 Workspace = 1
        Character principal" revision. Wired here purely for
        architectural consistency with CharactersPage/LoRAPage/
        SettingsPage/TrainingPage, which already react to these same 2
        events the same way — not because a real user can trigger them
        today.

        Mission 165: also forces name_edit back onto the current Domain
        state, regardless of any unsaved name draft — a real context
        reset must never carry a draft across Workspaces/Characters, and
        update_datasets() alone would preserve it whenever the Manager
        still reports the same active Dataset. Never used for
        WORKSPACE_SAVED/RENAMED, which go to update_datasets() only.
        """
        self.update_datasets()
        self._reload_name_editor()

    def _refresh_caption_panel_for_current_selection(self):
        current_item = self.images_list.currentItem()
        new_image_id = current_item.data(Qt.UserRole + 1) if current_item is not None else None

        if new_image_id == self._caption_loaded_image_id:
            return

        self._load_caption_into_editor(new_image_id)

    def _load_caption_into_editor(self, image_id):

        self._caption_loaded_image_id = image_id

        # blockSignals: setPlainText() below must never itself mark the
        # freshly loaded caption as dirty (Mission 098) — same principle
        # as images_list/dataset_list's own blockSignals() around every
        # programmatic rebuild in this Page.
        self.caption_edit.blockSignals(True)
        if image_id is None:
            self.caption_edit.setPlainText("")
            self.caption_edit.setEnabled(False)
        else:
            dataset = self.dataset_manager.active_dataset
            entry = dataset.entries.get(image_id) if dataset is not None else None
            self.caption_edit.setPlainText(entry.caption if entry is not None else "")
            self.caption_edit.setEnabled(True)
        self.caption_edit.blockSignals(False)

        self._caption_dirty = False
        self.save_caption_button.setEnabled(False)

    def _on_caption_changed(self):
        self._caption_dirty = True
        self.save_caption_button.setEnabled(True)

    def save_caption(self):
        return self._save_caption_or_report_error()

    def _save_caption_or_report_error(self) -> bool:

        if self._caption_loaded_image_id is None:
            return True

        try:
            self.dataset_manager.set_caption(
                self._caption_loaded_image_id, self.caption_edit.toPlainText()
            )
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer la caption dans le projet : {exc}"
            )
            return False

        self._caption_dirty = False
        self.save_caption_button.setEnabled(False)
        return True
