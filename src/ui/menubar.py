from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenuBar


class MainMenuBar(QMenuBar):

    def __init__(self):
        super().__init__()

        # ===== Menu Fichier =====

        self.file_menu = self.addMenu("File")

        self.action_new_project = QAction("Nouveau projet", self)
        self.action_open_project = QAction("Ouvrir un projet", self)
        self.action_save_project = QAction("Sauvegarder", self)
        self.action_rename_project = QAction("Renommer le projet…", self)
        self.action_exit = QAction("Quitter", self)

        self.file_menu.addAction(self.action_new_project)
        self.file_menu.addAction(self.action_open_project)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.action_save_project)
        self.file_menu.addAction(self.action_rename_project)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.action_exit)

        # ===== Menu Edition =====

        self.edit_menu = self.addMenu("Edit")

        # ===== Menu Affichage =====

        self.view_menu = self.addMenu("View")

        # ===== Menu Outils =====

        self.tools_menu = self.addMenu("Tools")

        # ===== Menu Aide =====

        self.help_menu = self.addMenu("Help")

        # ===== Connexions =====

      