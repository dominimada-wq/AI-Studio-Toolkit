from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QSpinBox,
    QFileDialog,
    QInputDialog,
    QMessageBox,
)

from src.engines.onetrainer_config import OneTrainerConfigError
from src.managers.training_manager import (
    TRAINING_ARCHITECTURE_SD15,
    TRAINING_ARCHITECTURE_SDXL,
    TRAINING_ARCHITECTURE_FLUX,
    TRAINING_ARCHITECTURES,
    TrainingPreparationError,
)
from src.managers.workspace_manager import WorkspaceManagerError

# Mission 097 section 3.7: architecture-appropriate resolution
# suggestions — confirmed against OneTrainer's own real shipped LoRA
# presets ("#sd 1.5 LoRA.json"/"#sdxl 1.0 LoRA.json"/"#flux LoRA.json"),
# applied to resolution_spinbox the moment an architecture is chosen
# (never stored as a Training default — see Training.resolution's own
# docstring). A value the architect then changes manually is never
# overwritten again by this same suggestion.
_SUGGESTED_RESOLUTION_BY_ARCHITECTURE = {
    TRAINING_ARCHITECTURE_SD15: 512,
    TRAINING_ARCHITECTURE_SDXL: 1024,
    TRAINING_ARCHITECTURE_FLUX: 768,
}


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
        self.delete_button.setEnabled(False)
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

        # Mission 097: generic training hyperparameters — an explicit
        # "Enregistrer" commit, same pattern as LoRAPage.save_metadata()
        # (Mission 073's combined multi-field TrainingManager.update()),
        # never an immediate per-field commit like name_edit above.
        #
        # Mission 097 crash investigation (docs/missions/MISSION_097.md):
        # regrouped into a single QFormLayout (established pattern — see
        # LoRAPage.metadata_form) instead of one QHBoxLayout per field.
        # This is a structural simplification (same fields, same
        # behavior, fewer QLayout container objects) — it does not by
        # itself fix the native crash investigated in that mission; the
        # actual fix was to the test-only Qt dialog safety net.
        base_model_field = QHBoxLayout()

        self.base_model_edit = QLineEdit()
        self.base_model_browse_button = QPushButton("Parcourir un fichier…")
        self.base_model_browse_button.clicked.connect(self.browse_base_model_source)

        base_model_field.addWidget(self.base_model_edit)
        base_model_field.addWidget(self.base_model_browse_button)

        self.architecture_combo = QComboBox()
        self.architecture_combo.addItems(TRAINING_ARCHITECTURES)
        self.architecture_combo.setCurrentIndex(-1)
        self.architecture_combo.currentTextChanged.connect(self.on_architecture_changed)

        self.resolution_spinbox = QSpinBox()
        self.resolution_spinbox.setRange(64, 4096)
        self.resolution_spinbox.setSingleStep(64)

        self.epochs_spinbox = QSpinBox()
        self.epochs_spinbox.setRange(1, 10000)

        self.learning_rate_spinbox = QDoubleSpinBox()
        self.learning_rate_spinbox.setRange(0.0, 1.0)
        self.learning_rate_spinbox.setDecimals(6)
        self.learning_rate_spinbox.setSingleStep(0.0001)

        self.lora_rank_spinbox = QSpinBox()
        self.lora_rank_spinbox.setRange(1, 256)

        self.lora_alpha_spinbox = QDoubleSpinBox()
        self.lora_alpha_spinbox.setRange(0.0, 256.0)
        self.lora_alpha_spinbox.setDecimals(2)

        self.trigger_word_edit = QLineEdit()

        training_form = QFormLayout()
        training_form.addRow("Modèle de base :", base_model_field)
        training_form.addRow("Architecture :", self.architecture_combo)
        training_form.addRow("Résolution :", self.resolution_spinbox)
        training_form.addRow("Epochs :", self.epochs_spinbox)
        training_form.addRow("Learning rate :", self.learning_rate_spinbox)
        training_form.addRow("LoRA rank :", self.lora_rank_spinbox)
        training_form.addRow("LoRA alpha :", self.lora_alpha_spinbox)
        training_form.addRow("Trigger word :", self.trigger_word_edit)

        layout.addLayout(training_form)

        self.save_parameters_button = QPushButton("Enregistrer les paramètres d'entraînement")
        self.save_parameters_button.setEnabled(False)
        self.save_parameters_button.clicked.connect(self.save_training_parameters)

        layout.addWidget(self.save_parameters_button)

        # Mission 097: the mission's one orchestration entry point —
        # materializes the Dataset, builds and writes the OneTrainer
        # configuration, never starts OneTrainer (see MISSION_097.md
        # section 7/8 for the explicit boundary).
        self.prepare_config_button = QPushButton("Préparer la configuration OneTrainer")
        self.prepare_config_button.setEnabled(False)
        self.prepare_config_button.clicked.connect(self.prepare_onetrainer_config)

        layout.addWidget(self.prepare_config_button)

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

        try:
            training = self.training_manager.create(name.strip(), dataset_id)
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer la nouvelle session dans le projet : {exc}\n"
                "La session n'a pas été créée."
            )
            return

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

        # Mission 070: update_name() rolls back Training.name before
        # re-raising on a save() failure — update_trainings() redraws
        # name_edit from that rolled-back Domain state, so no manual
        # widget restoration is needed beyond informing the user.
        try:
            self.training_manager.update_name(self.name_edit.text())
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer le renommage dans le projet : {exc}\n"
                "Le nom précédent a été restauré."
            )
            self.update_trainings()

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

        # Mission 068: delete() rolls back the Domain removal (and
        # active_training_id) before re-raising on a save() failure —
        # the training stays exactly where it was, so no refresh is
        # needed here beyond informing the user.
        try:
            self.training_manager.delete(item.data(Qt.UserRole))
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer la suppression dans le projet : {exc}\n"
                "La session d'entraînement n'a pas été supprimée."
            )

    def on_training_selection_changed(self, current, previous):

        # Mission 063: "Supprimer" must always reflect whether there is
        # currently something to delete — set regardless of the early
        # return just below, unlike training_manager.select() itself.
        self.delete_button.setEnabled(current is not None)
        # Mission 097: same treatment for the two new actions — nothing
        # to save or prepare without an active training.
        self.save_parameters_button.setEnabled(current is not None)
        self.prepare_config_button.setEnabled(current is not None)

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
        active_training = None

        for training in trainings:

            item = QListWidgetItem(training["name"])
            item.setData(Qt.UserRole, training["training_id"])

            self.training_list.addItem(item)

            if training["training_id"] == active_training_id:
                self.training_list.setCurrentItem(item)
                active_dataset_id = training["dataset_id"]
                active_name = training["name"]
                active_training = training

        self.training_list.blockSignals(False)
        # Mission 063: blockSignals() above suppresses currentItemChanged,
        # so setCurrentItem()/clear() never reach on_training_selection_changed()
        # during a rebuild — the buttons' state must be recomputed here.
        has_active = self.training_list.currentItem() is not None
        self.delete_button.setEnabled(has_active)
        self.save_parameters_button.setEnabled(has_active)
        self.prepare_config_button.setEnabled(has_active)

        self.name_edit.setText(active_name)
        self.dataset_label.setText(self._describe_dataset(active_dataset_id))

        # Mission 097: blockSignals() on architecture_combo — reloading
        # a training's own saved architecture must never trigger
        # on_architecture_changed()'s resolution suggestion, which would
        # silently overwrite whatever resolution was actually saved.
        self.base_model_edit.setText(active_training["base_model_source"] if active_training else "")

        self.architecture_combo.blockSignals(True)
        architecture = active_training["architecture"] if active_training else ""
        index = self.architecture_combo.findText(architecture) if architecture else -1
        self.architecture_combo.setCurrentIndex(index)
        self.architecture_combo.blockSignals(False)

        # Mission 097: Training.resolution's own "0 means not yet
        # configured" sentinel (see its docstring) is a Domain-level
        # concept only — resolution_spinbox's range starts at 64 (no
        # real resolution is ever meaningfully below that), so 0 is
        # never displayed literally; a genuinely unset training simply
        # shows 64 until an architecture suggests a real value (see
        # on_architecture_changed() below) or the architect edits it.
        saved_resolution = active_training["resolution"] if active_training else 0
        self.resolution_spinbox.setValue(saved_resolution if saved_resolution else 64)
        self.epochs_spinbox.setValue(active_training["epochs"] if active_training else 1)
        self.learning_rate_spinbox.setValue(active_training["learning_rate"] if active_training else 0.0)
        self.lora_rank_spinbox.setValue(active_training["lora_rank"] if active_training else 1)
        self.lora_alpha_spinbox.setValue(active_training["lora_alpha"] if active_training else 0.0)
        self.trigger_word_edit.setText(active_training["trigger_word"] if active_training else "")

    def _describe_dataset(self, dataset_id):

        if not dataset_id:
            return ""

        for dataset in self.dataset_manager.list_datasets():
            if dataset["dataset_id"] == dataset_id:
                return f"Dataset : {dataset['name']} [{dataset_id[:8]}]"

        return f"Dataset introuvable [{dataset_id}]"

    def browse_base_model_source(self):
        # Mission 097 section 3.3: only the local-file form is actively
        # exposed by this mission's UI — a Diffusers folder or a Hugging
        # Face identifier both remain reachable by typing/pasting
        # directly into base_model_edit, deliberately not offered a
        # dedicated picker here (see MISSION_097.md section 3.3 for the
        # scope decision).
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner un modèle de base",
            "",
            "Modèles (*.safetensors *.ckpt)"
        )

        if not file_path:
            return

        self.base_model_edit.setText(file_path)

    def on_architecture_changed(self, architecture):
        # Mission 097 section 3.7: only ever fires on a genuine user
        # selection — update_trainings() blocks this signal while
        # reloading a training's own saved architecture, so a stored
        # resolution is never silently overwritten by this suggestion.
        suggested_resolution = _SUGGESTED_RESOLUTION_BY_ARCHITECTURE.get(architecture)
        if suggested_resolution is not None:
            self.resolution_spinbox.setValue(suggested_resolution)

    def save_training_parameters(self):

        if self.training_manager.active_training_id is None:
            return

        architecture = self.architecture_combo.currentText()

        try:
            self.training_manager.update(
                base_model_source=self.base_model_edit.text(),
                architecture=architecture,
                resolution=self.resolution_spinbox.value(),
                epochs=self.epochs_spinbox.value(),
                learning_rate=self.learning_rate_spinbox.value(),
                lora_rank=self.lora_rank_spinbox.value(),
                lora_alpha=self.lora_alpha_spinbox.value(),
                trigger_word=self.trigger_word_edit.text(),
            )
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer les paramètres d'entraînement dans le projet : {exc}\n"
                "Les valeurs précédentes ont été restaurées."
            )
            self.update_trainings()

    def prepare_onetrainer_config(self):
        """
        Mission 097: the mission's one real orchestration action —
        materializes the active training's Dataset and writes a real
        OneTrainer configuration file. Never starts OneTrainer, never
        touches the network or the GPU (see MISSION_097.md section
        7/8) — this method's own body never imports or calls anything
        beyond TrainingManager.prepare_onetrainer_config().
        """

        training_id = self.training_manager.active_training_id

        if training_id is None:
            return

        try:
            result = self.training_manager.prepare_onetrainer_config(training_id)
        except (TrainingPreparationError, OneTrainerConfigError) as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible de préparer la configuration OneTrainer : {exc}"
            )
            return

        QMessageBox.information(
            self,
            "Configuration préparée",
            "La configuration OneTrainer a été préparée avec succès :\n\n"
            f"Concept : {result.concept_path}\n"
            f"Configuration : {result.config_path}\n"
            f"Résultat attendu : {result.output_path}\n\n"
            "Aucun entraînement n'a été lancé."
        )
