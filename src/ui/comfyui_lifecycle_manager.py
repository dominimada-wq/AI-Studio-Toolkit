"""
Mission 114: owns the QProcess lifecycle of a locally-launched ComfyUI
instance -- Start/ownership/readiness/Stop -- the only piece of this
vertical that knows about Qt process management, exactly as
TrainingJobRunner (Mission 100) is for OneTrainer and GenerationWorker
(Mission 013) is for Qt threading during a single generation.
ComfyUIEngine itself stays a pure HTTP client -- no process-management
responsibility is added to it by this mission.

Ownership contract: Toolkit only ever calls terminate()/kill() on a
QProcess it created itself here. A backend already reachable at
comfyui_url before Start is EXTERNAL_ACTIVE and is never touched by
stop()/confirm_safe_to_close() -- ownership is never persisted anywhere
(no PID, no state written to ApplicationSettings), so a backend left
running at a previous Toolkit close is always rediscovered as
EXTERNAL_ACTIVE on the next Start, never assumed to still be "ours".

Readiness is checked off the Qt main thread (ComfyUIReadinessWorker on
its own QThread) -- QProcess.started only proves the OS process exists,
never that ComfyUI's HTTP API is actually answering yet.

comfyui_path/comfyui_install_path/comfyui_url are passed into start()
fresh every call, never cached between calls -- and a transient
ComfyUIEngine is built here from the exact resolved host/port for both
the pre-Start reachability check and the readiness polling, deliberately
never the shared MainWindow.comfyui_engine (which may carry a stale
base_url under the existing no-hot-reload contract, Mission 018) --
this guarantees the check always targets the same backend Toolkit is
about to launch or has just launched.

Six states only (module-level string constants below), no generic state
machine: STOPPED, EXTERNAL_ACTIVE, STARTING, RUNNING_OWNED, STOPPING,
START_FAILED. STARTING and STOPPING always resolve to a final state --
either via QProcess's own started/finished/errorOccurred signals or via
the bounded terminate()-then-kill() escalation below -- never left
permanently transitional.

ComfyUI Local only -- no ComfyUI Cloud concept, no Forge, no
Inference/GenerationManager wiring: consuming this class from Generate
is deliberately left to a future mission (MISSION_114.md section 6).
"""
from PySide6.QtCore import QObject, QProcess, QThread, QTimer, Signal
from PySide6.QtWidgets import QMessageBox

from src.engines.comfyui_engine import ComfyUIEngine, ComfyUIEngineError
from src.engines.comfyui_launch import ComfyUILaunchError, resolve_comfyui_launch
from src.ui.comfyui_readiness_worker import ComfyUIReadinessWorker

STOPPED = "stopped"
EXTERNAL_ACTIVE = "external_active"
STARTING = "starting"
RUNNING_OWNED = "running_owned"
STOPPING = "stopping"
START_FAILED = "start_failed"

# 120s (raised from an initial 60s after a real diagnostic relaunch on
# 2026-09-11, see docs/missions/MISSION_114.md): a real cold start on
# the reference machine opened the HTTP port at 58.9s (CUDA/PyTorch
# init + custom-node scanning) -- 60s left virtually no margin. 120s
# keeps a bounded, non-infinite timeout while giving real headroom.
READINESS_BUDGET_SECONDS = 120.0
READINESS_POLL_INTERVAL_SECONDS = 1.0
READINESS_ATTEMPT_TIMEOUT_SECONDS = 2.0
TERMINATE_TIMEOUT_SECONDS = 10.0


