import uuid
from pathlib import Path
from typing import List, NamedTuple, Optional

from src.core.event_bus import EventBus
from src.domain.lora import LoRA
from src.infrastructure.storage.lora_library_storage import (
    LoRALibraryStorage,
    LoRALibraryStorageError,
)
from src.infrastructure.storage.workspace_storage import (
    WorkspaceStorage,
    WorkspaceStorageError,
)

LORA_LIBRARY_IMPORTED = "lora_library.imported"
LORA_LIBRARY_DELETED = "lora_library.deleted"


class LoRALibraryError(Exception):
    """
    Raised on any real failure of a LoRALibraryManager mutation — a
    partial/failed file copy, or a registry persistence failure.
    Normalizes LoRALibraryStorageError/WorkspaceStorageError into a
    single Manager-level exception type, the same pattern
    WorkspaceManagerError already uses to wrap WorkspaceStorageError,
    and GenerationError uses to wrap ComfyUIEngineError/OSError.
    """


class LoRALibraryDeletionResult(NamedTuple):
    """
    delete()'s return type — same shape and rationale as
    LoRADeletionResult/DatasetDeletionResult (Mission 075): the
    physical cleanup of the now-trashed folder is a distinct,
    best-effort step that can fail independently of (and after) the
    functional deletion already succeeding. Duplicated rather than
    shared, per this codebase's existing convention for these small
    per-Manager result types.
    """

    deleted: bool
    cleanup_failed: bool
    residual_path: Optional[str]


