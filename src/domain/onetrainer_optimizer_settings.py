from dataclasses import dataclass, field


@dataclass
class OneTrainerOptimizerSettings:
    """
    Mission 122: structured optimizer selection, deliberately its own
    nested structure rather than a flat field on OneTrainerSettings —
    see MISSION_122.md section 3.1. `optimizer` is the discriminant
    (OneTrainer's real Optimizer enum, "" = not configured, never one of
    the 43 real enum values). `extra_overrides` is a second, narrower
    escape hatch, scoped to this nested object only — distinct from
    OneTrainerSettings.extra_overrides — so that reserving the top-level
    "optimizer" key globally (src/engines/onetrainer_config.py) never
    blocks expressing any of OneTrainer's ~99 real optimizer
    hyperparameters not yet modeled as a typed field here (MISSION_122.md
    section 3.3).
    """

    optimizer: str = ""
    extra_overrides: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "optimizer": self.optimizer,
            "extra_overrides": dict(self.extra_overrides),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OneTrainerOptimizerSettings":
        extra_overrides = data.get("extra_overrides")
        return cls(
            optimizer=data.get("optimizer", ""),
            extra_overrides=dict(extra_overrides) if isinstance(extra_overrides, dict) else {},
        )
