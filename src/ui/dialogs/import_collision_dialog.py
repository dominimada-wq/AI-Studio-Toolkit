from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


class ImportCollisionDialog(QDialog):
    """
    Mission 028 (second smoke test): shown once per import operation,
    never once per colliding file — WorkspaceManager/DatasetManager.
    preview_collisions() finds every source that would otherwise be
    silently renamed on import (e.g. "photo.jpg" -> "photo_1.jpg"), and
    this dialog lets the user decide, for each one, in a single screen:
    keep importing under a new name (pre-filled with the same
    collision-free suggestion add_images() would have picked
    automatically, editable) or skip it entirely (reported as
    "skipped", never as a failure). Accepting with an empty/duplicate
    new name for a row that isn't skipped is refused (OK stays
    disabled) — same live-validation principle as RenameProjectDialog.
    Never touches the filesystem itself; the actual copy/rename still
    goes exclusively through WorkspaceStorage.copy_into_workspace()
    once the caller (ImagesPage/DatasetsPage) applies these decisions.
    """

    def __init__(self, collisions, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Des images portent déjà ce nom")

        self._rows = []

        layout = QVBoxLayout(self)

        info = QLabel(
            "Une image portant déjà ce nom existe dans le Workspace. "
            "Choisissez un nouveau nom pour chaque import concerné, "
            "ou cochez « Ignorer » pour ne pas l'importer."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()

        for collision in collisions:
            name_edit = QLineEdit(collision.suggested_name)
            skip_checkbox = QCheckBox("Ignorer cet import")
            skip_checkbox.toggled.connect(name_edit.setDisabled)
            skip_checkbox.toggled.connect(self._revalidate)
            name_edit.textChanged.connect(self._revalidate)

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(name_edit)
            row_layout.addWidget(skip_checkbox)

            form.addRow(f"{Path(collision.source).name} :", row_widget)
            self._rows.append((collision.source, name_edit, skip_checkbox))

        layout.addLayout(form)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self._revalidate()

    def _revalidate(self):
        # OK stays disabled while any row that isn't skipped has an
        # empty proposed name — mirrors RenameProjectDialog's live
        # validation. Cross-row duplicate names are not rejected here:
        # a real name clash at copy time is still caught, never
        # silently overwritten, by WorkspaceStorage.copy_into_workspace()
        # itself (raises WorkspaceStorageError, reported as `failed`) —
        # the minimal UX asked for does not require anticipating this
        # rare case in the dialog itself.
        valid = all(
            skip_checkbox.isChecked() or name_edit.text().strip()
            for _source, name_edit, skip_checkbox in self._rows
        )
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(valid)

    def decisions(self) -> dict:
        """
        Returns {source_path: chosen_name} for every collision the
        user chose to rename, and {source_path: None} for every one
        chosen to skip. Only meaningful after exec() == QDialog.Accepted.
        """
        result = {}
        for source, name_edit, skip_checkbox in self._rows:
            result[source] = None if skip_checkbox.isChecked() else name_edit.text().strip()
        return result
