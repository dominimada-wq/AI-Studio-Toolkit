from pathlib import Path
from typing import Optional

from src.core.event_bus import EventBus
from src.domain.application_settings import ApplicationSettings
from src.infrastructure.storage.application_settings_storage import (
    ApplicationSettingsStorage,
)
from src.managers.lora_library_manager import LoRALibraryManager

APPLICATION_SETTINGS_UPDATED = "application_settings.updated"


class LoRALibraryPathLockedError(Exception):
    """
    Mission 087: raised by update() when lora_library_path is given a
    genuinely different value while the central LoRA library registry
    already holds at least one entry. Deliberately conservative — no
    migration/copy/move of an existing library is attempted; the path
    becomes changeable again only once every entry has been deleted.
    A future explicit "Move library" action may revisit this, out of
    scope here.
    """


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
        lora_library_manager: Optional[LoRALibraryManager] = None,
    ):
        self._directory = storage_directory or ApplicationSettingsStorage.default_directory()
        self._event_bus = event_bus
        # Mission 087: optional so this Manager stays independently
        # constructible/testable without pulling in the LoRA library —
        # None simply means the path-change lock below never applies
        # (nothing to check against).
        self._lora_library_manager = lora_library_manager

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
        comfyui_lora_name: Optional[str] = None,
        comfyui_lora_strength: Optional[float] = None,
        ollama_url: Optional[str] = None,
        ollama_path: Optional[str] = None,
        ollama_model_name: Optional[str] = None,
        lora_library_path: Optional[str] = None,
    ) -> bool:

        current = self._settings

        # Mission 087: computed standalone (not folded into the generic
        # `changed` clause below) because it also gates the path-change
        # lock — resaisir exactement la valeur déjà configurée must stay
        # a silent no-op even with a non-empty library, never a refusal;
        # only a genuine value change is checked against the registry.
        lora_library_path_changed = (
            lora_library_path is not None and lora_library_path != current.lora_library_path
        )

        if (
            lora_library_path_changed
            and self._lora_library_manager is not None
            and self._lora_library_manager.list_loras()
        ):
            raise LoRALibraryPathLockedError(
                "Impossible de modifier l'emplacement de la bibliothèque LoRA "
                "centrale tant qu'elle contient au moins une LoRA. Supprimez "
                "toutes les entrées de la bibliothèque avant de changer ce "
                "chemin, ou conservez le chemin actuel."
            )

        changed = (
            (python_path is not None and python_path != current.python_path)
            or (comfyui_path is not None and comfyui_path != current.comfyui_path)
            or (onetrainer_path is not None and onetrainer_path != current.onetrainer_path)
            or (comfyui_url is not None and comfyui_url != current.comfyui_url)
            or (
                comfyui_checkpoint_name is not None
                and comfyui_checkpoint_name != current.comfyui_checkpoint_name
            )
            or (
                comfyui_lora_name is not None
                and comfyui_lora_name != current.comfyui_lora_name
            )
            or (
                comfyui_lora_strength is not None
                and comfyui_lora_strength != current.comfyui_lora_strength
            )
            or (ollama_url is not None and ollama_url != current.ollama_url)
            or (ollama_path is not None and ollama_path != current.ollama_path)
            or (
                ollama_model_name is not None
                and ollama_model_name != current.ollama_model_name
            )
            or lora_library_path_changed
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
            comfyui_lora_name=(
                comfyui_lora_name
                if comfyui_lora_name is not None
                else current.comfyui_lora_name
            ),
            comfyui_lora_strength=(
                comfyui_lora_strength
                if comfyui_lora_strength is not None
                else current.comfyui_lora_strength
            ),
            ollama_url=ollama_url if ollama_url is not None else current.ollama_url,
            ollama_path=ollama_path if ollama_path is not None else current.ollama_path,
            ollama_model_name=(
                ollama_model_name
                if ollama_model_name is not None
                else current.ollama_model_name
            ),
            lora_library_path=(
                lora_library_path
                if lora_library_path is not None
                else current.lora_library_path
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
