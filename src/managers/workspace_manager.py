from pathlib import Path
from typing import Optional

from src.core.event_bus import EventBus
from src.domain.workspace import Workspace
from src.infrastructure.storage.workspace_storage import (
    WorkspaceStorage,
    WorkspaceStorageError,
)

WORKSPACE_CREATED = "workspace.created"
WORKSPACE_OPENED = "workspace.opened"
WORKSPACE_SAVED = "workspace.saved"
WORKSPACE_CLOSED = "workspace.closed"


class WorkspaceManagerError(Exception):
    """
    Raised by WorkspaceManager when a workspace operation fails.
    Wraps infrastructure-level errors (e.g. WorkspaceStorageError) so
    that callers — in particular the UI — never need to import
    anything from src.infrastructure directly.
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

    def close(self) -> None:
        self.current_workspace = None
        self._publish(WORKSPACE_CLOSED)

    def add_images(self, paths: list) -> int:
        """
        Append paths not already present in the workspace's images.
        Returns the number of images actually added (paths already
        present, or duplicated within the input itself, are skipped).
        """

        if self.current_workspace is None:
            return 0

        seen = set(self.current_workspace.images)
        new_paths = []

        for path in paths:
            if path in seen:
                continue
            seen.add(path)
            new_paths.append(path)

        if not new_paths:
            return 0

        self.current_workspace.images.extend(new_paths)

        self.save()

        return len(new_paths)

    def _publish(self, event_name: str) -> None:

        if self._event_bus is None:
            return

        payload = (
            self.current_workspace.to_dict()
            if self.current_workspace is not None
            else None
        )

        self._event_bus.publish(event_name, payload)
