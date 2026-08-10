from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

from src.ui.sidebar import Sidebar
from src.ui.toolbar import MainToolBar
from src.ui.statusbar import MainStatusBar
from src.ui.menubar import MainMenuBar

from src.ui.pages.dashboard_page import DashboardPage
from src.ui.pages.characters_page import CharactersPage
from src.ui.pages.images_page import ImagesPage
from src.ui.pages.datasets_page import DatasetsPage
from src.ui.pages.models_page import ModelsPage
from src.ui.pages.lora_page import LoRAPage
from src.ui.pages.training_page import TrainingPage
from src.ui.pages.inference_page import InferencePage
from src.ui.pages.settings_page import SettingsPage


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

        # CharactersPage/DatasetsPage also refresh on their own manager's
        # events — list_characters()/list_datasets() are always re-read
        # from the manager rather than trusting the per-item payload
        # (which carries only the one item that changed, not the full
        # list).
        for event_name in (CHARACTER_CREATED, CHARACTER_SELECTED, CHARACTER_DELETED):
            self.event_bus.subscribe(event_name, self.characters_page.update_characters)
            self.event_bus.subscribe(event_name, self.datasets_page.update_datasets)

        for event_name in (DATASET_CREATED, DATASET_SELECTED, DATASET_DELETED):
            self.event_bus.subscribe(event_name, self.datasets_page.update_datasets)

        self.models_page = ModelsPage()
        self.lora_page = LoRAPage()
        self.training_page = TrainingPage()
        self.inference_page = InferencePage()
        self.settings_page = SettingsPage()

        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.characters_page)
        self.stack.addWidget(self.images_page)
        self.stack.addWidget(self.datasets_page)
        self.stack.addWidget(self.models_page)
        self.stack.addWidget(self.lora_page)
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

        folder = QFileDialog.getExistingDirectory(
            self,
            "Créer un projet"
        )

        if not folder:
            return

        try:
            self.workspace_manager.create(folder)
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