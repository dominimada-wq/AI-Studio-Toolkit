from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout

DEFAULT_WIDTH = 1000
DEFAULT_HEIGHT = 750

UNAVAILABLE_MESSAGE = "Image indisponible : fichier introuvable ou illisible."


class ImagePreviewDialog(QDialog):
    """
    Mission 015: strictly passive image viewer, shared between
    ImagesPage and InferencePage's pending preview. Receives only a
    file_path — never a Domain object, a Manager, or a Page reference —
    so it has no channel to touch Workspace.images, persistence, or any
    generation state; visualizing an image can only ever read the file
    at file_path.
    """

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)

        self.setWindowTitle(Path(file_path).name or file_path)
        self.resize(DEFAULT_WIDTH, DEFAULT_HEIGHT)

        self._source_pixmap = QPixmap(file_path)
        if self._source_pixmap.isNull():
            self._source_pixmap = None

        layout = QVBoxLayout(self)

        self.fullscreen_button = QPushButton("Plein écran (F11)")
        self.fullscreen_button.clicked.connect(self._toggle_fullscreen)

        layout.addWidget(self.fullscreen_button)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        # Without an explicit minimum size, QLabel.minimumSizeHint()
        # locks onto whatever pixmap was last set on it via
        # setPixmap() — since _update_scaled_pixmap() keeps setting a
        # freshly scaled pixmap, the label's own floor would silently
        # ratchet up on every resize, making the dialog unable to
        # shrink back below its largest-ever rendered size. An
        # explicit (1, 1) floor decouples the layout's minimum size
        # from the currently displayed pixmap.
        self.image_label.setMinimumSize(1, 1)

        layout.addWidget(self.image_label)

        if self._source_pixmap is None:
            self.image_label.setText(UNAVAILABLE_MESSAGE)
        else:
            self._update_scaled_pixmap()

        self._fullscreen_shortcut = QShortcut(QKeySequence("F11"), self)
        self._fullscreen_shortcut.activated.connect(self._toggle_fullscreen)

    def showEvent(self, event):
        super().showEvent(event)
        if self._source_pixmap is not None:
            self._update_scaled_pixmap()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._source_pixmap is not None:
            self._update_scaled_pixmap()

    def _update_scaled_pixmap(self):
        # The original pixmap is loaded once in __init__ and kept in
        # memory — every resize/show rescales that single in-memory
        # copy, the file itself is never re-read.
        size = self.image_label.size()
        if size.width() <= 0 or size.height() <= 0:
            return

        scaled = self._source_pixmap.scaled(
            size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
