from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QHBoxLayout,
)


class ModelsPage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title = QLabel("Models")
        title.setStyleSheet("font-size:24px;font-weight:bold;")

        layout.addWidget(title)

        buttons = QHBoxLayout()

        self.scan_button = QPushButton("Scanner les modèles")
        self.refresh_button = QPushButton("Actualiser")

        buttons.addWidget(self.scan_button)
        buttons.addWidget(self.refresh_button)

        layout.addLayout(buttons)

        self.model_list = QListWidget()

        layout.addWidget(self.model_list)

        self.model_list.addItems([
            "Flux",
            "SDXL",
            "Pony",
            "Wan",
            "Hunyuan"
        ])