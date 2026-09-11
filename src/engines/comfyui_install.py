"""
Mission 113: resolves and validates the ComfyUI Local/Desktop
installation root -- Qt-free (same src/engines/ convention as
onetrainer_launch.py), pure filesystem existence check, never the
network, never a process launch. Deliberately distinct from
ApplicationSettings.comfyui_path (the data/--base-directory root,
confirmed by direct inspection to be a completely separate folder from
the ComfyUI Local/Desktop installation itself on a real machine) and
from ComfyUIEngine.check_connection() (Mission 112 -- HTTP reachability
of an already-running backend, an entirely different concept from "is
a local installation present on disk").

ComfyUI Local only. A future ComfyUI Cloud provider/executor is a
separate concept -- this module never assumes every ComfyUI usage
requires a local installation.

Building an actual runnable launch command (arguments, working
directory, python executable) is deliberately deferred to a future
Start mission -- this module only proves the entry point exists.
"""
from pathlib import Path
from typing import NamedTuple

_ENTRY_POINT_RELATIVE_PARTS = ("resources", "ComfyUI", "main.py")


class ComfyUIInstallError(Exception):
    """
    Raised by resolve_comfyui_install() whenever ComfyUI Local/Desktop
    cannot be confirmed present from the current
    ApplicationSettings.comfyui_install_path state — path unset/blank,
    or the expected entry point (resources/ComfyUI/main.py) missing at
    that root. Always carries an actionable message naming the exact
    path checked, never a generic one.
    """


class ComfyUIInstallConfig(NamedTuple):
    entry_point: str
    install_root: str


def resolve_comfyui_install(comfyui_install_path: str) -> ComfyUIInstallConfig:
    """
    Never touches the network, never launches anything, never imports
    anything from ComfyUI itself — pure filesystem existence check.
    Validates only that resources/ComfyUI/main.py exists as a file
    under comfyui_install_path; a folder existing without this entry
    point is not a valid installation.
    """
    if not comfyui_install_path or not comfyui_install_path.strip():
        raise ComfyUIInstallError(
            "ComfyUI (Local/Desktop) installation folder is not configured — "
            "set it in Settings before validating the installation."
        )

    root = Path(comfyui_install_path)
    entry_point = root.joinpath(*_ENTRY_POINT_RELATIVE_PARTS)

    if not entry_point.is_file():
        raise ComfyUIInstallError(
            f"ComfyUI's entry point was not found at {entry_point} — check "
            f"the ComfyUI installation folder in Settings."
        )

    return ComfyUIInstallConfig(entry_point=str(entry_point), install_root=str(root))
