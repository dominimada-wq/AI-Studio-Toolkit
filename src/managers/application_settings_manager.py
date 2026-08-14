from pathlib import Path
from typing import Optional

from src.core.event_bus import EventBus
from src.domain.application_settings import ApplicationSettings
from src.infrastructure.storage.application_settings_storage import (
    ApplicationSettingsStorage,
)

APPLICATION_SETTINGS_UPDATED = "application_settings.updated"


class ApplicationSettingsManager:
    """
    Coordinates read/write access to ApplicationSettings — a singleton
    entirely independent of any Workspace. Loaded once at construction
    from a machine-local file (never project.json), it exists and
    functions whether or not any Workspace has ever been opened.
    """

    def __init__(
        self,
        storage_directory: Optional[Path] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self._directory = storage_directory or ApplicationSettingsStorage.default_directory()
        self._event_bus = event_bus

        raw = ApplicationSettingsStorage.load(self._directory)
        self._settings = (
            ApplicationSettings.from_dict(raw) if raw is not None else ApplicationSettings()
        )

    @property
    def settings(self) -> ApplicationSettings:
        return self._settings

    def update(
        self,
        python_path: Optional[str] = None,
        comfyui_path: Optional[str] = None,
        onetrainer_path: Optional[str] = None,
        comfyui_url: Optional[str] = None,
        comfyui_checkpoint_name: Optional[str] = None,
    ) -> bool:

        current = self._settings

        changed = (
            (python_path is not None and python_path != current.python_path)
            or (comfyui_path is not None and comfyui_path != current.comfyui_path)
            or (onetrainer_path is not None and onetrainer_path != current.onetrainer_path)
            or (comfyui_url is not None and comfyui_url != current.comfyui_url)
            or (
                comfyui_checkpoint_name is not None
                and comfyui_checkpoint_name != current.comfyui_checkpoint_name
            )
        )

        if not changed:
            return False

        candidate = ApplicationSettings(
            python_path=python_path if python_path is not None else current.python_path,
            comfyui_path=comfyui_path if comfyui_path is not None else current.comfyui_path,
            onetrainer_path=onetrainer_path if onetrainer_path is not None else current.onetrainer_path,
            comfyui_url=comfyui_url if comfyui_url is not None else current.comfyui_url,
            comfyui_checkpoint_name=(
                comfyui_checkpoint_name
                if comfyui_checkpoint_name is not None
                else current.comfyui_checkpoint_name
            ),
        )

        # Storage.save() may raise ApplicationSettingsStorageError — left
        # to propagate uncaught. self._settings is only reassigned below,
        # so a failed save leaves memory exactly as it was; no rollback
        # is needed because nothing was mutated before success.
        ApplicationSettingsStorage.save(self._directory, candidate.to_dict())

        self._settings = candidate

        self._publish(APPLICATION_SETTINGS_UPDATED, candidate)

        return True

    def _publish(self, event_name: str, settings: ApplicationSettings) -> None:

        if self._event_bus is None:
            return

        self._event_bus.publish(event_name, settings.to_dict())
