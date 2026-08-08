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

    def __init__(self, workspace_manager):
        super().__init__()

        self.workspace_manager = workspace_manager

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

        if not self.workspace_manager.opened:
            QMessageBox.warning(
                self,
                "Aucun projet ouvert",
                "Ouvrez ou créez un projet avant d'importer des images."
            )
            return

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Sélectionner des images",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )

        if not files:
            return

        added = self.workspace_manager.add_images(files)
        duplicates = len(files) - added

        if added == 0:
            QMessageBox.information(
                self,
                "Import terminé",
                "Aucune nouvelle image importée (déjà présentes)."
            )
        elif duplicates > 0:
            QMessageBox.information(
                self,
                "Import terminé",
                f"{added} image(s) importée(s), {duplicates} déjà présente(s) ignorée(s)."
            )
        else:
            QMessageBox.information(
                self,
                "Import terminé",
                f"{added} image(s) importée(s)."
            )

    def update_images(self, workspace):

        self.list_widget.clear()

        if workspace is None:
            return

        for image in workspace.get("images", []):
            self.list_widget.addItem(image)
