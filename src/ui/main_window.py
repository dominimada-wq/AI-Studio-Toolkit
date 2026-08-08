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
from src.infrastructure.storage.workspace_storage import WorkspaceStorageError
from src.managers.workspace_manager import (
    WorkspaceManager,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_SAVED,
    WORKSPACE_CLOSED,
)

from src.ui.sidebar import Sidebar
from src.ui.toolbar import MainToolBar
from src.ui.statusbar import MainStatusBar
from src.ui.menubar import MainMenuBar

from src.ui.pages.dashboard_page import DashboardPage
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

        # DashboardPage.update_project() expects a plain dict (it reads
        # fields via .get()), so it works with workspace.to_dict() —
        # already what WorkspaceManager publishes — without depending on
        # the Workspace domain class. Keeps Presentation independent of
        # Domain, per the Blueprint's layering rules.
        for event_name in (
            WORKSPACE_CREATED,
            WORKSPACE_OPENED,
            WORKSPACE_SAVED,
            WORKSPACE_CLOSED,
        ):
            self.event_bus.subscribe(event_name, self.dashboard_page.update_project)

        self.images_page = ImagesPage()
        self.datasets_page = DatasetsPage()
        self.models_page = ModelsPage()
        self.lora_page = LoRAPage()
        self.training_page = TrainingPage()
        self.inference_page = InferencePage()
        self.settings_page = SettingsPage()

        self.stack.addWidget(self.dashboard_page)
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
        except WorkspaceStorageError as exc:
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
        except WorkspaceStorageError as exc:
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
        except WorkspaceStorageError as exc:
            QMessageBox.critical(self, "Erreur", str(exc))
            return

        self.statusBar().showMessage("Projet sauvegardé")