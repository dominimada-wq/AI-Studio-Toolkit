"""
Coverage for src/engines/forge_install.py — Mission 113's static Forge
local installation validator. Pure filesystem existence checks against
a disposable temp directory standing in for a Forge installation — no
dependency on a real Forge actually being installed, no network, no
process launched.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from src.engines.forge_install import (
    ForgeInstallConfig,
    ForgeInstallError,
    resolve_forge_install,
)


class ResolveForgeInstallTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.root = Path(self.tmp_dir) / "WebUI Forge"

    def _make_fake_installation(self):
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "run.bat").write_bytes(b"")

    def test_raises_when_path_is_blank(self):
        with self.assertRaises(ForgeInstallError):
            resolve_forge_install("")
        with self.assertRaises(ForgeInstallError):
            resolve_forge_install("   ")

    def test_raises_when_path_does_not_exist(self):
        missing_root = Path(self.tmp_dir) / "does-not-exist"

        with self.assertRaises(ForgeInstallError) as ctx:
            resolve_forge_install(str(missing_root))
        self.assertIn("entry point", str(ctx.exception))

    def test_raises_when_entry_point_missing(self):
        self.root.mkdir(parents=True, exist_ok=True)

        with self.assertRaises(ForgeInstallError) as ctx:
            resolve_forge_install(str(self.root))
        self.assertIn("run.bat", str(ctx.exception))

    def test_resolves_correct_config_for_a_complete_installation(self):
        self._make_fake_installation()

        config = resolve_forge_install(str(self.root))

        self.assertIsInstance(config, ForgeInstallConfig)
        self.assertEqual(Path(config.entry_point), self.root / "run.bat")
        self.assertEqual(Path(config.install_root), self.root)


if __name__ == "__main__":
    unittest.main()
