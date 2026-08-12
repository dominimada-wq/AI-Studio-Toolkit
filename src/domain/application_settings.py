from dataclasses import dataclass


@dataclass
class ApplicationSettings:

    python_path: str = ""

    comfyui_path: str = ""

    onetrainer_path: str = ""

    def to_dict(self) -> dict:
        return {
            "python_path": self.python_path,
            "comfyui_path": self.comfyui_path,
            "onetrainer_path": self.onetrainer_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ApplicationSettings":
        return cls(
            python_path=data.get("python_path", ""),
            comfyui_path=data.get("comfyui_path", ""),
            onetrainer_path=data.get("onetrainer_path", ""),
        )
