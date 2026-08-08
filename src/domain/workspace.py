from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Workspace:

    name: str = ""

    version: str = "0.4"

    # Runtime-only: never serialized into project.json. Injected by
    # WorkspaceManager when a workspace is created or opened. Keeping
    # the path out of the JSON file keeps project.json portable — the
    # workspace folder can be moved, renamed, or synced without
    # invalidating a stored absolute path.
    root: Optional[Path] = None

    images: list = field(default_factory=list)

    datasets: list = field(default_factory=list)

    models: list = field(default_factory=list)

    loras: list = field(default_factory=list)

    training: dict = field(default_factory=dict)

    settings: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "images": self.images,
            "datasets": self.datasets,
            "models": self.models,
            "loras": self.loras,
            "training": self.training,
            "settings": self.settings,
        }

    @classmethod
    def from_dict(cls, data: dict, root: Optional[Path] = None) -> "Workspace":
        return cls(
            name=data.get("name", ""),
            version=data.get("version", ""),
            root=root,
            images=data.get("images", []),
            datasets=data.get("datasets", []),
            models=data.get("models", []),
            loras=data.get("loras", []),
            training=data.get("training", {}),
            settings=data.get("settings", {}),
        )
