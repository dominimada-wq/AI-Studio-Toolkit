"""
Coverage for src/engines/onetrainer_cancel_helper.py — Mission 100's
single-responsibility Cancel helper, run as its own OS process. Tested
against a disposable, minimal fake `modules.util.commands.TrainCommands`
module tree written to a temp directory (same shape/method names as
OneTrainer's real class) rather than a real OneTrainer installation —
this keeps the test portable (it must run identically on any machine,
without J:\\Programmes\\Onetrainer present), while still exercising the
helper's real logic end-to-end: argument handling, dynamic sys.path
import, TrainCommands.stop(), and the pickle write.

DELIBERATELY EXCLUDED FROM THE MAIN CANONICAL SUITE (never a forgotten
test): named without a "test_" prefix so it is never matched by the
project's canonical `discover -s tests -p "test_*.py"` — this file
spawns a real child OS process via subprocess.run(), which was proven
(Mission 100 execution report) to reproducibly trigger a native
`STATUS_HEAP_CORRUPTION` (0xC0000374) when run as part of the ~2000-test
monoprocess suite, after the cumulative Qt widget weight already
characterized as harness debt in Mission 097/099 — never in isolation,
and never in the real application. Run it on its own, in a fresh
Python process, as its own mandatory validation step for any mission
touching src/engines/onetrainer_cancel_helper.py:

    ./.venv/Scripts/python.exe -m unittest \\
        tests.integration.isolated_test_onetrainer_cancel_helper -v

A one-time manual smoke test against the real installed OneTrainer
(confirming the real modules.util.commands.TrainCommands unpickles
correctly) is reported separately in the mission's execution report —
same precedent as Mission 097's own real-installation smoke tests,
deliberately kept out of the always-green automated suite.
"""

import pickle
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HELPER_SCRIPT = str(
    Path(__file__).resolve().parents[2] / "src" / "engines" / "onetrainer_cancel_helper.py"
)

_FAKE_TRAIN_COMMANDS_SOURCE = '''
class TrainCommands:
    def __init__(self):
        self.__stop_command = False

    def stop(self):
        self.__stop_command = True

    def get_stop_command(self):
        return self.__stop_command
'''


class OnetrainerCancelHelperTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.fake_onetrainer_root = Path(self.tmp_dir) / "FakeOnetrainer"

        for package in ("modules", "modules/util", "modules/util/commands"):
            package_dir = self.fake_onetrainer_root / package
            package_dir.mkdir(parents=True, exist_ok=True)
            (package_dir / "__init__.py").write_text("", encoding="utf-8")

        (self.fake_onetrainer_root / "modules" / "util" / "commands" / "TrainCommands.py").write_text(
            _FAKE_TRAIN_COMMANDS_SOURCE, encoding="utf-8"
        )

        self.command_pipe_path = Path(self.tmp_dir) / "command.pipe"
        self.command_pipe_path.touch()

    def _run_helper(self, args):
        return subprocess.run(
            [sys.executable, _HELPER_SCRIPT] + args,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_writes_a_real_stop_command_into_the_pipe(self):
        result = self._run_helper([str(self.fake_onetrainer_root), str(self.command_pipe_path)])

        self.assertEqual(result.returncode, 0, msg=result.stderr)

        sys.path.insert(0, str(self.fake_onetrainer_root))
        try:
            from modules.util.commands.TrainCommands import TrainCommands  # noqa: F401
            with open(self.command_pipe_path, "rb") as f:
                commands = pickle.load(f)
        finally:
            sys.path.remove(str(self.fake_onetrainer_root))
            sys.modules.pop("modules.util.commands.TrainCommands", None)
            sys.modules.pop("modules.util.commands", None)
            sys.modules.pop("modules.util", None)
            sys.modules.pop("modules", None)

        self.assertTrue(commands.get_stop_command())

    def test_wrong_argument_count_fails_cleanly(self):
        result = self._run_helper([str(self.fake_onetrainer_root)])
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr)

    def test_unresolvable_onetrainer_path_fails_cleanly_never_crashes(self):
        result = self._run_helper([str(Path(self.tmp_dir) / "does-not-exist"), str(self.command_pipe_path)])
        self.assertEqual(result.returncode, 1)
        self.assertIn("Could not import", result.stderr)

    def test_unwritable_command_pipe_fails_cleanly(self):
        unwritable_path = Path(self.tmp_dir) / "no-such-directory" / "command.pipe"
        result = self._run_helper([str(self.fake_onetrainer_root), str(unwritable_path)])
        self.assertEqual(result.returncode, 1)
        self.assertIn("Could not write", result.stderr)


if __name__ == "__main__":
    unittest.main()
