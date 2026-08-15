from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QMessageBox,
    QStyle,
)

from src.ui.dialogs.image_preview_dialog import ImagePreviewDialog

THUMBNAIL_SIZE = QSize(128, 128)
GRID_SIZE = QSize(150, 170)


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
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.setMovement(QListWidget.Static)
        self.list_widget.setWordWrap(True)
        self.list_widget.setIconSize(THUMBNAIL_SIZE)
        self.list_widget.setGridSize(GRID_SIZE)
        self.list_widget.itemSelectionChanged.connect(self._update_enlarge_button_state)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)

        layout.addWidget(self.list_widget)

        self.enlarge_button = QPushButton("Voir en grand")
        self.enlarge_button.setEnabled(False)
        self.enlarge_button.clicked.connect(self._on_enlarge_clicked)

        layout.addWidget(self.enlarge_button)

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

        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        if workspace is not None:
            for image in workspace.get("images", []):
                self.list_widget.addItem(self._build_item(image["file_path"]))

        self.list_widget.blockSignals(False)
        self._update_enlarge_button_state()

    def _build_item(self, file_path):
        item = QListWidgetItem()
        item.setIcon(self._load_thumbnail_icon(file_path))
        item.setText(Path(file_path).name)
        item.setToolTip(file_path)
        item.setData(Qt.UserRole, file_path)
        return item

    def _load_thumbnail_icon(self, file_path):
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            return self.style().standardIcon(QStyle.SP_MessageBoxWarning)

        scaled = pixmap.scaled(
            THUMBNAIL_SIZE,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        return QIcon(scaled)

    def _update_enlarge_button_state(self):
        self.enlarge_button.setEnabled(self.list_widget.currentItem() is not None)

    def _on_item_double_clicked(self, item):
        self._open_preview(item.data(Qt.UserRole))

    def _on_enlarge_clicked(self):
        item = self.list_widget.currentItem()
        if item is None:
            return
        self._open_preview(item.data(Qt.UserRole))

    def _open_preview(self, file_path):
        ImagePreviewDialog(file_path, parent=self).exec()