class ComfyUILifecycleManager(QObject):

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

        # Set only while an "Oui" (stop-then-close) confirmation is
        # awaiting the real Stop to finish -- see confirm_safe_to_close()
        # and _resume_close_if_pending().
        self._pending_close_widget = None

        # Set only by the readiness-timeout path, consumed exactly once
        # by _on_process_finished()/_finish_process_teardown() so the
        # outward state lands on START_FAILED (with this message) rather
        # than being silently downgraded to STOPPED by the cleanup
        # terminate()/kill() sequence they share with a normal Stop.
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

    def start(self, comfyui_path: str, comfyui_install_path: str, comfyui_url: str) -> None:
        """
        No-op if a Start/Stop cycle is already in flight or already
        owns/observes a running backend (STARTING/RUNNING_OWNED/
        STOPPING) -- never a second concurrent attempt. Safe to call
        again after STOPPED/EXTERNAL_ACTIVE/START_FAILED.
        """
        if self._state not in (STOPPED, EXTERNAL_ACTIVE, START_FAILED):
            return

        try:
            launch = resolve_comfyui_launch(comfyui_path, comfyui_install_path, comfyui_url)
        except ComfyUILaunchError as error:
            self._set_state(START_FAILED, str(error))
            return

        check_engine = ComfyUIEngine(base_url=f"http://{launch.listen_host}:{launch.port}")

        try:
            check_engine.check_connection(timeout=READINESS_ATTEMPT_TIMEOUT_SECONDS)
        except ComfyUIEngineError:
            pass
        else:
            # Already joignable -- never launch a second instance, never
            # take ownership of it (section 3/7 of MISSION_114.md).
            self._set_state(EXTERNAL_ACTIVE)
            return

        process = QProcess(self)
        process.setWorkingDirectory(launch.working_directory)
        process.errorOccurred.connect(self._on_process_error_occurred)
        process.finished.connect(self._on_process_finished)
        self._process = process

        self._set_state(STARTING)
        process.start(
            launch.python_executable,
            [
                launch.entry_point,
                "--base-directory", launch.working_directory,
                "--user-directory", launch.user_directory,
                "--database-url", launch.database_url,
                "--listen", launch.listen_host,
                "--port", str(launch.port),
            ],
        )

        self._start_readiness_worker(check_engine)

    def _start_readiness_worker(self, check_engine) -> None:
        thread = QThread()
        worker = ComfyUIReadinessWorker(
            check_engine,
            budget_seconds=READINESS_BUDGET_SECONDS,
            poll_interval_seconds=READINESS_POLL_INTERVAL_SECONDS,
            attempt_timeout_seconds=READINESS_ATTEMPT_TIMEOUT_SECONDS,
        )
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        # Connected as plain bound methods (never a lambda) so Qt's
        # AutoConnection correctly detects the cross-thread case (the
        # worker lives on `thread`; these handlers must run on the main
        # thread, since _on_readiness_timed_out() below creates a new
        # QTimer that needs a real, already-pumped main-thread event
        # loop). A lambda has no QObject thread affinity of its own, so
        # Qt would otherwise invoke it directly on the emitting (worker)
        # thread instead -- silently starving anything created inside it
        # (a QTimer with no event loop ever servicing it, confirmed
        # empirically while implementing this mission). self.sender()
        # recovers which worker actually emitted, for the same
        # stale-worker identity guard the lambda used to provide via a
        # captured argument.
        worker.ready.connect(self._on_readiness_ready)
        worker.timed_out.connect(self._on_readiness_timed_out)
        worker.ready.connect(thread.quit)
        worker.timed_out.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        # worker/thread captured by value here (not re-read from
        # self._readiness_worker/self._readiness_thread, which may
        # already point at a newer cycle by the time this fires) --
        # same precedent as InferencePage._cleanup_thread (Mission 014).
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
            "ComfyUI did not become available within the expected delay. "
            "A port conflict is possible but not confirmed."
        )
        # State deliberately stays STARTING here (never STOPPING) -- this
        # is an internal failure cleanup, not a user-requested Stop; see
        # _finish_process_teardown()/_on_process_finished() below for how
        # the message survives the shared terminate()/kill() sequence.
        self._terminate_owned_process()

    # ------------------------------------------------------------------
    # QProcess signals
    # ------------------------------------------------------------------

    def _on_process_error_occurred(self, error) -> None:
        if self._state == STARTING and error == QProcess.ProcessError.FailedToStart:
            if self._readiness_worker is not None:
                self._readiness_worker.cancel()
            self._process = None
            self._set_state(START_FAILED, "The ComfyUI process failed to start")

    def _on_process_finished(self, exit_code, exit_status) -> None:
        if self._state == STARTING:
            # Reached either because the process exited entirely on its
            # own before readiness (no cleanup was ever triggered, no
            # _readiness_timeout_message set), or because
            # _terminate_owned_process() was driving a readiness-timeout
            # cleanup and the process has now actually exited.
            if self._readiness_worker is not None:
                self._readiness_worker.cancel()
            message = self._readiness_timeout_message or (
                f"ComfyUI process exited before becoming available (exit_code={exit_code})"
            )
            self._readiness_timeout_message = None
            self._process = None
            self._set_state(START_FAILED, message)
        elif self._state == STOPPING:
            self._process = None
            self._set_state(STOPPED)
            self._resume_close_if_pending()

    # ------------------------------------------------------------------
    # Stop
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """
        No-op on EXTERNAL_ACTIVE/STOPPED/START_FAILED -- Toolkit only
        ever stops a process it owns. Idempotent: a second call while
        already STOPPING, or after STOPPED, does nothing further.
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

        self._process.terminate()
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(self._on_terminate_timeout)
        timer.start(int(TERMINATE_TIMEOUT_SECONDS * 1000))
        self._terminate_timer = timer

    def _on_terminate_timeout(self) -> None:
        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()

    def _finish_process_teardown(self) -> None:
        # Only reached when _terminate_owned_process() finds no live
        # process to begin with (already exited) -- the live-process
        # path always resolves through _on_process_finished() instead,
        # so both converge on the exact same state-transition logic.
        self._process = None
        if self._state == STARTING:
            message = self._readiness_timeout_message or "ComfyUI process was no longer running"
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
        TrainingPage.confirm_no_active_training()/
        InferencePage.confirm_no_active_generation(). STARTING/STOPPING
        always refuse (a bounded, always-resolving transient window --
        never a permanent block). EXTERNAL_ACTIVE/STOPPED/START_FAILED
        always proceed without touching ComfyUI. RUNNING_OWNED asks
        explicitly; answering "Oui" defers the actual close until Stop
        has genuinely finished (parent_widget.close() is invoked again
        from _resume_close_if_pending(), never before) rather than
        destroying this QProcess/QThread while they are still working.
        """
        if self._state in (STARTING, STOPPING):
            QMessageBox.warning(
                parent_widget,
                "ComfyUI en cours d'opération",
                "Une opération ComfyUI (démarrage ou arrêt) est en cours. "
                "Attendez qu'elle soit terminée avant de fermer l'application.",
            )
            return False

        if self._state != RUNNING_OWNED:
            return True

        answer = QMessageBox.question(
            parent_widget,
            "ComfyUI en cours d'exécution",
            "ComfyUI a été démarré par AI Studio Toolkit. "
            "Voulez-vous également arrêter ComfyUI ?",
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
