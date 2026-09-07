"""
Mission 100: resolves and validates the concrete OneTrainer launch
configuration from ApplicationSettings.onetrainer_path -- Qt-free (same
src/engines/ convention as onetrainer_config.py), so both TrainingPage
(to decide whether Start should be enabled, MISSION_100.md section 6
"UI") and the QProcess-owning runner (src/ui/, to revalidate right
before actually launching, section 6 "Runner / couche fonctionnelle")
share the exact same validation, never two independently-drifting
implementations.

ApplicationSettings.python_path is deliberately never used here.
Verified against the Blueprint (01_PRODUCT_REQUIREMENTS.md section 8):
"Python" is listed as its own standalone Settings item, structurally
coordinate with OneTrainer/Kohya_ss/ComfyUI/Fooocus/Forge/
AUTOMATIC1111 -- never documented anywhere as "the interpreter
OneTrainer specifically uses". The only interpreter guaranteed to carry
OneTrainer's own installed dependencies (torch, xformers, ...) is its
own bundled venv, always at <onetrainer_path>/venv/Scripts/python.exe
on Windows -- derived here, never a second configurable setting.
"""
from pathlib import Path
from typing import NamedTuple

_VENV_PYTHON_RELATIVE_PARTS = ("venv", "Scripts", "python.exe")
_TRAIN_REMOTE_SCRIPT_RELATIVE_PARTS = ("scripts", "train_remote.py")


class OneTrainerLaunchError(Exception):
    """
    Raised by resolve_onetrainer_launch() whenever OneTrainer cannot
    actually be launched from the current ApplicationSettings state —
    onetrainer_path unset/blank, or the expected venv interpreter/
    scripts/train_remote.py missing at that root. Always carries an
    actionable message (MISSION_100.md section 6) — never a generic one.
    """


class OneTrainerLaunchConfig(NamedTuple):
    python_executable: str
    script_path: str
    working_directory: str


def resolve_onetrainer_launch(onetrainer_path: str) -> OneTrainerLaunchConfig:
    """
    Never touches the network or the GPU, never imports anything from
    OneTrainer itself — pure filesystem existence checks. Called twice
    in the real flow (MISSION_100.md section 6): once by TrainingPage
    to decide whether the Start button is enabled, once again by the
    runner right before QProcess.start() (a path valid when the UI was
    drawn may have become invalid by the time Start is actually
    clicked — never trusted from the button state alone).
    """
    if not onetrainer_path or not onetrainer_path.strip():
        raise OneTrainerLaunchError(
            "OneTrainer is not configured — set the OneTrainer installation "
            "folder in Settings before starting a training."
        )

    root = Path(onetrainer_path)
    python_executable = root.joinpath(*_VENV_PYTHON_RELATIVE_PARTS)
    script_path = root.joinpath(*_TRAIN_REMOTE_SCRIPT_RELATIVE_PARTS)

    if not python_executable.is_file():
        raise OneTrainerLaunchError(
            f"OneTrainer's Python environment was not found at "
            f"{python_executable} — check the OneTrainer installation "
            f"folder in Settings."
        )
    if not script_path.is_file():
        raise OneTrainerLaunchError(
            f"OneTrainer's train_remote.py was not found at {script_path} — "
            f"check the OneTrainer installation folder in Settings."
        )

    return OneTrainerLaunchConfig(
        python_executable=str(python_executable),
        script_path=str(script_path),
        working_directory=str(root),
    )
