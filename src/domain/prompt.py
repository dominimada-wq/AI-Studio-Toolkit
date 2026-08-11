from dataclasses import dataclass


@dataclass
class Prompt:

    prompt_id: str = ""

    name: str = ""

    # Deliberately a single scalar, not a list: unlike Dataset.images or
    # LoRA.files, a Prompt's content is edited/replaced in place
    # (PromptManager.update_text()), never accumulated.
    text: str = ""

    # Deliberately minimal (Mission 005), matching Dataset's and
    # Character's own discipline rather than LoRA's justified exception.
    # The Blueprint (04_DOMAIN_MODEL.md §13) also lists Category,
    # Variables, Tags, Favorite, Rating, Version, Author, Creation Date
    # and Last Modified — all deferred, not forgotten. Category/type
    # (Master/Negative/Generation/Training/Template/Dynamic Prompt) only
    # gains meaning once a real consumer exists (generation pipeline,
    # training pipeline, prompt library filtering); adding it now would
    # be guessing a taxonomy for features that don't exist yet. Every
    # field here is a plain scalar with a default, so adding any of
    # these later requires no migration.

    def to_dict(self) -> dict:
        return {
            "prompt_id": self.prompt_id,
            "name": self.name,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Prompt":
        return cls(
            prompt_id=data.get("prompt_id", ""),
            name=data.get("name", ""),
            text=data.get("text", ""),
        )
