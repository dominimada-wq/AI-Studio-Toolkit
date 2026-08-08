from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QListWidget,
    QVBoxLayout,
    QHBoxLayout,
)


class LoRAPage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title = QLabel("LoRA Manager")
        title.setStyleSheet("font-size:24px;font-weight:bold;")

        layout.addWidget(title)

        buttons = QHBoxLayout()

        self.new_button = QPushButton("Nouvelle LoRA")
        self.train_button = QPushButton("Entraîner")
        self.delete_button = QPushButton("Supprimer")

        buttons.addWidget(self.new_button)
        buttons.addWidget(self.train_button)
        buttons.addWidget(self.delete_button)

        layout.addLayout(buttons)

        self.lora_list = QListWidget()

        layout.addWidget(self.lora_list)