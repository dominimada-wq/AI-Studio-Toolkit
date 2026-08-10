from dataclasses import dataclass, field


@dataclass
class Character:

    character_id: str = ""

    name: str = ""

    # Plain image file paths — mirrors Workspace.images exactly.
    # Introduced here to prepare the future migration of image
    # ownership from Workspace to Character, but NOT wired to
    # ImagesPage in this mission (Mission 002 decision 1): ImagesPage
    # still reads/writes Workspace.images. This field stays empty in
    # practice until that migration happens.
    images: list[str] = field(default_factory=list)

    # The following three lists hold plain string identifiers, not
    # file paths and not domain objects. Dataset, LoRA and Prompt do
    # not exist as domain classes yet (deferred to future missions,
    # same precedent as Mission 001: no dependency on not-yet-built
    # classes). Once those classes are introduced, these lists become
    # lists of their identifiers rather than changing shape.
    datasets: list[str] = field(default_factory=list)

    loras: list[str] = field(default_factory=list)

    prompts: list[str] = field(default_factory=list)

    history: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "character_id": self.character_id,
            "name": self.name,
            "images": self.images,
            "datasets": self.datasets,
            "loras": self.loras,
            "prompts": self.prompts,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        return cls(
            character_id=data.get("character_id", ""),
            name=data.get("name", ""),
            images=data.get("images", []),
            datasets=data.get("datasets", []),
            loras=data.get("loras", []),
            prompts=data.get("prompts", []),
            history=data.get("history", []),
        )
