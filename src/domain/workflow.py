from dataclasses import dataclass


@dataclass
class Workflow:

    workflow_id: str = ""

    name: str = ""

    # Unlike Model.file_path (which maps directly to the Blueprint's
    # named "Installation Path" attribute), Workflow's Attributes list
    # (04_DOMAIN_MODEL.md §14) names no path field at all. file_path
    # here is a minimal, revisable Mission 007 choice based on today's
    # file-based use cases (ComfyUI Workflow, Forge/Fooocus Preset) —
    # not a Blueprint-mandated invariant.
    file_path: str = ""

    # Deliberately minimal (Mission 007), matching Dataset's/Prompt's/
    # Model's own discipline. Description, Compatible Engine, Inputs,
    # Outputs, Parameters, Version, Category, Author, Thumbnail, Tags
    # and Metadata are deferred, not forgotten — no real consumer
    # exists today.

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "file_path": self.file_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Workflow":
        return cls(
            workflow_id=data.get("workflow_id", ""),
            name=data.get("name", ""),
            file_path=data.get("file_path", ""),
        )
