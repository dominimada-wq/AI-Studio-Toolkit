from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GenerationReference:
    """
    Mirrors the shape of generation_manager.Reference (path, role) without
    importing it — that class lives in src/managers/, and Domain must
    never depend on a Manager (Dependency Rule).

    `path` is historical provenance only: it records which file was used
    as a reference at the moment this generation ran. It is never
    revalidated, never resolved back to an Image/Dataset id (the source
    snapshot carries no such stable identifier), and nothing guarantees
    the file still exists at this path later. This is not a basis for
    Replay/regeneration.
    """

    path: str = ""
    role: str = ""

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "role": self.role,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GenerationReference":
        return cls(
            path=data.get("path", ""),
            role=data.get("role", ""),
        )


@dataclass
class GenerationMetadata:
    """
    The generation parameters that actually produced one accepted Image,
    captured once from InferencePage's immutable per-generation snapshot
    (_PendingGenerationRequest) -- never rebuilt from live widget state.
    Image.generation_metadata is None for any image with no generation
    provenance (manually imported, or generated before this field
    existed) -- no field here is ever invented for such an image.
    """

    engine: str = ""
    prompt: str = ""
    negative_prompt: str = ""
    seed: int = -1
    width: int = 0
    height: int = 0
    steps: int = 0
    cfg: float = 0.0
    sampler_name: str = ""
    scheduler: str = ""
    checkpoint_name: Optional[str] = None
    lora_name: str = ""
    lora_strength: Optional[float] = None
    references: list = field(default_factory=list)
    reference_strength: float = 0.0

    def to_dict(self) -> dict:
        return {
            "engine": self.engine,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "seed": self.seed,
            "width": self.width,
            "height": self.height,
            "steps": self.steps,
            "cfg": self.cfg,
            "sampler_name": self.sampler_name,
            "scheduler": self.scheduler,
            "checkpoint_name": self.checkpoint_name,
            "lora_name": self.lora_name,
            "lora_strength": self.lora_strength,
            "references": [reference.to_dict() for reference in self.references],
            "reference_strength": self.reference_strength,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GenerationMetadata":
        raw_references = data.get("references")
        references = (
            [
                GenerationReference.from_dict(entry)
                for entry in raw_references
                if isinstance(entry, dict)
            ]
            if isinstance(raw_references, list)
            else []
        )

        return cls(
            engine=data.get("engine", ""),
            prompt=data.get("prompt", ""),
            negative_prompt=data.get("negative_prompt", ""),
            seed=data.get("seed", -1),
            width=data.get("width", 0),
            height=data.get("height", 0),
            steps=data.get("steps", 0),
            cfg=data.get("cfg", 0.0),
            sampler_name=data.get("sampler_name", ""),
            scheduler=data.get("scheduler", ""),
            checkpoint_name=data.get("checkpoint_name"),
            lora_name=data.get("lora_name", ""),
            lora_strength=data.get("lora_strength"),
            references=references,
            reference_strength=data.get("reference_strength", 0.0),
        )
