"""
Mission 113: resolves and validates the local Forge installation root —
Qt-free (same src/engines/ convention as onetrainer_launch.py and
comfyui_install.py), pure filesystem existence check, never the
network, never a process launch. Distinct from ForgeEngine.
check_connection() (Mission 112 -- HTTP reachability of an already-
running backend, an entirely different concept from "is a local
installation present on disk").

Validates only run.bat at the installation root — confirmed by direct
inspection to be the correct, stable entry point for a real portable
Forge installation (run.bat -> environment.bat sets up the portable
Python/PATH before invoking webui-user.bat -> webui.bat -> launch.py;
calling launch.py directly without this environment setup is fragile).
No forge_launcher_path setting exists or is needed — the launcher is
deterministic from the installation root alone.

Building an actual runnable launch command is deliberately deferred to
a future Start mission -- this module only proves the entry point
exists.
"""
from pathlib import Path
from typing import NamedTuple

_ENTRY_POINT_RELATIVE_PARTS = ("run.bat",)


class ForgeInstallError(Exception):
    """
    Raised by resolve_forge_install() whenever a local Forge
    installation cannot be confirmed present from the current
    ApplicationSettings.forge_path state — path unset/blank, or the
    expected entry point (run.bat) missing at that root. Always
    carries an actionable message naming the exact path checked, never
    a generic one.
    """


class ForgeInstallConfig(NamedTuple):
    entry_point: str
    install_root: str


def resolve_forge_install(forge_path: str) -> ForgeInstallConfig:
    """
    Never touches the network, never launches anything — pure
    filesystem existence check. Validates only that run.bat exists as
    a file directly under forge_path; a folder existing without this
    entry point is not a valid installation.
    """
    if not forge_path or not forge_path.strip():
        raise ForgeInstallError(
            "Forge installation folder is not configured — set it in "
            "Settings before validating the installation."
        )

    root = Path(forge_path)
    entry_point = root.joinpath(*_ENTRY_POINT_RELATIVE_PARTS)

    if not entry_point.is_file():
        raise ForgeInstallError(
            f"Forge's entry point was not found at {entry_point} — check "
            f"the Forge installation folder in Settings."
        )

    return ForgeInstallConfig(entry_point=str(entry_point), install_root=str(root))
