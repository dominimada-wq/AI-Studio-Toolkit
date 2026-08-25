from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QStyle

# Mission 064: 256 cached 128x128 RGBA icons is ~16 MiB (256 * 128*128*4
# bytes) worst case — a deliberate, proportionate bound for a desktop
# app's thumbnail gallery, not a general-purpose cache facility.
THUMBNAIL_CACHE_MAXSIZE = 256


def load_thumbnail_icon(file_path, size, style):
    # Mission 064: the file is stat()'d here, before any cache lookup,
    # so a missing/replaced/modified file can never be satisfied by a
    # stale cache entry — only the resulting signature reaches the
    # cacheable function below.
    try:
        stat = Path(file_path).stat()
    except OSError:
        return style.standardIcon(QStyle.SP_MessageBoxWarning)

    icon = _decode_and_scale(file_path, stat.st_mtime_ns, stat.st_size, size.width(), size.height())
    if icon is None:
        return style.standardIcon(QStyle.SP_MessageBoxWarning)
    return icon


@lru_cache(maxsize=THUMBNAIL_CACHE_MAXSIZE)
def _decode_and_scale(file_path, mtime_ns, file_size, width, height):
    # Mission 064: mtime_ns/file_size (read by the caller, above) make
    # the full-resolution decode below the cache miss path only — a
    # modified or replaced file at the same path never reuses this
    # entry, since its signature changes with it. The full-resolution
    # QPixmap is intentionally local: only the scaled-down result is
    # returned/cached.
    pixmap = QPixmap(file_path)
    if pixmap.isNull():
        return None

    scaled = pixmap.scaled(QSize(width, height), Qt.KeepAspectRatio, Qt.SmoothTransformation)
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
