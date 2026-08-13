from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QInputDialog,
    QFileDialog,
    QMessageBox,
)


class DatasetsPage(QWidget):

    def __init__(self, dataset_manager):
        super().__init__()

        self.dataset_manager = dataset_manager

        layout = QVBoxLayout(self)

        title = QLabel("Datasets")
        title.setStyleSheet("font-size:24px;font-weight:bold;")
        layout.addWidget(title)

        dataset_buttons = QHBoxLayout()

        self.new_button = QPushButton("Nouveau dataset")
        self.new_button.clicked.connect(self.create_dataset)

        self.delete_button = QPushButton("Supprimer")
        self.delete_button.clicked.connect(self.delete_dataset)

        dataset_buttons.addWidget(self.new_button)
        dataset_buttons.addWidget(self.delete_button)

        layout.addLayout(dataset_buttons)

        self.dataset_list = QListWidget()
        self.dataset_list.currentItemChanged.connect(self.on_dataset_selection_changed)

        layout.addWidget(self.dataset_list)

        self.import_images_button = QPushButton("Importer des images")
        self.import_images_button.clicked.connect(self.import_images)

        layout.addWidget(self.import_images_button)

        self.images_list = QListWidget()

        layout.addWidget(self.images_list)

    def create_dataset(self):

        name, ok = QInputDialog.getText(self, "Nouveau dataset", "Nom :")

        if not ok or not name.strip():
            return

        dataset = self.dataset_manager.create(name.strip())

        if dataset is None:
            QMessageBox.warning(
                self,
                "Aucun personnage actif",
                "Sélectionnez un personnage avant de créer un dataset."
            )

    def delete_dataset(self):

        item = self.dataset_list.currentItem()

        if item is None:
            return

        dataset_id = item.data(Qt.UserRole)

        if self.dataset_manager.is_referenced_by_training(dataset_id):
            QMessageBox.warning(
                self,
                "Dataset utilisé",
                "Impossible de supprimer ce dataset : il est utilisé par une ou plusieurs sessions d'entraînement."
            )
            return

        self.dataset_manager.delete(dataset_id)

    def on_dataset_selection_changed(self, current, previous):

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

        added = self.dataset_manager.add_images(files)
        duplicates = len(files) - added

        if added == 0:
            QMessageBox.information(
                self,
                "Import terminé",
                "Aucune nouvelle image importée (déjà présentes)."
            )
        elif duplicates > 0:
            QMessageBox.information(
                self,
                "Import terminé",
                f"{added} image(s) importée(s), {duplicates} déjà présente(s) ignorée(s)."
            )
        else:
            QMessageBox.information(
                self,
                "Import terminé",
                f"{added} image(s) importée(s)."
            )

    def update_datasets(self, _payload=None):

        datasets = self.dataset_manager.list_datasets()
        active_dataset_id = self.dataset_manager.active_dataset_id

        self.dataset_list.blockSignals(True)
        self.dataset_list.clear()

        active_images = []

        for dataset in datasets:

            item = QListWidgetItem(
                f"{dataset['name']} ({len(dataset['images'])} image(s))"
            )
            item.setData(Qt.UserRole, dataset["dataset_id"])

            self.dataset_list.addItem(item)

            if dataset["dataset_id"] == active_dataset_id:
                self.dataset_list.setCurrentItem(item)
                active_images = dataset["images"]

        self.dataset_list.blockSignals(False)

        self.images_list.clear()

        for image in active_images:
            self.images_list.addItem(image["file_path"])
