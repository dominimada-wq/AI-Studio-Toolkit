from PySide6.QtWidgets import (
    QWidget,
    QDoubleSpinBox,
    QLabel,
    QComboBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from src.engines.ai_backend import AIBackendError
from src.engines.comfyui_engine import ComfyUIEngine, ComfyUIEngineError
from src.engines.ollama_engine import OllamaEngine
from src.infrastructure.storage.application_settings_storage import (
    ApplicationSettingsStorageError,
)
from src.managers.workspace_manager import WorkspaceManagerError

# Mission 025: short, dedicated timeout for the on-demand checkpoint
# discovery call — distinct from GenerationManager's long generation
# timeout (120s default). A wrong/unreachable ComfyUI URL must not
# freeze SettingsPage for minutes over a single "Rafraîchir" click.
CHECKPOINT_DISCOVERY_TIMEOUT = 5.0

# Mission 030: same rationale as CHECKPOINT_DISCOVERY_TIMEOUT above,
# for the Ollama model discovery call.
OLLAMA_DISCOVERY_TIMEOUT = 5.0

# Mission 059: same rationale as CHECKPOINT_DISCOVERY_TIMEOUT above,
# for the on-demand LoRA discovery call.
LORA_DISCOVERY_TIMEOUT = 5.0


class SettingsPage(QWidget):

    def __init__(self, settings_manager, application_settings_manager):
        super().__init__()

        self.settings_manager = settings_manager
        self.application_settings_manager = application_settings_manager

        layout = QVBoxLayout(self)

        title = QLabel("Settings")
        title.setStyleSheet("font-size:24px;font-weight:bold;")
        layout.addWidget(title)

        # --- Workspace section ---

        workspace_title = QLabel("Workspace")
        workspace_title.setStyleSheet("font-size:16px;font-weight:bold;")
        layout.addWidget(workspace_title)

        workspace_form = QFormLayout()

        self.theme_edit = QLineEdit()
        self.language_edit = QLineEdit()

        workspace_form.addRow("Thème :", self.theme_edit)
        workspace_form.addRow("Langue :", self.language_edit)

        layout.addLayout(workspace_form)

        self.save_button = QPushButton("Enregistrer")
        self.save_button.clicked.connect(self.save_settings)

        layout.addWidget(self.save_button)

        workspace_hint = QLabel(
            "Ces préférences sont enregistrées dans le Workspace. "
            "Leur application à l'interface sera prise en charge ultérieurement."
        )

        layout.addWidget(workspace_hint)

        # --- Application section ---

        application_title = QLabel("Application")
        application_title.setStyleSheet("font-size:16px;font-weight:bold;")
        layout.addWidget(application_title)

        application_form = QFormLayout()

        self.python_path_edit = QLineEdit()
        self.comfyui_path_edit = QLineEdit()
        self.onetrainer_path_edit = QLineEdit()
        self.comfyui_url_edit = QLineEdit()

        # Mission 025: QComboBox (editable=True) replaces the former
        # free-text QLineEdit — a single widget covers both selecting a
        # checkpoint discovered from the running ComfyUI server and
        # typing a name manually (remote/cloud instance, or discovery
        # unavailable). Attribute name kept identical on purpose.
        self.comfyui_checkpoint_name_edit = QComboBox()
        self.comfyui_checkpoint_name_edit.setEditable(True)

        # Mission 059: same editable QComboBox pattern as
        # comfyui_checkpoint_name_edit — selects a LoRA name discovered
        # from the running ComfyUI server (ComfyUIEngine.list_loras()),
        # never a Workspace-local LoRA.files entry (no reliable mapping
        # exists — see ApplicationSettings.comfyui_lora_name). Empty
        # text means "no LoRA".
        self.comfyui_lora_name_edit = QComboBox()
        self.comfyui_lora_name_edit.setEditable(True)

        # Single combined force applied to both strength_model/
        # strength_clip (Mission 059) — the native LoraLoader node
        # distinguishes them, but no current need justifies two
        # separate controls. 0.0-2.0 is an indicative UI range, not
        # verified against a real server; ComfyUI itself would reject
        # an out-of-range value explicitly, the same way it already
        # rejects an unknown checkpoint/lora_name.
        self.comfyui_lora_strength_edit = QDoubleSpinBox()
        self.comfyui_lora_strength_edit.setRange(0.0, 2.0)
        self.comfyui_lora_strength_edit.setSingleStep(0.05)
        self.comfyui_lora_strength_edit.setValue(1.0)

        self.ollama_url_edit = QLineEdit()
        self.ollama_path_edit = QLineEdit()

        # Mission 030: same editable QComboBox pattern already used for
        # comfyui_checkpoint_name_edit — one widget covers both
        # selecting a model discovered from a running Ollama instance
        # and typing a name manually.
        self.ollama_model_name_edit = QComboBox()
        self.ollama_model_name_edit.setEditable(True)

        application_form.addRow("Python :", self.python_path_edit)
        application_form.addRow("ComfyUI :", self.comfyui_path_edit)
        application_form.addRow("OneTrainer :", self.onetrainer_path_edit)
        application_form.addRow("ComfyUI URL :", self.comfyui_url_edit)
        application_form.addRow("ComfyUI Checkpoint :", self.comfyui_checkpoint_name_edit)
        application_form.addRow("ComfyUI LoRA :", self.comfyui_lora_name_edit)
        application_form.addRow("Force LoRA :", self.comfyui_lora_strength_edit)
        application_form.addRow("Ollama URL :", self.ollama_url_edit)
        application_form.addRow("Ollama :", self.ollama_path_edit)
        application_form.addRow("Ollama Model :", self.ollama_model_name_edit)

        layout.addLayout(application_form)

        self.refresh_checkpoints_button = QPushButton("Rafraîchir les checkpoints")
        self.refresh_checkpoints_button.clicked.connect(self.refresh_checkpoints)
        layout.addWidget(self.refresh_checkpoints_button)

        self.checkpoint_discovery_status_label = QLabel("")
        layout.addWidget(self.checkpoint_discovery_status_label)

        self.refresh_loras_button = QPushButton("Rafraîchir les LoRA")
        self.refresh_loras_button.clicked.connect(self.refresh_loras)
        layout.addWidget(self.refresh_loras_button)

        self.lora_discovery_status_label = QLabel("")
        layout.addWidget(self.lora_discovery_status_label)

        self.refresh_ollama_models_button = QPushButton("Rafraîchir les modèles")
        self.refresh_ollama_models_button.clicked.connect(self.refresh_ollama_models)
        layout.addWidget(self.refresh_ollama_models_button)

        self.ollama_discovery_status_label = QLabel("")
        layout.addWidget(self.ollama_discovery_status_label)

        self.application_save_button = QPushButton("Enregistrer")
        self.application_save_button.clicked.connect(self.save_application_settings)

        layout.addWidget(self.application_save_button)

        application_hint = QLabel(
            "Ces chemins sont propres à cette installation et indépendants du Workspace. "
            "Les modifications de la configuration ComfyUI/Ollama prennent effet après le "
            "redémarrage de l'application. Le LoRA choisi doit être compatible avec le "
            "checkpoint sélectionné (ex. SD1.5/SDXL) — ComfyUI reste seul juge de cette "
            "compatibilité et rejette explicitement toute combinaison incompatible."
        )
        # Mission 059: word wrap prevents this label's natural unwrapped
        # width from setting SettingsPage's (and therefore MainWindow's,
        # via QStackedWidget's own size aggregation across every page)
        # minimum/preferred size — a real regression measured before this
        # fix (SettingsPage.sizeHint() went from (996, 596) to (2004, 704)
        # once this label's text grew past the M059 LoRA sentence).
        application_hint.setWordWrap(True)

        layout.addWidget(application_hint)

        layout.addStretch()

        self.theme_edit.setEnabled(False)
        self.language_edit.setEnabled(False)
        self.save_button.setEnabled(False)

        # Application Settings exist independently of any Workspace and
        # are already loaded by the time this Page is constructed — this
        # populates the section immediately, it is not a reactive refresh.
        self.update_application_settings()

    def save_settings(self):

        try:
            self.settings_manager.update(
                theme=self.theme_edit.text(),
                language=self.language_edit.text(),
            )
        except WorkspaceManagerError as exc:
            QMessageBox.critical(self, "Erreur", str(exc))
            # Mission 077: update() rolls back settings.theme/settings.
            # language before re-raising on a save() failure — without this,
            # theme_edit/language_edit would keep displaying the rejected
            # value just typed instead of the restored one. A workspace is
            # necessarily still open here (update() only mutates/raises
            # past its own `workspace is None` guard), so any truthy
            # payload keeps the fields enabled; update_settings() never
            # reads the payload's content, only whether it is None.
            self.update_settings(payload=True)
            return

    def save_application_settings(self):

        try:
            self.application_settings_manager.update(
                python_path=self.python_path_edit.text(),
                comfyui_path=self.comfyui_path_edit.text(),
                onetrainer_path=self.onetrainer_path_edit.text(),
                comfyui_url=self.comfyui_url_edit.text(),
                comfyui_checkpoint_name=self.comfyui_checkpoint_name_edit.currentText(),
                comfyui_lora_name=self.comfyui_lora_name_edit.currentText(),
                comfyui_lora_strength=self.comfyui_lora_strength_edit.value(),
                ollama_url=self.ollama_url_edit.text(),
                ollama_path=self.ollama_path_edit.text(),
                ollama_model_name=self.ollama_model_name_edit.currentText(),
            )
        except ApplicationSettingsStorageError as exc:
            QMessageBox.critical(self, "Erreur", str(exc))
            return

    def refresh_checkpoints(self):

        current_text = self.comfyui_checkpoint_name_edit.currentText()

        engine = ComfyUIEngine(
            base_url=self.comfyui_url_edit.text(), timeout=CHECKPOINT_DISCOVERY_TIMEOUT
        )

        try:
            checkpoints = engine.list_checkpoints()
        except ComfyUIEngineError:
            self.checkpoint_discovery_status_label.setText(
                "Découverte impossible : ComfyUI injoignable ou configuration invalide. "
                "La saisie manuelle du checkpoint reste disponible."
            )
            return

        # blockSignals: repopulating a QComboBox fires currentIndexChanged/
        # editTextChanged transiently for every intermediate state (clear(),
        # each addItem(), setCurrentText()) — none of that is a real user
        # edit, same rationale as InferencePage's reference controls reset.
        self.comfyui_checkpoint_name_edit.blockSignals(True)
        self.comfyui_checkpoint_name_edit.clear()
        self.comfyui_checkpoint_name_edit.addItems(checkpoints)
        # Never let discovery override the value already displayed —
        # setCurrentText() on an editable QComboBox accepts a value absent
        # from the freshly discovered list without error.
        self.comfyui_checkpoint_name_edit.setCurrentText(current_text)
        self.comfyui_checkpoint_name_edit.blockSignals(False)

        self.checkpoint_discovery_status_label.setText(
            f"{len(checkpoints)} checkpoint(s) détecté(s)."
            if checkpoints
            else "Aucun checkpoint détecté sur ce serveur ComfyUI."
        )

    def refresh_loras(self):

        current_text = self.comfyui_lora_name_edit.currentText()

        engine = ComfyUIEngine(
            base_url=self.comfyui_url_edit.text(), timeout=LORA_DISCOVERY_TIMEOUT
        )

        try:
            loras = engine.list_loras()
        except ComfyUIEngineError:
            self.lora_discovery_status_label.setText(
                "Découverte impossible : ComfyUI injoignable ou configuration invalide. "
                "La saisie manuelle du LoRA reste disponible."
            )
            return

        # blockSignals: same rationale as refresh_checkpoints() above.
        self.comfyui_lora_name_edit.blockSignals(True)
        self.comfyui_lora_name_edit.clear()
        self.comfyui_lora_name_edit.addItems(loras)
        # Never let discovery override the value already displayed —
        # same guarantee as refresh_checkpoints(): a saved LoRA name is
        # never silently replaced, even if absent from the freshly
        # discovered list.
        self.comfyui_lora_name_edit.setCurrentText(current_text)
        self.comfyui_lora_name_edit.blockSignals(False)

        self.lora_discovery_status_label.setText(
            f"{len(loras)} LoRA détecté(s)."
            if loras
            else "Aucun LoRA détecté sur ce serveur ComfyUI."
        )

    def refresh_ollama_models(self):

        current_text = self.ollama_model_name_edit.currentText()

        engine = OllamaEngine(
            base_url=self.ollama_url_edit.text(), timeout=OLLAMA_DISCOVERY_TIMEOUT
        )

        try:
            models = engine.list_models()
        except AIBackendError:
            self.ollama_discovery_status_label.setText(
                "Découverte impossible : Ollama injoignable ou configuration invalide. "
                "La saisie manuelle du modèle reste disponible."
            )
            return

        model_names = [model.name for model in models]

        # blockSignals: repopulating a QComboBox fires currentIndexChanged/
        # editTextChanged transiently for every intermediate state — same
        # rationale as refresh_checkpoints() above.
        self.ollama_model_name_edit.blockSignals(True)
        self.ollama_model_name_edit.clear()
        self.ollama_model_name_edit.addItems(model_names)
        # Never let discovery override the value already displayed —
        # setCurrentText() on an editable QComboBox accepts a value absent
        # from the freshly discovered list without error.
        self.ollama_model_name_edit.setCurrentText(current_text)
        self.ollama_model_name_edit.blockSignals(False)

        self.ollama_discovery_status_label.setText(
            f"{len(model_names)} modèle(s) détecté(s)."
            if model_names
            else "Aucun modèle détecté sur cette instance Ollama."
        )

    def update_settings(self, payload=None):

        opened = payload is not None

        self.theme_edit.setEnabled(opened)
        self.language_edit.setEnabled(opened)
        self.save_button.setEnabled(opened)

        settings = self.settings_manager.settings

        self.theme_edit.setText(settings.theme)
        self.language_edit.setText(settings.language)

    def update_application_settings(self, payload=None):

        settings = self.application_settings_manager.settings

        self.python_path_edit.setText(settings.python_path)
        self.comfyui_path_edit.setText(settings.comfyui_path)
        self.onetrainer_path_edit.setText(settings.onetrainer_path)
        self.comfyui_url_edit.setText(settings.comfyui_url)
        self.comfyui_checkpoint_name_edit.setCurrentText(settings.comfyui_checkpoint_name)
        self.comfyui_lora_name_edit.setCurrentText(settings.comfyui_lora_name)
        self.comfyui_lora_strength_edit.setValue(settings.comfyui_lora_strength)
        self.ollama_url_edit.setText(settings.ollama_url)
        self.ollama_path_edit.setText(settings.ollama_path)
        self.ollama_model_name_edit.setCurrentText(settings.ollama_model_name)
