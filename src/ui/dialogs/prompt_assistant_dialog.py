"""
PromptAssistantDialog — Mission 031's UI entry point for
PromptAssistantManager, opened from InferencePage (the mission's first,
tactical consumer — see PromptAssistantManager's own docstring for the
long-term Option C direction). Presents two explicit intents, "Créer"
and "Améliorer": the existing prompt is never sent to the backend
silently — when "Améliorer" is chosen, it is shown read-only in this
dialog before the user can trigger generation. Runs the assist call off
the Qt main thread (QThread + PromptAssistantWorker), the same pattern
already validated by InferencePage/GenerationWorker.
"""

from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from src.ui.prompt_assistant_worker import PromptAssistantWorker


class PromptAssistantDialog(QDialog):

    def __init__(self, prompt_assistant_manager, existing_prompt="", character_context=None, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Assistant IA")

        # Mission 031 smoke test follow-up: the default QDialog size was
        # too small to read/work with generated prompts comfortably.
        # QDialog is resizable by default (no setFixedSize anywhere) —
        # this only sets a larger, more usable starting size; no
        # size/position persistence is introduced.
        # Mission 061: same availableGeometry()-bounded default as
        # MainWindow (Mission 060) — 800x700 stays the preferred size
        # whenever the screen has room for it.
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            width = min(800, available.width())
            height = min(700, available.height())
        else:
            width, height = 800, 700
        self.resize(width, height)

        self._prompt_assistant_manager = prompt_assistant_manager
        self._existing_prompt = existing_prompt
        # Mission 034: an already-resolved CharacterContext | None,
        # handed in by the caller (PromptsPage/InferencePage) — this
        # dialog never knows Character or CharacterManager, never
        # inspects individual fields, only decides at generate-time
        # whether to pass this object through or None (see
        # _on_generate_clicked below).
        self._character_context = character_context
        self._mode = "create"
        self._thread = None
        self._worker = None

        # Mission 031: the only way this dialog ever hands a result
        # back to its caller — set only when the user explicitly clicks
        # "Utiliser ce texte" below, never implicitly.
        self.result_text = None

        layout = QVBoxLayout(self)

        mode_row = QHBoxLayout()

        # Mission 041: checkable + an exclusive QButtonGroup make these
        # a real mode selector rather than two independent action
        # buttons — native Qt :checked rendering, no custom stylesheet.
        # _set_mode() below remains the single source of truth for both
        # self._mode and each button's checked state, so the logical
        # and visual state can never drift apart regardless of which
        # button fired the click.
        self.create_mode_button = QPushButton("Créer un nouveau prompt")
        self.create_mode_button.setCheckable(True)
        # Mission 041 smoke test follow-up: without this, Qt makes the
        # first QPushButton of the dialog its "default button" (Enter
        # shortcut) — a second, unrelated native highlight that stayed
        # on this button even while logically unchecked, making it
        # visually indistinguishable from the actually-checked sibling.
        self.create_mode_button.setAutoDefault(False)
        self.create_mode_button.clicked.connect(lambda: self._set_mode("create"))
        mode_row.addWidget(self.create_mode_button)

        self._mode_button_group = QButtonGroup(self)
        self._mode_button_group.setExclusive(True)
        self._mode_button_group.addButton(self.create_mode_button)

        # Mission 031: "Améliorer" is only offered when there is
        # something to improve — with no existing prompt, "Créer" is
        # the only meaningful intent, so the button is never even
        # created rather than shown disabled.
        if existing_prompt.strip():
            self.improve_mode_button = QPushButton("Améliorer le prompt actuel")
            self.improve_mode_button.setCheckable(True)
            self.improve_mode_button.setAutoDefault(False)
            self.improve_mode_button.clicked.connect(lambda: self._set_mode("improve"))
            mode_row.addWidget(self.improve_mode_button)
            self._mode_button_group.addButton(self.improve_mode_button)
        else:
            self.improve_mode_button = None

        layout.addLayout(mode_row)

        self.mode_status_label = QLabel("")
        layout.addWidget(self.mode_status_label)

        # Mission 031: shown only in "improve" mode — the explicit,
        # visible confirmation that the existing prompt is used as a
        # base, never a silent transmission.
        self.existing_prompt_label = QLabel("Prompt actuel utilisé comme base :")
        self.existing_prompt_preview = QTextEdit(existing_prompt)
        self.existing_prompt_preview.setReadOnly(True)
        self.existing_prompt_preview.setMinimumHeight(90)
        layout.addWidget(self.existing_prompt_label)
        # Mission 031 smoke test follow-up: stretch factors give each
        # text area a fair, expanding share of the dialog's height —
        # comfortable room for the source prompt, the request, and
        # especially the result (see result_edit below), both at the
        # larger starting size and when the user resizes the dialog.
        layout.addWidget(self.existing_prompt_preview, 1)

        layout.addWidget(QLabel("Votre demande :"))
        self.request_edit = QTextEdit()
        self.request_edit.setPlaceholderText("Décrivez ce que vous voulez...")
        self.request_edit.setMinimumHeight(90)
        layout.addWidget(self.request_edit, 1)

        # Mission 034: created only when a usable identity context
        # exists — same idiom as improve_mode_button above (never
        # shown greyed out). Unchecked by default in every case: the
        # identity is never injected implicitly.
        if character_context is not None:
            self.use_identity_checkbox = QCheckBox("Utiliser l'identité du personnage")
            self.use_identity_checkbox.setChecked(False)
            layout.addWidget(self.use_identity_checkbox)
        else:
            self.use_identity_checkbox = None

        self.generate_button = QPushButton("Générer")
        self.generate_button.clicked.connect(self._on_generate_clicked)
        layout.addWidget(self.generate_button)

        self.busy_label = QLabel("")
        layout.addWidget(self.busy_label)

        layout.addWidget(QLabel("Résultat proposé :"))
        self.result_edit = QTextEdit()
        self.result_edit.setReadOnly(True)
        self.result_edit.setMinimumHeight(150)
        # Larger stretch than existing_prompt_preview/request_edit above
        # — the result is what the user actually reads and works with
        # at length, so it gets a bigger share of the extra vertical
        # space once the dialog is resized larger than its 800x700 start.
        layout.addWidget(self.result_edit, 2)

        self.use_result_button = QPushButton("Utiliser ce texte")
        self.use_result_button.setEnabled(False)
        self.use_result_button.clicked.connect(self._on_use_result_clicked)
        layout.addWidget(self.use_result_button)

        # Mission 031: disabled while a request is in flight (see
        # _on_generate_clicked) — no cancellation mechanism exists in
        # this codebase (same accepted limitation as InferencePage's
        # own generation cycle), so closing this modal dialog mid-call
        # must never be offered rather than leave a worker/thread
        # signaling into an already-destroyed dialog.
        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button)

        self._set_mode("create")

    def _set_mode(self, mode):
        self._mode = mode
        # Mission 041: the single point enforcing that exactly one mode
        # button is checked, matching self._mode — never left to the
        # QButtonGroup's own click-driven exclusivity alone.
        self.create_mode_button.setChecked(mode == "create")
        if self.improve_mode_button is not None:
            self.improve_mode_button.setChecked(mode == "improve")
        self.existing_prompt_label.setVisible(mode == "improve")
        self.existing_prompt_preview.setVisible(mode == "improve")
        self.mode_status_label.setText(
            "Mode : Améliorer le prompt actuel"
            if mode == "improve"
            else "Mode : Créer un nouveau prompt"
        )

    def _on_generate_clicked(self):

        request_text = self.request_edit.toPlainText()

        if not request_text.strip():
            QMessageBox.warning(self, "Demande vide", "Décrivez votre demande avant de générer.")
            return

        existing_prompt = self._existing_prompt if self._mode == "improve" else ""

        # Mission 034: the only place deciding whether the resolved
        # snapshot is actually sent — unchecked (or absent) checkbox
        # means None, exactly the pre-Mission 034 call shape.
        character_context = (
            self._character_context
            if self.use_identity_checkbox is not None and self.use_identity_checkbox.isChecked()
            else None
        )

        self._set_controls_enabled(False)
        self.use_result_button.setEnabled(False)
        self.busy_label.setText("Génération en cours...")

        thread = QThread()
        worker = PromptAssistantWorker(
            self._prompt_assistant_manager, request_text, existing_prompt, character_context
        )
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(self._on_assist_finished)
        worker.failed.connect(self._on_assist_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        # worker/thread captured by value here — same guarantee already
        # established by InferencePage._start_generation()/_cleanup_thread.
        thread.finished.connect(lambda: self._cleanup_thread(worker, thread))

        self._thread = thread
        self._worker = worker

        thread.start()

    def _on_assist_finished(self, text):
        self.busy_label.setText("")
        self._set_controls_enabled(True)
        self.result_edit.setPlainText(text)
        self.use_result_button.setEnabled(True)

    def _on_assist_failed(self, message):
        self.busy_label.setText("")
        self._set_controls_enabled(True)
        # Mission 040: result_edit already holds the last successful
        # result (untouched by this failed attempt) — use_result_button
        # must track that content, not just the outcome of this call.
        self.use_result_button.setEnabled(bool(self.result_edit.toPlainText().strip()))
        QMessageBox.critical(self, "Erreur de l'assistant", message)

    def _set_controls_enabled(self, enabled):
        self.generate_button.setEnabled(enabled)
        self.create_mode_button.setEnabled(enabled)
        if self.improve_mode_button is not None:
            self.improve_mode_button.setEnabled(enabled)
        self.cancel_button.setEnabled(enabled)

    def _on_use_result_clicked(self):
        self.result_text = self.result_edit.toPlainText()
        self.accept()

    def _cleanup_thread(self, worker, thread):
        worker.deleteLater()
        thread.deleteLater()

        if self._worker is worker:
            self._worker = None

        if self._thread is thread:
            self._thread = None
