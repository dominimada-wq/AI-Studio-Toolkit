"""
Coverage for src/utils/lora_library_path.py — Mission 104's shared,
Qt-free guard against an empty/blank ApplicationSettings.
lora_library_path silently resolving relative to the process cwd. Pure
string/Path logic, no disk I/O performed by the helper itself, no Qt.
"""

import os
import tempfile
import unittest
from pathlib import Path

from src.utils.lora_library_path import LoRALibraryPathError, resolve_lora_library_root


class ResolveLoraLibraryRootTest(unittest.TestCase):

    def _listdir_before_after(self, directory):
        return set(os.listdir(directory))

    def test_empty_string_raises(self):
        with self.assertRaises(LoRALibraryPathError):
            resolve_lora_library_root("")

    def test_blank_string_raises(self):
        with self.assertRaises(LoRALibraryPathError):
            resolve_lora_library_root("   ")

    def test_valid_value_returns_matching_path(self):
        result = resolve_lora_library_root(r"C:\Somewhere\LoRA Library")
        self.assertEqual(result, Path(r"C:\Somewhere\LoRA Library"))

    def test_nonexistent_but_creatable_path_is_accepted(self):
        # Bootstrap contract: a syntactically valid path that does not
        # yet exist on disk must never be rejected by this helper --
        # WorkspaceStorage.copy_into_workspace()'s own
        # mkdir(parents=True) is what creates it later, unchanged.
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: os.path.exists(tmp_dir) and os.rmdir(tmp_dir))
        candidate = Path(tmp_dir) / "does_not_exist_yet" / "LoRA Library"
        self.assertFalse(candidate.exists())

        result = resolve_lora_library_root(str(candidate))

        self.assertEqual(result, candidate)
        self.assertFalse(candidate.exists())

    def test_helper_never_touches_disk(self):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(os.rmdir, tmp_dir)
        before = self._listdir_before_after(tmp_dir)

        resolve_lora_library_root(str(Path(tmp_dir) / "unwritten"))
        try:
            resolve_lora_library_root("")
        except LoRALibraryPathError:
            pass
        try:
            resolve_lora_library_root("   ")
        except LoRALibraryPathError:
            pass

        after = self._listdir_before_after(tmp_dir)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
