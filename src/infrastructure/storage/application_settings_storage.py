import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ApplicationSettingsStorageError(Exception):
    """Raised when the application settings file cannot be written to disk."""


class ApplicationSettingsStorage:

    DIRECTORY_NAME = "AIStudioToolkit"
    FILE_NAME = "application_settings.json"

    @staticmethod
    def default_directory() -> Path:
        base = os.getenv("LOCALAPPDATA")
        if base:
            return Path(base) / ApplicationSettingsStorage.DIRECTORY_NAME
        return Path.home() / "AppData" / "Local" / ApplicationSettingsStorage.DIRECTORY_NAME

    @staticmethod
    def load(directory: Path) -> Optional[dict]:

        file = Path(directory) / ApplicationSettingsStorage.FILE_NAME

        if not file.exists():
            return None

        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Could not read application settings file %s: %s", file, exc
            )
            return None

        if not isinstance(data, dict):
            logger.warning(
                "Application settings file %s does not contain a JSON object; ignoring",
                file,
            )
            return None

        return data

    @staticmethod
    def save(directory: Path, data: dict) -> None:

        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        file = directory / ApplicationSettingsStorage.FILE_NAME

        # The temporary file lives in the same directory as the target so
        # that os.replace() below stays on a single filesystem — a
        # cross-filesystem rename (e.g. a system temp folder on another
        # volume) would not be atomic.
        fd, tmp_path = tempfile.mkstemp(
            dir=directory, prefix=".application_settings_", suffix=".tmp"
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
            raise ApplicationSettingsStorageError(
                f"Could not write {file}"
            ) from exc
