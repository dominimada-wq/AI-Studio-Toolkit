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

        # Mission 078: local UI-only dirty-state for the 7 identity
        # fields — never persisted, never exposed to CharacterManager.
        # _loaded_character_id tracks whichever principal_character_id
        # the fiche currently reflects, distinct from
        # CharacterManager.active_character_id itself — same role as
        # PromptsPage._loaded_prompt_id (Mission 038).
        self._dirty = False
        self._loaded_character_id = None

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

        # Mission 078: textChanged only ever fires from real user typing,
        # since every programmatic write to these 7 fields goes through
        # _load_identity_fields(), which wraps all of them in
        # blockSignals() — same rationale as PromptsPage._on_text_changed
        # (Mission 038).
        self.name_edit.textChanged.connect(self._on_identity_changed)
        self.bio_edit.textChanged.connect(self._on_identity_changed)
        self.description_edit.textChanged.connect(self._on_identity_changed)
        self.character_lock_edit.textChanged.connect(self._on_identity_changed)
        self.personality_edit.textChanged.connect(self._on_identity_changed)
        self.interests_edit.textChanged.connect(self._on_identity_changed)
        self.trigger_token_edit.textChanged.connect(self._on_identity_changed)

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

        try:
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
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer l'identité dans le projet : {exc}\n"
                "Les informations précédentes ont été restaurées."
            )
            # Mission 078: _load_identity_fields() bypasses the dirty-state
            # guard on purpose — the just-rejected input must always be
            # replaced by the restored Domain value here, regardless of
            # _dirty, exactly like Mission 074's own failure contract.
            self._load_identity_fields(self._find_displayed_character(principal_id))
            return

        # Mission 078: the save intent is satisfied — nothing from the
        # UI's point of view remains unsaved, regardless of update()'s own
        # True/False return. No field resync needed: the 7 fields already
        # display exactly what was just persisted.
        self._dirty = False

    def _on_identity_changed(self):
        # Mission 078: only ever connected to textChanged, so this never
        # fires during a programmatic load protected by
        # _load_identity_fields()'s blockSignals() — genuine user typing
        # is the only way this can run.
        self._dirty = True

    def _refresh_character_list(self):
        # Mission 078: extracted from the former single update_characters()
        # — rebuilds list_widget only, shared by update_characters()/
        # reset_for_context_change(). Returns (principal_id,
        # displayed_character) so callers never need a second, separate
        # lookup pass.

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

        return principal_id, displayed_character

    def _find_displayed_character(self, principal_id):
        if principal_id is None:
            return None

        for character in self.character_manager.list_characters():
            if character["character_id"] == principal_id:
                return character

        return None

    def _load_identity_fields(self, displayed_character):
        # Mission 078: unconditional — bypasses the dirty-state guard on
        # purpose. Shared by update_characters() (only when the principal
        # Character actually changed), reset_for_context_change() (real
        # context change, must always discard any draft) and
        # save_identity()'s/confirm_context_change()'s failure branches
        # (must always show the restored Domain value, never the rejected
        # input, per the Mission 074 contract).
        fields = (
            self.name_edit,
            self.bio_edit,
            self.description_edit,
            self.character_lock_edit,
            self.personality_edit,
            self.interests_edit,
            self.trigger_token_edit,
        )

        for field in fields:
            field.blockSignals(True)

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

        for field in fields:
            field.blockSignals(False)

        self._dirty = False

    def update_characters(self, _payload=None):
        # Mission 078: subscribed (see main_window.py) only to
        # WORKSPACE_SAVED/WORKSPACE_RENAMED and CHARACTER_CREATED —
        # WORKSPACE_CREATED/OPENED/CLOSED and CHARACTER_SELECTED/DELETED
        # are handled exclusively by reset_for_context_change() below, so
        # this dirty-draft protection never depends on subscriber
        # ordering between the two methods.
        principal_id, displayed_character = self._refresh_character_list()

        if principal_id == self._loaded_character_id and self._dirty:
            # Non-destructive refresh (e.g. WORKSPACE_SAVED fired by an
            # unrelated LoRA/Dataset/etc. mutation elsewhere, or
            # CHARACTER_CREATED for a second Character that never becomes
            # principal) while the user has a real unsaved draft — the 7
            # fields are left untouched. When nothing is dirty, the same
            # Character's fields are still refreshed unconditionally: a
            # clean fiche must always reflect the latest Domain state,
            # including a mutation applied directly through
            # CharacterManager.update() outside this Page's own
            # save_identity() (e.g. by another code path or test).
            return

        self._load_identity_fields(displayed_character)
        self._loaded_character_id = principal_id

    def reset_for_context_change(self, _payload=None):
        """
        Subscribed by MainWindow to WORKSPACE_CREATED/OPENED/CLOSED and
        CHARACTER_SELECTED/CHARACTER_DELETED — never to
        update_characters()'s own events. A naive principal_id vs
        _loaded_character_id comparison would wrongly read None == None as
        "nothing changed" when switching between two Workspaces that both
        happen to have zero Character (a defensive edge case, never
        reachable through the real "1 Workspace = 1 principal Character"
        UI, but exercised by the historical multi-character test suite) —
        silently carrying a stray draft across a genuine Workspace/
        Character switch. This method is therefore the sole, unconditional
        Presentation path for these 5 events, mirroring
        PromptsPage.reset_for_context_change() (Mission 038).
        """
        principal_id, displayed_character = self._refresh_character_list()
        self._load_identity_fields(displayed_character)
        self._loaded_character_id = principal_id

    def confirm_context_change(self) -> bool:
        """
        Mission 078: same role as PromptsPage.confirm_context_change()
        (Mission 069) — called by MainWindow before a Workspace switch
        (new_project()/open_project()) that would otherwise let
        reset_for_context_change() silently discard an unsaved identity
        draft once current_workspace is replaced, too late for a genuine
        Save or Cancel. Returns True if the caller may proceed with the
        switch, False if it must be abandoned entirely (Cancel, or a
        save() failure — which must never let the switch continue).
        Mission 079 reuses this same guard from closeEvent() before
        closing the whole application.
        """
        if not self._dirty:
            return True

        box = QMessageBox(self)
        box.setWindowTitle("Modifications non enregistrées")
        box.setText(
            "La fiche d'identité du personnage contient des modifications "
            "non enregistrées. Que souhaitez-vous faire ?"
        )
        box.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        box.setButtonText(QMessageBox.Save, "Enregistrer")
        box.setButtonText(QMessageBox.Discard, "Ignorer les modifications")
        box.setButtonText(QMessageBox.Cancel, "Annuler")
        box.setDefaultButton(QMessageBox.Cancel)
        choice = box.exec()

        if choice == QMessageBox.Cancel:
            return False

        if choice == QMessageBox.Save:
            principal_id = self.character_manager.principal_character_id

            if principal_id is None:
                # Nothing to persist into (no principal Character) — the
                # draft is knowingly discarded here rather than silently
                # kept across the switch.
                self._dirty = False
                return True

            try:
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
            except WorkspaceManagerError as exc:
                QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Impossible d'enregistrer l'identité avant de changer de projet : {exc}"
                )
                self._load_identity_fields(self._find_displayed_character(principal_id))
                return False

        self._dirty = False
        return True
