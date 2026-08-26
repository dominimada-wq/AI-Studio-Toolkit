from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QDialog,
    QFileDialog,
    QMessageBox,
)

from src.managers.workspace_manager import WorkspaceManagerError
from src.ui.dialogs.image_preview_dialog import ImagePreviewDialog
from src.ui.dialogs.import_collision_dialog import ImportCollisionDialog
from src.ui.thumbnails import load_thumbnail_icon, file_mtime_sort_key

THUMBNAIL_SIZE = QSize(128, 128)
GRID_SIZE = QSize(150, 170)


class ImagesPage(QWidget):

    def __init__(self, workspace_manager):
        super().__init__()

        self.workspace_manager = workspace_manager

        layout = QVBoxLayout(self)

        title = QLabel("Images")
        title.setStyleSheet("""
            QLabel{
                font-size:24px;
                font-weight:bold;
            }
        """)

        layout.addWidget(title)

        self.import_button = QPushButton("Importer des images")
        self.import_button.clicked.connect(self.import_images)

        layout.addWidget(self.import_button)

        sort_row = QHBoxLayout()

        sort_label = QLabel("Trier par :")

        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Nom (A → Z)", "name")
        self.sort_combo.addItem("Date du fichier (plus récent d'abord)", "date")
        self.sort_combo.currentIndexChanged.connect(self._on_sort_criterion_changed)

        sort_row.addWidget(sort_label)
        sort_row.addWidget(self.sort_combo)

        layout.addLayout(sort_row)

        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.setMovement(QListWidget.Static)
        self.list_widget.setWordWrap(True)
        self.list_widget.setIconSize(THUMBNAIL_SIZE)
        self.list_widget.setGridSize(GRID_SIZE)
        # Mission 046: ExtendedSelection lets "Supprimer" act on several
        # images at once — enlarge_button/double-click keep operating
        # on currentItem() alone (Qt's own notion of the focused item),
        # unchanged single-image preview semantics.
        self.list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.list_widget.itemSelectionChanged.connect(self._update_enlarge_button_state)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)

        layout.addWidget(self.list_widget)

        action_buttons = QHBoxLayout()

        self.enlarge_button = QPushButton("Voir en grand")
        self.enlarge_button.setEnabled(False)
        self.enlarge_button.clicked.connect(self._on_enlarge_clicked)

        self.delete_button = QPushButton("Supprimer")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_selected_images)

        action_buttons.addWidget(self.enlarge_button)
        action_buttons.addWidget(self.delete_button)

        layout.addLayout(action_buttons)

    def import_images(self):

        if not self.workspace_manager.opened:
            QMessageBox.warning(
                self,
                "Aucun projet ouvert",
                "Ouvrez ou créez un projet avant d'importer des images."
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

        # Mission 028 (second smoke test): a colliding name is never
        # auto-suffixed without asking anymore — preview first, and if
        # anything collides, resolve every collision in a single
        # dialog (never one QMessageBox per file) before the real
        # import runs. WorkspaceStorage.copy_into_workspace()'s own
        # silent auto-suffix remains the underlying safety net for any
        # caller that skips this dialog (tests, programmatic use) —
        # only this UI-driven flow now always asks first.
        collisions = self.workspace_manager.preview_collisions(files)
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

        # Mission 067: add_images() now rollbacks Workspace.images and
        # compensates any newly created copy before re-raising on a
        # save() failure — nothing here needs to reintroduce the
        # imported files, a retry with the same selection is a genuine
        # new attempt.
        try:
            result = self.workspace_manager.add_images(files, renames=renames)
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer l'import dans le projet : {exc}\n"
                "Aucune image n'a été importée."
            )
            return

        self._show_import_result(result, ui_skipped=ui_skipped)

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

    def _on_sort_criterion_changed(self):

        workspace = self.workspace_manager.current_workspace
        self.update_images(workspace.to_dict() if workspace is not None else None)

    def update_images(self, workspace):

        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        if workspace is not None:
            if self.sort_combo.currentData() == "date":
                sorted_images = sorted(
                    workspace.get("images", []),
                    key=lambda image: file_mtime_sort_key(image["file_path"]),
                    reverse=True,
                )
            else:
                sorted_images = sorted(
                    workspace.get("images", []),
                    key=lambda image: Path(image["file_path"]).name.lower(),
                )
            for image in sorted_images:
                self.list_widget.addItem(self._build_item(image["file_path"]))

        self.list_widget.blockSignals(False)
        self._update_enlarge_button_state()

    def _build_item(self, file_path):
        item = QListWidgetItem()
        item.setIcon(self._load_thumbnail_icon(file_path))
        item.setText(Path(file_path).name)
        item.setToolTip(file_path)
        item.setData(Qt.UserRole, file_path)
        return item

    def _load_thumbnail_icon(self, file_path):
        return load_thumbnail_icon(file_path, THUMBNAIL_SIZE, self.style())

    def _update_enlarge_button_state(self):
        self.enlarge_button.setEnabled(self.list_widget.currentItem() is not None)
        # Mission 046: "Supprimer" follows the same has-a-selection
        # state as "Voir en grand" — no second source of truth for
        # image-selection gating in this Page.
        self.delete_button.setEnabled(bool(self.list_widget.selectedItems()))

    def _on_item_double_clicked(self, item):
        self._open_preview(item.data(Qt.UserRole))

    def _on_enlarge_clicked(self):
        item = self.list_widget.currentItem()
        if item is None:
            return
        self._open_preview(item.data(Qt.UserRole))

    def _open_preview(self, file_path):
        ImagePreviewDialog(file_path, parent=self).exec()

    def delete_selected_images(self):

        paths = [item.data(Qt.UserRole) for item in self.list_widget.selectedItems()]

        if not paths:
            return

        blocked_by = self.workspace_manager.images_referenced_by_datasets(paths)

        if blocked_by:
            dataset_names = ", ".join(sorted(blocked_by.keys()))
            QMessageBox.warning(
                self,
                "Suppression impossible",
                "Une ou plusieurs images sélectionnées sont encore utilisées par un ou "
                f"plusieurs Datasets ({dataset_names}). Retirez-les d'abord de ces "
                "Datasets avant de les supprimer de la galerie Images."
            )
            return

        preview = self.workspace_manager.preview_image_removal(paths)

        if preview.reference_only and not preview.deletable:
            title = "Retirer les images sélectionnées ?"
            text = (
                "Ces images seront retirées de la galerie du projet. "
                "Aucun fichier ne sera supprimé du disque."
            )
            accept_label = "Retirer"
        elif preview.deletable and not preview.reference_only:
            title = "Supprimer les images sélectionnées ?"
            text = (
                "Les images seront retirées de la galerie et les fichiers correspondants "
                "seront supprimés définitivement du projet. Cette action est irréversible."
            )
            accept_label = "Supprimer"
        else:
            title = "Supprimer les images sélectionnées ?"
            text = (
                f"{len(preview.deletable)} image(s) seront retirées de la galerie et "
                "leur(s) fichier(s) seront supprimé(s) définitivement du projet. "
                f"{len(preview.reference_only)} image(s) seront retirées de la galerie "
                "sans suppression de fichier."
            )
            accept_label = "Continuer"

        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        accept_button = box.addButton(accept_label, QMessageBox.AcceptRole)
        cancel_button = box.addButton("Annuler", QMessageBox.RejectRole)
        box.setDefaultButton(cancel_button)
        box.exec()

        if box.clickedButton() is not accept_button:
            return

        # Mission 066: remove_images() is persistence-first — a
        # WorkspaceManagerError here means the removal was never
        # persisted and no file was touched (see its docstring); a
        # successful return already reflects a durable, project-level
        # removal even if deletion_failed is non-empty below, so it
        # must never be presented as a failure of the removal itself.
        try:
            result = self.workspace_manager.remove_images(paths)
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer la suppression dans le projet : {exc}\n"
                "Aucun fichier n'a été supprimé."
            )
            return

        if result.deletion_failed:
            names = ", ".join(Path(p).name for p in result.deletion_failed)
            QMessageBox.warning(
                self,
                "Suppression partielle",
                "Les images ont été retirées du projet. Suppression sur disque "
                f"impossible pour {len(result.deletion_failed)} fichier(s) : {names}."
            )
