from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class InferencePage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title = QLabel("Inference")
        title.setStyleSheet("font-size:24px;font-weight:bold;")

        layout.addWidget(title)

        self.generate_button = QPushButton("Générer")

        layout.addWidget(self.generate_button)

        self.prompt = QTextEdit()

        self.prompt.setPlaceholderText("Prompt...")

        layout.addWidget(self.prompt)