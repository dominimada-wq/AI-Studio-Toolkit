"""
Mission 100: TrainingJobRunner — real QProcess lifecycle against the
deterministic fake OneTrainer process (_fake_onetrainer_process.py),
never the real OneTrainer runtime, never a GPU. Success/failure/crash
are driven by real subprocess exit codes/status; the cooperative-Cancel
end-to-end path uses a real onetrainer_cancel_helper.py run against a
disposable fake `modules.util.commands.TrainCommands` (same fixture
technique as test_onetrainer_cancel_helper.py) — never the real
OneTrainer installation, so the suite stays portable.

The terminate()/kill() escalation logic itself (section 8) is verified
separately via direct method calls with the internal QProcess spied on
— real OS-level process-termination timing on Windows is not something
this suite should depend on for determinism.
"""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication

from src.engines.onetrainer_launch import OneTrainerLaunchConfig, OneTrainerLaunchError
from src.managers.training_manager import TrainingJobPaths
from src.ui import training_job_runner as runner_module
from src.ui.training_job_runner import TrainingJobRunner

_app = QApplication.instance() or QApplication([])

_FAKE_PROCESS_SCRIPT = str(Path(__file__).resolve().parent / "_fake_onetrainer_process.py")

_FAKE_TRAIN_COMMANDS_SOURCE = '''
class TrainCommands:
    def __init__(self):
        self.__stop_command = False

    def stop(self):
        self.__stop_command = True

    def get_stop_command(self):
        return self.__stop_command
'''


