from PySide6.QtWidgets import QStatusBar


class MainStatusBar(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.showMessage("Ready")