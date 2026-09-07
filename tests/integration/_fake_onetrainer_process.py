"""
Mission 100: a deterministic double for OneTrainer's scripts/
train_remote.py, used to exercise TrainingJobRunner's full QProcess
lifecycle (success, failure, crash, cooperative Cancel, terminate/kill
fallback) without ever needing the real OneTrainer runtime or a GPU.
Never imported — always launched as its own process, exactly like the
real script would be, so the runner code under test is byte-for-byte
identical to what drives the real OneTrainer process.

Accepts the same two CLI arguments TrainingJobRunner actually passes:
    --config-path <path> --command-path <path>

Behavior is controlled entirely through environment variables (so the
runner's own launch-argument-building code is exercised unchanged,
never branched for tests):

    FAKE_EXIT_CODE            int, default "0"
    FAKE_WRITE_OUTPUT         "1"/"0", default "1" — write a fake
                              .safetensors at the config's
                              output_model_destination
    FAKE_CRASH                "1"/"0", default "0" — abort() instead of
                              a normal exit (QProcess sees CrashExit)
    FAKE_RESPECT_STOP         "1"/"0", default "1" — poll command.pipe
                              for a real pickled TrainCommands with
                              get_stop_command() True (needs
                              FAKE_MODULES_ROOT on sys.path, same
                              contract as the real
                              modules.util.commands.TrainCommands)
    FAKE_MODULES_ROOT         path prepended to sys.path to import the
                              (real or fake) TrainCommands class from,
                              only consulted when FAKE_RESPECT_STOP=1
    FAKE_RUN_SECONDS          float, default "0" — how long to keep
                              polling/running before exiting on its own
                              if no stop command arrives
"""
import json
import os
import pickle
import sys
import time


def _arg(name):
    for i, value in enumerate(sys.argv):
        if value == name and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return None


def _env_bool(name, default):
    return os.environ.get(name, default) == "1"


def main():
    config_path = _arg("--config-path")
    command_path = _arg("--command-path")

    exit_code = int(os.environ.get("FAKE_EXIT_CODE", "0"))
    write_output = _env_bool("FAKE_WRITE_OUTPUT", "1")
    crash = _env_bool("FAKE_CRASH", "0")
    respect_stop = _env_bool("FAKE_RESPECT_STOP", "1")
    modules_root = os.environ.get("FAKE_MODULES_ROOT", "")
    run_seconds = float(os.environ.get("FAKE_RUN_SECONDS", "0"))

    print("fake OneTrainer process starting", flush=True)
    print("simulated step 1/10", file=sys.stderr, flush=True)

    stopped_cooperatively = False
    deadline = time.time() + run_seconds
    poll_interval = 0.05
    while time.time() < deadline:
        if respect_stop and command_path and _stop_requested(command_path, modules_root):
            stopped_cooperatively = True
            break
        time.sleep(poll_interval)

    if crash:
        print("fake OneTrainer process aborting (simulated crash)", file=sys.stderr, flush=True)
        sys.stderr.flush()
        os.abort()

    if write_output and config_path:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        output_path = config["output_model_destination"]
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(b"fake-lora-safetensors-bytes")

    print(f"fake OneTrainer process exiting, stopped_cooperatively={stopped_cooperatively}", flush=True)
    return exit_code


def _stop_requested(command_path, modules_root):
    if modules_root:
        sys.path.insert(0, modules_root)
    try:
        with open(command_path, "rb") as f:
            commands = pickle.load(f)
    except (FileNotFoundError, EOFError, pickle.UnpicklingError, ImportError, ModuleNotFoundError):
        return False
    try:
        return bool(commands.get_stop_command())
    except AttributeError:
        return False


if __name__ == "__main__":
    sys.exit(main())
