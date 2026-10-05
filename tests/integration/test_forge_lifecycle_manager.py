"""
Mission 119: ForgeLifecycleManager — real QProcess lifecycle against a
deterministic fake run.bat wrapping the existing fake process double
(tests/integration/_fake_comfyui_process.py — a generic "stay alive
until killed, or exit on cue" script, not ComfyUI-specific in
behavior, reused here unchanged), never a real Forge installation,
never a GPU, never real network traffic (ForgeEngine.check_connection()
is mocked throughout — this suite tests process/state orchestration,
not HTTP behavior, already covered by test_forge_engine.py's own
connection tests).

The fake run.bat launches the fake process script via sys.executable
directly (no `call`, no bare-name resolution, no PATH dependency) so
these tests exercise the exact real process tree Mission 119's audit
confirmed for a genuine Forge installation: QProcess owns "cmd.exe"
(here, running the fake run.bat), which becomes the real OS parent of
python.exe (the fake process) — proving Stop's taskkill-based tree
termination against a real, if disposable, tree rather than only ever
mocking it away.

Two families, mirroring test_comfyui_lifecycle_manager.py's own split:
- ForgeLifecycleManagerRealProcessTest: a real cmd.exe -> python.exe
  tree, with short timing constants patched in so the suite stays fast.
- ForgeLifecycleManagerGuardTest: the stale-signal/identity/state
  guards and confirm_safe_to_close(), verified by direct method calls
  and fabricated internal state — same idiom as
  ComfyUILifecycleManagerGuardTest.

Mission 170 adds the families around _LifecycleCase (a real cmd.exe -> python.exe
tree against the same fake process double, kept alive, with a strict cooperative
cleanup): behavior-only regressions (an exception outside the engine's own error
used to lose the readiness worker's terminal signal and leave STARTING forever),
the historical invariants around them, the new contract (failed, its message,
its guards) and its passage through the existing taskkill rendezvous, kept apart
from the proof of the defect.
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

from src.engines.forge_engine import ForgeEngineError
from src.engines.forge_launch import ForgeLaunchConfig, ForgeLaunchError
from src.ui import forge_lifecycle_manager as lifecycle_module
from src.ui import forge_readiness_worker as worker_module
from src.ui.forge_lifecycle_manager import (
    EXTERNAL_ACTIVE,
    RUNNING_OWNED,
    STARTING,
    START_FAILED,
    STOPPED,
    STOPPING,
    ForgeLifecycleManager,
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


class ForgeLifecycleManagerRealProcessTest(unittest.TestCase):
    """
    Real cmd.exe -> python.exe tree against the fake run.bat/fake
    process double. Timing constants are patched down so the suite
    stays fast — the taskkill-based tree-termination *logic* is
    exercised for real, only the wait/budget is short.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        fake_run_bat = Path(self.tmp_dir) / "run.bat"
        fake_run_bat.write_text(
            f'@echo off\n"{sys.executable}" "{_FAKE_PROCESS_SCRIPT}"\n'
        )

        self._launch_config = ForgeLaunchConfig(
            working_directory=self.tmp_dir,
            run_bat_path=str(fake_run_bat),
            extra_path_dirs=(),
            listen_host="127.0.0.1",
            port=7860,
        )
        self._resolve_patch = patch.object(
            lifecycle_module, "resolve_forge_launch", return_value=self._launch_config
        )
        self._resolve_patch.start()
        self.addCleanup(self._resolve_patch.stop)

        self._fake_engine = MagicMock()
        self._engine_patch = patch.object(
            lifecycle_module, "ForgeEngine", return_value=self._fake_engine
        )
        self._engine_patch.start()
        self.addCleanup(self._engine_patch.stop)

        self._timing_patches = [
            patch.object(lifecycle_module, "READINESS_BUDGET_SECONDS", 0.5),
            patch.object(lifecycle_module, "READINESS_POLL_INTERVAL_SECONDS", 0.05),
            patch.object(lifecycle_module, "READINESS_ATTEMPT_TIMEOUT_SECONDS", 0.05),
            patch.object(lifecycle_module, "TERMINATE_TIMEOUT_SECONDS", 3.0),
        ]
        for p in self._timing_patches:
            p.start()
            self.addCleanup(p.stop)

        self.manager = ForgeLifecycleManager()

    def _start(self):
        self.manager.start("fake-forge-path", "http://127.0.0.1:7860")

    def tearDown(self):
        # Best-effort real cleanup: never leave a fake process tree
        # behind, regardless of how the test itself ended.
        if self.manager._process is not None and self.manager._process.state() != QProcess.ProcessState.NotRunning:
            pid = self.manager._process.processId()
            if pid:
                QProcess.execute("taskkill", ["/PID", str(pid), "/T", "/F"])
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
        with patch.object(lifecycle_module, "resolve_forge_launch", side_effect=ForgeLaunchError("boom")):
            self.manager.start("", "http://127.0.0.1:7860")
        self._resolve_patch.start()

        self.assertEqual(self.manager.state, START_FAILED)
        self.assertEqual(self.manager.last_error_message, "boom")

    def test_readiness_success_reaches_running_owned_and_stops_polling(self):
        self._fake_engine.check_connection.side_effect = [
            ForgeEngineError("not yet"),  # pre-Start check
            ForgeEngineError("not yet"),  # readiness attempt 1
            ForgeEngineError("not yet"),  # readiness attempt 2
            True,                          # readiness attempt 3 -- ready
        ]

        states = []
        self.manager.state_changed.connect(states.append)
        self._start()

        self.assertTrue(_pump_until(lambda: self.manager.state == RUNNING_OWNED))
        self.assertIn(STARTING, states)
        self.assertIn(RUNNING_OWNED, states)
        self.assertTrue(_pump_until(lambda: self.manager._readiness_thread is None))

        self.manager.stop()
        self.assertTrue(_pump_until(lambda: self.manager.state == STOPPED, timeout=10.0))
        self.assertIsNone(self.manager._process)

    def test_stop_on_running_owned_kills_the_real_process_tree(self):
        """
        The core Mission 119 guarantee: Stop must actually terminate the
        real python.exe descendant, not just the cmd.exe QProcess owns
        directly (QProcess.terminate()/.kill() alone never recurses into
        children on Windows -- confirmed empirically during this
        mission's audit).
        """
        self._fake_engine.check_connection.side_effect = [ForgeEngineError("not yet"), True]

        self._start()
        self.assertTrue(_pump_until(lambda: self.manager.state == RUNNING_OWNED))
        owned_process = self.manager._process
        self.assertIsNotNone(owned_process)
        cmd_pid = owned_process.processId()
        self.assertTrue(cmd_pid)

        self.manager.stop()
        self.assertEqual(self.manager.state, STOPPING)
        self.assertTrue(_pump_until(lambda: self.manager.state == STOPPED, timeout=10.0))
        self.assertIsNone(self.manager._process)

        # The owned cmd.exe itself must be genuinely gone (not merely
        # forgotten by this object) -- QProcess reports NotRunning only
        # once the OS process has actually exited.
        self.assertTrue(_pump_until(lambda: owned_process.state() == QProcess.ProcessState.NotRunning))

    def test_stop_during_starting_reaches_stopped(self):
        self._fake_engine.check_connection.side_effect = ForgeEngineError("not yet")

        self._start()
        self.assertTrue(_pump_until(lambda: self.manager.state == STARTING))

        self.manager.stop()
        self.assertEqual(self.manager.state, STOPPING)

        self.assertTrue(_pump_until(lambda: self.manager.state == STOPPED, timeout=10.0))
        self.assertIsNone(self.manager._process)

    def test_stop_is_idempotent_on_running_owned(self):
        self._fake_engine.check_connection.side_effect = [ForgeEngineError("not yet"), True]

        self._start()
        self.assertTrue(_pump_until(lambda: self.manager.state == RUNNING_OWNED))

        self.manager.stop()
        self.manager.stop()  # second call while already STOPPING must not raise or double-act
        self.assertTrue(_pump_until(lambda: self.manager.state == STOPPED, timeout=10.0))

    def test_process_dies_spontaneously_while_running_owned_reaches_start_failed(self):
        # Mission 146: a real cmd.exe -> python.exe tree that exits on
        # its own (never killed by Toolkit) while genuinely RUNNING_OWNED
        # -- no Stop ever requested here.
        import os

        self._fake_engine.check_connection.side_effect = [
            ForgeEngineError("not yet"),  # pre-Start check
            ForgeEngineError("not yet"),  # readiness attempt 1
            True,                          # readiness attempt 2 -- ready
        ]

        with patch.dict(os.environ, {"FAKE_RUN_SECONDS": "0.3", "FAKE_EXIT_CODE": "0"}):
            self._start()
            self.assertTrue(_pump_until(lambda: self.manager.state == RUNNING_OWNED))
            old_process = self.manager._process
            self.assertIsNotNone(old_process)

            self.assertTrue(_pump_until(lambda: self.manager.state == START_FAILED, timeout=5.0))

        self.assertIsNone(self.manager._process)
        self.assertIn("exit_code=0", self.manager.last_error_message)

        # start() must work immediately afterward, launching a genuinely
        # new, distinct process tree.
        self._fake_engine.check_connection.side_effect = ForgeEngineError("not yet")
        self._start()
        self.assertTrue(_pump_until(lambda: self.manager.state == STARTING))
        self.assertIsNotNone(self.manager._process)
        self.assertIsNot(self.manager._process, old_process)


