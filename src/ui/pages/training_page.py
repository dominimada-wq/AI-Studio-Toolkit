from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QInputDialog,
    QMessageBox,
)


class TrainingPage(QWidget):

    def __init__(self, training_manager, dataset_manager, workspace_manager):
        super().__init__()

        self.training_manager = training_manager
        self.dataset_manager = dataset_manager
        # Mission 036: source of authority for "no Workspace open" vs
        # "Workspace open without a principal Character" — see
        # create_training() below. Note: the "Aucun dataset disponible"
        # branch above it (list_datasets() empty) is a distinct,
        # out-of-scope ambiguity — see Mission 036 specification.
        self.workspace_manager = workspace_manager

        layout = QVBoxLayout(self)

        title = QLabel("Training")
        title.setStyleSheet("font-size:24px;font-weight:bold;")
        layout.addWidget(title)

        training_buttons = QHBoxLayout()

        self.new_button = QPushButton("Nouvelle session")
        self.new_button.clicked.connect(self.create_training)

        self.delete_button = QPushButton("Supprimer")
        self.delete_button.clicked.connect(self.delete_training)

        training_buttons.addWidget(self.new_button)
        training_buttons.addWidget(self.delete_button)

        layout.addLayout(training_buttons)

        self.training_list = QListWidget()
        self.training_list.currentItemChanged.connect(self.on_training_selection_changed)

        layout.addWidget(self.training_list)

        # Mission 054: renaming is an immediate-commit edit, independent
        # of the Mission 051 alphabetical sort and of dataset_label
        # below — mirrors PromptsPage.name_edit.
        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self.rename_training)

        layout.addWidget(self.name_edit)

        self.dataset_label = QLabel("")

        layout.addWidget(self.dataset_label)

    def create_training(self):

        # Mission 037: must precede the dataset lookup below — otherwise
        # "Aucun dataset disponible" fires when no Workspace is open at
        # all (DatasetManager.datasets is [] in both cases), masking the
        # real cause. See the Mission 037 specification for the full
        # ordering rationale.
        if not self.workspace_manager.opened:
            QMessageBox.warning(
                self,
                "Aucun projet ouvert",
                "Ouvrez ou créez un projet avant de créer une session d'entraînement."
            )
            return

        datasets = self.dataset_manager.list_datasets()

        if not datasets:
            QMessageBox.warning(
                self,
                "Aucun dataset disponible",
                "Créez un dataset avant de créer une session d'entraînement."
            )
            return

        # Labels must stay unique even when two datasets share the same
        # name — the dataset_id fragment disambiguates them. The
        # mapping is local to this dialog, never persisted.
        label_to_id = {
            f"{dataset['name']} [{dataset['dataset_id'][:8]}]": dataset['dataset_id']
            for dataset in datasets
        }
        labels = list(label_to_id.keys())

        label, ok = QInputDialog.getItem(
            self, "Sélectionner un dataset", "Dataset :", labels, 0, False
        )

        if not ok or not label:
            return

        dataset_id = label_to_id[label]

        name, ok = QInputDialog.getText(self, "Nouvelle session", "Nom :")

        if not ok or not name.strip():
            return

        training = self.training_manager.create(name.strip(), dataset_id)

        if training is None:
            # TrainingManager.create() now follows the Workspace's
            # principal Character (Mission 026/028), not a manual
            # selection the hidden multi-character UI no longer offers a
            # way to make — this can only fire for the genuine edge case
            # of a Workspace with zero Character at all (workspace_manager
            # is already guaranteed open at this point by the guard above).
            QMessageBox.warning(
                self,
                "Aucun personnage",
                "Ce projet ne possède aucun personnage — créez-en un depuis Characters avant de créer une session d'entraînement."
            )

    def rename_training(self):

        if self.training_manager.active_training_id is None:
            return

        self.training_manager.update_name(self.name_edit.text())

    def delete_training(self):

        item = self.training_list.currentItem()

        if item is None:
            return

        box = QMessageBox(self)
        box.setWindowTitle("Supprimer la session d'entraînement ?")
        box.setText(
            f"Supprimer la session d'entraînement « {item.text()} » ? "
            "Cette action est irréversible."
        )
        delete_button = box.addButton("Supprimer", QMessageBox.AcceptRole)
        cancel_button = box.addButton("Annuler", QMessageBox.RejectRole)
        box.setDefaultButton(cancel_button)
        box.exec()

        if box.clickedButton() is not delete_button:
            return

        self.training_manager.delete(item.data(Qt.UserRole))

    def on_training_selection_changed(self, current, previous):

        if current is None:
            return

        self.training_manager.select(current.data(Qt.UserRole))

    def update_trainings(self, _payload=None):

        trainings = sorted(
            self.training_manager.list_trainings(),
            key=lambda training: training["name"].lower(),
        )
        active_training_id = self.training_manager.active_training_id

        self.training_list.blockSignals(True)
        self.training_list.clear()

        active_dataset_id = ""
        active_name = ""

        for training in trainings:

            item = QListWidgetItem(training["name"])
            item.setData(Qt.UserRole, training["training_id"])

            self.training_list.addItem(item)

            if training["training_id"] == active_training_id:
                self.training_list.setCurrentItem(item)
                active_dataset_id = training["dataset_id"]
                active_name = training["name"]

        self.training_list.blockSignals(False)

        self.name_edit.setText(active_name)
        self.dataset_label.setText(self._describe_dataset(active_dataset_id))

    def _describe_dataset(self, dataset_id):

        if not dataset_id:
            return ""

        for dataset in self.dataset_manager.list_datasets():
            if dataset["dataset_id"] == dataset_id:
                return f"Dataset : {dataset['name']} [{dataset_id[:8]}]"

        return f"Dataset introuvable [{dataset_id}]"
