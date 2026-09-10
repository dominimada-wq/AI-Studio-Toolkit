from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
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
    QPlainTextEdit,
)

from src.engines.onetrainer_config import OneTrainerConfigError
from src.engines.onetrainer_launch import OneTrainerLaunchError, resolve_onetrainer_launch
from src.managers.lora_library_manager import LoRALibraryError
from src.managers.training_manager import (
    TRAINING_ARCHITECTURE_SD15,
    TRAINING_ARCHITECTURE_SDXL,
    TRAINING_ARCHITECTURE_FLUX,
    TRAINING_ARCHITECTURES,
    TRAINING_JOB_STATE_RUNNING,
    TRAINING_JOB_STATE_SUCCEEDED,
    TrainingJobError,
    TrainingPreparationError,
)
from src.managers.workspace_manager import WorkspaceManagerError
from src.ui.training_job_runner import TrainingJobRunner
from src.utils.lora_library_path import LoRALibraryPathError, resolve_lora_library_root

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

    # Mission 109: local Presentation-layer signal, mirror of
    # PromptsPage.send_to_inference_requested (Mission 033) — carries
    # only the lora_id of a Job's already-imported LoRA, never a Domain
    # mutation. MainWindow is the sole subscriber/mediator; TrainingPage
    # never references InferencePage directly.
    use_lora_in_inference_requested = Signal(str)

    def __init__(
        self,
        training_manager,
        dataset_manager,
        workspace_manager,
        application_settings_manager,
        lora_library_manager,
    ):
        super().__init__()

        self.training_manager = training_manager
        self.dataset_manager = dataset_manager
        # Mission 036: source of authority for "no Workspace open" vs
        # "Workspace open without a principal Character" — see
        # create_training() below. Note: the "Aucun dataset disponible"
        # branch above it (list_datasets() empty) is a distinct,
        # out-of-scope ambiguity — see Mission 036 specification.
        self.workspace_manager = workspace_manager
        # Mission 100: the sole source of ApplicationSettings.onetrainer_path
        # — never ApplicationSettings.python_path (see
        # src/engines/onetrainer_launch.py's own docstring for why).
        self.application_settings_manager = application_settings_manager
        # Mission 103: same Central LoRA Library the Bibliothèque tab and
        # InferencePage already share — reused as-is, no new storage.
        self.lora_library_manager = lora_library_manager

        # Mission 100: runtime-only, never persisted — the runner/job
        # this Page is currently watching, at most one at a time (same
        # "single active operation" shape as GenerationManager._busy).
        # None whenever no Job started from this Page is in flight.
        self._active_runner = None
        self._active_job_id = None
        self._cancel_in_flight = False

        # Mission 105: dirty-draft protection for the 8 persistent
        # parameters below, same canonical pattern as CharactersPage/
        # LoRAPage/SettingsPage (Mission 078)/PromptsPage (Mission 038) —
        # a single flag for the whole form, never one per field.
        # _loaded_training_id distinguishes a non-destructive refresh
        # (active_training_id unchanged) from a genuine context change,
        # exactly like _loaded_lora_id/_loaded_prompt_id elsewhere.
        self._dirty = False
        self._loaded_training_id = None

        # Mission 105: distinct from _dirty — tracks whether the
        # persisted Training may have changed, in this session, since
        # the last successful prepare_onetrainer_config() call (which
        # is the only thing that writes onetrainer_config.json).
        # Presentation/session-only, never a persistence-freshness
        # guarantee across a restart — see MISSION_105.md section 3.5.
        self._config_stale = False

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
        self.base_model_edit.textChanged.connect(self._on_training_parameters_changed)
        self.base_model_browse_button = QPushButton("Parcourir un fichier…")
        self.base_model_browse_button.clicked.connect(self.browse_base_model_source)

        base_model_field.addWidget(self.base_model_edit)
        base_model_field.addWidget(self.base_model_browse_button)

        self.architecture_combo = QComboBox()
        self.architecture_combo.addItems(TRAINING_ARCHITECTURES)
        self.architecture_combo.setCurrentIndex(-1)
        # Mission 105: on_architecture_changed() itself now also marks
        # the form dirty (see its own body below) — a single connection,
        # never a second one to the same signal.
        self.architecture_combo.currentTextChanged.connect(self.on_architecture_changed)

        self.resolution_spinbox = QSpinBox()
        self.resolution_spinbox.setRange(64, 4096)
        self.resolution_spinbox.setSingleStep(64)
        self.resolution_spinbox.valueChanged.connect(self._on_training_parameters_changed)

        self.epochs_spinbox = QSpinBox()
        self.epochs_spinbox.setRange(1, 10000)
        self.epochs_spinbox.valueChanged.connect(self._on_training_parameters_changed)

        self.learning_rate_spinbox = QDoubleSpinBox()
        self.learning_rate_spinbox.setRange(0.0, 1.0)
        self.learning_rate_spinbox.setDecimals(6)
        self.learning_rate_spinbox.setSingleStep(0.0001)
        self.learning_rate_spinbox.valueChanged.connect(self._on_training_parameters_changed)

        self.lora_rank_spinbox = QSpinBox()
        self.lora_rank_spinbox.setRange(1, 256)
        self.lora_rank_spinbox.valueChanged.connect(self._on_training_parameters_changed)

        self.lora_alpha_spinbox = QDoubleSpinBox()
        self.lora_alpha_spinbox.setRange(0.0, 256.0)
        self.lora_alpha_spinbox.setDecimals(2)
        self.lora_alpha_spinbox.valueChanged.connect(self._on_training_parameters_changed)

        self.trigger_word_edit = QLineEdit()
        self.trigger_word_edit.textChanged.connect(self._on_training_parameters_changed)

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

        # Mission 100: minimal execution UI — Start/Cancel, a coarse
        # state label, and raw stdout/stderr logs. No percentage bar
        # (callback.pipe is not consumed — see MISSION_100.md section
        # 7): if OneTrainer's own tqdm progress text is exploitable, it
        # simply appears as-is in job_log_view below, never parsed.
        job_buttons = QHBoxLayout()

        self.start_training_button = QPushButton("Démarrer l'entraînement")
        self.start_training_button.setEnabled(False)
        self.start_training_button.clicked.connect(self.start_training)

        self.cancel_training_button = QPushButton("Annuler")
        self.cancel_training_button.setEnabled(False)
        self.cancel_training_button.clicked.connect(self.cancel_training)

        job_buttons.addWidget(self.start_training_button)
        job_buttons.addWidget(self.cancel_training_button)

        layout.addLayout(job_buttons)

        self.job_state_label = QLabel("")

        layout.addWidget(self.job_state_label)

        self.job_log_view = QPlainTextEdit()
        self.job_log_view.setReadOnly(True)
        self.job_log_view.setMaximumBlockCount(2000)

        layout.addWidget(self.job_log_view)

        # Mission 103: minimal, persistent list of every TrainingJob of
        # the selected Training — never a log viewer or a monitoring
        # dashboard (MISSION_103.md section 3.2). Read directly from
        # Training.jobs (already Workspace-persisted since Mission 100),
        # no new storage. A single contextual action below acts on
        # whichever Job is currently selected in this list, same
        # established pattern as training_list/delete_button above.
        jobs_label = QLabel("Résultats des entraînements :")
        layout.addWidget(jobs_label)

        self.jobs_list = QListWidget()
        self.jobs_list.currentItemChanged.connect(self._on_job_selection_changed)

        layout.addWidget(self.jobs_list)

        self.import_lora_button = QPushButton("Importer dans la Bibliothèque LoRA centrale")
        self.import_lora_button.setEnabled(False)
        self.import_lora_button.clicked.connect(self.import_selected_job_to_library)

        layout.addWidget(self.import_lora_button)

        # Mission 109: distinct action from the import above — available
        # for any Job whose imported_lora_id still resolves to a real
        # Central Library LoRA, not only right after a fresh import.
        self.use_lora_in_inference_button = QPushButton("Utiliser dans Inference")
        self.use_lora_in_inference_button.setEnabled(False)
        self.use_lora_in_inference_button.clicked.connect(self.use_selected_lora_in_inference)

        layout.addWidget(self.use_lora_in_inference_button)

        self._refresh_job_controls()

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
        # Mission 105: the currently displayed parameter draft belongs to
        # this exact Training only when it is still the loaded one (it
        # always is here — this is the same list item currentItem() just
        # returned) — a single adapted dialog rather than a second,
        # separate confirmation, mirroring LoRAPage.delete_lora()'s intent
        # without stacking two dialogs in a row.
        if self._dirty and item.data(Qt.UserRole) == self._loaded_training_id:
            box.setText(
                f"Supprimer la session d'entraînement « {item.text()} » ? Cette "
                "action est irréversible et les paramètres non enregistrés de "
                "cette session seront perdus."
            )
        else:
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
            self._refresh_job_controls()
            return

        # Mission 105: captured now, before any Manager call below can
        # reentrantly trigger update_trainings() -> training_list.clear(),
        # which deletes the underlying C++ QListWidgetItem `current`
        # wraps (e.g. save_training_parameters() calls TrainingManager.
        # update(), which publishes WORKSPACE_SAVED synchronously).
        # Reading current.data() again afterward would then raise. Same
        # precedent as LoRAPage/PromptsPage.
        target_training_id = current.data(Qt.UserRole)

        if self._dirty:
            choice = self._confirm_discard_training_before_switch()

            if choice == QMessageBox.Cancel:
                # Mission 105: training_manager.select() is never called
                # — active_training_id stays untouched. Revert the
                # widget's own native selection (already changed by Qt
                # before this handler ran) back to `previous`, with
                # signals blocked to avoid recursively re-entering this
                # same handler.
                self.training_list.blockSignals(True)
                self.training_list.setCurrentItem(previous)
                self.training_list.blockSignals(False)
                self.delete_button.setEnabled(previous is not None)
                self.save_parameters_button.setEnabled(previous is not None)
                self.prepare_config_button.setEnabled(previous is not None)
                return

            if choice == QMessageBox.Save:
                if not self.save_training_parameters():
                    # save_training_parameters()'s own error dialog is
                    # already shown, and it has already resynced the
                    # fields to the rolled-back Domain state — revert
                    # only the visual selection, exactly like Cancel
                    # above, so the switch itself does not proceed.
                    self.training_list.blockSignals(True)
                    self.training_list.setCurrentItem(previous)
                    self.training_list.blockSignals(False)
                    self.delete_button.setEnabled(previous is not None)
                    self.save_parameters_button.setEnabled(previous is not None)
                    self.prepare_config_button.setEnabled(previous is not None)
                    return

            self._dirty = False

        self.training_manager.select(target_training_id)
        self._refresh_job_controls()

    def _confirm_discard_training_before_switch(self):
        box = QMessageBox(self)
        box.setWindowTitle("Modifications non enregistrées")
        box.setText(
            "Les paramètres d'entraînement actuels contiennent des "
            "modifications non enregistrées. Que souhaitez-vous faire ?"
        )
        box.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        box.setButtonText(QMessageBox.Save, "Enregistrer")
        box.setButtonText(QMessageBox.Discard, "Ignorer les modifications")
        box.setButtonText(QMessageBox.Cancel, "Annuler")
        box.setDefaultButton(QMessageBox.Cancel)
        return box.exec()

    def confirm_context_change(self) -> bool:
        """
        Mission 105: same role/contract as LoRAPage.confirm_context_change()
        (Mission 078) — called by MainWindow before a Workspace switch
        (new_project()/open_project()) that would otherwise let
        reset_for_context_change() silently discard an unsaved parameter
        draft once current_workspace is replaced, too late for a genuine
        Save or Cancel. Also reused, same contract, from closeEvent()
        before closing the whole application — after the orthogonal
        confirm_no_active_training() guard (Mission 100): a genuinely
        active Job has produced no result yet, so it cannot be protected
        by any dirty-draft guard.
        """
        if not self._dirty:
            return True

        choice = self._confirm_discard_training_before_switch()

        if choice == QMessageBox.Cancel:
            return False

        if choice == QMessageBox.Save:
            if not self.save_training_parameters():
                # save_training_parameters()'s own error dialog is
                # already shown — never re-inspect _dirty here (it is
                # already False again, resynced to the rolled-back
                # Domain state by the same failure branch).
                return False

        self._dirty = False
        return True

    def update_trainings(self, _payload=None):
        # Mission 105: subscribed (see main_window.py) only to
        # WORKSPACE_SAVED/RENAMED, CHARACTER_CREATED and TRAINING_CREATED/
        # SELECTED/DELETED — WORKSPACE_CREATED/OPENED/CLOSED and
        # CHARACTER_SELECTED/DELETED are handled exclusively by
        # reset_for_context_change() below, and a real Training switch is
        # handled by on_training_selection_changed() before
        # TRAINING_SELECTED is even published — so this dirty-draft
        # protection never depends on subscriber ordering.

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

        # Mission 105: name_edit/dataset_label have no dirty-state of
        # their own (name_edit saves immediately on blur, mirroring
        # LoRAPage) — always resynced regardless of _dirty, unchanged
        # from their pre-existing behavior.
        self.name_edit.setText(active_name)
        self.dataset_label.setText(self._describe_dataset(active_dataset_id))

        if active_training_id != self._loaded_training_id or not self._dirty:
            # Either the active Training genuinely changed (e.g.
            # TRAINING_DELETED cleared it, or TRAINING_SELECTED/
            # TRAINING_CREATED made a different one active) — the 8
            # parameter fields must reflect the new Training, never the
            # previous one's draft — or nothing is actually dirty, in
            # which case refreshing is harmless and must still reflect a
            # mutation applied directly through TrainingManager.update()
            # outside this Page's own save_training_parameters() (e.g.
            # by another code path or test).
            self._load_training_parameters(active_training)
            self._loaded_training_id = active_training_id
        # else: a real unsaved parameter draft on the still-active
        # Training — non-destructive refresh (e.g. WORKSPACE_SAVED fired
        # by an unrelated Dataset/Character/etc. mutation elsewhere) —
        # the 8 parameter fields are left untouched.

        self._refresh_job_controls()

    def _load_training_parameters(self, active_training):
        # Mission 105: unconditional — bypasses the parameters dirty-
        # state guard on purpose. Called whenever the active Training
        # actually changed (update_trainings()/reset_for_context_change())
        # or by a forced resync (_force_refresh_training_parameters(),
        # used by save_training_parameters()'s failure-rollback path).
        # Mirrors LoRAPage._load_metadata_fields().
        fields = (
            self.base_model_edit,
            self.architecture_combo,
            self.resolution_spinbox,
            self.epochs_spinbox,
            self.learning_rate_spinbox,
            self.lora_rank_spinbox,
            self.lora_alpha_spinbox,
            self.trigger_word_edit,
        )

        for field in fields:
            field.blockSignals(True)

        self.base_model_edit.setText(active_training["base_model_source"] if active_training else "")

        architecture = active_training["architecture"] if active_training else ""
        index = self.architecture_combo.findText(architecture) if architecture else -1
        self.architecture_combo.setCurrentIndex(index)

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

        for field in fields:
            field.blockSignals(False)

        self._dirty = False
        self._config_stale = False

    def _force_refresh_training_parameters(self):
        # Mission 105: bypasses the dirty-state guard entirely — used by
        # save_training_parameters()'s failure-rollback path, which must
        # always reflect the just-restored Domain state, never a stale
        # or rejected view. Mirrors LoRAPage._force_refresh_lora(),
        # scoped to the 8 parameter fields only (training_list/name_edit/
        # dataset_label never change on this failure).
        active_training_id = self.training_manager.active_training_id
        active_training = None
        if active_training_id is not None:
            for training in self.training_manager.list_trainings():
                if training["training_id"] == active_training_id:
                    active_training = training
                    break

        self._load_training_parameters(active_training)
        self._loaded_training_id = active_training_id

    def reset_for_context_change(self, _payload=None):
        """
        Mission 105: subscribed by MainWindow to WORKSPACE_CREATED/
        OPENED/CLOSED and CHARACTER_SELECTED/DELETED — never to
        update_trainings()'s own events. A naive active_training_id vs
        _loaded_training_id comparison would wrongly read None == None
        as "nothing changed" when switching between two Workspaces that
        both happen to leave no Training active — silently carrying a
        stray draft across a genuine Workspace/Character switch. This
        method is therefore the sole, unconditional Presentation path
        for these 5 events, mirroring LoRAPage.reset_for_context_change()
        (Mission 078).
        """
        self.training_list.blockSignals(True)
        self.training_list.clear()
        self.training_list.blockSignals(False)

        self.delete_button.setEnabled(False)
        self.save_parameters_button.setEnabled(False)
        self.prepare_config_button.setEnabled(False)

        self.name_edit.setText("")
        self.dataset_label.setText("")

        self._load_training_parameters(None)
        self._loaded_training_id = None

        self._refresh_job_controls()

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
        # selection — update_trainings()/_load_training_parameters()
        # block this signal while reloading a training's own saved
        # architecture, so a stored resolution is never silently
        # overwritten by this suggestion, and a programmatic reload
        # never marks the form dirty by itself.
        #
        # Mission 105: marks the form dirty here rather than adding a
        # second connection to currentTextChanged — this is the only
        # place that signal is (and needs to be) handled.
        self._dirty = True

        suggested_resolution = _SUGGESTED_RESOLUTION_BY_ARCHITECTURE.get(architecture)
        if suggested_resolution is not None:
            self.resolution_spinbox.setValue(suggested_resolution)

    def _on_training_parameters_changed(self, _value=None):
        # Mission 105: connected to the textChanged/valueChanged signal
        # of each of the 8 parameter widgets except architecture_combo
        # (handled directly by on_architecture_changed() above). Never
        # fires during a programmatic load protected by
        # _load_training_parameters()'s blockSignals() — genuine user
        # editing (including browse_base_model_source()'s setText()) is
        # the only way this can run.
        self._dirty = True

    def save_training_parameters(self) -> bool:
        """
        Mission 105: returns True only on genuine success. On failure,
        the pre-existing (Mission 097) contract resyncs the widgets to
        the just-rolled-back Domain state and informs the user their
        edit was not kept — the same "discard and resync" contract
        LoRAPage.save_metadata() already uses, unlike PromptsPage.
        save_text()'s "preserve the draft" contract. This means _dirty
        ends up False either way (there is genuinely nothing left
        unsaved once the widgets reflect reality again) — callers that
        need to distinguish success from failure (prepare_onetrainer_
        config()/start_training() below) must check this return value,
        never re-inspect _dirty afterward.
        """

        if self.training_manager.active_training_id is None:
            return False

        architecture = self.architecture_combo.currentText()

        try:
            changed = self.training_manager.update(
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
            # Mission 105: unconditional resync to the just-rolled-back
            # Domain state — update_trainings() would wrongly skip this
            # while _dirty is still True and the active Training hasn't
            # changed, exactly the case _force_refresh_training_parameters()
            # exists to bypass (same precedent as LoRAPage's failure sites).
            self._force_refresh_training_parameters()
            return False

        # Mission 105: the save intent is satisfied here regardless of
        # update()'s own True/False return — its idempotent False (every
        # value already matches the persisted Training) still means
        # nothing is left unsaved from the UI's point of view. A real
        # change (True) means onetrainer_config.json, if any, may no
        # longer reflect this Training — see prepare_onetrainer_config()/
        # start_training() below, the only two consumers of
        # _config_stale.
        self._dirty = False
        if changed:
            self._config_stale = True

        return True

    def prepare_onetrainer_config(self):
        """
        Mission 097: the mission's one real orchestration action —
        materializes the active training's Dataset and writes a real
        OneTrainer configuration file. Never starts OneTrainer, never
        touches the network or the GPU (see MISSION_097.md section
        7/8) — this method's own body never imports or calls anything
        beyond TrainingManager.prepare_onetrainer_config().

        Mission 105: if the form is dirty, the currently displayed
        values are saved first — save_training_parameters()'s own
        failure already shows its own error dialog and returns False
        (never re-inspect _dirty afterward: a failed save resyncs the
        widgets to the rolled-back Domain state and clears _dirty too,
        same "discard and resync" contract as LoRAPage.save_metadata()),
        which this method treats as "stop here", never calling
        TrainingManager.prepare_onetrainer_config() against a save that
        did not actually happen.
        """

        training_id = self.training_manager.active_training_id

        if training_id is None:
            return

        if self._dirty:
            if not self.save_training_parameters():
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

        self._config_stale = False

        QMessageBox.information(
            self,
            "Configuration préparée",
            "La configuration OneTrainer a été préparée avec succès :\n\n"
            f"Concept : {result.concept_path}\n"
            f"Configuration : {result.config_path}\n"
            f"Résultat attendu : {result.output_path}\n\n"
            "Aucun entraînement n'a été lancé."
        )

    def is_training_active(self) -> bool:
        """
        Mission 100 section 11 (close guard): the Domain-level source of
        truth (TrainingManager.has_active_job()) — never this Page's own
        `self._active_runner`, which only reflects this particular Page
        instance's own in-flight Job, not the persisted Job state that
        survives across Page rebuilds within the same session.
        """
        return self.training_manager.has_active_job()

    def confirm_no_active_training(self, blocked_message: str) -> bool:
        """
        Mission 100 section 11: same True=proceed/False=abandon contract
        as InferencePage.confirm_no_active_generation() (Mission 085) —
        never merged with it, a different Manager/Domain entity entirely.
        """
        if not self.is_training_active():
            return True

        QMessageBox.warning(self, "Entraînement en cours", blocked_message)
        return False

    def start_training(self):
        """
        Mission 100: the mission's real execution entry point — creates
        a TrainingJob (Training-scoped Prepare stays untouched) and
        drives it via a TrainingJobRunner. Revalidates OneTrainer's
        launch preconditions itself (via the runner, section 6) even
        though start_training_button is only enabled when
        _refresh_job_controls() last saw them satisfied — a path valid
        when the UI was drawn may have become invalid by the time this
        runs.

        Mission 105: guarantees that the parameters visible at the
        moment Start is clicked are the ones actually used by the new
        Job. create_job() itself only ever reads the onetrainer_config.
        json already written by the last successful
        TrainingManager.prepare_onetrainer_config() call — never the
        widgets, never the Training object directly — so a dirty form
        is saved first, and a persisted change since the last Prepare
        in this session (_config_stale) triggers one more Prepare
        before create_job(), reusing TrainingManager.
        prepare_onetrainer_config() verbatim (never a second
        configuration-generation path). A clean, non-stale form keeps
        the exact historical behavior: no extra call before create_job().
        """
        training_id = self.training_manager.active_training_id

        if training_id is None or self._active_runner is not None:
            return

        if self._dirty:
            if not self.save_training_parameters():
                # save_training_parameters()'s own error dialog is
                # already shown — never re-inspect _dirty here (a
                # failed save resyncs the widgets and clears it too,
                # same contract as prepare_onetrainer_config() above) —
                # no Job is created against a save that did not happen.
                return

        if self._config_stale:
            try:
                self.training_manager.prepare_onetrainer_config(training_id)
            except (TrainingPreparationError, OneTrainerConfigError) as exc:
                QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Impossible de préparer la configuration OneTrainer avant "
                    f"le démarrage : {exc}"
                )
                return
            self._config_stale = False

        try:
            job = self.training_manager.create_job(training_id)
        except TrainingJobError as exc:
            QMessageBox.critical(self, "Erreur", f"Impossible de démarrer l'entraînement : {exc}")
            return
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer le démarrage de l'entraînement dans le projet : {exc}\n"
                "L'entraînement n'a pas été démarré."
            )
            return

        self._active_job_id = job.job_id
        self._cancel_in_flight = False
        self.job_log_view.clear()

        job_paths = self.training_manager.job_paths(training_id, job.job_id)
        onetrainer_path = self.application_settings_manager.settings.onetrainer_path

        self._active_runner = TrainingJobRunner(job_paths, onetrainer_path)
        self._active_runner.started.connect(self._on_job_started)
        self._active_runner.log_line.connect(self._on_job_log_line)
        self._active_runner.finished.connect(self._on_job_finished)
        self._active_runner.start()

        self._refresh_job_controls()

    def cancel_training(self):
        if self._active_runner is None:
            return

        self._cancel_in_flight = True
        self._active_runner.cancel()
        self._refresh_job_controls()

    def _on_job_started(self):
        # Mission 100 section 5.2: "running" is only ever set once the
        # OneTrainer subprocess is confirmed started by QProcess itself
        # — never assumed the moment start_training() returns.
        try:
            self.training_manager.update_job_state(self._active_job_id, TRAINING_JOB_STATE_RUNNING)
        except WorkspaceManagerError as exc:
            QMessageBox.warning(
                self,
                "Avertissement",
                f"L'entraînement a bien démarré mais son état n'a pas pu être enregistré "
                f"dans le projet : {exc}"
            )
        self._refresh_job_controls()

    def _on_job_log_line(self, line: str):
        self.job_log_view.appendPlainText(line)

    def _on_job_finished(self, state: str, error_message: str, final_output_path: str):
        kwargs = {}
        if error_message:
            kwargs["error_message"] = error_message
        if final_output_path:
            kwargs["final_output_path"] = final_output_path

        try:
            self.training_manager.update_job_state(self._active_job_id, state, **kwargs)
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer le résultat de l'entraînement dans le projet : {exc}"
            )

        self._active_runner = None
        self._active_job_id = None
        self._cancel_in_flight = False
        self._refresh_job_controls()

        if state == "succeeded":
            QMessageBox.information(
                self,
                "Entraînement terminé",
                f"Entraînement terminé avec succès.\n\nLoRA produit : {final_output_path}"
            )
        elif state == "failed":
            QMessageBox.critical(
                self,
                "Entraînement échoué",
                error_message or "L'entraînement a échoué pour une raison inconnue."
            )

    def _refresh_job_controls(self):
        """
        Mission 100 section 6 ("UI"): Start is disabled outright when
        OneTrainer is not configured — checked here, not left to a
        failed launch attempt, with an actionable hint. Never a modal
        dialog just because the button is unavailable.
        """
        job_active = self._active_runner is not None
        has_selected_training = self.training_manager.active_training_id is not None

        try:
            resolve_onetrainer_launch(self.application_settings_manager.settings.onetrainer_path)
            onetrainer_configured = True
        except OneTrainerLaunchError:
            onetrainer_configured = False

        self.start_training_button.setEnabled(
            has_selected_training and not job_active and onetrainer_configured
        )
        self.cancel_training_button.setEnabled(job_active and not self._cancel_in_flight)

        if job_active:
            self.job_state_label.setText(
                "Annulation en cours…" if self._cancel_in_flight else "Entraînement en cours…"
            )
        elif not onetrainer_configured:
            self.job_state_label.setText(
                "Configurez OneTrainer dans Réglages avant de démarrer un entraînement."
            )
        else:
            self.job_state_label.setText("")

        self._refresh_jobs_list()

    def _refresh_jobs_list(self):
        """
        Mission 103: rebuilds the small Jobs list of the currently
        selected Training directly from Training.jobs — recomputed
        fresh on every call, never cached, so a Job's import status
        always reflects the real current state of the Central LoRA
        Library rather than a stale snapshot (MISSION_103.md section
        3.3). Selection is preserved across a rebuild by job_id, same
        convention as update_trainings() above for training_list.
        """
        previous_job_id = None
        current_item = self.jobs_list.currentItem()
        if current_item is not None:
            previous_job_id = current_item.data(Qt.UserRole)

        self.jobs_list.blockSignals(True)
        self.jobs_list.clear()

        training = self.training_manager.active_training

        restored_item = None
        if training is not None:
            for job in training.jobs:
                item = QListWidgetItem(self._describe_job(job))
                item.setData(Qt.UserRole, job.job_id)
                self.jobs_list.addItem(item)
                if job.job_id == previous_job_id:
                    restored_item = item

        if restored_item is not None:
            self.jobs_list.setCurrentItem(restored_item)

        self.jobs_list.blockSignals(False)

        self._refresh_import_button_state()

    def _describe_job(self, job) -> str:
        """
        Mission 103 section 3.3: the four import states, computed fresh
        — never a cached boolean — from the Job's own fields and a
        fresh read of the Central LoRA Library.
        """
        timestamp = (
            datetime.fromtimestamp(job.created_at).strftime("%Y-%m-%d %H:%M")
            if job.created_at
            else "?"
        )
        status = f"{timestamp} — {job.state}"

        if job.state != TRAINING_JOB_STATE_SUCCEEDED:
            return status

        if not job.final_output_path or not Path(job.final_output_path).is_file():
            return f"{status} — fichier introuvable"

        if not job.imported_lora_id:
            return f"{status} — importable"

        lora = self.lora_library_manager.get(job.imported_lora_id)
        if lora is not None:
            return f"{status} — importé : {lora.name}"

        return f"{status} — LoRA supprimé, réimport possible"

    def _on_job_selection_changed(self, current, previous):
        self._refresh_import_button_state()

    def _refresh_import_button_state(self):
        self.import_lora_button.setEnabled(self._importable_job() is not None)
        # Mission 109: recomputed from the same real data every time,
        # right alongside the import button — never a value cached at
        # import time, so a LoRA deleted afterwards correctly disables
        # this action again on the next selection/refresh.
        self.use_lora_in_inference_button.setEnabled(
            self._usable_in_inference_job() is not None
        )

    def _importable_job(self):
        """
        Mission 103: the single Job (if any) the currently selected row
        of jobs_list may be imported from — None disables the import
        action entirely. Reused as-is by import_selected_job_to_library()
        so the enable check and the actual action never disagree.
        """
        item = self.jobs_list.currentItem()
        if item is None:
            return None

        training = self.training_manager.active_training
        if training is None:
            return None

        job_id = item.data(Qt.UserRole)
        job = next((j for j in training.jobs if j.job_id == job_id), None)

        if job is None or job.state != TRAINING_JOB_STATE_SUCCEEDED:
            return None

        if not job.final_output_path or not Path(job.final_output_path).is_file():
            return None

        if job.imported_lora_id and self.lora_library_manager.get(job.imported_lora_id) is not None:
            return None

        return job

    def _usable_in_inference_job(self):
        """
        Mission 109: the single Job (if any) the currently selected row
        of jobs_list may be sent to Inference for — symmetric to
        _importable_job() above, but the opposite condition: a real
        imported_lora_id that still resolves to a real Central Library
        LoRA. Always re-read live (job.imported_lora_id then a fresh
        lora_library_manager.get() call) — never a boolean cached from
        the moment of import, so a LoRA deleted afterwards is reflected
        immediately on the next selection/refresh.
        """
        item = self.jobs_list.currentItem()
        if item is None:
            return None

        training = self.training_manager.active_training
        if training is None:
            return None

        job_id = item.data(Qt.UserRole)
        job = next((j for j in training.jobs if j.job_id == job_id), None)

        if job is None or not job.imported_lora_id:
            return None

        if self.lora_library_manager.get(job.imported_lora_id) is None:
            return None

        return job

    def use_selected_lora_in_inference(self):
        """
        Mission 109: emits use_lora_in_inference_requested(lora_id) for
        the Job returned by _usable_in_inference_job() — the same
        guard already used to enable/disable the button, so the click
        handler and the enable check never disagree (same discipline
        as import_selected_job_to_library()/_importable_job()). No
        navigation, no InferencePage/Sidebar reference here — MainWindow
        is the sole mediator, exactly like Prompts → Inference (Mission
        033).
        """
        job = self._usable_in_inference_job()
        if job is None:
            return

        self.use_lora_in_inference_requested.emit(job.imported_lora_id)

    def import_selected_job_to_library(self):
        """
        Mission 103 section 3.5: import_lora() first, then — only if it
        succeeds — set_job_imported_lora_id(). The Library entry created
        by a successful import_lora() is never rolled back if the
        second step fails: it is already real and already usable
        (LORA_LIBRARY_IMPORTED already published), so hiding or
        deleting it would be strictly worse than an honest partial-
        success message.
        """
        job = self._importable_job()
        if job is None:
            return

        training = self.training_manager.active_training
        if training is None:
            return

        # Never trust the stored final_output_path blindly — revalidate
        # right before the real copy, since the file could have been
        # removed since the list was last refreshed.
        if not Path(job.final_output_path).is_file():
            QMessageBox.warning(
                self,
                "Fichier introuvable",
                "Le fichier LoRA produit par cet entraînement est introuvable "
                f"({job.final_output_path}). Import annulé."
            )
            self._refresh_jobs_list()
            return

        name, ok = QInputDialog.getText(
            self,
            "Importer dans la Bibliothèque LoRA centrale",
            "Nom :",
            text=training.name,
        )

        if not ok or not name.strip():
            return

        try:
            library_root = resolve_lora_library_root(
                self.application_settings_manager.settings.lora_library_path
            )
        except LoRALibraryPathError as exc:
            QMessageBox.critical(self, "Erreur", str(exc))
            return

        try:
            lora = self.lora_library_manager.import_lora(
                name.strip(), [job.final_output_path], library_root=library_root
            )
        except LoRALibraryError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'importer le LoRA dans la Bibliothèque centrale : {exc}"
            )
            return

        try:
            self.training_manager.set_job_imported_lora_id(job.job_id, lora.lora_id)
        except WorkspaceManagerError as exc:
            QMessageBox.warning(
                self,
                "Import partiel",
                f"Le LoRA « {lora.name} » a bien été importé dans la Bibliothèque "
                "centrale et est déjà utilisable, mais son association avec cet "
                f"entraînement n'a pas pu être enregistrée dans le projet : {exc}\n\n"
                "Cet entraînement réapparaîtra comme non importé — une nouvelle "
                "tentative d'import créera une entrée distincte dans la "
                "Bibliothèque, jamais un doublon fusionné automatiquement."
            )
            self._refresh_jobs_list()
            return

        QMessageBox.information(
            self,
            "Import réussi",
            f"Le LoRA « {lora.name} » a été importé dans la Bibliothèque LoRA centrale."
        )
        self._refresh_jobs_list()
