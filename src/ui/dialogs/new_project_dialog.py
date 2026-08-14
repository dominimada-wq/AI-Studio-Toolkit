from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

RESERVED_WINDOWS_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

FORBIDDEN_CHARACTERS = '<>:"|?*'

NO_PARENT_MESSAGE = "Choisissez un dossier parent."
EMPTY_NAME_MESSAGE = "Le nom du projet ne peut pas être vide."
DOT_NAME_MESSAGE = "Le nom \".\" ou \"..\" n'est pas autorisé."
PATH_SEPARATOR_MESSAGE = "Le nom ne peut pas contenir de séparateur de chemin (/ ou \\)."
FORBIDDEN_CHARACTER_MESSAGE = (
    f"Le nom ne peut pas contenir l'un des caractères suivants : {FORBIDDEN_CHARACTERS}"
)
TRAILING_CHARACTER_MESSAGE = "Le nom ne peut pas se terminer par un espace ou un point."
RESERVED_NAME_MESSAGE = "Ce nom est réservé par Windows et ne peut pas être utilisé."
TARGET_EXISTS_MESSAGE = "Ce dossier existe déjà — choisissez un autre nom."


def validate_project_name(name: str) -> Optional[str]:
    """
    Presentation-layer-only validation (no Domain/Manager rule).
    Returns None if name is valid, otherwise a user-facing error
    message. Operates on the raw string as typed — never stripped
    before the trailing-space/trailing-dot check, so a name actually
    typed with a trailing space or dot is caught, not silently
    trimmed away.
    """
    if name.strip() == "":
        return EMPTY_NAME_MESSAGE

    if name in (".", ".."):
        return DOT_NAME_MESSAGE

    if "/" in name or "\\" in name:
        return PATH_SEPARATOR_MESSAGE

    if any(character in name for character in FORBIDDEN_CHARACTERS):
        return FORBIDDEN_CHARACTER_MESSAGE

    if name != name.rstrip(" ."):
        return TRAILING_CHARACTER_MESSAGE

    base_name = name.split(".", 1)[0].upper()
    if base_name in RESERVED_WINDOWS_NAMES:
        return RESERVED_NAME_MESSAGE

    return None


class NewProjectDialog(QDialog):
    """
    Mission 016: builds and validates a target_path (parent directory
    + project name) for a new project — it never creates anything on
    disk itself. Physical folder creation stays exclusively
    WorkspaceManager.create()'s responsibility (via
    WorkspaceStorage.create_directories()), called by MainWindow only
    after this dialog has been accepted. Structurally the same
    passivity principle as Mission 015's ImagePreviewDialog: no
    Domain/Manager/WorkspaceManager reference is ever held here.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Nouveau projet")

        self._parent_directory = ""
        self.target_path: Optional[Path] = None

        layout = QVBoxLayout(self)

        parent_row = QHBoxLayout()
        self.parent_line_edit = QLineEdit()
        self.parent_line_edit.setReadOnly(True)
        self.browse_button = QPushButton("Parcourir...")
        self.browse_button.clicked.connect(self._on_browse_clicked)
        parent_row.addWidget(self.parent_line_edit)
        parent_row.addWidget(self.browse_button)
        layout.addLayout(parent_row)

        self.name_line_edit = QLineEdit()
        self.name_line_edit.setPlaceholderText("Nom du projet")
        self.name_line_edit.textChanged.connect(self._revalidate)
        layout.addWidget(self.name_line_edit)

        self.preview_label = QLabel()
        layout.addWidget(self.preview_label)

        self.button_box = QDialogButtonBox()
        self.create_button = self.button_box.addButton("Créer", QDialogButtonBox.AcceptRole)
        self.button_box.addButton("Annuler", QDialogButtonBox.RejectRole)
        self.button_box.accepted.connect(self._on_accept_clicked)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self._revalidate()

    def _on_browse_clicked(self):
        folder = QFileDialog.getExistingDirectory(self, "Choisir le dossier parent")
        if not folder:
            return
        self._parent_directory = folder
        self.parent_line_edit.setText(folder)
        self._revalidate()

    def _compute_target_path(self):
        """
        Returns (target_path, error_message). target_path is a ready-
        to-create Path only when error_message is None; otherwise
        target_path is None and error_message explains why (shown in
        preview_label). Read-only: only Path.is_dir()/Path.exists()
        inspection, never a filesystem mutation.
        """
        if not self._parent_directory or not Path(self._parent_directory).is_dir():
            return None, NO_PARENT_MESSAGE

        name = self.name_line_edit.text()
        error = validate_project_name(name)
        if error is not None:
            return None, error

        target_path = Path(self._parent_directory) / name

        if target_path.exists():
            return None, TARGET_EXISTS_MESSAGE

        return target_path, None

    def _revalidate(self):
        target_path, error = self._compute_target_path()

        if error is None:
            self.preview_label.setText(str(target_path))
            self.create_button.setEnabled(True)
        else:
            self.preview_label.setText(error)
            self.create_button.setEnabled(False)

    def _on_accept_clicked(self):
        # Re-validated at the exact moment of acceptance, not just
        # trusting the last _revalidate() pass — the target could have
        # appeared on disk between the last keystroke/browse and this
        # click. If so, the dialog must stay open, "Créer" disabled,
        # the collision message shown, and WorkspaceManager.create()
        # must never be reached (self.accept() is not called).
        target_path, error = self._compute_target_path()

        if error is not None:
            self.preview_label.setText(error)
            self.create_button.setEnabled(False)
            return

        self.target_path = target_path
        self.accept()