class ForgeLifecycleManagerGuardTest(unittest.TestCase):
    """
    Stale-signal/identity/state guards and confirm_safe_to_close() —
    direct method calls with fabricated internal state, same idiom as
    ComfyUILifecycleManagerGuardTest. No real QProcess/QThread here.
    """

    def setUp(self):
        self.manager = ForgeLifecycleManager()

    def test_start_uses_cmd_exe_with_the_resolved_run_bat_and_prepended_path(self):
        launch = ForgeLaunchConfig(
            working_directory="C:/Forge",
            run_bat_path="C:/Forge/run.bat",
            extra_path_dirs=("C:/Forge", "C:/Forge/webui"),
            listen_host="127.0.0.1",
            port=7860,
        )
        mock_process = MagicMock()
        with patch.object(lifecycle_module, "resolve_forge_launch", return_value=launch), \
                patch.object(lifecycle_module, "ForgeEngine") as engine_cls, \
                patch.object(lifecycle_module, "QProcess", return_value=mock_process):
            engine_cls.return_value.check_connection.side_effect = [
                ForgeEngineError("not yet"),  # pre-Start check -- must fail so Start proceeds
                True,  # readiness worker's first poll -- succeeds immediately
            ]
            self.manager.start("C:/Forge", "http://127.0.0.1:7860")

        mock_process.start.assert_called_once_with("cmd.exe", ["/c", "C:/Forge/run.bat"])
        mock_process.setProcessEnvironment.assert_called_once()

    def _fake_sender(self, sender):
        return patch.object(ForgeLifecycleManager, "sender", return_value=sender)

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
        self.manager._state = EXTERNAL_ACTIVE
        self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)
        self.assertEqual(self.manager.state, EXTERNAL_ACTIVE)

    # --- Readiness-timeout Start-failure cleanup shares the exact same
    # taskkill-confirmation rendezvous as an explicit Stop (see
    # _maybe_finish_teardown()'s own docstring) -- these mirror the
    # STOPPING-side confirmation tests above, applied to the STARTING
    # cleanup path instead. ---

    def test_readiness_timeout_cleanup_with_confirmed_taskkill_reaches_start_failed_latch_clear(self):
        self.manager._state = STARTING
        self.manager._readiness_timeout_message = (
            "Forge did not become available within the expected delay. "
            "A port conflict is possible but not confirmed."
        )
        self.manager._terminating_owned_process = True
        self.manager._stop_confirmed = True
        self.manager._taskkill_resolved = True
        self.manager._process = MagicMock()

        self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)

        self.assertEqual(self.manager.state, START_FAILED)
        self.assertFalse(self.manager._stop_unconfirmed)
        # The readiness cause is preserved, never silently replaced by a
        # generic Stop-shaped message.
        self.assertIn("did not become available", self.manager.last_error_message)
        self.assertNotIn("could not be confirmed fully cleaned up", self.manager.last_error_message)

    def test_readiness_timeout_cleanup_with_unconfirmed_taskkill_arms_the_latch(self):
        """
        The exact gap this mission's own review identified: the
        readiness-timeout cleanup must never silently report a clean
        teardown, and must arm the same _stop_unconfirmed latch a Stop
        would, so a later Start cannot launch a duplicate.
        """
        self.manager._state = STARTING
        self.manager._readiness_timeout_message = (
            "Forge did not become available within the expected delay. "
            "A port conflict is possible but not confirmed."
        )
        self.manager._terminating_owned_process = True
        self.manager._stop_confirmed = False
        self.manager._taskkill_resolved = True
        self.manager._process = MagicMock()

        self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)

        self.assertEqual(self.manager.state, START_FAILED)
        self.assertTrue(self.manager._stop_unconfirmed)
        message = self.manager.last_error_message
        # Both the original readiness cause AND the cleanup uncertainty
        # must be present -- never one silently replacing the other.
        self.assertIn("did not become available", message)
        self.assertIn("could not be confirmed fully cleaned up", message)

    def test_readiness_timeout_cleanup_waits_for_taskkill_before_concluding(self):
        # Same ordering hazard as the STOPPING side: the owned process
        # dying must never, by itself, resolve anything while taskkill's
        # own outcome is still unknown.
        self.manager._state = STARTING
        self.manager._readiness_timeout_message = "Forge did not become available..."
        self.manager._terminating_owned_process = True
        self.manager._stop_confirmed = False
        self.manager._taskkill_resolved = False
        self.manager._process = MagicMock()

        self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)
        self.assertEqual(self.manager.state, STARTING)  # still waiting on taskkill

        self.manager._on_taskkill_finished(0, QProcess.ExitStatus.NormalExit)
        self.assertEqual(self.manager.state, START_FAILED)
        self.assertFalse(self.manager._stop_unconfirmed)

    def test_process_crash_entirely_on_its_own_never_touches_the_latch(self):
        # No active kill was ever attempted here (_terminating_owned_
        # process stays False) -- must behave exactly as before this
        # mission's own review, untouched by the confirmation machinery.
        self.manager._state = STARTING
        self.manager._terminating_owned_process = False
        self.manager._process = MagicMock()

        self.manager._on_process_finished(1, QProcess.ExitStatus.CrashExit)

        self.assertEqual(self.manager.state, START_FAILED)
        self.assertFalse(self.manager._stop_unconfirmed)
        self.assertIn("exit_code=1", self.manager.last_error_message)

    # --- Mission 146: spontaneous death while genuinely RUNNING_OWNED,
    # no Stop ever requested (_terminating_owned_process stays False) ---

    def test_process_finished_while_running_owned_without_active_kill_reaches_start_failed(self):
        self.manager._state = RUNNING_OWNED
        self.manager._terminating_owned_process = False
        self.manager._process = MagicMock()

        self.manager._on_process_finished(1, QProcess.ExitStatus.CrashExit)

        self.assertEqual(self.manager.state, START_FAILED)
        self.assertIsNone(self.manager._process)
        self.assertIn("exit_code=1", self.manager.last_error_message)
        # Never borrows the STARTING readiness-timeout wording -- Forge
        # was fully up and running, not still becoming available.
        self.assertNotIn("becoming available", self.manager.last_error_message)

    def test_process_finished_while_running_owned_never_triggers_a_teardown(self):
        # The owned process is already dead -- there is nothing left to
        # kill, so this recovery path must never shell out to taskkill,
        # arm a terminate timer, or touch the rendezvous flags at all.
        self.manager._state = RUNNING_OWNED
        self.manager._terminating_owned_process = False
        self.manager._process = MagicMock()

        with patch.object(self.manager, "_terminate_owned_process") as terminate_mock:
            self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)

        terminate_mock.assert_not_called()
        self.assertIsNone(self.manager._taskkill_process)
        self.assertIsNone(self.manager._terminate_timer)

    def test_process_finished_during_active_teardown_is_never_reclassified_as_spontaneous_death(self):
        # A voluntary teardown already in flight (_terminating_owned_
        # process=True) must always take priority over the new
        # spontaneous-death branch, regardless of the state it happens
        # to be sitting on at that instant.
        self.manager._state = RUNNING_OWNED
        self.manager._terminating_owned_process = True
        self.manager._process = MagicMock()

        with patch.object(self.manager, "_maybe_finish_teardown") as teardown_mock:
            self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)

        teardown_mock.assert_called_once()
        self.assertTrue(self.manager._owned_process_gone)
        self.assertIsNone(self.manager._process)
        # _maybe_finish_teardown() itself is mocked out here -- this test
        # only proves the dispatch, not the rendezvous resolution, which
        # is already covered by the STOPPING-side confirmation tests.

    def test_start_after_running_owned_recovery_launches_a_genuinely_new_process(self):
        old_process = MagicMock()
        self.manager._state = RUNNING_OWNED
        self.manager._terminating_owned_process = False
        self.manager._process = old_process

        self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)
        self.assertEqual(self.manager.state, START_FAILED)

        launch = ForgeLaunchConfig(
            working_directory="C:/Forge",
            run_bat_path="C:/Forge/run.bat",
            extra_path_dirs=("C:/Forge",),
            listen_host="127.0.0.1",
            port=7860,
        )
        new_process = MagicMock()
        with patch.object(lifecycle_module, "resolve_forge_launch", return_value=launch), \
                patch.object(lifecycle_module, "ForgeEngine") as engine_cls, \
                patch.object(lifecycle_module, "QProcess", return_value=new_process):
            engine_cls.return_value.check_connection.side_effect = ForgeEngineError("not yet")
            self.manager.start("C:/Forge", "http://127.0.0.1:7860")

        self.assertEqual(self.manager.state, STARTING)
        self.assertIs(self.manager._process, new_process)
        self.assertIsNot(self.manager._process, old_process)

    def test_stop_is_a_no_op_on_external_active(self):
        self.manager._state = EXTERNAL_ACTIVE
        self.manager.stop()
        self.assertEqual(self.manager.state, EXTERNAL_ACTIVE)

    def test_stop_is_a_no_op_on_stopped(self):
        self.manager._state = STOPPED
        self.manager.stop()
        self.assertEqual(self.manager.state, STOPPED)

    # --- Stop confirmation (taskkill outcome) -- see MISSION_119.md's
    # own audit of why the owned cmd.exe exiting is never, by itself,
    # sufficient proof the real Forge server (a descendant process) is
    # also gone. ---

    def test_taskkill_success_confirms_stop(self):
        self.manager._stop_confirmed = False
        self.manager._on_taskkill_finished(0, QProcess.ExitStatus.NormalExit)
        self.assertTrue(self.manager._stop_confirmed)
        self.assertTrue(self.manager._taskkill_resolved)

    def test_taskkill_nonzero_exit_does_not_confirm_stop(self):
        self.manager._stop_confirmed = False
        self.manager._on_taskkill_finished(1, QProcess.ExitStatus.NormalExit)
        self.assertFalse(self.manager._stop_confirmed)
        self.assertTrue(self.manager._taskkill_resolved)

    def test_taskkill_failed_to_start_does_not_confirm_stop(self):
        self.manager._stop_confirmed = False
        self.manager._on_taskkill_error_occurred(QProcess.ProcessError.FailedToStart)
        self.assertFalse(self.manager._stop_confirmed)
        self.assertTrue(self.manager._taskkill_resolved)

    def test_stale_taskkill_finished_signal_is_ignored(self):
        # A real empirical test proved the owned cmd.exe's own finished
        # signal can arrive before taskkill's -- this proves the reverse
        # safety property: a taskkill signal from an *earlier* Stop
        # cycle (already superseded by a new one) must never resolve
        # the current cycle's confirmation.
        current_taskkill = MagicMock()
        self.manager._taskkill_process = current_taskkill
        stale_taskkill = MagicMock()

        with patch.object(ForgeLifecycleManager, "sender", return_value=stale_taskkill):
            self.manager._on_taskkill_finished(0, QProcess.ExitStatus.NormalExit)

        self.assertFalse(self.manager._stop_confirmed)
        self.assertFalse(self.manager._taskkill_resolved)
        self.assertIs(self.manager._taskkill_process, current_taskkill)

    # --- Mission 141: a Stop cycle's own bounded-wait timer used to
    # stay armed forever once the rendezvous resolved via taskkill --
    # since ForgeLifecycleManager lives for the whole session, that
    # timer would still fire later, landing on whatever unrelated
    # Start/Stop cycle happened to be in flight on the same instance at
    # that moment. See MISSION_141.md for the full audit. ---

    def test_maybe_finish_teardown_stops_and_clears_the_terminate_timer_once_resolved(self):
        real_timer = QTimer(self.manager)
        real_timer.setSingleShot(True)
        real_timer.timeout.connect(self.manager._on_terminate_timeout)
        real_timer.start(60_000)  # long enough to never fire during this test
        self.manager._terminate_timer = real_timer

        self.manager._state = STOPPING
        self.manager._terminating_owned_process = True
        self.manager._owned_process_gone = True
        self.manager._taskkill_resolved = True
        self.manager._stop_confirmed = True

        self.manager._maybe_finish_teardown()

        self.assertEqual(self.manager.state, STOPPED)
        self.assertIsNone(self.manager._terminate_timer)
        self.assertFalse(real_timer.isActive())

    def test_stale_terminate_timeout_signal_is_ignored(self):
        # Mirrors test_stale_taskkill_finished_signal_is_ignored above,
        # for the third rendezvous callback: a terminate-timeout signal
        # from a timer that is no longer the current one must never act.
        current_timer = MagicMock()
        self.manager._terminate_timer = current_timer
        stale_timer = MagicMock()
        self.manager._process = MagicMock()
        self.manager._taskkill_resolved = False

        with patch.object(ForgeLifecycleManager, "sender", return_value=stale_timer):
            self.manager._on_terminate_timeout()

        self.manager._process.kill.assert_not_called()
        self.assertFalse(self.manager._taskkill_resolved)
        self.assertIs(self.manager._terminate_timer, current_timer)

    def test_terminate_timeout_from_the_current_timer_is_not_treated_as_stale(self):
        # Non-regression: the guard must never block the genuine,
        # non-stale timeout it is also connected to in production.
        timer = MagicMock()
        self.manager._terminate_timer = timer
        self.manager._process = MagicMock()
        self.manager._process.state.return_value = QProcess.ProcessState.Running

        with patch.object(ForgeLifecycleManager, "sender", return_value=timer):
            self.manager._on_terminate_timeout()

        self.manager._process.kill.assert_called_once()
        self.assertTrue(self.manager._taskkill_resolved)
        self.assertIsNone(self.manager._taskkill_process)

    def test_stale_terminate_timeout_from_a_resolved_cycle_never_affects_a_later_cycle(self):
        """
        Mission 141's main regression test -- the exact cross-cycle
        scenario the audit demonstrated (MISSION_141.md section 2):

        Cycle A (Stop) resolves via taskkill well before its own
        bounded-wait timer would ever expire. Before this mission,
        nothing stopped that timer -- it stayed alive as a Qt child of
        this same, session-long manager instance. Cycle B (a brand-new,
        legitimate Start on the very same instance) never itself calls
        _terminate_owned_process(), so self._terminate_timer would still
        be pointing at cycle A's own timer object when it fires late --
        exactly the case a naive "is this the CURRENT timer" check alone
        cannot distinguish, since cycle B never rearms one of its own.

        Proven here against a real business/lifecycle effect -- cycle
        B's own process is never killed, cycle B's own state is never
        altered -- rather than merely asserting an internal flag or that
        timer.stop() was called.
        """
        # --- Cycle A: a Stop that resolves via taskkill before its own
        # real QTimer would ever fire. ---
        self.manager._state = STOPPING
        self.manager._terminating_owned_process = True
        self.manager._owned_process_gone = True  # cmd.exe already confirmed gone

        timer_a = QTimer(self.manager)
        timer_a.setSingleShot(True)
        timer_a.timeout.connect(self.manager._on_terminate_timeout)
        timer_a.start(60_000)  # long enough to never fire for real during this test
        self.manager._terminate_timer = timer_a

        taskkill_a = MagicMock()
        self.manager._taskkill_process = taskkill_a

        with patch.object(ForgeLifecycleManager, "sender", return_value=taskkill_a):
            self.manager._on_taskkill_finished(0, QProcess.ExitStatus.NormalExit)

        self.assertEqual(self.manager.state, STOPPED)
        # The critical, previously-missing guarantee: cycle A's own
        # resolution must leave no live timer behind.
        self.assertIsNone(self.manager._terminate_timer)
        self.assertFalse(timer_a.isActive())

        # --- Cycle B: a brand-new, legitimate Start on the very same
        # manager instance -- it never itself calls
        # _terminate_owned_process(), so (before this mission's fix)
        # self._terminate_timer would still be pointing at timer_a. ---
        process_b = MagicMock()
        self.manager._state = STARTING
        self.manager._process = process_b

        # Simulates timer_a firing late, exactly as Qt would dispatch it
        # if it had never been stopped -- sender() reports the real
        # timer_a object.
        with patch.object(ForgeLifecycleManager, "sender", return_value=timer_a):
            self.manager._on_terminate_timeout()

        process_b.kill.assert_not_called()
        self.assertEqual(self.manager.state, STARTING)
        self.assertIs(self.manager._process, process_b)

    def test_process_finished_while_stopping_with_confirmed_stop_reaches_stopped(self):
        self.manager._state = STOPPING
        self.manager._terminating_owned_process = True
        self.manager._stop_confirmed = True
        self.manager._taskkill_resolved = True
        self.manager._process = MagicMock()
        self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)
        self.assertEqual(self.manager.state, STOPPED)

    def test_process_finished_while_stopping_without_confirmation_never_reports_stopped(self):
        """
        The exact safety contract under review: the owned cmd.exe exiting
        must never, by itself, be reported as a clean Stop when taskkill
        never confirmed the whole tree was actually terminated (e.g. it
        failed, returned non-zero, or the bounded wait's own single-
        process kill() fallback was used instead).
        """
        self.manager._state = STOPPING
        self.manager._terminating_owned_process = True
        self.manager._stop_confirmed = False
        self.manager._taskkill_resolved = True
        self.manager._process = MagicMock()
        self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)

        self.assertNotEqual(self.manager.state, STOPPED)
        self.assertEqual(self.manager.state, START_FAILED)
        self.assertIn("not be confirmed", self.manager.last_error_message.lower())

    def test_process_finished_before_taskkill_resolved_waits_for_taskkill(self):
        """
        The exact bug this rendezvous fixes: a real empirical test showed
        the owned cmd.exe's own finished signal reliably arrives BEFORE
        taskkill's own outcome is known. Resolving STOPPING the instant
        only the owned process is confirmed gone (ignoring
        _taskkill_resolved) was confirmed to falsely report START_FAILED
        even on a real, fully successful Stop -- this proves
        _on_process_finished() alone must never conclude anything.
        """
        self.manager._state = STOPPING
        self.manager._terminating_owned_process = True
        self.manager._stop_confirmed = False
        self.manager._taskkill_resolved = False
        self.manager._process = MagicMock()

        self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)
        self.assertEqual(self.manager.state, STOPPING)  # still waiting on taskkill

        self.manager._on_taskkill_finished(0, QProcess.ExitStatus.NormalExit)
        self.assertEqual(self.manager.state, STOPPED)

    # --- Pending close ("Oui, stop Forge then close") vs. Stop
    # confirmation -- a deferred close must never resume just because
    # STOPPING resolved to *some* final state; it must resume only on a
    # confirmed clean Stop, never on an unconfirmed one. ---

    def test_pending_close_resumes_on_confirmed_stop(self):
        parent = MagicMock()
        self.manager._pending_close_widget = parent
        self.manager._state = STOPPING
        self.manager._terminating_owned_process = True
        self.manager._stop_confirmed = True
        self.manager._taskkill_resolved = True
        self.manager._process = MagicMock()

        self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)

        self.assertEqual(self.manager.state, STOPPED)
        parent.close.assert_called_once()
        self.assertIsNone(self.manager._pending_close_widget)

    def test_pending_close_never_resumes_on_taskkill_nonzero_exit(self):
        """
        Mission 119 (post-review): closing Toolkit automatically here
        would silently contradict the user's own explicit choice ("stop
        Forge, *then* close") -- a real Forge process could still be
        running. Toolkit must stay open and show an explicit error
        instead.
        """
        parent = MagicMock()
        self.manager._pending_close_widget = parent
        self.manager._state = STOPPING
        self.manager._terminating_owned_process = True
        self.manager._process = MagicMock()

        with patch("src.ui.forge_lifecycle_manager.QMessageBox") as box:
            self.manager._on_taskkill_finished(1, QProcess.ExitStatus.NormalExit)  # non-zero
            self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)

            box.critical.assert_called_once()

        self.assertEqual(self.manager.state, START_FAILED)
        parent.close.assert_not_called()
        self.assertIsNone(self.manager._pending_close_widget)

    def test_pending_close_never_resumes_when_taskkill_could_not_be_started(self):
        parent = MagicMock()
        self.manager._pending_close_widget = parent
        self.manager._state = STOPPING
        self.manager._terminating_owned_process = True
        self.manager._process = MagicMock()

        with patch("src.ui.forge_lifecycle_manager.QMessageBox") as box:
            self.manager._on_taskkill_error_occurred(QProcess.ProcessError.FailedToStart)
            self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)

            box.critical.assert_called_once()

        self.assertEqual(self.manager.state, START_FAILED)
        parent.close.assert_not_called()
        self.assertIsNone(self.manager._pending_close_widget)

    def test_pending_close_never_resumes_via_the_no_taskkill_needed_fallback_message(self):
        # Same outcome, reached through _on_terminate_timeout()'s own
        # fallback path (taskkill never resolved in time).
        parent = MagicMock()
        self.manager._pending_close_widget = parent
        self.manager._state = STOPPING
        self.manager._terminating_owned_process = True
        self.manager._process = MagicMock()
        self.manager._process.state.return_value = QProcess.ProcessState.Running

        with patch("src.ui.forge_lifecycle_manager.QMessageBox") as box:
            self.manager._on_terminate_timeout()  # taskkill never resolved
            self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)

            box.critical.assert_called_once()

        self.assertEqual(self.manager.state, START_FAILED)
        parent.close.assert_not_called()

    def test_no_pending_close_widget_means_no_dialog_on_unconfirmed_stop(self):
        # Stop invoked directly from Settings (never through the close
        # guard) must never pop an unrelated close-failure dialog.
        self.manager._state = STOPPING
        self.manager._terminating_owned_process = True
        self.manager._taskkill_resolved = True
        self.manager._stop_confirmed = False
        self.manager._process = MagicMock()

        with patch("src.ui.forge_lifecycle_manager.QMessageBox") as box:
            self.manager._on_process_finished(0, QProcess.ExitStatus.NormalExit)
            box.critical.assert_not_called()

        self.assertEqual(self.manager.state, START_FAILED)

    # --- Start() after an unconfirmed Stop -- must never blindly launch
    # a duplicate if the surviving descendant is already reachable. ---

    # --- Start() after an unconfirmed Stop -- the _stop_unconfirmed
    # latch (see __init__'s own docstring for the exact contract). ---

    def _make_launch(self):
        return ForgeLaunchConfig(
            working_directory="C:/Forge",
            run_bat_path="C:/Forge/run.bat",
            extra_path_dirs=("C:/Forge", "C:/Forge/webui"),
            listen_host="127.0.0.1",
            port=7860,
        )

    def test_start_after_unconfirmed_stop_detects_a_still_reachable_survivor_as_external_active(self):
        self.manager._state = START_FAILED
        self.manager._stop_unconfirmed = True

        with patch.object(lifecycle_module, "resolve_forge_launch", return_value=self._make_launch()), \
                patch.object(lifecycle_module, "ForgeEngine") as engine_cls, \
                patch.object(lifecycle_module, "QProcess") as process_cls:
            engine_cls.return_value.check_connection.return_value = True  # survivor answers HTTP

            self.manager.start("C:/Forge", "http://127.0.0.1:7860")

            process_cls.assert_not_called()  # never launches a second instance

        self.assertEqual(self.manager.state, EXTERNAL_ACTIVE)
        # The backend is now identified/reachable -- the uncertainty an
        # earlier unconfirmed Stop left behind no longer applies.
        self.assertFalse(self.manager._stop_unconfirmed)

    def test_start_after_unconfirmed_stop_is_refused_while_survivor_not_yet_reachable(self):
        """
        The exact gap under review: a real descendant can be alive but
        not yet answering HTTP (still loading). start()'s pre-check alone
        cannot distinguish this from "genuinely nothing left running" --
        the latch must block launching a second real instance here.
        """
        self.manager._state = START_FAILED
        self.manager._stop_unconfirmed = True

        with patch.object(lifecycle_module, "resolve_forge_launch", return_value=self._make_launch()), \
                patch.object(lifecycle_module, "ForgeEngine") as engine_cls, \
                patch.object(lifecycle_module, "QProcess") as process_cls:
            engine_cls.return_value.check_connection.side_effect = ForgeEngineError("not yet")

            self.manager.start("C:/Forge", "http://127.0.0.1:7860")

            process_cls.assert_not_called()  # never launches a second cmd.exe

        self.assertEqual(self.manager.state, START_FAILED)
        self.assertTrue(self.manager._stop_unconfirmed)  # latch stays armed
        message = self.manager.last_error_message.lower()
        self.assertIn("not be confirmed", message)
        self.assertIn("blocked", message)

    def test_start_after_a_confirmed_stop_is_not_blocked(self):
        # The latch must never linger after a Stop that genuinely
        # succeeded -- a normal Start afterward proceeds exactly as
        # before this mission's own safety review.
        self.manager._state = STOPPED
        self.manager._stop_unconfirmed = False
        mock_process = MagicMock()

        with patch.object(lifecycle_module, "resolve_forge_launch", return_value=self._make_launch()), \
                patch.object(lifecycle_module, "ForgeEngine") as engine_cls, \
                patch.object(lifecycle_module, "QProcess", return_value=mock_process):
            engine_cls.return_value.check_connection.side_effect = [
                ForgeEngineError("not yet"),  # pre-Start check -- must fail so Start proceeds
                True,  # readiness worker's first poll -- succeeds immediately
            ]
            self.manager.start("C:/Forge", "http://127.0.0.1:7860")

        mock_process.start.assert_called_once_with("cmd.exe", ["/c", "C:/Forge/run.bat"])

    def test_fresh_manager_never_has_the_latch_armed(self):
        # No persistence of any kind -- a brand new instance (e.g. after
        # a Toolkit restart) always starts with the protection absent.
        fresh_manager = ForgeLifecycleManager()
        self.assertFalse(fresh_manager._stop_unconfirmed)

    def test_start_is_a_no_op_while_already_starting(self):
        with patch.object(lifecycle_module, "resolve_forge_launch") as resolve_mock:
            self.manager._state = STARTING
            self.manager.start("p", "http://127.0.0.1:7860")
            resolve_mock.assert_not_called()

    def test_start_is_a_no_op_while_running_owned(self):
        with patch.object(lifecycle_module, "resolve_forge_launch") as resolve_mock:
            self.manager._state = RUNNING_OWNED
            self.manager.start("p", "http://127.0.0.1:7860")
            resolve_mock.assert_not_called()

    # --- confirm_safe_to_close() ---

    def test_confirm_safe_to_close_true_when_stopped(self):
        self.manager._state = STOPPED
        self.assertTrue(self.manager.confirm_safe_to_close(MagicMock()))

    def test_confirm_safe_to_close_true_when_external_active_no_dialog(self):
        self.manager._state = EXTERNAL_ACTIVE
        with patch("src.ui.forge_lifecycle_manager.QMessageBox") as box:
            self.assertTrue(self.manager.confirm_safe_to_close(MagicMock()))
            box.question.assert_not_called()
            box.warning.assert_not_called()

    def test_confirm_safe_to_close_true_when_start_failed(self):
        self.manager._state = START_FAILED
        self.assertTrue(self.manager.confirm_safe_to_close(MagicMock()))

    def test_confirm_safe_to_close_blocks_during_starting(self):
        self.manager._state = STARTING
        with patch("src.ui.forge_lifecycle_manager.QMessageBox") as box:
            self.assertFalse(self.manager.confirm_safe_to_close(MagicMock()))
            box.warning.assert_called_once()

    def test_confirm_safe_to_close_blocks_during_stopping(self):
        self.manager._state = STOPPING
        with patch("src.ui.forge_lifecycle_manager.QMessageBox") as box:
            self.assertFalse(self.manager.confirm_safe_to_close(MagicMock()))
            box.warning.assert_called_once()

    def test_confirm_safe_to_close_running_owned_no_leaves_forge_running(self):
        self.manager._state = RUNNING_OWNED
        parent = MagicMock()
        with patch("src.ui.forge_lifecycle_manager.QMessageBox") as box:
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
        with patch("src.ui.forge_lifecycle_manager.QMessageBox") as box:
            box.Yes, box.No = QMessageBox.Yes, QMessageBox.No
            box.question.return_value = QMessageBox.Yes
            with patch.object(self.manager, "stop") as stop_mock:
                result = self.manager.confirm_safe_to_close(parent)

        self.assertFalse(result)
        stop_mock.assert_called_once()
        parent.close.assert_not_called()  # not yet -- only once Stop really finishes

        self.manager._state = STOPPED
        self.manager._resume_close_if_pending()
        parent.close.assert_called_once()

    def test_confirm_safe_to_close_does_not_ask_twice_after_resumed_close(self):
        self.manager._state = RUNNING_OWNED
        parent = MagicMock()
        with patch("src.ui.forge_lifecycle_manager.QMessageBox") as box:
            box.Yes, box.No = QMessageBox.Yes, QMessageBox.No
            box.question.return_value = QMessageBox.Yes
            with patch.object(self.manager, "stop"):
                self.manager.confirm_safe_to_close(parent)

            self.manager._state = STOPPED
            self.manager._resume_close_if_pending()

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
        with patch("src.ui.forge_lifecycle_manager.QMessageBox") as box, \
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
        with patch("src.ui.forge_lifecycle_manager.QMessageBox") as box, \
                patch.object(self.manager, "_terminate_owned_process") as terminate_mock:
            box.Yes, box.No = QMessageBox.Yes, QMessageBox.No
            box.question.side_effect = self._yes_after_dying_during_dialog()
            self.manager.confirm_safe_to_close(parent)

        terminate_mock.assert_not_called()
        self.assertIsNone(self.manager._taskkill_process)
        self.assertIsNone(self.manager._terminate_timer)
        self.assertFalse(self.manager._terminating_owned_process)

    def test_confirm_safe_to_close_process_died_during_dialog_leaves_no_stale_pending_close_for_a_later_cycle(self):
        self.manager._state = RUNNING_OWNED
        parent = MagicMock()
        with patch("src.ui.forge_lifecycle_manager.QMessageBox") as box:
            box.Yes, box.No = QMessageBox.Yes, QMessageBox.No
            box.question.side_effect = self._yes_after_dying_during_dialog()
            self.manager.confirm_safe_to_close(parent)

        self.assertIsNone(self.manager._pending_close_widget)

        # A later, completely unrelated Stop cycle resolving on this same
        # session-long instance must never resume a close nobody asked
        # for -- there is no stale widget reference left to resume.
        self.manager._owned_process_gone = True
        self.manager._taskkill_resolved = True
        self.manager._stop_confirmed = True
        self.manager._state = STOPPING
        self.manager._maybe_finish_teardown()

        self.assertEqual(self.manager.state, STOPPED)
        parent.close.assert_not_called()


