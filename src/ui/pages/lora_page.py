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


class LoRAPage(QWidget):

    def __init__(self, lora_manager):
        super().__init__()

        self.lora_manager = lora_manager

        layout = QVBoxLayout(self)

        title = QLabel("LoRA")
        title.setStyleSheet("font-size:24px;font-weight:bold;")
        layout.addWidget(title)

        lora_buttons = QHBoxLayout()

        self.new_button = QPushButton("Nouvelle LoRA")
        self.new_button.clicked.connect(self.create_lora)

        self.delete_button = QPushButton("Supprimer")
        self.delete_button.clicked.connect(self.delete_lora)

        lora_buttons.addWidget(self.new_button)
        lora_buttons.addWidget(self.delete_button)

        layout.addLayout(lora_buttons)

        self.lora_list = QListWidget()
        self.lora_list.currentItemChanged.connect(self.on_lora_selection_changed)

        layout.addWidget(self.lora_list)

        self.import_files_button = QPushButton("Importer des fichiers")
        self.import_files_button.clicked.connect(self.import_files)

        layout.addWidget(self.import_files_button)

        self.files_list = QListWidget()

        layout.addWidget(self.files_list)

    def create_lora(self):

        name, ok = QInputDialog.getText(self, "Nouvelle LoRA", "Nom :")

        if not ok or not name.strip():
            return

        lora = self.lora_manager.create(name.strip())

        if lora is None:
            # Mission 029: LoRAManager.create() now follows the Workspace's
            # principal Character (Mission 026/028), not a manual selection
            # the hidden multi-character UI no longer offers a way to make —
            # this can now only fire for the genuine edge case of a
            # Workspace with zero Character at all.
            QMessageBox.warning(
                self,
                "Aucun personnage",
                "Ce projet ne possède aucun personnage — créez-en un depuis Characters avant de créer une LoRA."
            )

    def delete_lora(self):

        item = self.lora_list.currentItem()

        if item is None:
            return

        self.lora_manager.delete(item.data(Qt.UserRole))

    def on_lora_selection_changed(self, current, previous):

        if current is None:
            return

        self.lora_manager.select(current.data(Qt.UserRole))

    def import_files(self):

        if self.lora_manager.active_lora_id is None:
            QMessageBox.warning(
                self,
                "Aucune LoRA sélectionnée",
                "Sélectionnez une LoRA avant d'importer des fichiers."
            )
            return

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Sélectionner des fichiers",
            "",
            "Fichiers LoRA (*.safetensors *.ckpt *.pt *.bin *.json);;Tous les fichiers (*)"
        )

        if not files:
            return

        added = self.lora_manager.add_files(files)
        duplicates = len(files) - added

        if added == 0:
            QMessageBox.information(
                self,
                "Import terminé",
                "Aucun nouveau fichier importé (déjà présents)."
            )
        elif duplicates > 0:
            QMessageBox.information(
                self,
                "Import terminé",
                f"{added} fichier(s) importé(s), {duplicates} déjà présent(s) ignoré(s)."
            )
        else:
            QMessageBox.information(
                self,
                "Import terminé",
                f"{added} fichier(s) importé(s)."
            )

    def update_loras(self, _payload=None):

        loras = self.lora_manager.list_loras()
        active_lora_id = self.lora_manager.active_lora_id

        self.lora_list.blockSignals(True)
        self.lora_list.clear()

        active_files = []

        for lora in loras:

            item = QListWidgetItem(
                f"{lora['name']} ({len(lora['files'])} fichier(s))"
            )
            item.setData(Qt.UserRole, lora["lora_id"])

            self.lora_list.addItem(item)

            if lora["lora_id"] == active_lora_id:
                self.lora_list.setCurrentItem(item)
                active_files = lora["files"]

        self.lora_list.blockSignals(False)

        self.files_list.clear()

        for file_path in active_files:
            self.files_list.addItem(file_path)
