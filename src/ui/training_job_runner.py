"""
TrainingJobRunner drives one real OneTrainer execution attempt via
QProcess — the only piece of this vertical that knows about Qt process
management, exactly as GenerationWorker (src/ui/generation_worker.py)
is the only piece that knows about Qt threading for Inference.
TrainingManager itself stays Qt-free (Mission 013 precedent).

Mission 100 contract (docs/missions/MISSION_100.md), as revised after
the callback.pipe boundary decision:
- stdout/stderr is the ONLY runtime channel from OneTrainer. No
  --callback-path is ever passed to train_remote.py, so OneTrainer's
  own TrainCallbacks stays a pure no-op and never attempts to write a
  callback.pipe at all — deserializing OneTrainer's own
  TrainProgress/TrainCommands objects in this (PySide6) process would
  require importing OneTrainer's internal package here, exactly the
  boundary this mission refuses to cross (section 3/7/8).
- command.pipe MUST already exist before QProcess.start() — created by
  TrainingManager.create_job(), never here (section 3.4/6).
- Cancel: cooperative stop (via the separate onetrainer_cancel_helper.py
  process, launched with OneTrainer's own interpreter — never imported
  here) -> bounded wait -> QProcess.terminate() -> bounded wait ->
  QProcess.kill() (section 8).
- Both Python interpreter/path preconditions and the terminal state are
  decided exclusively by resolve_onetrainer_launch() and QProcess's own
  exit code/status plus a real filesystem check of
  expected_output_path — never guessed, never fabricated.
"""
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from src.engines.onetrainer_launch import OneTrainerLaunchError, resolve_onetrainer_launch

# Internal, documented constants (MISSION_100.md section 8) — determined
# and tested against the fake deterministic process, not a calibration
# against real OneTrainer (that calibration belongs to Mission 101).
COOPERATIVE_STOP_TIMEOUT_SECONDS = 30.0
TERMINATE_TIMEOUT_SECONDS = 10.0

_CANCEL_HELPER_SCRIPT_PATH = str(
    Path(__file__).resolve().parents[1] / "engines" / "onetrainer_cancel_helper.py"
)


