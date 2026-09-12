"""
Mission 119: resolves the concrete local launch command for Forge --
Qt-free (same src/engines/ convention as comfyui_launch.py/
onetrainer_launch.py/forge_install.py), pure validation, never touches
the network, never launches anything itself (that is
ForgeLifecycleManager's job, in src/ui/).

Deliberately diverges from resolve_comfyui_launch() wherever Forge's
own launch mechanism requires it (per the architect's explicit
instruction not to copy the ComfyUI mechanism mechanically):

- Forge's only entry point is run.bat, a batch script -- not a directly
  executable .exe like ComfyUI's venv python.exe. QProcess cannot
  execute a .bat file directly on Windows (confirmed empirically: a
  bare QProcess.start("run.bat", []) never even reaches "started").
  Start therefore always launches via "cmd.exe" ["/c", run_bat_path] --
  see ForgeLifecycleManager's own docstring for what that process tree
  actually looks like and how Stop handles it.

- Toolkit never builds Forge's own command-line arguments (--api,
  --listen, --port, etc.) the way it builds ComfyUI's -- those live
  inside webui-user.bat's own COMMANDLINE_ARGS, a file the architect
  owns and edits manually, per ForgeEngine's own pre-existing,
  unchanged contract (Mission 107: "it never activates --api ... a
  prerequisite the architect must satisfy manually, exactly like
  ComfyUI/OneTrainer"). forge_url is used here only to validate a
  local-only target with an explicit port (same safety principle as
  ComfyUI: Start refuses anything but 127.0.0.1/localhost) and to let
  ForgeLifecycleManager build the readiness-check ForgeEngine against
  the right port -- never to construct argv.

- extra_path_dirs (confirmed necessary by a real empirical test against
  a real portable Forge installation): run.bat's own internal
  `call environment.bat` / `call webui-user.bat` lines use bare
  filenames, relying on cmd.exe's current-directory search. Windows
  disables that search system-wide whenever the (commonly-set,
  security-hardening) NoDefaultCurrentDirectoryInExePath environment
  variable is present -- confirmed set on the machine this mission was
  developed on -- regardless of whether cmd.exe was launched
  interactively, via double-click, or via /c. The fix applied here is
  scoped to this one child process only (never the registry, never any
  other process, never a rewrite of the vendor-shipped run.bat itself):
  prepend the Forge install root and its webui/ subfolder to the
  child's own PATH, so cmd.exe's bare-name resolution succeeds via PATH
  search even when its own current-directory search is disabled.
  Verified end-to-end against a real installation: without this,
  run.bat fails at its very first line ("'environment.bat' n'est pas
  reconnu..."); with it, the full chain (run.bat -> environment.bat ->
  webui-user.bat -> webui.bat -> python.exe launch.py) starts correctly.
"""
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlparse

from src.engines.forge_install import ForgeInstallError, resolve_forge_install

_LOCAL_HOSTS = {"127.0.0.1", "localhost"}
_LISTEN_HOST = "127.0.0.1"


class ForgeLaunchError(Exception):
    """
    Raised by resolve_forge_launch() whenever Forge cannot actually be
    launched locally from the given settings -- forge_path unset/blank
    or missing run.bat (propagated from resolve_forge_install()), or
    forge_url not local-only/missing an explicit port. Always carries
    an actionable message naming the exact path/value checked, never a
    generic one.
    """


class ForgeLaunchConfig(NamedTuple):
    working_directory: str
    run_bat_path: str
    extra_path_dirs: tuple
    listen_host: str
    port: int


def resolve_forge_launch(forge_path: str, forge_url: str) -> ForgeLaunchConfig:
    """
    Never touches the network or launches anything -- pure filesystem/
    URL validation. Revalidated fresh on every call by its own caller
    (ForgeLifecycleManager.start()), never cached, same principle
    already established by resolve_comfyui_launch()'s callers.
    """
    try:
        install = resolve_forge_install(forge_path)
    except ForgeInstallError as error:
        raise ForgeLaunchError(str(error)) from error

    parsed = urlparse(forge_url)
    host = parsed.hostname
    if not host:
        raise ForgeLaunchError(f"Forge URL is invalid or missing a host: {forge_url!r}")
    if host not in _LOCAL_HOSTS:
        raise ForgeLaunchError(
            f"Forge can only be started locally for 127.0.0.1/localhost — "
            f"forge_url currently targets {host!r}."
        )

    try:
        port = parsed.port
    except ValueError as error:
        raise ForgeLaunchError(f"Forge URL has an invalid port: {forge_url!r}") from error
    if port is None:
        raise ForgeLaunchError(
            f"Forge URL must specify an explicit port to start locally: {forge_url!r}."
        )

    root = Path(install.install_root)

    return ForgeLaunchConfig(
        working_directory=str(root),
        run_bat_path=install.entry_point,
        extra_path_dirs=(str(root), str(root / "webui")),
        listen_host=_LISTEN_HOST,
        port=port,
    )
