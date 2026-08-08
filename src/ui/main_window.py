from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QSplitter,
    QStackedWidget,
    QFileDialog,
)

from src.project.project_io import ProjectIO

from src.ui.sidebar import Sidebar
from src.ui.toolbar import MainToolBar
from src.ui.statusbar import MainStatusBar
from src.ui.menubar import MainMenuBar

from src.pages.dashboard_page import DashboardPage
from src.pages.images_page import ImagesPage
from src.pages.datasets_page import DatasetsPage
from src.pages.models_page import ModelsPage
from src.pages.lora_page import LoRAPage
from src.pages.training_page import TrainingPage
from src.pages.inference_page import InferencePage
from src.pages.settings_page import SettingsPage


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        # Projet courant
        self.current_project = None
        self.project_folder = None

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

        self.current_project = ProjectIO.create_project(folder)
        self.project_folder = folder

        self.statusBar().showMessage("Projet créé")

    def open_project(self):

        folder = QFileDialog.getExistingDirectory(
            self,
            "Ouvrir un projet"
        )

        if not folder:
            return

        self.current_project = ProjectIO.load_project(folder)
        self.project_folder = folder

        if self.current_project is None:
            self.statusBar().showMessage("Projet invalide")
            return

        self.statusBar().showMessage(
            f"Projet ouvert : {self.current_project['name']}"
        )

    def save_project(self):

        if self.current_project is None:
            return

        ProjectIO.save_project(
            self.project_folder,
            self.current_project
        )

        self.statusBar().showMessage("Projet sauvegardé")