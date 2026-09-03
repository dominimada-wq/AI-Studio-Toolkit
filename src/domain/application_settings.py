from dataclasses import dataclass, field
from pathlib import Path


def _default_lora_library_path() -> str:
    # Mission 087: %USERPROFILE%\AI Studio Toolkit\LoRA Library — never
    # %LOCALAPPDATA% (reserved for small machine-local metadata, not
    # potentially multi-GB .safetensors binaries) and never Documents
    # (frequently auto-synced by OneDrive's Known Folder Move on modern
    # Windows installs, which would silently push a large model library
    # to the cloud). Path.home() mirrors the same USERPROFILE resolution
    # ApplicationSettingsStorage.default_directory() already falls back
    # to. Computed dynamically (never a plain string literal default)
    # since it depends on the current OS user at runtime.
    return str(Path.home() / "AI Studio Toolkit" / "LoRA Library")


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

    # Mission 059: no prior hardcoded behavior to preserve (no LoRA was
    # ever applied by any engine before this mission) — "" honestly
    # means "no LoRA configured", same convention as ollama_model_name,
    # unlike comfyui_checkpoint_name above. Selects a LoRA name known to
    # the active ComfyUI server (ComfyUIEngine.list_loras()), never a
    # Workspace-local LoRA.files entry — see comfyui_workflows.py for
    # why that mapping does not exist.
    comfyui_lora_name: str = ""

    # LoraLoader's own native default. A single value applied to both
    # strength_model/strength_clip (Mission 059) — the node itself
    # distinguishes them, but no current need justifies exposing two
    # separate controls; this field could be split additively later
    # without a migration if that need ever appears.
    comfyui_lora_strength: float = 1.0

    # Mission 030: Ollama's own documented default local port — unlike
    # comfyui_url/comfyui_checkpoint_name above, there is no prior
    # hardcoded behavior to preserve (Ollama is a brand new
    # integration), so this is simply Ollama's own real default, not a
    # value this application already depended on before this field
    # existed.
    ollama_url: str = "http://127.0.0.1:11434"

    # Optional local installation folder — mirrors comfyui_path exactly
    # (Mission 010): never required (an Ollama instance may be local,
    # remote, or exposed on the network), not consumed by any code this
    # mission. Reserved for a future need (detection, opening the
    # folder, diagnostics, start/stop, local model exploration).
    ollama_path: str = ""

    # No literal non-empty default (unlike comfyui_checkpoint_name):
    # "" honestly means "not configured yet", same convention as
    # python_path/onetrainer_path.
    ollama_model_name: str = ""

    # Mission 087: unlike python_path/onetrainer_path/ollama_path above
    # (where "" honestly means "not configured"), an empty central LoRA
    # library path is never a meaningful, usable state — it always
    # resolves to a real default (see _default_lora_library_path()),
    # same structural family as comfyui_url/comfyui_checkpoint_name.
    lora_library_path: str = field(default_factory=_default_lora_library_path)

    # Mission 095: unlike lora_library_path above, no generated default —
    # this must name a loras root the architect has already declared to
    # ComfyUI (outside the Toolkit); a silently-invented default would
    # not correspond to anything real. "" honestly means "exposure not
    # configured", same convention as python_path/onetrainer_path/
    # ollama_path/comfyui_lora_name.
    comfyui_lora_expose_path: str = ""

    def to_dict(self) -> dict:
        return {
            "python_path": self.python_path,
            "comfyui_path": self.comfyui_path,
            "onetrainer_path": self.onetrainer_path,
            "comfyui_url": self.comfyui_url,
            "comfyui_checkpoint_name": self.comfyui_checkpoint_name,
            "comfyui_lora_name": self.comfyui_lora_name,
            "comfyui_lora_strength": self.comfyui_lora_strength,
            "ollama_url": self.ollama_url,
            "ollama_path": self.ollama_path,
            "ollama_model_name": self.ollama_model_name,
            "lora_library_path": self.lora_library_path,
            "comfyui_lora_expose_path": self.comfyui_lora_expose_path,
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
            comfyui_lora_name=data.get("comfyui_lora_name", ""),
            comfyui_lora_strength=data.get("comfyui_lora_strength", 1.0),
            ollama_url=data.get("ollama_url", "http://127.0.0.1:11434"),
            ollama_path=data.get("ollama_path", ""),
            ollama_model_name=data.get("ollama_model_name", ""),
            lora_library_path=data.get("lora_library_path") or _default_lora_library_path(),
            comfyui_lora_expose_path=data.get("comfyui_lora_expose_path", ""),
        )
