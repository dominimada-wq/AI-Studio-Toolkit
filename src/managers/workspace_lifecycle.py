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
    principal Character. If create_without_publishing() itself fails
    (create_directories() or the very first save()), or if
    character_manager.ensure_default_character() fails afterwards (the
    second save()), the same rollback applies: the just-materialized
    Workspace folder is removed (best effort) and current_workspace is
    restored to whatever it was before this call, so the caller never
    sees a Workspace half-created either way.

    Mission 153: this rollback used to cover only the second failure
    point (ensure_default_character()) — create_without_publishing()
    was called outside the try/except below, so a failure inside it
    (create_directories() or the first save()) left a partially
    materialized folder (root, and possibly some of its subfolders)
    on disk with no cleanup attempt at all. Both failure points now go
    through the exact same rollback, since by the time either can
    fail, current_workspace has not yet been reassigned to the new
    Workspace in a way this function cannot already account for:
    create_without_publishing() only mutates current_workspace after
    its own internal try/except has fully succeeded, so restoring it
    to previous_workspace below is a correct no-op for the first
    failure point (nothing to actually undo yet) and a real
    restoration for the second (current_workspace really did change).

    Safety precondition, deliberately not re-validated here: this
    unconditional WorkspaceStorage.delete_folder(folder) is only safe
    because `folder` is guaranteed to not have existed before this
    call — enforced by NewProjectDialog (target_path is rejected
    up front, and re-checked again at the exact moment "Create" is
    clicked, if it already exists) and, as of this mission, by
    create_workspace_with_default_character() still having exactly one
    production caller (MainWindow.new_project()). A future caller that
    reuses this function against a folder that might already contain
    unrelated content would make this cleanup destructive — this
    function does not defend against that itself.
    """

    previous_workspace = workspace_manager.current_workspace

    try:
        workspace = workspace_manager.create_without_publishing(folder)
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
