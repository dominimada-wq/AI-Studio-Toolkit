"""
Mission 114: ComfyUILifecycleManager — real QProcess lifecycle against
the deterministic fake ComfyUI process (_fake_comfyui_process.py), never
a real ComfyUI installation, never a GPU, never real network traffic
(ComfyUIEngine.check_connection() is mocked throughout — this suite
tests process/state orchestration, not HTTP behavior, which is already
covered by test_comfyui_engine.py's own ComfyUIEngineCheckConnectionTest).

Two families, mirroring test_training_job_runner.py's own split:
- ComfyUILifecycleManagerRealProcessTest: a real QProcess against the
  fake script, with short timing constants patched in so the suite
  stays fast regardless of real OS terminate()/kill() timing.
- ComfyUILifecycleManagerGuardTest: the stale-signal/identity/state
  guards and confirm_safe_to_close(), verified by direct method calls
  and fabricated internal state — same idiom already established by
  TrainingJobRunnerCancelEscalationTest.
"""
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication, QMessageBox

from src.engines.comfyui_engine import ComfyUIEngineError
from src.engines.comfyui_launch import ComfyUILaunchConfig, ComfyUILaunchError
from src.ui import comfyui_lifecycle_manager as lifecycle_module
from src.ui.comfyui_lifecycle_manager import (
    EXTERNAL_ACTIVE,
    RUNNING_OWNED,
    STARTING,
    START_FAILED,
    STOPPED,
    STOPPING,
    ComfyUILifecycleManager,
)

_app = QApplication.instance() or QApplication([])

_FAKE_PROCESS_SCRIPT = str(Path(__file__).resolve().parent / "_fake_comfyui_process.py")


