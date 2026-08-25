"""
Mission 064: coverage for thumbnails.py's shared LRU cache — avoids
re-decoding an unchanged image's thumbnail on every WORKSPACE_SAVED-
driven list rebuild across ImagesPage/DatasetsPage/SelectImagesDialog.
load_thumbnail_icon()'s public signature is unchanged; these tests
exercise the private _decode_and_scale() directly (via cache_info()/
cache_clear()) since that is the only place the cache's hit/miss
behavior is observable — there is no other way to demonstrate the
mission's actual contract (avoiding redundant decodes) without it.

The cache is process-wide (module-level), so every test clears it
before and after running to stay independent of execution order.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from src.ui.thumbnails import THUMBNAIL_CACHE_MAXSIZE, _decode_and_scale, load_thumbnail_icon

_app = QApplication.instance() or QApplication([])
_style = QApplication.style()


def _make_png(path: str, width: int = 4, height: int = 4) -> None:
    pixmap = QPixmap(width, height)
    pixmap.fill()
    assert pixmap.save(path, "PNG")


class ThumbnailCacheTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        _decode_and_scale.cache_clear()
        self.addCleanup(_decode_and_scale.cache_clear)

    def test_first_call_is_a_cache_miss(self):
        path = str(Path(self.tmp_dir) / "a.png")
        _make_png(path)

        load_thumbnail_icon(path, QSize(128, 128), _style)

        info = _decode_and_scale.cache_info()
        self.assertEqual(info.misses, 1)
        self.assertEqual(info.hits, 0)

    def test_second_call_on_unchanged_file_is_a_cache_hit(self):
        path = str(Path(self.tmp_dir) / "a.png")
        _make_png(path)

        load_thumbnail_icon(path, QSize(128, 128), _style)
        load_thumbnail_icon(path, QSize(128, 128), _style)

        info = _decode_and_scale.cache_info()
        self.assertEqual(info.misses, 1)
        self.assertEqual(info.hits, 1)

    def test_modified_file_changes_signature_and_causes_a_new_miss(self):
        path = str(Path(self.tmp_dir) / "a.png")
        _make_png(path, width=4, height=4)
        load_thumbnail_icon(path, QSize(128, 128), _style)
        stat_before = Path(path).stat()

        # A real content rewrite (different dimensions -> different
        # file size, not just a different mtime), rather than a bare
        # os.utime() touch — avoids depending on the filesystem's
        # mtime resolution being fine enough to register a touch-only
        # change reliably.
        _make_png(path, width=8, height=8)
        stat_after = Path(path).stat()
        self.assertNotEqual(
            (stat_before.st_mtime_ns, stat_before.st_size),
            (stat_after.st_mtime_ns, stat_after.st_size),
        )

        load_thumbnail_icon(path, QSize(128, 128), _style)

        info = _decode_and_scale.cache_info()
        self.assertEqual(info.misses, 2)
        self.assertEqual(info.hits, 0)

    def test_replaced_file_at_the_same_path_is_not_served_the_old_thumbnail(self):
        path = str(Path(self.tmp_dir) / "a.png")
        _make_png(path, width=4, height=4)
        load_thumbnail_icon(path, QSize(128, 128), _style)

        _make_png(path, width=16, height=16)
        icon_after = load_thumbnail_icon(path, QSize(128, 128), _style)

        self.assertEqual(_decode_and_scale.cache_info().misses, 2)
        self.assertFalse(icon_after.isNull())

    def test_different_dimensions_for_the_same_file_are_distinct_cache_entries(self):
        path = str(Path(self.tmp_dir) / "a.png")
        _make_png(path)

        load_thumbnail_icon(path, QSize(128, 128), _style)
        load_thumbnail_icon(path, QSize(64, 64), _style)

        info = _decode_and_scale.cache_info()
        self.assertEqual(info.misses, 2)
        self.assertEqual(info.hits, 0)

    def test_missing_file_falls_back_without_ever_reaching_the_cache(self):
        path = str(Path(self.tmp_dir) / "missing.png")

        icon = load_thumbnail_icon(path, QSize(128, 128), _style)

        self.assertFalse(icon.isNull())
        info = _decode_and_scale.cache_info()
        self.assertEqual(info.misses, 0)
        self.assertEqual(info.hits, 0)

    def test_file_deleted_after_a_successful_load_falls_back_instead_of_reusing_the_cache(self):
        path = str(Path(self.tmp_dir) / "a.png")
        _make_png(path)
        load_thumbnail_icon(path, QSize(128, 128), _style)

        Path(path).unlink()
        icon = load_thumbnail_icon(path, QSize(128, 128), _style)

        # stat() fails before any cache lookup — the deleted file must
        # never resolve to the thumbnail decoded while it still existed.
        self.assertFalse(icon.isNull())
        self.assertEqual(_decode_and_scale.cache_info().misses, 1)

    def test_unreadable_image_content_falls_back_to_the_standard_icon(self):
        path = str(Path(self.tmp_dir) / "broken.png")
        Path(path).write_bytes(b"not a real png")

        icon = load_thumbnail_icon(path, QSize(128, 128), _style)

        self.assertFalse(icon.isNull())
        self.assertEqual(_decode_and_scale.cache_info().misses, 1)

    def test_cache_bound_matches_the_documented_constant(self):
        self.assertEqual(_decode_and_scale.cache_info().maxsize, THUMBNAIL_CACHE_MAXSIZE)
