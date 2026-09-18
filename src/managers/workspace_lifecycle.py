from src.infrastructure.storage.workspace_storage import (
    WorkspaceStorage,
    WorkspaceStorageError,
)
from src.managers.character_manager import CharacterManager
from src.managers.workspace_manager import WorkspaceManager, WorkspaceManagerError


def create_workspace_with_default_character(
    workspace_manager: WorkspaceManager,
    character_manager: CharacterManager,
    folder,
):
    """
    Mission 137: the product-level "create a new Workspace" operation —
    the only one that guarantees the "a created Workspace always has a
    usable principal Character" invariant (Mission 026/036).

    WorkspaceManager.create() alone cannot guarantee this without
    depending on CharacterManager, which would be circular (CharacterManager
    already depends on WorkspaceManager, and neither can be constructed
    before the other). This function sits above both instead, importing
    each without either importing it back.

    WORKSPACE_CREATED is deliberately published only after the
    Character has been created and selected — never before, and never
    for a Workspace that ends up rolled back — so no observer can ever
    see a Workspace "created" that either doesn't exist or has no
    principal Character. If character_manager.ensure_default_character()
    fails, the just-materialized Workspace folder is removed (best
    effort) and current_workspace is restored to whatever it was before
    this call, so the caller never sees a Workspace half-created.
    """

    previous_workspace = workspace_manager.current_workspace

    workspace = workspace_manager.create_without_publishing(folder)

    try:
        character_manager.ensure_default_character()
    except WorkspaceManagerError as exc:
        workspace_manager.current_workspace = previous_workspace
        try:
            WorkspaceStorage.delete_folder(folder)
        except WorkspaceStorageError:
            # Mission 134/LoRALibraryManager.import_lora() idiom: the
            # cleanup failure is reported alongside the original cause,
            # never in place of it — from exc keeps the primary failure
            # as the chained cause, not the cleanup's own exception.
            raise WorkspaceManagerError(
                f"{exc} Additionally, the incomplete project folder could not be "
                f"cleaned up and remains on disk at {folder}. Manual recovery "
                f"required: delete {folder} yourself once the underlying issue is "
                f"resolved."
            ) from exc
        raise WorkspaceManagerError(str(exc)) from exc

    workspace_manager.publish_created()

    return workspace
