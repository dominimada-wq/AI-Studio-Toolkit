from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class BasePage(QWidget):
    def __init__(self, title):
        super().__init__()

        layout = QVBoxLayout(self)

        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel{
                font-size:22px;
                font-weight:bold;
            }
        """)

        layout.addWidget(title_label)
        layout.addStretch()