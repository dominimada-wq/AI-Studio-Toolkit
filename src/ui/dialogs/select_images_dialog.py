from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from src.ui.thumbnails import load_thumbnail_icon

THUMBNAIL_SIZE = QSize(128, 128)
GRID_SIZE = QSize(150, 170)


class SelectImagesDialog(QDialog):
    """
    Mission 044: lets the user pick one or more images already present
    in the Workspace's own Images gallery (Workspace.images), to be
    added to the currently active Dataset — DatasetsPage.
    add_images_from_gallery() applies the selection via
    DatasetManager.add_images(), unchanged; this dialog never touches
    the filesystem or any Manager, purely a presentation-layer picker,
    same division of responsibility as ImportCollisionDialog.

    Mission 086: selection_mode/title/info_text are optional
    constructor parameters, defaulting to this exact Dataset contract
    byte-for-byte — InferencePage reuses this same dialog for a
    single-reference picker (selection_mode=QListWidget.SingleSelection,
    Inference-specific wording) without any second, near-identical
    dialog class.
    """

    def __init__(
        self,
        image_paths,
        parent=None,
        selection_mode=QListWidget.ExtendedSelection,
        title="Ajouter depuis Images",
        info_text="Sélectionnez une ou plusieurs images à ajouter au dataset actif :",
    ):
        super().__init__(parent)

        self.setWindowTitle(title)

        layout = QVBoxLayout(self)

        info = QLabel(info_text)
        info.setWordWrap(True)
        layout.addWidget(info)

        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.setMovement(QListWidget.Static)
        self.list_widget.setWordWrap(True)
        self.list_widget.setIconSize(THUMBNAIL_SIZE)
        self.list_widget.setGridSize(GRID_SIZE)
        self.list_widget.setSelectionMode(selection_mode)

        for file_path in image_paths:
            item = QListWidgetItem()
            item.setIcon(load_thumbnail_icon(file_path, THUMBNAIL_SIZE, self.style()))
            item.setText(Path(file_path).name)
            item.setToolTip(file_path)
            item.setData(Qt.UserRole, file_path)
            self.list_widget.addItem(item)

        layout.addWidget(self.list_widget)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def selected_paths(self) -> list:
        """
        Returns the full internal file path of every image the user
        selected. Only meaningful after exec() == QDialog.Accepted.
        """
        return [item.data(Qt.UserRole) for item in self.list_widget.selectedItems()]