def _pid_is_alive(pid: int) -> bool:
    """
    Stdlib-only (subprocess + the real tasklist.exe), no wmic/psutil
    dependency. An earlier ctypes-based OpenProcess() implementation was
    empirically found unreliable here -- it reported a genuinely-dead
    PID (independently confirmed gone via a real `tasklist` call) as
    still alive, likely a 64-bit HANDLE/ctypes default-restype truncation
    issue never fully chased down. `tasklist` is the ground truth the
    discrepancy was verified against, so it is used directly instead.
    """
    import subprocess

    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
        capture_output=True, text=True,
    )
    for line in result.stdout.splitlines():
        if str(pid) in line.split():
            return True
    return False


class ForgeLifecycleManagerStopConfirmationTest(unittest.TestCase):
    """
    Mission 119 (post-review): end-to-end proof, against a real
    cmd.exe -> python.exe tree, of the exact danger the architect's
    review flagged -- if taskkill cannot do its job, the owned cmd.exe
    can still end up dead (via _on_terminate_timeout()'s own single-
    process kill() fallback) while the real Forge server (python.exe)
    survives as an orphan. Without _stop_confirmed, that scenario would
    previously have been reported as a clean STOPPED.

    The fake run.bat here wraps the shared fake process double
    (_fake_comfyui_process.py) in a tiny inline launcher that writes its
    own real PID to a file first -- the only way to identify the exact
    descendant PID to check afterward, without adding a psutil/wmic
    dependency anywhere.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        self._pid_file = Path(self.tmp_dir) / "descendant.pid"
        launcher_script = Path(self.tmp_dir) / "launch_with_pidfile.py"
        launcher_script.write_text(
            "import os, runpy\n"
            f"open(r'{self._pid_file}', 'w').write(str(os.getpid()))\n"
            f"runpy.run_path(r'{_FAKE_PROCESS_SCRIPT}', run_name='__main__')\n"
        )

        fake_run_bat = Path(self.tmp_dir) / "run.bat"
        fake_run_bat.write_text(
            f'@echo off\n"{sys.executable}" "{launcher_script}"\n'
        )

        self._launch_config = ForgeLaunchConfig(
            working_directory=self.tmp_dir,
            run_bat_path=str(fake_run_bat),
            extra_path_dirs=(),
            listen_host="127.0.0.1",
            port=7860,
        )
        self._resolve_patch = patch.object(
            lifecycle_module, "resolve_forge_launch", return_value=self._launch_config
        )
        self._resolve_patch.start()
        self.addCleanup(self._resolve_patch.stop)

        self._fake_engine = MagicMock()
        self._engine_patch = patch.object(
            lifecycle_module, "ForgeEngine", return_value=self._fake_engine
        )
        self._engine_patch.start()
        self.addCleanup(self._engine_patch.stop)

        self._timing_patches = [
            patch.object(lifecycle_module, "READINESS_BUDGET_SECONDS", 0.5),
            patch.object(lifecycle_module, "READINESS_POLL_INTERVAL_SECONDS", 0.05),
            patch.object(lifecycle_module, "READINESS_ATTEMPT_TIMEOUT_SECONDS", 0.05),
            patch.object(lifecycle_module, "TERMINATE_TIMEOUT_SECONDS", 1.0),
        ]
        for p in self._timing_patches:
            p.start()
            self.addCleanup(p.stop)

        self.manager = ForgeLifecycleManager()
        self._survivor_pid = None

    def tearDown(self):
        # This test's own point is to leave a real descendant alive on
        # purpose -- it alone is responsible for actually killing it,
        # regardless of pass/fail, so no real process is ever leaked.
        if self._survivor_pid is not None and _pid_is_alive(self._survivor_pid):
            import subprocess
            subprocess.run(
                ["taskkill", "/PID", str(self._survivor_pid), "/T", "/F"],
                capture_output=True,
            )
        if self.manager._process is not None and self.manager._process.state() != QProcess.ProcessState.NotRunning:
            self.manager._process.kill()
            self.manager._process.waitForFinished(2000)

    def test_taskkill_unavailable_leaves_descendant_alive_and_reports_unconfirmed(self):
        # Force a real, deterministic "taskkill could not even be
        # started" -- a genuine QProcess.errorOccurred(FailedToStart)
        # against a real owned tree, never simulated/mocked away.
        with patch.object(lifecycle_module, "TASKKILL_EXECUTABLE", "definitely_not_a_real_taskkill_binary.exe"):
            self._fake_engine.check_connection.side_effect = [
                ForgeEngineError("not yet"),  # pre-Start check
                True,  # readiness worker's first poll -- succeeds immediately
                ForgeEngineError("not yet"),  # retried start()'s own pre-check below
            ]
            self.manager.start("fake-forge-path", "http://127.0.0.1:7860")
            self.assertTrue(_pump_until(lambda: self.manager.state == RUNNING_OWNED))

            self.assertTrue(_pump_until(lambda: self._pid_file.exists(), timeout=5.0))
            descendant_pid = int(self._pid_file.read_text().strip())
            self._survivor_pid = descendant_pid
            self.assertTrue(
                _pid_is_alive(descendant_pid), "expected the real fake-process descendant to be alive"
            )

            self.manager.stop()
            self.assertEqual(self.manager.state, STOPPING)

            # _on_terminate_timeout()'s single-process kill() fallback
            # brings the owned cmd.exe down -- but must never be
            # reported as a clean Stop.
            self.assertTrue(_pump_until(lambda: self.manager.state == START_FAILED, timeout=10.0))
            self.assertIn("not be confirmed", self.manager.last_error_message.lower())
            self.assertIsNone(self.manager._process)

            # The exact danger this fix guards against, proven for
            # real: the owned cmd.exe is genuinely gone, yet its real
            # python.exe descendant -- never reached by a single-
            # process kill() -- is still alive.
            self.assertTrue(
                _pid_is_alive(descendant_pid),
                "expected the descendant to survive an unavailable taskkill -- "
                "if this fails, the fallback kill() started reaching "
                "descendants and this test (and its own rationale) needs "
                "revisiting, not silently loosening.",
            )

            # The exact scenario under review: retrying Start while the
            # real survivor is alive but not yet HTTP-ready (the fake
            # process never serves HTTP at all, so check_connection()
            # keeps failing here exactly like a real Forge server still
            # loading would) must never launch a second real cmd.exe.
            self.manager.start("fake-forge-path", "http://127.0.0.1:7860")

            self.assertEqual(self.manager.state, START_FAILED)
            self.assertIsNone(self.manager._process)  # no second cmd.exe owned
            self.assertIn("blocked", self.manager.last_error_message.lower())

            # The original descendant is untouched -- still the same
            # single survivor, never joined by a second real instance.
            self.assertEqual(int(self._pid_file.read_text().strip()), descendant_pid)
            self.assertTrue(_pid_is_alive(descendant_pid))

    def test_pending_close_never_resumes_while_a_real_descendant_survives(self):
        """
        Mission 119 (post-review): end-to-end proof of the exact
        MainWindow scenario the architect's review described -- Forge
        RUNNING_OWNED, the user closes Toolkit, answers "Oui, stop Forge
        then close", taskkill cannot do its job, the owned cmd.exe dies
        anyway (fallback kill()) while the real python.exe descendant
        survives. Toolkit must never close itself in this situation.
        """
        with patch.object(lifecycle_module, "TASKKILL_EXECUTABLE", "definitely_not_a_real_taskkill_binary.exe"), \
                patch("src.ui.forge_lifecycle_manager.QMessageBox") as box:
            self._fake_engine.check_connection.side_effect = [ForgeEngineError("not yet"), True]
            self.manager.start("fake-forge-path", "http://127.0.0.1:7860")
            self.assertTrue(_pump_until(lambda: self.manager.state == RUNNING_OWNED))

            self.assertTrue(_pump_until(lambda: self._pid_file.exists(), timeout=5.0))
            descendant_pid = int(self._pid_file.read_text().strip())
            self._survivor_pid = descendant_pid

            # Simulates confirm_safe_to_close()'s own "Oui" branch --
            # never a second QMessageBox.question mock here, since this
            # test is only about what happens once Stop resolves, not
            # about the confirmation dialog itself (already covered by
            # ForgeLifecycleManagerGuardTest's confirm_safe_to_close()
            # tests).
            parent_widget = MagicMock()
            self.manager._pending_close_widget = parent_widget
            self.manager.stop()

            self.assertTrue(_pump_until(lambda: self.manager.state == START_FAILED, timeout=10.0))

            # The real point of this test: Toolkit is never told to
            # close itself while the descendant could still be alive --
            # an explicit error is shown instead.
            parent_widget.close.assert_not_called()
            box.critical.assert_called_once()
            self.assertIsNone(self.manager._pending_close_widget)
            self.assertTrue(_pid_is_alive(descendant_pid))


class ForgeLifecycleManagerReadinessTimeoutCleanupConfirmationTest(unittest.TestCase):
    """
    Mission 119 (post-review): the readiness-timeout Start-failure
    cleanup shares the exact same taskkill-based tree termination as an
    explicit Stop -- _terminate_owned_process()/_maybe_finish_teardown()
    are the single, shared implementation for both -- and therefore the
    exact same ownership hazard applies. This class exercises that
    shared machinery from the readiness-timeout caller specifically,
    against a real cmd.exe -> python.exe tree, mirroring
    ForgeLifecycleManagerStopConfirmationTest above (which exercises it
    from the explicit-Stop caller).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        self._pid_file = Path(self.tmp_dir) / "descendant.pid"
        launcher_script = Path(self.tmp_dir) / "launch_with_pidfile.py"
        launcher_script.write_text(
            "import os, runpy\n"
            f"open(r'{self._pid_file}', 'w').write(str(os.getpid()))\n"
            f"runpy.run_path(r'{_FAKE_PROCESS_SCRIPT}', run_name='__main__')\n"
        )

        fake_run_bat = Path(self.tmp_dir) / "run.bat"
        fake_run_bat.write_text(
            f'@echo off\n"{sys.executable}" "{launcher_script}"\n'
        )

        self._launch_config = ForgeLaunchConfig(
            working_directory=self.tmp_dir,
            run_bat_path=str(fake_run_bat),
            extra_path_dirs=(),
            listen_host="127.0.0.1",
            port=7860,
        )
        self._resolve_patch = patch.object(
            lifecycle_module, "resolve_forge_launch", return_value=self._launch_config
        )
        self._resolve_patch.start()
        self.addCleanup(self._resolve_patch.stop)

        self._fake_engine = MagicMock()
        self._engine_patch = patch.object(
            lifecycle_module, "ForgeEngine", return_value=self._fake_engine
        )
        self._engine_patch.start()
        self.addCleanup(self._engine_patch.stop)

        self._timing_patches = [
            patch.object(lifecycle_module, "READINESS_BUDGET_SECONDS", 0.3),
            patch.object(lifecycle_module, "READINESS_POLL_INTERVAL_SECONDS", 0.05),
            patch.object(lifecycle_module, "READINESS_ATTEMPT_TIMEOUT_SECONDS", 0.05),
            patch.object(lifecycle_module, "TERMINATE_TIMEOUT_SECONDS", 1.0),
        ]
        for p in self._timing_patches:
            p.start()
            self.addCleanup(p.stop)

        self.manager = ForgeLifecycleManager()
        self._survivor_pid = None

    def tearDown(self):
        if self._survivor_pid is not None and _pid_is_alive(self._survivor_pid):
            import subprocess
            subprocess.run(
                ["taskkill", "/PID", str(self._survivor_pid), "/T", "/F"],
                capture_output=True,
            )
        if self.manager._process is not None and self.manager._process.state() != QProcess.ProcessState.NotRunning:
            self.manager._process.kill()
            self.manager._process.waitForFinished(2000)

    def test_readiness_timeout_with_taskkill_success_confirms_cleanup(self):
        # Never HTTP-ready -- the readiness budget genuinely expires and
        # drives the real cleanup path, exactly like a real Forge
        # instance stuck mid-startup would.
        self._fake_engine.check_connection.side_effect = ForgeEngineError("not yet")

        self.manager.start("fake-forge-path", "http://127.0.0.1:7860")
        self.assertTrue(_pump_until(lambda: self.manager.state == STARTING))

        self.assertTrue(_pump_until(lambda: self._pid_file.exists(), timeout=5.0))
        descendant_pid = int(self._pid_file.read_text().strip())
        self._survivor_pid = descendant_pid

        self.assertTrue(_pump_until(lambda: self.manager.state == START_FAILED, timeout=10.0))

        self.assertFalse(self.manager._stop_unconfirmed)
        self.assertIn("did not become available", self.manager.last_error_message)
        self.assertIsNone(self.manager._process)
        # taskkill genuinely tore down the whole real tree. Checked
        # immediately, once, rather than polled over a window: Windows
        # aggressively recycles PIDs, so re-checking the *same* PID
        # number after a longer delay risks a false "still alive"
        # positive once some unrelated later process reuses it -- a
        # real false failure observed while developing this exact test.
        self.assertFalse(_pid_is_alive(descendant_pid))

    def test_readiness_timeout_with_taskkill_unavailable_leaves_descendant_alive_and_blocks_start(self):
        """
        Covers items 1 and 4 of the review's own test list in one real
        scenario: a genuine surviving descendant, not yet HTTP-ready,
        after a readiness-timeout cleanup whose taskkill could not run.
        """
        with patch.object(lifecycle_module, "TASKKILL_EXECUTABLE", "definitely_not_a_real_taskkill_binary.exe"):
            self._fake_engine.check_connection.side_effect = ForgeEngineError("not yet")

            self.manager.start("fake-forge-path", "http://127.0.0.1:7860")
            self.assertTrue(_pump_until(lambda: self.manager.state == STARTING))

            self.assertTrue(_pump_until(lambda: self._pid_file.exists(), timeout=5.0))
            descendant_pid = int(self._pid_file.read_text().strip())
            self._survivor_pid = descendant_pid

            self.assertTrue(_pump_until(lambda: self.manager.state == START_FAILED, timeout=10.0))

            # Cleanup could not be confirmed -- the latch must be armed,
            # and the real descendant genuinely survives the fallback
            # kill() (which only ever reaches the owned cmd.exe).
            self.assertTrue(self.manager._stop_unconfirmed)
            self.assertIn("could not be confirmed fully cleaned up", self.manager.last_error_message)
            self.assertIsNone(self.manager._process)
            self.assertTrue(_pid_is_alive(descendant_pid))

            # A retried Start must be blocked outright -- no second real
            # cmd.exe, since the survivor still is not HTTP-ready.
            self.manager.start("fake-forge-path", "http://127.0.0.1:7860")

            self.assertEqual(self.manager.state, START_FAILED)
            self.assertIn("blocked", self.manager.last_error_message.lower())
            self.assertIsNone(self.manager._process)
            self.assertEqual(int(self._pid_file.read_text().strip()), descendant_pid)
            self.assertTrue(_pid_is_alive(descendant_pid))

    def test_survivor_becoming_reachable_after_readiness_timeout_clears_the_latch(self):
        # Same latch, regardless of which caller (Stop or readiness-
        # timeout cleanup) armed it -- once the survivor is confirmed
        # reachable, start() must detect EXTERNAL_ACTIVE and clear it,
        # never launch a second instance.
        self.manager._state = START_FAILED
        self.manager._stop_unconfirmed = True

        with patch.object(lifecycle_module, "QProcess") as process_cls:
            self._fake_engine.check_connection.return_value = True  # now reachable

            self.manager.start("fake-forge-path", "http://127.0.0.1:7860")

            process_cls.assert_not_called()

        self.assertEqual(self.manager.state, EXTERNAL_ACTIVE)
        self.assertFalse(self.manager._stop_unconfirmed)


