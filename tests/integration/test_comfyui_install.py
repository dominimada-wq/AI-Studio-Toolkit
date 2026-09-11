"""
Coverage for src/engines/comfyui_install.py — Mission 113's static
ComfyUI Local/Desktop installation validator. Pure filesystem existence
checks against a disposable temp directory standing in for a ComfyUI
Local/Desktop installation — no dependency on a real ComfyUI actually
being installed, no network, no process launched.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from src.engines.comfyui_install import (
    ComfyUIInstallConfig,
    ComfyUIInstallError,
    resolve_comfyui_install,
)


class ResolveComfyUIInstallTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.root = Path(self.tmp_dir) / "ComfyUI"

    def _make_fake_installation(self):
        (self.root / "resources" / "ComfyUI").mkdir(parents=True, exist_ok=True)
        (self.root / "resources" / "ComfyUI" / "main.py").write_bytes(b"")

    def test_raises_when_path_is_blank(self):
        with self.assertRaises(ComfyUIInstallError):
            resolve_comfyui_install("")
        with self.assertRaises(ComfyUIInstallError):
            resolve_comfyui_install("   ")

    def test_raises_when_path_does_not_exist(self):
        missing_root = Path(self.tmp_dir) / "does-not-exist"

        with self.assertRaises(ComfyUIInstallError) as ctx:
            resolve_comfyui_install(str(missing_root))
        self.assertIn("entry point", str(ctx.exception))

    def test_raises_when_entry_point_missing(self):
        self.root.mkdir(parents=True, exist_ok=True)

        with self.assertRaises(ComfyUIInstallError) as ctx:
            resolve_comfyui_install(str(self.root))
        self.assertIn("main.py", str(ctx.exception))

    def test_resolves_correct_config_for_a_complete_installation(self):
        self._make_fake_installation()

        config = resolve_comfyui_install(str(self.root))

        self.assertIsInstance(config, ComfyUIInstallConfig)
        self.assertEqual(
            Path(config.entry_point),
            self.root / "resources" / "ComfyUI" / "main.py",
        )
        self.assertEqual(Path(config.install_root), self.root)


if __name__ == "__main__":
    unittest.main()
