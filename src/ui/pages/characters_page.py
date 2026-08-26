from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QTextEdit,
    QInputDialog,
    QMessageBox,
)

from src.managers.workspace_manager import WorkspaceManagerError


class CharactersPage(QWidget):

    def __init__(self, character_manager, workspace_manager):
        super().__init__()

        self.character_manager = character_manager
        # Mission 036: source of authority for "no Workspace open" vs
        # "Workspace open without a principal Character" — see
        # save_identity() below. Same precedent already established by
        # InferencePage._workspace_manager (Mission 013).
        self.workspace_manager = workspace_manager

        layout = QVBoxLayout(self)

        title = QLabel("Characters")
        title.setStyleSheet("font-size:24px;font-weight:bold;")

        layout.addWidget(title)

        # Mission 026 (UX revision): multi-character CRUD controls are
        # kept fully wired for internal/test compatibility (the Domain
        # still supports N characters per Workspace — see
        # CharacterManager) but hidden from the UI — the target product
        # UX is "1 Workspace = 1 principal Character", auto-created and
        # auto-selected on WORKSPACE_CREATED, so a user never needs to
        # see or use this list/these buttons. setVisible(False) rather
        # than removing the widgets: they stay fully functional
        # (addItem/currentItem/click still work programmatically),
        # which is exactly what the historical multi-character tests
        # rely on to prove internal compatibility.
        buttons = QHBoxLayout()

        self.new_button = QPushButton("Nouveau personnage")
        self.new_button.clicked.connect(self.create_character)
        self.new_button.setVisible(False)

        self.delete_button = QPushButton("Supprimer")
        self.delete_button.clicked.connect(self.delete_character)
        self.delete_button.setVisible(False)

        buttons.addWidget(self.new_button)
        buttons.addWidget(self.delete_button)

        layout.addLayout(buttons)

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self.on_selection_changed)
        self.list_widget.setVisible(False)

        layout.addWidget(self.list_widget)

        # --- Identité ---

        identity_title = QLabel("Identité")
        identity_title.setStyleSheet("font-size:16px;font-weight:bold;")
        layout.addWidget(identity_title)

        identity_form = QFormLayout()

        self.name_edit = QLineEdit()
        self.bio_edit = QTextEdit()

        identity_form.addRow("Nom :", self.name_edit)
        identity_form.addRow("Biographie :", self.bio_edit)

        layout.addLayout(identity_form)

        # --- Apparence / identité visuelle ---

        appearance_title = QLabel("Apparence / identité visuelle")
        appearance_title.setStyleSheet("font-size:16px;font-weight:bold;")
        layout.addWidget(appearance_title)

        appearance_form = QFormLayout()

        self.description_edit = QTextEdit()
        self.character_lock_edit = QTextEdit()

        appearance_form.addRow("Description physique :", self.description_edit)
        appearance_form.addRow("Character Lock :", self.character_lock_edit)

        layout.addLayout(appearance_form)

        # --- Personnalité ---

        personality_title = QLabel("Personnalité")
        personality_title.setStyleSheet("font-size:16px;font-weight:bold;")
        layout.addWidget(personality_title)

        personality_form = QFormLayout()

        self.personality_edit = QTextEdit()

        personality_form.addRow("Personnalité :", self.personality_edit)

        layout.addLayout(personality_form)

        # --- Goûts et centres d'intérêt ---

        interests_title = QLabel("Goûts et centres d'intérêt")
        interests_title.setStyleSheet("font-size:16px;font-weight:bold;")
        layout.addWidget(interests_title)

        interests_form = QFormLayout()

        self.interests_edit = QTextEdit()

        interests_form.addRow("Goûts et centres d'intérêt :", self.interests_edit)

        layout.addLayout(interests_form)

        # --- Informations techniques IA ---

        ai_title = QLabel("Informations techniques IA")
        ai_title.setStyleSheet("font-size:16px;font-weight:bold;")
        layout.addWidget(ai_title)

        ai_form = QFormLayout()

        self.trigger_token_edit = QLineEdit()

        ai_form.addRow("Trigger token :", self.trigger_token_edit)

        layout.addLayout(ai_form)

        self.save_identity_button = QPushButton("Enregistrer l'identité")
        self.save_identity_button.clicked.connect(self.save_identity)

        layout.addWidget(self.save_identity_button)

    def create_character(self):

        name, ok = QInputDialog.getText(self, "Nouveau personnage", "Nom :")

        if not ok or not name.strip():
            return

        try:
            character = self.character_manager.create(name.strip())
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer le nouveau personnage dans le projet : {exc}\n"
                "Le personnage n'a pas été créé."
            )
            return

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

    def save_identity(self):

        # Mission 026 (post-smoke-test revision): the fiche now edits
        # CharacterManager.principal_character_id — the Workspace's
        # principal Character, falling back to the first Character when
        # nothing is actively selected — rather than requiring
        # active_character_id to have been set through the historical
        # (now hidden) list-selection mechanism. CharactersPage
        # represents that Character directly; saving its own fiche must
        # never depend on a selection step the user can no longer make.
        principal_id = self.character_manager.principal_character_id

        if principal_id is None:
            # Mission 036: principal_character_id is None both when no
            # Workspace is open and when one is open with zero
            # Character — WorkspaceManager.opened is the only reliable
            # way to tell them apart (see Mission 036 specification).
            if not self.workspace_manager.opened:
                QMessageBox.warning(
                    self,
                    "Aucun projet ouvert",
                    "Ouvrez ou créez un projet avant d'enregistrer l'identité d'un personnage."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Aucun personnage sélectionné",
                    "Sélectionnez un personnage avant d'enregistrer son identité."
                )
            return

        self.character_manager.update(
            principal_id,
            name=self.name_edit.text(),
            bio=self.bio_edit.toPlainText(),
            description=self.description_edit.toPlainText(),
            character_lock=self.character_lock_edit.toPlainText(),
            personality=self.personality_edit.toPlainText(),
            interests=self.interests_edit.toPlainText(),
            trigger_token=self.trigger_token_edit.text(),
        )

    def update_characters(self, _payload=None):

        # blockSignals prevents a feedback loop: rebuild -> setCurrentItem
        # -> currentItemChanged -> select() -> event -> rebuild -> ...
        self.list_widget.blockSignals(True)

        self.list_widget.clear()

        active_id = self.character_manager.active_character_id
        # Mission 026: the fiche displays principal_character_id (with
        # its active_character-then-first-Character fallback), decoupled
        # from active_id, which continues to drive only the (now hidden)
        # list's highlighted item — preserved for internal/test
        # consistency with the historical multi-character mechanism.
        principal_id = self.character_manager.principal_character_id

        displayed_character = None

        for character in self.character_manager.list_characters():

            item = QListWidgetItem(character["name"])
            item.setData(Qt.UserRole, character["character_id"])

            self.list_widget.addItem(item)

            if character["character_id"] == active_id:
                self.list_widget.setCurrentItem(item)

            if character["character_id"] == principal_id:
                displayed_character = character

        self.list_widget.blockSignals(False)

        if displayed_character is None:
            self.name_edit.setText("")
            self.bio_edit.setPlainText("")
            self.description_edit.setPlainText("")
            self.character_lock_edit.setPlainText("")
            self.personality_edit.setPlainText("")
            self.interests_edit.setPlainText("")
            self.trigger_token_edit.setText("")
        else:
            self.name_edit.setText(displayed_character["name"])
            self.bio_edit.setPlainText(displayed_character["bio"])
            self.description_edit.setPlainText(displayed_character["description"])
            self.character_lock_edit.setPlainText(displayed_character["character_lock"])
            self.personality_edit.setPlainText(displayed_character["personality"])
            self.interests_edit.setPlainText(displayed_character["interests"])
            self.trigger_token_edit.setText(displayed_character["trigger_token"])
