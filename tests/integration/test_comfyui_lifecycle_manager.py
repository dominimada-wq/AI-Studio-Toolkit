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

Mission 170 adds the families around _LifecycleCase (a real QProcess against
the same fake process double, kept alive, with a strict cooperative cleanup):
behavior-only regressions (an exception outside the engine's own error used to
lose the readiness worker's terminal signal and leave STARTING forever), the
historical invariants around them, and the new contract (failed, its message,
its guards), kept apart from the proof of the defect.
"""
import http.client
import logging
import os
import shutil
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from src.engines.comfyui_engine import ComfyUIEngineError
from src.engines.comfyui_launch import ComfyUILaunchConfig, ComfyUILaunchError
from src.ui import comfyui_lifecycle_manager as lifecycle_module
from src.ui import comfyui_readiness_worker as worker_module
from src.ui.comfyui_lifecycle_manager import (
    EXTERNAL_ACTIVE,
    RUNNING_OWNED,
    STARTING,
    START_FAILED,
    STOPPED,
    STOPPING,
    ComfyUILifecycleManager,
)
from src.ui.pages.settings_page import SettingsPage

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

    def test_process_dies_spontaneously_while_running_owned_reaches_start_failed(self):
        # Mission 146: a real process that exits on its own (never killed
        # by Toolkit) while genuinely RUNNING_OWNED -- no Stop ever
        # requested here.
        self._fake_engine.check_connection.side_effect = [
            ComfyUIEngineError("not yet"),  # pre-Start check
            ComfyUIEngineError("not yet"),  # readiness attempt 1
            True,                            # readiness attempt 2 -- ready
        ]
        self._set_env(FAKE_RUN_SECONDS="0.3", FAKE_EXIT_CODE="0")

        self._start()
        self.assertTrue(_pump_until(lambda: self.manager.state == RUNNING_OWNED))
        old_process = self.manager._process
        self.assertIsNotNone(old_process)

        self.assertTrue(_pump_until(lambda: self.manager.state == START_FAILED, timeout=5.0))
        self.assertIsNone(self.manager._process)
        self.assertIn("exit_code=0", self.manager.last_error_message)

        # start() must work immediately afterward, launching a genuinely
        # new, distinct process.
        self._fake_engine.check_connection.side_effect = ComfyUIEngineError("not yet")
        self._set_env(FAKE_RUN_SECONDS="3600")
        self._start()
        self.assertTrue(_pump_until(lambda: self.manager.state == STARTING))
        self.assertIsNotNone(self.manager._process)
        self.assertIsNot(self.manager._process, old_process)

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
        # _on_process_finished only acts on STARTING/STOPPING/RUNNING_OWNED
        # -- any other state (defensive) must leave state untouched.
        self.manager._state = EXTERNAL_ACTIVE
        self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)
        self.assertEqual(self.manager.state, EXTERNAL_ACTIVE)

    # --- Mission 146: spontaneous death while genuinely RUNNING_OWNED,
    # no Stop ever requested ---

    def test_process_finished_while_running_owned_reaches_start_failed(self):
        self.manager._state = RUNNING_OWNED
        self.manager._process = MagicMock()

        self.manager._on_process_finished(1, QProcess.ExitStatus.CrashExit)

        self.assertEqual(self.manager.state, START_FAILED)
        self.assertIsNone(self.manager._process)
        self.assertIn("exit_code=1", self.manager.last_error_message)
        # Never borrows the STARTING readiness-timeout wording -- ComfyUI
        # was fully up and running, not still becoming available.
        self.assertNotIn("becoming available", self.manager.last_error_message)

    def test_process_finished_while_running_owned_never_arms_a_terminate_timer(self):
        # The owned process is already dead -- there is nothing left to
        # terminate()/kill(), so this recovery path must never arm a new
        # terminate timer.
        self.manager._state = RUNNING_OWNED
        self.manager._process = MagicMock()

        self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)

        self.assertIsNone(self.manager._terminate_timer)

    def test_start_after_running_owned_recovery_launches_a_genuinely_new_process(self):
        old_process = MagicMock()
        self.manager._state = RUNNING_OWNED
        self.manager._process = old_process

        self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)
        self.assertEqual(self.manager.state, START_FAILED)

        launch = ComfyUILaunchConfig(
            python_executable="C:/ComfyUI/.venv/Scripts/python.exe",
            entry_point="C:/ComfyUIDesktop/resources/ComfyUI/main.py",
            working_directory="C:/ComfyUI",
            listen_host="127.0.0.1",
            port=8000,
            user_directory="C:/ComfyUI/user",
            database_url="sqlite:///C:/ComfyUI/user/comfyui.db",
        )
        new_process = MagicMock()
        with patch.object(lifecycle_module, "resolve_comfyui_launch", return_value=launch), \
                patch.object(lifecycle_module, "ComfyUIEngine") as engine_cls, \
                patch.object(lifecycle_module, "QProcess", return_value=new_process):
            engine_cls.return_value.check_connection.side_effect = ComfyUIEngineError("not yet")
            self.manager.start("C:/ComfyUI", "C:/ComfyUIDesktop", "http://127.0.0.1:8000")

        self.assertEqual(self.manager.state, STARTING)
        self.assertIs(self.manager._process, new_process)
        self.assertIsNot(self.manager._process, old_process)

    # --- Mission 142: stale terminate timer guards ---

    def test_on_process_finished_stops_and_clears_the_terminate_timer_once_resolved(self):
        real_timer = QTimer(self.manager)
        real_timer.setSingleShot(True)
        real_timer.timeout.connect(self.manager._on_terminate_timeout)
        real_timer.start(60_000)  # long enough to never fire during this test
        self.manager._terminate_timer = real_timer

        self.manager._state = STOPPING
        self.manager._process = MagicMock()

        self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)

        self.assertEqual(self.manager.state, STOPPED)
        self.assertIsNone(self.manager._terminate_timer)
        self.assertFalse(real_timer.isActive())

    def test_finish_process_teardown_stops_and_clears_a_residual_terminate_timer(self):
        real_timer = QTimer(self.manager)
        real_timer.setSingleShot(True)
        real_timer.timeout.connect(self.manager._on_terminate_timeout)
        real_timer.start(60_000)
        self.manager._terminate_timer = real_timer

        self.manager._state = STOPPING
        self.manager._process = MagicMock()

        self.manager._finish_process_teardown()

        self.assertEqual(self.manager.state, STOPPED)
        self.assertIsNone(self.manager._terminate_timer)
        self.assertFalse(real_timer.isActive())

    def test_stale_terminate_timeout_signal_is_ignored(self):
        current_timer = MagicMock()
        self.manager._terminate_timer = current_timer
        stale_timer = MagicMock()
        self.manager._process = MagicMock()

        with self._fake_sender(stale_timer):
            self.manager._on_terminate_timeout()

        self.manager._process.kill.assert_not_called()
        self.assertIs(self.manager._terminate_timer, current_timer)

    def test_terminate_timeout_from_the_current_timer_is_not_treated_as_stale(self):
        timer = MagicMock()
        self.manager._terminate_timer = timer
        self.manager._process = MagicMock()
        self.manager._process.state.return_value = QProcess.ProcessState.Running

        with self._fake_sender(timer):
            self.manager._on_terminate_timeout()

        self.manager._process.kill.assert_called_once()

    def test_stale_terminate_timeout_from_a_resolved_stop_never_affects_a_later_start(self):
        # Cycle A: a Stop that resolves via the process actually exiting
        # before its own real QTimer would ever fire.
        self.manager._state = STOPPING

        timer_a = QTimer(self.manager)
        timer_a.setSingleShot(True)
        timer_a.timeout.connect(self.manager._on_terminate_timeout)
        timer_a.start(60_000)
        self.manager._terminate_timer = timer_a
        self.manager._process = MagicMock()

        self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)

        self.assertEqual(self.manager.state, STOPPED)
        self.assertIsNone(self.manager._terminate_timer)
        self.assertFalse(timer_a.isActive())

        # Cycle B: a brand-new, legitimate Start on the very same
        # manager instance -- never itself calls
        # _terminate_owned_process().
        process_b = MagicMock()
        self.manager._state = STARTING
        self.manager._process = process_b

        with self._fake_sender(timer_a):
            self.manager._on_terminate_timeout()

        process_b.kill.assert_not_called()
        self.assertEqual(self.manager.state, STARTING)
        self.assertIs(self.manager._process, process_b)

    def test_stale_terminate_timeout_from_a_resolved_stop_never_kills_a_later_running_owned_process(self):
        # Same cross-cycle scenario, but cycle B has already reached
        # RUNNING_OWNED by the time the stale timer fires -- the
        # silent-state variant documented in MISSION_142.md section 2.
        self.manager._state = STOPPING
        timer_a = QTimer(self.manager)
        timer_a.setSingleShot(True)
        timer_a.timeout.connect(self.manager._on_terminate_timeout)
        timer_a.start(60_000)
        self.manager._terminate_timer = timer_a
        self.manager._process = MagicMock()

        self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)
        self.assertIsNone(self.manager._terminate_timer)

        process_b = MagicMock()
        process_b.state.return_value = QProcess.ProcessState.Running
        self.manager._state = RUNNING_OWNED
        self.manager._process = process_b

        with self._fake_sender(timer_a):
            self.manager._on_terminate_timeout()

        process_b.kill.assert_not_called()
        self.assertEqual(self.manager.state, RUNNING_OWNED)
        self.assertIs(self.manager._process, process_b)

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

    # --- Mission 147: confirm_safe_to_close() modal reentrancy race ---

    def _yes_after_dying_during_dialog(self):
        # Mission 146's own recovery firing while this QMessageBox.
        # question() call's own nested event loop is still running --
        # the exact Mission 147 race, reproduced deterministically
        # without any real QProcess.
        def _side_effect(*args, **kwargs):
            self.manager._state = START_FAILED
            self.manager._process = None
            return QMessageBox.Yes
        return _side_effect

    def test_confirm_safe_to_close_allows_close_when_process_died_during_the_dialog(self):
        self.manager._state = RUNNING_OWNED
        parent = MagicMock()
        with patch("src.ui.comfyui_lifecycle_manager.QMessageBox") as box, \
                patch.object(self.manager, "stop") as stop_mock:
            box.Yes, box.No = QMessageBox.Yes, QMessageBox.No
            box.question.side_effect = self._yes_after_dying_during_dialog()
            result = self.manager.confirm_safe_to_close(parent)

        self.assertTrue(result)
        self.assertIsNone(self.manager._pending_close_widget)
        stop_mock.assert_not_called()
        parent.close.assert_not_called()

    def test_confirm_safe_to_close_process_died_during_dialog_never_triggers_a_teardown(self):
        self.manager._state = RUNNING_OWNED
        parent = MagicMock()
        with patch("src.ui.comfyui_lifecycle_manager.QMessageBox") as box, \
                patch.object(self.manager, "_terminate_owned_process") as terminate_mock:
            box.Yes, box.No = QMessageBox.Yes, QMessageBox.No
            box.question.side_effect = self._yes_after_dying_during_dialog()
            self.manager.confirm_safe_to_close(parent)

        terminate_mock.assert_not_called()
        self.assertIsNone(self.manager._terminate_timer)

    def test_confirm_safe_to_close_process_died_during_dialog_leaves_no_stale_pending_close_for_a_later_cycle(self):
        self.manager._state = RUNNING_OWNED
        parent = MagicMock()
        with patch("src.ui.comfyui_lifecycle_manager.QMessageBox") as box:
            box.Yes, box.No = QMessageBox.Yes, QMessageBox.No
            box.question.side_effect = self._yes_after_dying_during_dialog()
            self.manager.confirm_safe_to_close(parent)

        self.assertIsNone(self.manager._pending_close_widget)

        # A later, completely unrelated Stop cycle resolving on this same
        # session-long instance must never resume a close nobody asked
        # for -- there is no stale widget reference left to resume.
        self.manager._state = STOPPING
        self.manager._finish_process_teardown()

        self.assertEqual(self.manager.state, STOPPED)
        parent.close.assert_not_called()


class _EngineScript:
    """
    Mission 170: callable side_effect for the mocked engine -- one action per
    call, the last one repeating. Controlled waits use a releasable Event
    (never a free sleep), so the test cleanup can always free them.
    Actions: ("ok",) | ("raise", exc) | ("wait", seconds, then_action).
    """

    def __init__(self, release, actions):
        self._release = release
        self._actions = list(actions)
        self.calls = 0

    def __call__(self, *args, **kwargs):
        index = self.calls
        self.calls += 1
        action = self._actions[min(index, len(self._actions) - 1)]
        while action[0] == "wait":
            self._release.wait(action[1])
            action = action[2]
        if action[0] == "raise":
            raise action[1]
        return True


def _ok():
    return ("ok",)


def _raise(exc):
    return ("raise", exc)


def _wait(seconds, then):
    return ("wait", seconds, then)


# Worker/thread pairs that the cooperative cleanup could not stop: kept referenced so a
# running QThread is never destroyed while active, and never terminate()d.
_GRAVEYARD = []


def _ui_commands(manager):
    """(start_enabled, stop_enabled) as the real SettingsPage handler computes them from manager.state."""
    stub = types.SimpleNamespace(
        comfyui_lifecycle_status_label=MagicMock(),
        comfyui_lifecycle_manager=manager,
        comfyui_start_button=MagicMock(),
        comfyui_stop_button=MagicMock(),
    )
    SettingsPage._on_comfyui_lifecycle_state_changed(stub, manager.state)
    return (
        stub.comfyui_start_button.setEnabled.call_args[0][0],
        stub.comfyui_stop_button.setEnabled.call_args[0][0],
    )


class _LifecycleCase(unittest.TestCase):
    """
    Mission 170 fixture: a real ComfyUILifecycleManager, a real QProcess against
    the existing fake process double (kept ALIVE until the manager or the cleanup
    ends it), a mocked engine, short timings.

    Cleanup contract, valid even on an implementation that loses the terminal
    signal: every (worker, thread) pair is recorded right after each
    _start_readiness_worker() call (before a later start() could replace it);
    controlled waits are released; cancel() then quit() are requested and wait()
    is checked with a bounded delay -- a thread still active is a cleanup failure,
    kept referenced, never destroyed, never terminate()d. Only the QProcess
    objects this test's manager created are ever killed.
    """

    quiet_logs = True

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
        self._fake_engine = MagicMock()
        patches = [
            patch.object(lifecycle_module, "resolve_comfyui_launch", return_value=self._launch_config),
            patch.object(lifecycle_module, "ComfyUIEngine", return_value=self._fake_engine),
            patch.object(lifecycle_module, "READINESS_BUDGET_SECONDS", 0.5),
            patch.object(lifecycle_module, "READINESS_POLL_INTERVAL_SECONDS", 0.05),
            patch.object(lifecycle_module, "READINESS_ATTEMPT_TIMEOUT_SECONDS", 0.05),
            patch.object(lifecycle_module, "TERMINATE_TIMEOUT_SECONDS", 0.2),
            patch.dict(os.environ, {"FAKE_RUN_SECONDS": "3600", "FAKE_EXIT_CODE": "0"}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        if self.quiet_logs:
            for name in (worker_module.__name__, lifecycle_module.__name__):
                module_logger = logging.getLogger(name)
                previous = module_logger.disabled
                module_logger.disabled = True
                self.addCleanup(setattr, module_logger, "disabled", previous)

        self.release = threading.Event()
        self._registry = []
        self._processes = []
        self.states = []

        self.manager = ComfyUILifecycleManager()
        original_start_worker = self.manager._start_readiness_worker

        def _recording_start_worker(check_engine):
            original_start_worker(check_engine)
            self._registry.append((self.manager._readiness_worker, self.manager._readiness_thread))

        self.manager._start_readiness_worker = _recording_start_worker
        self.manager.state_changed.connect(self._on_state)
        self.addCleanup(self._cooperative_cleanup)  # registered last, so it runs first

    def _on_state(self, state):
        self.states.append(state)
        process = self.manager._process
        if process is not None and process not in self._processes:
            self._processes.append(process)

    def _cooperative_cleanup(self):
        failures = []
        self.release.set()
        for worker, thread in self._registry:
            try:
                worker.cancel()
                thread.quit()
                stopped = thread.wait(3000)
            except RuntimeError:
                stopped = True  # the C++ object is already deleted: nothing is left running
            if not stopped:
                _GRAVEYARD.append((worker, thread))
                failures.append("a readiness thread is still active after the cooperative cleanup")
        for process in self._processes:
            try:
                if process.state() != QProcess.ProcessState.NotRunning:
                    process.kill()
                    if not process.waitForFinished(3000):
                        failures.append("an owned test process is still running")
            except RuntimeError:
                pass
        if failures:
            raise AssertionError("; ".join(failures))

    def script(self, actions):
        script = _EngineScript(self.release, actions)
        self._fake_engine.check_connection.side_effect = script
        return script

    def start(self):
        self.manager.start("fake-comfyui-path", "fake-install-path", "http://127.0.0.1:8000")

    def wait_for_state(self, state, timeout=4.0):
        reached = _pump_until(lambda: self.manager.state == state, timeout=timeout)
        self.assertTrue(
            reached,
            "state stuck at %r (waiting for %r), states seen: %r, last message: %r"
            % (self.manager.state, state, self.states, self.manager.last_error_message),
        )

    def assert_owned_process_ended_and_thread_cleaned(self):
        self.assertTrue(self._processes, "an owned process must have been created")
        self.assertTrue(
            _pump_until(lambda: all(p.state() == QProcess.ProcessState.NotRunning for p in self._processes), timeout=5.0),
            "the owned process must no longer be running",
        )
        self.assertTrue(
            _pump_until(lambda: self.manager._readiness_thread is None, timeout=5.0),
            "the readiness thread must have ended and been cleaned up",
        )


class ComfyUILifecycleManagerUnexpectedFailureRegressionTest(_LifecycleCase):
    """
    Behavior-only proofs of the Mission 170 defect: an exception outside the
    engine's own error during polling used to lose the terminal signal and leave
    the lifecycle in STARTING, with Start/Stop disabled and the close refused.
    Nothing here reads a new symbol: they fail on the previous implementation by
    assertion.
    """

    def test_unexpected_exception_during_polling_reaches_start_failed_and_cleans_up(self):
        self.script([_raise(ComfyUIEngineError("not yet")), _raise(AttributeError("'list' object has no attribute 'get'"))])

        self.start()
        self.wait_for_state(START_FAILED)

        self.assert_owned_process_ended_and_thread_cleaned()
        self.assertEqual(self.states, [STARTING, START_FAILED])

    def test_after_the_failure_the_user_commands_and_the_close_guard_are_available(self):
        self.script([_raise(ComfyUIEngineError("not yet")), _raise(RuntimeError("boom"))])

        self.start()
        self.wait_for_state(START_FAILED)

        self.assertEqual(_ui_commands(self.manager), (True, False))
        with patch.object(lifecycle_module, "QMessageBox") as box:
            self.assertTrue(self.manager.confirm_safe_to_close(None))
        box.warning.assert_not_called()  # START_FAILED without a process never blocks the close
        box.question.assert_not_called()

    def test_a_new_start_after_the_failure_reaches_running_owned_and_still_asks_before_closing(self):
        self.script([_raise(ComfyUIEngineError("not yet")), _raise(RuntimeError("boom"))])
        self.start()
        self.wait_for_state(START_FAILED)
        failed_process = self._processes[0]

        self.script([_raise(ComfyUIEngineError("not yet")), _ok()])
        self.start()
        self.wait_for_state(RUNNING_OWNED)

        self.assertIsNot(self.manager._process, failed_process)
        # A RUNNING_OWNED process is still protected by the existing confirmation.
        with patch.object(lifecycle_module, "QMessageBox") as box:
            box.Yes, box.No = QMessageBox.Yes, QMessageBox.No
            box.question.return_value = QMessageBox.No
            self.assertTrue(self.manager.confirm_safe_to_close(None))
        box.question.assert_called_once()
        self.assertNotEqual(self.manager._process.state(), QProcess.ProcessState.NotRunning)

        self.manager.stop()
        self.wait_for_state(STOPPED)

    def test_stop_during_a_blocking_attempt_that_then_raises_ends_stopped_and_cleans_the_thread(self):
        engine_script = self.script([_raise(ComfyUIEngineError("not yet")), _wait(0.4, _raise(RuntimeError("late boom")))])

        self.start()
        self.assertTrue(_pump_until(lambda: engine_script.calls >= 2, timeout=3.0), "the polling attempt must be in flight")
        self.manager.stop()
        self.assertEqual(self.manager.state, STOPPING)

        self.wait_for_state(STOPPED, timeout=5.0)
        self.assertTrue(
            _pump_until(lambda: self.manager._readiness_thread is None, timeout=5.0),
            "the readiness thread must end once the blocked attempt returns",
        )
        self.assertEqual(self.states, [STARTING, STOPPING, STOPPED])

    def test_transient_http_errors_followed_by_success_reach_running_owned(self):
        engine_script = self.script([
            _raise(ComfyUIEngineError("not yet")),  # pre-start check
            _raise(http.client.IncompleteRead(b"ab", 10)),
            _raise(http.client.BadStatusLine("garbage")),
            _ok(),
        ])

        self.start()
        self.wait_for_state(RUNNING_OWNED)

        self.assertEqual(engine_script.calls, 4)
        self.assertTrue(_pump_until(lambda: self.manager._readiness_thread is None, timeout=5.0))
        self.manager.stop()
        self.wait_for_state(STOPPED)

    def test_transient_http_errors_until_the_budget_end_in_the_historical_timeout(self):
        self.script([_raise(ComfyUIEngineError("not yet")), _raise(http.client.BadStatusLine("garbage"))])

        self.start()
        self.wait_for_state(START_FAILED, timeout=6.0)

        self.assertIn("did not become available", self.manager.last_error_message)
        self.assert_owned_process_ended_and_thread_cleaned()

    def test_an_http_client_state_error_during_polling_is_not_retried(self):
        engine_script = self.script([_raise(ComfyUIEngineError("not yet")), _raise(http.client.CannotSendRequest("Request-sent"))])

        self.start()
        self.wait_for_state(START_FAILED)

        self.assertEqual(engine_script.calls, 2, "pre-start check plus exactly one polling attempt")
        self.assert_owned_process_ended_and_thread_cleaned()


class ComfyUILifecycleManagerPreStartCheckRegressionTest(_LifecycleCase):
    """
    Behavior-only: an exception outside the engine's own error at the synchronous
    pre-start check must never escape start() nor launch anything (a malformed or
    truncated response does not prove that no service answers on the port).
    """

    def test_an_unexpected_exception_at_the_pre_start_check_never_launches(self):
        cases = [
            ("AttributeError", AttributeError("'list' object has no attribute 'get'")),
            ("IncompleteRead", http.client.IncompleteRead(b"ab", 10)),
            ("BadStatusLine", http.client.BadStatusLine("garbage")),
            ("CannotSendRequest", http.client.CannotSendRequest("Request-sent")),
        ]
        for label, exc in cases:
            with self.subTest(label):
                manager = ComfyUILifecycleManager()
                states = []
                manager.state_changed.connect(states.append)
                self._fake_engine.check_connection.side_effect = exc

                raised = None
                with patch.object(lifecycle_module, "QProcess") as process_cls:
                    try:
                        manager.start("fake-comfyui-path", "fake-install-path", "http://127.0.0.1:8000")
                    except Exception as error:  # the defect: it used to escape start()
                        raised = error

                self.assertIsNone(raised, "start() must not let the exception escape")
                self.assertEqual(manager.state, START_FAILED)
                self.assertEqual(states, [START_FAILED], "never passes through STARTING")
                process_cls.assert_not_called()
                self.assertIsNone(manager._process)
                self.assertIsNone(manager._readiness_thread)


class ComfyUILifecycleManagerReadinessInvariantTest(_LifecycleCase):

    def test_a_pre_start_engine_error_still_proceeds_to_launch(self):
        # Historical meaning kept: an error the engine already translated into
        # ComfyUIEngineError (nothing usable on the port) leads to the launch.
        self.script([_raise(ComfyUIEngineError("not yet")), _ok()])
        mock_process = MagicMock()

        with patch.object(lifecycle_module, "QProcess", return_value=mock_process):
            self.start()

        mock_process.start.assert_called_once()
        self.wait_for_state(RUNNING_OWNED)

    def test_an_already_reachable_service_is_never_launched_over_nor_stopped(self):
        self.script([_ok()])

        with patch.object(lifecycle_module, "QProcess") as process_cls:
            self.start()
            self.manager.stop()

        process_cls.assert_not_called()
        self.assertEqual(self.manager.state, EXTERNAL_ACTIVE)
        self.assertIsNone(self.manager._process)
        self.assertIsNone(self.manager._readiness_thread)


class ComfyUILifecycleManagerUnexpectedFailureContractTest(_LifecycleCase):
    """The Mission 170 contract: failed, its message, its cleanup path. Not a proof of the defect."""

    quiet_logs = False

    def test_the_failure_message_reaches_start_failed_unchanged_with_a_real_process(self):
        self.script([_raise(ComfyUIEngineError("not yet")), _raise(AttributeError("boom"))])

        with self.assertLogs(worker_module.logger, "ERROR") as captured:
            self.start()
            self.wait_for_state(START_FAILED)

        message = self.manager.last_error_message
        self.assertEqual(message, "ComfyUI readiness check failed unexpectedly (AttributeError: boom).")
        self.assertNotIn("stopped", message.lower())  # no claim about an unresolved stop
        self.assertNotIn("did not become available", message)
        self.assert_owned_process_ended_and_thread_cleaned()
        self.assertEqual(len(captured.records), 1)

    def test_a_failure_with_no_live_process_lands_on_start_failed_through_the_shared_teardown(self):
        self.manager._state = STARTING
        worker = MagicMock()
        self.manager._readiness_worker = worker
        self.manager._process = None

        with patch.object(ComfyUILifecycleManager, "sender", return_value=worker):
            self.manager._on_readiness_failed("RuntimeError: boom")

        self.assertEqual(self.manager.state, START_FAILED)
        self.assertEqual(self.manager.last_error_message, "ComfyUI readiness check failed unexpectedly (RuntimeError: boom).")
        self.assertIsNone(self.manager._readiness_timeout_message)  # consumed exactly once


class ComfyUILifecycleManagerFailedHandlerGuardTest(unittest.TestCase):
    """_on_readiness_failed(): worker-identity guard and state guard, fabricated state (no real process or thread)."""

    def setUp(self):
        self.manager = ComfyUILifecycleManager()

    def _fake_sender(self, sender):
        return patch.object(ComfyUILifecycleManager, "sender", return_value=sender)

    def test_a_failed_signal_from_a_stale_worker_is_ignored(self):
        current_worker, stale_worker = MagicMock(), MagicMock()
        self.manager._readiness_worker = current_worker
        self.manager._state = STARTING

        with self._fake_sender(stale_worker), patch.object(self.manager, "_terminate_owned_process") as terminate:
            self.manager._on_readiness_failed("RuntimeError: boom")

        terminate.assert_not_called()
        self.assertIsNone(self.manager._readiness_timeout_message)
        self.assertEqual(self.manager.state, STARTING)

    def test_a_late_failed_signal_is_ignored_once_the_state_left_starting(self):
        for state in (STOPPING, START_FAILED, RUNNING_OWNED, STOPPED):
            with self.subTest(state):
                worker = MagicMock()
                self.manager._readiness_worker = worker
                self.manager._state = state
                self.manager._readiness_timeout_message = None

                with self._fake_sender(worker), patch.object(self.manager, "_terminate_owned_process") as terminate:
                    self.manager._on_readiness_failed("RuntimeError: boom")

                terminate.assert_not_called()
                self.assertIsNone(self.manager._readiness_timeout_message)
                self.assertEqual(self.manager.state, state)

    def test_the_current_worker_in_starting_sets_the_message_and_starts_one_cleanup(self):
        worker = MagicMock()
        self.manager._readiness_worker = worker
        self.manager._state = STARTING

        with self._fake_sender(worker), patch.object(self.manager, "_terminate_owned_process") as terminate:
            self.manager._on_readiness_failed("RuntimeError: boom")

        terminate.assert_called_once_with()
        self.assertEqual(
            self.manager._readiness_timeout_message,
            "ComfyUI readiness check failed unexpectedly (RuntimeError: boom).",
        )
        self.assertEqual(self.manager.state, STARTING)  # internal cleanup, never a Stop


class ComfyUILifecycleManagerPreStartCheckContractTest(_LifecycleCase):
    """The pre-start failure message, logging and no-op Stop. Not a proof of the defect."""

    quiet_logs = False

    def _start_with_pre_check_exception(self, exc):
        self._fake_engine.check_connection.side_effect = exc
        with patch.object(lifecycle_module, "QProcess") as process_cls:
            self.start()
        process_cls.assert_not_called()

    def test_the_message_states_that_nothing_was_started(self):
        with self.assertLogs(lifecycle_module.logger, "ERROR") as captured:
            self._start_with_pre_check_exception(AttributeError("boom"))

        self.assertEqual(
            self.manager.last_error_message,
            "ComfyUI pre-start check failed unexpectedly (AttributeError: boom). "
            "The state of the port could not be determined, so nothing was started.",
        )
        self.assertEqual(len(captured.records), 1)

    def test_a_raw_http_exception_is_reported_with_its_type(self):
        with self.assertLogs(lifecycle_module.logger, "ERROR"):
            self._start_with_pre_check_exception(http.client.IncompleteRead(b"ab", 10))

        self.assertEqual(self.manager.state, START_FAILED)
        self.assertIn("IncompleteRead", self.manager.last_error_message)

    def test_an_exception_whose_str_fails_still_reaches_start_failed_with_its_type_name(self):
        class _BadStr(Exception):
            def __str__(self):
                raise RuntimeError("str() failed")

        with self.assertLogs(lifecycle_module.logger, "ERROR"):
            self._start_with_pre_check_exception(_BadStr())

        self.assertEqual(self.manager.state, START_FAILED)
        self.assertIn("(_BadStr)", self.manager.last_error_message)

    def test_stop_after_a_pre_start_failure_is_a_no_op(self):
        with self.assertLogs(lifecycle_module.logger, "ERROR"):
            self._start_with_pre_check_exception(AttributeError("boom"))

        self.manager.stop()

        self.assertEqual(self.manager.state, START_FAILED)
        self.assertIsNone(self.manager._process)


if __name__ == "__main__":
    unittest.main()
