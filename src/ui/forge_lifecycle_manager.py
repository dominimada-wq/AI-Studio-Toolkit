"""
Mission 119: owns the lifecycle of a locally-launched Forge instance --
Start/ownership/readiness/Stop -- the only piece of this vertical that
knows about Qt process management, mirroring ComfyUILifecycleManager's
already-validated contract (Mission 114) wherever the two engines'
launch mechanisms agree: six explicit states, readiness checked off the
Qt main thread, ownership never persisted (no PID, no state written to
ApplicationSettings), EXTERNAL_ACTIVE never touched by stop()/
confirm_safe_to_close(), STARTING/STOPPING always resolving to a final
state. ForgeEngine itself stays a pure HTTP client -- no process-
management responsibility is added to it by this mission.

Deliberately diverges from ComfyUILifecycleManager exactly where a real
empirical test (see docs/missions/MISSION_119.md) proved Forge's launch
mechanism forces it:

Forge's own launcher is run.bat -- a batch script, not a directly
executable .exe like ComfyUI's venv python.exe. QProcess cannot execute
a .bat file directly on Windows, so the process this class actually
owns is "cmd.exe" ["/c", run_bat_path] (see resolve_forge_launch() for
why, and for the PATH-prepend fix its own run.bat's internal `call`
lines require on a machine with NoDefaultCurrentDirectoryInExePath
set). Because every `call` inside run.bat/environment.bat/
webui-user.bat/webui.bat runs in that SAME cmd.exe (call never forks),
and only the final, non-`call` `%PYTHON% launch.py` line spawns a real
child process, the actual Forge server (python.exe) is only ever a
*child* of the cmd.exe this class owns -- never the process itself.
QProcess.terminate()/.kill() only ever signal the single process they
are called on (confirmed empirically: Windows does not recurse into
children for either call) -- so Stop here never relies on them as the
primary mechanism. Instead it shells out to
`taskkill /PID <cmd_pid> /T /F`, verified empirically against a real
installation to terminate the entire real tree (the owned cmd.exe, its
conhost.exe console, and python.exe running launch.py) in one call,
while being strictly scoped to the actual descendants of the one
process Toolkit itself launched -- taskkill's /T walks the real NT
process tree rooted at exactly that PID, so it can never reach a
sibling process, an unrelated externally-started Forge/Python instance,
or any other process on the machine. QProcess.kill() on the owned
cmd.exe remains a last-resort fallback (bounded by TERMINATE_TIMEOUT_
SECONDS) purely in case taskkill itself could not run.

Forge Local only -- no Fooocus, no cloud providers, no Inference/
GenerationManager wiring: consuming this class from Generate is left to
a future mission, exactly like ComfyUILifecycleManager's own Mission
114 scope note.
"""
from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QThread, QTimer, Signal
from PySide6.QtWidgets import QMessageBox

from src.engines.forge_engine import ForgeEngine, ForgeEngineError
from src.engines.forge_launch import ForgeLaunchError, resolve_forge_launch
from src.ui.forge_readiness_worker import ForgeReadinessWorker

STOPPED = "stopped"
EXTERNAL_ACTIVE = "external_active"
STARTING = "starting"
RUNNING_OWNED = "running_owned"
STOPPING = "stopping"
START_FAILED = "start_failed"

# Same budget as ComfyUILifecycleManager -- Forge/A1111 is a comparable
# CUDA/PyTorch cold-start cost (model loading + extension scanning),
# not a launch-mechanism-specific value, so the already-measured
# ComfyUI figure is reused as a defensible default absent a dedicated
# real cold-start measurement for this exact installation.
READINESS_BUDGET_SECONDS = 120.0
READINESS_POLL_INTERVAL_SECONDS = 1.0
READINESS_ATTEMPT_TIMEOUT_SECONDS = 2.0
TERMINATE_TIMEOUT_SECONDS = 10.0

# Named as a module constant (rather than an inline literal) so a test
# can force a real, deterministic "taskkill could not even be started"
# scenario by pointing this at a nonexistent binary -- exercising the
# real QProcess.errorOccurred(FailedToStart) path against a real owned
# process tree, never simulated.
TASKKILL_EXECUTABLE = "taskkill"


