"""
Mission 114: resolves the concrete local launch command for ComfyUI --
Qt-free (same src/engines/ convention as onetrainer_launch.py/
comfyui_install.py), pure validation, never touches the network, never
launches anything itself (that is ComfyUILifecycleManager's job, in
src/ui/ -- the only piece of this vertical that imports Qt/QProcess).

Combines two settings resolve_comfyui_install() alone cannot: the
Python interpreter lives under comfyui_path (the data/--base-directory
root, Mission 010), while main.py lives under comfyui_install_path (the
ComfyUI Local/Desktop installation root, Mission 113) -- two roots
confirmed distinct by direct inspection of a real installation
(MISSION_113.md section 1). This resolver is the first place in the
codebase that combines both for a single purpose: building a real
launch command. It never modifies or duplicates resolve_comfyui_install()
-- ComfyUIInstallError propagates unchanged, re-raised as
ComfyUILaunchError so callers only ever catch one exception type from
this module.

Local-only by construction: comfyui_url's host must be 127.0.0.1 or
localhost (normalized to 127.0.0.1 for --listen) -- Start refuses any
other host, including 0.0.0.0, rather than ever exposing a locally
launched ComfyUI on the network just because comfyui_url happened to be
configured that way. ComfyUIEngine's own general HTTP-client contract
(any URL, local or remote) is unaffected by this restriction -- it
applies only to what Toolkit itself is willing to launch as a local
process.

--user-directory/--database-url (added after a real diagnostic
relaunch on 2026-09-11, see docs/missions/MISSION_114.md): running the
minimal command without them left ComfyUI resolving its own database
path in a way that failed on this real installation ("Failed to
initialize database ... unable to open database file") -- a real,
observed correctness gap, not a redundant argument as the pre-mission
audit had assumed. Both are derived from comfyui_path exactly like the
real ComfyUI Desktop launch command captured during that audit:
<comfyui_path>/user and sqlite:///<comfyui_path>/user/comfyui.db (three
slashes, forward-slash path, matching the exact format observed in
ComfyUI Desktop's own real logs -- never invented). Every other Desktop
argument (--front-end-root, --input-directory, --output-directory,
--extra-model-paths-config, --enable-manager, --log-stdout) is
deliberately still omitted: the same diagnostic proved the bundled pip
frontend, default custom-node scanning, and default model paths all
work correctly without them.
"""
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlparse

from src.engines.comfyui_install import ComfyUIInstallError, resolve_comfyui_install

_VENV_PYTHON_RELATIVE_PARTS = (".venv", "Scripts", "python.exe")
_LOCAL_HOSTS = {"127.0.0.1", "localhost"}
_LISTEN_HOST = "127.0.0.1"


class ComfyUILaunchError(Exception):
    """
    Raised by resolve_comfyui_launch() whenever ComfyUI cannot actually
    be launched locally from the given settings -- comfyui_path
    unset/blank or missing its .venv interpreter, comfyui_install_path
    invalid (propagated from resolve_comfyui_install()), or comfyui_url
    not local-only/missing an explicit port. Always carries an
    actionable message naming the exact path/value checked, never a
    generic one.
    """


class ComfyUILaunchConfig(NamedTuple):
    python_executable: str
    entry_point: str
    working_directory: str
    listen_host: str
    port: int
    user_directory: str
    database_url: str


def resolve_comfyui_launch(
    comfyui_path: str, comfyui_install_path: str, comfyui_url: str
) -> ComfyUILaunchConfig:
    """
    Never touches the network or launches anything -- pure filesystem/
    URL validation. Revalidated fresh on every call by its own caller
    (ComfyUILifecycleManager.start()), never cached, same principle
    already established by resolve_onetrainer_launch()'s callers.
    """
    if not comfyui_path or not comfyui_path.strip():
        raise ComfyUILaunchError(
            "ComfyUI's data folder (comfyui_path) is not configured — set it "
            "in Settings before starting ComfyUI."
        )

    root = Path(comfyui_path)
    python_executable = root.joinpath(*_VENV_PYTHON_RELATIVE_PARTS)
    if not python_executable.is_file():
        raise ComfyUILaunchError(
            f"ComfyUI's Python environment was not found at {python_executable} "
            f"— check the ComfyUI data folder (comfyui_path) in Settings."
        )

    try:
        install = resolve_comfyui_install(comfyui_install_path)
    except ComfyUIInstallError as error:
        raise ComfyUILaunchError(str(error)) from error

    parsed = urlparse(comfyui_url)
    host = parsed.hostname
    if not host:
        raise ComfyUILaunchError(f"ComfyUI URL is invalid or missing a host: {comfyui_url!r}")
    if host not in _LOCAL_HOSTS:
        raise ComfyUILaunchError(
            f"ComfyUI can only be started locally for 127.0.0.1/localhost — "
            f"comfyui_url currently targets {host!r}."
        )

    try:
        port = parsed.port
    except ValueError as error:
        raise ComfyUILaunchError(f"ComfyUI URL has an invalid port: {comfyui_url!r}") from error
    if port is None:
        raise ComfyUILaunchError(
            f"ComfyUI URL must specify an explicit port to start locally: {comfyui_url!r}."
        )

    user_directory = root / "user"
    database_path = user_directory / "comfyui.db"

    return ComfyUILaunchConfig(
        python_executable=str(python_executable),
        entry_point=install.entry_point,
        working_directory=str(root),
        listen_host=_LISTEN_HOST,
        port=port,
        user_directory=str(user_directory),
        database_url=f"sqlite:///{database_path.as_posix()}",
    )
