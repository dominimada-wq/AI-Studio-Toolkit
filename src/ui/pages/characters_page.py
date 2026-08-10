from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QInputDialog,
    QMessageBox,
)


class CharactersPage(QWidget):

    def __init__(self, character_manager):
        super().__init__()

        self.character_manager = character_manager

        layout = QVBoxLayout(self)

        title = QLabel("Characters")
        title.setStyleSheet("font-size:24px;font-weight:bold;")

        layout.addWidget(title)

        buttons = QHBoxLayout()

        self.new_button = QPushButton("Nouveau personnage")
        self.new_button.clicked.connect(self.create_character)

        self.delete_button = QPushButton("Supprimer")
        self.delete_button.clicked.connect(self.delete_character)

        buttons.addWidget(self.new_button)
        buttons.addWidget(self.delete_button)

        layout.addLayout(buttons)

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self.on_selection_changed)

        layout.addWidget(self.list_widget)

    def create_character(self):

        name, ok = QInputDialog.getText(self, "Nouveau personnage", "Nom :")

        if not ok or not name.strip():
            return

        character = self.character_manager.create(name.strip())

        if character is None:
            QMessageBox.warning(
                self,
                "Aucun projet ouvert",
                "Ouvrez ou créez un projet avant de créer un personnage."
            )

    def delete_character(self):

        item = self.list_widget.currentItem()

        if item is None:
            return

        self.character_manager.delete(item.data(Qt.UserRole))

    def on_selection_changed(self, current, previous):

        if current is None:
            return

        self.character_manager.select(current.data(Qt.UserRole))

    def update_characters(self, _payload=None):

        # blockSignals prevents a feedback loop: rebuild -> setCurrentItem
        # -> currentItemChanged -> select() -> event -> rebuild -> ...
        self.list_widget.blockSignals(True)

        self.list_widget.clear()

        active_id = self.character_manager.active_character_id

        for character in self.character_manager.list_characters():

            item = QListWidgetItem(character["name"])
            item.setData(Qt.UserRole, character["character_id"])

            self.list_widget.addItem(item)

            if character["character_id"] == active_id:
                self.list_widget.setCurrentItem(item)

        self.list_widget.blockSignals(False)
