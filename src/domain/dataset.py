from dataclasses import dataclass, field

from src.domain.image import Image


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

    def to_dict(self) -> dict:
        return {
            "dataset_id": self.dataset_id,
            "name": self.name,
            "images": [image.to_dict() for image in self.images],
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
        )
