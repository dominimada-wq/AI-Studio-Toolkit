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
    QTextEdit,
    QMessageBox,
)


class PromptsPage(QWidget):

    def __init__(self, prompt_manager):
        super().__init__()

        self.prompt_manager = prompt_manager

        layout = QVBoxLayout(self)

        title = QLabel("Prompts")
        title.setStyleSheet("font-size:24px;font-weight:bold;")
        layout.addWidget(title)

        prompt_buttons = QHBoxLayout()

        self.new_button = QPushButton("Nouveau prompt")
        self.new_button.clicked.connect(self.create_prompt)

        self.delete_button = QPushButton("Supprimer")
        self.delete_button.clicked.connect(self.delete_prompt)

        prompt_buttons.addWidget(self.new_button)
        prompt_buttons.addWidget(self.delete_button)

        layout.addLayout(prompt_buttons)

        self.prompt_list = QListWidget()
        self.prompt_list.currentItemChanged.connect(self.on_prompt_selection_changed)

        layout.addWidget(self.prompt_list)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Texte du prompt...")

        layout.addWidget(self.text_edit)

        self.save_button = QPushButton("Enregistrer le texte")
        self.save_button.clicked.connect(self.save_text)

        layout.addWidget(self.save_button)

    def create_prompt(self):

        name, ok = QInputDialog.getText(self, "Nouveau prompt", "Nom :")

        if not ok or not name.strip():
            return

        prompt = self.prompt_manager.create(name.strip())

        if prompt is None:
            QMessageBox.warning(
                self,
                "Aucun personnage actif",
                "Sélectionnez un personnage avant de créer un prompt."
            )

    def delete_prompt(self):

        item = self.prompt_list.currentItem()

        if item is None:
            return

        self.prompt_manager.delete(item.data(Qt.UserRole))

    def on_prompt_selection_changed(self, current, previous):

        if current is None:
            return

        self.prompt_manager.select(current.data(Qt.UserRole))

    def save_text(self):

        if self.prompt_manager.active_prompt_id is None:
            QMessageBox.warning(
                self,
                "Aucun prompt sélectionné",
                "Sélectionnez un prompt avant d'enregistrer du texte."
            )
            return

        self.prompt_manager.update_text(self.text_edit.toPlainText())

    def update_prompts(self, _payload=None):

        prompts = self.prompt_manager.list_prompts()
        active_prompt_id = self.prompt_manager.active_prompt_id

        self.prompt_list.blockSignals(True)
        self.prompt_list.clear()

        active_text = ""

        for prompt in prompts:

            item = QListWidgetItem(prompt["name"])
            item.setData(Qt.UserRole, prompt["prompt_id"])

            self.prompt_list.addItem(item)

            if prompt["prompt_id"] == active_prompt_id:
                self.prompt_list.setCurrentItem(item)
                active_text = prompt["text"]

        self.prompt_list.blockSignals(False)

        self.text_edit.setPlainText(active_text)
