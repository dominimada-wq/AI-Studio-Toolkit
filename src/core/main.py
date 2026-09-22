"""
AI Studio Toolkit
Main entry point
"""

from PySide6.QtWidgets import QApplication, QMessageBox

from src.infrastructure.storage.application_settings_storage import (
    ApplicationSettingsStorageError,
)
from src.infrastructure.storage.lora_library_storage import LoRALibraryStorageError
from src.ui.main_window import MainWindow


def main():
    app = QApplication([])

    # Mission 144: ApplicationSettingsManager/LoRALibraryManager load
    # their machine-local file during MainWindow's own construction
    # (src/ui/main_window.py), with no try/except of their own — a
    # present-but-corrupt file now raises instead of silently falling
    # back to defaults, and that exception is deliberately left to
    # propagate all the way up to here rather than being caught inside
    # MainWindow itself. This is the single interception point for
    # either failure: one fatal message, MainWindow is never shown, the
    # event loop is never started. Neither file is ever touched here —
    # the existing file on disk is left exactly as it was found.
    try:
        window = MainWindow()
    except ApplicationSettingsStorageError as exc:
        QMessageBox.critical(
            None,
            "Erreur fatale au démarrage",
            "Les paramètres de l'application (Application Settings) sont "
            "illisibles ou corrompus.\n\n"
            f"{exc}\n\n"
            "Le fichier existant n'a pas été modifié ni remplacé, pour "
            "éviter d'écraser son contenu. Corrigez ou déplacez ce "
            "fichier avant de relancer l'application.",
        )
        return
    except LoRALibraryStorageError as exc:
        QMessageBox.critical(
            None,
            "Erreur fatale au démarrage",
            "Le registre de la bibliothèque LoRA centrale (LoRA Library) "
            "est illisible ou corrompu.\n\n"
            f"{exc}\n\n"
            "Le fichier existant n'a pas été modifié ni remplacé, pour "
            "éviter d'écraser son contenu. Corrigez ou déplacez ce "
            "fichier avant de relancer l'application.",
        )
        return

    window.show()

    app.exec()


if __name__ == "__main__":
    main()
