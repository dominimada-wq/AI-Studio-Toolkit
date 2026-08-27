import json
import logging
import os
import shutil
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
            # Mission 075: new_root.parent already always exists for this
            # primitive's original use (renaming the workspace root itself,
            # where the parent is simply the pre-existing folder's own
            # parent) — this lazily creates it for the new use introduced
            # by Mission 075 (moving an entity's folder into a `.trash/`
            # staging area that may not exist yet), a no-op everywhere else.
            new_root.parent.mkdir(parents=True, exist_ok=True)
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

    @staticmethod
    def is_inside(path, root) -> bool:
        """
        True if `path` resolves to a location under `root` (root itself
        included), compared component-by-component (Path.parts) with
        each component normalized via os.path.normcase() — the same
        explicit Windows/NTFS case-insensitive comparison technique
        already established by WorkspaceManager._remap_path() (Mission
        027), reproduced here as a small standalone predicate rather
        than imported (different layer — this is Infrastructure, pure
        and Domain-free, while _remap_path() is a private Manager
        helper that also rewrites the path, not just tests it). Safe
        even if `path` no longer exists on disk (resolve() without
        strict=True).
        """

        candidate_parts = Path(path).resolve().parts
        root_parts = Path(root).resolve().parts

        if len(candidate_parts) < len(root_parts):
            return False

        prefix = [os.path.normcase(part) for part in candidate_parts[: len(root_parts)]]
        root_normalized = [os.path.normcase(part) for part in root_parts]

        return prefix == root_normalized

    @staticmethod
    def copy_into_workspace(source, destination_folder, workspace_root, target_name=None) -> Path:
        """
        Returns a Path usable as an Image's internal file_path for
        `source` (Mission 028):

        - if `source` already resolves to a location anywhere under
          `workspace_root` (e.g. a generated image already under
          <root>/outputs/ — Mission 013/014's Accept flow — or a file
          re-selected directly from <root>/images/), it is returned
          as-is, resolved — no I/O, shutil.copy2() is never called.
          This is what keeps a source already sitting exactly at the
          destination folder from ever being copied onto itself
          (which would otherwise raise shutil.SameFileError), and what
          keeps Accept's own add_images() call from silently
          duplicating every accepted generation onto disk.
        - otherwise `source` is genuinely external: it is copied into
          `destination_folder`, preserving metadata (shutil.copy2).
          `target_name` (Mission 028 collision UX, second smoke test):
          when the caller already resolved a specific destination
          filename with the user (e.g. via WorkspaceManager.
          preview_collisions() and a confirmation dialog), it is used
          verbatim — re-checked for existence right before the copy
          (never silently overwritten even then) and rejected with
          WorkspaceStorageError if it is somehow already taken by the
          time the copy actually runs. Left as None (the default, used
          by every caller that never showed the user a collision
          prompt — e.g. direct/programmatic/test use), the destination
          name is resolved automatically and silently via
          resolve_collision_free_name() exactly as before — this
          automatic fallback is a property of the primitive itself,
          kept intentionally, never removed; only the UI-driven import
          flow (ImagesPage/DatasetsPage) no longer relies on it without
          asking first. Any partial file left behind by a failed copy
          is removed best-effort before the wrapped exception is
          raised — a failed copy can only ever leave behind a file
          under a name that did not previously exist, never corrupt an
          existing one.

        Raises WorkspaceStorageError on any OSError (source missing,
        permission denied, disk full, destination inaccessible, ...),
        or if `target_name` is given but already taken.
        """

        source = Path(source)
        destination_folder = Path(destination_folder)

        if WorkspaceStorage.is_inside(source, workspace_root):
            return source.resolve()

        try:
            destination_folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.error(
                "Failed to create destination folder %s: %s",
                destination_folder, exc,
            )
            raise WorkspaceStorageError(
                f"Could not create destination folder {destination_folder}"
            ) from exc

        if target_name is not None:
            target = destination_folder / target_name
            if target.exists():
                raise WorkspaceStorageError(
                    f"{target} already exists — the requested name is no "
                    f"longer available"
                )
        else:
            target = WorkspaceStorage.resolve_collision_free_name(source, destination_folder)

        try:
            shutil.copy2(source, target)
        except OSError as exc:
            logger.error(
                "Failed to copy %s into %s: %s", source, destination_folder, exc
            )
            if target.exists():
                try:
                    target.unlink()
                except OSError:
                    pass
            raise WorkspaceStorageError(
                f"Could not copy {source} into {destination_folder}"
            ) from exc

        return target.resolve()

    @staticmethod
    def resolve_collision_free_name(source, destination_folder, also_avoid=frozenset()) -> Path:
        """
        Returns a Path inside destination_folder guaranteed not to
        already exist on disk and not to be one of the names listed in
        `also_avoid`: source.name if free, otherwise "<stem>_1<suffix>",
        "_2", ... — never overwrites an existing file, silently or
        otherwise (Mission 028). No artificial limit on the suffix
        counter.

        `also_avoid` (Mission 028 second smoke test) lets a caller
        reserve names that are not yet on disk — used by
        WorkspaceManager/DatasetManager.preview_collisions() to predict
        the real outcome of a multi-file batch (where an earlier file
        in the same batch has not been physically copied yet at
        preview time, but will have claimed its name by the time this
        one is actually copied for real). copy_into_workspace()'s own
        real, sequential copy never needs this parameter — by the time
        it resolves a name for one file, every prior file in the batch
        has already been physically written, so disk state alone is
        already authoritative.
        """

        source = Path(source)

        def _is_free(name: str) -> bool:
            return name not in also_avoid and not (destination_folder / name).exists()

        if _is_free(source.name):
            return destination_folder / source.name

        stem, suffix = source.stem, source.suffix
        n = 1
        while True:
            candidate_name = f"{stem}_{n}{suffix}"
            if _is_free(candidate_name):
                return destination_folder / candidate_name
            n += 1

    @staticmethod
    def delete_folder(path) -> None:
        """
        Permanently deletes `path` and everything inside it (Mission
        075) — the final, non-reversible step of a transactional
        physical deletion, used only after the corresponding Domain
        mutation is already durably persisted (never as a rollback
        step). Idempotent: a path that no longer exists is treated as
        already deleted, not an error, since a caller can never
        meaningfully distinguish "already gone" from "nothing to do"
        here. Raises WorkspaceStorageError on any OSError — shutil.
        rmtree() can fail partway through a large tree (a locked file,
        a permission error), potentially leaving some entries already
        removed and others not; this surfaces as a single failure
        rather than partial bookkeeping, consistent with this
        primitive only ever being used for best-effort cleanup by its
        caller.
        """

        path = Path(path)

        if not path.exists():
            return

        try:
            shutil.rmtree(path)
        except OSError as exc:
            logger.error("Failed to delete folder %s: %s", path, exc)
            raise WorkspaceStorageError(f"Could not delete folder {path}") from exc
