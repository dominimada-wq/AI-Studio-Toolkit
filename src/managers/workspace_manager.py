import os
import uuid
from pathlib import Path
from typing import Optional

from src.core.event_bus import EventBus
from src.domain.image import Image
from src.domain.workspace import Workspace
from src.infrastructure.storage.workspace_storage import (
    WorkspaceStorage,
    WorkspaceStorageError,
    WorkspaceRenamePermissionError as _StorageRenamePermissionError,
)

WORKSPACE_CREATED = "workspace.created"
WORKSPACE_OPENED = "workspace.opened"
WORKSPACE_SAVED = "workspace.saved"
WORKSPACE_CLOSED = "workspace.closed"
WORKSPACE_RENAMED = "workspace.renamed"


class WorkspaceManagerError(Exception):
    """
    Raised by WorkspaceManager when a workspace operation fails.
    Wraps infrastructure-level errors (e.g. WorkspaceStorageError) so
    that callers — in particular the UI — never need to import
    anything from src.infrastructure directly.
    """


class WorkspaceRenamePermissionError(WorkspaceManagerError):
    """
    Raised by rename() specifically when the initial folder rename
    fails with access denied (see WorkspaceRenamePermissionError in
    workspace_storage.py — Mission 027, confirmed via Process Explorer
    to be explorer.exe holding handles on the project's subfolders, not
    an application-side resource leak). current_workspace is left
    strictly untouched in this case (the physical rename never
    succeeded), exactly like any other failure of the initial rename
    step. Kept distinct from WorkspaceManagerError so the UI can show an
    actionable message without ever misclassifying an unrelated
    failure (target already exists, disk full, ...) as this one.
    """


