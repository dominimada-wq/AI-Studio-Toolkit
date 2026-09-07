"""
Coverage for src/engines/onetrainer_launch.py — Mission 100's OneTrainer
launch-configuration resolver. Pure filesystem existence checks against
a disposable temp directory standing in for an OneTrainer installation
— no dependency on a real OneTrainer actually being installed, no
network, no GPU.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from src.engines.onetrainer_launch import (
    OneTrainerLaunchConfig,
    OneTrainerLaunchError,
    resolve_onetrainer_launch,
)


class ResolveOnetrainerLaunchTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.root = Path(self.tmp_dir) / "Onetrainer"

    def _make_fake_installation(self):
        (self.root / "venv" / "Scripts").mkdir(parents=True, exist_ok=True)
        (self.root / "venv" / "Scripts" / "python.exe").write_bytes(b"")
        (self.root / "scripts").mkdir(parents=True, exist_ok=True)
        (self.root / "scripts" / "train_remote.py").write_bytes(b"")

    def test_raises_when_path_is_blank(self):
        with self.assertRaises(OneTrainerLaunchError):
            resolve_onetrainer_launch("")
        with self.assertRaises(OneTrainerLaunchError):
            resolve_onetrainer_launch("   ")

    def test_raises_when_venv_python_missing(self):
        (self.root / "scripts").mkdir(parents=True, exist_ok=True)
        (self.root / "scripts" / "train_remote.py").write_bytes(b"")

        with self.assertRaises(OneTrainerLaunchError) as ctx:
            resolve_onetrainer_launch(str(self.root))
        self.assertIn("Python environment", str(ctx.exception))

    def test_raises_when_train_remote_script_missing(self):
        (self.root / "venv" / "Scripts").mkdir(parents=True, exist_ok=True)
        (self.root / "venv" / "Scripts" / "python.exe").write_bytes(b"")

        with self.assertRaises(OneTrainerLaunchError) as ctx:
            resolve_onetrainer_launch(str(self.root))
        self.assertIn("train_remote.py", str(ctx.exception))

    def test_resolves_correct_config_for_a_complete_installation(self):
        self._make_fake_installation()

        config = resolve_onetrainer_launch(str(self.root))

        self.assertIsInstance(config, OneTrainerLaunchConfig)
        self.assertEqual(
            Path(config.python_executable), self.root / "venv" / "Scripts" / "python.exe"
        )
        self.assertEqual(Path(config.script_path), self.root / "scripts" / "train_remote.py")
        self.assertEqual(Path(config.working_directory), self.root)

    def test_never_touches_python_path_setting(self):
        # Mission 100: resolve_onetrainer_launch() takes onetrainer_path
        # alone — python_path is deliberately never consulted (see the
        # module's own docstring for why).
        import inspect

        source = inspect.getsource(resolve_onetrainer_launch)
        self.assertNotIn("python_path", source)


if __name__ == "__main__":
    unittest.main()
