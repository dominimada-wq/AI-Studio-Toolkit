from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QDialog,
    QInputDialog,
    QTextEdit,
    QMessageBox,
)

from src.ui.dialogs.prompt_assistant_dialog import PromptAssistantDialog


class PromptsPage(QWidget):

    def __init__(self, prompt_manager, prompt_assistant_manager):
        super().__init__()

        self.prompt_manager = prompt_manager
        # Mission 032: second real consumer of the Mission 031 shared
        # service (Option C) — same instance InferencePage already
        # uses, injected once from the composition root. No direct AI
        # provider import here, see PromptAssistantDialog's own docstring.
        self.prompt_assistant_manager = prompt_assistant_manager

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

        # Mission 032: always enabled, like InferencePage.assistant_button
        # — mode availability (Créer only vs Créer+Améliorer) is decided
        # inside PromptAssistantDialog itself, from whatever
        # existing_prompt this page passes it (see _on_assistant_clicked).
        self.assistant_button = QPushButton("Assistant IA")
        self.assistant_button.clicked.connect(self._on_assistant_clicked)

        layout.addWidget(self.assistant_button)

        self.save_button = QPushButton("Enregistrer le texte")
        self.save_button.clicked.connect(self.save_text)

        layout.addWidget(self.save_button)

    def create_prompt(self):

        name, ok = QInputDialog.getText(self, "Nouveau prompt", "Nom :")

        if not ok or not name.strip():
            return

        prompt = self.prompt_manager.create(name.strip())

        if prompt is None:
            # Mission 029: PromptManager.create() now follows the
            # Workspace's principal Character (Mission 026/028), not a
            # manual selection the hidden multi-character UI no longer
            # offers a way to make — this can now only fire for the
            # genuine edge case of a Workspace with zero Character at all.
            QMessageBox.warning(
                self,
                "Aucun personnage",
                "Ce projet ne possède aucun personnage — créez-en un depuis Characters avant de créer un prompt."
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

    def _on_assistant_clicked(self):
        # Mission 032: "Améliorer" must only ever be offered when a
        # Prompt is actually selected — not merely when text_edit is
        # non-empty (it is never disabled, so stray unsaved text could
        # exist with no Prompt selected at all). existing_prompt is
        # explicitly forced to "" in that case, regardless of
        # text_edit's own content.
        if self.prompt_manager.active_prompt_id is not None:
            # The currently visible editor text, possibly edited but not
            # yet saved via "Enregistrer le texte" — never re-read from
            # the persisted Prompt Domain object.
            existing_prompt = self.text_edit.toPlainText()
        else:
            existing_prompt = ""

        dialog = PromptAssistantDialog(
            self.prompt_assistant_manager,
            existing_prompt=existing_prompt,
            parent=self,
        )

        if dialog.exec() == QDialog.Accepted and dialog.result_text is not None:
            # Replaces the editor content only — never persists. The
            # user must still click "Enregistrer le texte" explicitly.
            self.text_edit.setPlainText(dialog.result_text)

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