class WorkspaceManager:
    """
    Single source of truth for the current workspace.
    """

    def __init__(self, event_bus: Optional[EventBus] = None):
        self.current_workspace: Optional[Workspace] = None
        self._event_bus = event_bus

    @property
    def opened(self) -> bool:
        return self.current_workspace is not None

    def create(self, folder) -> Workspace:

        folder = Path(folder)

        workspace = Workspace(name=folder.name, root=folder)

        try:
            WorkspaceStorage.create_directories(folder)
            WorkspaceStorage.save(folder, workspace.to_dict())
        except WorkspaceStorageError as exc:
            raise WorkspaceManagerError(str(exc)) from exc

        self.current_workspace = workspace

        self._publish(WORKSPACE_CREATED)

        return workspace

    def open(self, folder) -> Optional[Workspace]:

        folder = Path(folder)

        try:
            data = WorkspaceStorage.load(folder)
        except WorkspaceStorageError as exc:
            raise WorkspaceManagerError(str(exc)) from exc

        if data is None:
            # A failed open must never close the workspace that is
            # currently open — leave current_workspace untouched.
            return None

        self.current_workspace = Workspace.from_dict(data, root=folder)

        self._publish(WORKSPACE_OPENED)

        return self.current_workspace

    def save(self) -> None:

        if self.current_workspace is None:
            return

        try:
            WorkspaceStorage.save(
                self.current_workspace.root,
                self.current_workspace.to_dict(),
            )
        except WorkspaceStorageError as exc:
            raise WorkspaceManagerError(str(exc)) from exc

        self._publish(WORKSPACE_SAVED)

    def rename(self, new_name: str) -> bool:
        """
        Renames the current project (Mission 027): the physical folder,
        Workspace.name, and every internal path (Workspace.images,
        Character.datasets[].images, Workspace.models, Workspace.workflows,
        Character.loras[].files/thumbnail) rewritten to the new root.
        Paths located outside the old root, and every Character.name, are
        never touched.

        Deliberately idempotent, mirroring CharacterManager.update()'s
        contract: returns False (no I/O, no event) if new_name already
        matches both the folder's actual current name and Workspace.name.
        No content validation is performed here (that is the UI's
        responsibility, see RenameProjectDialog) — only filesystem
        preconditions are checked, via WorkspaceStorage.

        self.current_workspace is deliberately never mutated until both
        the physical rename and the project.json save have fully
        succeeded — see MISSION_027.md section 7 for the full rationale.
        On any failure, current_workspace is either left byte-for-byte
        untouched, or (rename succeeded, save failed) a best-effort
        filesystem rollback is attempted; either way no partial state is
        ever exposed and WORKSPACE_RENAMED is never published.
        """

        if self.current_workspace is None:
            raise WorkspaceManagerError("No workspace is currently open")

        workspace = self.current_workspace
        old_root = workspace.root
        old_root_resolved = old_root.resolve()
        old_name = workspace.name

        folder_needs_rename = new_name != old_root.name
        name_needs_update = new_name != old_name

        if not folder_needs_rename and not name_needs_update:
            return False

        new_root = (old_root.parent / new_name) if folder_needs_rename else old_root

        # Pure computation — current_workspace is not mutated by this call.
        new_data = self._build_renamed_payload(
            workspace, old_root_resolved, new_root, new_name
        )

        if folder_needs_rename:
            try:
                WorkspaceStorage.rename_folder(old_root, new_root)
            except _StorageRenamePermissionError as exc:
                # current_workspace is still exactly what it was before
                # this call — the physical rename never happened. Distinct
                # type so the UI can show an actionable message (Mission
                # 027 smoke test diagnostic: explorer.exe holding handles
                # on the project's subfolders, see MISSION_027.md section
                # 20) instead of a generic technical error.
                raise WorkspaceRenamePermissionError(str(exc)) from exc
            except WorkspaceStorageError as exc:
                raise WorkspaceManagerError(str(exc)) from exc

        try:
            WorkspaceStorage.save(new_root, new_data)
        except WorkspaceStorageError as exc:
            if folder_needs_rename:
                try:
                    WorkspaceStorage.rename_folder(new_root, old_root)
                except WorkspaceStorageError as rollback_exc:
                    permission_hint = (
                        " This rollback failure is itself an access-denied "
                        "error, most likely for the same reason as a plain "
                        "rename failure (another application — commonly a "
                        "Windows Explorer window — has a subfolder of the "
                        "project open); closing it and retrying may resolve "
                        "this without any manual recovery."
                        if isinstance(rollback_exc, _StorageRenamePermissionError)
                        else ""
                    )
                    raise WorkspaceManagerError(
                        "Rename failed while saving project.json "
                        f"({exc}), and the automatic rollback also failed "
                        f"({rollback_exc}). The project folder is now "
                        f"named '{new_root.name}' on disk at {new_root}, "
                        f"but project.json inside it was not updated and "
                        f"still reflects the previous name '{old_name}'. "
                        f"The application's in-memory state was left "
                        f"unchanged and still points to {old_root}, which "
                        f"no longer exists on disk. Manual recovery "
                        f"required: rename the folder back to "
                        f"'{old_name}' yourself, or reopen the project "
                        f"from its current location ({new_root}) and "
                        f"retry.{permission_hint}"
                    ) from rollback_exc
            raise WorkspaceManagerError(str(exc)) from exc

        self.current_workspace = Workspace.from_dict(new_data, root=new_root)

        self._publish(WORKSPACE_RENAMED)

        return True

    def _build_renamed_payload(
        self, workspace: Workspace, old_root_resolved: Path, new_root: Path, new_name: str
    ) -> dict:
        """
        Pure computation (no I/O, no mutation of `workspace`): returns a
        fresh to_dict()-shaped payload with `name` replaced and every
        path-bearing field remapped from under old_root_resolved to
        new_root via _remap_path(). Fields outside old_root_resolved, and
        Character.name, are left byte-for-byte unchanged.
        """

        data = workspace.to_dict()
        data["name"] = new_name

        for image in data["images"]:
            image["file_path"] = self._remap_path(
                image["file_path"], old_root_resolved, new_root
            )

        for character in data["characters"]:
            for dataset in character["datasets"]:
                for image in dataset["images"]:
                    image["file_path"] = self._remap_path(
                        image["file_path"], old_root_resolved, new_root
                    )
            for lora in character["loras"]:
                lora["files"] = [
                    self._remap_path(path, old_root_resolved, new_root)
                    for path in lora["files"]
                ]
                lora["thumbnail"] = self._remap_path(
                    lora["thumbnail"], old_root_resolved, new_root
                )

        for model in data["models"]:
            model["file_path"] = self._remap_path(
                model["file_path"], old_root_resolved, new_root
            )

        for workflow in data["workflows"]:
            workflow["file_path"] = self._remap_path(
                workflow["file_path"], old_root_resolved, new_root
            )

        return data

    @staticmethod
    def _remap_path(path_str: str, old_root_resolved: Path, new_root: Path) -> str:
        """
        Returns path_str unchanged if it is empty (a legitimate "no file
        associated yet" value, e.g. Model.file_path/Workflow.file_path)
        or located outside old_root_resolved. Otherwise returns the
        equivalent path under new_root. Comparison is component-by-
        component (Path.parts), never a raw string prefix check, with
        each component normalized via os.path.normcase() — a deliberate,
        explicit case-insensitive/separator-normalized comparison
        (Windows/NTFS semantics), not relied upon implicitly from
        pathlib's own cross-version behavior.
        """

        if not path_str:
            return path_str

        candidate = Path(path_str).resolve()

        old_parts = old_root_resolved.parts
        candidate_parts = candidate.parts

        if len(candidate_parts) < len(old_parts):
            return path_str

        prefix = [os.path.normcase(part) for part in candidate_parts[: len(old_parts)]]
        old_normalized = [os.path.normcase(part) for part in old_parts]

        if prefix != old_normalized:
            return path_str

        remainder = candidate_parts[len(old_parts):]
        return str(new_root.joinpath(*remainder)) if remainder else str(new_root)

    def close(self) -> None:
        self.current_workspace = None
        self._publish(WORKSPACE_CLOSED)

    def add_images(self, paths: list) -> int:
        """
        Append paths not already present in the workspace's images.
        Returns the number of images actually added (paths already
        present, or duplicated within the input itself, are skipped).
        Each accepted path becomes its own Image (Mission 011: Workspace
        owns its own Image pool, independent from Dataset.images — see
        Image.list_from_data() for the legacy-format read path).
        """

        if self.current_workspace is None:
            return 0

        seen = {image.file_path for image in self.current_workspace.images}
        new_images = []

        for path in paths:
            if path in seen:
                continue
            seen.add(path)
            new_images.append(Image(image_id=str(uuid.uuid4()), file_path=path))

        if not new_images:
            return 0

        self.current_workspace.images.extend(new_images)

        self.save()

        return len(new_images)

    def _publish(self, event_name: str) -> None:

        if self._event_bus is None:
            return

        payload = (
            self.current_workspace.to_dict()
            if self.current_workspace is not None
            else None
        )

        self._event_bus.publish(event_name, payload)
