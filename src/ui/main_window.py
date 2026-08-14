from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QSplitter,
    QStackedWidget,
    QFileDialog,
    QMessageBox,
)

from src.core.event_bus import EventBus
from src.managers.workspace_manager import (
    WorkspaceManager,
    WorkspaceManagerError,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_SAVED,
    WORKSPACE_CLOSED,
)
from src.managers.character_manager import (
    CharacterManager,
    CHARACTER_CREATED,
    CHARACTER_SELECTED,
    CHARACTER_DELETED,
)
from src.managers.dataset_manager import (
    DatasetManager,
    DATASET_CREATED,
    DATASET_SELECTED,
    DATASET_DELETED,
)
from src.managers.lora_manager import (
    LoRAManager,
    LORA_CREATED,
    LORA_SELECTED,
    LORA_DELETED,
)
from src.managers.prompt_manager import (
    PromptManager,
    PROMPT_CREATED,
    PROMPT_SELECTED,
    PROMPT_DELETED,
)
from src.managers.training_manager import (
    TrainingManager,
    TRAINING_CREATED,
    TRAINING_SELECTED,
    TRAINING_DELETED,
)
from src.managers.model_manager import (
    ModelManager,
    MODEL_CREATED,
    MODEL_SELECTED,
    MODEL_DELETED,
)
from src.managers.workflow_manager import (
    WorkflowManager,
    WORKFLOW_CREATED,
    WORKFLOW_SELECTED,
    WORKFLOW_DELETED,
)
from src.managers.settings_manager import SettingsManager
from src.managers.application_settings_manager import (
    ApplicationSettingsManager,
    APPLICATION_SETTINGS_UPDATED,
)
from src.managers.generation_manager import GenerationManager
from src.engines.comfyui_engine import ComfyUIEngine

from src.ui.sidebar import Sidebar
from src.ui.toolbar import MainToolBar
from src.ui.statusbar import MainStatusBar
from src.ui.menubar import MainMenuBar

from src.ui.pages.dashboard_page import DashboardPage
from src.ui.pages.characters_page import CharactersPage
from src.ui.pages.images_page import ImagesPage
from src.ui.pages.datasets_page import DatasetsPage
from src.ui.pages.models_page import ModelsPage
from src.ui.pages.workflows_page import WorkflowsPage
from src.ui.pages.lora_page import LoRAPage
from src.ui.pages.prompts_page import PromptsPage
from src.ui.pages.training_page import TrainingPage
from src.ui.pages.inference_page import InferencePage
from src.ui.pages.settings_page import SettingsPage

from src.ui.dialogs.new_project_dialog import NewProjectDialog

# Mission 013: this machine's ComfyUI Desktop instance was empirically
# observed listening on this port (see Mission 012's post-release smoke
# tests), not ComfyUIEngine's own default of 8188 — this is a
# temporary, explicitly injectable wiring-time value, not a universal
# ComfyUI constant. ApplicationSettings.comfyui_url (deferred, Mission
# 013 audit) is the right place to make this genuinely configurable
# once a real UI need exists.
COMFYUI_BASE_URL = "http://127.0.0.1:8000"

