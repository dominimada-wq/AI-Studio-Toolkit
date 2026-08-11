from dataclasses import dataclass


@dataclass
class Model:

    model_id: str = ""

    name: str = ""

    # Deliberately a single scalar, not a list: a Model (Checkpoint, VAE,
    # Embedding, ...) is a single file in the overwhelming majority of
    # cases, unlike LoRA.files which was deliberately made list[str] for
    # a justified reason (files.py's own comment). "file_path" (not
    # "path") follows the naming already used elsewhere in this project
    # for an individual file's location, as opposed to a folder
    # (Workspace.root) or a collection (add_images()/add_files()'s
    # `paths` parameter).
    file_path: str = ""

    # Deliberately minimal (Mission 006), matching Dataset's and
    # Prompt's own discipline rather than LoRA's justified exception.
    # The Blueprint (04_DOMAIN_MODEL.md §10) also lists Display Name,
    # Version, Provider, Author, Engine, Architecture, Compatibility,
    # License, File Size, Hash, Thumbnail, Description and Tags — all
    # deferred, not forgotten. None of them has a real consumer today
    # (no automatic scan, no filtering, no metadata display). Every
    # field here is a plain scalar with a default, so adding any of
    # these later requires no migration.

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "name": self.name,
            "file_path": self.file_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Model":
        return cls(
            model_id=data.get("model_id", ""),
            name=data.get("name", ""),
            file_path=data.get("file_path", ""),
        )
