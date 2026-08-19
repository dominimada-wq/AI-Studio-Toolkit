from PySide6.QtCore import Qt, Signal
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

from src.managers.prompt_assistant_manager import CharacterContext
from src.ui.dialogs.prompt_assistant_dialog import PromptAssistantDialog


class PromptsPage(QWidget):

    # Mission 033: carries the text currently visible in text_edit at
    # the moment of the click — never re-read from the persisted
    # Prompt. MainWindow is the sole subscriber (Option A — Qt signal +
    # MainWindow mediator, see docs/missions/MISSION_033.md section 4.1
    # for why the EventBus is deliberately not used here: this is a
    # Presentation-layer intent, not a Domain mutation published by a
    # Manager). PromptsPage never imports or references InferencePage.
    send_to_inference_requested = Signal(str)

    def __init__(self, prompt_manager, prompt_assistant_manager, character_manager):
        super().__init__()

        self.prompt_manager = prompt_manager
        # Mission 032: second real consumer of the Mission 031 shared
        # service (Option C) — same instance InferencePage already
        # uses, injected once from the composition root. No direct AI
        # provider import here, see PromptAssistantDialog's own docstring.
        self.prompt_assistant_manager = prompt_assistant_manager
        # Mission 034: read-only access to the Workspace's principal
        # Character, resolved only at the moment the Assistant IA
        # dialog opens (see _on_assistant_clicked) — same precedent as
        # CharactersPage(self.character_manager).
        self.character_manager = character_manager

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
        self.text_edit.textChanged.connect(self._on_text_changed)

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

        # Mission 033: depends only on text_edit's current content, not
        # on active_prompt_id — same reasoning as _on_assistant_clicked's
        # existing_prompt, mirrored here as a dynamic enable/disable
        # (InferencePage.save_prompt_button's pattern, the closest
        # existing analog for an optional action on the editor's
        # current text), rather than a message shown on click.
        self.send_to_inference_button = QPushButton("Envoyer vers Inference")
        self.send_to_inference_button.setEnabled(False)
        self.send_to_inference_button.clicked.connect(self._on_send_to_inference_clicked)

        layout.addWidget(self.send_to_inference_button)

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

        # Mission 034: the single conversion point (CharacterContext.from_character)
        # is called identically here and in InferencePage — no separate
        # construction logic duplicated between the two Pages.
        character_context = CharacterContext.from_character(self.character_manager.principal_character)

        dialog = PromptAssistantDialog(
            self.prompt_assistant_manager,
            existing_prompt=existing_prompt,
            character_context=character_context,
            parent=self,
        )

        if dialog.exec() == QDialog.Accepted and dialog.result_text is not None:
            # Replaces the editor content only — never persists. The
            # user must still click "Enregistrer le texte" explicitly.
            self.text_edit.setPlainText(dialog.result_text)

    def _on_text_changed(self):
        self.send_to_inference_button.setEnabled(bool(self.text_edit.toPlainText().strip()))

    def _on_send_to_inference_clicked(self):
        text = self.text_edit.toPlainText()

        if not text.strip():
            return

        self.send_to_inference_requested.emit(text)

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