class ForgeLifecycleManager(QObject):

    # Emitted after every state transition, carrying the new state
    # string (one of the module constants above). last_error_message is
    # updated immediately before this fires, so a slot reading it in
    # response to state_changed always sees the value for this state.
    state_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = STOPPED
        self.last_error_message = ""

        self._process = None
        self._readiness_thread = None
        self._readiness_worker = None
        self._terminate_timer = None
        self._taskkill_process = None

        # Termination-confirmation rendezvous, shared by *every* path that
        # actively tries to kill an owned Forge tree -- a user-requested
        # Stop (RUNNING_OWNED/STARTING -> STOPPING) *and* the readiness-
        # timeout Start-failure cleanup (STARTING -> _terminate_owned_
        # process(), state deliberately unchanged) alike. Both call the
        # exact same _terminate_owned_process()/_maybe_finish_teardown()
        # machinery below -- this mission's own review confirmed the two
        # share the identical ownership/ordering hazard, so there is
        # deliberately only one implementation of it, not two parallel
        # ones. self._terminating_owned_process (further below) is what
        # tells _on_process_finished() an active kill attempt (rather
        # than the owned process exiting entirely on its own) is why the
        # process just died, regardless of which of the two callers
        # started that attempt.
        #
        # A real empirical test showed the owned cmd.exe's own finished
        # signal reliably arrives *before* taskkill's own finished/
        # errorOccurred signal (taskkill keeps running briefly after the
        # TerminateProcess call that kills cmd.exe, to report on the
        # whole tree) -- so this can never be decided the instant the
        # owned process dies; it must wait for taskkill's own outcome
        # too, whichever of the two arrives second. _stop_confirmed only
        # ever becomes True once taskkill's own process reports exit
        # code 0 -- never inferred merely from the owned cmd.exe exiting,
        # which can also happen because taskkill itself failed/could not
        # start and _on_terminate_timeout()'s own fallback killed only
        # the top-level cmd.exe (confirmed empirically: this never
        # reaches a descendant on Windows), leaving the real Forge server
        # (python.exe) potentially still running, unowned, undetected.
        self._stop_confirmed = False
        self._owned_process_gone = False
        self._taskkill_resolved = False
        self._terminating_owned_process = False

        # Latch, internal to this class only (never persisted anywhere --
        # a fresh ForgeLifecycleManager after a Toolkit restart always
        # starts with this False, per M119's own scope). Set True
        # whenever *any* active kill attempt on the owned tree -- a Stop
        # or a readiness-timeout cleanup alike -- ends up unconfirmed
        # (see _maybe_finish_teardown() below): a real descendant process
        # may still be alive but not yet reachable over HTTP. start()'s
        # own pre-check already detects a reachable survivor as
        # EXTERNAL_ACTIVE regardless of this latch; it exists
        # specifically for the gap that check cannot cover on its own --
        # a survivor that is alive but not yet HTTP-ready -- where
        # start() would otherwise launch a second real Forge instance
        # alongside the first. Cleared the moment a kill attempt is
        # genuinely confirmed, or the moment start()'s own pre-check
        # confirms a survivor as EXTERNAL_ACTIVE (the backend is then
        # identified and tracked, so the uncertainty this latch guards
        # against no longer applies).
        self._stop_unconfirmed = False

        # Set only while an "Oui" (stop-then-close) confirmation is
        # awaiting the real Stop to finish -- see confirm_safe_to_close()
        # and _resume_close_if_pending().
        self._pending_close_widget = None

        # Set only by the readiness-timeout path, consumed exactly once
        # by _on_process_finished()/_finish_process_teardown() so the
        # outward state lands on START_FAILED (with this message) rather
        # than being silently downgraded to STOPPED by the cleanup
        # sequence they share with a normal Stop.
        self._readiness_timeout_message = None

    @property
    def state(self) -> str:
        return self._state

    def _set_state(self, new_state: str, error_message: str = "") -> None:
        self._state = new_state
        self.last_error_message = error_message
        self.state_changed.emit(new_state)

    # ------------------------------------------------------------------
    # Start
    # ------------------------------------------------------------------

    def start(self, forge_path: str, forge_url: str) -> None:
        """
        No-op if a Start/Stop cycle is already in flight or already
        owns/observes a running backend (STARTING/RUNNING_OWNED/
        STOPPING) -- never a second concurrent attempt. Safe to call
        again after STOPPED/EXTERNAL_ACTIVE/START_FAILED.
        """
        if self._state not in (STOPPED, EXTERNAL_ACTIVE, START_FAILED):
            return

        try:
            launch = resolve_forge_launch(forge_path, forge_url)
        except ForgeLaunchError as error:
            self._set_state(START_FAILED, str(error))
            return

        check_engine = ForgeEngine(base_url=f"http://{launch.listen_host}:{launch.port}")

        try:
            check_engine.check_connection(timeout=READINESS_ATTEMPT_TIMEOUT_SECONDS)
        except ForgeEngineError:
            pass
        else:
            # Already joignable -- never launch a second instance, never
            # take ownership of it (same principle as ComfyUI's own
            # Mission 114 contract). The backend is now identified and
            # reachable, so any uncertainty an earlier unconfirmed Stop
            # left behind no longer applies.
            self._stop_unconfirmed = False
            self._set_state(EXTERNAL_ACTIVE)
            return

        if self._stop_unconfirmed:
            # A previous kill attempt (a Stop, or a readiness-timeout
            # cleanup) could not confirm the whole owned tree was
            # actually terminated (see _maybe_finish_teardown() below),
            # and the pre-check above just proved the would-be
            # survivor is not (yet) reachable over HTTP -- exactly the
            # one gap that check cannot cover on its own: a real Forge
            # process could still be alive, mid-startup, about to bind
            # this same port. Launching a second real instance here
            # would be the one scenario that check-then-launch cannot
            # protect against. Refuse outright -- no QProcess is ever
            # created in this branch.
            self._set_state(
                START_FAILED,
                "Forge's previous Stop could not be confirmed, and a process "
                "may still be running. Starting again is blocked to avoid "
                "launching a duplicate -- check or stop Forge manually, or "
                "wait for it to become reachable (it will then be detected "
                "as already active)."
            )
            return

        process = QProcess(self)
        process.setWorkingDirectory(launch.working_directory)

        # PATH-prepend fix -- see resolve_forge_launch()'s own docstring
        # and MISSION_119.md for the real, empirically-confirmed reason
        # this is required: run.bat's own internal `call` lines use bare
        # filenames that only resolve via PATH once the current-
        # directory search is disabled (NoDefaultCurrentDirectoryInExePath).
        # Scoped to this one child process only -- never the registry,
        # never any other process.
        environment = QProcessEnvironment.systemEnvironment()
        current_path = environment.value("Path") or environment.value("PATH") or ""
        environment.insert("Path", ";".join(launch.extra_path_dirs) + ";" + current_path)
        process.setProcessEnvironment(environment)

        process.errorOccurred.connect(self._on_process_error_occurred)
        process.finished.connect(self._on_process_finished)
        self._process = process

        self._set_state(STARTING)
        process.start("cmd.exe", ["/c", launch.run_bat_path])

        self._start_readiness_worker(check_engine)

    def _start_readiness_worker(self, check_engine) -> None:
        thread = QThread()
        worker = ForgeReadinessWorker(
            check_engine,
            budget_seconds=READINESS_BUDGET_SECONDS,
            poll_interval_seconds=READINESS_POLL_INTERVAL_SECONDS,
            attempt_timeout_seconds=READINESS_ATTEMPT_TIMEOUT_SECONDS,
        )
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        # Connected as plain bound methods (never a lambda) -- same
        # cross-thread AutoConnection rationale as
        # ComfyUILifecycleManager._start_readiness_worker() (Mission 114).
        worker.ready.connect(self._on_readiness_ready)
        worker.timed_out.connect(self._on_readiness_timed_out)
        worker.ready.connect(thread.quit)
        worker.timed_out.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        thread.finished.connect(lambda: self._cleanup_readiness(worker, thread))

        self._readiness_worker = worker
        self._readiness_thread = thread

        thread.start()

    def _cleanup_readiness(self, worker, thread) -> None:
        worker.deleteLater()
        thread.deleteLater()
        if self._readiness_worker is worker:
            self._readiness_worker = None
        if self._readiness_thread is thread:
            self._readiness_thread = None

    # ------------------------------------------------------------------
    # Readiness outcomes -- each guarded by both worker identity (a
    # stale signal from an older Start cycle must never act on the
    # current one) and current state (a Stop already requested during
    # STARTING must never be overtaken by a late HTTP success).
    # ------------------------------------------------------------------

    def _on_readiness_ready(self) -> None:
        worker = self.sender()
        if self._readiness_worker is not worker or self._state != STARTING:
            return
        self._set_state(RUNNING_OWNED)

    def _on_readiness_timed_out(self) -> None:
        worker = self.sender()
        if self._readiness_worker is not worker or self._state != STARTING:
            return
        self._readiness_timeout_message = (
            "Forge did not become available within the expected delay. "
            "A port conflict is possible but not confirmed."
        )
        # State deliberately stays STARTING here (never STOPPING) -- this
        # is an internal failure cleanup, not a user-requested Stop.
        self._terminate_owned_process()

    # ------------------------------------------------------------------
    # QProcess signals
    # ------------------------------------------------------------------

    def _on_process_error_occurred(self, error) -> None:
        if self._state == STARTING and error == QProcess.ProcessError.FailedToStart:
            if self._readiness_worker is not None:
                self._readiness_worker.cancel()
            self._process = None
            self._set_state(START_FAILED, "The Forge process failed to start")

    def _on_process_finished(self, exit_code, exit_status) -> None:
        if self._readiness_worker is not None:
            self._readiness_worker.cancel()

        if self._terminating_owned_process:
            # An active kill attempt is in flight -- a user Stop
            # (STOPPING) or a readiness-timeout Start-failure cleanup
            # (still STARTING) alike -- so this owned process dying is
            # never, by itself, enough to conclude anything: taskkill's
            # own outcome must still be confirmed too. See
            # _maybe_finish_teardown() below for the actual resolution,
            # shared by both callers.
            self._process = None
            self._owned_process_gone = True
            self._maybe_finish_teardown()
            return

        if self._state == STARTING:
            # The owned process exited entirely on its own -- no active
            # kill was ever attempted (_terminating_owned_process is
            # False), so there is nothing here whose confirmation could
            # be uncertain: cmd.exe's own blocking `%PYTHON% launch.py`
            # invocation only exits once python.exe itself already has.
            message = self._readiness_timeout_message or (
                f"Forge process exited before becoming available (exit_code={exit_code})"
            )
            self._readiness_timeout_message = None
            self._process = None
            self._set_state(START_FAILED, message)

    def _maybe_finish_teardown(self) -> None:
        """
        The rendezvous point for the two independent async signals any
        active kill attempt on the owned tree produces -- the owned
        cmd.exe's own finished (_owned_process_gone) and taskkill's own
        outcome (_taskkill_resolved, set by _on_taskkill_finished()/
        _on_taskkill_error_occurred()/_on_terminate_timeout()). Shared,
        deliberately, by both callers of _terminate_owned_process(): a
        user-requested Stop (state STOPPING) and the readiness-timeout
        Start-failure cleanup (state still STARTING) -- the exact same
        ownership hazard applies to both, so there is only one
        implementation of this rendezvous, not two parallel ones.

        A real empirical test showed the two signals can arrive in
        either order (taskkill keeps running briefly after the
        TerminateProcess call that kills cmd.exe) -- resolving as soon
        as only one of the two had fired was confirmed to produce
        exactly the false negative this mission's review flagged.
        Neither a clean STOPPED nor a "cleanup confirmed" START_FAILED
        is ever reported until both have resolved *and* taskkill's own
        process confirmed success -- the owned cmd.exe exiting is never,
        by itself, sufficient proof the whole tree (in particular the
        real Forge server, python.exe) is actually gone.
        """
        if self._state not in (STARTING, STOPPING):
            return
        if not self._owned_process_gone or not self._taskkill_resolved:
            return

        self._terminating_owned_process = False

        if self._state == STOPPING:
            if self._stop_confirmed:
                # A Stop that is now genuinely confirmed clears any
                # earlier uncertainty -- see start()'s own use of this
                # latch.
                self._stop_unconfirmed = False
                self._set_state(STOPPED)
                # A deferred "Oui, stop then close" (confirm_safe_to_
                # close()) only ever resumes once Stop is a *confirmed*
                # success -- never merely because STOPPING resolved to
                # some final state.
                self._resume_close_if_pending()
            else:
                # Latched so a later start() refuses to launch a second
                # instance while a real descendant could still be alive
                # but not yet reachable over HTTP -- the one gap
                # start()'s own pre-check cannot cover by itself. See
                # start()'s own use of this latch for the exact contract
                # and when it is cleared.
                self._stop_unconfirmed = True
                self._set_state(
                    START_FAILED,
                    "Forge could not be confirmed fully stopped -- a descendant "
                    "process may still be running. Starting again will detect "
                    "it as already active if it has since become reachable, or "
                    "be refused otherwise to avoid launching a duplicate."
                )
                self._abandon_pending_close_after_unconfirmed_stop()
            return

        # STARTING: the readiness-timeout Start-failure cleanup. The
        # outward result is always START_FAILED either way (the Start
        # attempt itself failed regardless of cleanup confirmation) --
        # never silently replaced by a generic Stop-shaped message --
        # but _stop_unconfirmed is armed exactly like the STOPPING case
        # whenever the kill attempt itself could not be confirmed.
        base_message = self._readiness_timeout_message or (
            "Forge process was terminated before becoming available"
        )
        self._readiness_timeout_message = None
        if self._stop_confirmed:
            self._stop_unconfirmed = False
            self._set_state(START_FAILED, base_message)
        else:
            self._stop_unconfirmed = True
            self._set_state(
                START_FAILED,
                base_message + " Additionally, Forge's process tree could not "
                "be confirmed fully cleaned up afterward -- a descendant "
                "process may still be running. Starting again will detect it "
                "as already active if it has since become reachable, or be "
                "refused otherwise to avoid launching a duplicate."
            )

    # ------------------------------------------------------------------
    # Stop
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """
        No-op on EXTERNAL_ACTIVE/STOPPED/START_FAILED -- Toolkit only
        ever stops a process tree it owns. Idempotent: a second call
        while already STOPPING, or after STOPPED, does nothing further.
        """
        if self._state == STARTING:
            if self._readiness_worker is not None:
                self._readiness_worker.cancel()
            self._set_state(STOPPING)
            self._terminate_owned_process()
            return

        if self._state != RUNNING_OWNED:
            return

        self._set_state(STOPPING)
        self._terminate_owned_process()

    def _terminate_owned_process(self) -> None:
        if self._process is None or self._process.state() == QProcess.ProcessState.NotRunning:
            self._finish_process_teardown()
            return

        pid = self._process.processId()
        self._stop_confirmed = False
        self._owned_process_gone = False
        self._taskkill_resolved = False
        self._terminating_owned_process = True

        # taskkill /T /F: verified empirically (MISSION_119.md) to
        # terminate the entire real tree Toolkit owns (the cmd.exe this
        # class started, its conhost.exe console, and the real Forge
        # server, python.exe launch.py) in one call -- QProcess.
        # terminate()/.kill() alone only ever signal this single cmd.exe,
        # never its children, on Windows. Strictly scoped to pid's own
        # descendants -- never a sibling process or an unrelated Forge/
        # Python instance elsewhere on the machine.
        #
        # A real, tracked QProcess is used here (never startDetached())
        # specifically so this class learns taskkill's own outcome --
        # startDetached() is fire-and-forget and would leave this class
        # with no way to ever know taskkill actually succeeded, which is
        # exactly the gap that would let a failed/partial kill silently
        # be reported as a clean Stop.
        taskkill = QProcess(self)
        taskkill.finished.connect(self._on_taskkill_finished)
        taskkill.errorOccurred.connect(self._on_taskkill_error_occurred)
        self._taskkill_process = taskkill
        taskkill.start(TASKKILL_EXECUTABLE, ["/PID", str(pid), "/T", "/F"])

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(self._on_terminate_timeout)
        timer.start(int(TERMINATE_TIMEOUT_SECONDS * 1000))
        self._terminate_timer = timer

    def _on_taskkill_finished(self, exit_code, exit_status) -> None:
        if self.sender() is not self._taskkill_process:
            return  # stale signal from an earlier Stop cycle
        # Exit code 0 is taskkill's own documented success contract --
        # every process it was told to terminate (via /PID .../T) was
        # actually terminated. Any other exit code (e.g. access denied
        # on a descendant, or the tree only partially torn down) must
        # never be treated as a confirmed clean Stop -- _stop_confirmed
        # simply stays at its current (already-False) value.
        if exit_code == 0:
            self._stop_confirmed = True
        self._taskkill_resolved = True
        self._taskkill_process = None
        self._maybe_finish_teardown()

    def _on_taskkill_error_occurred(self, error) -> None:
        if self.sender() is not self._taskkill_process:
            return  # stale signal from an earlier Stop cycle
        # taskkill.exe itself could not even be started (e.g. missing
        # from this machine, or some other launch failure) -- never
        # assume success; _stop_confirmed is simply left at its current
        # (already-False) value from _terminate_owned_process() above.
        self._taskkill_resolved = True
        self._taskkill_process = None
        self._maybe_finish_teardown()

    def _on_terminate_timeout(self) -> None:
        # taskkill has not resolved (finished or errored) within the
        # bounded wait -- stop waiting for it. Killing only the
        # top-level cmd.exe here would NOT guarantee the real Forge
        # server (python.exe) actually dies too (confirmed empirically:
        # Windows does not recurse into children for QProcess.kill()) --
        # this is a last-resort, best-effort attempt to at least stop
        # the one process this object still directly tracks, deliberately
        # never treated as proof the whole tree is gone: _stop_confirmed
        # is left untouched here, so _maybe_finish_teardown() reports
        # this honestly rather than as a clean Stop. A late taskkill
        # signal arriving after this point is ignored as stale (see the
        # sender()-identity guards above), since this cycle has already
        # moved on and self._taskkill_process is cleared here too.
        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
        self._taskkill_resolved = True
        self._taskkill_process = None
        self._maybe_finish_teardown()

    def _finish_process_teardown(self) -> None:
        # Only reached when _terminate_owned_process() finds no live
        # owned process to begin with -- i.e. no taskkill was ever
        # issued, because there was nothing left to kill. Unlike
        # _maybe_finish_teardown() above, this path never needs
        # _stop_confirmed/_stop_unconfirmed: there is no active kill
        # attempt whose outcome could be uncertain here.
        self._process = None
        if self._state == STARTING:
            message = self._readiness_timeout_message or "Forge process was no longer running"
            self._readiness_timeout_message = None
            self._set_state(START_FAILED, message)
        elif self._state == STOPPING:
            self._set_state(STOPPED)
            self._resume_close_if_pending()

    # ------------------------------------------------------------------
    # Toolkit close guard
    # ------------------------------------------------------------------

    def confirm_safe_to_close(self, parent_widget) -> bool:
        """
        True=proceed/False=abandon, same contract shape as
        ComfyUILifecycleManager.confirm_safe_to_close() (Mission 114).
        STARTING/STOPPING always refuse (a bounded, always-resolving
        transient window -- never a permanent block). EXTERNAL_ACTIVE/
        STOPPED/START_FAILED always proceed without touching Forge.
        RUNNING_OWNED asks explicitly; answering "Oui" defers the actual
        close until Stop has genuinely finished (parent_widget.close()
        is invoked again from _resume_close_if_pending(), never before).
        """
        if self._state in (STARTING, STOPPING):
            QMessageBox.warning(
                parent_widget,
                "Forge en cours d'opération",
                "Une opération Forge (démarrage ou arrêt) est en cours. "
                "Attendez qu'elle soit terminée avant de fermer l'application.",
            )
            return False

        if self._state != RUNNING_OWNED:
            return True

        answer = QMessageBox.question(
            parent_widget,
            "Forge en cours d'exécution",
            "Forge a été démarré par AI Studio Toolkit. "
            "Voulez-vous également arrêter Forge ?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer == QMessageBox.No:
            return True

        self._pending_close_widget = parent_widget
        self.stop()
        return False

    def _resume_close_if_pending(self) -> None:
        widget = self._pending_close_widget
        if widget is not None:
            self._pending_close_widget = None
            widget.close()

    def _abandon_pending_close_after_unconfirmed_stop(self) -> None:
        """
        Mission 119 (post-review): a deferred "Oui, stop Forge then
        close" request must never silently resume once STOPPING
        resolves to an *unconfirmed* Stop -- doing so would close
        Toolkit while a real Forge process could still be running,
        exactly contradicting the user's own explicit choice ("stop it,
        *then* close"). Unlike _resume_close_if_pending(), this never
        calls widget.close() -- Toolkit stays open so the user can see
        the failure and decide what to do next (retry Stop, or close
        anyway themselves, which is then their own separate, explicit
        choice rather than one made silently on their behalf here).
        """
        widget = self._pending_close_widget
        if widget is None:
            return
        self._pending_close_widget = None
        QMessageBox.critical(
            widget,
            "Impossible de confirmer l'arrêt de Forge",
            "Forge n'a pas pu être confirmé comme arrêté (l'opération d'arrêt "
            "a échoué ou n'a pas pu être lancée). Un processus Forge pourrait "
            "encore être actif en arrière-plan. AI Studio Toolkit reste "
            "ouvert pour vous permettre de vérifier la situation avant de "
            "fermer à nouveau.",
        )
