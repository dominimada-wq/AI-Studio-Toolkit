"""
Mission 100: single-responsibility helper — emits one real, correctly-
typed TrainCommands.stop() command into an already-existing
command.pipe. Launched as its own OS process using OneTrainer's own
Python interpreter (<onetrainer_path>/venv/Scripts/python.exe) — never
imported by, and never run inside, AI Studio Toolkit's main PySide6
process. That boundary is deliberate (MISSION_100.md section 3/8): the
main process must never load OneTrainer's own runtime/package, yet
train_remote.py's command_thread_function() requires an actual pickled
modules.util.commands.TrainCommands instance — pickle requires the
exact same importable class on both the writing and reading side, so
only a process that genuinely runs under OneTrainer's own environment
can produce a valid one.

This script does exactly one thing and nothing else: it never creates
a Trainer, never reads the training configuration, never touches the
GPU, never becomes a second orchestration layer over OneTrainer. If the
cooperative stop is not delivered in time (this helper fails to start,
the interpreter/path is wrong, or OneTrainer's own command reader
thread never picks it up), the caller's QProcess.terminate()/kill()
fallback (MISSION_100.md section 8) remains available regardless — this
script's success or failure is never itself a precondition for
cancelling a Job.

Usage:
    <onetrainer_path>/venv/Scripts/python.exe onetrainer_cancel_helper.py \
        <onetrainer_path> <command_pipe_path>

Exit code 0 on success. Any failure (bad arguments, TrainCommands not
importable at the given onetrainer_path, or a filesystem error writing
command_pipe_path) is reported on stderr and a non-zero exit code —
never a silent no-op, since the caller needs to be able to tell it
apart from the case where TrainCommands.stop() really was written.
"""
import pickle
import sys


def main(argv) -> int:
    if len(argv) != 3:
        print(
            "usage: onetrainer_cancel_helper.py <onetrainer_path> <command_pipe_path>",
            file=sys.stderr,
        )
        return 2

    onetrainer_path, command_pipe_path = argv[1], argv[2]

    sys.path.insert(0, onetrainer_path)
    try:
        from modules.util.commands.TrainCommands import TrainCommands
    except ImportError as exc:
        print(f"Could not import OneTrainer's TrainCommands from {onetrainer_path!r}: {exc}", file=sys.stderr)
        return 1

    commands = TrainCommands()
    commands.stop()

    try:
        with open(command_pipe_path, "wb") as f:
            pickle.dump(commands, f)
    except OSError as exc:
        print(f"Could not write the stop command to {command_pipe_path!r}: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
