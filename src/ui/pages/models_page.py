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

        # Mission 163: tracks the identity/value name_edit was last
        # loaded for, and whether a rename commit is currently in
        # flight — see _reload_name_editor()/_has_unsaved_name_draft()/
        # rename_model() below.
        self._name_editor_owner_id = None
        self._name_editor_loaded_value = ""
        self._renaming_in_progress = False

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

        try:
            model = self.model_manager.create(name.strip())
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer le nouveau modèle dans le projet : {exc}\n"
                "Le modèle n'a pas été créé."
            )
            return

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

        # Mission 070: update_file_path() rolls back Model.file_path
        # before re-raising on a save() failure. file_path_edit is only
        # ever written by update_models()'s own refresh, never directly
        # by this picker, so it was never showing the rejected value —
        # only the error needs surfacing here.
        try:
            self.model_manager.update_file_path(file_path)
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer le fichier dans le projet : {exc}\n"
                "Le fichier précédent a été restauré."
            )

    def rename_model(self):

        if self._renaming_in_progress:
            # Mission 163: reentrant call — e.g. a second editingFinished
            # firing while QMessageBox.critical()'s nested event loop is
            # still running below. No new Manager call, no new dialog, no
            # extra reconciliation: the in-flight call below remains
            # solely responsible for the final state.
            return

        active_model = self.model_manager.active_model

        if active_model is None or self._name_editor_owner_id != active_model.model_id:
            # Mission 163: nothing active, or name_edit's content was
            # loaded for a different identity than the one currently
            # active — never send this text to update_name() for the
            # wrong (or no) target. Existence is checked on the object
            # itself, never inferred from active_model_id alone.
            self._reload_name_editor()
            return

        self._renaming_in_progress = True
        try:
            # Mission 070: update_name() rolls back Model.name before
            # re-raising on a save() failure.
            try:
                self.model_manager.update_name(self.name_edit.text())
            except WorkspaceManagerError as exc:
                QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Impossible d'enregistrer le renommage dans le projet : {exc}\n"
                    "Le nom précédent a été restauré."
                )
        finally:
            # Mission 163: reconciles name_edit with whatever is now
            # canonical — success, idempotent no-op, or the rolled-back
            # previous name on failure — regardless of focus. Never
            # re-derived from a value captured for an earlier context.
            try:
                self._reload_name_editor()
            finally:
                self._renaming_in_progress = False

    def _reload_name_editor(self):
        active_model = self.model_manager.active_model
        if active_model is None:
            self._name_editor_owner_id = None
            self._name_editor_loaded_value = ""
        else:
            self._name_editor_owner_id = active_model.model_id
            self._name_editor_loaded_value = active_model.name
        self.name_edit.setText(self._name_editor_loaded_value)

    def _has_unsaved_name_draft(self, active_model) -> bool:
        return (
            active_model is not None
            and self._name_editor_owner_id == active_model.model_id
            and self.name_edit.text() != self._name_editor_loaded_value
        )

    def update_models(self, _payload=None):

        models = sorted(
            self.model_manager.list_models(),
            key=lambda model: model["name"].lower(),
        )
        active_model = self.model_manager.active_model
        active_model_id = active_model.model_id if active_model is not None else None

        self.model_list.blockSignals(True)
        self.model_list.clear()

        for model in models:

            item = QListWidgetItem(model["name"])
            item.setData(Qt.UserRole, model["model_id"])

            self.model_list.addItem(item)

            if model["model_id"] == active_model_id:
                self.model_list.setCurrentItem(item)

        self.model_list.blockSignals(False)
        # Mission 063: blockSignals() above suppresses currentItemChanged,
        # so setCurrentItem()/clear() never reach on_model_selection_changed()
        # during a rebuild — the button's state must be recomputed here.
        self.delete_button.setEnabled(self.model_list.currentItem() is not None)

        # Mission 163: an unrelated refresh (any WORKSPACE_SAVED elsewhere
        # in the Workspace, WORKSPACE_RENAMED, MODEL_CREATED/SELECTED/
        # DELETED for a different entity...) must never overwrite an
        # in-progress, still-unsaved edit of name_edit for the SAME
        # active Model. Preservation requires the active object to
        # genuinely exist, its identity to match what name_edit was last
        # loaded for, and the displayed text to still differ from that
        # loaded value — never inferred from focus.
        if not self._has_unsaved_name_draft(active_model):
            self._reload_name_editor()

        self.file_path_edit.setText(
            active_model.file_path if active_model is not None else ""
        )
