from dataclasses import dataclass, field


@dataclass
class LoRA:

    lora_id: str = ""

    name: str = ""

    # Technical files that constitute the LoRA itself (.safetensors,
    # metadata.json, ...). Deliberately list[str], not a single
    # file_path — mirrors Dataset.images, avoiding a future migration
    # once multiple files need to be associated with one LoRA.
    files: list[str] = field(default_factory=list)

    # Distinct from `files`: a thumbnail is not one of the LoRA's
    # constitutive files, it's a separate preview asset — the same
    # distinction CivitAI/ComfyUI/A1111/Forge make in their own LoRA
    # managers. Named "thumbnail" to match the Blueprint's own
    # vocabulary for this exact concept on Model and Workflow
    # (04_DOMAIN_MODEL.md §10/§14) rather than inventing a new term.
    thumbnail: str = ""

    engine: str = ""

    architecture: str = ""

    trigger_word: str = ""

    version: str = ""

    def to_dict(self) -> dict:
        return {
            "lora_id": self.lora_id,
            "name": self.name,
            "files": self.files,
            "thumbnail": self.thumbnail,
            "engine": self.engine,
            "architecture": self.architecture,
            "trigger_word": self.trigger_word,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LoRA":
        return cls(
            lora_id=data.get("lora_id", ""),
            name=data.get("name", ""),
            # (X or []): files will genuinely be mutated later via
            # LoRAManager.add_files() — same robustness already applied
            # to Dataset.images for the same reason.
            files=data.get("files") or [],
            thumbnail=data.get("thumbnail", ""),
            engine=data.get("engine", ""),
            architecture=data.get("architecture", ""),
            trigger_word=data.get("trigger_word", ""),
            version=data.get("version", ""),
        )
