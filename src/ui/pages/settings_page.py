from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)


class SettingsPage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title = QLabel("Settings")
        title.setStyleSheet("font-size:24px;font-weight:bold;")

        layout.addWidget(title)

        form = QFormLayout()

        self.python_path = QLineEdit()
        self.comfyui_path = QLineEdit()
        self.onetrainer_path = QLineEdit()

        form.addRow("Python :", self.python_path)
        form.addRow("ComfyUI :", self.comfyui_path)
        form.addRow("OneTrainer :", self.onetrainer_path)

        layout.addLayout(form)

        layout.addStretch()