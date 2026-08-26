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
    QLineEdit,
    QFileDialog,
    QMessageBox,
)

from src.managers.workspace_manager import WorkspaceManagerError


class ModelsPage(QWidget):

    def __init__(self, model_manager):
        super().__init__()

        self.model_manager = model_manager

        layout = QVBoxLayout(self)

        title = QLabel("Models")
        title.setStyleSheet("font-size:24px;font-weight:bold;")
        layout.addWidget(title)

        model_buttons = QHBoxLayout()

        self.new_button = QPushButton("Nouveau modèle")
        self.new_button.clicked.connect(self.create_model)

        self.delete_button = QPushButton("Supprimer")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_model)

        model_buttons.addWidget(self.new_button)
        model_buttons.addWidget(self.delete_button)

        layout.addLayout(model_buttons)

        self.model_list = QListWidget()
        self.model_list.currentItemChanged.connect(self.on_model_selection_changed)

        layout.addWidget(self.model_list)

        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self.rename_model)

        layout.addWidget(self.name_edit)

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setPlaceholderText("Aucun fichier sélectionné")

        layout.addWidget(self.file_path_edit)

        self.browse_button = QPushButton("Sélectionner un fichier")
        self.browse_button.clicked.connect(self.browse_file)

        layout.addWidget(self.browse_button)

    def create_model(self):

        name, ok = QInputDialog.getText(self, "Nouveau modèle", "Nom :")

        if not ok or not name.strip():
            return

        model = self.model_manager.create(name.strip())

        if model is None:
            QMessageBox.warning(
                self,
                "Aucun projet ouvert",
                "Ouvrez ou créez un projet avant d'ajouter un modèle."
            )

    def delete_model(self):

        item = self.model_list.currentItem()

        if item is None:
            return

        box = QMessageBox(self)
        box.setWindowTitle("Supprimer le modèle ?")
        box.setText(
            f"Supprimer le modèle « {item.text()} » ? Cette action est irréversible."
        )
        delete_button = box.addButton("Supprimer", QMessageBox.AcceptRole)
        cancel_button = box.addButton("Annuler", QMessageBox.RejectRole)
        box.setDefaultButton(cancel_button)
        box.exec()

        if box.clickedButton() is not delete_button:
            return

        # Mission 068: delete() rolls back the Domain removal (and
        # active_model_id) before re-raising on a save() failure — the
        # model stays exactly where it was, so no refresh is needed here
        # beyond informing the user.
        try:
            self.model_manager.delete(item.data(Qt.UserRole))
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer la suppression dans le projet : {exc}\n"
                "Le modèle n'a pas été supprimé."
            )

    def on_model_selection_changed(self, current, previous):

        # Mission 063: "Supprimer" must always reflect whether there is
        # currently something to delete — set regardless of the early
        # return just below, unlike model_manager.select() itself.
        self.delete_button.setEnabled(current is not None)

        if current is None:
            return

        self.model_manager.select(current.data(Qt.UserRole))

    def browse_file(self):

        if self.model_manager.active_model_id is None:
            QMessageBox.warning(
                self,
                "Aucun modèle sélectionné",
                "Sélectionnez un modèle avant d'associer un fichier."
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner un fichier de modèle",
            "",
            "Fichiers modèle (*.safetensors *.ckpt *.pt *.bin);;Tous les fichiers (*)"
        )

        if not file_path:
            return

        self.model_manager.update_file_path(file_path)

    def rename_model(self):

        if self.model_manager.active_model_id is None:
            return

        self.model_manager.update_name(self.name_edit.text())

    def update_models(self, _payload=None):

        models = sorted(
            self.model_manager.list_models(),
            key=lambda model: model["name"].lower(),
        )
        active_model_id = self.model_manager.active_model_id

        self.model_list.blockSignals(True)
        self.model_list.clear()

        active_name = ""
        active_file_path = ""

        for model in models:

            item = QListWidgetItem(model["name"])
            item.setData(Qt.UserRole, model["model_id"])

            self.model_list.addItem(item)

            if model["model_id"] == active_model_id:
                self.model_list.setCurrentItem(item)
                active_name = model["name"]
                active_file_path = model["file_path"]

        self.model_list.blockSignals(False)
        # Mission 063: blockSignals() above suppresses currentItemChanged,
        # so setCurrentItem()/clear() never reach on_model_selection_changed()
        # during a rebuild — the button's state must be recomputed here.
        self.delete_button.setEnabled(self.model_list.currentItem() is not None)

        self.name_edit.setText(active_name)
        self.file_path_edit.setText(active_file_path)