class _EngineScript:
    """
    Mission 170: callable side_effect for the mocked engine -- one action per
    call, the last one repeating. Controlled waits use a releasable Event
    (never a free sleep), so the test cleanup can always free them.
    Actions: ("ok",) | ("raise", exc) | ("wait", seconds, then_action) |
    ("until", predicate, then_action) -- waits (bounded to 5s) until predicate()
    is true, so a real descendant has certainly written its pid file first.
    """

    def __init__(self, release, actions):
        self._release = release
        self._actions = list(actions)
        self.calls = 0

    def __call__(self, *args, **kwargs):
        index = self.calls
        self.calls += 1
        action = self._actions[min(index, len(self._actions) - 1)]
        while action[0] in ("wait", "until"):
            if action[0] == "wait":
                self._release.wait(action[1])
            else:
                deadline = time.monotonic() + 5.0
                while not action[1]() and time.monotonic() < deadline:
                    self._release.wait(0.02)
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
        forge_lifecycle_status_label=MagicMock(),
        forge_lifecycle_manager=manager,
        forge_start_button=MagicMock(),
        forge_stop_button=MagicMock(),
    )
    SettingsPage._on_forge_lifecycle_state_changed(stub, manager.state)
    return (
        stub.forge_start_button.setEnabled.call_args[0][0],
        stub.forge_stop_button.setEnabled.call_args[0][0],
    )


