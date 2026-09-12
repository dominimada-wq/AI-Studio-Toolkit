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

from src.engines.forge_engine import ForgeEngineError
from src.engines.forge_launch import ForgeLaunchConfig, ForgeLaunchError
from src.ui import forge_lifecycle_manager as lifecycle_module
from src.ui.forge_lifecycle_manager import (
    EXTERNAL_ACTIVE,
    RUNNING_OWNED,
    STARTING,
    START_FAILED,
    STOPPED,
    STOPPING,
    ForgeLifecycleManager,
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


if __name__ == "__main__":
    unittest.main()
