from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
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
    WorkspaceRenamePermissionError,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_SAVED,
    WORKSPACE_CLOSED,
    WORKSPACE_RENAMED,
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
from src.managers.lora_library_manager import (
    LoRALibraryManager,
    LORA_LIBRARY_IMPORTED,
    LORA_LIBRARY_DELETED,
    LORA_LIBRARY_UPDATED,
)
from src.managers.generation_manager import GenerationManager
from src.managers.prompt_assistant_manager import PromptAssistantManager
from src.engines.comfyui_engine import ComfyUIEngine
from src.engines.ollama_engine import OllamaEngine

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
from src.ui.dialogs.rename_project_dialog import RenameProjectDialog


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
        # Mission 087: the central LoRA library registry — like
        # ApplicationSettings, a separate machine-local persistence tier
        # entirely independent of any Workspace. Built before
        # ApplicationSettingsManager below and injected into it (to
        # enforce the lora_library_path change lock) rather than the
        # other way around: LoRALibraryManager holds no library_root
        # state of its own (see its own docstring), so it has no
        # dependency on ApplicationSettings and this ordering avoids any
        # circular Manager dependency.
        self.lora_library_manager = LoRALibraryManager(event_bus=self.event_bus)
        # ApplicationSettings is a separate, machine-local persistence
        # tier — entirely independent of any Workspace. No
        # storage_directory override here: real usage resolves to
        # %LOCALAPPDATA%\AIStudioToolkit\ automatically.
        self.application_settings_manager = ApplicationSettingsManager(
            event_bus=self.event_bus,
            lora_library_manager=self.lora_library_manager,
        )
        # ComfyUIEngine/GenerationManager: Mission 013's first real
        # consumer. GenerationManager stays Qt-free and knows nothing
        # about Workspace — no event_bus dependency, no CRUD events of
        # its own (see src/managers/generation_manager.py). Mission 018:
        # base_url/checkpoint_name come exclusively from
        # ApplicationSettings, read once here at startup — it is the
        # sole source of truth, no fallback constant exists in this
        # file. A later change saved via SettingsPage only takes effect
        # on the next application start (no hot reload, by design).
        self.comfyui_engine = ComfyUIEngine(
            base_url=self.application_settings_manager.settings.comfyui_url
        )
        self.generation_manager = GenerationManager(
            self.comfyui_engine,
            checkpoint_name=self.application_settings_manager.settings.comfyui_checkpoint_name,
            # Mission 059: same no-hot-reload contract as checkpoint_name
            # above — a later change saved via SettingsPage only takes
            # effect on the next application start.
            lora_name=self.application_settings_manager.settings.comfyui_lora_name,
            lora_strength=self.application_settings_manager.settings.comfyui_lora_strength,
        )
        # Mission 031: same composition-root pattern as comfyui_engine/
        # generation_manager above — built once here from
        # ApplicationSettings, exactly the existing no-hot-reload
        # contract already documented for ComfyUI (a later change saved
        # via SettingsPage only takes effect on the next application
        # start; see SettingsPage's own application_hint label, which
        # already names "ComfyUI/Ollama" together). PromptAssistantManager
        # never imports OllamaEngine's own type beyond this single
        # construction site — every consumer (InferencePage, PromptsPage
        # — Mission 032) only ever sees PromptAssistantManager, one
        # shared instance injected into both.
        self.ollama_engine = OllamaEngine(
            base_url=self.application_settings_manager.settings.ollama_url
        )
        self.prompt_assistant_manager = PromptAssistantManager(
            self.ollama_engine,
            model_name=self.application_settings_manager.settings.ollama_model_name,
        )

        # Fenêtre
        self.setWindowTitle("AI Studio Toolkit")
        # Mission 060: 1700x950 stays the preferred default, but is
        # never allowed to exceed the actually usable screen area
        # (availableGeometry() excludes the taskbar/reserved zones,
        # unlike geometry()). screen() falls back to primaryScreen()
        # (both can be None before any window is shown on some
        # platforms); if neither is available, the historical default
        # is kept as-is rather than failing.
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            width = min(1700, available.width())
            height = min(950, available.height())
        else:
            width, height = 1700, 950
        self.resize(width, height)

        # Barre de menu / outils / statut
        self.menu = MainMenuBar()
        self.setMenuBar(self.menu)

        self.toolbar = MainToolBar()
        self.addToolBar(self.toolbar)
        self.setStatusBar(MainStatusBar())
        self.menu.action_new_project.triggered.connect(self.new_project)
        self.menu.action_open_project.triggered.connect(self.open_project)
        self.menu.action_save_project.triggered.connect(self.save_project)
        self.menu.action_rename_project.triggered.connect(self.rename_project)
        self.menu.action_exit.triggered.connect(self.close)
        self.toolbar.action_open.triggered.connect(self.open_project)
        self.toolbar.action_save.triggered.connect(self.save_project)

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
        self.characters_page = CharactersPage(self.character_manager, self.workspace_manager)
        self.images_page = ImagesPage(self.workspace_manager)
        self.datasets_page = DatasetsPage(self.dataset_manager, self.workspace_manager)
        self.lora_page = LoRAPage(
            self.lora_manager,
            self.workspace_manager,
            self.lora_library_manager,
            self.application_settings_manager,
        )
        self.prompts_page = PromptsPage(
            self.prompt_manager, self.prompt_assistant_manager, self.character_manager,
            self.workspace_manager,
        )
        self.training_page = TrainingPage(
            self.training_manager, self.dataset_manager, self.workspace_manager
        )
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
            WORKSPACE_RENAMED,
        )

        for event_name in workspace_events:
            self.event_bus.subscribe(event_name, self.dashboard_page.update_project)
            self.event_bus.subscribe(event_name, self.images_page.update_images)
            self.event_bus.subscribe(event_name, self.datasets_page.update_datasets)
            self.event_bus.subscribe(event_name, self.training_page.update_trainings)
            self.event_bus.subscribe(event_name, self.models_page.update_models)
            self.event_bus.subscribe(event_name, self.workflows_page.update_workflows)

        # Mission 078: CharactersPage.update_characters()/LoRAPage.
        # update_loras()/SettingsPage.update_settings() are deliberately
        # NOT subscribed to WORKSPACE_CREATED/OPENED/CLOSED (unlike every
        # other Page above) — those 3 events are a genuine Workspace
        # context reset, handled exclusively by each Page's own
        # reset_for_context_change() below, so the dirty-draft protection
        # (identity fiche / LoRA metadata / theme+language) never depends
        # on subscriber ordering between the two methods. Same precedent
        # as PromptsPage (Mission 038).
        for event_name in (WORKSPACE_SAVED, WORKSPACE_RENAMED):
            self.event_bus.subscribe(event_name, self.characters_page.update_characters)
            self.event_bus.subscribe(event_name, self.lora_page.update_loras)
            self.event_bus.subscribe(event_name, self.settings_page.update_settings)

        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            self.event_bus.subscribe(event_name, self.characters_page.reset_for_context_change)
            self.event_bus.subscribe(event_name, self.lora_page.reset_for_context_change)
            self.event_bus.subscribe(event_name, self.settings_page.reset_for_context_change)

        # Mission 089/090: the central-library tab of LoRAPage is
        # Application-level — deliberately its own set of subscriptions,
        # never mixed into the Workspace/Character events above.
        for event_name in (LORA_LIBRARY_IMPORTED, LORA_LIBRARY_DELETED, LORA_LIBRARY_UPDATED):
            self.event_bus.subscribe(event_name, self.lora_page.update_central_library)

        # CharactersPage/DatasetsPage/LoRAPage/PromptsPage/TrainingPage also
        # refresh on their own manager's events — list_characters()/
        # list_datasets()/list_loras()/list_prompts()/list_trainings() are
        # always re-read from the manager rather than trusting the
        # per-item payload (which carries only the one item that changed,
        # not the full list).
        #
        # Mission 078: CHARACTER_CREATED never changes principal_character_id
        # (create() never touches active_character_id) and never changes
        # LoRAManager.active_lora_id either — both go to the auto-refresh
        # method, which safely no-ops on their own dirty-draft via its own
        # id comparison. CHARACTER_SELECTED/DELETED genuinely change
        # principal_character_id/reset active_lora_id — a real context
        # change for CharactersPage/LoRAPage, routed to
        # reset_for_context_change() instead.
        self.event_bus.subscribe(CHARACTER_CREATED, self.characters_page.update_characters)
        self.event_bus.subscribe(CHARACTER_CREATED, self.datasets_page.update_datasets)
        self.event_bus.subscribe(CHARACTER_CREATED, self.lora_page.update_loras)
        self.event_bus.subscribe(CHARACTER_CREATED, self.training_page.update_trainings)

        for event_name in (CHARACTER_SELECTED, CHARACTER_DELETED):
            self.event_bus.subscribe(event_name, self.characters_page.reset_for_context_change)
            self.event_bus.subscribe(event_name, self.datasets_page.update_datasets)
            self.event_bus.subscribe(event_name, self.lora_page.reset_for_context_change)
            self.event_bus.subscribe(event_name, self.training_page.update_trainings)

        # Mission 038: PromptsPage.update_prompts() is deliberately NOT
        # subscribed to WORKSPACE_CREATED/OPENED/CLOSED or CHARACTER_
        # SELECTED/DELETED (unlike every other Page above) — those 5
        # events are a genuine Workspace/Character context reset, handled
        # exclusively by PromptsPage.reset_for_context_change() below, so
        # the dirty-draft protection never depends on subscriber
        # ordering between the two methods. update_prompts() only ever
        # receives the events where an unsaved draft must be preserved
        # by default (WORKSPACE_SAVED/RENAMED, CHARACTER_CREATED) or
        # where PromptManager.active_prompt_id itself is the correct
        # signal to react to (PROMPT_CREATED/SELECTED/DELETED, see the
        # dedicated loop further below).
        for event_name in (WORKSPACE_SAVED, WORKSPACE_RENAMED):
            self.event_bus.subscribe(event_name, self.prompts_page.update_prompts)

        self.event_bus.subscribe(CHARACTER_CREATED, self.prompts_page.update_prompts)

        for event_name in (
            WORKSPACE_CREATED,
            WORKSPACE_OPENED,
            WORKSPACE_CLOSED,
            CHARACTER_SELECTED,
            CHARACTER_DELETED,
        ):
            self.event_bus.subscribe(event_name, self.prompts_page.reset_for_context_change)

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

        self.inference_page = InferencePage(
            self.generation_manager,
            self.workspace_manager,
            self.prompt_manager,
            self.prompt_assistant_manager,
            self.character_manager,
        )

        # Mission 014 final review: a pending (not-yet-accepted)
        # generation result belongs exclusively to the workspace that
        # was active when it was produced. WORKSPACE_CREATED/OPENED/
        # CLOSED/RENAMED are the events that actually change which
        # workspace (or which root path) WorkspaceManager.current_workspace
        # points to — WORKSPACE_SAVED deliberately excluded, since saving
        # (including Accept's own add_images()->save()) never changes
        # that context. WORKSPACE_RENAMED added in Mission 027: a rename
        # changes current_workspace.root, so a pending result's absolute
        # path (computed from the pre-rename root) can no longer be
        # trusted and must be invalidated the same way as Created/Opened/
        # Closed.
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED, WORKSPACE_RENAMED):
            self.event_bus.subscribe(event_name, self.inference_page.reset_for_workspace_change)

        # Mission 083: InferencePage.prompt's own dirty-draft protection
        # — deliberately a *separate* method/subscription from
        # reset_for_workspace_change() above, which stays responsible for
        # _pending_path/the reference selection on its own unrelated
        # 4-event set (including WORKSPACE_RENAMED, which must never
        # clear the prompt — see reset_for_context_change()'s own
        # docstring). Same 3-event set as CharactersPage/LoRAPage/
        # SettingsPage's own reset_for_context_change() (Mission 078).
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            self.event_bus.subscribe(event_name, self.inference_page.reset_for_context_change)

        # Mission 033: PromptsPage never references InferencePage —
        # MainWindow is the sole mediator (Option A, see
        # docs/missions/MISSION_033.md section 4.1). Not an EventBus
        # event: no Domain mutation happens here, only a Presentation-
        # layer intent, unlike every event_bus.subscribe() call above.
        self.prompts_page.send_to_inference_requested.connect(
            self._on_prompts_send_to_inference
        )

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

        # Mission 069: a dirty PromptsPage draft would otherwise be
        # silently discarded by reset_for_context_change() once
        # current_workspace is replaced below — too late for a genuine
        # Save or Cancel. Must run before workspace_manager.create().
        # Mission 078: same guard extended to CharactersPage/LoRAPage/
        # SettingsPage, which now carry the same kind of unsaved draft.
        if not self.prompts_page.confirm_context_change():
            return

        if not self.characters_page.confirm_context_change():
            return

        if not self.lora_page.confirm_context_change():
            return

        if not self.settings_page.confirm_context_change():
            return

        # Mission 083: appended after the 4 existing guards, same
        # contract, same early-return-on-False pattern — InferencePage's
        # prompt draft is an independent Domain entity (a future Prompt),
        # unrelated to the other 4, so no reordering of those is needed.
        if not self.inference_page.confirm_context_change():
            return

        # Mission 084: 6th and last guard — an independent draft
        # (a not-yet-Accept/Reject generation result, a future
        # Workspace.images entry) from the prompt-text guard just
        # above, deliberately kept as a separate method/dialog rather
        # than merged into confirm_context_change() (see that method's
        # own docstring).
        if not self.inference_page.confirm_pending_result_change():
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

        # Mission 069: same guard as new_project() — must run before
        # workspace_manager.open() replaces current_workspace.
        # Mission 078: same guard extended to CharactersPage/LoRAPage/
        # SettingsPage, which now carry the same kind of unsaved draft.
        if not self.prompts_page.confirm_context_change():
            return

        if not self.characters_page.confirm_context_change():
            return

        if not self.lora_page.confirm_context_change():
            return

        if not self.settings_page.confirm_context_change():
            return

        # Mission 083: same append as new_project() above.
        if not self.inference_page.confirm_context_change():
            return

        # Mission 084: same 6th guard as new_project() above.
        if not self.inference_page.confirm_pending_result_change():
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

    def rename_project(self):

        if not self.workspace_manager.opened:
            self.statusBar().showMessage("Aucun projet ouvert")
            return

        # Mission 085: checked before the dialog is even shown — a
        # rename physically moves the whole Workspace root while a
        # generation may still be writing its result into it (see
        # MISSION_085.md), so there is no point asking the user for a
        # new name only to refuse the operation afterward.
        if not self.inference_page.confirm_no_active_generation(
            "Une génération est en cours. Attendez qu'elle soit terminée "
            "avant de renommer le projet."
        ):
            return

        dialog = RenameProjectDialog(self.workspace_manager.current_workspace.root, self)

        if dialog.exec() != QDialog.Accepted:
            return

        # Mission 084: unlike new_project()/open_project()/closeEvent(),
        # rename_project() deliberately does NOT run the 5 prompt/
        # metadata dirty-state guards — Mission 083 established that a
        # rename never destroys any of those drafts (none of their
        # reset_for_context_change() are subscribed to WORKSPACE_RENAMED),
        # so there is nothing for them to protect here. Only the pending
        # generation result is actually destroyed by a rename (via
        # reset_for_workspace_change(), which IS subscribed to
        # WORKSPACE_RENAMED — see its own docstring) — this is therefore
        # the sole guard added to this method, run before any physical
        # mutation of the Workspace.
        if not self.inference_page.confirm_pending_result_change():
            return

        try:
            self.workspace_manager.rename(dialog.new_name)
        except WorkspaceRenamePermissionError:
            # Mission 027 smoke test: confirmed via Process Explorer to
            # be explorer.exe holding handles on the project's
            # subfolders (a Windows Explorer window browsing one of
            # them), never an application-side resource leak — see
            # MISSION_027.md section 20. Deliberately caught before the
            # generic WorkspaceManagerError below, and only for this
            # specific, identifiable case — any other rename failure
            # still falls through to the generic message untouched.
            QMessageBox.warning(
                self,
                "Renommage impossible",
                "Impossible de renommer le projet : le dossier du projet "
                "ou l'un de ses sous-dossiers (images, outputs, datasets, "
                "models...) semble actuellement utilisé par une autre "
                "application — le plus souvent une fenêtre de "
                "l'Explorateur Windows ouverte dans un sous-dossier du "
                "projet.\n\nFermez les fenêtres de l'Explorateur Windows "
                "ouvertes dans ce dossier ou ses sous-dossiers, puis "
                "réessayez."
            )
            return
        except WorkspaceManagerError as exc:
            QMessageBox.critical(self, "Erreur", str(exc))
            return

        self.statusBar().showMessage(
            f"Projet renommé : {self.workspace_manager.current_workspace.name}"
        )

    # ======================================================
    # Prompts -> Inference (Mission 033)
    # ======================================================

    def _on_prompts_send_to_inference(self, text):
        """
        text is exactly what PromptsPage.text_edit currently shows —
        never re-read from the persisted Prompt. Collision rule: an
        empty/whitespace-only or identical (exact string comparison,
        no normalization) InferencePage.prompt transfers immediately;
        a genuinely different one requires explicit confirmation.
        Cancelling leaves both pages and the Domain Prompt untouched —
        no PromptManager.update_text()/save() is ever called from this
        flow (see MISSION_033.md section 9).
        """
        current = self.inference_page.prompt_text()

        if current.strip() and current != text:
            box = QMessageBox(self)
            box.setWindowTitle("Remplacer le prompt ?")
            box.setText(
                "Un prompt différent est déjà présent dans Inference. "
                "Voulez-vous le remplacer ?"
            )
            replace_button = box.addButton("Remplacer", QMessageBox.AcceptRole)
            cancel_button = box.addButton("Annuler", QMessageBox.RejectRole)
            box.setDefaultButton(cancel_button)
            box.exec()

            if box.clickedButton() is not replace_button:
                return

        self.inference_page.set_prompt_text(text)
        self.sidebar.select_page("inference")

    def closeEvent(self, event):
        # Mission 085: must run before any of the 6 guards below and
        # before InferencePage.shutdown() — a genuinely active
        # generation has produced no result yet, so none of those
        # guards have anything to protect, and shutdown()'s blocking
        # wait()-then-cleanup sequence is exactly what silently
        # destroyed the freshly generated file once the deferred
        # cross-thread signal landed after that cleanup (see
        # MISSION_085.md). No dirty guard runs and no draft is ever
        # saved before the user learns closing is impossible.
        if not self.inference_page.confirm_no_active_generation(
            "Une génération est en cours. Attendez qu'elle soit terminée "
            "avant de fermer l'application."
        ):
            event.ignore()
            return

        # Mission 079: same dirty-draft guard as new_project()/open_project()
        # (Missions 069/078), same order, applied to closing the whole
        # application — otherwise a dirty draft on any of these 4 Pages
        # would be silently discarded by the OS-level window close, with
        # no Save/Discard/Cancel opportunity. Must run before any
        # irreversible shutdown step below.
        if not self.prompts_page.confirm_context_change():
            event.ignore()
            return

        if not self.characters_page.confirm_context_change():
            event.ignore()
            return

        if not self.lora_page.confirm_context_change():
            event.ignore()
            return

        # Mission 090: a separate guard, deliberately not added to
        # new_project()/open_project()/rename_project() — the
        # central-library tab never reacts to any Workspace event
        # (Mission 089 mandate), so none of those genuinely threaten an
        # unsaved edit draft there; only closing the whole application
        # does.
        if not self.lora_page.confirm_library_context_change():
            event.ignore()
            return

        if not self.settings_page.confirm_context_change():
            event.ignore()
            return

        # Mission 083: same append as new_project()/open_project() —
        # must run before inference_page.shutdown() below, which
        # unconditionally discards any pending generation result and is
        # otherwise unrelated to this guard.
        if not self.inference_page.confirm_context_change():
            event.ignore()
            return

        # Mission 084: same 6th guard as new_project()/open_project() —
        # must also run before inference_page.shutdown() below, whose
        # own unconditional pending-result destruction (Mission 014) is
        # this guard's exact target.
        if not self.inference_page.confirm_pending_result_change():
            event.ignore()
            return

        # Mission 013 — minimal handling: never leave a generation
        # thread dangling when the application closes. No cancellation,
        # just a deterministic wait for the in-progress worker to stop.
        self.inference_page.shutdown()
        super().closeEvent(event)