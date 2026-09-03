import os
import re
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
LORA_LIBRARY_UPDATED = "lora_library.updated"

# Mission 095: fixed, non-configurable — the Toolkit only ever manages
# aliases under this one subfolder of whatever ComfyUI loras root the
# architect points comfyui_lora_expose_path at, never at that root's
# own top level (see MISSION_095.md §3.3 for why a subfolder was
# chosen over a flat placement).
_COMFYUI_EXPOSE_SUBFOLDER_NAME = "AIStudioToolkit"

_SLUG_MAX_LENGTH = 80
_SLUG_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


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


class LoRALibraryThumbnailResult(NamedTuple):
    """
    Mission 093: set_thumbnail()'s return type on success — same
    principle as LoRAThumbnailResult (LoRAManager, Mission 080) and
    LoRALibraryDeletionResult above: the physical cleanup of the
    now-superseded previous thumbnail is a distinct, best-effort step
    that can fail independently of (and after) the functional mutation
    already succeeding. Duplicated rather than shared, per this
    codebase's existing convention for these small per-Manager result
    types. The unknown-lora case still returns a bare None (unchanged
    contract, see set_thumbnail()) rather than this NamedTuple, since
    nothing happened that a cleanup outcome could describe.
    """

    thumbnail: str
    cleanup_failed: bool
    residual_path: Optional[str]


