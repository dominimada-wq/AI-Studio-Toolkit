from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QFileDialog,
    QMessageBox,
)


class ImagesPage(QWidget):

    def __init__(self):
        super().__init__()

        self.image_paths = []

        layout = QVBoxLayout(self)

        title = QLabel("Images")
        title.setStyleSheet("""
            QLabel{
                font-size:24px;
                font-weight:bold;
            }
        """)

        layout.addWidget(title)

        self.import_button = QPushButton("Importer des images")
        self.import_button.clicked.connect(self.import_images)

        layout.addWidget(self.import_button)

        self.list_widget = QListWidget()

        layout.addWidget(self.list_widget)

    def import_images(self):

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Sélectionner des images",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )

        if not files:
            return

        self.image_paths.extend(files)

        self.list_widget.clear()

        for image in self.image_paths:
            self.list_widget.addItem(image)

        QMessageBox.information(
            self,
            "Import terminé",
            f"{len(files)} image(s) importée(s)."
        )