class _LifecycleCase(unittest.TestCase):
    """
    Mission 170 fixture: a real ForgeLifecycleManager, a real cmd.exe -> python.exe
    tree against the existing fake process double (kept ALIVE until the manager or
    the cleanup ends it), a mocked engine, short timings. The fake descendant
    records its pid in self._pid_file.

    Cleanup contract, valid even on an implementation that loses the terminal
    signal: every (worker, thread) pair is recorded right after each
    _start_readiness_worker() call (before a later start() could replace it);
    controlled waits are released; cancel() then quit() are requested and wait()
    is checked with a bounded delay -- a thread still active is a cleanup failure,
    kept referenced, never destroyed, never terminate()d. Only the QProcess objects
    this test's manager created (and, while such a QProcess is still running, its
    own tree through taskkill /PID <its pid> /T /F) and the descendant recorded in
    this test's pid file are ever terminated.
    """

    quiet_logs = True

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        self._pid_file = Path(self.tmp_dir) / "descendant.pid"
        launcher_script = Path(self.tmp_dir) / "launch_with_pidfile.py"
        launcher_script.write_text(
            "import os, runpy\n"
            f"open(r'{self._pid_file}', 'w').write(str(os.getpid()))\n"
            f"runpy.run_path(r'{_FAKE_PROCESS_SCRIPT}', run_name='__main__')\n"
        )
        self._launcher_script = launcher_script
        fake_run_bat = Path(self.tmp_dir) / "run.bat"
        fake_run_bat.write_text(f'@echo off\n"{sys.executable}" "{launcher_script}"\n')

        self._launch_config = ForgeLaunchConfig(
            working_directory=self.tmp_dir,
            run_bat_path=str(fake_run_bat),
            extra_path_dirs=(),
            listen_host="127.0.0.1",
            port=7860,
        )
        self._fake_engine = MagicMock()
        patches = [
            patch.object(lifecycle_module, "resolve_forge_launch", return_value=self._launch_config),
            patch.object(lifecycle_module, "ForgeEngine", return_value=self._fake_engine),
            patch.object(lifecycle_module, "READINESS_BUDGET_SECONDS", 0.5),
            patch.object(lifecycle_module, "READINESS_POLL_INTERVAL_SECONDS", 0.05),
            patch.object(lifecycle_module, "READINESS_ATTEMPT_TIMEOUT_SECONDS", 0.05),
            patch.object(lifecycle_module, "TERMINATE_TIMEOUT_SECONDS", 2.0),
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

        self.manager = ForgeLifecycleManager()
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
        import subprocess

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
            if not isinstance(process, QProcess):
                continue  # a mocked QProcess (controlled-double tests): nothing real to terminate
            try:
                if process.state() != QProcess.ProcessState.NotRunning:
                    pid = process.processId()
                    if pid:  # the owned cmd.exe is still running, so this pid is still ours
                        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=15)
                    process.kill()
                    if not process.waitForFinished(3000) and process.state() != QProcess.ProcessState.NotRunning:
                        failures.append("an owned test process is still running")
            except RuntimeError:
                pass
        failures.extend(self._terminate_recorded_descendant())
        if failures:
            raise AssertionError("; ".join(failures))

    @staticmethod
    def _command_line_of(pid):
        """Command line of `pid` through Windows CIM (stdlib subprocess only), or None if it cannot be read."""
        import subprocess

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                 "(Get-CimInstance Win32_Process -Filter 'ProcessId=%d').CommandLine" % pid],
                capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return result.stdout.strip() if result.returncode == 0 else None

    def _terminate_recorded_descendant(self):
        """
        Terminates the descendant this test's own launcher recorded in the pid file, and VERIFIES it is gone.
        A pid alone is never trusted (Windows recycles pids): the process is only touched if its command
        line carries this test's own launcher script path. Returns the list of cleanup failures.
        """
        import subprocess

        try:
            pid = int(self._pid_file.read_text().strip())
        except (OSError, ValueError):
            return []  # never written (or unreadable): no descendant was recorded
        if not _pid_is_alive(pid):
            return []
        launcher = str(self._launcher_script)
        command_line = self._command_line_of(pid)
        if command_line is None:
            return ["descendant pid %d is alive and its identity could not be established: it was not terminated" % pid]
        if launcher not in command_line:
            return []  # alive but not ours: the pid was recycled after our descendant exited -- never touched
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=15)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if not _pid_is_alive(pid):
                return []
            time.sleep(0.2)
        command_line = self._command_line_of(pid)
        if command_line is not None and launcher not in command_line:
            return []  # recycled by an unrelated process after our descendant ended
        return ["descendant pid %d is still alive 5s after taskkill (identity %s)" % (pid, "unknown" if command_line is None else "confirmed")]

    def script(self, actions):
        script = _EngineScript(self.release, actions)
        self._fake_engine.check_connection.side_effect = script
        return script

    def descendant_pid_written(self):
        # exists() alone is not enough: the file is created empty before the pid is written.
        try:
            return self._pid_file.read_text().strip().isdigit()
        except OSError:
            return False

    def start(self):
        self.manager.start("fake-forge-path", "http://127.0.0.1:7860")

    def wait_for_state(self, state, timeout=8.0):
        reached = _pump_until(lambda: self.manager.state == state, timeout=timeout)
        self.assertTrue(
            reached,
            "state stuck at %r (waiting for %r), states seen: %r, last message: %r"
            % (self.manager.state, state, self.states, self.manager.last_error_message),
        )

    def assert_owned_process_ended_and_thread_cleaned(self):
        self.assertTrue(self._processes, "an owned process must have been created")
        self.assertTrue(
            _pump_until(lambda: all(p.state() == QProcess.ProcessState.NotRunning for p in self._processes), timeout=8.0),
            "the owned process must no longer be running",
        )
        self.assertTrue(
            _pump_until(lambda: self.manager._readiness_thread is None, timeout=5.0),
            "the readiness thread must have ended and been cleaned up",
        )


