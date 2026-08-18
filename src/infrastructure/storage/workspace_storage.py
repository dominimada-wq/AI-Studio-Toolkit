import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class WorkspaceStorageError(Exception):
    """Raised when a workspace cannot be read from or written to disk."""


class WorkspaceRenamePermissionError(WorkspaceStorageError):
    """
    Raised specifically by rename_folder() when the OS reports access
    denied (Python's PermissionError — WinError 5 on Windows) while
    renaming the workspace's root folder. Mission 027 smoke test: real
    diagnostic with Process Explorer confirmed this is caused by
    explorer.exe holding open handles on the project's subfolders
    (images/outputs/models/training/datasets/logs/captions/...) when a
    Windows Explorer window is browsing one of them — not a resource
    leak inside this application (see MISSION_027.md section 20 for the
    full discriminating test). Kept as a distinct type, never raised for
    any other OSError (target already exists, disk full, cross-device
    rename, ...), so a caller can offer an actionable message without
    ever misclassifying an unrelated failure as this specific case.
    """


class WorkspaceStorage:

    WORKSPACE_FILE = "project.json"  # name kept for backward compatibility (Q1)

    DIRECTORIES = [
        "images",
        "datasets",
        "datasets/train",
        "datasets/validation",
        "captions",
        "models",
        "models/checkpoints",
        "models/loras",
        "models/vae",
        "models/embeddings",
        "outputs",
        "training",
        "logs",
    ]

    @staticmethod
    def create_directories(folder) -> None:

        folder = Path(folder)

        try:
            folder.mkdir(parents=True, exist_ok=True)

            for directory in WorkspaceStorage.DIRECTORIES:
                (folder / directory).mkdir(parents=True, exist_ok=True)

        except OSError as exc:
            logger.error(
                "Failed to create workspace directories in %s: %s", folder, exc
            )
            raise WorkspaceStorageError(
                f"Could not create workspace folders in {folder}"
            ) from exc

    @staticmethod
    def load(folder) -> Optional[dict]:

        folder = Path(folder)
        file = folder / WorkspaceStorage.WORKSPACE_FILE

        if not file.exists():
            return None

        try:
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)

        except json.JSONDecodeError as exc:
            logger.error("Corrupted workspace file %s: %s", file, exc)
            raise WorkspaceStorageError(f"{file} is not valid JSON") from exc

        except OSError as exc:
            logger.error("Failed to read workspace file %s: %s", file, exc)
            raise WorkspaceStorageError(f"Could not read {file}") from exc

    @staticmethod
    def save(folder, data: dict) -> None:
        """
        Writes project.json atomically: the content is fully written to a
        temporary file in the same folder first, then swapped into place
        via os.replace() (same-volume, OS-atomic on both POSIX and
        Windows). Unlike a direct open(..., "w"), this never truncates
        the existing project.json before the new content is known to be
        complete — a failure at any point before the swap (including a
        mid-write failure such as a full disk) leaves the previous file
        byte-for-byte untouched. This guarantee is relied upon by
        WorkspaceManager.rename()'s rollback strategy (Mission 027).
        """

        folder = Path(folder)
        target = folder / WorkspaceStorage.WORKSPACE_FILE

        tmp_path = None
        try:
            fd, tmp_name = tempfile.mkstemp(
                dir=folder, prefix=".project_", suffix=".tmp"
            )
            tmp_path = Path(tmp_name)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                os.replace(tmp_path, target)
                tmp_path = None
            finally:
                if tmp_path is not None and tmp_path.exists():
                    tmp_path.unlink()

        except OSError as exc:
            logger.error("Failed to write workspace file in %s: %s", folder, exc)
            raise WorkspaceStorageError(
                f"Could not write project.json in {folder}"
            ) from exc

    @staticmethod
    def rename_folder(old_root, new_root) -> None:
        """
        Renames the workspace's root folder on disk — the one genuinely
        non-local filesystem step in WorkspaceManager.rename() (Mission
        027). A same-volume directory rename is atomic at the OS level
        (Windows MoveFileEx / POSIX rename()): it either fully succeeds
        or fully fails, never leaves a half-renamed folder. Raises
        WorkspaceStorageError if new_root already exists (never
        overwrites an existing folder) or on any OSError (permission
        denied, locked file, cross-device rename, ...).
        """

        old_root = Path(old_root)
        new_root = Path(new_root)

        if new_root.exists():
            raise WorkspaceStorageError(
                f"A folder already exists at {new_root}"
            )

        try:
            old_root.rename(new_root)
        except PermissionError as exc:
            logger.error(
                "Access denied while renaming workspace folder %s to %s: %s",
                old_root, new_root, exc,
            )
            raise WorkspaceRenamePermissionError(
                f"Could not rename {old_root} to {new_root}: {exc}"
            ) from exc
        except OSError as exc:
            logger.error(
                "Failed to rename workspace folder %s to %s: %s",
                old_root, new_root, exc,
            )
            raise WorkspaceStorageError(
                f"Could not rename {old_root} to {new_root}: {exc}"
            ) from exc
