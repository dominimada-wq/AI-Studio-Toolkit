import json
from pathlib import Path


class ProjectIO:

    PROJECT_FILE = "project.json"

    # --------------------------------------------------

    @staticmethod
    def create_project(folder):

        folder = Path(folder)

        folder.mkdir(parents=True, exist_ok=True)

        directories = [
            "images",
            "datasets",
            "datasets/train",
            "datasets/validation",
            "captions",
            "models",
            "models/checkpoints",
            "models/loras",
            "models/vae",
            "models/embeddings",
            "outputs",
            "training",
            "logs",
        ]

        for directory in directories:
            (folder / directory).mkdir(parents=True, exist_ok=True)

        project = {
            "name": folder.name,
            "version": "0.4",
            "images": [],
            "datasets": [],
            "models": [],
            "loras": [],
            "training": {},
            "settings": {},
        }

        ProjectIO.save_project(folder, project)

        return project

    # --------------------------------------------------

    @staticmethod
    def load_project(folder):

        folder = Path(folder)

        file = folder / ProjectIO.PROJECT_FILE

        if not file.exists():
            return None

        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)

    # --------------------------------------------------

    @staticmethod
    def save_project(folder, project):

        folder = Path(folder)

        with open(
            folder / ProjectIO.PROJECT_FILE,
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                project,
                f,
                indent=4,
                ensure_ascii=False,
            )