class ForgeLifecycleManagerUnexpectedFailureRegressionTest(_LifecycleCase):
    """
    Behavior-only proofs of the Mission 170 defect: an exception outside the
    engine's own error during polling used to lose the terminal signal and leave
    the lifecycle in STARTING, with Start/Stop disabled and the close refused.
    Nothing here reads a new symbol: they fail on the previous implementation by
    assertion.
    """

    def test_unexpected_exception_during_polling_reaches_start_failed_and_cleans_up(self):
        self.script([_raise(ForgeEngineError("not yet")), _raise(UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"))])

        self.start()
        self.wait_for_state(START_FAILED)

        self.assert_owned_process_ended_and_thread_cleaned()
        self.assertEqual(self.states, [STARTING, START_FAILED])

    def test_after_the_failure_the_user_commands_and_the_close_guard_are_available(self):
        self.script([_raise(ForgeEngineError("not yet")), _raise(RuntimeError("boom"))])

        self.start()
        self.wait_for_state(START_FAILED)

        self.assertEqual(_ui_commands(self.manager), (True, False))
        with patch.object(lifecycle_module, "QMessageBox") as box:
            self.assertTrue(self.manager.confirm_safe_to_close(None))
        box.warning.assert_not_called()  # START_FAILED without a process never blocks the close
        box.question.assert_not_called()

    def test_a_new_start_after_the_failure_follows_the_latch_left_by_the_real_cleanup(self):
        # Real cmd.exe -> python.exe tree. The _stop_unconfirmed latch is NEVER assigned here: it is whatever
        # the real taskkill /T rendezvous decided, and the second start() must respect it. taskkill /T can
        # legitimately fail to confirm a teardown (a child exiting while it walks the tree), so both
        # outcomes are valid and each one has its own contract below. The deterministic confirmed and
        # unconfirmed sequences are proved with controlled doubles in
        # ForgeLifecycleManagerFailureRestartWithControlledRendezvousTest.
        self.script([_raise(ForgeEngineError("not yet")), _raise(RuntimeError("boom"))])
        self.start()
        self.wait_for_state(START_FAILED)
        failed_process = self._processes[0]
        cleanup_was_confirmed = not self.manager._stop_unconfirmed  # observed, never forced

        self.script([_raise(ForgeEngineError("not yet")), _ok()])
        self.start()

        if not cleanup_was_confirmed:
            # The safety latch refuses a second launch while a descendant could still be alive.
            self.assertEqual(self.manager.state, START_FAILED)
            self.assertIn("blocked", self.manager.last_error_message.lower())
            self.assertEqual(self._processes, [failed_process], "no second process may be created")
            return

        self.wait_for_state(RUNNING_OWNED)
        self.assertIsNot(self.manager._process, failed_process)
        # A RUNNING_OWNED process is still protected by the existing confirmation.
        with patch.object(lifecycle_module, "QMessageBox") as box:
            box.Yes, box.No = QMessageBox.Yes, QMessageBox.No
            box.question.return_value = QMessageBox.No
            self.assertTrue(self.manager.confirm_safe_to_close(None))
        box.question.assert_called_once()
        self.assertNotEqual(self.manager._process.state(), QProcess.ProcessState.NotRunning)
        # No final stop() here: the tree is ended by the fixture's verified cooperative cleanup.

    def test_stop_during_a_blocking_attempt_that_then_raises_resolves_the_stop_and_cleans_the_thread(self):
        engine_script = self.script([_raise(ForgeEngineError("not yet")), _wait(0.4, _raise(RuntimeError("late boom")))])

        self.start()
        self.assertTrue(_pump_until(lambda: engine_script.calls >= 2, timeout=3.0), "the polling attempt must be in flight")
        self.manager.stop()
        self.assertEqual(self.manager.state, STOPPING)

        # The Stop must resolve. taskkill /T either confirms it (STOPPED) or not (START_FAILED): both are
        # outcomes of the existing rendezvous, and each one is checked against its own contract -- any
        # other failure is not accepted.
        self.assertTrue(
            _pump_until(lambda: self.manager.state in (STOPPED, START_FAILED), timeout=10.0),
            "the Stop must resolve, states seen: %r" % (self.states,),
        )
        if self.manager.state == STOPPED:
            self.assertFalse(self.manager._stop_unconfirmed)
            self.assertEqual(self.states, [STARTING, STOPPING, STOPPED])
        else:
            self.assertTrue(self.manager._stop_unconfirmed)
            self.assertIn("could not be confirmed fully stopped", self.manager.last_error_message)
            self.assertEqual(self.states, [STARTING, STOPPING, START_FAILED])
        self.assertTrue(
            _pump_until(lambda: self.manager._readiness_thread is None, timeout=5.0),
            "the readiness thread must end once the blocked attempt returns",
        )

    def test_transient_http_errors_followed_by_success_reach_running_owned(self):
        engine_script = self.script([
            _raise(ForgeEngineError("not yet")),  # pre-start check
            _raise(http.client.IncompleteRead(b"ab", 10)),
            _raise(http.client.BadStatusLine("garbage")),
            _ok(),
        ])

        self.start()
        self.wait_for_state(RUNNING_OWNED)

        self.assertEqual(engine_script.calls, 4)
        self.assertTrue(_pump_until(lambda: self.manager._readiness_thread is None, timeout=5.0))
        # The tree is ended by the fixture's cooperative cleanup (see the note above on taskkill /T).

    def test_transient_http_errors_until_the_budget_end_in_the_historical_timeout(self):
        self.script([_raise(ForgeEngineError("not yet")), _raise(http.client.BadStatusLine("garbage"))])

        self.start()
        self.wait_for_state(START_FAILED, timeout=10.0)

        self.assertIn("did not become available", self.manager.last_error_message)
        self.assert_owned_process_ended_and_thread_cleaned()

    def test_an_http_client_state_error_during_polling_is_not_retried(self):
        engine_script = self.script([_raise(ForgeEngineError("not yet")), _raise(http.client.CannotSendRequest("Request-sent"))])

        self.start()
        self.wait_for_state(START_FAILED)

        self.assertEqual(engine_script.calls, 2, "pre-start check plus exactly one polling attempt")
        self.assert_owned_process_ended_and_thread_cleaned()


class ForgeLifecycleManagerPreStartCheckRegressionTest(_LifecycleCase):
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
                manager = ForgeLifecycleManager()
                states = []
                manager.state_changed.connect(states.append)
                self._fake_engine.check_connection.side_effect = exc

                raised = None
                with patch.object(lifecycle_module, "QProcess") as process_cls:
                    try:
                        manager.start("fake-forge-path", "http://127.0.0.1:7860")
                    except Exception as error:  # the defect: it used to escape start()
                        raised = error

                self.assertIsNone(raised, "start() must not let the exception escape")
                self.assertEqual(manager.state, START_FAILED)
                self.assertEqual(states, [START_FAILED], "never passes through STARTING")
                process_cls.assert_not_called()
                self.assertIsNone(manager._process)
                self.assertIsNone(manager._readiness_thread)


class ForgeLifecycleManagerReadinessInvariantTest(_LifecycleCase):

    def test_a_pre_start_engine_error_still_proceeds_to_launch(self):
        # Historical meaning kept: an error the engine already translated into
        # ForgeEngineError (nothing usable on the port) leads to the launch.
        self.script([_raise(ForgeEngineError("not yet")), _ok()])
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


class ForgeLifecycleManagerUnexpectedFailureContractTest(_LifecycleCase):
    """The Mission 170 contract: failed, its message, its cleanup path. Not a proof of the defect."""

    quiet_logs = False

    def test_the_failure_message_reaches_start_failed_unchanged_with_a_real_tree(self):
        self.script([_raise(ForgeEngineError("not yet")), ("until", self.descendant_pid_written, _raise(AttributeError("boom")))])

        with self.assertLogs(worker_module.logger, "ERROR") as captured:
            self.start()
            self.wait_for_state(START_FAILED)
        descendant_pid = int(self._pid_file.read_text().strip())  # written before the failure, by construction

        message = self.manager.last_error_message
        base_message = "Forge readiness check failed unexpectedly (AttributeError: boom)."
        self.assertTrue(message.startswith(base_message))
        self.assertNotIn("stopped", message.lower())
        self.assertNotIn("did not become available", message)
        # The message and the latch always agree, whichever way taskkill /T resolved: a confirmed
        # teardown gives the bare message, an unconfirmed one arms the latch and appends the caveat.
        # (The deterministic confirmed/unconfirmed paths are covered by the rendezvous tests.)
        if self.manager._stop_unconfirmed:
            self.assertIn("could not be confirmed fully cleaned up", message)
        else:
            self.assertEqual(message, base_message)
            self.assertFalse(_pid_is_alive(descendant_pid))  # checked once, never polled (PID reuse)
        self.assert_owned_process_ended_and_thread_cleaned()
        self.assertEqual(len(captured.records), 1)

    def test_a_failure_with_taskkill_unavailable_is_unconfirmed_arms_the_latch_and_blocks_start(self):
        self.script([_raise(ForgeEngineError("not yet")), ("until", self.descendant_pid_written, _raise(AttributeError("boom")))])

        with patch.object(lifecycle_module, "TASKKILL_EXECUTABLE", "definitely_not_a_real_taskkill_binary.exe"), \
                self.assertLogs(worker_module.logger, "ERROR"):
            self.start()
            self.wait_for_state(START_FAILED, timeout=10.0)
            descendant_pid = int(self._pid_file.read_text().strip())  # written before the failure, by construction

            message = self.manager.last_error_message
            self.assertTrue(message.startswith("Forge readiness check failed unexpectedly (AttributeError: boom)."))
            self.assertIn("could not be confirmed fully cleaned up", message)
            self.assertNotIn("stopped", message.lower())
            self.assertTrue(self.manager._stop_unconfirmed)
            self.assertTrue(_pid_is_alive(descendant_pid))  # the real descendant survives the fallback kill()

            # A retried Start is blocked outright while the survivor is not HTTP-ready.
            self._fake_engine.check_connection.side_effect = ForgeEngineError("not yet")
            self.start()
            self.assertEqual(self.manager.state, START_FAILED)
            self.assertIn("blocked", self.manager.last_error_message.lower())
            self.assertTrue(self.manager._stop_unconfirmed)


class ForgeLifecycleManagerFailedRendezvousTest(unittest.TestCase):
    """
    _on_readiness_failed() through the existing taskkill rendezvous, with
    fabricated state and mocked QProcess/QTimer (no real process): guards,
    confirmed cleanup, unconfirmed cleanup (exit code, launch error, timer), no
    live process, late signals, and the _stop_unconfirmed latch.
    """

    BASE_MESSAGE = "Forge readiness check failed unexpectedly (RuntimeError: X)."

    def setUp(self):
        self.manager = ForgeLifecycleManager()
        self.worker = MagicMock()
        self.owned_process = MagicMock()
        self.owned_process.state.return_value = QProcess.ProcessState.Running
        self.owned_process.processId.return_value = 4242
        self.taskkill = MagicMock()
        self.timer = MagicMock()

    def _sender(self, sender):
        return patch.object(ForgeLifecycleManager, "sender", return_value=sender)

    def _arm_cleanup(self, latch=False):
        self.manager._state = STARTING
        self.manager._stop_unconfirmed = latch
        self.manager._readiness_worker = self.worker
        self.manager._process = self.owned_process
        with patch.object(lifecycle_module, "QProcess", return_value=self.taskkill), \
                patch.object(lifecycle_module, "QTimer", return_value=self.timer), \
                self._sender(self.worker):
            self.manager._on_readiness_failed("RuntimeError: X")
        self.assertTrue(self.manager._terminating_owned_process)
        # Strictly scoped to the owned pid, never a name-based or tree-wide kill.
        self.taskkill.start.assert_called_once_with(
            lifecycle_module.TASKKILL_EXECUTABLE, ["/PID", "4242", "/T", "/F"]
        )

    def _owned_cmd_finished(self):
        self.manager._on_process_finished(1, QProcess.ExitStatus.NormalExit)

    def _taskkill_finished(self, exit_code):
        with self._sender(self.taskkill):
            self.manager._on_taskkill_finished(exit_code, QProcess.ExitStatus.NormalExit)

    def test_a_confirmed_cleanup_lands_on_start_failed_with_the_unchanged_message_in_both_orders(self):
        for order in ("cmd first", "taskkill first"):
            with self.subTest(order):
                self.setUp()
                self._arm_cleanup(latch=True)  # an earlier uncertainty is cleared by a confirmed cleanup

                if order == "cmd first":
                    self._owned_cmd_finished()
                    self._taskkill_finished(0)
                else:
                    self._taskkill_finished(0)
                    self._owned_cmd_finished()

                self.assertEqual(self.manager.state, START_FAILED)
                self.assertEqual(self.manager.last_error_message, self.BASE_MESSAGE)
                self.assertNotIn("stopped", self.manager.last_error_message.lower())
                self.assertFalse(self.manager._stop_unconfirmed)

    def test_an_unconfirmed_cleanup_arms_the_latch_and_never_claims_a_stop(self):
        def taskkill_exit_code_1():
            self._taskkill_finished(1)

        def taskkill_launch_error():
            with self._sender(self.taskkill):
                self.manager._on_taskkill_error_occurred(QProcess.ProcessError.FailedToStart)

        def terminate_timer_fired():
            with self._sender(self.timer):
                self.manager._on_terminate_timeout()
            self.owned_process.kill.assert_called_once_with()

        for label, resolve_taskkill in (
            ("taskkill exit code 1", taskkill_exit_code_1),
            ("taskkill could not start", taskkill_launch_error),
            ("terminate timer fired first", terminate_timer_fired),
        ):
            for initial_latch in (False, True):
                with self.subTest("%s, latch %s" % (label, initial_latch)):
                    self.setUp()
                    self._arm_cleanup(latch=initial_latch)

                    resolve_taskkill()
                    self._owned_cmd_finished()

                    message = self.manager.last_error_message
                    self.assertEqual(self.manager.state, START_FAILED)
                    self.assertTrue(message.startswith(self.BASE_MESSAGE))
                    self.assertIn("could not be confirmed fully cleaned up", message)
                    self.assertNotIn("stopped", message.lower())
                    self.assertTrue(self.manager._stop_unconfirmed)

    def test_with_no_live_process_the_failure_lands_on_start_failed_without_any_taskkill(self):
        self.manager._state = STARTING
        self.manager._stop_unconfirmed = True
        self.manager._readiness_worker = self.worker
        self.manager._process = None

        with patch.object(lifecycle_module, "QProcess") as process_cls, self._sender(self.worker):
            self.manager._on_readiness_failed("RuntimeError: X")

        process_cls.assert_not_called()  # no taskkill was ever constructed
        self.assertEqual(self.manager.state, START_FAILED)
        self.assertEqual(self.manager.last_error_message, self.BASE_MESSAGE)
        self.assertTrue(self.manager._stop_unconfirmed)  # neither cleared nor armed by this path
        self.assertIsNone(self.manager._readiness_timeout_message)

    def test_a_failed_signal_from_a_stale_worker_is_ignored(self):
        self.manager._state = STARTING
        self.manager._stop_unconfirmed = True
        self.manager._readiness_worker = self.worker

        with self._sender(MagicMock()), patch.object(self.manager, "_terminate_owned_process") as terminate:
            self.manager._on_readiness_failed("RuntimeError: X")

        terminate.assert_not_called()
        self.assertIsNone(self.manager._readiness_timeout_message)
        self.assertTrue(self.manager._stop_unconfirmed)
        self.assertEqual(self.manager.state, STARTING)

    def test_a_late_failed_signal_is_ignored_once_the_state_left_starting(self):
        for state in (STOPPING, START_FAILED, RUNNING_OWNED, STOPPED):
            with self.subTest(state):
                self.setUp()
                self.manager._state = state
                self.manager._stop_unconfirmed = True
                self.manager._readiness_worker = self.worker
                self.manager.last_error_message = "previous message"

                with self._sender(self.worker), patch.object(self.manager, "_terminate_owned_process") as terminate:
                    self.manager._on_readiness_failed("RuntimeError: X")

                terminate.assert_not_called()
                self.assertIsNone(self.manager._readiness_timeout_message)
                self.assertEqual(self.manager.last_error_message, "previous message")
                self.assertTrue(self.manager._stop_unconfirmed)
                self.assertEqual(self.manager.state, state)


class ForgeLifecycleManagerFailureRestartWithControlledRendezvousTest(_LifecycleCase):
    """
    Restart after an unexpected readiness failure, through the REAL rendezvous callbacks
    (_on_process_finished, _on_taskkill_finished) driven by controlled doubles -- a deterministic
    proof, distinct from the real-tree test. The _stop_unconfirmed latch is only ever changed by
    the production code: it is set as a precondition BEFORE the failure (an earlier unconfirmed
    cleanup) and is never assigned afterwards. No confirmation is simulated while a real
    descendant is alive: there is no real descendant here at all.
    """

    def _fail_and_resolve(self, taskkill_exit_code, initial_latch):
        worker = MagicMock()
        owned_process = MagicMock()
        owned_process.state.return_value = QProcess.ProcessState.Running
        owned_process.processId.return_value = 4242
        taskkill = MagicMock()

        self.manager._state = STARTING
        self.manager._stop_unconfirmed = initial_latch  # precondition only
        self.manager._readiness_worker = worker
        self.manager._process = owned_process

        with patch.object(lifecycle_module, "QProcess", return_value=taskkill), \
                patch.object(lifecycle_module, "QTimer", return_value=MagicMock()), \
                patch.object(ForgeLifecycleManager, "sender", return_value=worker):
            self.manager._on_readiness_failed("RuntimeError: boom")
        taskkill.start.assert_called_once_with(lifecycle_module.TASKKILL_EXECUTABLE, ["/PID", "4242", "/T", "/F"])

        self.manager._on_process_finished(1, QProcess.ExitStatus.NormalExit)  # the owned cmd.exe is gone
        with patch.object(ForgeLifecycleManager, "sender", return_value=taskkill):
            self.manager._on_taskkill_finished(taskkill_exit_code, QProcess.ExitStatus.NormalExit)

    def test_a_confirmed_cleanup_releases_the_latch_naturally_so_a_new_start_proceeds(self):
        self._fail_and_resolve(taskkill_exit_code=0, initial_latch=True)

        self.assertEqual(self.manager.state, START_FAILED)
        self.assertEqual(self.manager.last_error_message, "Forge readiness check failed unexpectedly (RuntimeError: boom).")
        self.assertFalse(self.manager._stop_unconfirmed, "released by the confirmed cleanup itself")

        self.script([_raise(ForgeEngineError("not yet")), _ok()])
        new_process = MagicMock()
        with patch.object(lifecycle_module, "QProcess", return_value=new_process):
            self.start()

        new_process.start.assert_called_once_with("cmd.exe", ["/c", str(self._launch_config.run_bat_path)])
        self.wait_for_state(RUNNING_OWNED)
        # A RUNNING_OWNED process is still protected by the existing confirmation.
        with patch.object(lifecycle_module, "QMessageBox") as box:
            box.Yes, box.No = QMessageBox.Yes, QMessageBox.No
            box.question.return_value = QMessageBox.No
            self.assertTrue(self.manager.confirm_safe_to_close(None))
        box.question.assert_called_once()
        self.assertIs(self.manager._process, new_process)

    def test_an_unconfirmed_cleanup_keeps_the_latch_armed_and_refuses_a_new_start(self):
        self._fail_and_resolve(taskkill_exit_code=1, initial_latch=False)

        self.assertEqual(self.manager.state, START_FAILED)
        self.assertTrue(self.manager.last_error_message.startswith("Forge readiness check failed unexpectedly (RuntimeError: boom)."))
        self.assertIn("could not be confirmed fully cleaned up", self.manager.last_error_message)
        self.assertTrue(self.manager._stop_unconfirmed, "armed by the unconfirmed cleanup itself")

        self.script([_raise(ForgeEngineError("not yet"))])  # the would-be survivor is not HTTP-ready
        with patch.object(lifecycle_module, "QProcess") as process_cls:
            self.start()

        process_cls.assert_not_called()  # no second launch while a descendant could still be alive
        self.assertEqual(self.manager.state, START_FAILED)
        self.assertIn("blocked", self.manager.last_error_message.lower())
        self.assertTrue(self.manager._stop_unconfirmed)


class ForgeLifecycleManagerPreStartCheckContractTest(_LifecycleCase):
    """The pre-start failure message, logging, no-op Stop and the _stop_unconfirmed latch. Not a proof of the defect."""

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
            "Forge pre-start check failed unexpectedly (AttributeError: boom). "
            "The state of the port could not be determined, so nothing was started.",
        )
        self.assertEqual(len(captured.records), 1)

    def test_a_raw_http_exception_is_reported_with_its_type(self):
        with self.assertLogs(lifecycle_module.logger, "ERROR"):
            self._start_with_pre_check_exception(http.client.BadStatusLine("garbage"))

        self.assertEqual(self.manager.state, START_FAILED)
        self.assertIn("BadStatusLine", self.manager.last_error_message)

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

    def test_an_armed_stop_unconfirmed_latch_stays_armed_and_the_message_is_the_pre_start_failure(self):
        self.manager._stop_unconfirmed = True

        with self.assertLogs(lifecycle_module.logger, "ERROR"):
            self._start_with_pre_check_exception(AttributeError("boom"))

        self.assertTrue(self.manager._stop_unconfirmed)  # neither cleared nor armed by this path
        self.assertIn("pre-start check failed unexpectedly", self.manager.last_error_message)
        self.assertNotIn("blocked", self.manager.last_error_message.lower())

    def test_a_clear_latch_stays_clear(self):
        with self.assertLogs(lifecycle_module.logger, "ERROR"):
            self._start_with_pre_check_exception(AttributeError("boom"))

        self.assertFalse(self.manager._stop_unconfirmed)


if __name__ == "__main__":
    unittest.main()
