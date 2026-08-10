from dataclasses import dataclass, field


@dataclass
class Dataset:

    dataset_id: str = ""

    name: str = ""

    # Unlike Character.images in Mission 002, this field will actually
    # be populated starting Commit 5 (DatasetManager.add_images()) —
    # not left as a permanently empty placeholder. Mission 003 gives
    # Dataset its own, independent image-import path; it does not
    # depend on or migrate Workspace.images/ImagesPage.
    images: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "dataset_id": self.dataset_id,
            "name": self.name,
            "images": self.images,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Dataset":
        return cls(
            dataset_id=data.get("dataset_id", ""),
            name=data.get("name", ""),
            # (data.get("images") or []) rather than data.get("images", []):
            # degrades safely both when the key is absent (old/malformed
            # files) AND when it is explicitly "images": null, avoiding a
            # future append()/extend() on None once DatasetManager.add_images()
            # (Commit 4/5) starts mutating this list.
            images=data.get("images") or [],
        )
