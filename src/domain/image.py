import uuid
from dataclasses import dataclass


@dataclass
class Image:

    image_id: str = ""

    file_path: str = ""

    def to_dict(self) -> dict:
        return {
            "image_id": self.image_id,
            "file_path": self.file_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Image":
        return cls(
            image_id=data.get("image_id", ""),
            file_path=data.get("file_path", ""),
        )

    @staticmethod
    def list_from_data(entries) -> list["Image"]:
        """
        Shared by Workspace.from_dict() and Dataset.from_dict(), the two
        independent Image pools (Mission 011 ownership model D). Accepts
        a mix of legacy str entries (pre-Mission-011 project.json) and
        already-migrated dict entries: each str becomes a new Image with
        a freshly generated image_id (none existed before), each dict is
        deserialized via Image.from_dict() (preserving its image_id
        across round-trips). An entry is only kept if it resolves to a
        usable file_path (non-empty str) — this is where validity is
        decided, deliberately not inside Image.from_dict(), which stays
        a simple, exception-free constructor for direct Domain use.
        Anything else (wrong type, empty/non-str file_path) is filtered
        out, same defensive-compatibility principle as every other
        nested-list field in this codebase.
        """
        images = []
        for entry in entries or []:
            if isinstance(entry, dict):
                image = Image.from_dict(entry)
                if isinstance(image.file_path, str) and image.file_path:
                    images.append(image)
            elif isinstance(entry, str) and entry:
                images.append(Image(image_id=str(uuid.uuid4()), file_path=entry))
        return images
