import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class WorkspaceStorageError(Exception):
    """Raised when a workspace cannot be read from or written to disk."""


class WorkspaceStorage:

    WORKSPACE_FILE = "project.json"  # name kept for backward compatibility (Q1)

    DIRECTORIES = [
        "images",
        "datasets",
        "datasets/train",
        "datasets/validation",
        "captions",
        "models",
        "models/checkpoints",
        "models/loras",
        "models/vae",
        "models/embeddings",
        "outputs",
        "training",
        "logs",
    ]

    @staticmethod
    def create_directories(folder) -> None:

        folder = Path(folder)

        try:
            folder.mkdir(parents=True, exist_ok=True)

            for directory in WorkspaceStorage.DIRECTORIES:
                (folder / directory).mkdir(parents=True, exist_ok=True)

        except OSError as exc:
            logger.error(
                "Failed to create workspace directories in %s: %s", folder, exc
            )
            raise WorkspaceStorageError(
                f"Could not create workspace folders in {folder}"
            ) from exc

    @staticmethod
    def load(folder) -> Optional[dict]:

        folder = Path(folder)
        file = folder / WorkspaceStorage.WORKSPACE_FILE

        if not file.exists():
            return None

        try:
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)

        except json.JSONDecodeError as exc:
            logger.error("Corrupted workspace file %s: %s", file, exc)
            raise WorkspaceStorageError(f"{file} is not valid JSON") from exc

        except OSError as exc:
            logger.error("Failed to read workspace file %s: %s", file, exc)
            raise WorkspaceStorageError(f"Could not read {file}") from exc

    @staticmethod
    def save(folder, data: dict) -> None:

        folder = Path(folder)

        try:
            with open(
                folder / WorkspaceStorage.WORKSPACE_FILE, "w", encoding="utf-8"
            ) as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

        except OSError as exc:
            logger.error("Failed to write workspace file in %s: %s", folder, exc)
            raise WorkspaceStorageError(
                f"Could not write project.json in {folder}"
            ) from exc
