from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QFormLayout,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
)

from src.engines.ai_backend import AIBackendError
from src.engines.comfyui_engine import ComfyUIEngine, ComfyUIEngineError
from src.engines.comfyui_install import ComfyUIInstallError, resolve_comfyui_install
from src.engines.forge_engine import ForgeEngine, ForgeEngineError
from src.engines.forge_install import ForgeInstallError, resolve_forge_install
from src.engines.ollama_engine import OllamaEngine
from src.ui.comfyui_lifecycle_manager import (
    EXTERNAL_ACTIVE,
    RUNNING_OWNED,
    STARTING,
    START_FAILED,
    STOPPED,
    STOPPING,
    ComfyUILifecycleManager,
)
from src.infrastructure.storage.application_settings_storage import (
    ApplicationSettingsStorageError,
)
from src.managers.application_settings_manager import LoRALibraryPathLockedError
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

# Mission 112: same rationale as CHECKPOINT_DISCOVERY_TIMEOUT above, for
# the explicit connection-diagnostic call (ComfyUI and Forge both).
CONNECTION_TEST_TIMEOUT = 5.0


class SettingsPage(QWidget):

    def __init__(self, settings_manager, application_settings_manager, comfyui_lifecycle_manager=None):
        super().__init__()

        self.settings_manager = settings_manager
        self.application_settings_manager = application_settings_manager
        # Mission 114: defaults to a private instance when not supplied
        # (every existing SettingsPage() call site outside MainWindow
        # stays unchanged) — MainWindow always passes its own shared
        # instance, the same one closeEvent() consults directly, so
        # Start/Stop here and the close guard always observe one
        # identical lifecycle state.
        self.comfyui_lifecycle_manager = comfyui_lifecycle_manager or ComfyUILifecycleManager()
        self.comfyui_lifecycle_manager.state_changed.connect(self._on_comfyui_lifecycle_state_changed)

        # Mini-correctif (hors périmètre Mission 115) : le contenu réel de
        # cette page (accumulé sur de nombreuses missions — M087, M108,
        # M112, M113, M114...) dépasse désormais la hauteur d'une fenêtre
        # normale sans qu'aucun mécanisme de défilement n'existe, rendant
        # certains contrôles ajoutés en fin de page (dont
        # application_save_button lui-même) physiquement inatteignables.
        # Un seul changement structurel : le contenu existant, inchangé,
        # est désormais construit dans content_widget puis placé dans un
        # QScrollArea — aucune section réorganisée, aucun onglet introduit,
        # aucune logique de sauvegarde modifiée. `layout` référence
        # toujours exactement le même QVBoxLayout que tout le code
        # ci-dessous continue de peupler sans aucun changement.
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        outer_layout.addWidget(scroll_area)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)

        layout = QVBoxLayout(content_widget)

        title = QLabel("Settings")
        title.setStyleSheet("font-size:24px;font-weight:bold;")
        layout.addWidget(title)

        # --- Mission 118: Settings navigation ---
        #
        # Reuses the exact Sidebar/stack idiom already established and
        # documented as a permanent convention (CLAUDE.md) for
        # MainWindow's own page navigation — applied here a second time,
        # nested inside SettingsPage, rather than inventing a new UI
        # idiom (no QTreeWidget). settings_nav_list holds both real,
        # selectable category rows and purely visual, disabled "group
        # header" rows (Training, Local Image Generation) that nest
        # OneTrainer / ComfyUI Local / Stable Diffusion Forge under their
        # parent category without a second widget type.
        # _settings_nav_stack_index maps a selectable row to its
        # settings_stack page; header rows are simply absent from it, so
        # currentRowChanged is a no-op when one is (attempted to be)
        # selected. Cloud Image Generation, Video Generation, Audio
        # Generation and any "Online Services" catch-all are deliberately
        # absent: an audit of every field against its real consumer
        # (ComfyUIEngine/ComfyUILifecycleManager, ForgeEngine,
        # OllamaEngine, onetrainer_launch.py) confirmed nothing is
        # orphaned by the categories below. Adding a future sibling (e.g.
        # Fooocus under Local Image Generation, or a new Cloud Image
        # Generation category once a provider is actually implemented)
        # only means appending one more add_settings_header()/
        # add_settings_page() call, never restructuring this mechanism.
        self.settings_nav_list = QListWidget()
        self.settings_nav_list.setFixedWidth(200)
        self.settings_stack = QStackedWidget()
        self._settings_nav_stack_index = {}

        def add_settings_header(label):
            row = self.settings_nav_list.count()
            self.settings_nav_list.addItem(label)
            item = self.settings_nav_list.item(row)
            item.setFlags(item.flags() & ~(Qt.ItemIsEnabled | Qt.ItemIsSelectable))

        def add_settings_page(label, page):
            row = self.settings_nav_list.count()
            self.settings_nav_list.addItem(label)
            self._settings_nav_stack_index[row] = self.settings_stack.addWidget(page)

        nav_stack_row = QWidget()
        nav_stack_layout = QHBoxLayout(nav_stack_row)
        nav_stack_layout.setContentsMargins(0, 0, 0, 0)
        nav_stack_layout.addWidget(self.settings_nav_list)
        nav_stack_layout.addWidget(self.settings_stack, 1)
        layout.addWidget(nav_stack_row)

        # --- General ---

        general_page = QWidget()
        general_layout = QVBoxLayout(general_page)

        workspace_title = QLabel("Workspace")
        workspace_title.setStyleSheet("font-size:16px;font-weight:bold;")
        general_layout.addWidget(workspace_title)

        workspace_form = QFormLayout()

        self.theme_edit = QLineEdit()
        self.language_edit = QLineEdit()

        # Mission 078: local UI-only dirty-state for the Workspace section
        # only (theme/language) — never persisted, never exposed to
        # SettingsManager. Mirrors PromptsPage's _dirty (Mission 038):
        # textChanged only ever fires from real user typing, since every
        # programmatic write below goes through _load_settings_fields(),
        # which wraps both setText() calls in blockSignals().
        self._dirty = False
        self.theme_edit.textChanged.connect(self._on_settings_changed)
        self.language_edit.textChanged.connect(self._on_settings_changed)

        workspace_form.addRow("Thème :", self.theme_edit)
        workspace_form.addRow("Langue :", self.language_edit)

        general_layout.addLayout(workspace_form)

        self.save_button = QPushButton("Enregistrer")
        self.save_button.clicked.connect(self.save_settings)

        general_layout.addWidget(self.save_button)

        workspace_hint = QLabel(
            "Ces préférences sont enregistrées dans le Workspace. "
            "Leur application à l'interface sera prise en charge ultérieurement."
        )

        general_layout.addWidget(workspace_hint)

        # Mission 118: lora_library_path is Application-level, but
        # cross-cutting (its central library is exposed to both ComfyUI
        # Local and Forge, each in their own category below) — General is
        # its natural home rather than either specific engine's category.
        lora_library_title = QLabel("Bibliothèque LoRA")
        lora_library_title.setStyleSheet("font-size:16px;font-weight:bold;")
        general_layout.addWidget(lora_library_title)

        lora_library_form = QFormLayout()

        # Mission 087: the only path field in this section with a
        # Browse button — unlike comfyui_path/onetrainer_path/etc.
        # (free text only, no physical constraint enforced), this value
        # must be a real, writable directory, so a folder picker is
        # warranted. Mirrors the QFileDialog pattern already used by
        # ModelsPage.browse_file() (a file picker there; a directory
        # picker here), not a new UI idiom.
        self.lora_library_path_edit = QLineEdit()
        self.lora_library_browse_button = QPushButton("Parcourir…")
        self.lora_library_browse_button.clicked.connect(self.browse_lora_library_path)
        lora_library_path_row = QWidget()
        lora_library_path_layout = QHBoxLayout(lora_library_path_row)
        lora_library_path_layout.setContentsMargins(0, 0, 0, 0)
        lora_library_path_layout.addWidget(self.lora_library_path_edit)
        lora_library_path_layout.addWidget(self.lora_library_browse_button)

        lora_library_form.addRow("Bibliothèque LoRA centrale :", lora_library_path_row)

        general_layout.addLayout(lora_library_form)
        general_layout.addStretch()

        add_settings_page("General", general_page)

        # --- Training ---

        add_settings_header("Training")

        onetrainer_page = QWidget()
        onetrainer_layout = QVBoxLayout(onetrainer_page)
        onetrainer_form = QFormLayout()

        # Mission 113: python_path_edit deliberately has no Browse
        # button — its semantics (folder vs. executable file) are not
        # established by any consumer in this codebase beyond
        # onetrainer_launch.py's own docstring — guessing a picker type
        # for it here would be an unverified assumption.
        self.python_path_edit = QLineEdit()

        # Mission 113: same physical-directory-picker rationale as
        # lora_library_path_edit (General) — onetrainer_path is confirmed
        # a real directory by resolve_onetrainer_launch() (Mission 100),
        # which already resolves <onetrainer_path>/venv/Scripts/python.exe
        # and <onetrainer_path>/scripts/train_remote.py from it.
        self.onetrainer_path_edit = QLineEdit()
        self.onetrainer_path_browse_button = QPushButton("Parcourir…")
        self.onetrainer_path_browse_button.clicked.connect(self.browse_onetrainer_path)
        onetrainer_path_row = QWidget()
        onetrainer_path_layout = QHBoxLayout(onetrainer_path_row)
        onetrainer_path_layout.setContentsMargins(0, 0, 0, 0)
        onetrainer_path_layout.addWidget(self.onetrainer_path_edit)
        onetrainer_path_layout.addWidget(self.onetrainer_path_browse_button)

        onetrainer_form.addRow("Python :", self.python_path_edit)
        onetrainer_form.addRow("OneTrainer :", onetrainer_path_row)

        onetrainer_layout.addLayout(onetrainer_form)
        onetrainer_layout.addStretch()

        add_settings_page("  OneTrainer", onetrainer_page)

        # --- Local Image Generation ---

        add_settings_header("Local Image Generation")

        # - ComfyUI Local -

        comfyui_page = QWidget()
        comfyui_layout = QVBoxLayout(comfyui_page)
        comfyui_form = QFormLayout()

        # Mission 113: comfyui_path is a real directory (confirmed
        # against a real ComfyUI Desktop installation: it is exactly
        # the data/--base-directory root), same physical-directory-
        # picker rationale already established for lora_library_path_edit
        # (General) — added retroactively here since the constraint
        # already existed, it was simply never given a picker before
        # this mission.
        self.comfyui_path_edit = QLineEdit()
        self.comfyui_path_browse_button = QPushButton("Parcourir…")
        self.comfyui_path_browse_button.clicked.connect(self.browse_comfyui_path)
        comfyui_path_row = QWidget()
        comfyui_path_layout = QHBoxLayout(comfyui_path_row)
        comfyui_path_layout.setContentsMargins(0, 0, 0, 0)
        comfyui_path_layout.addWidget(self.comfyui_path_edit)
        comfyui_path_layout.addWidget(self.comfyui_path_browse_button)

        # Mission 113: distinct from comfyui_path above — the root of
        # the ComfyUI Local/Desktop installation itself (used to
        # resolve resources/ComfyUI/main.py), never the data root.
        # Static validation only (resolve_comfyui_install()); never a
        # network call, never a launch, and deliberately independent
        # from the Mission 112 HTTP connection status below — changing
        # this path never touches comfyui_connection_status_label, and
        # vice versa.
        self.comfyui_install_path_edit = QLineEdit()
        self.comfyui_install_path_edit.textEdited.connect(
            self._on_comfyui_install_path_edited
        )
        self.comfyui_install_browse_button = QPushButton("Parcourir…")
        self.comfyui_install_browse_button.clicked.connect(
            self.browse_comfyui_install_path
        )
        comfyui_install_path_row = QWidget()
        comfyui_install_path_layout = QHBoxLayout(comfyui_install_path_row)
        comfyui_install_path_layout.setContentsMargins(0, 0, 0, 0)
        comfyui_install_path_layout.addWidget(self.comfyui_install_path_edit)
        comfyui_install_path_layout.addWidget(self.comfyui_install_browse_button)

        self.comfyui_install_check_button = QPushButton("Vérifier l'installation")
        self.comfyui_install_check_button.clicked.connect(self.check_comfyui_install)
        self.comfyui_install_status_label = QLabel("Installation non vérifiée.")
        comfyui_install_check_row = QWidget()
        comfyui_install_check_layout = QHBoxLayout(comfyui_install_check_row)
        comfyui_install_check_layout.setContentsMargins(0, 0, 0, 0)
        comfyui_install_check_layout.addWidget(self.comfyui_install_check_button)
        comfyui_install_check_layout.addWidget(self.comfyui_install_status_label)

        self.comfyui_url_edit = QLineEdit()

        # Mission 112: explicit, dedicated connection diagnostic — distinct
        # from refresh_checkpoints()/refresh_loras() below, which only
        # prove reachability as a side effect of checkpoint/LoRA
        # discovery. textEdited (never textChanged) only fires on a real
        # user keystroke, never on update_application_settings()'s own
        # setText() reload below — no blockSignals() needed here.
        self.comfyui_test_connection_button = QPushButton("Tester la connexion")
        self.comfyui_test_connection_button.clicked.connect(self.test_comfyui_connection)
        self.comfyui_connection_status_label = QLabel("Connexion non testée.")
        self.comfyui_url_edit.textEdited.connect(self._on_comfyui_url_edited)
        comfyui_connection_row = QWidget()
        comfyui_connection_layout = QHBoxLayout(comfyui_connection_row)
        comfyui_connection_layout.setContentsMargins(0, 0, 0, 0)
        comfyui_connection_layout.addWidget(self.comfyui_test_connection_button)
        comfyui_connection_layout.addWidget(self.comfyui_connection_status_label)

        # Mission 114: ComfyUI Local lifecycle (Start/ownership/
        # readiness/Stop) — a third, visually distinct control from the
        # installation-validity label above (Mission 113) and the
        # connection-diagnostic label above it (Mission 112). Uses
        # whatever is currently typed in comfyui_path_edit/
        # comfyui_install_path_edit/comfyui_url_edit, exactly like
        # "Vérifier l'installation"/"Tester la connexion" — never
        # necessarily the already-saved values.
        self.comfyui_start_button = QPushButton("Démarrer")
        self.comfyui_start_button.clicked.connect(self.start_comfyui)
        self.comfyui_stop_button = QPushButton("Arrêter")
        self.comfyui_stop_button.clicked.connect(self.stop_comfyui)
        self.comfyui_stop_button.setEnabled(False)
        self.comfyui_lifecycle_status_label = QLabel("ComfyUI non démarré par Toolkit.")
        comfyui_lifecycle_row = QWidget()
        comfyui_lifecycle_layout = QHBoxLayout(comfyui_lifecycle_row)
        comfyui_lifecycle_layout.setContentsMargins(0, 0, 0, 0)
        comfyui_lifecycle_layout.addWidget(self.comfyui_start_button)
        comfyui_lifecycle_layout.addWidget(self.comfyui_stop_button)
        comfyui_lifecycle_layout.addWidget(self.comfyui_lifecycle_status_label)

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

        # Mission 095: same physical-directory-picker rationale as
        # lora_library_path_edit (General), since this must name a real,
        # already-existing ComfyUI loras root (never created/validated
        # against ComfyUI itself by this Page — only that it exists as a
        # directory, checked by LoRALibraryManager.expose_to_comfyui()
        # at the moment of use, never here).
        self.comfyui_lora_expose_path_edit = QLineEdit()
        self.comfyui_lora_expose_browse_button = QPushButton("Parcourir…")
        self.comfyui_lora_expose_browse_button.clicked.connect(
            self.browse_comfyui_lora_expose_path
        )
        comfyui_lora_expose_path_row = QWidget()
        comfyui_lora_expose_path_layout = QHBoxLayout(comfyui_lora_expose_path_row)
        comfyui_lora_expose_path_layout.setContentsMargins(0, 0, 0, 0)
        comfyui_lora_expose_path_layout.addWidget(self.comfyui_lora_expose_path_edit)
        comfyui_lora_expose_path_layout.addWidget(self.comfyui_lora_expose_browse_button)

        comfyui_form.addRow("ComfyUI :", comfyui_path_row)
        comfyui_form.addRow("ComfyUI (installation locale) :", comfyui_install_path_row)
        comfyui_form.addRow("", comfyui_install_check_row)
        comfyui_form.addRow("ComfyUI URL :", self.comfyui_url_edit)
        comfyui_form.addRow("", comfyui_connection_row)
        comfyui_form.addRow("", comfyui_lifecycle_row)
        comfyui_form.addRow("ComfyUI Checkpoint :", self.comfyui_checkpoint_name_edit)
        comfyui_form.addRow("ComfyUI LoRA :", self.comfyui_lora_name_edit)
        comfyui_form.addRow("Force LoRA :", self.comfyui_lora_strength_edit)
        comfyui_form.addRow(
            "Exposition ComfyUI (racine loras déjà déclarée) :", comfyui_lora_expose_path_row
        )

        comfyui_layout.addLayout(comfyui_form)

        self.refresh_checkpoints_button = QPushButton("Rafraîchir les checkpoints")
        self.refresh_checkpoints_button.clicked.connect(self.refresh_checkpoints)
        comfyui_layout.addWidget(self.refresh_checkpoints_button)

        self.checkpoint_discovery_status_label = QLabel("")
        comfyui_layout.addWidget(self.checkpoint_discovery_status_label)

        self.refresh_loras_button = QPushButton("Rafraîchir les LoRA")
        self.refresh_loras_button.clicked.connect(self.refresh_loras)
        comfyui_layout.addWidget(self.refresh_loras_button)

        self.lora_discovery_status_label = QLabel("")
        comfyui_layout.addWidget(self.lora_discovery_status_label)

        comfyui_layout.addStretch()

        add_settings_page("  ComfyUI Local", comfyui_page)

        # - Stable Diffusion Forge -

        forge_page = QWidget()
        forge_layout = QVBoxLayout(forge_page)
        forge_form = QFormLayout()

        # Mission 113: the root of the local Forge installation (the
        # folder containing run.bat) — same static-validation-only
        # rationale as comfyui_install_path_edit (ComfyUI Local's own
        # section above), independent from the Mission 112 HTTP
        # connection status below.
        self.forge_path_edit = QLineEdit()
        self.forge_path_edit.textEdited.connect(self._on_forge_path_edited)
        self.forge_path_browse_button = QPushButton("Parcourir…")
        self.forge_path_browse_button.clicked.connect(self.browse_forge_path)
        forge_path_row = QWidget()
        forge_path_layout = QHBoxLayout(forge_path_row)
        forge_path_layout.setContentsMargins(0, 0, 0, 0)
        forge_path_layout.addWidget(self.forge_path_edit)
        forge_path_layout.addWidget(self.forge_path_browse_button)

        self.forge_install_check_button = QPushButton("Vérifier l'installation")
        self.forge_install_check_button.clicked.connect(self.check_forge_install)
        self.forge_install_status_label = QLabel("Installation non vérifiée.")
        forge_install_check_row = QWidget()
        forge_install_check_layout = QHBoxLayout(forge_install_check_row)
        forge_install_check_layout.setContentsMargins(0, 0, 0, 0)
        forge_install_check_layout.addWidget(self.forge_install_check_button)
        forge_install_check_layout.addWidget(self.forge_install_status_label)

        # Mission 108: forge_url mirrors comfyui_url_edit exactly — a
        # plain QLineEdit, no discovery button of its own (Forge's
        # checkpoint/sampler/scheduler discovery lives in InferencePage
        # via GenerationManager, not in SettingsPage — no
        # forge_checkpoint_name/forge_lora_name field exists to refresh
        # here).
        self.forge_url_edit = QLineEdit()

        # Mission 112: same explicit connection diagnostic as ComfyUI
        # above — Forge's first and only connectivity check of any kind
        # in Settings (no checkpoint/LoRA discovery exists for Forge
        # here, see forge_url_edit's own Mission 108 comment above).
        self.forge_test_connection_button = QPushButton("Tester la connexion")
        self.forge_test_connection_button.clicked.connect(self.test_forge_connection)
        self.forge_connection_status_label = QLabel("Connexion non testée.")
        self.forge_url_edit.textEdited.connect(self._on_forge_url_edited)
        forge_connection_row = QWidget()
        forge_connection_layout = QHBoxLayout(forge_connection_row)
        forge_connection_layout.setContentsMargins(0, 0, 0, 0)
        forge_connection_layout.addWidget(self.forge_test_connection_button)
        forge_connection_layout.addWidget(self.forge_connection_status_label)

        # Mission 108: forge_lora_expose_path mirrors
        # comfyui_lora_expose_path_edit exactly — same physical-
        # directory-picker rationale (must name a real, already-existing
        # Forge loras root), same Browse button pattern from its
        # introduction (Mission 087 precedent).
        self.forge_lora_expose_path_edit = QLineEdit()
        self.forge_lora_expose_browse_button = QPushButton("Parcourir…")
        self.forge_lora_expose_browse_button.clicked.connect(
            self.browse_forge_lora_expose_path
        )
        forge_lora_expose_path_row = QWidget()
        forge_lora_expose_path_layout = QHBoxLayout(forge_lora_expose_path_row)
        forge_lora_expose_path_layout.setContentsMargins(0, 0, 0, 0)
        forge_lora_expose_path_layout.addWidget(self.forge_lora_expose_path_edit)
        forge_lora_expose_path_layout.addWidget(self.forge_lora_expose_browse_button)

        forge_form.addRow("Forge (installation locale) :", forge_path_row)
        forge_form.addRow("", forge_install_check_row)
        forge_form.addRow("Forge URL :", self.forge_url_edit)
        forge_form.addRow("", forge_connection_row)
        forge_form.addRow(
            "Exposition Forge (racine loras déjà déclarée) :", forge_lora_expose_path_row
        )

        forge_layout.addLayout(forge_form)
        forge_layout.addStretch()

        add_settings_page("  Stable Diffusion Forge", forge_page)

        # --- AI Assistants ---

        ai_assistants_page = QWidget()
        ai_assistants_layout = QVBoxLayout(ai_assistants_page)
        ai_assistants_form = QFormLayout()

        self.ollama_url_edit = QLineEdit()
        self.ollama_path_edit = QLineEdit()

        # Mission 030: same editable QComboBox pattern already used for
        # comfyui_checkpoint_name_edit (ComfyUI Local) — one widget
        # covers both selecting a model discovered from a running Ollama
        # instance and typing a name manually.
        self.ollama_model_name_edit = QComboBox()
        self.ollama_model_name_edit.setEditable(True)

        ai_assistants_form.addRow("Ollama URL :", self.ollama_url_edit)
        ai_assistants_form.addRow("Ollama :", self.ollama_path_edit)
        ai_assistants_form.addRow("Ollama Model :", self.ollama_model_name_edit)

        ai_assistants_layout.addLayout(ai_assistants_form)

        self.refresh_ollama_models_button = QPushButton("Rafraîchir les modèles")
        self.refresh_ollama_models_button.clicked.connect(self.refresh_ollama_models)
        ai_assistants_layout.addWidget(self.refresh_ollama_models_button)

        self.ollama_discovery_status_label = QLabel("")
        ai_assistants_layout.addWidget(self.ollama_discovery_status_label)

        ai_assistants_layout.addStretch()

        add_settings_page("AI Assistants", ai_assistants_page)

        self.settings_nav_list.currentRowChanged.connect(self._on_settings_nav_row_changed)
        self.settings_nav_list.setCurrentRow(0)

        # --- Persistent actions ---
        #
        # Mission 118: both Save buttons stay global, outside
        # settings_stack — application_save_button already persists
        # every Application field in one call (save_application_settings()
        # below), regardless of which category is currently selected, so
        # pinning it to a single category would misleadingly suggest it
        # only affects that one category's fields. Reading any widget's
        # current value works whether or not its page is the one
        # currently shown (QStackedWidget hides pages, it never disables
        # or destroys them).
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

    def _on_settings_nav_row_changed(self, row):
        # Mission 118: header rows (Training, Local Image Generation) are
        # absent from _settings_nav_stack_index and also non-selectable
        # (add_settings_header), so this is only ever a real category
        # switch in practice — the guard stays defensive rather than
        # assuming Qt can never report such a row as current.
        stack_index = self._settings_nav_stack_index.get(row)
        if stack_index is not None:
            self.settings_stack.setCurrentIndex(stack_index)

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
            # value just typed instead of the restored one.
            # Mission 078: _load_settings_fields() bypasses the dirty-state
            # guard on purpose — the just-rejected input must always be
            # replaced by the restored Domain value here, regardless of
            # _dirty, exactly like Missions 073/074's own failure contract.
            self._load_settings_fields()
            return

        # Mission 078: the save intent is satisfied — nothing from the UI's
        # point of view remains unsaved, regardless of update()'s own
        # True/False return (idempotent no-op still means "nothing left
        # unsaved"). No field resync needed: theme_edit/language_edit
        # already display exactly what was just persisted.
        self._dirty = False

    def save_application_settings(self):

        try:
            self.application_settings_manager.update(
                python_path=self.python_path_edit.text(),
                comfyui_path=self.comfyui_path_edit.text(),
                comfyui_install_path=self.comfyui_install_path_edit.text(),
                onetrainer_path=self.onetrainer_path_edit.text(),
                comfyui_url=self.comfyui_url_edit.text(),
                comfyui_checkpoint_name=self.comfyui_checkpoint_name_edit.currentText(),
                comfyui_lora_name=self.comfyui_lora_name_edit.currentText(),
                comfyui_lora_strength=self.comfyui_lora_strength_edit.value(),
                ollama_url=self.ollama_url_edit.text(),
                ollama_path=self.ollama_path_edit.text(),
                ollama_model_name=self.ollama_model_name_edit.currentText(),
                lora_library_path=self.lora_library_path_edit.text(),
                comfyui_lora_expose_path=self.comfyui_lora_expose_path_edit.text(),
                forge_path=self.forge_path_edit.text(),
                forge_url=self.forge_url_edit.text(),
                forge_lora_expose_path=self.forge_lora_expose_path_edit.text(),
            )
        except LoRALibraryPathLockedError as exc:
            QMessageBox.critical(self, "Erreur", str(exc))
            # Mission 087: nothing was persisted (update() raises before
            # building the candidate/saving) — reload every field back to
            # the actual stored state, discarding the rejected library
            # path (and any other field edited in the same click, since
            # this Page bundles every Application field into one Save).
            self.update_application_settings()
            return
        except ApplicationSettingsStorageError as exc:
            QMessageBox.critical(self, "Erreur", str(exc))
            return

    def browse_lora_library_path(self):

        directory = QFileDialog.getExistingDirectory(
            self, "Choisir le dossier de la bibliothèque LoRA centrale", self.lora_library_path_edit.text()
        )

        if directory:
            self.lora_library_path_edit.setText(directory)

    def browse_comfyui_lora_expose_path(self):

        directory = QFileDialog.getExistingDirectory(
            self,
            "Choisir la racine loras déjà déclarée à ComfyUI",
            self.comfyui_lora_expose_path_edit.text(),
        )

        if directory:
            self.comfyui_lora_expose_path_edit.setText(directory)

    def browse_forge_lora_expose_path(self):

        directory = QFileDialog.getExistingDirectory(
            self,
            "Choisir la racine loras déjà déclarée à Forge",
            self.forge_lora_expose_path_edit.text(),
        )

        if directory:
            self.forge_lora_expose_path_edit.setText(directory)

    def browse_comfyui_path(self):

        directory = QFileDialog.getExistingDirectory(
            self, "Choisir le dossier de données ComfyUI (--base-directory)", self.comfyui_path_edit.text()
        )

        if directory:
            self.comfyui_path_edit.setText(directory)

    def browse_onetrainer_path(self):

        directory = QFileDialog.getExistingDirectory(
            self, "Choisir le dossier d'installation OneTrainer", self.onetrainer_path_edit.text()
        )

        if directory:
            self.onetrainer_path_edit.setText(directory)

    def browse_comfyui_install_path(self):
        """
        Mission 113: selecting a new folder here must invalidate the
        static install-validation status exactly like a real keystroke
        would (_on_comfyui_install_path_edited below) — textEdited
        never fires from this programmatic setText(), so this method
        calls the same reset explicitly. Never touches
        comfyui_connection_status_label (Mission 112's HTTP diagnostic
        is an independent concept).
        """
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choisir le dossier d'installation ComfyUI (Local/Desktop)",
            self.comfyui_install_path_edit.text(),
        )

        if directory:
            self.comfyui_install_path_edit.setText(directory)
            self._on_comfyui_install_path_edited(directory)

    def browse_forge_path(self):
        """
        Mission 113: same rationale as browse_comfyui_install_path()
        above, for Forge.
        """
        directory = QFileDialog.getExistingDirectory(
            self, "Choisir le dossier d'installation Forge", self.forge_path_edit.text()
        )

        if directory:
            self.forge_path_edit.setText(directory)
            self._on_forge_path_edited(directory)

    def check_comfyui_install(self):
        """
        Mission 113: static, read-only filesystem validation of the
        ComfyUI Local/Desktop installation currently typed in
        comfyui_install_path_edit — never necessarily the already-saved
        one, same "test the currently displayed value" principle as
        test_comfyui_connection() below. Never touches the network,
        never calls save_application_settings(). Deliberately
        independent from comfyui_connection_status_label (Mission 112):
        this only proves an installation exists on disk, never that a
        backend is currently reachable.
        """
        try:
            resolve_comfyui_install(self.comfyui_install_path_edit.text())
        except ComfyUIInstallError as error:
            self.comfyui_install_status_label.setText(str(error))
            return

        self.comfyui_install_status_label.setText("Installation ComfyUI reconnue.")

    def check_forge_install(self):
        """
        Mission 113: same rationale as check_comfyui_install() above,
        for Forge.
        """
        try:
            resolve_forge_install(self.forge_path_edit.text())
        except ForgeInstallError as error:
            self.forge_install_status_label.setText(str(error))
            return

        self.forge_install_status_label.setText("Installation Forge reconnue.")

    def _on_comfyui_install_path_edited(self, _text):
        # Mission 113: a real user edit (keystroke or Browse selection)
        # invalidates any previous static validation result for ComfyUI
        # only — never comfyui_connection_status_label (Mission 112),
        # which depends on comfyui_url, not on this path.
        self.comfyui_install_status_label.setText("Installation non vérifiée.")

    def _on_forge_path_edited(self, _text):
        # Mission 113: same rationale as _on_comfyui_install_path_edited()
        # above, for Forge.
        self.forge_install_status_label.setText("Installation non vérifiée.")

    def test_comfyui_connection(self):
        """
        Mission 112: explicit, dedicated reachability check — uses the
        URL currently typed in comfyui_url_edit, never necessarily the
        already-saved one (same transient-engine pattern as
        refresh_checkpoints()/refresh_loras() below). Never touches
        comfyui_checkpoint_name_edit/comfyui_lora_name_edit, never calls
        save_application_settings(). check_connection() propagates
        ComfyUIEngineError unchanged on failure (Mission 112 contract) —
        its message already names the engine and the URL, so it is
        shown as-is rather than through a new translation layer.
        """
        engine = ComfyUIEngine(
            base_url=self.comfyui_url_edit.text(), timeout=CONNECTION_TEST_TIMEOUT
        )

        try:
            engine.check_connection()
        except ComfyUIEngineError as error:
            self.comfyui_connection_status_label.setText(str(error))
            return

        self.comfyui_connection_status_label.setText("ComfyUI disponible.")

    def start_comfyui(self):
        """
        Mission 114: delegates entirely to comfyui_lifecycle_manager,
        using whatever is currently typed in comfyui_path_edit/
        comfyui_install_path_edit/comfyui_url_edit — never necessarily
        the already-saved values, same convention as
        check_comfyui_install()/test_comfyui_connection() above. All
        state feedback arrives back through state_changed
        (_on_comfyui_lifecycle_state_changed below), never read
        synchronously here.
        """
        self.comfyui_lifecycle_manager.start(
            self.comfyui_path_edit.text(),
            self.comfyui_install_path_edit.text(),
            self.comfyui_url_edit.text(),
        )

    def stop_comfyui(self):
        self.comfyui_lifecycle_manager.stop()

    def _on_comfyui_lifecycle_state_changed(self, state):
        # Mission 114: kept visually and mechanically distinct from
        # comfyui_install_status_label (M113, installation presence on
        # disk) and comfyui_connection_status_label (M112, HTTP
        # reachability) — this label only ever reflects Toolkit's own
        # process ownership.
        messages = {
            STOPPED: "ComfyUI non démarré par Toolkit.",
            EXTERNAL_ACTIVE: "ComfyUI déjà joignable — non géré par Toolkit.",
            STARTING: "Démarrage de ComfyUI en cours…",
            RUNNING_OWNED: "ComfyUI démarré et possédé par Toolkit.",
            STOPPING: "Arrêt de ComfyUI en cours…",
            START_FAILED: self.comfyui_lifecycle_manager.last_error_message or "Échec du démarrage de ComfyUI.",
        }
        self.comfyui_lifecycle_status_label.setText(messages.get(state, state))

        self.comfyui_start_button.setEnabled(state in (STOPPED, EXTERNAL_ACTIVE, START_FAILED))
        self.comfyui_stop_button.setEnabled(state == RUNNING_OWNED)

    def test_forge_connection(self):
        """
        Mission 112: same rationale as test_comfyui_connection() above,
        for Forge — the first and only connectivity check of any kind
        for Forge in SettingsPage.
        """
        engine = ForgeEngine(
            base_url=self.forge_url_edit.text(), timeout=CONNECTION_TEST_TIMEOUT
        )

        try:
            engine.check_connection()
        except ForgeEngineError as error:
            self.forge_connection_status_label.setText(str(error))
            return

        self.forge_connection_status_label.setText("Forge disponible.")

    def _on_comfyui_url_edited(self, _text):
        # Mission 112: a real user keystroke in comfyui_url_edit
        # invalidates any previous test result for ComfyUI only —
        # textEdited never fires from update_application_settings()'s
        # own setText() reload, so this never falsely resets on load.
        self.comfyui_connection_status_label.setText("Connexion non testée.")

    def _on_forge_url_edited(self, _text):
        # Mission 112: same rationale as _on_comfyui_url_edited() above,
        # for Forge only.
        self.forge_connection_status_label.setText("Connexion non testée.")

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

    def _on_settings_changed(self):
        # Mission 078: only ever connected to textChanged, so this never
        # fires during a programmatic load protected by
        # _load_settings_fields()'s blockSignals() — genuine user typing
        # is the only way this can run.
        self._dirty = True

    def _load_settings_fields(self):
        # Mission 078: unconditional — bypasses the dirty-state guard on
        # purpose. Shared by update_settings() (auto-refresh, only called
        # when not dirty), reset_for_context_change() (real context change,
        # must always discard any draft) and save_settings()'s failure
        # branch (must always show the restored Domain value, never the
        # rejected input, per the Mission 077 contract).
        settings = self.settings_manager.settings

        self.theme_edit.blockSignals(True)
        self.language_edit.blockSignals(True)
        self.theme_edit.setText(settings.theme)
        self.language_edit.setText(settings.language)
        self.theme_edit.blockSignals(False)
        self.language_edit.blockSignals(False)

        self._dirty = False

    def update_settings(self, payload=None):
        # Mission 078: subscribed (see main_window.py) only to
        # WORKSPACE_SAVED/WORKSPACE_RENAMED — a Workspace is necessarily
        # already open for either event to fire, so theme_edit/
        # language_edit/save_button are already enabled and left alone
        # here. WORKSPACE_CREATED/OPENED/CLOSED are handled exclusively by
        # reset_for_context_change() below, so this dirty-draft protection
        # never depends on subscriber ordering between the two methods.
        if self._dirty:
            # Mutation independent of this Page's own draft (e.g. any
            # other Manager's save()) — preserve the unsaved input.
            return

        self._load_settings_fields()

    def reset_for_context_change(self, payload=None):
        """
        Subscribed by MainWindow to WORKSPACE_CREATED/OPENED/CLOSED —
        never to update_settings()'s own events. These are genuine
        Workspace context changes: the Settings object update_settings()
        would otherwise reload from may no longer be the one the user was
        editing (a different Workspace, or none at all) — any draft must
        be unconditionally discarded here, never preserved by a dirty
        check the way update_settings() does.
        """
        opened = payload is not None

        self.theme_edit.setEnabled(opened)
        self.language_edit.setEnabled(opened)
        self.save_button.setEnabled(opened)

        self._load_settings_fields()

    def confirm_context_change(self) -> bool:
        """
        Mission 078: same role as PromptsPage.confirm_context_change()
        (Mission 069) — called by MainWindow before a Workspace switch
        (new_project()/open_project()) that would otherwise let
        reset_for_context_change() silently discard an unsaved theme/
        language draft once current_workspace is replaced, too late for a
        genuine Save or Cancel. Returns True if the caller may proceed
        with the switch, False if it must be abandoned entirely (Cancel,
        or a save() failure — which must never let the switch continue).
        Mission 079 reuses this same guard from closeEvent() before
        closing the whole application.
        """
        if not self._dirty:
            return True

        box = QMessageBox(self)
        box.setWindowTitle("Modifications non enregistrées")
        box.setText(
            "Les préférences du Workspace (thème/langue) contiennent des "
            "modifications non enregistrées. Que souhaitez-vous faire ?"
        )
        box.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        box.setButtonText(QMessageBox.Save, "Enregistrer")
        box.setButtonText(QMessageBox.Discard, "Ignorer les modifications")
        box.setButtonText(QMessageBox.Cancel, "Annuler")
        box.setDefaultButton(QMessageBox.Cancel)
        choice = box.exec()

        if choice == QMessageBox.Cancel:
            return False

        if choice == QMessageBox.Save:
            try:
                self.settings_manager.update(
                    theme=self.theme_edit.text(),
                    language=self.language_edit.text(),
                )
            except WorkspaceManagerError as exc:
                QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Impossible d'enregistrer les préférences avant de changer de projet : {exc}"
                )
                self._load_settings_fields()
                return False

        self._dirty = False
        return True

    def update_application_settings(self, payload=None):

        settings = self.application_settings_manager.settings

        self.python_path_edit.setText(settings.python_path)
        self.comfyui_path_edit.setText(settings.comfyui_path)
        self.comfyui_install_path_edit.setText(settings.comfyui_install_path)
        self.onetrainer_path_edit.setText(settings.onetrainer_path)
        self.comfyui_url_edit.setText(settings.comfyui_url)
        self.comfyui_checkpoint_name_edit.setCurrentText(settings.comfyui_checkpoint_name)
        self.comfyui_lora_name_edit.setCurrentText(settings.comfyui_lora_name)
        self.comfyui_lora_strength_edit.setValue(settings.comfyui_lora_strength)
        self.ollama_url_edit.setText(settings.ollama_url)
        self.ollama_path_edit.setText(settings.ollama_path)
        self.ollama_model_name_edit.setCurrentText(settings.ollama_model_name)
        self.lora_library_path_edit.setText(settings.lora_library_path)
        self.comfyui_lora_expose_path_edit.setText(settings.comfyui_lora_expose_path)
        self.forge_path_edit.setText(settings.forge_path)
        self.forge_url_edit.setText(settings.forge_url)
        self.forge_lora_expose_path_edit.setText(settings.forge_lora_expose_path)
