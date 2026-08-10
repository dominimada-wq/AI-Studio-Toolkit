from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QGridLayout,
    QFrame,
)


class DashboardCard(QFrame):

    def __init__(self, title, value="0"):

        super().__init__()

        self.setFrameShape(QFrame.Shape.Box)

        layout = QVBoxLayout(self)

        self.title = QLabel(title)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.value = QLabel(value)
        self.value.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title.setStyleSheet("""
            font-size:16px;
            font-weight:bold;
        """)

        self.value.setStyleSheet("""
            font-size:28px;
            color:#4CAF50;
            font-weight:bold;
        """)

        layout.addWidget(self.title)
        layout.addWidget(self.value)


class DashboardPage(QWidget):

    def __init__(self):

        super().__init__()

        main = QVBoxLayout(self)

        title = QLabel("Dashboard")
        title.setStyleSheet("""
            font-size:28px;
            font-weight:bold;
        """)

        subtitle = QLabel("Bienvenue dans AI Studio Toolkit")

        main.addWidget(title)
        main.addWidget(subtitle)

        grid = QGridLayout()

        self.projectCard = DashboardCard("Projet", "Aucun")
        self.imagesCard = DashboardCard("Images", "0")
        self.datasetsCard = DashboardCard("Datasets", "0")
        self.modelsCard = DashboardCard("Models", "0")
        self.lorasCard = DashboardCard("LoRA", "0")
        self.trainingCard = DashboardCard("Training", "Idle")

        grid.addWidget(self.projectCard, 0, 0)
        grid.addWidget(self.imagesCard, 0, 1)
        grid.addWidget(self.datasetsCard, 0, 2)

        grid.addWidget(self.modelsCard, 1, 0)
        grid.addWidget(self.lorasCard, 1, 1)
        grid.addWidget(self.trainingCard, 1, 2)

        main.addLayout(grid)

        self.newProjectButton = QPushButton("Créer un projet")
        self.openProjectButton = QPushButton("Ouvrir un projet")
        self.importImagesButton = QPushButton("Importer des images")
        self.trainingButton = QPushButton("Lancer un entraînement")

        main.addWidget(self.newProjectButton)
        main.addWidget(self.openProjectButton)
        main.addWidget(self.importImagesButton)
        main.addWidget(self.trainingButton)

        main.addStretch()

    def update_project(self, project):

        if project is None:

            self.projectCard.value.setText("Aucun")
            self.imagesCard.value.setText("0")
            self.datasetsCard.value.setText("0")
            self.modelsCard.value.setText("0")
            self.lorasCard.value.setText("0")

            return

        self.projectCard.value.setText(
            project.get("name", "Projet")
        )

        self.imagesCard.value.setText(
            str(len(project.get("images", [])))
        )

        # Real datasets live under each Character, not on the workspace's
        # own vestigial "datasets" field (never populated since Mission
        # 001 — see Mission 004's audit). (X or []) tolerates both a
        # missing key and an explicit null, for "characters" and for each
        # character's own "datasets".
        total_datasets = sum(
            len(character.get("datasets") or [])
            for character in (project.get("characters") or [])
        )
        self.datasetsCard.value.setText(str(total_datasets))

        self.modelsCard.value.setText(
            str(len(project.get("models", [])))
        )

        self.lorasCard.value.setText(
            str(len(project.get("loras", [])))
        )