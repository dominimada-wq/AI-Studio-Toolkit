from dataclasses import dataclass, field


@dataclass
class Project:

    name: str = ""

    root: str = ""

    images_dir: str = ""

    datasets_dir: str = ""

    models_dir: str = ""

    outputs_dir: str = ""

    training_dir: str = ""

    logs_dir: str = ""

    captions_dir: str = ""

    config: dict = field(default_factory=dict)