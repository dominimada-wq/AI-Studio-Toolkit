from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QStyle


def load_thumbnail_icon(file_path, size, style):
    pixmap = QPixmap(file_path)
    if pixmap.isNull():
        return style.standardIcon(QStyle.SP_MessageBoxWarning)

    scaled = pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return QIcon(scaled)
