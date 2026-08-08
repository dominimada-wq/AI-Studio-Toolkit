from PySide6.QtWidgets import QToolBar
from PySide6.QtGui import QAction


class MainToolBar(QToolBar):
    def __init__(self, parent=None):
        super().__init__("Toolbar", parent)

        self.addAction(QAction("Open", self))
        self.addAction(QAction("Save", self))
        self.addSeparator()
        self.addAction(QAction("Run", self))