class LoRAComfyUIExposureResult(NamedTuple):
    """
    Mission 095: expose_to_comfyui()'s return type on success — same
    shape and rationale as LoRALibraryDeletionResult/
    LoRALibraryThumbnailResult above: cleaning up a now-stale alias
    (after LoRA.name changed since the last exposure, see
    expose_to_comfyui()'s docstring) is a distinct, best-effort step
    that can fail independently of (and after) the new alias having
    already been created successfully.
    """

    alias_name: str
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
        engine: str = "",
        architecture: str = "",
        trigger_word: str = "",
        version: str = "",
    ) -> LoRA:
        """
        engine/architecture/trigger_word/version (Mission 088) are
        transmitted as-is to the created LoRA, never validated or
        transformed — purely additive, defaulting to "" to match
        LoRA's own dataclass defaults and keep every pre-Mission-088
        caller's behavior unchanged.

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
            engine=engine,
            architecture=architecture,
            trigger_word=trigger_word,
            version=version,
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

    def update(
        self,
        lora_id: str,
        name: Optional[str] = None,
        engine: Optional[str] = None,
        architecture: Optional[str] = None,
        trigger_word: Optional[str] = None,
        version: Optional[str] = None,
    ) -> bool:
        """
        Mission 090: a single combined mutation for name + the 4 text
        metadata fields — mirrors CharacterManager.update() (Mission
        074), not LoRAManager's split update()/update_name() (an
        artifact of two separate missions, 052 then 073, not a contract
        to reproduce here: this Mission delivers all 5 fields through
        one form and one Save button, so one atomic Manager call with
        one failure surface).

        lora_id unknown -> False, no _save(). Strictly idempotent: a
        field left as None is untouched, an empty string is a
        legitimate value distinct from "not provided", and no _save()
        fires unless at least one of the 5 actually changed. lora_id
        itself is never mutated by this method.

        On a _save() failure, all 5 fields are rolled back to their
        exact previous values on the same LoRA instance before
        LoRALibraryError is raised (wrapping LoRALibraryStorageError,
        the same enveloppe import_lora()/delete() already use — never
        the raw storage exception). No event is published in that case.

        Never touches the filesystem: <library_root>/<lora_id>/ is
        keyed by lora_id (a uuid4, never reused), never by name — a
        rename here never renames/moves anything on disk.
        """

        lora = self._find(lora_id)

        if lora is None:
            return False

        changed = (
            (name is not None and name != lora.name)
            or (engine is not None and engine != lora.engine)
            or (architecture is not None and architecture != lora.architecture)
            or (trigger_word is not None and trigger_word != lora.trigger_word)
            or (version is not None and version != lora.version)
        )

        if not changed:
            return False

        previous_name = lora.name
        previous_engine = lora.engine
        previous_architecture = lora.architecture
        previous_trigger_word = lora.trigger_word
        previous_version = lora.version

        if name is not None:
            lora.name = name
        if engine is not None:
            lora.engine = engine
        if architecture is not None:
            lora.architecture = architecture
        if trigger_word is not None:
            lora.trigger_word = trigger_word
        if version is not None:
            lora.version = version

        try:
            self._save()
        except LoRALibraryStorageError as exc:
            lora.name = previous_name
            lora.engine = previous_engine
            lora.architecture = previous_architecture
            lora.trigger_word = previous_trigger_word
            lora.version = previous_version
            raise LoRALibraryError(str(exc)) from exc

        self._publish(LORA_LIBRARY_UPDATED, lora)

        return True

    def set_thumbnail(
        self, lora_id: str, source_path: str, library_root
    ) -> Optional[LoRALibraryThumbnailResult]:
        """
        Mission 093: mirrors LoRAManager.set_thumbnail()'s transactional
        contract (Missions 047/067/080) almost exactly, adapted to this
        Manager's own conventions rather than copied verbatim:

        - lora_id unknown -> None (nothing happened) — same meaning as
          get()/update()/delete() for an unknown id, NOT the same as a
          real failure.
        - Any real failure (copy or persistence) raises
          LoRALibraryError — unlike LoRAManager.set_thumbnail(), which
          collapses "unknown lora" and "failed copy" into the same bare
          None. LoRALibraryManager's own established contract (see
          import_lora()'s docstring) is that a real failure always
          raises; None/False are reserved for "nothing happened".

        Copies source_path into <library_root>/<lora_id>/ — the same
        destination_folder already used by import_lora()/delete() —
        via WorkspaceStorage.copy_into_workspace() with
        workspace_root=destination_folder (this entry's own folder,
        never the wider library_root): the same choice import_lora()
        already makes, and for the same reason — it guarantees that a
        source already living inside a DIFFERENT entry's own folder is
        never reused as-is, always copied independently.

        On a copy failure, nothing is mutated: lora.thumbnail is left
        untouched and copy_into_workspace() already cleans up any
        partial destination file itself (Mission 028) — no additional
        folder cleanup is needed here, unlike import_lora()'s
        multi-file case.

        On a persistence failure after a successful copy,
        lora.thumbnail is restored to exactly what it was before this
        call, and — only if this call actually created a new physical
        copy, never for a source already reused as-is from this same
        folder — that new copy is deleted on a best-effort basis. A
        cleanup failure never masks the original persistence error,
        only adds orphan information to it.

        Once persistence has actually succeeded, the now-superseded
        previous thumbnail is examined for cleanup — never before,
        never on a persistence failure. It is only ever deleted if it
        is non-empty, resolves to a different file than the new
        thumbnail, AND is demonstrably owned by this entry's own
        private folder (WorkspaceStorage.is_inside(old_thumbnail,
        destination_folder)). Unlike LoRAManager (where a passthrough
        thumbnail can legitimately live anywhere under workspace_root,
        including another LoRA's own folder), every write path this
        Manager has today (import_lora(), and this method) always
        copies into the entry's own folder — an externally-owned old
        thumbnail is therefore structurally unreachable in practice,
        but the ownership guard is kept unconditionally regardless, as
        pure defense in depth, exactly mirroring Mission 080's own
        precedent. An already-owned-but-missing file is treated as
        already cleaned up (no warning); any other OSError is reported
        via cleanup_failed/residual_path without ever rolling back the
        already-persisted new thumbnail.

        LORA_LIBRARY_UPDATED is published only after this call's own
        persistence succeeds — reused as-is (no new event type), since
        its sole consumer (LoRAPage.update_central_library()) already
        ignores the event payload and unconditionally re-reads
        list_loras() in full.
        """

        lora = self._find(lora_id)

        if lora is None:
            return None

        library_root = Path(library_root)
        destination_folder = library_root / lora_id

        try:
            effective_path = WorkspaceStorage.copy_into_workspace(
                Path(source_path), destination_folder, workspace_root=destination_folder,
            )
        except WorkspaceStorageError as exc:
            raise LoRALibraryError(str(exc)) from exc

        is_new_copy = os.path.normcase(str(effective_path)) != os.path.normcase(
            str(Path(source_path).resolve())
        )

        old_thumbnail = lora.thumbnail
        lora.thumbnail = str(effective_path)

        try:
            self._save()
        except LoRALibraryStorageError as exc:
            lora.thumbnail = old_thumbnail
            if is_new_copy:
                try:
                    effective_path.unlink()
                except OSError:
                    raise LoRALibraryError(
                        f"{exc} Additionally, the newly copied thumbnail file could not be "
                        f"cleaned up and remains orphaned on disk at {effective_path}."
                    ) from exc
            raise LoRALibraryError(str(exc)) from exc

        cleanup_failed = False
        residual_path = None

        if old_thumbnail and os.path.normcase(
            str(Path(old_thumbnail).resolve())
        ) != os.path.normcase(str(effective_path)):
            if WorkspaceStorage.is_inside(old_thumbnail, destination_folder):
                try:
                    Path(old_thumbnail).unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    cleanup_failed = True
                    residual_path = old_thumbnail

        self._publish(LORA_LIBRARY_UPDATED, lora)

        return LoRALibraryThumbnailResult(
            thumbnail=lora.thumbnail,
            cleanup_failed=cleanup_failed,
            residual_path=residual_path,
        )

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

    def expose_to_comfyui(self, lora: LoRA, expose_root) -> LoRAComfyUIExposureResult:
        """
        Mission 095: makes a central-library entry visible to ComfyUI
        without duplicating its physical file — creates an NTFS hardlink
        (os.link(), same underlying Win32 mechanism validated empirically
        against the architect's real ComfyUI installation, see
        MISSION_095.md §3.4) from the entry's single model file into
        <expose_root>/AIStudioToolkit/<slug(lora.name)>__<lora.lora_id>.<ext>
        — expose_root must already be a loras root the architect has
        declared to ComfyUI themselves; this method never touches any
        ComfyUI configuration file (MISSION_095.md §3.3/§3.6).

        Validated, in order, each failure raising LoRALibraryError with a
        distinct explicit message — never a bare propagation of the
        underlying OSError:
        - expose_root not configured (empty/falsy);
        - lora.files does not contain exactly one entry (MISSION_095.md
          §3.5 — never an implicit files[0], a cardinality violation is
          always refused outright);
        - that single file does not actually exist on disk;
        - expose_root does not exist as a directory (this method never
          creates it — only the AIStudioToolkit subfolder inside it);
        - the source file and expose_root are not on the same
          filesystem volume (os.stat().st_dev, checked before any
          filesystem mutation) — a hardlink cannot cross volumes, and
          no automatic copy/symlink fallback is performed.

        Idempotence and collision handling (MISSION_095.md §5.3), an
        existing alias always located by lora.lora_id alone
        (_find_existing_alias(), never by recomputing today's expected
        filename from lora.name — see that helper's own docstring for
        why):
        - no existing alias -> create AIStudioToolkit/ if needed, create
          the hardlink, return it (cleanup_failed=False always in this
          branch — nothing to clean up);
        - an existing alias already at today's expected filename
          (lora.name unchanged since it was created) -> if it is
          demonstrably the same file as the current source
          (os.path.samefile) this is a genuine no-op, no filesystem
          mutation at all; if it is not (a different file now occupies
          that exact deterministic name — external tampering, since no
          code path in this Manager can produce that on its own) this
          raises LoRALibraryError rather than ever overwriting it;
        - an existing alias found under a *different* filename (i.e.
          lora.name changed since the last exposure) -> if it is still
          demonstrably the same file as the current source, this is a
          re-exposure: the new hardlink is created *first* (never
          destructive on its own), and only then is the old, now-stale
          alias removed. If that final removal fails, the new exposure
          has still fully succeeded — reported via
          cleanup_failed=True/residual_path, exactly like
          LoRALibraryDeletionResult/LoRALibraryThumbnailResult already
          report a best-effort cleanup failure without ever rolling back
          an already-succeeded primary operation. If the stale alias is
          not demonstrably the same file, this raises LoRALibraryError
          instead of silently deleting an unrelated file.
        """

        if not expose_root:
            raise LoRALibraryError(
                "No ComfyUI exposure path is configured "
                "(ApplicationSettings.comfyui_lora_expose_path) — configure an "
                "already-declared ComfyUI loras root in Settings before exposing "
                "a LoRA to ComfyUI."
            )

        if len(lora.files) != 1:
            raise LoRALibraryError(
                f"LoRA {lora.lora_id!r} has {len(lora.files)} model file(s); exposure "
                f"to ComfyUI requires exactly one admissible model file."
            )

        source_path = Path(lora.files[0])

        if not source_path.is_file():
            raise LoRALibraryError(
                f"LoRA {lora.lora_id!r}'s model file does not exist on disk: {source_path}"
            )

        expose_root = Path(expose_root)

        if not expose_root.is_dir():
            raise LoRALibraryError(
                f"Configured ComfyUI exposure path does not exist or is not a "
                f"directory: {expose_root}"
            )

        if not self._same_volume(source_path, expose_root):
            raise LoRALibraryError(
                f"LoRA {lora.lora_id!r}'s file ({source_path}) and the configured "
                f"ComfyUI exposure path ({expose_root}) are not on the same "
                f"filesystem volume — an NTFS hardlink requires both to be on the "
                f"same volume. No automatic copy/symlink fallback is performed."
            )

        subfolder = expose_root / _COMFYUI_EXPOSE_SUBFOLDER_NAME
        desired_filename = self._expose_alias_filename(lora, source_path)
        desired_path = subfolder / desired_filename

        existing = self._find_existing_alias(expose_root, lora.lora_id)

        if existing is None:
            subfolder.mkdir(parents=True, exist_ok=True)
            try:
                os.link(source_path, desired_path)
            except OSError as exc:
                raise LoRALibraryError(
                    f"Could not create ComfyUI exposure hardlink for LoRA "
                    f"{lora.lora_id!r}: {exc}"
                ) from exc
            return LoRAComfyUIExposureResult(
                alias_name=f"{_COMFYUI_EXPOSE_SUBFOLDER_NAME}\\{desired_filename}",
                cleanup_failed=False,
                residual_path=None,
            )

        if not os.path.samefile(existing, source_path):
            raise LoRALibraryError(
                f"A ComfyUI exposure alias already exists at {existing} for LoRA "
                f"{lora.lora_id!r} but does not point to its current file — "
                f"refusing to overwrite it."
            )

        if existing == desired_path:
            return LoRAComfyUIExposureResult(
                alias_name=f"{_COMFYUI_EXPOSE_SUBFOLDER_NAME}\\{desired_filename}",
                cleanup_failed=False,
                residual_path=None,
            )

        try:
            os.link(source_path, desired_path)
        except OSError as exc:
            raise LoRALibraryError(
                f"Could not re-expose LoRA {lora.lora_id!r} to ComfyUI under its "
                f"updated name: {exc}"
            ) from exc

        cleanup_failed = False
        residual_path = None

        try:
            existing.unlink()
        except OSError:
            cleanup_failed = True
            residual_path = str(existing)

        return LoRAComfyUIExposureResult(
            alias_name=f"{_COMFYUI_EXPOSE_SUBFOLDER_NAME}\\{desired_filename}",
            cleanup_failed=cleanup_failed,
            residual_path=residual_path,
        )

    def unexpose_from_comfyui(self, lora: LoRA, expose_root) -> bool:
        """
        Mission 095: removes a LoRA's ComfyUI exposure alias, if any —
        symmetric to expose_to_comfyui(), never touches the entry's
        canonical file. Idempotent: no configured expose_root, or no
        alias found for lora.lora_id (never created, or already
        removed), is a no-op returning False — this is never an error,
        matching MISSION_095.md §5.4. An alias found for lora.lora_id
        (located exactly like expose_to_comfyui() does — by lora_id
        alone, independent of any renaming of lora.name since it was
        created) is deleted; only a real filesystem failure while
        deleting it raises LoRALibraryError.
        """

        if not expose_root:
            return False

        existing = self._find_existing_alias(Path(expose_root), lora.lora_id)

        if existing is None:
            return False

        try:
            existing.unlink()
        except OSError as exc:
            raise LoRALibraryError(
                f"Could not remove ComfyUI exposure alias for LoRA "
                f"{lora.lora_id!r} at {existing}: {exc}"
            ) from exc

        return True

    @staticmethod
    def _slugify_lora_name(name: str) -> str:
        slug = _SLUG_UNSAFE_CHARS.sub("_", name).strip("_")
        return slug[:_SLUG_MAX_LENGTH] or "lora"

    @classmethod
    def _expose_alias_filename(cls, lora: LoRA, source_path: Path) -> str:
        # Mission 095: keyed on lora.lora_id in full (never truncated —
        # the full uuid4 costs nothing and removes any artificial
        # collision risk a short prefix would otherwise introduce) so
        # that the filename alone is enough to prove which entry it
        # belongs to; the slug of lora.name is purely cosmetic, never
        # used to locate an existing alias (see _find_existing_alias()).
        return f"{cls._slugify_lora_name(lora.name)}__{lora.lora_id}{source_path.suffix}"

    @staticmethod
    def _find_existing_alias(expose_root: Path, lora_id: str) -> Optional[Path]:
        # Mission 095: always searched by lora_id alone, deliberately
        # never by recomputing the filename expose_to_comfyui() would
        # produce for the entry's *current* lora.name — a rename
        # between two exposures would make that recomputed name diverge
        # from what is actually on disk, causing an existing alias to go
        # silently unnoticed (and, in unexpose_from_comfyui(), silently
        # unremovable). The suffixed pattern is unambiguous: lora_id is
        # a uuid4 and therefore never contains a ".".
        subfolder = expose_root / _COMFYUI_EXPOSE_SUBFOLDER_NAME

        if not subfolder.is_dir():
            return None

        matches = sorted(subfolder.glob(f"*__{lora_id}.*"))

        if len(matches) > 1:
            raise LoRALibraryError(
                f"Multiple ComfyUI exposure aliases found for LoRA {lora_id!r} "
                f"under {subfolder} ({[m.name for m in matches]}) — refusing to "
                f"guess which one is correct; remove the unexpected file(s) "
                f"manually before retrying."
            )

        return matches[0] if matches else None

    @staticmethod
    def _same_volume(path_a: Path, path_b: Path) -> bool:
        return os.stat(path_a).st_dev == os.stat(path_b).st_dev

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
