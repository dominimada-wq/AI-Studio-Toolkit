import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from src.infrastructure.storage.application_settings_storage import (
    ApplicationSettingsStorage,
)

logger = logging.getLogger(__name__)


class LoRALibraryStorageError(Exception):
    """Raised when the central LoRA library registry cannot be written to disk."""


class LoRALibraryStorage:
    """
    Mission 087: persists the central LoRA registry — deliberately a
    separate file from application_settings.json (a growing catalog of
    entries is a different concern from a handful of flat scalar
    preferences, and would otherwise be rewritten on every unrelated
    Settings edit) but the same machine-local directory, resolved via
    ApplicationSettingsStorage.default_directory() rather than
    duplicating that resolution logic — a one-line delegation, not a
    generic Storage abstraction shared between the two classes.
    """

    FILE_NAME = "lora_library.json"

    @staticmethod
    def default_directory() -> Path:
        return ApplicationSettingsStorage.default_directory()

    @staticmethod
    def load(directory: Path) -> Optional[dict]:

        file = Path(directory) / LoRALibraryStorage.FILE_NAME

        if not file.exists():
            return None

        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Could not read LoRA library registry file %s: %s", file, exc
            )
            return None

        if not isinstance(data, dict):
            logger.warning(
                "LoRA library registry file %s does not contain a JSON object; ignoring",
                file,
            )
            return None

        return data

    @staticmethod
    def save(directory: Path, data: dict) -> None:

        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        file = directory / LoRALibraryStorage.FILE_NAME

        # Same-directory tempfile so os.replace() below stays on a single
        # filesystem — a cross-filesystem rename would not be atomic.
        fd, tmp_path = tempfile.mkstemp(
            dir=directory, prefix=".lora_library_", suffix=".tmp"
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, file)

        except OSError as exc:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise LoRALibraryStorageError(
                f"Could not write {file}"
            ) from exc
