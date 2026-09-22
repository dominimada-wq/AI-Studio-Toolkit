import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ApplicationSettingsStorageError(Exception):
    """
    Raised when the application settings file cannot be written to disk,
    or (Mission 144) when it is present but cannot be read back: invalid
    JSON, an OSError while reading, or a syntactically valid JSON value
    that is not an object. A file in this state must never be treated
    as equivalent to a missing file — load() only ever returns None
    when the file genuinely does not exist.
    """


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
        """
        Mission 144: a file that is present but cannot be read — invalid
        JSON, an OSError, or a syntactically valid JSON value that is
        not an object — must never be silently treated the same as a
        missing file (which legitimately means "first run", handled by
        the caller). Both cases now raise ApplicationSettingsStorageError
        instead of returning None, so a caller can never mistake
        "corrupt" for "nothing saved yet" and go on to silently persist
        fresh defaults over it.
        """

        file = Path(directory) / ApplicationSettingsStorage.FILE_NAME

        if not file.exists():
            return None

        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            logger.error("Corrupted application settings file %s: %s", file, exc)
            raise ApplicationSettingsStorageError(
                f"{file} is not valid JSON"
            ) from exc
        except OSError as exc:
            logger.error("Failed to read application settings file %s: %s", file, exc)
            raise ApplicationSettingsStorageError(f"Could not read {file}") from exc

        if not isinstance(data, dict):
            logger.error(
                "Application settings file %s does not contain a JSON object", file
            )
            raise ApplicationSettingsStorageError(
                f"{file} does not contain a JSON object"
            )

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
