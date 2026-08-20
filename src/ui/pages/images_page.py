from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QDialog,
    QFileDialog,
    QMessageBox,
)

from src.ui.dialogs.image_preview_dialog import ImagePreviewDialog
from src.ui.dialogs.import_collision_dialog import ImportCollisionDialog
from src.ui.thumbnails import load_thumbnail_icon

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

        # Mission 028 (second smoke test): a colliding name is never
        # auto-suffixed without asking anymore — preview first, and if
        # anything collides, resolve every collision in a single
        # dialog (never one QMessageBox per file) before the real
        # import runs. WorkspaceStorage.copy_into_workspace()'s own
        # silent auto-suffix remains the underlying safety net for any
        # caller that skips this dialog (tests, programmatic use) —
        # only this UI-driven flow now always asks first.
        collisions = self.workspace_manager.preview_collisions(files)
        ui_skipped = []
        renames = {}

        if collisions:
            dialog = ImportCollisionDialog(collisions, parent=self)
            if dialog.exec() != QDialog.Accepted:
                return

            for source, choice in dialog.decisions().items():
                if choice is None:
                    ui_skipped.append(source)
                else:
                    renames[source] = choice

            files = [f for f in files if f not in ui_skipped]

        result = self.workspace_manager.add_images(files, renames=renames)
        self._show_import_result(result, ui_skipped=ui_skipped)

    def _show_import_result(self, result, ui_skipped=None):

        all_skipped = list(ui_skipped or []) + list(result.skipped)

        if result.failed:
            failed_names = ", ".join(Path(p).name for p in result.failed)
            message = f"{result.added} image(s) importée(s)."
            if all_skipped:
                message += f" {len(all_skipped)} ignorée(s) ou déjà présente(s)."
            message += f" {len(result.failed)} échec(s) : {failed_names}."
            QMessageBox.warning(self, "Import partiellement réussi", message)
        elif result.added == 0:
            QMessageBox.information(
                self,
                "Import terminé",
                "Aucune nouvelle image importée (ignorée(s) ou déjà présente(s))."
            )
        elif all_skipped:
            QMessageBox.information(
                self,
                "Import terminé",
                f"{result.added} image(s) importée(s), "
                f"{len(all_skipped)} ignorée(s) ou déjà présente(s)."
            )
        else:
            QMessageBox.information(
                self,
                "Import terminé",
                f"{result.added} image(s) importée(s)."
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
        return load_thumbnail_icon(file_path, THUMBNAIL_SIZE, self.style())

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
