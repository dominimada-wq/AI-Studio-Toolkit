from dataclasses import dataclass, field

from src.domain.image import Image


@dataclass
class DatasetEntryMetadata:
    """
    Mission 098: metadata attached to the association between a Dataset
    and one of its images (keyed by Image.image_id in Dataset.entries),
    never to the Image itself — the same physical file can belong to
    several Datasets with different training objectives (Mission 011
    already gives each Dataset its own independent Image pool). This is
    the sole place for any future per-image, per-Dataset metadata
    (caption source, validation status, AI-captioning info, ...) — a
    future need is a new field here, never a new parallel dict on
    Dataset alongside `entries`.
    """

    caption: str = ""

    def to_dict(self) -> dict:
        return {
            "caption": self.caption,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DatasetEntryMetadata":
        return cls(
            caption=data.get("caption", "") if isinstance(data.get("caption", ""), str) else "",
        )


@dataclass
class Dataset:

    dataset_id: str = ""

    name: str = ""

    # Unlike Character.images in Mission 002, this field will actually
    # be populated starting Commit 5 (DatasetManager.add_images()) —
    # not left as a permanently empty placeholder. Mission 003 gives
    # Dataset its own, independent image-import path; it does not
    # depend on or migrate Workspace.images/ImagesPage. Mission 011
    # types this collection as Image (ownership model D: Dataset owns
    # its own Image pool, entirely independent from Workspace.images —
    # no shared registry, no cross-pool reference).
    images: list[Image] = field(default_factory=list)

    # Mission 098: additive, keyed by Image.image_id — never touches or
    # restructures `images` above (see MISSION_098.md section 3). Key
    # absent means "no caption explicitly defined" (Training falls back
    # to trigger_word); a present entry with an empty caption means
    # "explicitly no caption" and must never be treated the same as
    # absence.
    entries: dict[str, DatasetEntryMetadata] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "dataset_id": self.dataset_id,
            "name": self.name,
            "images": [image.to_dict() for image in self.images],
            "entries": {
                image_id: metadata.to_dict()
                for image_id, metadata in self.entries.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Dataset":
        return cls(
            dataset_id=data.get("dataset_id", ""),
            name=data.get("name", ""),
            # Mission 011: images may be a legacy list[str] (pre-migration
            # project.json) or an already-migrated list[dict] — both are
            # accepted transparently, see Image.list_from_data().
            images=Image.list_from_data(data.get("images")),
            # Mission 098: absent in any project.json saved before this
            # mission — defaults to {} defensively, never a migration.
            entries=Dataset._entries_from_data(data.get("entries")),
        )

    @staticmethod
    def _entries_from_data(entries) -> dict:
        if not isinstance(entries, dict):
            return {}
        return {
            image_id: DatasetEntryMetadata.from_dict(metadata)
            for image_id, metadata in entries.items()
            if isinstance(image_id, str) and isinstance(metadata, dict)
        }
