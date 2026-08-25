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


class WorkflowsPage(QWidget):

    def __init__(self, workflow_manager):
        super().__init__()

        self.workflow_manager = workflow_manager

        layout = QVBoxLayout(self)

        title = QLabel("Workflows")
        title.setStyleSheet("font-size:24px;font-weight:bold;")
        layout.addWidget(title)

        workflow_buttons = QHBoxLayout()

        self.new_button = QPushButton("Nouveau workflow")
        self.new_button.clicked.connect(self.create_workflow)

        self.delete_button = QPushButton("Supprimer")
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

        workflow = self.workflow_manager.create(name.strip())

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

        self.workflow_manager.delete(item.data(Qt.UserRole))

    def on_workflow_selection_changed(self, current, previous):

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

        self.workflow_manager.update_file_path(file_path)

    def rename_workflow(self):

        if self.workflow_manager.active_workflow_id is None:
            return

        self.workflow_manager.update_name(self.name_edit.text())

    def update_workflows(self, _payload=None):

        workflows = sorted(
            self.workflow_manager.list_workflows(),
            key=lambda workflow: workflow["name"].lower(),
        )
        active_workflow_id = self.workflow_manager.active_workflow_id

        self.workflow_list.blockSignals(True)
        self.workflow_list.clear()

        active_name = ""
        active_file_path = ""

        for workflow in workflows:

            item = QListWidgetItem(workflow["name"])
            item.setData(Qt.UserRole, workflow["workflow_id"])

            self.workflow_list.addItem(item)

            if workflow["workflow_id"] == active_workflow_id:
                self.workflow_list.setCurrentItem(item)
                active_name = workflow["name"]
                active_file_path = workflow["file_path"]

        self.workflow_list.blockSignals(False)

        self.name_edit.setText(active_name)
        self.file_path_edit.setText(active_file_path)
