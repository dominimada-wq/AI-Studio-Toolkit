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
    QMessageBox,
)


class TrainingPage(QWidget):

    def __init__(self, training_manager, dataset_manager):
        super().__init__()

        self.training_manager = training_manager
        self.dataset_manager = dataset_manager

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

        self.dataset_label = QLabel("")

        layout.addWidget(self.dataset_label)

    def create_training(self):

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
            QMessageBox.warning(
                self,
                "Aucun personnage actif",
                "Sélectionnez un personnage avant de créer une session d'entraînement."
            )

    def delete_training(self):

        item = self.training_list.currentItem()

        if item is None:
            return

        self.training_manager.delete(item.data(Qt.UserRole))

    def on_training_selection_changed(self, current, previous):

        if current is None:
            return

        self.training_manager.select(current.data(Qt.UserRole))

    def update_trainings(self, _payload=None):

        trainings = self.training_manager.list_trainings()
        active_training_id = self.training_manager.active_training_id

        self.training_list.blockSignals(True)
        self.training_list.clear()

        active_dataset_id = ""

        for training in trainings:

            item = QListWidgetItem(training["name"])
            item.setData(Qt.UserRole, training["training_id"])

            self.training_list.addItem(item)

            if training["training_id"] == active_training_id:
                self.training_list.setCurrentItem(item)
                active_dataset_id = training["dataset_id"]

        self.training_list.blockSignals(False)

        self.dataset_label.setText(self._describe_dataset(active_dataset_id))

    def _describe_dataset(self, dataset_id):

        if not dataset_id:
            return ""

        for dataset in self.dataset_manager.list_datasets():
            if dataset["dataset_id"] == dataset_id:
                return f"Dataset : {dataset['name']} [{dataset_id[:8]}]"

        return f"Dataset introuvable [{dataset_id}]"
