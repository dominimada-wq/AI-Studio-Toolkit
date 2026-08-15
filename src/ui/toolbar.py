from PySide6.QtWidgets import QToolBar
from PySide6.QtGui import QAction


class MainToolBar(QToolBar):
    def __init__(self, parent=None):
        super().__init__("Toolbar", parent)

        self.action_open = QAction("Open", self)
        self.action_save = QAction("Save", self)
        self.action_run = QAction("Run", self)

        self.addAction(self.action_open)
        self.addAction(self.action_save)
        self.addSeparator()
        self.addAction(self.action_run)

        self.action_run.setEnabled(False)
        self.action_run.setToolTip(
            "L'exécution depuis la barre d'outils n'est pas encore disponible."
        )
