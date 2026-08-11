from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.domain.character import Character
from src.domain.model import Model


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

    models: list[Model] = field(default_factory=list)

    loras: list = field(default_factory=list)

    training: dict = field(default_factory=dict)

    settings: dict = field(default_factory=dict)

    # Characters owned by this Workspace. The currently active/selected
    # character (if any) is deliberately NOT part of this model — it is
    # runtime state owned by CharacterManager (Commit 3), the same way
    # `root` above is runtime state owned by WorkspaceManager rather
    # than a fact about the workspace's persisted content.
    characters: list[Character] = field(default_factory=list)

    def to_dict(self) -> dict:
        # This is the single serialization contract shared by two independent
        # consumers: WorkspaceStorage, which persists the result to
        # project.json (Infrastructure layer), and the Presentation layer
        # (e.g. DashboardPage.update_project), which receives this same
        # shape as the payload of Workspace events published through the
        # EventBus. Runtime-only fields (currently: root) are intentionally
        # excluded — they are never serialized to disk and never part of
        # the event payload contract either; see the root field's own
        # comment above for why.
        return {
            "name": self.name,
            "version": self.version,
            "images": self.images,
            "datasets": self.datasets,
            "models": [model.to_dict() for model in self.models],
            "loras": self.loras,
            "training": self.training,
            "settings": self.settings,
            "characters": [character.to_dict() for character in self.characters],
        }

    @classmethod
    def from_dict(cls, data: dict, root: Optional[Path] = None) -> "Workspace":
        return cls(
            name=data.get("name", ""),
            version=data.get("version", ""),
            root=root,
            images=data.get("images", []),
            datasets=data.get("datasets", []),
            # Defensive compatibility only (not a migration): Workspace.models
            # has never held real data (see Mission 006's Commit 1/2 impact
            # reports). A stale entry from a manually edited project.json is
            # silently ignored, never converted — same principle already
            # applied to Character.datasets/loras/prompts.
            models=[
                Model.from_dict(m)
                for m in (data.get("models") or [])
                if isinstance(m, dict)
            ],
            loras=data.get("loras", []),
            training=data.get("training", {}),
            settings=data.get("settings", {}),
            characters=[
                Character.from_dict(c) for c in (data.get("characters") or [])
            ],
        )
