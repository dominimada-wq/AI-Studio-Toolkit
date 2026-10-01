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


class WorkflowsPage(QWidget):

    def __init__(self, workflow_manager):
        super().__init__()

        self.workflow_manager = workflow_manager

        # Mission 163: tracks the identity/value name_edit was last
        # loaded for, and whether a rename commit is currently in
        # flight — see _reload_name_editor()/_has_unsaved_name_draft()/
        # rename_workflow() below.
        self._name_editor_owner_id = None
        self._name_editor_loaded_value = ""
        self._renaming_in_progress = False

        layout = QVBoxLayout(self)

        title = QLabel("Workflows")
        title.setStyleSheet("font-size:24px;font-weight:bold;")
        layout.addWidget(title)

        workflow_buttons = QHBoxLayout()

        self.new_button = QPushButton("Nouveau workflow")
        self.new_button.clicked.connect(self.create_workflow)

        self.delete_button = QPushButton("Supprimer")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_workflow)

        workflow_buttons.addWidget(self.new_button)
        workflow_buttons.addWidget(self.delete_button)

        layout.addLayout(workflow_buttons)

        self.workflow_list = QListWidget()
        self.workflow_list.currentItemChanged.connect(self.on_workflow_selection_changed)

        layout.addWidget(self.workflow_list)

        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self.rename_workflow)

        layout.addWidget(self.name_edit)

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setPlaceholderText("Aucun fichier sélectionné")

        layout.addWidget(self.file_path_edit)

        self.browse_button = QPushButton("Sélectionner un fichier")
        self.browse_button.clicked.connect(self.browse_file)

        layout.addWidget(self.browse_button)

    def create_workflow(self):

        name, ok = QInputDialog.getText(self, "Nouveau workflow", "Nom :")

        if not ok or not name.strip():
            return

        try:
            workflow = self.workflow_manager.create(name.strip())
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer le nouveau workflow dans le projet : {exc}\n"
                "Le workflow n'a pas été créé."
            )
            return

        if workflow is None:
            QMessageBox.warning(
                self,
                "Aucun projet ouvert",
                "Ouvrez ou créez un projet avant d'ajouter un workflow."
            )

    def delete_workflow(self):

        item = self.workflow_list.currentItem()

        if item is None:
            return

        box = QMessageBox(self)
        box.setWindowTitle("Supprimer le workflow ?")
        box.setText(
            f"Supprimer le workflow « {item.text()} » ? Cette action est irréversible."
        )
        delete_button = box.addButton("Supprimer", QMessageBox.AcceptRole)
        cancel_button = box.addButton("Annuler", QMessageBox.RejectRole)
        box.setDefaultButton(cancel_button)
        box.exec()

        if box.clickedButton() is not delete_button:
            return

        # Mission 068: delete() rolls back the Domain removal (and
        # active_workflow_id) before re-raising on a save() failure —
        # the workflow stays exactly where it was, so no refresh is
        # needed here beyond informing the user.
        try:
            self.workflow_manager.delete(item.data(Qt.UserRole))
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer la suppression dans le projet : {exc}\n"
                "Le workflow n'a pas été supprimé."
            )

    def on_workflow_selection_changed(self, current, previous):

        # Mission 063: "Supprimer" must always reflect whether there is
        # currently something to delete — set regardless of the early
        # return just below, unlike workflow_manager.select() itself.
        self.delete_button.setEnabled(current is not None)

        if current is None:
            return

        self.workflow_manager.select(current.data(Qt.UserRole))

    def browse_file(self):

        if self.workflow_manager.active_workflow_id is None:
            QMessageBox.warning(
                self,
                "Aucun workflow sélectionné",
                "Sélectionnez un workflow avant d'associer un fichier."
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner un fichier de workflow",
            "",
            "Workflows (*.json);;Tous les fichiers (*)"
        )

        if not file_path:
            return

        # Mission 070: update_file_path() rolls back Workflow.file_path
        # before re-raising on a save() failure. file_path_edit is only
        # ever written by update_workflows()'s own refresh, never
        # directly by this picker, so it was never showing the rejected
        # value — only the error needs surfacing here.
        try:
            self.workflow_manager.update_file_path(file_path)
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer le fichier dans le projet : {exc}\n"
                "Le fichier précédent a été restauré."
            )

    def rename_workflow(self):

        if self._renaming_in_progress:
            # Mission 163: reentrant call — e.g. a second editingFinished
            # firing while QMessageBox.critical()'s nested event loop is
            # still running below. No new Manager call, no new dialog, no
            # extra reconciliation: the in-flight call below remains
            # solely responsible for the final state.
            return

        active_workflow = self.workflow_manager.active_workflow

        if active_workflow is None or self._name_editor_owner_id != active_workflow.workflow_id:
            # Mission 163: nothing active, or name_edit's content was
            # loaded for a different identity than the one currently
            # active — never send this text to update_name() for the
            # wrong (or no) target. Existence is checked on the object
            # itself, never inferred from active_workflow_id alone.
            self._reload_name_editor()
            return

        self._renaming_in_progress = True
        try:
            # Mission 070: update_name() rolls back Workflow.name before
            # re-raising on a save() failure.
            try:
                self.workflow_manager.update_name(self.name_edit.text())
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
        active_workflow = self.workflow_manager.active_workflow
        if active_workflow is None:
            self._name_editor_owner_id = None
            self._name_editor_loaded_value = ""
        else:
            self._name_editor_owner_id = active_workflow.workflow_id
            self._name_editor_loaded_value = active_workflow.name
        self.name_edit.setText(self._name_editor_loaded_value)

    def _has_unsaved_name_draft(self, active_workflow) -> bool:
        return (
            active_workflow is not None
            and self._name_editor_owner_id == active_workflow.workflow_id
            and self.name_edit.text() != self._name_editor_loaded_value
        )

    def update_workflows(self, _payload=None):

        workflows = sorted(
            self.workflow_manager.list_workflows(),
            key=lambda workflow: workflow["name"].lower(),
        )
        active_workflow = self.workflow_manager.active_workflow
        active_workflow_id = (
            active_workflow.workflow_id if active_workflow is not None else None
        )

        self.workflow_list.blockSignals(True)
        self.workflow_list.clear()

        for workflow in workflows:

            item = QListWidgetItem(workflow["name"])
            item.setData(Qt.UserRole, workflow["workflow_id"])

            self.workflow_list.addItem(item)

            if workflow["workflow_id"] == active_workflow_id:
                self.workflow_list.setCurrentItem(item)

        self.workflow_list.blockSignals(False)
        # Mission 063: blockSignals() above suppresses currentItemChanged,
        # so setCurrentItem()/clear() never reach on_workflow_selection_changed()
        # during a rebuild — the button's state must be recomputed here.
        self.delete_button.setEnabled(self.workflow_list.currentItem() is not None)

        # Mission 163: an unrelated refresh (any WORKSPACE_SAVED elsewhere
        # in the Workspace, WORKSPACE_RENAMED, WORKFLOW_CREATED/SELECTED/
        # DELETED for a different entity...) must never overwrite an
        # in-progress, still-unsaved edit of name_edit for the SAME
        # active Workflow. Preservation requires the active object to
        # genuinely exist, its identity to match what name_edit was last
        # loaded for, and the displayed text to still differ from that
        # loaded value — never inferred from focus.
        if not self._has_unsaved_name_draft(active_workflow):
            self._reload_name_editor()

        self.file_path_edit.setText(
            active_workflow.file_path if active_workflow is not None else ""
        )
