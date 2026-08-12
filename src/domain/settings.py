from dataclasses import dataclass


@dataclass
class Settings:

    theme: str = ""

    language: str = ""

    def to_dict(self) -> dict:
        return {
            "theme": self.theme,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        return cls(
            theme=data.get("theme", ""),
            language=data.get("language", ""),
        )
