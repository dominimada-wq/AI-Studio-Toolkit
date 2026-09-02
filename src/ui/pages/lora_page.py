from PySide6.QtCore import Qt, QSize, QItemSelectionModel
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QTabWidget,
    QInputDialog,
    QFileDialog,
    QMessageBox,
)

from src.managers.lora_library_manager import LoRALibraryError
from src.managers.workspace_manager import WorkspaceManagerError
from src.ui.dialogs.image_preview_dialog import UNAVAILABLE_MESSAGE

THUMBNAIL_PREVIEW_SIZE = QSize(128, 128)
NO_THUMBNAIL_MESSAGE = "Aucune miniature."


class LoRAPage(QWidget):

    def __init__(self, lora_manager, workspace_manager, lora_library_manager, application_settings_manager):
        super().__init__()

        self.lora_manager = lora_manager
        # Mission 036: source of authority for "no Workspace open" vs
        # "Workspace open without a principal Character" — see
        # create_lora() below.
        self.workspace_manager = workspace_manager
        # Mission 088: Application-level, entirely independent of any
        # Workspace/Character — see add_to_central_library() below.
        self.lora_library_manager = lora_library_manager
        self.application_settings_manager = application_settings_manager

        # Mission 078: local UI-only dirty-state for the 4 metadata
        # fields only (engine/architecture/trigger_word/version) — never
        # persisted, never exposed to LoRAManager. _loaded_lora_id tracks
        # whichever active_lora_id the metadata form currently reflects —
        # same role as PromptsPage._loaded_prompt_id (Mission 038).
        # name_edit/files_list/thumbnail have no draft of their own
        # (unchanged from their pre-existing save-on-blur/read-only
        # behavior) and are always resynced regardless of this flag.
        self._metadata_dirty = False
        self._loaded_lora_id = None

        # Mission 090: same role as _metadata_dirty/_loaded_lora_id
        # above, but for the central-library tab's own editable form
        # (name/engine/architecture/trigger_word/version) — a fully
        # separate flag/id pair, never shared with the Personnage tab's,
        # since the two tabs edit two entirely independent Managers.
        self._library_metadata_dirty = False
        self._loaded_library_lora_id = None

        layout = QVBoxLayout(self)

        title = QLabel("LoRA")
        title.setStyleSheet("font-size:24px;font-weight:bold;")
        layout.addWidget(title)

        # Mission 089: the Character-scoped surface (unchanged logic,
        # unchanged widget names) now lives in its own tab, alongside a
        # second, strictly Application-level tab consuming only
        # LoRALibraryManager — the two collections are never merged,
        # each tab reads/writes through its own Manager exclusively.
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        character_tab = QWidget()
        character_layout = QVBoxLayout(character_tab)

        lora_buttons = QHBoxLayout()

        self.new_button = QPushButton("Nouvelle LoRA")
        self.new_button.clicked.connect(self.create_lora)

        self.delete_button = QPushButton("Supprimer")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_lora)

        # Mission 088: enablement follows the same active_lora_id source
        # as choose_thumbnail_button/save_metadata_button — see
        # _update_metadata_buttons_state() below.
        self.add_to_library_button = QPushButton("Ajouter à la bibliothèque centrale")
        self.add_to_library_button.setEnabled(False)
        self.add_to_library_button.clicked.connect(self.add_to_central_library)

        lora_buttons.addWidget(self.new_button)
        lora_buttons.addWidget(self.delete_button)
        lora_buttons.addWidget(self.add_to_library_button)

        character_layout.addLayout(lora_buttons)

        self.lora_list = QListWidget()
        self.lora_list.currentItemChanged.connect(self.on_lora_selection_changed)

        character_layout.addWidget(self.lora_list)

        # Renommage (Mission 052) — édition immédiate sur perte de focus,
        # distinct du bouton "Enregistrer les métadonnées" ci-dessous
        # (Mission 047) : le nom identifie la LoRA elle-même, ce n'est
        # pas une métadonnée au sens de sa fiche engine/architecture/
        # trigger_word/version.
        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self.rename_lora)

        character_layout.addWidget(self.name_edit)

        self.import_files_button = QPushButton("Importer des fichiers")
        self.import_files_button.clicked.connect(self.import_files)

        character_layout.addWidget(self.import_files_button)

        self.files_list = QListWidget()
        self.files_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.files_list.itemSelectionChanged.connect(self._update_files_button_state)

        character_layout.addWidget(self.files_list)

        self.remove_files_button = QPushButton("Retirer les fichiers sélectionnés")
        self.remove_files_button.setEnabled(False)
        self.remove_files_button.clicked.connect(self.remove_selected_files)

        character_layout.addWidget(self.remove_files_button)

        # --- Métadonnées (Mission 047) ---

        metadata_title = QLabel("Métadonnées")
        metadata_title.setStyleSheet("font-size:16px;font-weight:bold;")
        character_layout.addWidget(metadata_title)

        metadata_form = QFormLayout()

        self.engine_edit = QLineEdit()
        self.architecture_edit = QLineEdit()
        self.trigger_word_edit = QLineEdit()
        self.version_edit = QLineEdit()

        metadata_form.addRow("Engine :", self.engine_edit)
        metadata_form.addRow("Architecture :", self.architecture_edit)
        metadata_form.addRow("Trigger word :", self.trigger_word_edit)
        metadata_form.addRow("Version :", self.version_edit)

        character_layout.addLayout(metadata_form)

        # Mission 078: textChanged only ever fires from real user typing,
        # since every programmatic write to these 4 fields goes through
        # _load_metadata_fields(), which wraps them in blockSignals() —
        # same rationale as PromptsPage._on_text_changed (Mission 038).
        self.engine_edit.textChanged.connect(self._on_metadata_changed)
        self.architecture_edit.textChanged.connect(self._on_metadata_changed)
        self.trigger_word_edit.textChanged.connect(self._on_metadata_changed)
        self.version_edit.textChanged.connect(self._on_metadata_changed)

        self.thumbnail_label = QLabel(NO_THUMBNAIL_MESSAGE)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setFixedSize(THUMBNAIL_PREVIEW_SIZE)

        character_layout.addWidget(self.thumbnail_label)

        thumbnail_buttons = QHBoxLayout()

        self.choose_thumbnail_button = QPushButton("Choisir une miniature…")
        self.choose_thumbnail_button.clicked.connect(self.choose_thumbnail)

        self.save_metadata_button = QPushButton("Enregistrer les métadonnées")
        self.save_metadata_button.clicked.connect(self.save_metadata)

        thumbnail_buttons.addWidget(self.choose_thumbnail_button)
        thumbnail_buttons.addWidget(self.save_metadata_button)

        character_layout.addLayout(thumbnail_buttons)

        self.tab_widget.addTab(character_tab, "Personnage")

        # --- Bibliothèque centrale (Mission 089) ---
        #
        # Strictly Application-level: reads/writes only through
        # self.lora_library_manager, never self.lora_manager. Consultation,
        # editing (Mission 090) and deletion, plus two independent import
        # paths — copy from the active Character-scoped LoRA (Mission 088,
        # Personnage tab) and direct import from disk (Mission 092, this
        # tab) — both funnel through the same LoRALibraryManager.import_lora()
        # call, never a second pipeline. No Character/Workspace association
        # yet.

        library_tab = QWidget()
        library_layout = QVBoxLayout(library_tab)

        # Mission 092: always enabled — no active-entry precondition,
        # mirrors new_button/create_lora() rather than the other
        # central-tab buttons (save/delete), which require a selection.
        self.import_to_library_button = QPushButton("Importer depuis le disque…")
        self.import_to_library_button.clicked.connect(self.import_to_library_from_disk)

        library_layout.addWidget(self.import_to_library_button)

        self.library_list = QListWidget()
        self.library_list.currentItemChanged.connect(self.on_library_selection_changed)

        library_layout.addWidget(self.library_list)

        library_metadata_title = QLabel("Métadonnées")
        library_metadata_title.setStyleSheet("font-size:16px;font-weight:bold;")
        library_layout.addWidget(library_metadata_title)

        library_form = QFormLayout()

        # Mission 090: name has no widget of its own before this
        # mission — only the list item's combined text ever displayed
        # it. The 4 metadata fields switch from read-only QLabel (M089)
        # to editable QLineEdit — a deliberate, conscious change: this
        # tab stops being pure consultation and becomes a real edit
        # form, per the architect's explicit M090 decision.
        self.library_name_edit = QLineEdit()
        self.library_name_edit.textChanged.connect(self._on_library_metadata_changed)
        self.library_engine_edit = QLineEdit()
        self.library_engine_edit.textChanged.connect(self._on_library_metadata_changed)
        self.library_architecture_edit = QLineEdit()
        self.library_architecture_edit.textChanged.connect(self._on_library_metadata_changed)
        self.library_trigger_word_edit = QLineEdit()
        self.library_trigger_word_edit.textChanged.connect(self._on_library_metadata_changed)
        self.library_version_edit = QLineEdit()
        self.library_version_edit.textChanged.connect(self._on_library_metadata_changed)

        library_form.addRow("Nom :", self.library_name_edit)
        library_form.addRow("Engine :", self.library_engine_edit)
        library_form.addRow("Architecture :", self.library_architecture_edit)
        library_form.addRow("Trigger word :", self.library_trigger_word_edit)
        library_form.addRow("Version :", self.library_version_edit)

        library_layout.addLayout(library_form)

        self.library_thumbnail_label = QLabel(NO_THUMBNAIL_MESSAGE)
        self.library_thumbnail_label.setAlignment(Qt.AlignCenter)
        self.library_thumbnail_label.setFixedSize(THUMBNAIL_PREVIEW_SIZE)

        library_layout.addWidget(self.library_thumbnail_label)

        # Mission 090: enabled only while a real, unsaved change exists
        # (see _update_library_metadata_button_state()) — deliberately
        # stricter than the Personnage tab's save_metadata_button
        # (always enabled once a LoRA is active, dirty or not), per the
        # architect's explicit requirement for this tab.
        self.save_library_metadata_button = QPushButton("Enregistrer")
        self.save_library_metadata_button.setEnabled(False)
        self.save_library_metadata_button.clicked.connect(self.save_library_metadata)

        library_layout.addWidget(self.save_library_metadata_button)

        self.delete_from_library_button = QPushButton("Supprimer")
        self.delete_from_library_button.setEnabled(False)
        self.delete_from_library_button.clicked.connect(self.delete_from_library)

        library_layout.addWidget(self.delete_from_library_button)

        self.tab_widget.addTab(library_tab, "Bibliothèque centrale")

        self._update_metadata_buttons_state()
        # Mission 089: populates the central-library tab immediately at
        # startup — the registry may already contain entries loaded from
        # disk before any LORA_LIBRARY_IMPORTED/DELETED event ever fires.
        self.update_central_library()

    def create_lora(self):

        name, ok = QInputDialog.getText(self, "Nouvelle LoRA", "Nom :")

        if not ok or not name.strip():
            return

        try:
            lora = self.lora_manager.create(name.strip())
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer la nouvelle LoRA dans le projet : {exc}\n"
                "La LoRA n'a pas été créée."
            )
            return

        if lora is None:
            # Mission 029: LoRAManager.create() now follows the Workspace's
            # principal Character (Mission 026/028), not a manual selection
            # the hidden multi-character UI no longer offers a way to make —
            # this can now only fire for the genuine edge case of a
            # Workspace with zero Character at all.
            if not self.workspace_manager.opened:
                QMessageBox.warning(
                    self,
                    "Aucun projet ouvert",
                    "Ouvrez ou créez un projet avant de créer une LoRA."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Aucun personnage",
                    "Ce projet ne possède aucun personnage — créez-en un depuis Characters avant de créer une LoRA."
                )

    def delete_lora(self):

        item = self.lora_list.currentItem()

        if item is None:
            return

        # Mission 078: the currently displayed metadata draft belongs to
        # this exact LoRA only when it is still the loaded one (it always
        # is here — this is the same list item currentItem() just
        # returned) — a single adapted dialog rather than a second,
        # separate confirmation, mirroring PromptsPage.delete_prompt()'s
        # intent without stacking two dialogs in a row.
        box = QMessageBox(self)
        box.setWindowTitle("Supprimer la LoRA ?")
        if self._metadata_dirty and item.data(Qt.UserRole) == self._loaded_lora_id:
            box.setText(
                f"Supprimer la LoRA « {item.text()} » ? Cette action est "
                "irréversible et les métadonnées non enregistrées de cette "
                "LoRA seront perdues."
            )
        else:
            box.setText(
                f"Supprimer la LoRA « {item.text()} » ? Cette action est irréversible."
            )
        delete_button = box.addButton("Supprimer", QMessageBox.AcceptRole)
        cancel_button = box.addButton("Annuler", QMessageBox.RejectRole)
        box.setDefaultButton(cancel_button)
        box.exec()

        if box.clickedButton() is not delete_button:
            return

        # Mission 068: delete() rolls back the Domain removal (and
        # active_lora_id) before re-raising on a save() failure — the
        # LoRA stays exactly where it was, so no refresh is needed here
        # beyond informing the user.
        try:
            result = self.lora_manager.delete(item.data(Qt.UserRole))
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer la suppression dans le projet : {exc}\n"
                "La LoRA n'a pas été supprimée."
            )
            return

        # Mission 075: a successful deletion can still leave its private
        # folder only partially cleaned up on disk (best-effort, never
        # rolled back) — a non-blocking warning, never presented as a
        # failure of the deletion itself, which already succeeded.
        if result.cleanup_failed:
            QMessageBox.warning(
                self,
                "Suppression partielle",
                "La LoRA a été supprimée du projet, mais certains fichiers "
                "associés n'ont pas pu être supprimés du disque (dossier "
                f"résiduel : {result.residual_path})."
            )

    def on_lora_selection_changed(self, current, previous):

        # Mission 063: "Supprimer" must always reflect whether there is
        # currently something to delete — set regardless of the early
        # return just below, unlike lora_manager.select() itself.
        self.delete_button.setEnabled(current is not None)

        if current is None:
            return

        # Mission 078: captured now, before any Manager call below can
        # reentrantly trigger update_loras() -> _refresh_lora_list() ->
        # lora_list.clear(), which deletes the underlying C++
        # QListWidgetItem `current` wraps (e.g. "Enregistrer" below calls
        # lora_manager.update(), which publishes WORKSPACE_SAVED
        # synchronously). Reading current.data() again afterward would
        # then raise. Same precedent as PromptsPage.
        target_lora_id = current.data(Qt.UserRole)

        if self._metadata_dirty:
            choice = self._confirm_discard_metadata_before_switch()

            if choice == QMessageBox.Cancel:
                # Mission 078: lora_manager.select() is never called —
                # active_lora_id stays untouched. Revert the widget's own
                # native selection (already changed by Qt before this
                # handler ran) back to `previous`, with signals blocked to
                # avoid recursively re-entering this same handler.
                self.lora_list.blockSignals(True)
                self.lora_list.setCurrentItem(previous)
                self.lora_list.blockSignals(False)
                self.delete_button.setEnabled(previous is not None)
                return

            if choice == QMessageBox.Save:
                previous_lora_id = self._loaded_lora_id
                try:
                    self.lora_manager.update(
                        previous_lora_id,
                        engine=self.engine_edit.text(),
                        architecture=self.architecture_edit.text(),
                        trigger_word=self.trigger_word_edit.text(),
                        version=self.version_edit.text(),
                    )
                except WorkspaceManagerError as exc:
                    QMessageBox.critical(
                        self,
                        "Erreur",
                        "Impossible d'enregistrer les métadonnées avant de "
                        f"changer de sélection : {exc}"
                    )
                    self.lora_list.blockSignals(True)
                    self.lora_list.setCurrentItem(previous)
                    self.lora_list.blockSignals(False)
                    self.delete_button.setEnabled(previous is not None)
                    return

            self._metadata_dirty = False

        self.lora_manager.select(target_lora_id)

    def _confirm_discard_metadata_before_switch(self):
        box = QMessageBox(self)
        box.setWindowTitle("Modifications non enregistrées")
        box.setText(
            "Les métadonnées de la LoRA actuelle contiennent des "
            "modifications non enregistrées. Que souhaitez-vous faire ?"
        )
        box.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        box.setButtonText(QMessageBox.Save, "Enregistrer")
        box.setButtonText(QMessageBox.Discard, "Ignorer les modifications")
        box.setButtonText(QMessageBox.Cancel, "Annuler")
        box.setDefaultButton(QMessageBox.Cancel)
        return box.exec()

    def confirm_context_change(self) -> bool:
        """
        Mission 078: same role as PromptsPage.confirm_context_change()
        (Mission 069) — called by MainWindow before a Workspace switch
        (new_project()/open_project()) that would otherwise let
        reset_for_context_change() silently discard an unsaved metadata
        draft once current_workspace is replaced, too late for a genuine
        Save or Cancel. Mission 079 reuses this same guard from
        closeEvent() before closing the whole application.
        """
        if not self._metadata_dirty:
            return True

        choice = self._confirm_discard_metadata_before_switch()

        if choice == QMessageBox.Cancel:
            return False

        if choice == QMessageBox.Save:
            active_lora_id = self._loaded_lora_id
            try:
                self.lora_manager.update(
                    active_lora_id,
                    engine=self.engine_edit.text(),
                    architecture=self.architecture_edit.text(),
                    trigger_word=self.trigger_word_edit.text(),
                    version=self.version_edit.text(),
                )
            except WorkspaceManagerError as exc:
                QMessageBox.critical(
                    self,
                    "Erreur",
                    "Impossible d'enregistrer les métadonnées avant de "
                    f"changer de projet : {exc}"
                )
                self._force_refresh_lora()
                return False

        self._metadata_dirty = False
        return True

    def rename_lora(self):

        active_lora_id = self.lora_manager.active_lora_id

        if active_lora_id is None:
            return

        # Mission 070: update_name() rolls back LoRA.name before
        # re-raising on a save() failure — update_loras() redraws
        # name_edit from that rolled-back Domain state, so no manual
        # widget restoration is needed beyond informing the user.
        try:
            self.lora_manager.update_name(active_lora_id, self.name_edit.text())
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer le renommage dans le projet : {exc}\n"
                "Le nom précédent a été restauré."
            )
            self._force_refresh_lora()

    def import_files(self):

        if self.lora_manager.active_lora_id is None:
            QMessageBox.warning(
                self,
                "Aucune LoRA sélectionnée",
                "Sélectionnez une LoRA avant d'importer des fichiers."
            )
            return

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Sélectionner des fichiers",
            "",
            "Fichiers LoRA (*.safetensors *.ckpt *.pt *.bin *.json);;Tous les fichiers (*)"
        )

        if not files:
            return

        # Mission 076: add_files() rolls back lora.files before
        # re-raising on a save() failure — WORKSPACE_SAVED is not
        # published on failure, so update_loras() must be called
        # explicitly to resync files_list on the restored Domain state.
        try:
            added = self.lora_manager.add_files(files)
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer l'import dans le projet : {exc}\n"
                "Aucun fichier n'a été importé."
            )
            self._force_refresh_lora()
            return

        duplicates = len(files) - added

        if added == 0:
            QMessageBox.information(
                self,
                "Import terminé",
                "Aucun nouveau fichier importé (déjà présents)."
            )
        elif duplicates > 0:
            QMessageBox.information(
                self,
                "Import terminé",
                f"{added} fichier(s) importé(s), {duplicates} déjà présent(s) ignoré(s)."
            )
        else:
            QMessageBox.information(
                self,
                "Import terminé",
                f"{added} fichier(s) importé(s)."
            )

    def choose_thumbnail(self):

        active_lora_id = self.lora_manager.active_lora_id

        if active_lora_id is None:
            QMessageBox.warning(
                self,
                "Aucune LoRA sélectionnée",
                "Sélectionnez une LoRA avant de choisir une miniature."
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir une miniature",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )

        if not file_path:
            return

        # Mission 067: set_thumbnail() now restores the previous
        # thumbnail and compensates any newly created copy before
        # re-raising on a save() failure — the LoRA keeps whatever
        # thumbnail it had before this call, exactly as a WorkspaceStorageError
        # already guaranteed for a failed copy.
        try:
            result = self.lora_manager.set_thumbnail(active_lora_id, file_path)
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer la miniature dans le projet : {exc}\n"
                "La miniature précédente, si elle existe, est conservée."
            )
            return

        if result is None:
            QMessageBox.warning(
                self,
                "Copie impossible",
                "La miniature n'a pas pu être copiée dans le projet. "
                "La miniature précédente, si elle existe, est conservée."
            )
            return

        # Mission 080: a successful thumbnail replacement can still leave
        # the now-superseded previous file only partially cleaned up on
        # disk (best-effort, never rolled back) — a non-blocking warning,
        # never presented as a failure of the thumbnail change itself,
        # which already succeeded. Same principle as delete_lora()'s own
        # residual-folder warning (Mission 075).
        if result.cleanup_failed:
            QMessageBox.warning(
                self,
                "Nettoyage partiel",
                "La nouvelle miniature a bien été enregistrée, mais "
                "l'ancien fichier n'a pas pu être supprimé du disque "
                f"(fichier résiduel : {result.residual_path})."
            )

    def save_metadata(self):

        active_lora_id = self.lora_manager.active_lora_id

        if active_lora_id is None:
            return

        try:
            self.lora_manager.update(
                active_lora_id,
                engine=self.engine_edit.text(),
                architecture=self.architecture_edit.text(),
                trigger_word=self.trigger_word_edit.text(),
                version=self.version_edit.text(),
            )
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer les métadonnées dans le projet : {exc}\n"
                "Les métadonnées précédentes ont été restaurées."
            )
            self._force_refresh_lora()
            return

        # Mission 078: the save intent is satisfied — nothing from the
        # UI's point of view remains unsaved, regardless of update()'s own
        # True/False return. No field resync needed: the 4 metadata
        # fields already display exactly what was just persisted.
        self._metadata_dirty = False

    def _update_metadata_buttons_state(self):

        has_active_lora = self.lora_manager.active_lora_id is not None

        self.choose_thumbnail_button.setEnabled(has_active_lora)
        self.save_metadata_button.setEnabled(has_active_lora)
        self.add_to_library_button.setEnabled(has_active_lora)

    def add_to_central_library(self):
        """
        Mission 088: copies the currently active Character-scoped LoRA
        into the Application-level central library posed by Mission
        087 — a one-way, independent copy, never an association back
        to this LoRA. No hash/deduplication: importing the same LoRA
        again later creates another independent central entry with its
        own physical copy, exactly the existing LoRALibraryManager
        contract.
        """

        active_lora_id = self.lora_manager.active_lora_id

        if active_lora_id is None:
            return

        if self._metadata_dirty:
            choice = self._confirm_discard_metadata_before_switch()

            if choice == QMessageBox.Cancel:
                return

            if choice == QMessageBox.Save:
                try:
                    self.lora_manager.update(
                        active_lora_id,
                        engine=self.engine_edit.text(),
                        architecture=self.architecture_edit.text(),
                        trigger_word=self.trigger_word_edit.text(),
                        version=self.version_edit.text(),
                    )
                except WorkspaceManagerError as exc:
                    QMessageBox.critical(
                        self,
                        "Erreur",
                        "Impossible d'enregistrer les métadonnées avant "
                        f"l'ajout à la bibliothèque centrale : {exc}\n"
                        "L'ajout à la bibliothèque centrale a été annulé."
                    )
                    self._force_refresh_lora()
                    return

                self._metadata_dirty = False
            else:
                # Discard: no selection change follows to trigger a
                # natural resync (unlike on_lora_selection_changed()) —
                # explicitly restore the fields from the persisted
                # Domain state, which also clears _metadata_dirty.
                self._force_refresh_lora()

        # Mission 070's rollback contract guarantees LoRAManager.update()
        # restores the exact previous value on failure (handled above,
        # which already returned) — active_lora is therefore guaranteed
        # non-None here, unchanged since active_lora_id was read above.
        lora = self.lora_manager.active_lora

        library_root = self.application_settings_manager.settings.lora_library_path

        try:
            self.lora_library_manager.import_lora(
                name=lora.name,
                file_paths=lora.files,
                library_root=library_root,
                thumbnail_path=lora.thumbnail,
                engine=lora.engine,
                architecture=lora.architecture,
                trigger_word=lora.trigger_word,
                version=lora.version,
            )
        except LoRALibraryError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'ajouter la LoRA à la bibliothèque centrale : {exc}"
            )
            return

        QMessageBox.information(
            self,
            "Ajout terminé",
            f"« {lora.name} » a été ajoutée à la bibliothèque centrale."
        )

    def remove_selected_files(self):

        paths = [item.text() for item in self.files_list.selectedItems()]

        if not paths:
            return

        # Mission 076: remove_files() rolls back lora.files before
        # re-raising on a save() failure — WORKSPACE_SAVED is not
        # published on failure, so update_loras() must be called
        # explicitly to resync files_list on the restored Domain state.
        try:
            self.lora_manager.remove_files(paths)
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer la suppression dans le projet : {exc}\n"
                "Aucun fichier n'a été retiré."
            )
            self._force_refresh_lora()

    def _update_files_button_state(self):

        has_active_lora = self.lora_manager.active_lora_id is not None

        self.remove_files_button.setEnabled(
            has_active_lora and bool(self.files_list.selectedItems())
        )

    def _load_thumbnail_preview(self, thumbnail_path):
        self._render_thumbnail_preview(self.thumbnail_label, thumbnail_path)

    def _render_thumbnail_preview(self, label, thumbnail_path):
        # Mission 089: extracted from the former _load_thumbnail_preview()
        # (now a thin wrapper around this, unchanged behavior for the
        # Personnage tab) so the central-library tab's own thumbnail
        # label can reuse the exact same rendering contract — verified
        # before reuse: the original method only ever mutated a single
        # hardcoded label, so it could not be called as-is for a second,
        # independent label without this parameterization.
        if not thumbnail_path:
            label.setText(NO_THUMBNAIL_MESSAGE)
            return

        pixmap = QPixmap(thumbnail_path)

        if pixmap.isNull():
            label.setText(UNAVAILABLE_MESSAGE)
            return

        scaled = pixmap.scaled(
            THUMBNAIL_PREVIEW_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        label.setPixmap(scaled)

    def _on_metadata_changed(self):
        # Mission 078: only ever connected to textChanged, so this never
        # fires during a programmatic load protected by
        # _load_metadata_fields()'s blockSignals() — genuine user typing
        # is the only way this can run.
        self._metadata_dirty = True

    def _refresh_lora_list(self):
        # Mission 078: extracted from the former single update_loras() —
        # rebuilds lora_list only, shared by update_loras()/
        # reset_for_context_change()/_force_refresh_lora(). Returns
        # (active_lora_id, active_lora_data) so callers never need a
        # second, separate lookup pass.
        loras = sorted(
            self.lora_manager.list_loras(),
            key=lambda lora: lora["name"].lower(),
        )
        active_lora_id = self.lora_manager.active_lora_id

        self.lora_list.blockSignals(True)
        self.lora_list.clear()

        active_lora_data = None

        for lora in loras:

            item = QListWidgetItem(
                f"{lora['name']} ({len(lora['files'])} fichier(s))"
            )
            item.setData(Qt.UserRole, lora["lora_id"])

            self.lora_list.addItem(item)

            if lora["lora_id"] == active_lora_id:
                self.lora_list.setCurrentItem(item)
                active_lora_data = lora

        self.lora_list.blockSignals(False)
        # Mission 063: blockSignals() above suppresses currentItemChanged,
        # so setCurrentItem()/clear() never reach on_lora_selection_changed()
        # during a rebuild — the button's state must be recomputed here.
        self.delete_button.setEnabled(self.lora_list.currentItem() is not None)

        return active_lora_id, active_lora_data

    def _load_non_metadata_details(self, active_lora_data, restore_selection=False):
        # Mission 078: files_list/name_edit/thumbnail have no draft of
        # their own (name_edit saves immediately on blur, Mission 052;
        # files_list/thumbnail are read-only displays) — always resynced
        # regardless of _metadata_dirty/_loaded_lora_id, unchanged from
        # their pre-existing behavior.
        #
        # Mission 082: files_list's own selectedItems() (identity =
        # item.text(), the file path itself — no Qt.UserRole is set on
        # this list) is preserved across a same-LoRA refresh only —
        # restore_selection is False whenever the caller cannot prove
        # this is still the same active LoRA as before (see update_loras()/
        # _force_refresh_lora() below), since LoRA.files can legitimately
        # reference the same external file from two different LoRAs.
        # currentItem() is deliberately never restored here — nothing on
        # files_list reads it (only itemSelectionChanged/selectedItems()
        # are wired, confirmed by audit), unlike ImagesPage/DatasetsPage.
        previously_selected_paths = set()
        if restore_selection:
            previously_selected_paths = {item.text() for item in self.files_list.selectedItems()}

        self.files_list.blockSignals(True)
        self.files_list.clear()

        if active_lora_data is None:
            self.name_edit.setText("")
            self._load_thumbnail_preview("")
        else:
            for file_path in active_lora_data["files"]:
                self.files_list.addItem(file_path)

            self.name_edit.setText(active_lora_data["name"])
            self._load_thumbnail_preview(active_lora_data["thumbnail"])

        if previously_selected_paths:
            for i in range(self.files_list.count()):
                item = self.files_list.item(i)
                if item.text() in previously_selected_paths:
                    item.setSelected(True)

        self.files_list.blockSignals(False)

    def _load_metadata_fields(self, active_lora_data):
        # Mission 078: unconditional — bypasses the metadata dirty-state
        # guard on purpose. Called whenever the active LoRA actually
        # changed (update_loras()/reset_for_context_change()) or by a
        # forced resync (_force_refresh_lora(), used by every failure-
        # rollback call site and by confirm_context_change()'s own
        # failure branch).
        fields = (
            self.engine_edit,
            self.architecture_edit,
            self.trigger_word_edit,
            self.version_edit,
        )

        for field in fields:
            field.blockSignals(True)

        if active_lora_data is None:
            self.engine_edit.setText("")
            self.architecture_edit.setText("")
            self.trigger_word_edit.setText("")
            self.version_edit.setText("")
        else:
            self.engine_edit.setText(active_lora_data["engine"])
            self.architecture_edit.setText(active_lora_data["architecture"])
            self.trigger_word_edit.setText(active_lora_data["trigger_word"])
            self.version_edit.setText(active_lora_data["version"])

        for field in fields:
            field.blockSignals(False)

        self._metadata_dirty = False

    def update_loras(self, _payload=None):
        # Mission 078: subscribed (see main_window.py) only to
        # WORKSPACE_SAVED/WORKSPACE_RENAMED, CHARACTER_CREATED and
        # LORA_CREATED — WORKSPACE_CREATED/OPENED/CLOSED and
        # CHARACTER_SELECTED/DELETED are handled exclusively by
        # reset_for_context_change() below, and a real LoRA switch is
        # handled by on_lora_selection_changed() before LORA_SELECTED is
        # even published — so this dirty-draft protection never depends
        # on subscriber ordering.
        active_lora_id, active_lora_data = self._refresh_lora_list()

        # Mission 082: computed here, before _loaded_lora_id is possibly
        # reassigned below — the exact same comparison the metadata
        # dirty-state guard already uses, reused to decide whether
        # files_list's selection may be restored (same active LoRA) or
        # must not be (a genuine switch to a different LoRA, e.g. via
        # LORA_SELECTED/LORA_CREATED/LORA_DELETED — all routed through
        # this same method).
        same_lora = active_lora_id is not None and active_lora_id == self._loaded_lora_id
        self._load_non_metadata_details(active_lora_data, restore_selection=same_lora)

        if active_lora_id != self._loaded_lora_id or not self._metadata_dirty:
            # Either the active LoRA genuinely changed (e.g. LORA_DELETED
            # cleared it, or LORA_SELECTED/LORA_CREATED made a different
            # one active) — the 4 metadata fields must reflect the new
            # LoRA, never the previous one's draft — or nothing is
            # actually dirty, in which case refreshing is harmless and
            # must still reflect a mutation applied directly through
            # LoRAManager.update() outside this Page's own
            # save_metadata() (e.g. by another code path or test).
            self._load_metadata_fields(active_lora_data)
            self._loaded_lora_id = active_lora_id
        # else: a real unsaved metadata draft on the still-active LoRA —
        # non-destructive refresh (e.g. WORKSPACE_SAVED fired by an
        # unrelated Dataset/Character/etc. mutation elsewhere) — the 4
        # metadata fields are left untouched.

        self._update_metadata_buttons_state()
        self._update_files_button_state()

    def reset_for_context_change(self, _payload=None):
        """
        Subscribed by MainWindow to WORKSPACE_CREATED/OPENED/CLOSED and
        CHARACTER_SELECTED/CHARACTER_DELETED — never to update_loras()'s
        own events. A naive active_lora_id vs _loaded_lora_id comparison
        would wrongly read None == None as "nothing changed" when
        switching between two Workspaces that both happen to leave no
        LoRA active — silently carrying a stray draft across a genuine
        Workspace/Character switch. This method is therefore the sole,
        unconditional Presentation path for these 5 events, mirroring
        PromptsPage.reset_for_context_change() (Mission 038).

        Mission 089: the central-library tab is Application-level and
        deliberately NOT touched here — it never reacts to any Workspace/
        Character event, only to LORA_LIBRARY_IMPORTED/DELETED (see
        update_central_library() below and its wiring in main_window.py).
        """
        self._force_refresh_lora()

    def _force_refresh_lora(self):
        # Mission 078: bypasses the metadata dirty-state gate entirely —
        # used by every failure-rollback call site (rename_lora/
        # import_files/choose_thumbnail/remove_selected_files/
        # save_metadata) and by confirm_context_change()'s failure branch,
        # all of which must always reflect the just-restored Domain state,
        # never a stale or rejected view. Also reused by
        # reset_for_context_change() above.
        active_lora_id, active_lora_data = self._refresh_lora_list()
        # Mission 082: restore_selection=False unconditionally — this is
        # always a genuine context reset (Workspace/Character switch) or
        # a just-restored-from-rollback resync, never a same-LoRA
        # unrelated refresh, mirroring the same "always reset, never
        # restore a draft" contract this method already has for the
        # metadata fields (see reset_for_context_change()'s own comment).
        self._load_non_metadata_details(active_lora_data, restore_selection=False)
        self._load_metadata_fields(active_lora_data)
        self._loaded_lora_id = active_lora_id
        self._update_metadata_buttons_state()
        self._update_files_button_state()

    def on_library_selection_changed(self, current, previous):
        # Mission 090: the central-library tab now carries a real edit
        # draft (name/engine/architecture/trigger_word/version), so
        # switching selection must guard it exactly like
        # on_lora_selection_changed() (Mission 078) guards the
        # Personnage tab's own metadata draft.

        if current is None:
            self.delete_from_library_button.setEnabled(False)
            self._loaded_library_lora_id = None
            self._load_library_details(None)
            return

        # Mission 090: captured now, before any Manager call below can
        # reentrantly trigger update_central_library() ->
        # library_list.clear(), which deletes the underlying C++
        # QListWidgetItem `current` wraps (a successful update() below
        # publishes LORA_LIBRARY_UPDATED synchronously) — same
        # reentrancy hazard already guarded against by
        # on_lora_selection_changed().
        target_lora_id = current.data(Qt.UserRole)

        if self._library_metadata_dirty:
            choice = self._confirm_discard_library_metadata_before_switch()

            if choice == QMessageBox.Cancel:
                self.library_list.blockSignals(True)
                self.library_list.setCurrentItem(previous)
                self.library_list.blockSignals(False)
                self.delete_from_library_button.setEnabled(previous is not None)
                return

            if choice == QMessageBox.Save:
                previous_lora_id = self._loaded_library_lora_id
                try:
                    self.lora_library_manager.update(
                        previous_lora_id,
                        name=self.library_name_edit.text(),
                        engine=self.library_engine_edit.text(),
                        architecture=self.library_architecture_edit.text(),
                        trigger_word=self.library_trigger_word_edit.text(),
                        version=self.library_version_edit.text(),
                    )
                except LoRALibraryError as exc:
                    QMessageBox.critical(
                        self,
                        "Erreur",
                        "Impossible d'enregistrer les modifications avant de "
                        f"changer de sélection : {exc}"
                    )
                    self.library_list.blockSignals(True)
                    self.library_list.setCurrentItem(previous)
                    self.library_list.blockSignals(False)
                    self.delete_from_library_button.setEnabled(previous is not None)
                    return

                # Mission 090: a successful update() has already
                # published LORA_LIBRARY_UPDATED synchronously, handled
                # reentrantly by update_central_library() — which
                # rebuilds library_list (destroying `current`/`previous`)
                # and preserves *this* (previous_lora_id's) row, since
                # _library_metadata_dirty is still True at that exact
                # moment. The target row must therefore be re-found by
                # identity rather than reused from `current`.
                self._library_metadata_dirty = False
                self._display_library_entry(target_lora_id)
                return

            self._library_metadata_dirty = False

        self.delete_from_library_button.setEnabled(True)
        self._loaded_library_lora_id = target_lora_id
        self._load_library_details(self.lora_library_manager.get(target_lora_id))

    def _display_library_entry(self, lora_id):
        # Mission 090: re-finds a row by identity rather than trusting a
        # previously captured QListWidgetItem, which
        # update_central_library()'s own reentrant rebuild may already
        # have destroyed by the time this runs (see
        # on_library_selection_changed()'s Save branch above).
        for index in range(self.library_list.count()):
            item = self.library_list.item(index)
            if item.data(Qt.UserRole) == lora_id:
                self.library_list.blockSignals(True)
                self.library_list.setCurrentItem(item, QItemSelectionModel.NoUpdate)
                self.library_list.blockSignals(False)
                break

        self._loaded_library_lora_id = lora_id
        self._load_library_details(self.lora_library_manager.get(lora_id))
        self.delete_from_library_button.setEnabled(True)

    def _confirm_discard_library_metadata_before_switch(self):
        box = QMessageBox(self)
        box.setWindowTitle("Modifications non enregistrées")
        box.setText(
            "Les métadonnées de l'entrée actuelle de la bibliothèque "
            "centrale contiennent des modifications non enregistrées. "
            "Que souhaitez-vous faire ?"
        )
        box.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        box.setButtonText(QMessageBox.Save, "Enregistrer")
        box.setButtonText(QMessageBox.Discard, "Ignorer les modifications")
        box.setButtonText(QMessageBox.Cancel, "Annuler")
        box.setDefaultButton(QMessageBox.Cancel)
        return box.exec()

    def confirm_library_context_change(self) -> bool:
        """
        Mission 090: mirrors LoRAPage.confirm_context_change() (Mission
        078), but is wired only into MainWindow.closeEvent() — the
        central-library tab never reacts to any Workspace/Character
        event (Mission 089 mandate: it stays Application-level), so
        New/Open/Rename Project genuinely destroy nothing here; only
        closing the whole application can silently discard this draft.
        """
        if not self._library_metadata_dirty:
            return True

        choice = self._confirm_discard_library_metadata_before_switch()

        if choice == QMessageBox.Cancel:
            return False

        if choice == QMessageBox.Save:
            lora_id = self._loaded_library_lora_id
            try:
                self.lora_library_manager.update(
                    lora_id,
                    name=self.library_name_edit.text(),
                    engine=self.library_engine_edit.text(),
                    architecture=self.library_architecture_edit.text(),
                    trigger_word=self.library_trigger_word_edit.text(),
                    version=self.library_version_edit.text(),
                )
            except LoRALibraryError as exc:
                QMessageBox.critical(
                    self,
                    "Erreur",
                    "Impossible d'enregistrer les modifications avant de "
                    f"fermer l'application : {exc}"
                )
                return False

        self._library_metadata_dirty = False
        return True

    def _on_library_metadata_changed(self):
        # Mission 090: only ever connected to textChanged, so this never
        # fires during a programmatic load protected by
        # _load_library_details()'s blockSignals() — genuine user typing
        # is the only way this can run. Mirrors _on_metadata_changed().
        self._library_metadata_dirty = True
        self._update_library_metadata_button_state()

    def _update_library_metadata_button_state(self):
        # Mission 090: deliberately stricter than
        # _update_metadata_buttons_state() (Personnage tab) — enabled
        # only while a real, unsaved change exists, per the architect's
        # explicit requirement for this tab.
        self.save_library_metadata_button.setEnabled(
            self._library_metadata_dirty and self.library_list.currentItem() is not None
        )

    def save_library_metadata(self):

        item = self.library_list.currentItem()

        if item is None:
            return

        lora_id = item.data(Qt.UserRole)

        try:
            self.lora_library_manager.update(
                lora_id,
                name=self.library_name_edit.text(),
                engine=self.library_engine_edit.text(),
                architecture=self.library_architecture_edit.text(),
                trigger_word=self.library_trigger_word_edit.text(),
                version=self.library_version_edit.text(),
            )
        except LoRALibraryError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                "Impossible d'enregistrer les modifications dans la "
                f"bibliothèque centrale : {exc}\n"
                "Les valeurs précédentes ont été restaurées."
            )
            self._load_library_details(self.lora_library_manager.get(lora_id))
            return

        # Mission 090: on success, LoRALibraryManager.update() has
        # already published LORA_LIBRARY_UPDATED synchronously, which
        # update_central_library() (subscribed in main_window.py) has
        # already handled — the list row now reflects any renamed name,
        # and the panel was deliberately left untouched (still dirty at
        # that exact moment, same entry) rather than reloaded, so no
        # manual refresh call is needed here, matching this codebase's
        # Event-Driven UI principle (save_metadata() above never calls
        # update_loras() itself either).
        self._library_metadata_dirty = False
        self._update_library_metadata_button_state()

    def _load_library_details(self, lora):
        fields = (
            self.library_name_edit,
            self.library_engine_edit,
            self.library_architecture_edit,
            self.library_trigger_word_edit,
            self.library_version_edit,
        )

        for field in fields:
            field.blockSignals(True)

        if lora is None:
            for field in fields:
                field.setText("")
            self._render_thumbnail_preview(self.library_thumbnail_label, "")
        else:
            self.library_name_edit.setText(lora.name)
            self.library_engine_edit.setText(lora.engine)
            self.library_architecture_edit.setText(lora.architecture)
            self.library_trigger_word_edit.setText(lora.trigger_word)
            self.library_version_edit.setText(lora.version)
            self._render_thumbnail_preview(self.library_thumbnail_label, lora.thumbnail)

        for field in fields:
            field.blockSignals(False)

        self._library_metadata_dirty = False
        self._update_library_metadata_button_state()

    def update_central_library(self, _payload=None):
        """
        Mission 089: subscribed (see main_window.py) only to
        LORA_LIBRARY_IMPORTED/LORA_LIBRARY_DELETED/LORA_LIBRARY_UPDATED
        (Mission 090) — always re-reads LoRALibraryManager.list_loras()
        in full, ignoring the event's own single-entry payload, matching
        this codebase's established convention (e.g. update_loras()
        above never trusts a per-item payload either). Never subscribed
        to any Workspace/Character event — the central library is
        Application-level and must never be reset/rebuilt by a project
        switch.

        Mission 090: the list itself is always fully rebuilt (a renamed
        entry's row must always reflect its new text), but the detail
        panel is only destructively reloaded when the currently
        displayed entry genuinely no longer exists or nothing is dirty
        — mirroring update_loras()'s identity+dirty gate (Mission 078).
        This also transparently covers this entry's own successful
        save: at the exact moment LORA_LIBRARY_UPDATED is published
        synchronously by update(), _library_metadata_dirty is still
        True (save_library_metadata()/on_library_selection_changed()
        only clear it after the call returns) and
        _loaded_library_lora_id still identifies the same entry — so
        the panel is correctly left untouched (already showing exactly
        what was just saved) while the list row is refreshed around it.
        If the displayed entry has genuinely disappeared (deleted by
        this same user, the only possible source of mutation today),
        the reconstruction remains fully destructive exactly as before:
        selection/panel/dirty flag/button all cleared.
        """
        loras = sorted(
            self.lora_library_manager.list_loras(),
            key=lambda lora: lora.name.lower(),
        )

        still_exists = any(lora.lora_id == self._loaded_library_lora_id for lora in loras)
        preserve_panel = self._library_metadata_dirty and still_exists

        self.library_list.blockSignals(True)
        self.library_list.clear()

        restored_item = None
        for lora in loras:
            item = QListWidgetItem(f"{lora.name} ({len(lora.files)} fichier(s))")
            item.setData(Qt.UserRole, lora.lora_id)
            self.library_list.addItem(item)
            if preserve_panel and lora.lora_id == self._loaded_library_lora_id:
                restored_item = item

        if restored_item is not None:
            self.library_list.setCurrentItem(restored_item, QItemSelectionModel.NoUpdate)

        self.library_list.blockSignals(False)

        if preserve_panel:
            self.delete_from_library_button.setEnabled(True)
            return

        self.delete_from_library_button.setEnabled(False)
        self._loaded_library_lora_id = None
        self._load_library_details(None)

    def delete_from_library(self):

        item = self.library_list.currentItem()

        if item is None:
            return

        lora_id = item.data(Qt.UserRole)

        # Mission 090: same adapted-wording principle as delete_lora()
        # (Mission 078) — a single dialog, never a second one stacked on
        # top, when the entry being deleted is also the one currently
        # holding an unsaved edit draft.
        box = QMessageBox(self)
        box.setWindowTitle("Supprimer de la bibliothèque centrale ?")
        if self._library_metadata_dirty and lora_id == self._loaded_library_lora_id:
            box.setText(
                f"Supprimer « {item.text()} » de la bibliothèque centrale ? "
                "Cette action est irréversible et les modifications non "
                "enregistrées de cette entrée seront perdues."
            )
        else:
            box.setText(
                f"Supprimer « {item.text()} » de la bibliothèque centrale ? "
                "Cette action est irréversible."
            )
        delete_button = box.addButton("Supprimer", QMessageBox.AcceptRole)
        cancel_button = box.addButton("Annuler", QMessageBox.RejectRole)
        box.setDefaultButton(cancel_button)
        box.exec()

        if box.clickedButton() is not delete_button:
            return

        # Mission 089: read live at the moment of the click, never
        # cached — same principle as add_to_central_library() (Mission
        # 088).
        library_root = self.application_settings_manager.settings.lora_library_path

        try:
            result = self.lora_library_manager.delete(lora_id, library_root)
        except LoRALibraryError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible de supprimer l'entrée de la bibliothèque centrale : {exc}"
            )
            return

        # Mission 089: on success, LoRALibraryManager.delete() has already
        # published LORA_LIBRARY_DELETED synchronously, which
        # update_central_library() (subscribed in main_window.py) has
        # already handled — no manual refresh call here, matching this
        # codebase's Event-Driven UI principle (delete_lora() above never
        # calls update_loras() itself either).
        if result.cleanup_failed:
            QMessageBox.warning(
                self,
                "Suppression partielle",
                "L'entrée a été supprimée de la bibliothèque centrale, mais "
                "certains fichiers associés n'ont pas pu être supprimés du "
                f"disque (dossier résiduel : {result.residual_path})."
            )

    def import_to_library_from_disk(self):
        """
        Mission 092: second, independent entry point into
        LoRALibraryManager.import_lora() — a direct import from disk,
        with no Character-scoped LoRA involved at all. Reuses
        import_lora() exactly as add_to_central_library() already does
        (same Manager call, same library_root source); only the origin
        of name/file_paths differs (dialogs here, an active
        Character-scoped LoRA object there). No thumbnail, no metadata
        at import time (engine/architecture/trigger_word/version stay
        at their "" defaults) — both are immediately completable via
        this same tab's Mission 090 edit form once the new entry is
        selected below.

        The dirty-state guard is evaluated first, before the file
        dialog is even opened: _display_library_entry() below selects
        the new entry via setCurrentItem() under blockSignals(), so it
        would never trigger on_library_selection_changed()'s own
        guard — importing without this explicit check first could
        otherwise silently discard an unsaved edit draft on whatever
        other entry is currently loaded.
        """

        if self._library_metadata_dirty:
            choice = self._confirm_discard_library_metadata_before_switch()

            if choice == QMessageBox.Cancel:
                return

            if choice == QMessageBox.Save:
                try:
                    self.lora_library_manager.update(
                        self._loaded_library_lora_id,
                        name=self.library_name_edit.text(),
                        engine=self.library_engine_edit.text(),
                        architecture=self.library_architecture_edit.text(),
                        trigger_word=self.library_trigger_word_edit.text(),
                        version=self.library_version_edit.text(),
                    )
                except LoRALibraryError as exc:
                    QMessageBox.critical(
                        self,
                        "Erreur",
                        "Impossible d'enregistrer les modifications avant "
                        f"l'import depuis le disque : {exc}\n"
                        "L'import a été annulé."
                    )
                    return

            self._library_metadata_dirty = False

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Sélectionner des fichiers",
            "",
            "Fichiers LoRA (*.safetensors *.ckpt *.pt *.bin *.json);;Tous les fichiers (*)"
        )

        if not files:
            return

        name, ok = QInputDialog.getText(self, "Importer dans la bibliothèque centrale", "Nom :")

        if not ok or not name.strip():
            return

        library_root = self.application_settings_manager.settings.lora_library_path

        try:
            lora = self.lora_library_manager.import_lora(
                name=name.strip(),
                file_paths=files,
                library_root=library_root,
            )
        except LoRALibraryError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'importer la LoRA dans la bibliothèque centrale : {exc}"
            )
            return

        self._display_library_entry(lora.lora_id)