def _pump_until(condition, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if condition():
            return True
        time.sleep(0.01)
    return condition()


class ComfyUILifecycleManagerRealProcessTest(unittest.TestCase):
    """
    Real QProcess against the deterministic fake script. Timing
    constants are patched down so the suite stays fast — the escalation
    *logic* (terminate() then kill() after a bounded wait) is exercised
    for real, only the wait itself is short.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        self._launch_config = ComfyUILaunchConfig(
            python_executable=sys.executable,
            entry_point=_FAKE_PROCESS_SCRIPT,
            working_directory=self.tmp_dir,
            listen_host="127.0.0.1",
            port=8000,
            user_directory=str(Path(self.tmp_dir) / "user"),
            database_url=f"sqlite:///{(Path(self.tmp_dir) / 'user' / 'comfyui.db').as_posix()}",
        )
        self._resolve_patch = patch.object(
            lifecycle_module, "resolve_comfyui_launch", return_value=self._launch_config
        )
        self._resolve_patch.start()
        self.addCleanup(self._resolve_patch.stop)

        self._fake_engine = MagicMock()
        self._engine_patch = patch.object(
            lifecycle_module, "ComfyUIEngine", return_value=self._fake_engine
        )
        self._engine_patch.start()
        self.addCleanup(self._engine_patch.stop)

        self._timing_patches = [
            patch.object(lifecycle_module, "READINESS_BUDGET_SECONDS", 0.5),
            patch.object(lifecycle_module, "READINESS_POLL_INTERVAL_SECONDS", 0.05),
            patch.object(lifecycle_module, "READINESS_ATTEMPT_TIMEOUT_SECONDS", 0.05),
            patch.object(lifecycle_module, "TERMINATE_TIMEOUT_SECONDS", 0.2),
        ]
        for p in self._timing_patches:
            p.start()
            self.addCleanup(p.stop)

        self._env_backup = dict(__import__("os").environ)
        self.addCleanup(self._restore_env)

        self.manager = ComfyUILifecycleManager()

    def _restore_env(self):
        import os
        os.environ.clear()
        os.environ.update(self._env_backup)

    def _set_env(self, **kwargs):
        import os
        for key, value in kwargs.items():
            os.environ[key] = value

    def _start(self):
        self.manager.start("fake-comfyui-path", "fake-install-path", "http://127.0.0.1:8000")

    def tearDown(self):
        # Best-effort real cleanup: never leave a fake process behind.
        if self.manager._process is not None and self.manager._process.state() != QProcess.ProcessState.NotRunning:
            self.manager._process.kill()
            self.manager._process.waitForFinished(2000)

    def test_already_active_before_start_is_external_active_and_never_launches(self):
        self._fake_engine.check_connection.return_value = True  # pre-check succeeds

        self._start()

        self.assertEqual(self.manager.state, EXTERNAL_ACTIVE)
        self.assertIsNone(self.manager._process)

        self.manager.stop()
        self.assertEqual(self.manager.state, EXTERNAL_ACTIVE)

    def test_launch_error_before_any_process_is_start_failed(self):
        self._resolve_patch.stop()
        with patch.object(lifecycle_module, "resolve_comfyui_launch", side_effect=ComfyUILaunchError("boom")):
            self.manager.start("", "", "http://127.0.0.1:8000")
        self._resolve_patch.start()

        self.assertEqual(self.manager.state, START_FAILED)
        self.assertEqual(self.manager.last_error_message, "boom")

    def test_readiness_success_reaches_running_owned_and_stops_polling(self):
        self._fake_engine.check_connection.side_effect = [
            ComfyUIEngineError("not yet"),  # pre-Start check
            ComfyUIEngineError("not yet"),  # readiness attempt 1
            ComfyUIEngineError("not yet"),  # readiness attempt 2
            True,                            # readiness attempt 3 -- ready
        ]
        self._set_env(FAKE_RUN_SECONDS="3600")

        states = []
        self.manager.state_changed.connect(states.append)
        self._start()

        self.assertTrue(_pump_until(lambda: self.manager.state == RUNNING_OWNED))
        self.assertIn(STARTING, states)
        self.assertIn(RUNNING_OWNED, states)

        call_count_at_ready = self._fake_engine.check_connection.call_count
        _pump_until(lambda: False, timeout=0.3)  # let any stray late poll surface
        self.assertEqual(self._fake_engine.check_connection.call_count, call_count_at_ready)
        self.assertTrue(_pump_until(lambda: self.manager._readiness_thread is None))

        self.manager.stop()
        self.assertTrue(_pump_until(lambda: self.manager.state == STOPPED))
        self.assertIsNone(self.manager._process)

    def test_process_exits_before_readiness_is_start_failed(self):
        self._fake_engine.check_connection.side_effect = ComfyUIEngineError("never ready")
        self._set_env(FAKE_RUN_SECONDS="0.1", FAKE_EXIT_CODE="1")

        self._start()
        self.assertTrue(_pump_until(lambda: self.manager.state == START_FAILED, timeout=5.0))
        self.assertIn("exit_code=1", self.manager.last_error_message)
        self.assertTrue(_pump_until(lambda: self.manager._readiness_thread is None))

    def test_readiness_timeout_cleans_up_process_and_lands_on_start_failed(self):
        self._fake_engine.check_connection.side_effect = ComfyUIEngineError("never ready")
        self._set_env(FAKE_RUN_SECONDS="3600")  # would run forever without the timeout cleanup

        self._start()
        self.assertTrue(_pump_until(lambda: self.manager.state == START_FAILED, timeout=5.0))
        self.assertIn("did not become available", self.manager.last_error_message)
        self.assertTrue(_pump_until(
            lambda: self.manager._process is None
            or self.manager._process.state() == QProcess.ProcessState.NotRunning
        ))
        self.assertTrue(_pump_until(lambda: self.manager._readiness_thread is None))

    def test_stop_during_starting_reaches_stopped_and_ignores_late_ready(self):
        self._fake_engine.check_connection.side_effect = ComfyUIEngineError("not yet")
        self._set_env(FAKE_RUN_SECONDS="3600")

        self._start()
        self.assertTrue(_pump_until(lambda: self.manager.state == STARTING))

        self.manager.stop()
        self.assertEqual(self.manager.state, STOPPING)

        # A late HTTP success arriving after Stop was requested must
        # never flip the state back to RUNNING_OWNED.
        stale_or_current = self.manager._readiness_worker or object()
        with patch.object(ComfyUILifecycleManager, "sender", return_value=stale_or_current):
            self.manager._on_readiness_ready()
        self.assertNotEqual(self.manager.state, RUNNING_OWNED)

        self.assertTrue(_pump_until(lambda: self.manager.state == STOPPED, timeout=5.0))
        self.assertIsNone(self.manager._process)
        self.assertTrue(_pump_until(lambda: self.manager._readiness_thread is None))

    def test_stop_on_running_owned_reaches_stopped(self):
        self._fake_engine.check_connection.return_value = True  # pre-check first
        self._set_env(FAKE_RUN_SECONDS="3600")

        # First call (pre-check) must fail so Start actually launches;
        # subsequent calls (readiness) succeed immediately.
        self._fake_engine.check_connection.side_effect = [ComfyUIEngineError("not yet"), True]

        self._start()
        self.assertTrue(_pump_until(lambda: self.manager.state == RUNNING_OWNED))

        self.manager.stop()
        self.assertEqual(self.manager.state, STOPPING)
        self.assertTrue(_pump_until(lambda: self.manager.state == STOPPED, timeout=5.0))

    def test_stop_is_idempotent_on_running_owned(self):
        self._fake_engine.check_connection.side_effect = [ComfyUIEngineError("not yet"), True]
        self._set_env(FAKE_RUN_SECONDS="3600")

        self._start()
        self.assertTrue(_pump_until(lambda: self.manager.state == RUNNING_OWNED))

        self.manager.stop()
        self.manager.stop()  # second call while already STOPPING must not raise or double-act
        self.assertTrue(_pump_until(lambda: self.manager.state == STOPPED, timeout=5.0))


class ComfyUILifecycleManagerGuardTest(unittest.TestCase):
    """
    Stale-signal/identity/state guards and confirm_safe_to_close() —
    direct method calls with fabricated internal state, same idiom as
    TrainingJobRunnerCancelEscalationTest. No real QProcess/QThread here.
    """

    def setUp(self):
        self.manager = ComfyUILifecycleManager()

    def test_start_command_includes_user_directory_and_database_url(self):
        # Mission 114 (post-diagnostic correction): the real command
        # QProcess.start() is actually given, verified in full -- Python
        # executable, main.py, --base-directory, the two new arguments
        # added after the real diagnostic relaunch, and --listen/--port
        # all present, in the order the resolver's own fields dictate.
        # QProcess is mocked (never a real subprocess) to keep this a
        # fast, isolated unit test of the constructed argument list --
        # the real QProcess lifecycle is already covered end to end by
        # ComfyUILifecycleManagerRealProcessTest above. QThread is left
        # real (a MagicMock fails PySide6's moveToThread() type check),
        # but the readiness engine succeeds on its very first poll, so
        # that real background thread finishes and tears itself down
        # within milliseconds regardless of this test's own lifetime.
        launch = ComfyUILaunchConfig(
            python_executable="C:/ComfyUI/.venv/Scripts/python.exe",
            entry_point="C:/ComfyUIDesktop/resources/ComfyUI/main.py",
            working_directory="C:/ComfyUI",
            listen_host="127.0.0.1",
            port=8000,
            user_directory="C:/ComfyUI/user",
            database_url="sqlite:///C:/ComfyUI/user/comfyui.db",
        )
        mock_process = MagicMock()
        with patch.object(lifecycle_module, "resolve_comfyui_launch", return_value=launch), \
                patch.object(lifecycle_module, "ComfyUIEngine") as engine_cls, \
                patch.object(lifecycle_module, "QProcess", return_value=mock_process):
            engine_cls.return_value.check_connection.side_effect = [
                ComfyUIEngineError("not yet"),  # pre-Start check -- must fail so Start proceeds
                True,  # readiness worker's first poll -- succeeds immediately
            ]
            self.manager.start("C:/ComfyUI", "C:/ComfyUIDesktop", "http://127.0.0.1:8000")

        mock_process.start.assert_called_once_with(
            "C:/ComfyUI/.venv/Scripts/python.exe",
            [
                "C:/ComfyUIDesktop/resources/ComfyUI/main.py",
                "--base-directory", "C:/ComfyUI",
                "--user-directory", "C:/ComfyUI/user",
                "--database-url", "sqlite:///C:/ComfyUI/user/comfyui.db",
                "--listen", "127.0.0.1",
                "--port", "8000",
            ],
        )

    def _fake_sender(self, sender):
        # _on_readiness_ready()/_on_readiness_timed_out() are real bound-
        # method Qt slots (never a lambda, since only a genuine bound
        # method of a QObject gets Qt's automatic cross-thread queuing --
        # see comfyui_lifecycle_manager.py's own comment on this) and
        # read the emitting worker via self.sender(), which only returns
        # a real value while a connected signal is actually being
        # dispatched. Patching QObject.sender() lets these guards be unit
        # tested directly, exactly like TrainingJobRunnerCancelEscalationTest
        # calls internal handlers directly with QProcess spied on.
        return patch.object(ComfyUILifecycleManager, "sender", return_value=sender)

    def test_readiness_ready_from_a_stale_worker_is_ignored(self):
        current_worker = MagicMock()
        stale_worker = MagicMock()
        self.manager._readiness_worker = current_worker
        self.manager._state = STARTING

        with self._fake_sender(stale_worker):
            self.manager._on_readiness_ready()

        self.assertEqual(self.manager.state, STARTING)

    def test_readiness_ready_after_state_left_starting_is_ignored(self):
        worker = MagicMock()
        self.manager._readiness_worker = worker
        self.manager._state = STOPPING  # e.g. Stop was requested first

        with self._fake_sender(worker):
            self.manager._on_readiness_ready()

        self.assertEqual(self.manager.state, STOPPING)

    def test_readiness_timed_out_from_a_stale_worker_is_ignored(self):
        current_worker = MagicMock()
        stale_worker = MagicMock()
        self.manager._readiness_worker = current_worker
        self.manager._state = STARTING

        with self._fake_sender(stale_worker):
            self.manager._on_readiness_timed_out()

        self.assertEqual(self.manager.state, STARTING)
        self.assertIsNone(self.manager._readiness_timeout_message)

    def test_process_finished_ignored_shape_never_double_transitions(self):
        # _on_process_finished only acts on STARTING/STOPPING -- any
        # other state (defensive) must leave state untouched.
        self.manager._state = EXTERNAL_ACTIVE
        self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)
        self.assertEqual(self.manager.state, EXTERNAL_ACTIVE)

    def test_stop_is_a_no_op_on_external_active(self):
        self.manager._state = EXTERNAL_ACTIVE
        self.manager.stop()
        self.assertEqual(self.manager.state, EXTERNAL_ACTIVE)

    def test_stop_is_a_no_op_on_stopped(self):
        self.manager._state = STOPPED
        self.manager.stop()
        self.assertEqual(self.manager.state, STOPPED)

    def test_start_is_a_no_op_while_already_starting(self):
        with patch.object(lifecycle_module, "resolve_comfyui_launch") as resolve_mock:
            self.manager._state = STARTING
            self.manager.start("p", "i", "http://127.0.0.1:8000")
            resolve_mock.assert_not_called()

    def test_start_is_a_no_op_while_running_owned(self):
        with patch.object(lifecycle_module, "resolve_comfyui_launch") as resolve_mock:
            self.manager._state = RUNNING_OWNED
            self.manager.start("p", "i", "http://127.0.0.1:8000")
            resolve_mock.assert_not_called()

    # --- confirm_safe_to_close() ---

    def test_confirm_safe_to_close_true_when_stopped(self):
        self.manager._state = STOPPED
        self.assertTrue(self.manager.confirm_safe_to_close(MagicMock()))

    def test_confirm_safe_to_close_true_when_external_active_no_dialog(self):
        self.manager._state = EXTERNAL_ACTIVE
        with patch("src.ui.comfyui_lifecycle_manager.QMessageBox") as box:
            self.assertTrue(self.manager.confirm_safe_to_close(MagicMock()))
            box.question.assert_not_called()
            box.warning.assert_not_called()

    def test_confirm_safe_to_close_true_when_start_failed(self):
        self.manager._state = START_FAILED
        self.assertTrue(self.manager.confirm_safe_to_close(MagicMock()))

    def test_confirm_safe_to_close_blocks_during_starting(self):
        self.manager._state = STARTING
        with patch("src.ui.comfyui_lifecycle_manager.QMessageBox") as box:
            self.assertFalse(self.manager.confirm_safe_to_close(MagicMock()))
            box.warning.assert_called_once()

    def test_confirm_safe_to_close_blocks_during_stopping(self):
        self.manager._state = STOPPING
        with patch("src.ui.comfyui_lifecycle_manager.QMessageBox") as box:
            self.assertFalse(self.manager.confirm_safe_to_close(MagicMock()))
            box.warning.assert_called_once()

    def test_confirm_safe_to_close_running_owned_no_leaves_comfyui_running(self):
        self.manager._state = RUNNING_OWNED
        parent = MagicMock()
        with patch("src.ui.comfyui_lifecycle_manager.QMessageBox") as box:
            box.Yes, box.No = QMessageBox.Yes, QMessageBox.No
            box.question.return_value = QMessageBox.No
            with patch.object(self.manager, "stop") as stop_mock:
                result = self.manager.confirm_safe_to_close(parent)

        self.assertTrue(result)
        stop_mock.assert_not_called()
        parent.close.assert_not_called()

    def test_confirm_safe_to_close_running_owned_yes_defers_close_until_stopped(self):
        self.manager._state = RUNNING_OWNED
        parent = MagicMock()
        with patch("src.ui.comfyui_lifecycle_manager.QMessageBox") as box:
            box.Yes, box.No = QMessageBox.Yes, QMessageBox.No
            box.question.return_value = QMessageBox.Yes
            with patch.object(self.manager, "stop") as stop_mock:
                result = self.manager.confirm_safe_to_close(parent)

        self.assertFalse(result)
        stop_mock.assert_called_once()
        parent.close.assert_not_called()  # not yet -- only once Stop really finishes

        # Simulate Stop having actually finished.
        self.manager._state = STOPPED
        self.manager._resume_close_if_pending()
        parent.close.assert_called_once()

    def test_confirm_safe_to_close_does_not_ask_twice_after_resumed_close(self):
        self.manager._state = RUNNING_OWNED
        parent = MagicMock()
        with patch("src.ui.comfyui_lifecycle_manager.QMessageBox") as box:
            box.Yes, box.No = QMessageBox.Yes, QMessageBox.No
            box.question.return_value = QMessageBox.Yes
            with patch.object(self.manager, "stop"):
                self.manager.confirm_safe_to_close(parent)

            self.manager._state = STOPPED
            self.manager._resume_close_if_pending()

            # The real second closeEvent() would call confirm_safe_to_close()
            # again -- by now state is STOPPED, so no dialog is shown.
            self.assertTrue(self.manager.confirm_safe_to_close(parent))
            box.question.assert_called_once()


if __name__ == "__main__":
    unittest.main()