def _pump_until(condition, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if condition():
            return True
        time.sleep(0.01)
    return condition()


class TrainingJobRunnerTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        job_folder = Path(self.tmp_dir) / "job"
        job_folder.mkdir(parents=True, exist_ok=True)
        output_path = job_folder / "output" / "lora.safetensors"
        (job_folder / "output").mkdir(parents=True, exist_ok=True)

        self.config_path = job_folder / "onetrainer_config.json"
        self.config_path.write_text(
            json.dumps({"output_model_destination": str(output_path)}), encoding="utf-8"
        )
        self.command_path = job_folder / "command.pipe"
        self.command_path.touch()

        self.job_paths = TrainingJobPaths(
            job_id="job-1",
            config_snapshot_path=str(self.config_path),
            expected_output_path=str(output_path),
            command_pipe_path=str(self.command_path),
            workspace_dir=str(job_folder / "workspace"),
            cache_dir=str(job_folder / "cache"),
            debug_dir=str(job_folder / "debug"),
        )

        self._env_backup = dict(os.environ)
        self.addCleanup(self._restore_env)

        self._launch_config = OneTrainerLaunchConfig(
            python_executable=sys.executable,
            script_path=_FAKE_PROCESS_SCRIPT,
            working_directory=self.tmp_dir,
        )
        self._resolve_patch = patch.object(
            runner_module, "resolve_onetrainer_launch", return_value=self._launch_config
        )
        self._resolve_patch.start()
        self.addCleanup(self._resolve_patch.stop)

        self.runner = TrainingJobRunner(self.job_paths, "fake-onetrainer-path")

    def _restore_env(self):
        os.environ.clear()
        os.environ.update(self._env_backup)

    def _set_env(self, **kwargs):
        for key, value in kwargs.items():
            os.environ[key] = value

    def test_success_reports_succeeded_with_output_path(self):
        self._set_env(FAKE_EXIT_CODE="0", FAKE_WRITE_OUTPUT="1")
        results = []
        self.runner.finished.connect(lambda *args: results.append(args))

        self.runner.start()
        self.assertTrue(_pump_until(lambda: results))

        state, error_message, final_output_path = results[0]
        self.assertEqual(state, "succeeded")
        self.assertEqual(error_message, "")
        self.assertEqual(final_output_path, self.job_paths.expected_output_path)
        self.assertTrue(Path(final_output_path).is_file())

    def test_nonzero_exit_code_reports_failed(self):
        self._set_env(FAKE_EXIT_CODE="7", FAKE_WRITE_OUTPUT="0")
        results = []
        self.runner.finished.connect(lambda *args: results.append(args))

        self.runner.start()
        self.assertTrue(_pump_until(lambda: results))

        state, error_message, final_output_path = results[0]
        self.assertEqual(state, "failed")
        self.assertIn("7", error_message)
        self.assertEqual(final_output_path, "")

    def test_exit_zero_without_output_file_is_still_failed(self):
        # Mission 100 section 5.2: succeeded requires BOTH exit 0 AND a
        # verified output file — never one alone.
        self._set_env(FAKE_EXIT_CODE="0", FAKE_WRITE_OUTPUT="0")
        results = []
        self.runner.finished.connect(lambda *args: results.append(args))

        self.runner.start()
        self.assertTrue(_pump_until(lambda: results))

        state, error_message, final_output_path = results[0]
        self.assertEqual(state, "failed")
        self.assertIn("no output file", error_message)

    def test_crash_reports_failed_with_native_detail(self):
        self._set_env(FAKE_CRASH="1", FAKE_WRITE_OUTPUT="0")
        results = []
        self.runner.finished.connect(lambda *args: results.append(args))

        self.runner.start()
        self.assertTrue(_pump_until(lambda: results))

        state, error_message, final_output_path = results[0]
        self.assertEqual(state, "failed")
        self.assertIn("crash", error_message.lower())

    def test_failed_to_start_reports_failed_and_never_launches(self):
        self._resolve_patch.stop()
        broken_config = OneTrainerLaunchConfig(
            python_executable=str(Path(self.tmp_dir) / "does-not-exist.exe"),
            script_path=_FAKE_PROCESS_SCRIPT,
            working_directory=self.tmp_dir,
        )
        patch.object(runner_module, "resolve_onetrainer_launch", return_value=broken_config).start()
        self.addCleanup(patch.stopall)

        results = []
        self.runner.finished.connect(lambda *args: results.append(args))

        self.runner.start()
        self.assertTrue(_pump_until(lambda: results))

        state, error_message, final_output_path = results[0]
        self.assertEqual(state, "failed")
        self.assertIn("failed to start", error_message.lower())

    def test_missing_onetrainer_settings_reports_failed_before_launching(self):
        self._resolve_patch.stop()
        patch.object(
            runner_module,
            "resolve_onetrainer_launch",
            side_effect=OneTrainerLaunchError("OneTrainer is not configured — set it in Settings."),
        ).start()
        self.addCleanup(patch.stopall)

        results = []
        self.runner.finished.connect(lambda *args: results.append(args))

        self.runner.start()
        self.assertTrue(_pump_until(lambda: results))

        state, error_message, final_output_path = results[0]
        self.assertEqual(state, "failed")
        self.assertIn("not configured", error_message)

    def test_log_lines_are_captured_from_stdout_and_stderr(self):
        self._set_env(FAKE_EXIT_CODE="0", FAKE_WRITE_OUTPUT="1")
        lines = []
        self.runner.log_line.connect(lines.append)
        finished = []
        self.runner.finished.connect(lambda *args: finished.append(args))

        self.runner.start()
        self.assertTrue(_pump_until(lambda: finished))

        joined = "\n".join(lines)
        self.assertIn("fake OneTrainer process starting", joined)
        self.assertIn("simulated step 1/10", joined)

    def test_cooperative_cancel_end_to_end_reports_cancelled(self):
        # Real subprocess, real command.pipe, real onetrainer_cancel_
        # helper.py — against a disposable fake TrainCommands tree
        # (never the real OneTrainer installation).
        fake_onetrainer_root = Path(self.tmp_dir) / "FakeOnetrainerModules"
        for package in ("modules", "modules/util", "modules/util/commands"):
            package_dir = fake_onetrainer_root / package
            package_dir.mkdir(parents=True, exist_ok=True)
            (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (fake_onetrainer_root / "modules" / "util" / "commands" / "TrainCommands.py").write_text(
            _FAKE_TRAIN_COMMANDS_SOURCE, encoding="utf-8"
        )

        self._set_env(
            FAKE_RUN_SECONDS="30",
            FAKE_RESPECT_STOP="1",
            FAKE_MODULES_ROOT=str(fake_onetrainer_root),
            FAKE_WRITE_OUTPUT="0",
        )

        # onetrainer_path (used by the cancel helper's own sys.path
        # insertion) points at the fake modules tree; the interpreter
        # for BOTH the main process and the cancel helper is
        # sys.executable via the patched resolve_onetrainer_launch.
        self.runner = TrainingJobRunner(self.job_paths, str(fake_onetrainer_root))

        results = []
        self.runner.finished.connect(lambda *args: results.append(args))

        self.runner.start()
        self.assertTrue(_pump_until(lambda: self.runner._process.state() == QProcess.ProcessState.Running))

        self.runner.cancel()
        self.assertTrue(_pump_until(lambda: results, timeout=15.0))

        state, error_message, final_output_path = results[0]
        self.assertEqual(state, "cancelled")

    def test_cancel_is_idempotent(self):
        self._set_env(FAKE_RUN_SECONDS="5", FAKE_RESPECT_STOP="0", FAKE_WRITE_OUTPUT="0")
        self.runner.start()
        self.assertTrue(_pump_until(lambda: self.runner._process.state() == QProcess.ProcessState.Running))

        self.runner.cancel()
        first_helper = self.runner._cancel_helper_process
        self.runner.cancel()
        self.assertIs(self.runner._cancel_helper_process, first_helper)

        self.runner._process.kill()
        _pump_until(lambda: self.runner._process.state() == QProcess.ProcessState.NotRunning)


class TrainingJobRunnerCancelEscalationTest(unittest.TestCase):
    """
    Mission 100 section 8: the terminate() -> kill() escalation logic
    itself, verified by direct method calls with QProcess spied on —
    deliberately not dependent on real OS-level termination timing.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        job_folder = Path(self.tmp_dir) / "job"
        job_folder.mkdir(parents=True, exist_ok=True)

        self.job_paths = TrainingJobPaths(
            job_id="job-1",
            config_snapshot_path=str(job_folder / "onetrainer_config.json"),
            expected_output_path=str(job_folder / "output" / "lora.safetensors"),
            command_pipe_path=str(job_folder / "command.pipe"),
            workspace_dir=str(job_folder / "workspace"),
            cache_dir=str(job_folder / "cache"),
            debug_dir=str(job_folder / "debug"),
        )
        self.runner = TrainingJobRunner(self.job_paths, "fake-onetrainer-path")

    def test_cooperative_timeout_calls_terminate_and_arms_terminate_timer(self):
        with patch.object(self.runner._process, "state", return_value=QProcess.ProcessState.Running), \
                patch.object(self.runner._process, "terminate") as mock_terminate:
            self.runner._on_cooperative_timeout()

        mock_terminate.assert_called_once()
        self.assertTrue(self.runner._terminate_timer.isActive())

    def test_terminate_timeout_calls_kill(self):
        with patch.object(self.runner._process, "state", return_value=QProcess.ProcessState.Running), \
                patch.object(self.runner._process, "kill") as mock_kill:
            self.runner._on_terminate_timeout()

        mock_kill.assert_called_once()

    def test_timeouts_are_no_ops_once_process_already_finished(self):
        with patch.object(self.runner._process, "state", return_value=QProcess.ProcessState.NotRunning), \
                patch.object(self.runner._process, "terminate") as mock_terminate, \
                patch.object(self.runner._process, "kill") as mock_kill:
            self.runner._on_cooperative_timeout()
            self.runner._on_terminate_timeout()

        mock_terminate.assert_not_called()
        mock_kill.assert_not_called()


if __name__ == "__main__":
    unittest.main()
