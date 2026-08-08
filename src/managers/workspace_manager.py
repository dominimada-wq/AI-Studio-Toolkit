from pathlib import Path
from typing import Optional

from src.core.event_bus import EventBus
from src.domain.workspace import Workspace
from src.infrastructure.storage.workspace_storage import WorkspaceStorage

WORKSPACE_CREATED = "workspace.created"
WORKSPACE_OPENED = "workspace.opened"
WORKSPACE_SAVED = "workspace.saved"
WORKSPACE_CLOSED = "workspace.closed"


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

        WorkspaceStorage.create_directories(folder)

        WorkspaceStorage.save(folder, workspace.to_dict())

        self.current_workspace = workspace

        self._publish(WORKSPACE_CREATED)

        return workspace

    def open(self, folder) -> Optional[Workspace]:

        folder = Path(folder)

        data = WorkspaceStorage.load(folder)

        if data is None:
            self.current_workspace = None
            return None

        self.current_workspace = Workspace.from_dict(data, root=folder)

        self._publish(WORKSPACE_OPENED)

        return self.current_workspace

    def save(self) -> None:

        if self.current_workspace is None:
            return

        WorkspaceStorage.save(
            self.current_workspace.root,
            self.current_workspace.to_dict(),
        )

        self._publish(WORKSPACE_SAVED)

    def close(self) -> None:
        self.current_workspace = None
        self._publish(WORKSPACE_CLOSED)

    def _publish(self, event_name: str) -> None:

        if self._event_bus is None:
            return

        payload = (
            self.current_workspace.to_dict()
            if self.current_workspace is not None
            else None
        )

        self._event_bus.publish(event_name, payload)
