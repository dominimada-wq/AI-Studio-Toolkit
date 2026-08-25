from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QInputDialog,
    QFileDialog,
    QMessageBox,
)

from src.ui.dialogs.image_preview_dialog import UNAVAILABLE_MESSAGE

THUMBNAIL_PREVIEW_SIZE = QSize(128, 128)
NO_THUMBNAIL_MESSAGE = "Aucune miniature."


class LoRAPage(QWidget):

    def __init__(self, lora_manager, workspace_manager):
        super().__init__()

        self.lora_manager = lora_manager
        # Mission 036: source of authority for "no Workspace open" vs
        # "Workspace open without a principal Character" — see
        # create_lora() below.
        self.workspace_manager = workspace_manager

        layout = QVBoxLayout(self)

        title = QLabel("LoRA")
        title.setStyleSheet("font-size:24px;font-weight:bold;")
        layout.addWidget(title)

        lora_buttons = QHBoxLayout()

        self.new_button = QPushButton("Nouvelle LoRA")
        self.new_button.clicked.connect(self.create_lora)

        self.delete_button = QPushButton("Supprimer")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_lora)

        lora_buttons.addWidget(self.new_button)
        lora_buttons.addWidget(self.delete_button)

        layout.addLayout(lora_buttons)

        self.lora_list = QListWidget()
        self.lora_list.currentItemChanged.connect(self.on_lora_selection_changed)

        layout.addWidget(self.lora_list)

        # Renommage (Mission 052) — édition immédiate sur perte de focus,
        # distinct du bouton "Enregistrer les métadonnées" ci-dessous
        # (Mission 047) : le nom identifie la LoRA elle-même, ce n'est
        # pas une métadonnée au sens de sa fiche engine/architecture/
        # trigger_word/version.
        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self.rename_lora)

        layout.addWidget(self.name_edit)

        self.import_files_button = QPushButton("Importer des fichiers")
        self.import_files_button.clicked.connect(self.import_files)

        layout.addWidget(self.import_files_button)

        self.files_list = QListWidget()
        self.files_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.files_list.itemSelectionChanged.connect(self._update_files_button_state)

        layout.addWidget(self.files_list)

        self.remove_files_button = QPushButton("Retirer les fichiers sélectionnés")
        self.remove_files_button.setEnabled(False)
        self.remove_files_button.clicked.connect(self.remove_selected_files)

        layout.addWidget(self.remove_files_button)

        # --- Métadonnées (Mission 047) ---

        metadata_title = QLabel("Métadonnées")
        metadata_title.setStyleSheet("font-size:16px;font-weight:bold;")
        layout.addWidget(metadata_title)

        metadata_form = QFormLayout()

        self.engine_edit = QLineEdit()
        self.architecture_edit = QLineEdit()
        self.trigger_word_edit = QLineEdit()
        self.version_edit = QLineEdit()

        metadata_form.addRow("Engine :", self.engine_edit)
        metadata_form.addRow("Architecture :", self.architecture_edit)
        metadata_form.addRow("Trigger word :", self.trigger_word_edit)
        metadata_form.addRow("Version :", self.version_edit)

        layout.addLayout(metadata_form)

        self.thumbnail_label = QLabel(NO_THUMBNAIL_MESSAGE)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setFixedSize(THUMBNAIL_PREVIEW_SIZE)

        layout.addWidget(self.thumbnail_label)

        thumbnail_buttons = QHBoxLayout()

        self.choose_thumbnail_button = QPushButton("Choisir une miniature…")
        self.choose_thumbnail_button.clicked.connect(self.choose_thumbnail)

        self.save_metadata_button = QPushButton("Enregistrer les métadonnées")
        self.save_metadata_button.clicked.connect(self.save_metadata)

        thumbnail_buttons.addWidget(self.choose_thumbnail_button)
        thumbnail_buttons.addWidget(self.save_metadata_button)

        layout.addLayout(thumbnail_buttons)

        self._update_metadata_buttons_state()

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
            if not self.workspace_manager.opened:
                QMessageBox.warning(
                    self,
                    "Aucun projet ouvert",
                    "Ouvrez ou créez un projet avant de créer une LoRA."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Aucun personnage",
                    "Ce projet ne possède aucun personnage — créez-en un depuis Characters avant de créer une LoRA."
                )

    def delete_lora(self):

        item = self.lora_list.currentItem()

        if item is None:
            return

        box = QMessageBox(self)
        box.setWindowTitle("Supprimer la LoRA ?")
        box.setText(
            f"Supprimer la LoRA « {item.text()} » ? Cette action est irréversible."
        )
        delete_button = box.addButton("Supprimer", QMessageBox.AcceptRole)
        cancel_button = box.addButton("Annuler", QMessageBox.RejectRole)
        box.setDefaultButton(cancel_button)
        box.exec()

        if box.clickedButton() is not delete_button:
            return

        self.lora_manager.delete(item.data(Qt.UserRole))

    def on_lora_selection_changed(self, current, previous):

        # Mission 063: "Supprimer" must always reflect whether there is
        # currently something to delete — set regardless of the early
        # return just below, unlike lora_manager.select() itself.
        self.delete_button.setEnabled(current is not None)

        if current is None:
            return

        self.lora_manager.select(current.data(Qt.UserRole))

    def rename_lora(self):

        active_lora_id = self.lora_manager.active_lora_id

        if active_lora_id is None:
            return

        self.lora_manager.update_name(active_lora_id, self.name_edit.text())

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

    def choose_thumbnail(self):

        active_lora_id = self.lora_manager.active_lora_id

        if active_lora_id is None:
            QMessageBox.warning(
                self,
                "Aucune LoRA sélectionnée",
                "Sélectionnez une LoRA avant de choisir une miniature."
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir une miniature",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )

        if not file_path:
            return

        result = self.lora_manager.set_thumbnail(active_lora_id, file_path)

        if result is None:
            QMessageBox.warning(
                self,
                "Copie impossible",
                "La miniature n'a pas pu être copiée dans le projet. "
                "La miniature précédente, si elle existe, est conservée."
            )

    def save_metadata(self):

        active_lora_id = self.lora_manager.active_lora_id

        if active_lora_id is None:
            return

        self.lora_manager.update(
            active_lora_id,
            engine=self.engine_edit.text(),
            architecture=self.architecture_edit.text(),
            trigger_word=self.trigger_word_edit.text(),
            version=self.version_edit.text(),
        )

    def _update_metadata_buttons_state(self):

        has_active_lora = self.lora_manager.active_lora_id is not None

        self.choose_thumbnail_button.setEnabled(has_active_lora)
        self.save_metadata_button.setEnabled(has_active_lora)

    def remove_selected_files(self):

        paths = [item.text() for item in self.files_list.selectedItems()]

        if not paths:
            return

        self.lora_manager.remove_files(paths)

    def _update_files_button_state(self):

        has_active_lora = self.lora_manager.active_lora_id is not None

        self.remove_files_button.setEnabled(
            has_active_lora and bool(self.files_list.selectedItems())
        )

    def _load_thumbnail_preview(self, thumbnail_path):

        if not thumbnail_path:
            self.thumbnail_label.setText(NO_THUMBNAIL_MESSAGE)
            return

        pixmap = QPixmap(thumbnail_path)

        if pixmap.isNull():
            self.thumbnail_label.setText(UNAVAILABLE_MESSAGE)
            return

        scaled = pixmap.scaled(
            THUMBNAIL_PREVIEW_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.thumbnail_label.setPixmap(scaled)

    def update_loras(self, _payload=None):

        loras = sorted(
            self.lora_manager.list_loras(),
            key=lambda lora: lora["name"].lower(),
        )
        active_lora_id = self.lora_manager.active_lora_id

        self.lora_list.blockSignals(True)
        self.lora_list.clear()

        active_lora_data = None

        for lora in loras:

            item = QListWidgetItem(
                f"{lora['name']} ({len(lora['files'])} fichier(s))"
            )
            item.setData(Qt.UserRole, lora["lora_id"])

            self.lora_list.addItem(item)

            if lora["lora_id"] == active_lora_id:
                self.lora_list.setCurrentItem(item)
                active_lora_data = lora

        self.lora_list.blockSignals(False)
        # Mission 063: blockSignals() above suppresses currentItemChanged,
        # so setCurrentItem()/clear() never reach on_lora_selection_changed()
        # during a rebuild — the button's state must be recomputed here.
        self.delete_button.setEnabled(self.lora_list.currentItem() is not None)

        self.files_list.clear()

        if active_lora_data is None:
            self.name_edit.setText("")
            self.engine_edit.setText("")
            self.architecture_edit.setText("")
            self.trigger_word_edit.setText("")
            self.version_edit.setText("")
            self._load_thumbnail_preview("")
        else:
            for file_path in active_lora_data["files"]:
                self.files_list.addItem(file_path)

            self.name_edit.setText(active_lora_data["name"])
            self.engine_edit.setText(active_lora_data["engine"])
            self.architecture_edit.setText(active_lora_data["architecture"])
            self.trigger_word_edit.setText(active_lora_data["trigger_word"])
            self.version_edit.setText(active_lora_data["version"])
            self._load_thumbnail_preview(active_lora_data["thumbnail"])

        self._update_metadata_buttons_state()
        self._update_files_button_state()
