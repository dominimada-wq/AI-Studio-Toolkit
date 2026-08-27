from typing import Optional

from src.domain.settings import Settings
from src.managers.workspace_manager import WorkspaceManager, WorkspaceManagerError


class SettingsManager:
    """
    Coordinates read/write access to the current Workspace's Settings.
    Unlike every other Manager in this project, there is nothing to
    select and nothing to reset on a workspace switch — settings is
    read live from workspace_manager.current_workspace on every access.
    Operates exclusively on workspace_manager.current_workspace.settings
    — never touches storage or Qt directly; persistence is delegated to
    WorkspaceManager.save().
    """

    def __init__(self, workspace_manager: WorkspaceManager):
        self._workspace_manager = workspace_manager

    @property
    def settings(self) -> Settings:
        workspace = self._workspace_manager.current_workspace
        if workspace is None:
            return Settings()
        return workspace.settings

    def update(
        self,
        theme: Optional[str] = None,
        language: Optional[str] = None,
    ) -> bool:
        """
        Mission 077: if save() fails, settings.theme/settings.language are
        restored to their exact previous values on this same Settings
        instance — same snapshot-and-rollback contract already used by
        every other Manager's scalar field updates (e.g.
        CharacterManager.update()), rather than replacing the instance.
        """

        workspace = self._workspace_manager.current_workspace

        if workspace is None:
            return False

        settings = workspace.settings

        changed = (
            (theme is not None and theme != settings.theme)
            or (language is not None and language != settings.language)
        )

        if not changed:
            return False

        old_theme = settings.theme
        old_language = settings.language

        if theme is not None:
            settings.theme = theme

        if language is not None:
            settings.language = language

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError:
            settings.theme = old_theme
            settings.language = old_language
            raise

        return True
