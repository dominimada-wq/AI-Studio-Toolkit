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
    """
    Raised when the central LoRA library registry cannot be written to
    disk, or (Mission 144) when it is present but cannot be read back:
    invalid JSON, an OSError while reading, a syntactically valid JSON
    value that is not an object, or a "loras" key whose value is not a
    list. A registry in this state must never be treated as equivalent
    to a missing file — load() only ever returns None when the file
    genuinely does not exist. This is a structural check only: an
    otherwise-valid "loras" list containing malformed individual
    entries is still tolerated defensively by LoRALibraryManager, not
    raised here.
    """


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
        """
        Mission 144: a file that is present but cannot be read — invalid
        JSON, an OSError, a syntactically valid JSON value that is not
        an object, or a "loras" key whose value is not a list — must
        never be silently treated the same as a missing file (which
        legitimately means "no registry yet", handled by the caller).
        All of these now raise LoRALibraryStorageError instead of
        returning None, so a caller can never mistake "corrupt" for
        "empty catalog" and go on to silently persist an empty/partial
        catalog over it. A missing "loras" key (e.g. "{}") remains
        tolerated, same as today — only a key that is present with the
        wrong type is structurally invalid. Malformed individual
        entries inside an otherwise valid "loras" list are deliberately
        left untouched here — that tolerance belongs to
        LoRALibraryManager, not to this structural check.
        """

        file = Path(directory) / LoRALibraryStorage.FILE_NAME

        if not file.exists():
            return None

        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            logger.error("Corrupted LoRA library registry file %s: %s", file, exc)
            raise LoRALibraryStorageError(f"{file} is not valid JSON") from exc
        except OSError as exc:
            logger.error("Failed to read LoRA library registry file %s: %s", file, exc)
            raise LoRALibraryStorageError(f"Could not read {file}") from exc

        if not isinstance(data, dict):
            logger.error(
                "LoRA library registry file %s does not contain a JSON object", file
            )
            raise LoRALibraryStorageError(f"{file} does not contain a JSON object")

        if "loras" in data and not isinstance(data["loras"], list):
            logger.error(
                "LoRA library registry file %s has a non-list 'loras' value", file
            )
            raise LoRALibraryStorageError(
                f"{file} has a 'loras' value that is not a list"
            )

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
