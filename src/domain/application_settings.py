from dataclasses import dataclass


@dataclass
class ApplicationSettings:

    python_path: str = ""

    comfyui_path: str = ""

    onetrainer_path: str = ""

    # Mission 018: unlike every other field above (where "" means "not
    # configured yet"), these two already have a real, currently active
    # behavior — the app connects to a specific ComfyUI server with a
    # specific checkpoint today (Mission 012/013). Defaulting them to ""
    # would silently change that working behavior the moment
    # ApplicationSettings becomes their only source of truth. These
    # literal defaults are exactly the values that were hardcoded in
    # main_window.py before this mission.
    comfyui_url: str = "http://127.0.0.1:8000"

    comfyui_checkpoint_name: str = "v1-5-pruned-emaonly-fp16.safetensors"

    def to_dict(self) -> dict:
        return {
            "python_path": self.python_path,
            "comfyui_path": self.comfyui_path,
            "onetrainer_path": self.onetrainer_path,
            "comfyui_url": self.comfyui_url,
            "comfyui_checkpoint_name": self.comfyui_checkpoint_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ApplicationSettings":
        return cls(
            python_path=data.get("python_path", ""),
            comfyui_path=data.get("comfyui_path", ""),
            onetrainer_path=data.get("onetrainer_path", ""),
            comfyui_url=data.get("comfyui_url", "http://127.0.0.1:8000"),
            comfyui_checkpoint_name=data.get(
                "comfyui_checkpoint_name", "v1-5-pruned-emaonly-fp16.safetensors"
            ),
        )
