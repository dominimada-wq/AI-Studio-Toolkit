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
    QLineEdit,
    QTextEdit,
    QMessageBox,
)

from src.managers.prompt_assistant_manager import CharacterContext
from src.managers.workspace_manager import WorkspaceManagerError
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

    def __init__(self, prompt_manager, prompt_assistant_manager, character_manager, workspace_manager):
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
        # Mission 036: source of authority for "no Workspace open" vs
        # "Workspace open without a principal Character" — see
        # create_prompt()/save_as_new_prompt() below.
        self.workspace_manager = workspace_manager

        # Mission 038: local UI-only dirty-state — never persisted, never
        # exposed to PromptManager. _loaded_prompt_id tracks whichever
        # active_prompt_id text_edit currently reflects, distinct from
        # PromptManager.active_prompt_id itself (see update_prompts()/
        # reset_for_context_change() below).
        self._dirty = False
        self._loaded_prompt_id = None

        layout = QVBoxLayout(self)

        title = QLabel("Prompts")
        title.setStyleSheet("font-size:24px;font-weight:bold;")
        layout.addWidget(title)

        prompt_buttons = QHBoxLayout()

        self.new_button = QPushButton("Nouveau prompt")
        self.new_button.clicked.connect(self.create_prompt)

        self.delete_button = QPushButton("Supprimer")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_prompt)

        prompt_buttons.addWidget(self.new_button)
        prompt_buttons.addWidget(self.delete_button)

        layout.addLayout(prompt_buttons)

        self.prompt_list = QListWidget()
        self.prompt_list.currentItemChanged.connect(self.on_prompt_selection_changed)

        layout.addWidget(self.prompt_list)

        # Renommage (Mission 053) — édition immédiate sur perte de focus,
        # totalement indépendant du dirty-state de text_edit ci-dessous
        # (Mission 038) : name_edit n'a pas de dirty-state propre et est
        # repeuplé à chaque appel de _refresh_prompt_list(), y compris
        # les rafraîchissements non destructifs qui laissent text_edit
        # intact — même principe que LoRAPage.name_edit (Mission 052)
        # vis-à-vis du panneau Metadata.
        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self.rename_prompt)

        layout.addWidget(self.name_edit)

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

        # Mission 035: depends only on text_edit's current content, not
        # on active_prompt_id — same enable/disable reasoning as
        # send_to_inference_button below. Distinct from save_button:
        # this always creates a new Prompt, it never updates the
        # currently active one (see save_as_new_prompt()).
        self.save_as_new_prompt_button = QPushButton("Enregistrer comme nouveau Prompt…")
        self.save_as_new_prompt_button.setEnabled(False)
        self.save_as_new_prompt_button.clicked.connect(self.save_as_new_prompt)

        layout.addWidget(self.save_as_new_prompt_button)

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
            # Mission 036: distinguish that edge case from "no Workspace
            # open" at all, which also makes create() return None.
            if not self.workspace_manager.opened:
                QMessageBox.warning(
                    self,
                    "Aucun projet ouvert",
                    "Ouvrez ou créez un projet avant de créer un prompt."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Aucun personnage",
                    "Ce projet ne possède aucun personnage — créez-en un depuis Characters avant de créer un prompt."
                )

    def delete_prompt(self):

        item = self.prompt_list.currentItem()

        if item is None:
            return

        if self._dirty:
            box = QMessageBox(self)
            box.setWindowTitle("Modifications non enregistrées")
            box.setText(
                "Le prompt actuellement affiché contient des modifications non "
                "enregistrées, qui seront perdues si vous le supprimez. Continuer ?"
            )
            box.setStandardButtons(QMessageBox.Discard | QMessageBox.Cancel)
            box.setButtonText(QMessageBox.Discard, "Supprimer")
            box.setButtonText(QMessageBox.Cancel, "Annuler")
            box.setDefaultButton(QMessageBox.Cancel)

            if box.exec() == QMessageBox.Cancel:
                # Mission 038: no deletion, text and dirty state untouched.
                return

        # Mission 038: PromptManager.delete() resets active_prompt_id to
        # None synchronously (the deleted prompt is always the currently
        # active one via this UI — no multi-select exists) before
        # publishing PROMPT_DELETED, which update_prompts() reacts to via
        # its normal active_prompt_id/_loaded_prompt_id comparison —
        # clearing the editor and resetting dirty=False without any
        # dedicated handling needed here.
        self.prompt_manager.delete(item.data(Qt.UserRole))

    def on_prompt_selection_changed(self, current, previous):

        if current is None:
            # Mission 063: "Supprimer" must always reflect whether there
            # is currently something to delete.
            self.delete_button.setEnabled(False)
            return

        # Mission 038: captured now, before any Manager call below can
        # reentrantly trigger update_prompts() -> _refresh_prompt_list()
        # -> prompt_list.clear(), which deletes the underlying C++
        # QListWidgetItem `current` wraps (e.g. "Enregistrer" below calls
        # update_text(), which publishes WORKSPACE_SAVED synchronously).
        # Reading current.data() again afterward would then raise.
        target_prompt_id = current.data(Qt.UserRole)

        if self._dirty:
            choice = self._confirm_discard_before_switch()

            if choice == QMessageBox.Cancel:
                # Mission 038: prompt_manager.select() is never called —
                # active_prompt_id stays untouched. Revert the widget's
                # own native selection (already changed by Qt before this
                # handler ran) back to `previous`, with signals blocked
                # to avoid recursively re-entering this same handler.
                self.prompt_list.blockSignals(True)
                self.prompt_list.setCurrentItem(previous)
                self.prompt_list.blockSignals(False)
                # Mission 063: the selection actually in effect after this
                # revert is `previous`, not `current` — the button must
                # follow it, not the switch attempt that got cancelled.
                self.delete_button.setEnabled(previous is not None)
                return

            if choice == QMessageBox.Save:
                self.prompt_manager.update_text(self.text_edit.toPlainText())

            self._dirty = False

        self.prompt_manager.select(target_prompt_id)
        self.delete_button.setEnabled(True)

    def _confirm_discard_before_switch(self):
        box = QMessageBox(self)
        box.setWindowTitle("Modifications non enregistrées")
        box.setText(
            "Le prompt actuel contient des modifications non enregistrées. "
            "Que souhaitez-vous faire ?"
        )
        box.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        box.setButtonText(QMessageBox.Save, "Enregistrer")
        box.setButtonText(QMessageBox.Discard, "Ignorer les modifications")
        box.setButtonText(QMessageBox.Cancel, "Annuler")
        box.setDefaultButton(QMessageBox.Cancel)
        return box.exec()

    def confirm_context_change(self) -> bool:
        """
        Mission 069: called by MainWindow before a Workspace switch
        (new_project()/open_project()) that would otherwise let
        reset_for_context_change() silently discard an unsaved draft —
        those events fire only after current_workspace has already been
        replaced, too late for a genuine Save or Cancel. Reuses
        _confirm_discard_before_switch()'s existing Save/Discard/Cancel
        dialog verbatim, never duplicating its logic. Returns True if
        the caller may proceed with the switch, False if it must be
        abandoned entirely (Cancel, or a save() failure — which must
        never let the switch continue). If not dirty, returns True
        immediately with no dialog at all — New/Open behaves exactly as
        before. On a successful Save, the draft is persisted into the
        still-active (old) Workspace; the subsequent
        reset_for_context_change() (triggered by the Workspace switch
        that follows) performs its own, already-existing cleanup — no
        cleanup duplicated here.
        """

        if not self._dirty:
            return True

        choice = self._confirm_discard_before_switch()

        if choice == QMessageBox.Cancel:
            return False

        if choice == QMessageBox.Save:
            try:
                self.prompt_manager.update_text(self.text_edit.toPlainText())
            except WorkspaceManagerError as exc:
                QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Impossible d'enregistrer le prompt avant de changer de projet : {exc}"
                )
                return False
            self._dirty = False

        return True

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
        # Mission 038: only ever connected to textChanged, so this never
        # fires during a programmatic load protected by
        # text_edit.blockSignals() (update_prompts()/
        # reset_for_context_change()) — genuine user typing and the
        # Prompt Assistant's "Utiliser ce texte" (deliberately left
        # unblocked, see _on_assistant_clicked) are the only two ways
        # this can run, and both must mark the editor dirty.
        self._dirty = True
        self._update_action_buttons_enabled()

    def _update_action_buttons_enabled(self):
        has_text = bool(self.text_edit.toPlainText().strip())
        self.send_to_inference_button.setEnabled(has_text)
        self.save_as_new_prompt_button.setEnabled(has_text)

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
        # Mission 038: the save intent is satisfied here regardless of
        # update_text()'s own True/False return — its idempotent False
        # (text already matches the persisted value) still means there is
        # nothing left unsaved from the UI's point of view.
        self._dirty = False

    def save_as_new_prompt(self):
        # Mission 035: unlike save_text(), this never touches whatever
        # Prompt is currently active (if any) — it always creates a
        # distinct new one from the text currently visible, regardless
        # of active_prompt_id. Same non-empty-text guard as
        # _on_send_to_inference_clicked, defensive in addition to the
        # button's own enabled state.
        text = self.text_edit.toPlainText()

        if not text.strip():
            return

        # Same dialog idiom already used by create_prompt() and by
        # InferencePage._on_save_prompt_clicked() — reproduced
        # identically rather than factored out (see Mission 031
        # specification: PromptManager never validates business
        # content, a shared UI helper for one line would be
        # disproportionate).
        name, ok = QInputDialog.getText(self, "Nouveau prompt", "Nom :")

        if not ok or not name.strip():
            return

        prompt = self.prompt_manager.create(name.strip(), text=text)

        if prompt is None:
            # Same edge case and wording as create_prompt(), including
            # the Mission 036 distinction below.
            if not self.workspace_manager.opened:
                QMessageBox.warning(
                    self,
                    "Aucun projet ouvert",
                    "Ouvrez ou créez un projet avant de créer un prompt."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Aucun personnage",
                    "Ce projet ne possède aucun personnage — créez-en un depuis Characters avant de créer un prompt."
                )
            return

        # Explicit select() here — deliberately different from
        # InferencePage._on_save_prompt_clicked(), which must never
        # select() to avoid silently changing PromptsPage's own
        # selection from another page. Here PromptsPage is choosing its
        # own new selection following its own action: the user just
        # asked to save this exact text as a new Prompt, so making it
        # the visible selection (Mission 035) is the intended outcome —
        # not a side-effect to avoid.
        self.prompt_manager.select(prompt.prompt_id)

    def rename_prompt(self):

        if self.prompt_manager.active_prompt_id is None:
            return

        self.prompt_manager.update_name(self.name_edit.text())

    def _refresh_prompt_list(self, active_prompt_id):
        # Mission 038: shared by update_prompts()/reset_for_context_change()
        # — rebuilds prompt_list only, never touches text_edit. Signals
        # blocked so setCurrentItem() below never re-enters
        # on_prompt_selection_changed().
        prompts = sorted(
            self.prompt_manager.list_prompts(),
            key=lambda prompt: prompt["name"].lower(),
        )

        self.prompt_list.blockSignals(True)
        self.prompt_list.clear()

        active_name = ""

        for prompt in prompts:

            item = QListWidgetItem(prompt["name"])
            item.setData(Qt.UserRole, prompt["prompt_id"])

            self.prompt_list.addItem(item)

            if prompt["prompt_id"] == active_prompt_id:
                self.prompt_list.setCurrentItem(item)
                active_name = prompt["name"]

        self.prompt_list.blockSignals(False)
        # Mission 063: blockSignals() above suppresses currentItemChanged,
        # so setCurrentItem()/clear() never reach on_prompt_selection_changed()
        # during a rebuild — the button's state must be recomputed here,
        # covering both update_prompts() and reset_for_context_change().
        self.delete_button.setEnabled(self.prompt_list.currentItem() is not None)

        # Mission 053: name_edit is repopulated on every call, including
        # non-destructive refreshes — it has no dirty-state of its own,
        # unlike text_edit, which this method never touches.
        self.name_edit.setText(active_name)

    def update_prompts(self, _payload=None):
        # Mission 038: subscribed (see main_window.py) only to
        # WORKSPACE_SAVED/RENAMED, CHARACTER_CREATED and PROMPT_CREATED/
        # SELECTED/DELETED — never to the 5 context-reset events handled
        # exclusively by reset_for_context_change() below. active_prompt_id
        # therefore never goes from None to None here in a way that would
        # actually mean "context changed" (see reset_for_context_change()'s
        # docstring for why that distinction matters).
        active_prompt_id = self.prompt_manager.active_prompt_id

        self._refresh_prompt_list(active_prompt_id)

        if active_prompt_id == self._loaded_prompt_id:
            # Non-destructive refresh (e.g. WORKSPACE_SAVED fired by
            # "Enregistrer dans Prompts" from InferencePage, or
            # PROMPT_CREATED without a select()) — text_edit and dirty
            # are left untouched.
            return

        prompt = self.prompt_manager.active_prompt
        active_text = prompt.text if prompt is not None else ""

        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(active_text)
        self.text_edit.blockSignals(False)

        self._dirty = False
        self._loaded_prompt_id = active_prompt_id
        self._update_action_buttons_enabled()

    def reset_for_context_change(self, _payload=None):
        """
        Subscribed by MainWindow to WORKSPACE_CREATED/OPENED/CLOSED and
        CHARACTER_SELECTED/DELETED — never to update_prompts()'s own
        events. These are exactly the events PromptManager itself treats
        as a context reset (_on_context_changed(), already run by the
        time this fires, always leaving active_prompt_id at None) — a
        naive active_prompt_id vs _loaded_prompt_id comparison would
        wrongly read None == None as "nothing changed" whenever no
        Prompt was selected beforehand (e.g. an unsaved draft with no
        active Prompt at all), silently carrying a stale draft across an
        actual Workspace/Character switch. This method is therefore the
        sole, unconditional Presentation path for these 5 events —
        deliberately not layered on top of update_prompts(), so the
        result never depends on EventBus subscriber ordering.
        """
        self._refresh_prompt_list(None)

        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText("")
        self.text_edit.blockSignals(False)

        self._dirty = False
        self._loaded_prompt_id = None
        self._update_action_buttons_enabled()
