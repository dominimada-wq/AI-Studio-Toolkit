from dataclasses import dataclass


@dataclass
class Training:

    training_id: str = ""

    name: str = ""

    # Character ownership is implicit via Character.trainings.
    # References the source Dataset used by this training session.
    dataset_id: str = ""

    def to_dict(self) -> dict:
        return {
            "training_id": self.training_id,
            "name": self.name,
            "dataset_id": self.dataset_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Training":
        return cls(
            training_id=data.get("training_id", ""),
            name=data.get("name", ""),
            dataset_id=data.get("dataset_id", ""),
        )
