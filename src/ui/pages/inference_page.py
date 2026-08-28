from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QDialog,
    QInputDialog,
    QLabel,
    QPushButton,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QMessageBox,
)

from src.managers.generation_manager import REFERENCE_ROLE_POSE_COMPOSITION, Reference
from src.managers.prompt_assistant_manager import CharacterContext
from src.managers.workspace_manager import WorkspaceManagerError
from src.ui.dialogs.image_preview_dialog import ImagePreviewDialog
from src.ui.dialogs.prompt_assistant_dialog import PromptAssistantDialog
from src.ui.generation_worker import GenerationWorker

# Mission 013: images produced from this page belong to Workspace.images
# (Mission 011 ownership model) — this subfolder is a plain runtime
# destination for ComfyUIEngine's download, not a new persisted field;
# Workspace/WorkspaceStorage are untouched.
GENERATED_IMAGES_SUBFOLDER = "outputs"

# Mission 024: this page's own generic "reference strength" default
# (0-100 slider units, i.e. 0.75) — deliberately not imported from
# comfyui_workflows/comfyui_engine (InferencePage must stay ignorant of
# ComfyUI's own internal name for this concept). Coordinated by mission
# specification with the engine layer's own default, not by a shared
# import.
DEFAULT_REFERENCE_STRENGTH_PERCENT = 75