# Same reasoning: the checkpoint actually validated against this
# machine's installation (Mission 012's smoke test) does not match
# comfyui_engine.DEMO_CHECKPOINT_NAME exactly. Injected here, not
# hardcoded into GenerationManager's or ComfyUIEngine's own defaults.
COMFYUI_CHECKPOINT_NAME = "v1-5-pruned-emaonly-fp16.safetensors"


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        # Workspace courant — source unique de vérité (WorkspaceManager)
        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(
            self.workspace_manager, event_bus=self.event_bus
        )
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.lora_manager = LoRAManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.prompt_manager = PromptManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.training_manager = TrainingManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        # Model is Workspace-owned, not Character-owned (Blueprint —
        # see Mission 006's architecture audit) — no character_manager
        # dependency, unlike the three Managers above.
        self.model_manager = ModelManager(
            self.workspace_manager, event_bus=self.event_bus
        )
        # Workflow is Workspace-owned too (Mission 007's architecture
        # audit) — no character_manager dependency, same as Model.
        self.workflow_manager = WorkflowManager(
            self.workspace_manager, event_bus=self.event_bus
        )
        # Settings is Workspace-owned like Model/Workflow, but it is a
        # singleton (Workspace.settings), not a collection — no
        # selection concept, no events of its own, no event_bus
        # dependency at all.
        self.settings_manager = SettingsManager(self.workspace_manager)
        # ApplicationSettings is a separate, machine-local persistence
        # tier — entirely independent of any Workspace. No
        # storage_directory override here: real usage resolves to
        # %LOCALAPPDATA%\AIStudioToolkit\ automatically.
        self.application_settings_manager = ApplicationSettingsManager(
            event_bus=self.event_bus
        )
        # ComfyUIEngine/GenerationManager: Mission 013's first real
        # consumer. GenerationManager stays Qt-free and knows nothing
        # about Workspace — no event_bus dependency, no CRUD events of
        # its own (see src/managers/generation_manager.py).
        self.comfyui_engine = ComfyUIEngine(base_url=COMFYUI_BASE_URL)
        self.generation_manager = GenerationManager(
            self.comfyui_engine, checkpoint_name=COMFYUI_CHECKPOINT_NAME
        )

        # Fenêtre
        self.setWindowTitle("AI Studio Toolkit")
        self.resize(1700, 950)

        # Barre de menu / outils / statut
        self.menu = MainMenuBar()
        self.setMenuBar(self.menu)

        self.addToolBar(MainToolBar())
        self.setStatusBar(MainStatusBar())
        self.menu.action_new_project.triggered.connect(self.new_project)
        self.menu.action_open_project.triggered.connect(self.open_project)
        self.menu.action_save_project.triggered.connect(self.save_project)
        self.menu.action_exit.triggered.connect(self.close)

        # Widget principal
        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)

        # Sidebar
        self.sidebar = Sidebar()
        splitter.addWidget(self.sidebar)

        # Pages
        self.stack = QStackedWidget()

        self.dashboard_page = DashboardPage()
        self.characters_page = CharactersPage(self.character_manager)
        self.images_page = ImagesPage(self.workspace_manager)
        self.datasets_page = DatasetsPage(self.dataset_manager)
        self.lora_page = LoRAPage(self.lora_manager)
        self.prompts_page = PromptsPage(self.prompt_manager)
        self.training_page = TrainingPage(self.training_manager, self.dataset_manager)
        self.models_page = ModelsPage(self.model_manager)
        self.workflows_page = WorkflowsPage(self.workflow_manager)
        self.settings_page = SettingsPage(
            self.settings_manager, self.application_settings_manager
        )

        # Mission 017: Dashboard quick-action buttons wired directly to
        # the already-existing methods they duplicate no logic of —
        # MainWindow.new_project()/open_project() (menu already wired to
        # the same methods) and ImagesPage.import_images() (its own
        # "Importer des images" button already calls this directly).
        # DashboardPage itself stays a pure UI view: no Manager/Workspace
        # reference of its own.
        self.dashboard_page.newProjectButton.clicked.connect(self.new_project)
        self.dashboard_page.openProjectButton.clicked.connect(self.open_project)
        self.dashboard_page.importImagesButton.clicked.connect(
            self.images_page.import_images
        )

        # DashboardPage.update_project() / ImagesPage.update_images() both
        # expect a plain dict (read via .get()), so they work with
        # workspace.to_dict() — already what WorkspaceManager publishes —
        # without depending on the Workspace domain class. Keeps
        # Presentation independent of Domain, per the Blueprint's
        # layering rules.
        workspace_events = (
            WORKSPACE_CREATED,
            WORKSPACE_OPENED,
            WORKSPACE_SAVED,
            WORKSPACE_CLOSED,
        )

        for event_name in workspace_events:
            self.event_bus.subscribe(event_name, self.dashboard_page.update_project)
            self.event_bus.subscribe(event_name, self.images_page.update_images)
            self.event_bus.subscribe(event_name, self.characters_page.update_characters)
            self.event_bus.subscribe(event_name, self.datasets_page.update_datasets)
            self.event_bus.subscribe(event_name, self.lora_page.update_loras)
            self.event_bus.subscribe(event_name, self.prompts_page.update_prompts)
            self.event_bus.subscribe(event_name, self.training_page.update_trainings)
            self.event_bus.subscribe(event_name, self.models_page.update_models)
            self.event_bus.subscribe(event_name, self.workflows_page.update_workflows)
            self.event_bus.subscribe(event_name, self.settings_page.update_settings)

        # CharactersPage/DatasetsPage/LoRAPage/PromptsPage/TrainingPage also
        # refresh on their own manager's events — list_characters()/
        # list_datasets()/list_loras()/list_prompts()/list_trainings() are
        # always re-read from the manager rather than trusting the
        # per-item payload (which carries only the one item that changed,
        # not the full list).
        for event_name in (CHARACTER_CREATED, CHARACTER_SELECTED, CHARACTER_DELETED):
            self.event_bus.subscribe(event_name, self.characters_page.update_characters)
            self.event_bus.subscribe(event_name, self.datasets_page.update_datasets)
            self.event_bus.subscribe(event_name, self.lora_page.update_loras)
            self.event_bus.subscribe(event_name, self.prompts_page.update_prompts)
            self.event_bus.subscribe(event_name, self.training_page.update_trainings)

        for event_name in (DATASET_CREATED, DATASET_SELECTED, DATASET_DELETED):
            self.event_bus.subscribe(event_name, self.datasets_page.update_datasets)

        for event_name in (LORA_CREATED, LORA_SELECTED, LORA_DELETED):
            self.event_bus.subscribe(event_name, self.lora_page.update_loras)

        for event_name in (PROMPT_CREATED, PROMPT_SELECTED, PROMPT_DELETED):
            self.event_bus.subscribe(event_name, self.prompts_page.update_prompts)

        for event_name in (MODEL_CREATED, MODEL_SELECTED, MODEL_DELETED):
            self.event_bus.subscribe(event_name, self.models_page.update_models)

        for event_name in (WORKFLOW_CREATED, WORKFLOW_SELECTED, WORKFLOW_DELETED):
            self.event_bus.subscribe(event_name, self.workflows_page.update_workflows)

        for event_name in (TRAINING_CREATED, TRAINING_SELECTED, TRAINING_DELETED):
            self.event_bus.subscribe(event_name, self.training_page.update_trainings)

        # Separate from workspace_events on purpose: ApplicationSettings
        # has nothing to do with the Workspace lifecycle, so its refresh
        # must never be wired into that loop.
        self.event_bus.subscribe(
            APPLICATION_SETTINGS_UPDATED, self.settings_page.update_application_settings
        )

        self.inference_page = InferencePage(self.generation_manager, self.workspace_manager)

        # Mission 014 final review: a pending (not-yet-accepted)
        # generation result belongs exclusively to the workspace that
        # was active when it was produced. WORKSPACE_CREATED/OPENED/
        # CLOSED are the only three events that actually change which
        # workspace WorkspaceManager.current_workspace points to —
        # WORKSPACE_SAVED deliberately excluded, since saving (including
        # Accept's own add_images()->save()) never changes that context.
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            self.event_bus.subscribe(event_name, self.inference_page.reset_for_workspace_change)

        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.characters_page)
        self.stack.addWidget(self.images_page)
        self.stack.addWidget(self.datasets_page)
        self.stack.addWidget(self.models_page)
        self.stack.addWidget(self.workflows_page)
        self.stack.addWidget(self.lora_page)
        self.stack.addWidget(self.prompts_page)
        self.stack.addWidget(self.training_page)
        self.stack.addWidget(self.inference_page)
        self.stack.addWidget(self.settings_page)

        splitter.addWidget(self.stack)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

        self.sidebar.currentRowChanged.connect(
            self.stack.setCurrentIndex
        )

        self.sidebar.setCurrentRow(0)

    # ======================================================
    # Gestion des projets
    # ======================================================

    def new_project(self):

        dialog = NewProjectDialog(self)

        if dialog.exec() != QDialog.Accepted:
            return

        try:
            self.workspace_manager.create(dialog.target_path)
        except WorkspaceManagerError as exc:
            QMessageBox.critical(self, "Erreur", str(exc))
            return

        self.statusBar().showMessage("Projet créé")

    def open_project(self):

        folder = QFileDialog.getExistingDirectory(
            self,
            "Ouvrir un projet"
        )

        if not folder:
            return

        try:
            workspace = self.workspace_manager.open(folder)
        except WorkspaceManagerError as exc:
            QMessageBox.critical(self, "Erreur", str(exc))
            return

        if workspace is None:
            self.statusBar().showMessage("Projet invalide")
            return

        self.statusBar().showMessage(
            f"Projet ouvert : {workspace.name}"
        )

    def save_project(self):

        if not self.workspace_manager.opened:
            self.statusBar().showMessage("Aucun projet ouvert")
            return

        try:
            self.workspace_manager.save()
        except WorkspaceManagerError as exc:
            QMessageBox.critical(self, "Erreur", str(exc))
            return

        self.statusBar().showMessage("Projet sauvegardé")

    def closeEvent(self, event):
        # Mission 013 — minimal handling: never leave a generation
        # thread dangling when the application closes. No cancellation,
        # just a deterministic wait for the in-progress worker to stop.
        self.inference_page.shutdown()
        super().closeEvent(event)