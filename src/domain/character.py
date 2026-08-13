from dataclasses import dataclass, field

from src.domain.dataset import Dataset
from src.domain.lora import LoRA
from src.domain.prompt import Prompt
from src.domain.training import Training


@dataclass
class Character:

    character_id: str = ""

    name: str = ""

    datasets: list[Dataset] = field(default_factory=list)

    loras: list[LoRA] = field(default_factory=list)

    prompts: list[Prompt] = field(default_factory=list)

    trainings: list[Training] = field(default_factory=list)

    history: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "character_id": self.character_id,
            "name": self.name,
            "datasets": [dataset.to_dict() for dataset in self.datasets],
            "loras": [lora.to_dict() for lora in self.loras],
            "prompts": [prompt.to_dict() for prompt in self.prompts],
            "trainings": [training.to_dict() for training in self.trainings],
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        return cls(
            character_id=data.get("character_id", ""),
            name=data.get("name", ""),
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
            # Defensive compatibility only (not a migration): Character.prompts
            # has never held real data (see Commit 3's impact report of Mission
            # 005). A stale list[str] entry from a manually edited project.json
            # is silently ignored, never converted — same principle as
            # datasets/loras above, and the one to reapply for any future
            # Domain Model following this list[str] -> list[Object] pattern.
            prompts=[
                Prompt.from_dict(p)
                for p in (data.get("prompts") or [])
                if isinstance(p, dict)
            ],
            # New field (Mission 008) — no prior format existed to be
            # defensive against, unlike datasets/loras/prompts.
            trainings=[
                Training.from_dict(t)
                for t in (data.get("trainings") or [])
                if isinstance(t, dict)
            ],
            history=data.get("history", []),
        )
