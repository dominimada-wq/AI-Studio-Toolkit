from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QStyle


def load_thumbnail_icon(file_path, size, style):
    pixmap = QPixmap(file_path)
    if pixmap.isNull():
        return style.standardIcon(QStyle.SP_MessageBoxWarning)

    scaled = pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return QIcon(scaled)


def file_mtime_sort_key(file_path):
    """
    Mission 049: sort key for "most recent file first" (descending
    mtime). Returns the file's last-modification time, or -inf if
    stat() fails (missing file, permission error, ...) — the smallest
    possible value, so a missing file always sorts last under a
    reverse=True sort, never accidentally first.
    """
    try:
        return Path(file_path).stat().st_mtime
    except OSError:
        return float("-inf")
