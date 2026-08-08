from pathlib import Path

from .project import Project
from .project_io import ProjectIO


class ProjectManager:
    """
    Gestionnaire central des projets.
    """

    def __init__(self):

        self.current_project = None
        self.current_folder = None

    # --------------------------------------------------

    @property
    def opened(self):

        return self.current_project is not None

    # --------------------------------------------------

    def create(self, folder):

        folder = Path(folder)

        ProjectIO.create_project(folder)

        self.current_project = ProjectIO.load_project(folder)

        self.current_folder = folder

        return self.current_project

    # --------------------------------------------------

    def open(self, folder):

        folder = Path(folder)

        self.current_project = ProjectIO.load_project(folder)

        self.current_folder = folder

        return self.current_project

    # --------------------------------------------------

    def save(self):

        if self.current_project is None:
            return

        ProjectIO.save_project(
            self.current_folder,
            self.current_project
        )

    # --------------------------------------------------

    def close(self):

        self.current_project = None
        self.current_folder = None

    # --------------------------------------------------

    @property
    def name(self):

        if self.current_project is None:
            return ""

        return self.current_project.get("name", "")

    # --------------------------------------------------

    @property
    def version(self):

        if self.current_project is None:
            return ""

        return self.current_project.get("version", "")

    # --------------------------------------------------

    @property
    def images(self):

        if self.current_project is None:
            return []

        return self.current_project.get("images", [])

    # --------------------------------------------------

    @property
    def datasets(self):

        if self.current_project is None:
            return []

        return self.current_project.get("datasets", [])

    # --------------------------------------------------

    @property
    def models(self):

        if self.current_project is None:
            return []

        return self.current_project.get("models", [])

    # --------------------------------------------------

    @property
    def loras(self):

        if self.current_project is None:
            return []

        return self.current_project.get("loras", [])