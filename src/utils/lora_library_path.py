from pathlib import Path


class LoRALibraryPathError(Exception):
    """
    Mission 104: raised by resolve_lora_library_root() when
    ApplicationSettings.lora_library_path is empty or blank -- the one
    value that otherwise silently resolves relative to the process cwd
    (Path("") / lora_id) instead of raising, letting import_lora()/
    set_thumbnail() "succeed" while writing outside any location the
    user actually configured.
    """


def resolve_lora_library_root(lora_library_path: str) -> Path:
    """
    Qt-free, side-effect-free precondition check shared by every UI
    call site that reaches LoRALibraryManager.import_lora()/
    set_thumbnail() with ApplicationSettings.lora_library_path.

    Only rejects "" and any value whose .strip() is empty. Never
    creates a directory, never checks existence, type (file vs
    directory), or writability -- those remain exactly where they are
    already correctly handled today (WorkspaceStorage.
    copy_into_workspace(), reached via LoRALibraryManager). A
    syntactically valid but not-yet-existing path is deliberately
    accepted unchanged (mkdir(parents=True) bootstraps it later) --
    this is not a general path-validation helper, only a guard against
    the one value that would otherwise never raise at all.
    """
    if not lora_library_path or not lora_library_path.strip():
        raise LoRALibraryPathError(
            "La Bibliothèque LoRA centrale n'est pas configurée (chemin vide). "
            "Renseignez un dossier dans Réglages avant d'importer un LoRA."
        )

    return Path(lora_library_path)
