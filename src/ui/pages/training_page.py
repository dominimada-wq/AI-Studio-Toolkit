from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class TrainingPage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title = QLabel("Training")
        title.setStyleSheet("font-size:24px;font-weight:bold;")

        layout.addWidget(title)

        self.start_button = QPushButton("Lancer l'entraînement")

        layout.addWidget(self.start_button)

        self.console = QTextEdit()
        self.console.setReadOnly(True)

        layout.addWidget(self.console)