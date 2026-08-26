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
    QLineEdit,
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

    def create_dataset(self):

        name, ok = QInputDialog.getText(self, "Nouveau dataset", "Nom :")

        if not ok or not name.strip():
            return

        dataset = self.dataset_manager.create(name.strip())

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

        if self.dataset_manager.active_dataset_id is None:
            return

        self.dataset_manager.update_name(self.name_edit.text())

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

        box = QMessageBox(self)
        box.setWindowTitle("Supprimer le dataset ?")
        box.setText(
            f"Supprimer le dataset « {item.text()} » ? Cette action est "
            "irréversible ; les images qu'il contient resteront dans la "
            "galerie Images."
        )
        delete_button = box.addButton("Supprimer", QMessageBox.AcceptRole)
        cancel_button = box.addButton("Annuler", QMessageBox.RejectRole)
        box.setDefaultButton(cancel_button)
        box.exec()

        if box.clickedButton() is not delete_button:
            return

        self.dataset_manager.delete(dataset_id)

    def on_dataset_selection_changed(self, current, previous):

        # Mission 063: "Supprimer" must always reflect whether there is
        # currently something to delete — set regardless of the early
        # return just below, unlike dataset_manager.select() itself.
        self.delete_button.setEnabled(current is not None)

        if current is None:
            return

        self.dataset_manager.select(current.data(Qt.UserRole))

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
        try:
            result = self.dataset_manager.add_images(files, renames=renames)
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

        self.dataset_list.blockSignals(True)
        self.dataset_list.clear()

        active_images = []
        active_name = ""

        for dataset in datasets:

            item = QListWidgetItem(
                f"{dataset['name']} ({len(dataset['images'])} image(s))"
            )
            item.setData(Qt.UserRole, dataset["dataset_id"])

            self.dataset_list.addItem(item)

            if dataset["dataset_id"] == active_dataset_id:
                self.dataset_list.setCurrentItem(item)
                active_images = dataset["images"]
                active_name = dataset["name"]

        self.dataset_list.blockSignals(False)
        # Mission 063: blockSignals() above suppresses currentItemChanged,
        # so setCurrentItem()/clear() never reach on_dataset_selection_changed()
        # during a rebuild — the button's state must be recomputed here.
        self.delete_button.setEnabled(self.dataset_list.currentItem() is not None)

        self.name_edit.setText(active_name)

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
            self.images_list.addItem(self._build_image_item(image["file_path"]))

        self.images_list.blockSignals(False)
        self._update_enlarge_button_state()

    def _on_sort_criterion_changed(self):
        self.update_datasets()

    def _build_image_item(self, file_path):
        item = QListWidgetItem()
        item.setIcon(load_thumbnail_icon(file_path, THUMBNAIL_SIZE, self.style()))
        item.setText(Path(file_path).name)
        item.setToolTip(file_path)
        item.setData(Qt.UserRole, file_path)
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

        selected_paths = [item.data(Qt.UserRole) for item in self.images_list.selectedItems()]

        if not selected_paths:
            return

        self.dataset_manager.remove_images(selected_paths)
