"""
Mission 114: a deterministic double for ComfyUI's main.py, used to
exercise ComfyUILifecycleManager's QProcess handling (started, crashed/
exited before readiness, terminate()/kill() escalation) without ever
needing a real ComfyUI installation or GPU. Never imported — always
launched as its own process, exactly like the real main.py would be.

Behavior is controlled entirely through environment variables:

    FAKE_EXIT_CODE     int, default "0" — exit code once FAKE_RUN_SECONDS
                       elapses without being killed first
    FAKE_RUN_SECONDS   float, default "3600" — how long to keep running
                       (a long default so "still running, waiting to be
                       terminated" is the default shape; tests that want
                       an early exit set this low instead)

ComfyUI has no known cooperative shutdown protocol in this codebase's
scope (unlike OneTrainer's command.pipe) — this fake only needs to stay
alive until terminate()/kill() ends it, or exit on its own to simulate
a crash/early exit before readiness.
"""
import os
import sys
import time


def main():
    exit_code = int(os.environ.get("FAKE_EXIT_CODE", "0"))
    run_seconds = float(os.environ.get("FAKE_RUN_SECONDS", "3600"))

    print("fake ComfyUI process starting", flush=True)

    deadline = time.time() + run_seconds
    while time.time() < deadline:
        time.sleep(0.05)

    print("fake ComfyUI process exiting on its own", flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
