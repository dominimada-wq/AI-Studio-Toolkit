"""
Coverage for src/engines/forge_launch.py — Mission 119's static Forge
local launch resolver. Pure filesystem/URL validation against
disposable temp directories standing in for a real installation — no
dependency on a real Forge actually being installed, no network, no
process launched.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from src.engines.forge_launch import (
    ForgeLaunchConfig,
    ForgeLaunchError,
    resolve_forge_launch,
)


class ResolveForgeLaunchTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.forge_path = Path(self.tmp_dir) / "Forge"

    def _make_install(self):
        self.forge_path.mkdir(parents=True, exist_ok=True)
        (self.forge_path / "run.bat").write_bytes(b"")

    def test_raises_when_forge_path_is_blank(self):
        with self.assertRaises(ForgeLaunchError):
            resolve_forge_launch("", "http://127.0.0.1:7860")
        with self.assertRaises(ForgeLaunchError):
            resolve_forge_launch("   ", "http://127.0.0.1:7860")

    def test_raises_when_run_bat_missing(self):
        with self.assertRaises(ForgeLaunchError) as ctx:
            resolve_forge_launch(str(self.forge_path), "http://127.0.0.1:7860")
        self.assertIn("run.bat", str(ctx.exception))

    def test_raises_when_host_is_not_local(self):
        self._make_install()
        with self.assertRaises(ForgeLaunchError) as ctx:
            resolve_forge_launch(str(self.forge_path), "http://192.168.1.50:7860")
        self.assertIn("192.168.1.50", str(ctx.exception))

    def test_raises_when_host_is_zero_zero_zero_zero(self):
        self._make_install()
        with self.assertRaises(ForgeLaunchError):
            resolve_forge_launch(str(self.forge_path), "http://0.0.0.0:7860")

    def test_raises_when_url_has_no_host(self):
        self._make_install()
        with self.assertRaises(ForgeLaunchError):
            resolve_forge_launch(str(self.forge_path), "not-a-url")

    def test_raises_when_port_missing(self):
        self._make_install()
        with self.assertRaises(ForgeLaunchError) as ctx:
            resolve_forge_launch(str(self.forge_path), "http://127.0.0.1")
        self.assertIn("port", str(ctx.exception))

    def test_localhost_normalized_to_127_0_0_1_for_listen(self):
        self._make_install()
        config = resolve_forge_launch(str(self.forge_path), "http://localhost:7860")
        self.assertEqual(config.listen_host, "127.0.0.1")
        self.assertEqual(config.port, 7860)

    def test_resolves_correct_config_for_a_complete_installation(self):
        self._make_install()

        config = resolve_forge_launch(str(self.forge_path), "http://127.0.0.1:7860")

        self.assertIsInstance(config, ForgeLaunchConfig)
        self.assertEqual(Path(config.working_directory), self.forge_path)
        self.assertEqual(Path(config.run_bat_path), self.forge_path / "run.bat")
        self.assertEqual(config.listen_host, "127.0.0.1")
        self.assertEqual(config.port, 7860)

    def test_extra_path_dirs_include_root_and_webui_subfolder(self):
        # Mission 119: confirmed necessary by a real empirical test on a
        # machine with NoDefaultCurrentDirectoryInExePath set -- run.bat
        # (root) and webui.bat/webui-user.bat (webui/) each need their
        # own directory reachable via PATH for their bare `call` lines
        # to resolve once cmd.exe's own current-directory search is
        # disabled.
        self._make_install()

        config = resolve_forge_launch(str(self.forge_path), "http://127.0.0.1:7860")

        self.assertEqual(
            config.extra_path_dirs,
            (str(self.forge_path), str(self.forge_path / "webui")),
        )

    def test_non_standard_port_is_accepted(self):
        self._make_install()
        config = resolve_forge_launch(str(self.forge_path), "http://127.0.0.1:17860")
        self.assertEqual(config.port, 17860)


if __name__ == "__main__":
    unittest.main()