class LoRALibraryManager:
    """
    Mission 087: foundation of the central LoRA library — an
    Application-level registry, entirely independent of any Workspace
    or Character. Unlike LoRAManager (Character-scoped, LoRA.files are
    never-copied external references), every LoRA this Manager holds
    is fully owned by the library: LoRA.files/LoRA.thumbnail are always
    copies physically stored under <library_root>/<lora_id>/, never a
    reference to the original external source. Persistence is
    delegated to LoRALibraryStorage — a separate file from
    project.json and from application_settings.json.

    Deliberately holds no library_root/path state of its own —
    import_lora()/delete() both take it as an explicit parameter on
    every call, resolved by the caller from
    ApplicationSettings.lora_library_path at the time of the call. This
    avoids any dependency on ApplicationSettingsManager (which itself
    depends on this Manager, to enforce the path-change lock below —
    a real dependency in the other direction would be circular), and
    avoids a "no hot reload" staleness trap: a path changed via
    Settings while the registry is empty takes effect on the very next
    import, no restart needed.

    No select()/active_lora_id — no UI consumes this registry yet in
    Mission 087, so a "current selection" concept would have no
    consumer.
    """

    def __init__(
        self,
        storage_directory: Optional[Path] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self._directory = storage_directory or LoRALibraryStorage.default_directory()
        self._event_bus = event_bus

        raw = LoRALibraryStorage.load(self._directory)
        self._loras: List[LoRA] = (
            [LoRA.from_dict(entry) for entry in raw.get("loras") or [] if isinstance(entry, dict)]
            if raw is not None
            else []
        )

    def list_loras(self) -> List[LoRA]:
        return list(self._loras)

    def get(self, lora_id: str) -> Optional[LoRA]:
        return self._find(lora_id)

    def import_lora(
        self,
        name: str,
        file_paths: List[str],
        library_root,
        thumbnail_path: Optional[str] = None,
    ) -> LoRA:
        """
        Copies every path in file_paths (and thumbnail_path, if given)
        into <library_root>/<lora_id>/ — a brand new uuid4, never
        reused. Each copy uses WorkspaceStorage.copy_into_workspace()
        with workspace_root=destination_folder (deliberately the same
        value as destination_folder, never the wider library_root):
        this scopes the "source already inside my own territory, skip
        the copy" passthrough check to this entry's own folder only.
        Passing the wider library_root there instead would let a
        source already living inside a DIFFERENT entry's own folder be
        referenced without a copy — silently breaking the one-entry-
        owns-one-folder contract this whole library depends on (that
        entry's own future deletion would then destroy a file this one
        still depends on).

        Two imports of the same source file produce two independent
        LoRA entries with two independent physical copies — no
        hash-based deduplication in Mission 087.

        Never returns None — LoRALibraryManager has no
        Workspace/Character precondition (unlike e.g. ModelManager.
        create(), which legitimately returns None only when no
        Workspace is open) that would justify an Optional return here.
        Any real failure raises LoRALibraryError.

        If any copy fails partway through a multi-file import, the
        destination folder (including any files already copied before
        the failure) is removed on a best-effort basis before
        LoRALibraryError is raised — nothing is ever left half-copied,
        and no Domain entry is ever created for a partial import.
        """

        library_root = Path(library_root)
        lora_id = str(uuid.uuid4())
        destination_folder = library_root / lora_id

        try:
            owned_files = [
                str(
                    WorkspaceStorage.copy_into_workspace(
                        Path(source_path), destination_folder, workspace_root=destination_folder
                    )
                )
                for source_path in file_paths
            ]

            owned_thumbnail = ""
            if thumbnail_path:
                owned_thumbnail = str(
                    WorkspaceStorage.copy_into_workspace(
                        Path(thumbnail_path), destination_folder, workspace_root=destination_folder
                    )
                )
        except WorkspaceStorageError as exc:
            if not self._best_effort_delete_folder(destination_folder):
                raise LoRALibraryError(
                    f"Could not import LoRA files: {exc} Additionally, the partially "
                    f"copied files could not be cleaned up and remain orphaned on "
                    f"disk at {destination_folder}."
                ) from exc
            raise LoRALibraryError(f"Could not import LoRA files: {exc}") from exc

        lora = LoRA(
            lora_id=lora_id,
            name=name,
            files=owned_files,
            thumbnail=owned_thumbnail,
        )

        self._loras.append(lora)

        try:
            self._save()
        except LoRALibraryStorageError as exc:
            self._loras.remove(lora)
            if not self._best_effort_delete_folder(destination_folder):
                raise LoRALibraryError(
                    f"{exc} Additionally, the newly copied LoRA files could not be "
                    f"cleaned up and remain orphaned on disk at {destination_folder}."
                ) from exc
            raise LoRALibraryError(str(exc)) from exc

        self._publish(LORA_LIBRARY_IMPORTED, lora)

        return lora

    def delete(self, lora_id: str, library_root) -> LoRALibraryDeletionResult:
        """
        Mirrors LoRAManager.delete()'s transactional contract (Missions
        066/067/075) almost exactly: the entry's own folder is moved
        atomically into a lazily-created <library_root>/.trash/
        staging area before any Domain mutation — abort before
        anything is touched if that move fails; on a persistence
        failure the Domain rollback (reinsert at the original index)
        always runs first (cannot itself fail), then the folder is
        independently moved back, with an enriched LoRALibraryError if
        that reverse move also fails; on persistence success the
        staged folder is permanently deleted on a best-effort basis,
        never rolling back an already-persisted deletion on failure —
        only reported via the returned LoRALibraryDeletionResult.

        Only ever touches <library_root>/<lora_id>/ — an entry's own
        folder, populated exclusively by import_lora()'s copies. Never
        touches an external source file (import_lora() never
        references one directly in the first place).
        """

        library_root = Path(library_root)

        lora = self._find(lora_id)

        if lora is None:
            return LoRALibraryDeletionResult(deleted=False, cleanup_failed=False, residual_path=None)

        source_folder = library_root / lora_id
        trash_folder = None

        if source_folder.exists():
            trash_folder = library_root / ".trash" / f"lora_{lora_id}_{uuid.uuid4().hex}"
            try:
                WorkspaceStorage.rename_folder(source_folder, trash_folder)
            except WorkspaceStorageError as exc:
                raise LoRALibraryError(str(exc)) from exc

        index = self._loras.index(lora)
        self._loras.remove(lora)

        try:
            self._save()
        except LoRALibraryStorageError as exc:
            self._loras.insert(index, lora)

            if trash_folder is not None:
                try:
                    WorkspaceStorage.rename_folder(trash_folder, source_folder)
                except WorkspaceStorageError as rollback_exc:
                    raise LoRALibraryError(
                        f"{exc} The LoRA itself has been restored in the "
                        f"library and is safe. However, its folder could not "
                        f"be moved back from its temporary location and now "
                        f"remains at {trash_folder} instead of {source_folder} "
                        f"({rollback_exc}). Manual recovery required: move "
                        f"{trash_folder} back to {source_folder} yourself "
                        f"once the underlying issue is resolved."
                    ) from rollback_exc
            raise LoRALibraryError(str(exc)) from exc

        cleanup_failed = False
        residual_path = None

        if trash_folder is not None and not self._best_effort_delete_folder(trash_folder):
            cleanup_failed = True
            residual_path = str(trash_folder)

        self._publish(LORA_LIBRARY_DELETED, lora)

        return LoRALibraryDeletionResult(
            deleted=True, cleanup_failed=cleanup_failed, residual_path=residual_path
        )

    def _find(self, lora_id: str) -> Optional[LoRA]:
        for lora in self._loras:
            if lora.lora_id == lora_id:
                return lora
        return None

    def _save(self) -> None:
        LoRALibraryStorage.save(self._directory, {"loras": [lora.to_dict() for lora in self._loras]})

    @staticmethod
    def _best_effort_delete_folder(folder: Path) -> bool:
        try:
            WorkspaceStorage.delete_folder(folder)
            return True
        except WorkspaceStorageError:
            return False

    def _publish(self, event_name: str, lora: LoRA) -> None:

        if self._event_bus is None:
            return

        self._event_bus.publish(event_name, lora.to_dict())
