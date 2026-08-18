from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from src.ui.dialogs.new_project_dialog import validate_project_name

SAME_NAME_MESSAGE = "C'est déjà le nom actuel du projet."
TARGET_EXISTS_MESSAGE = "Ce dossier existe déjà — choisissez un autre nom."


class RenameProjectDialog(QDialog):
    """
    Mission 027: renames the current project's folder from within the
    application (Fichier -> Renommer le projet...). Unlike
    NewProjectDialog, the parent directory is fixed (the project's
    current parent folder) — only the name itself is editable. Reuses
    validate_project_name() (new_project_dialog.py) rather than
    duplicating its rules. Never touches the filesystem itself —
    WorkspaceManager.rename() (called by MainWindow after this dialog is
    accepted) is the only place the actual rename happens.
    """

    def __init__(self, current_root, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Renommer le projet")

        self._current_root = Path(current_root)
        self.new_name: Optional[str] = None

        layout = QVBoxLayout(self)

        self.name_line_edit = QLineEdit()
        self.name_line_edit.setText(self._current_root.name)
        self.name_line_edit.textChanged.connect(self._revalidate)
        layout.addWidget(self.name_line_edit)

        self.preview_label = QLabel()
        layout.addWidget(self.preview_label)

        self.button_box = QDialogButtonBox()
        self.rename_button = self.button_box.addButton(
            "Renommer", QDialogButtonBox.AcceptRole
        )
        self.button_box.addButton("Annuler", QDialogButtonBox.RejectRole)
        self.button_box.accepted.connect(self._on_accept_clicked)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self._revalidate()

    def _compute_new_name(self):
        """
        Returns (new_name, error_message). new_name is a ready-to-use
        string only when error_message is None. Read-only: only
        Path.exists() inspection, never a filesystem mutation.
        """
        name = self.name_line_edit.text()

        error = validate_project_name(name)
        if error is not None:
            return None, error

        if name == self._current_root.name:
            return None, SAME_NAME_MESSAGE

        target_path = self._current_root.parent / name
        if target_path.exists():
            return None, TARGET_EXISTS_MESSAGE

        return name, None

    def _revalidate(self):
        new_name, error = self._compute_new_name()

        if error is None:
            self.preview_label.setText(str(self._current_root.parent / new_name))
            self.rename_button.setEnabled(True)
        else:
            self.preview_label.setText(error)
            self.rename_button.setEnabled(False)

    def _on_accept_clicked(self):
        # Re-validated at the exact moment of acceptance, not just
        # trusting the last _revalidate() pass — same principle as
        # NewProjectDialog._on_accept_clicked().
        new_name, error = self._compute_new_name()

        if error is not None:
            self.preview_label.setText(error)
            self.rename_button.setEnabled(False)
            return

        self.new_name = new_name
        self.accept()