class InferencePage(QWidget):

    def __init__(
        self,
        generation_manager,
        workspace_manager,
        prompt_manager,
        prompt_assistant_manager,
        character_manager,
    ):
        super().__init__()

        self._generation_manager = generation_manager
        self._workspace_manager = workspace_manager
        # Mission 031: PromptAssistantManager is the sole Prompt Assistant
        # consumer this page ever touches — no direct AI provider
        # import here, see PromptAssistantDialog's own docstring.
        self._prompt_manager = prompt_manager
        self._prompt_assistant_manager = prompt_assistant_manager
        # Mission 034: read-only access to the Workspace's principal
        # Character, resolved only at the moment the Assistant IA
        # dialog opens (see _on_assistant_clicked) — same precedent as
        # CharactersPage(self.character_manager).
        self._character_manager = character_manager
        self._thread = None
        self._worker = None

        # Mission 083: mirrors PromptsPage/CharactersPage/LoRAPage/
        # SettingsPage's own local dirty flag (Missions 038/078) — set
        # only by real user/Assistant edits (_on_prompt_text_changed(),
        # never blocked), never by a programmatic load (set_prompt_text()
        # and the new reset_for_context_change() below both wrap their
        # own self.prompt mutation in blockSignals() and set this
        # explicitly instead).
        self._dirty = False

        # Mission 014: a successful generation no longer persists itself.
        # _pending_path is the downloaded file awaiting an explicit
        # Accept/Reject/Regenerate decision — it exists on disk (written
        # by ComfyUIEngine.download_output(), same as before) but is
        # never added to Workspace.images until Accept.
        self._pending_path = None
        self._pending_pixmap = None

        # Mission 014 final review: the workspace root active when the
        # current generation cycle (in-flight or already pending) was
        # started. A pending/in-flight result belongs exclusively to
        # this workspace context, never to whatever WorkspaceManager.
        # current_workspace happens to be later — WorkspaceManager.
        # create()/open() replace current_workspace outright, with no
        # concept of "this page has an unrelated result in flight".
        self._generation_workspace_root = None

        # Mission 022: a purely transitory reference-image selection —
        # never added to Workspace.images, never written to
        # project.json. The UI only ever holds 0 or 1 path (a plain
        # scalar is enough here); it is converted to a 0..N list only
        # at the InferencePage -> GenerationWorker boundary
        # (_start_generation()), the single point where the collection
        # representation begins. No role/semantics are attached to it.
        self._reference_image_path: Optional[str] = None

        layout = QVBoxLayout(self)

        title = QLabel("Inference")
        title.setStyleSheet("font-size:24px;font-weight:bold;")

        layout.addWidget(title)

        self.generate_button = QPushButton("Générer")
        self.generate_button.clicked.connect(self._on_generate_clicked)

        layout.addWidget(self.generate_button)

        self.prompt = QTextEdit()

        self.prompt.setPlaceholderText("Prompt...")
        self.prompt.textChanged.connect(self._on_prompt_text_changed)

        layout.addWidget(self.prompt)

        # Mission 031: Prompt Assistant minimal — InferencePage is this
        # mission's sole UI consumer of PromptAssistantManager (Option C,
        # a shared service; PromptsPage became its second consumer in
        # Mission 032, reusing the same Manager/Dialog unchanged).
        # "Enregistrer dans Prompts" is independent of the Assistant —
        # it operates on whatever text is currently
        # in self.prompt, typed manually or produced by the Assistant.
        assistant_row = QHBoxLayout()

        self.assistant_button = QPushButton("Assistant IA")
        self.assistant_button.clicked.connect(self._on_assistant_clicked)

        self.save_prompt_button = QPushButton("Enregistrer dans Prompts")
        self.save_prompt_button.setEnabled(False)
        self.save_prompt_button.clicked.connect(self._on_save_prompt_clicked)

        assistant_row.addWidget(self.assistant_button)
        assistant_row.addWidget(self.save_prompt_button)

        layout.addLayout(assistant_row)

        reference_row = QHBoxLayout()

        self.select_reference_button = QPushButton("Sélectionner une image de référence")
        self.select_reference_button.clicked.connect(self._on_select_reference_clicked)

        self.reference_label = QLabel("Aucune référence sélectionnée")

        self.remove_reference_button = QPushButton("Retirer")
        self.remove_reference_button.setEnabled(False)
        self.remove_reference_button.clicked.connect(self._on_remove_reference_clicked)

        reference_row.addWidget(self.select_reference_button)
        reference_row.addWidget(self.reference_label)
        reference_row.addWidget(self.remove_reference_button)

        layout.addLayout(reference_row)

        # Mission 024: visible but disabled while no reference is
        # selected (discoverability, stable layout — same treatment as
        # remove_reference_button), enabled once a reference is
        # selected. Purely transitory: never persisted (project.json or
        # ApplicationSettings), reset to the default alongside the
        # reference selection itself (_clear_reference_selection()).
        strength_row = QHBoxLayout()

        self.reference_strength_label = QLabel("Force de transformation :")

        self.reference_strength_slider = QSlider(Qt.Horizontal)
        self.reference_strength_slider.setRange(0, 100)
        self.reference_strength_slider.setValue(DEFAULT_REFERENCE_STRENGTH_PERCENT)
        self.reference_strength_slider.setEnabled(False)
        self.reference_strength_slider.valueChanged.connect(self._on_reference_strength_changed)

        self.reference_strength_value_label = QLabel(
            self._format_reference_strength(DEFAULT_REFERENCE_STRENGTH_PERCENT)
        )

        strength_row.addWidget(self.reference_strength_label)
        strength_row.addWidget(self.reference_strength_slider)
        strength_row.addWidget(self.reference_strength_value_label)

        layout.addLayout(strength_row)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(240)

        layout.addWidget(self.preview_label)

        validation_buttons = QHBoxLayout()

        self.accept_button = QPushButton("Accepter")
        self.accept_button.clicked.connect(self._on_accept_clicked)
        self.accept_button.setEnabled(False)

        self.reject_button = QPushButton("Rejeter")
        self.reject_button.clicked.connect(self._on_reject_clicked)
        self.reject_button.setEnabled(False)

        self.regenerate_button = QPushButton("Régénérer")
        self.regenerate_button.clicked.connect(self._on_regenerate_clicked)
        self.regenerate_button.setEnabled(False)

        self.preview_enlarge_button = QPushButton("Voir en grand")
        self.preview_enlarge_button.clicked.connect(self._on_enlarge_clicked)
        self.preview_enlarge_button.setEnabled(False)

        validation_buttons.addWidget(self.accept_button)
        validation_buttons.addWidget(self.reject_button)
        validation_buttons.addWidget(self.regenerate_button)
        validation_buttons.addWidget(self.preview_enlarge_button)

        layout.addLayout(validation_buttons)

    def _on_generate_clicked(self):

        prompt_text = self.prompt.toPlainText()

        if not prompt_text.strip():
            QMessageBox.warning(
                self,
                "Prompt vide",
                "Saisissez un prompt avant de générer."
            )
            return

        if not self._workspace_manager.opened:
            QMessageBox.warning(
                self,
                "Aucun projet ouvert",
                "Ouvrez ou créez un projet avant de générer."
            )
            return

        self._start_generation(prompt_text)

    def _on_prompt_text_changed(self):
        # Mission 083: only ever connected to textChanged, so this never
        # fires during a programmatic load protected by
        # self.prompt.blockSignals() (set_prompt_text(),
        # reset_for_context_change()) — genuine manual typing and the
        # Prompt Assistant's result injection (_on_assistant_clicked(),
        # deliberately left unblocked, same precedent as PromptsPage) are
        # the only two ways this can run, and both must mark the prompt
        # dirty.
        self._dirty = True
        self.save_prompt_button.setEnabled(bool(self.prompt.toPlainText().strip()))

    def _on_assistant_clicked(self):
        # Mission 034: the single conversion point (CharacterContext.from_character)
        # is called identically here and in PromptsPage — no separate
        # construction logic duplicated between the two Pages.
        character_context = CharacterContext.from_character(self._character_manager.principal_character)

        dialog = PromptAssistantDialog(
            self._prompt_assistant_manager,
            existing_prompt=self.prompt.toPlainText(),
            character_context=character_context,
            parent=self,
        )

        if dialog.exec() == QDialog.Accepted and dialog.result_text is not None:
            self.prompt.setPlainText(dialog.result_text)

    def _on_save_prompt_clicked(self):

        text = self.prompt.toPlainText()

        if not text.strip():
            return

        # Mission 031: same non-empty-name guard as
        # PromptsPage.create_prompt() — reproduced identically rather
        # than factored out (PromptManager never validates business
        # content, and a shared UI helper for one line would be
        # disproportionate — see Mission 031 specification).
        name, ok = QInputDialog.getText(self, "Nouveau prompt", "Nom :")

        if not ok or not name.strip():
            return

        if self._save_prompt_as_new(name.strip(), text):
            # Mission 083: the text just became a persisted Prompt — the
            # page's own draft is no longer unsaved work from the
            # dirty-state guard's point of view. A further edit marks it
            # dirty again normally via _on_prompt_text_changed().
            self._dirty = False

    def _save_prompt_as_new(self, name: str, text: str) -> bool:
        """
        Mission 083: the single create()+error-handling primitive shared
        by _on_save_prompt_clicked() (name always confirmed non-empty
        beforehand) and confirm_context_change() (same). Deliberately
        does not touch self._dirty nor show any success feedback — both
        callers decide that for themselves; this only creates the Prompt
        and reports whether it succeeded, showing the appropriate
        QMessageBox on either failure path.

        create(name, text=...) — deliberately never select()/
        update_text() afterward: this must never change PromptManager.
        active_prompt_id nor PromptsPage's current selection (see
        Mission 031 specification, pre-implementation verification 2).
        """
        try:
            prompt = self._prompt_manager.create(name, text=text)
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer le nouveau prompt dans le projet : {exc}\n"
                "Le prompt n'a pas été créé."
            )
            return False

        if prompt is None:
            # Mission 036: distinguish "no Workspace open" from "Workspace
            # open without a principal Character" — both make create()
            # return None. Already has workspace_manager (Mission 013),
            # no new dependency needed.
            if not self._workspace_manager.opened:
                QMessageBox.warning(
                    self,
                    "Aucun projet ouvert",
                    "Ouvrez ou créez un projet avant d'enregistrer un prompt."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Aucun personnage",
                    "Ce projet ne possède aucun personnage — créez-en un depuis Characters avant d'enregistrer un prompt."
                )
            return False

        return True

    def _start_generation(self, prompt_text):

        workspace_root = str(self._workspace_manager.current_workspace.root)
        output_directory = str(Path(workspace_root) / GENERATED_IMAGES_SUBFOLDER)

        self._generation_workspace_root = workspace_root

        # Mission 022: the only point where the UI's singular selection
        # becomes a 0..N collection — captured here, before the worker
        # is even constructed, so nothing done to self._reference_image_path
        # afterward (removed, replaced) can ever reach this cycle. A
        # fresh list is built on every call, never mutated afterward.
        # Mission 056: the single element is now an explicit typed
        # Reference (role=pose_composition, the only role with a real
        # generation mechanism today) rather than a bare path — this
        # page is the primitive's real production consumer, not just a
        # legacy caller GenerationManager.generate() happens to still
        # accept.
        reference_images = (
            [Reference(self._reference_image_path, REFERENCE_ROLE_POSE_COMPOSITION)]
            if self._reference_image_path
            else []
        )

        # Mission 024: read fresh at call time, like reference_images
        # above — GenerationManager only ever uses this value when a
        # reference is actually present, so it is harmless to always
        # pass it regardless of whether one is selected.
        reference_strength = self.reference_strength_slider.value() / 100.0

        self.generate_button.setEnabled(False)
        self._set_reference_controls_enabled(False)
        self._set_validation_buttons_enabled(False)

        thread = QThread()
        worker = GenerationWorker(
            self._generation_manager,
            prompt_text,
            output_directory,
            reference_images,
            reference_strength,
        )
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(self._on_generation_finished)
        worker.failed.connect(self._on_generation_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        # worker/thread are captured by value here (not re-read from
        # self._worker/self._thread when this fires, which may be much
        # later) — this is what makes it impossible for this cycle's
        # deferred cleanup to ever act on a newer cycle's objects, even
        # if the user starts a second generation (via Regenerate) before
        # this callback runs (see _cleanup_thread's docstring). Mission
        # 014 does not touch this mechanism.
        thread.finished.connect(lambda: self._cleanup_thread(worker, thread))

        self._thread = thread
        self._worker = worker

        thread.start()

    def _on_generation_finished(self, path):

        if not self._workspace_context_matches(self._generation_workspace_root):
            # The active workspace changed while this generation was
            # in flight (no cancellation exists — Mission 013's
            # accepted limitation, not revisited here). The file was
            # still written correctly into its origin workspace's
            # outputs/ folder (output_directory was fixed at
            # _start_generation() time), but it must never surface as
            # a pending result the user could Accept into whatever
            # workspace is current now — discard it silently instead.
            self._delete_pending_file(path)
            self._generation_workspace_root = None
            self.generate_button.setEnabled(True)
            self._set_reference_controls_enabled(True)
            return

        # Mission 014: the generated file is not registered into
        # Workspace.images here anymore — it becomes the pending result
        # awaiting Accept/Reject/Regenerate. generate_button stays
        # disabled: Accept/Reject/Regenerate is the only way forward
        # from here, avoiding two concurrent paths to start a new
        # generation.
        self._set_pending(path)

    def _on_generation_failed(self, message):

        self._generation_workspace_root = None
        self.generate_button.setEnabled(True)
        self._set_reference_controls_enabled(True)
        self._set_validation_buttons_enabled(False)

        QMessageBox.critical(
            self,
            "Erreur de génération",
            message
        )

    def _on_accept_clicked(self):

        if self._pending_path is None:
            return

        # Defense in depth: reset_for_workspace_change() (subscribed by
        # MainWindow to WORKSPACE_CREATED/OPENED/CLOSED) already
        # invalidates a pending result the moment the workspace context
        # changes — this guard only protects against Accept somehow
        # being reached before that event was delivered/processed.
        if not self._workspace_context_matches(self._generation_workspace_root):
            QMessageBox.warning(
                self,
                "Projet changé",
                "Le projet actif a changé depuis cette génération ; le résultat n'a pas été enregistré."
            )
            self._clear_pending(delete_file=True)
            self.generate_button.setEnabled(True)
            self._set_reference_controls_enabled(True)
            return

        if not Path(self._pending_path).exists():
            QMessageBox.warning(
                self,
                "Fichier introuvable",
                "Le fichier généré n'existe plus sur le disque ; impossible de l'enregistrer."
            )
            self._clear_pending(delete_file=False)
            self.generate_button.setEnabled(True)
            self._set_reference_controls_enabled(True)
            return

        # WorkspaceManager.add_images() runs here, on the Qt main
        # thread — never from the worker itself, since
        # Workspace/WorkspaceManager are plain Python objects with no
        # thread-safety guarantee (Mission 013 architecture decision,
        # unchanged by Mission 014).
        #
        # Mission 067: add_images() now rollbacks Workspace.images and
        # compensates the passthrough-or-copy distinction itself before
        # re-raising on a save() failure — the pending image was never
        # actually added, so nothing here is cleared and no control is
        # re-enabled: the page stays in exactly the same pre-Accept
        # state (pending image still visible, Accepter/Rejeter/
        # Régénérer still available), and a second "Accepter" is a
        # genuine new attempt rather than a silent no-op.
        try:
            self._workspace_manager.add_images([self._pending_path])
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer l'image générée dans le projet : {exc}\n"
                "Le résultat reste en attente — vous pouvez réessayer Accepter ou Rejeter."
            )
            return

        self._clear_pending(delete_file=False)
        self.generate_button.setEnabled(True)
        self._set_reference_controls_enabled(True)

    def _on_reject_clicked(self):

        if self._pending_path is None:
            return

        deleted = self._clear_pending(delete_file=True)
        self.generate_button.setEnabled(True)
        self._set_reference_controls_enabled(True)

        if not deleted:
            QMessageBox.warning(
                self,
                "Suppression impossible",
                "Le fichier temporaire n'a pas pu être supprimé du disque ; "
                "il ne sera pas enregistré, mais peut rester présent sur le disque."
            )

    def _on_regenerate_clicked(self):

        if self._pending_path is None:
            return

        prompt_text = self.prompt.toPlainText()

        deleted = self._clear_pending(delete_file=True)

        if not deleted:
            QMessageBox.warning(
                self,
                "Suppression impossible",
                "L'ancien résultat temporaire n'a pas pu être supprimé du disque ; "
                "une nouvelle génération va tout de même être lancée."
            )

        self._start_generation(prompt_text)

    def _on_enlarge_clicked(self):
        # Mission 015: strictly a passive viewer over the pending file
        # already on disk — ImagePreviewDialog receives only a str
        # (self._pending_path), never a reference to this page or to
        # WorkspaceManager, so it has no way to affect the pending
        # state, Accept/Reject/Regenerate, or Workspace.images. It is
        # also modal (exec()), so no other button here can be clicked
        # while it is open.
        if self._pending_path is None:
            return

        ImagePreviewDialog(self._pending_path, parent=self).exec()

    def _on_select_reference_clicked(self):
        # Mission 022: same file-picker pattern already used by
        # ImagesPage.import_images()/DatasetsPage.import_images() —
        # single-file selection (getOpenFileName, not the plural
        # getOpenFileNames), since this page's UI only ever holds 0 or
        # 1 reference. No existence/business validation is done here:
        # a file removed between selection and Generate is naturally
        # caught as a GenerationError when upload_image() runs.
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner une image de référence",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )

        if not file_path:
            return

        self._reference_image_path = file_path
        self.reference_label.setText(f"{Path(file_path).name} — Pose / composition")
        self.remove_reference_button.setEnabled(True)
        self.reference_strength_slider.setEnabled(True)

    def _on_remove_reference_clicked(self):
        self._clear_reference_selection()

    def _clear_reference_selection(self):
        self._reference_image_path = None
        self.reference_label.setText("Aucune référence sélectionnée")
        self.remove_reference_button.setEnabled(False)
        self.reference_strength_slider.setEnabled(False)
        self.reference_strength_slider.setValue(DEFAULT_REFERENCE_STRENGTH_PERCENT)

    def _on_reference_strength_changed(self, value):
        self.reference_strength_value_label.setText(self._format_reference_strength(value))

    @staticmethod
    def _format_reference_strength(value):
        return f"{value / 100:.2f}"

    def _set_reference_controls_enabled(self, enabled):
        self.select_reference_button.setEnabled(enabled)
        self.remove_reference_button.setEnabled(enabled and self._reference_image_path is not None)
        self.reference_strength_slider.setEnabled(enabled and self._reference_image_path is not None)

    def prompt_text(self) -> str:
        return self.prompt.toPlainText()

    def set_prompt_text(self, text: str) -> None:
        # Mission 033: the intentional public write side of the pair
        # above — lets MainWindow deposit a prompt received from
        # PromptsPage without reaching into self.prompt (a QTextEdit)
        # directly.
        #
        # Mission 083: a programmatic load of a working copy, not new
        # user work — the source text remains protected at its origin
        # (already a persisted Prompt, or still guarded by PromptsPage's
        # own dirty-state if not). blockSignals() prevents
        # _on_prompt_text_changed() from marking this dirty; _dirty and
        # save_prompt_button are resynchronized explicitly instead,
        # exactly as reset_for_context_change() does below. Any further
        # edit made in Inference itself marks it dirty normally.
        self.prompt.blockSignals(True)
        self.prompt.setPlainText(text)
        self.prompt.blockSignals(False)

        self._dirty = False
        self.save_prompt_button.setEnabled(bool(text.strip()))

    def reset_for_workspace_change(self, _payload=None):
        """
        Subscribed by MainWindow to WORKSPACE_CREATED/OPENED/CLOSED/
        RENAMED (never WORKSPACE_SAVED — saving does not change which
        workspace is current, e.g. Accept's own add_images()->save()
        must not invalidate the pending result it is in the middle of
        clearing). Each of those four events means WorkspaceManager.
        current_workspace has just been replaced, cleared, or had its
        root path changed (Mission 027's WORKSPACE_RENAMED) — a pending
        result computed for the previous workspace/root must never be
        offered to the new one. An in-flight generation (no pending
        yet) is deliberately left running — no cancellation exists; its
        result is discarded when it eventually arrives, in
        _on_generation_finished()'s own workspace check above.
        """
        if self._pending_path is not None:
            self._clear_pending(delete_file=True)
            self.generate_button.setEnabled(True)
            self._set_reference_controls_enabled(True)

        # Mission 022: the selected reference is transitory and never
        # tied to Workspace.images/project.json — reset here for the
        # same reason a pending result is invalidated above: it must
        # never silently carry over into whichever workspace is now
        # current.
        self._clear_reference_selection()

    def confirm_context_change(self) -> bool:
        """
        Mission 083: same public contract as PromptsPage/CharactersPage/
        LoRAPage/SettingsPage's own confirm_context_change() — called by
        MainWindow before a Workspace switch (new_project()/
        open_project()) or application close, in each case before any
        irreversible step. Returns True if the caller may proceed, False
        if the transition must be abandoned entirely. If not dirty,
        returns True immediately with no dialog at all.

        Save recreates "Enregistrer dans Prompts"'s exact existing
        contract (always a new Prompt, name entered through the same
        QInputDialog) rather than silently generating a name — cancelling
        that name dialog, an empty/invalid name, no principal Character/
        Workspace, or a persistence failure all abandon the whole
        transition (False), leaving self.prompt and self._dirty
        untouched, exactly like a Cancel choice below.
        """
        if not self._dirty:
            return True

        text = self.prompt.toPlainText()

        if not text.strip():
            # Mirrors _on_save_prompt_clicked()'s own empty-text no-op:
            # nothing a Save could meaningfully persist, so there is
            # nothing left to protect either.
            self._dirty = False
            return True

        choice = self._confirm_discard_before_switch()

        if choice == QMessageBox.Cancel:
            return False

        if choice == QMessageBox.Save:
            name, ok = QInputDialog.getText(self, "Nouveau prompt", "Nom :")

            if not ok or not name.strip():
                return False

            if not self._save_prompt_as_new(name.strip(), text):
                return False

            self._dirty = False

        return True

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

    def reset_for_context_change(self, _payload=None):
        """
        Subscribed by MainWindow to WORKSPACE_CREATED/OPENED/CLOSED only
        — never WORKSPACE_RENAMED, unlike reset_for_workspace_change()
        above, which stays exclusively responsible for _pending_path/the
        reference selection and keeps its own unrelated 4-event
        subscription unchanged. A rename does not invalidate the
        prompt's own root-independent content, so self.prompt/self._dirty
        must survive it intact — exactly like PromptsPage/CharactersPage/
        LoRAPage/SettingsPage's own reset_for_context_change(), which is
        likewise never subscribed to WORKSPACE_RENAMED.
        """
        self.prompt.blockSignals(True)
        self.prompt.setPlainText("")
        self.prompt.blockSignals(False)

        self._dirty = False
        self.save_prompt_button.setEnabled(False)

    def _workspace_context_matches(self, expected_root):
        return (
            expected_root is not None
            and self._workspace_manager.opened
            and str(self._workspace_manager.current_workspace.root) == expected_root
        )

    def _set_pending(self, path):

        self._pending_path = path

        pixmap = QPixmap(path)
        self._pending_pixmap = pixmap if not pixmap.isNull() else None
        self._update_preview()

        self._set_validation_buttons_enabled(True)

    def _clear_pending(self, delete_file):
        """
        Returns True if there was nothing to delete or deletion
        succeeded, False if delete_file was requested and the file
        could not be removed (caller decides whether/how to surface
        that to the user).
        """
        path = self._pending_path

        self._pending_path = None
        self._pending_pixmap = None
        self._generation_workspace_root = None
        self.preview_label.clear()
        self._set_validation_buttons_enabled(False)

        if delete_file and path is not None:
            return self._delete_pending_file(path)

        return True

    @staticmethod
    def _delete_pending_file(path):
        # A pending result is never persisted, so a file already
        # missing (e.g. removed manually) or undeletable (e.g.
        # permission error) must never crash the UI — it is simply no
        # longer tracked as pending either way. A file that is already
        # gone counts as success (the desired end state — "no file left
        # behind" — already holds; nothing to warn the user about).
        # Only a genuine deletion failure (still present, still on
        # disk) is reported back to the caller as such.
        try:
            Path(path).unlink()
            return True
        except FileNotFoundError:
            return True
        except OSError:
            return False

    def _set_validation_buttons_enabled(self, enabled):
        self.accept_button.setEnabled(enabled)
        self.reject_button.setEnabled(enabled)
        self.regenerate_button.setEnabled(enabled)
        self.preview_enlarge_button.setEnabled(enabled)

    def _update_preview(self):

        if self._pending_pixmap is None:
            self.preview_label.clear()
            return

        scaled = self._pending_pixmap.scaled(
            self.preview_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_preview()

    def _cleanup_thread(self, worker, thread):
        """
        Runs once this specific cycle's thread has fully stopped
        (thread.finished). worker/thread are the exact objects created
        for this cycle, captured by value at connect() time in
        _start_generation() — never read from self._worker/
        self._thread here, so a second generation the user already
        started (whose objects now live in self._worker/self._thread)
        can never be torn down by this, older, callback.

        self._worker/self._thread are only reset to None if they still
        point at *this* cycle's objects — if a newer cycle has already
        replaced them, those newer references are left untouched.
        """
        worker.deleteLater()
        thread.deleteLater()

        if self._worker is worker:
            self._worker = None

        if self._thread is thread:
            self._thread = None

    def shutdown(self):
        """
        Called from MainWindow.closeEvent() so a generation in progress
        never leaves a dangling thread behind when the application
        closes (Mission 013 — minimal handling, no cancellation), and
        so a pending, not-yet-accepted result never survives as an
        orphan file nor gets silently persisted (Mission 014).
        """
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()

        self._clear_pending(delete_file=True)
