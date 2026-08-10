from dataclasses import dataclass, field

from src.domain.dataset import Dataset
from src.domain.lora import LoRA


@dataclass
class Character:

    character_id: str = ""

    name: str = ""

    images: list[str] = field(default_factory=list)

    datasets: list[Dataset] = field(default_factory=list)

    loras: list[LoRA] = field(default_factory=list)

    prompts: list[str] = field(default_factory=list)

    history: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "character_id": self.character_id,
            "name": self.name,
            "images": self.images,
            "datasets": [dataset.to_dict() for dataset in self.datasets],
            "loras": [lora.to_dict() for lora in self.loras],
            "prompts": self.prompts,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        return cls(
            character_id=data.get("character_id", ""),
            name=data.get("name", ""),
            images=data.get("images", []),
            # (data.get("datasets") or []) degrades a missing key or an
            # explicit null to an empty list. Each remaining entry must
            # also be a dict before being handed to Dataset.from_dict():
            # a manually edited project.json carrying a stale list[str]
            # entry (a format this application has never actually
            # written — see Commit 3's impact report) is filtered out
            # instead of raising an uncontrolled AttributeError.
            datasets=[
                Dataset.from_dict(d)
                for d in (data.get("datasets") or [])
                if isinstance(d, dict)
            ],
            # Same defensive filtering as datasets above: Character.loras
            # has never held real data (see Commit 3's impact report), but
            # a manually edited project.json could still carry a stale
            # list[str] entry that must be filtered out, not raise.
            loras=[
                LoRA.from_dict(l)
                for l in (data.get("loras") or [])
                if isinstance(l, dict)
            ],
            prompts=data.get("prompts", []),
            history=data.get("history", []),
        )
