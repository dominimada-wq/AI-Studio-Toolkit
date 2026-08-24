from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.domain.character import Character
from src.domain.image import Image
from src.domain.model import Model
from src.domain.settings import Settings
from src.domain.workflow import Workflow


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

    images: list[Image] = field(default_factory=list)

    models: list[Model] = field(default_factory=list)

    # New field (Mission 007) — no prior format existed to be defensive
    # against, unlike models/datasets/loras/prompts.
    workflows: list[Workflow] = field(default_factory=list)

    settings: Settings = field(default_factory=Settings)

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
            "images": [image.to_dict() for image in self.images],
            "models": [model.to_dict() for model in self.models],
            "workflows": [workflow.to_dict() for workflow in self.workflows],
            "settings": self.settings.to_dict(),
            "characters": [character.to_dict() for character in self.characters],
        }

    @classmethod
    def from_dict(cls, data: dict, root: Optional[Path] = None) -> "Workspace":
        return cls(
            name=data.get("name", ""),
            version=data.get("version", ""),
            root=root,
            # Mission 011: images may be a legacy list[str] (pre-migration
            # project.json) or an already-migrated list[dict] — both are
            # accepted transparently, see Image.list_from_data().
            images=Image.list_from_data(data.get("images")),
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
            # Defensive compatibility, not a migration: workflows is a
            # brand-new field, so this only guards against a hand-edited
            # project.json carrying a malformed entry.
            workflows=[
                Workflow.from_dict(w)
                for w in (data.get("workflows") or [])
                if isinstance(w, dict)
            ],
            # A project.json written before this field's removal may still
            # carry "datasets"/"loras"/"training" keys — they held no real
            # data even when present (see the models comment above for the
            # same principle) and are simply not read into anything anymore;
            # never re-emitted by to_dict() once this Workspace is saved
            # again. The real collections live on Character (datasets/
            # loras/trainings) and on this Workspace itself (models/
            # workflows) — both entirely unaffected.
            settings=(
                Settings.from_dict(data.get("settings"))
                if isinstance(data.get("settings"), dict)
                else Settings()
            ),
            characters=[
                Character.from_dict(c) for c in (data.get("characters") or [])
            ],
        )