class TrainingJobRunner(QObject):

    # Emitted once QProcess itself confirms the OneTrainer process has
    # actually started (MISSION_100.md section 5.2: "running" is only
    # ever set once this fires — never assumed at the moment start()
    # is called).
    started = Signal()

    # One line of raw stdout/stderr text, in emission order — the only
    # progress/status signal this mission provides (section 7: no
    # percentage, no structured status, never fabricated).
    log_line = Signal(str)

    # (state, error_message, final_output_path) — state is one of
    # TrainingManager's TRAINING_JOB_STATE_{SUCCEEDED,FAILED,CANCELLED}
    # (never STARTING/RUNNING/UNKNOWN, which this runner never decides).
    # error_message/final_output_path are "" when not applicable.
    finished = Signal(str, str, str)

    def __init__(self, job_paths, onetrainer_path: str, parent=None):
        super().__init__(parent)
        self._job_paths = job_paths
        self._onetrainer_path = onetrainer_path
        self._cancel_requested = False
        self._finished_emitted = False

        self._process = QProcess(self)
        self._process.started.connect(self.started)
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.errorOccurred.connect(self._on_error_occurred)
        self._process.finished.connect(self._on_process_finished)

        self._cooperative_timer = QTimer(self)
        self._cooperative_timer.setSingleShot(True)
        self._cooperative_timer.timeout.connect(self._on_cooperative_timeout)

        self._terminate_timer = QTimer(self)
        self._terminate_timer.setSingleShot(True)
        self._terminate_timer.timeout.connect(self._on_terminate_timeout)

        # Kept alive only so the QProcess is not garbage-collected while
        # the cancel helper runs — its own exit code is never checked:
        # the terminate()/kill() fallback below is always available
        # regardless of whether the cooperative command was delivered.
        self._cancel_helper_process = None

    def start(self) -> None:
        """
        Mission 100 section 6 ("Runner / couche fonctionnelle"):
        revalidates OneTrainer's launch preconditions here, every time —
        never trusts that TrainingPage's Start button being enabled is
        still true (a path valid when the UI was drawn may have become
        invalid by the time this runs). On failure, finishes as
        "failed" with an actionable message and never calls
        QProcess.start() at all — never a Job stuck in "starting".
        """
        try:
            launch = resolve_onetrainer_launch(self._onetrainer_path)
        except OneTrainerLaunchError as exc:
            self._finish("failed", str(exc), "")
            return

        args = [
            launch.script_path,
            "--config-path", self._job_paths.config_snapshot_path,
            "--command-path", self._job_paths.command_pipe_path,
        ]
        self._process.setWorkingDirectory(launch.working_directory)
        self._process.start(launch.python_executable, args)

    def cancel(self) -> None:
        """
        Mission 100 section 8: cooperative stop -> bounded wait ->
        terminate() -> bounded wait -> kill(). Idempotent — a second
        call while a cancel is already in flight, or after this Job has
        already finished, is a no-op.
        """
        if self._cancel_requested or self._finished_emitted:
            return
        self._cancel_requested = True
        self._send_cooperative_stop()
        self._cooperative_timer.start(int(COOPERATIVE_STOP_TIMEOUT_SECONDS * 1000))

    def _send_cooperative_stop(self) -> None:
        # Best-effort by construction: MISSION_100.md section 3/4
        # decision — the cooperative command is emitted by a separate
        # process running under OneTrainer's own interpreter (see
        # onetrainer_cancel_helper.py's own docstring for why this must
        # never be imported/executed inside this — PySide6 — process).
        # Its own success or failure is never awaited or required: the
        # terminate()/kill() fallback below always remains available.
        try:
            launch = resolve_onetrainer_launch(self._onetrainer_path)
        except OneTrainerLaunchError:
            return
        self._cancel_helper_process = QProcess(self)
        self._cancel_helper_process.start(
            launch.python_executable,
            [_CANCEL_HELPER_SCRIPT_PATH, self._onetrainer_path, self._job_paths.command_pipe_path],
        )

    def _on_cooperative_timeout(self) -> None:
        if self._process.state() == QProcess.ProcessState.NotRunning:
            return
        self._process.terminate()
        self._terminate_timer.start(int(TERMINATE_TIMEOUT_SECONDS * 1000))

    def _on_terminate_timeout(self) -> None:
        if self._process.state() == QProcess.ProcessState.NotRunning:
            return
        self._process.kill()

    def _on_error_occurred(self, error) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._finish("failed", "The OneTrainer process failed to start", "")

    def _on_process_finished(self, exit_code, exit_status) -> None:
        self._cooperative_timer.stop()
        self._terminate_timer.stop()

        # Checked first, deliberately: a real Cancel almost always ends
        # with QProcess.terminate()/kill() forcing the process down,
        # which Qt itself reports as exit_status == CrashExit — an
        # intentional termination we asked for must never be
        # misreported as a native crash.
        if self._cancel_requested:
            self._finish("cancelled", "", "")
            return

        if exit_status == QProcess.ExitStatus.CrashExit:
            self._finish(
                "failed",
                f"OneTrainer process terminated abnormally (native crash), exit_code={exit_code}",
                "",
            )
            return

        if exit_code != 0:
            self._finish("failed", f"OneTrainer process exited with code {exit_code}", "")
            return

        if Path(self._job_paths.expected_output_path).is_file():
            self._finish("succeeded", "", self._job_paths.expected_output_path)
        else:
            self._finish(
                "failed",
                "OneTrainer process exited successfully but no output file was found",
                "",
            )

    def _finish(self, state: str, error_message: str, final_output_path: str) -> None:
        if self._finished_emitted:
            return
        self._finished_emitted = True
        self.finished.emit(state, error_message, final_output_path)

    def _on_stdout(self) -> None:
        data = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            if line:
                self.log_line.emit(line)

    def _on_stderr(self) -> None:
        data = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            if line:
                self.log_line.emit(line)
