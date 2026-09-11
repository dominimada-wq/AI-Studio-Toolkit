"""
Coverage for src/engines/comfyui_launch.py — Mission 114's static
ComfyUI local launch resolver. Pure filesystem/URL validation against
disposable temp directories standing in for a real installation — no
dependency on a real ComfyUI actually being installed, no network, no
process launched.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from src.engines.comfyui_launch import (
    ComfyUILaunchConfig,
    ComfyUILaunchError,
    resolve_comfyui_launch,
)


class ResolveComfyUILaunchTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.comfyui_path = Path(self.tmp_dir) / "ComfyUIData"
        self.install_path = Path(self.tmp_dir) / "ComfyUIDesktop"

    def _make_python(self):
        venv_scripts = self.comfyui_path / ".venv" / "Scripts"
        venv_scripts.mkdir(parents=True, exist_ok=True)
        (venv_scripts / "python.exe").write_bytes(b"")

    def _make_install(self):
        entry_dir = self.install_path / "resources" / "ComfyUI"
        entry_dir.mkdir(parents=True, exist_ok=True)
        (entry_dir / "main.py").write_bytes(b"")

    def _make_complete_installation(self):
        self._make_python()
        self._make_install()

    def test_raises_when_comfyui_path_is_blank(self):
        with self.assertRaises(ComfyUILaunchError):
            resolve_comfyui_launch("", str(self.install_path), "http://127.0.0.1:8000")
        with self.assertRaises(ComfyUILaunchError):
            resolve_comfyui_launch("   ", str(self.install_path), "http://127.0.0.1:8000")

    def test_raises_when_python_executable_missing(self):
        with self.assertRaises(ComfyUILaunchError) as ctx:
            resolve_comfyui_launch(str(self.comfyui_path), str(self.install_path), "http://127.0.0.1:8000")
        self.assertIn("python.exe", str(ctx.exception))

    def test_raises_when_main_py_missing(self):
        self._make_python()
        with self.assertRaises(ComfyUILaunchError) as ctx:
            resolve_comfyui_launch(str(self.comfyui_path), str(self.install_path), "http://127.0.0.1:8000")
        self.assertIn("main.py", str(ctx.exception))

    def test_raises_when_host_is_not_local(self):
        self._make_complete_installation()
        with self.assertRaises(ComfyUILaunchError) as ctx:
            resolve_comfyui_launch(str(self.comfyui_path), str(self.install_path), "http://192.168.1.50:8000")
        self.assertIn("192.168.1.50", str(ctx.exception))

    def test_raises_when_host_is_zero_zero_zero_zero(self):
        self._make_complete_installation()
        with self.assertRaises(ComfyUILaunchError):
            resolve_comfyui_launch(str(self.comfyui_path), str(self.install_path), "http://0.0.0.0:8000")

    def test_raises_when_url_has_no_host(self):
        self._make_complete_installation()
        with self.assertRaises(ComfyUILaunchError):
            resolve_comfyui_launch(str(self.comfyui_path), str(self.install_path), "not-a-url")

    def test_raises_when_port_missing(self):
        self._make_complete_installation()
        with self.assertRaises(ComfyUILaunchError) as ctx:
            resolve_comfyui_launch(str(self.comfyui_path), str(self.install_path), "http://127.0.0.1")
        self.assertIn("port", str(ctx.exception))

    def test_localhost_normalized_to_127_0_0_1_for_listen(self):
        self._make_complete_installation()
        config = resolve_comfyui_launch(str(self.comfyui_path), str(self.install_path), "http://localhost:8188")
        self.assertEqual(config.listen_host, "127.0.0.1")
        self.assertEqual(config.port, 8188)

    def test_resolves_correct_config_for_a_complete_installation(self):
        self._make_complete_installation()

        config = resolve_comfyui_launch(
            str(self.comfyui_path), str(self.install_path), "http://127.0.0.1:8000"
        )

        self.assertIsInstance(config, ComfyUILaunchConfig)
        self.assertEqual(
            Path(config.python_executable), self.comfyui_path / ".venv" / "Scripts" / "python.exe"
        )
        self.assertEqual(
            Path(config.entry_point), self.install_path / "resources" / "ComfyUI" / "main.py"
        )
        self.assertEqual(Path(config.working_directory), self.comfyui_path)
        self.assertEqual(config.listen_host, "127.0.0.1")
        self.assertEqual(config.port, 8000)
        self.assertEqual(Path(config.user_directory), self.comfyui_path / "user")
        self.assertEqual(
            config.database_url,
            f"sqlite:///{(self.comfyui_path / 'user' / 'comfyui.db').as_posix()}",
        )

    def test_non_standard_port_is_accepted(self):
        self._make_complete_installation()
        config = resolve_comfyui_launch(str(self.comfyui_path), str(self.install_path), "http://127.0.0.1:12345")
        self.assertEqual(config.port, 12345)

    def test_user_directory_and_database_url_derived_from_comfyui_path(self):
        # Mission 114 (post-diagnostic correction): a real relaunch of
        # the minimal command without these two arguments produced a
        # real, observed "Failed to initialize database ... unable to
        # open database file" error on the reference machine -- these
        # are not redundant with --base-directory in practice, even
        # though comfy's own cli_args.py docstring suggests a derived
        # default should be equivalent.
        self._make_complete_installation()
        config = resolve_comfyui_launch(
            str(self.comfyui_path), str(self.install_path), "http://127.0.0.1:8000"
        )

        self.assertEqual(Path(config.user_directory), self.comfyui_path / "user")
        # sqlite:/// (three slashes) + forward-slash path -- the exact
        # format captured from ComfyUI Desktop's own real launch command
        # in %APPDATA%\ComfyUI\logs\main.log, never invented.
        self.assertTrue(config.database_url.startswith("sqlite:///"))
        self.assertNotIn("\\", config.database_url)
        self.assertTrue(config.database_url.endswith("user/comfyui.db"))


if __name__ == "__main__":
    unittest.main()
