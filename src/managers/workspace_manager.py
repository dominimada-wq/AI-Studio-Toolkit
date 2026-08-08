from pathlib import Path
from typing import Optional

from src.domain.workspace import Workspace
from src.infrastructure.storage.workspace_storage import WorkspaceStorage


class WorkspaceManager:
    """
    Single source of truth for the current workspace.
    """

    def __init__(self):
        self.current_workspace: Optional[Workspace] = None

    @property
    def opened(self) -> bool:
        return self.current_workspace is not None

    def create(self, folder) -> Workspace:

        folder = Path(folder)

        workspace = Workspace(name=folder.name, root=folder)

        WorkspaceStorage.create_directories(folder)

        WorkspaceStorage.save(folder, workspace.to_dict())

        self.current_workspace = workspace

        return workspace

    def open(self, folder) -> Optional[Workspace]:

        folder = Path(folder)

        data = WorkspaceStorage.load(folder)

        if data is None:
            self.current_workspace = None
            return None

        self.current_workspace = Workspace.from_dict(data, root=folder)

        return self.current_workspace

    def save(self) -> None:

        if self.current_workspace is None:
            return

        WorkspaceStorage.save(
            self.current_workspace.root,
            self.current_workspace.to_dict(),
        )

    def close(self) -> None:
        self.current_workspace = None
