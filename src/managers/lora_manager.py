import os
import uuid
from pathlib import Path
from typing import List, NamedTuple, Optional

from src.core.event_bus import EventBus
from src.domain.lora import LoRA
from src.infrastructure.storage.workspace_storage import (
    WorkspaceStorage,
    WorkspaceStorageError,
)
from src.managers.character_manager import (
    CharacterManager,
    CHARACTER_SELECTED,
    CHARACTER_DELETED,
)
from src.managers.workspace_manager import (
    WorkspaceManager,
    WorkspaceManagerError,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_CLOSED,
)

LORA_CREATED = "lora.created"
LORA_SELECTED = "lora.selected"
LORA_DELETED = "lora.deleted"


class LoRADeletionResult(NamedTuple):
    """
    Mission 075: delete()'s return type — see DatasetDeletionResult
    (dataset_manager.py) for the full rationale, identical here. Not
    shared across the two Managers — same "duplicate rather than
    introduce a shared abstraction" convention already followed by
    every rollback pattern since Mission 068.
    """

    deleted: bool
    cleanup_failed: bool
    residual_path: Optional[str]


class LoRAManager:
    """
    Coordinates LoRA CRUD, selection and file import within the
    Workspace's principal Character (Mission 026/028/029). Operates
    exclusively on character_manager.principal_character.loras — never
    touches storage or Qt directly; persistence is delegated to
    WorkspaceManager.save().
    """

    def __init__(
        self,
        character_manager: CharacterManager,
        workspace_manager: WorkspaceManager,
        event_bus: Optional[EventBus] = None,
    ):
        self._character_manager = character_manager
        self._workspace_manager = workspace_manager
        self._event_bus = event_bus

        # Runtime-only, like DatasetManager.active_dataset_id — never
        # persisted.
        self.active_lora_id: Optional[str] = None

        # A character switch (selection or deletion) or a workspace
        # switch must never leave active_lora_id pointing at a LoRA
        # that no longer belongs to the active character.
        if self._event_bus is not None:
            self._event_bus.subscribe(CHARACTER_SELECTED, self._on_context_changed)
            self._event_bus.subscribe(CHARACTER_DELETED, self._on_context_changed)
            self._event_bus.subscribe(WORKSPACE_CREATED, self._on_context_changed)
            self._event_bus.subscribe(WORKSPACE_OPENED, self._on_context_changed)
            self._event_bus.subscribe(WORKSPACE_CLOSED, self._on_context_changed)

    def _on_context_changed(self, payload) -> None:
        self.active_lora_id = None

    @property
    def loras(self) -> List[LoRA]:
        # Mission 029: reads principal_character, not active_character —
        # same fix already applied to DatasetManager in Mission 028 (see
        # its property's docstring for the full rationale). Any Workspace
        # opened via WORKSPACE_OPENED (as opposed to freshly created)
        # otherwise leaves active_character_id at None for the whole
        # session, since CharactersPage never calls select() anymore.
        character = self._character_manager.principal_character
        if character is None:
            return []
        return character.loras

    def list_loras(self) -> List[dict]:
        return [lora.to_dict() for lora in self.loras]

    @property
    def active_lora(self) -> Optional[LoRA]:
        if self.active_lora_id is None:
            return None
        return self._find(self.active_lora_id)

    def create(self, name: str) -> Optional[LoRA]:

        character = self._character_manager.principal_character

        if character is None:
            return None

        lora = LoRA(lora_id=str(uuid.uuid4()), name=name)

        character.loras.append(lora)

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError:
            character.loras.remove(lora)
            raise

        self._publish(LORA_CREATED, lora)

        return lora

    def select(self, lora_id: str) -> Optional[LoRA]:

        lora = self._find(lora_id)

        if lora is None:
            return None

        self.active_lora_id = lora.lora_id

        self._publish(LORA_SELECTED, lora)

        return lora

    def delete(self, lora_id: str) -> LoRADeletionResult:
        """
        Mission 068: if save() fails after the LoRA has already been
        removed from character.loras, the Domain deletion is rolled
        back before the exception is re-raised — the same LoRA object
        is reinserted at its original index, and active_lora_id (if it
        pointed at this LoRA) is restored to its previous value.

        Mission 075: the LoRA's private folder (models/loras/<id>/,
        created lazily only by set_thumbnail() — the files list is
        never copied there, only ever holding external references, so
        this folder can never contain a file shared with another LoRA
        or with a future centralized LoRA library) is now deleted
        transactionally along with the Domain object. Same order as
        DatasetManager.delete() (see its docstring for the full
        rationale): folder moved atomically into a lazily-created
        `.trash/` staging area before the Domain mutation — abort
        before anything is touched if that move fails; on a save()
        failure the Domain rollback above always runs first (cannot
        itself fail), then the folder is independently moved back,
        with an enriched WorkspaceManagerError if that reverse move
        also fails; on save() success the staged folder is permanently
        deleted on a best-effort basis, never rolling back an
        already-persisted deletion on failure — only reported via the
        returned LoRADeletionResult.
        """

        character = self._character_manager.principal_character

        if character is None:
            return LoRADeletionResult(deleted=False, cleanup_failed=False, residual_path=None)

        lora = self._find(lora_id)

        if lora is None:
            return LoRADeletionResult(deleted=False, cleanup_failed=False, residual_path=None)

        workspace_root = self._workspace_manager.current_workspace.root
        source_folder = workspace_root / "models" / "loras" / lora.lora_id
        trash_folder = None

        if source_folder.exists():
            trash_folder = workspace_root / ".trash" / f"lora_{lora.lora_id}_{uuid.uuid4().hex}"
            try:
                WorkspaceStorage.rename_folder(source_folder, trash_folder)
            except WorkspaceStorageError as exc:
                raise WorkspaceManagerError(str(exc)) from exc

        index = character.loras.index(lora)
        previous_active_lora_id = self.active_lora_id

        character.loras.remove(lora)

        if self.active_lora_id == lora_id:
            self.active_lora_id = None

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError as exc:
            # The Domain rollback must always run, regardless of whether
            # the filesystem rollback below succeeds — these two plain
            # statements cannot themselves raise.
            character.loras.insert(index, lora)
            self.active_lora_id = previous_active_lora_id

            if trash_folder is not None:
                try:
                    WorkspaceStorage.rename_folder(trash_folder, source_folder)
                except WorkspaceStorageError as rollback_exc:
                    raise WorkspaceManagerError(
                        f"{exc} The LoRA itself has been restored in the "
                        f"project and is safe. However, its folder could not "
                        f"be moved back from its temporary location and now "
                        f"remains at {trash_folder} instead of {source_folder} "
                        f"({rollback_exc}). Manual recovery required: move "
                        f"{trash_folder} back to {source_folder} yourself "
                        f"once the underlying issue is resolved."
                    ) from rollback_exc
            raise

        cleanup_failed = False
        residual_path = None

        if trash_folder is not None:
            try:
                WorkspaceStorage.delete_folder(trash_folder)
            except WorkspaceStorageError:
                cleanup_failed = True
                residual_path = str(trash_folder)

        self._publish(LORA_DELETED, lora)

        return LoRADeletionResult(
            deleted=True, cleanup_failed=cleanup_failed, residual_path=residual_path
        )

    def add_files(self, paths: List[str]) -> int:
        """
        Append paths not already present in the active LoRA's files.
        Returns the number of files actually added — mirrors
        DatasetManager.add_images()'s dedup contract exactly, operating
        on active_lora the same way.

        Mission 076: never copies/touches any physical file (LoRA.files
        only ever holds external path references — see set_thumbnail(),
        the sole method that copies anything into the LoRA's own private
        folder). If save() fails, lora.files is restored to the exact
        previous list object — kept by reference rather than mutated in
        place, so restoring it on failure is exact by construction.
        """

        lora = self.active_lora

        if lora is None:
            return 0

        seen = set(lora.files)
        new_paths = []

        for path in paths:
            if path in seen:
                continue
            seen.add(path)
            new_paths.append(path)

        if not new_paths:
            return 0

        original_files = lora.files
        lora.files = original_files + new_paths

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError:
            lora.files = original_files
            raise

        return len(new_paths)

    def remove_files(self, paths: List[str]) -> int:
        """
        Removes paths from the active LoRA's files (Mission 050) —
        symmetric to add_files(): exact string equality, never a
        resolved/normalized path comparison, since files are never
        copied for this field. Never touches the physical file, never
        touches name/engine/architecture/trigger_word/version/thumbnail.
        Returns the number of entries actually removed; saves only if
        at least one entry was actually removed.

        Mission 076: if save() fails, lora.files is restored to the
        exact previous list object (same order, same entries, including
        any pre-existing duplicates) — same rollback convention as
        add_files().
        """

        lora = self.active_lora

        if lora is None:
            return 0

        targets = set(paths)
        original_files = lora.files
        lora.files = [f for f in original_files if f not in targets]

        removed = len(original_files) - len(lora.files)

        if removed:
            try:
                self._workspace_manager.save()
            except WorkspaceManagerError:
                lora.files = original_files
                raise

        return removed

    def update(
        self,
        lora_id: str,
        engine: Optional[str] = None,
        architecture: Optional[str] = None,
        trigger_word: Optional[str] = None,
        version: Optional[str] = None,
    ) -> bool:
        """
        Updates a LoRA's text metadata (Mission 047). Strictly
        idempotent, same contract as CharacterManager.update(): a field
        left as None is untouched, an empty string is a legitimate
        value distinct from "not provided", and no save() fires unless
        something actually changed. Never touches `name`/`files`/
        `thumbnail` — name has its own sibling method (update_name(),
        Mission 052), files has add_files()/remove_files(), thumbnail
        has set_thumbnail() (file I/O, a different kind of operation
        entirely).

        Mission 073: if save() fails after the four fields have already
        been mutated in memory, all four are rolled back to their exact
        previous values on the same LoRA instance before the exception
        is re-raised — no event is published either before or after
        this mission (never had one, same as CharacterManager.update()),
        so that clause of the usual rollback contract has no effect
        here. Domain-only mutation, no filesystem involved, no other
        state touched (verified: no active_lora_id or other field is
        ever read or written by this method) — a local rollback of the
        four fields is sufficient.
        """

        lora = self._find(lora_id)

        if lora is None:
            return False

        changed = (
            (engine is not None and engine != lora.engine)
            or (architecture is not None and architecture != lora.architecture)
            or (trigger_word is not None and trigger_word != lora.trigger_word)
            or (version is not None and version != lora.version)
        )

        if not changed:
            return False

        previous_engine = lora.engine
        previous_architecture = lora.architecture
        previous_trigger_word = lora.trigger_word
        previous_version = lora.version

        if engine is not None:
            lora.engine = engine
        if architecture is not None:
            lora.architecture = architecture
        if trigger_word is not None:
            lora.trigger_word = trigger_word
        if version is not None:
            lora.version = version

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError:
            lora.engine = previous_engine
            lora.architecture = previous_architecture
            lora.trigger_word = previous_trigger_word
            lora.version = previous_version
            raise

        return True

    def update_name(self, lora_id: str, name: str) -> bool:
        """
        Rename a LoRA (Mission 052). Sibling of update() — targets a
        LoRA by lora_id explicitly (this Manager's existing convention
        for update(), unlike ModelManager/WorkflowManager which act on
        the active entity implicitly). Strictly idempotent: returns
        False (no save()) if lora_id is unknown or if `name` is
        identical to the stored value. Not validated (empty string
        legitimate, no stripping) — same convention already used by
        CharacterManager.update(name=...). Never touches `files`,
        `engine`/`architecture`/`trigger_word`/`version`, or
        `thumbnail`.
        """

        lora = self._find(lora_id)

        if lora is None:
            return False

        if lora.name == name:
            return False

        old_name = lora.name
        lora.name = name

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError:
            lora.name = old_name
            raise

        return True

    def set_thumbnail(self, lora_id: str, source_path: str) -> Optional[str]:
        """
        Copies source_path into <workspace_root>/models/loras/<lora_id>/
        (WorkspaceStorage.copy_into_workspace(), same primitive already
        reused by add_images()/add_files() — a source already internal
        to the Workspace is recognized and reused as-is, no new copy).
        Separate from update() because this performs real file I/O,
        with its own failure mode: on any WorkspaceStorageError (source
        missing, disk full, ...), LoRA.thumbnail is left completely
        untouched and nothing is saved — a failed copy must never lose
        the previously stored thumbnail. Returns the resulting internal
        path on success, or None if the LoRA doesn't exist or the copy
        failed. LoRA.files is never read or modified by this method.
        Whatever the previous physical thumbnail file was, replacing it
        with a new one never deletes it — an unrelated, pre-existing
        policy this method does not change.

        Mission 067: the same failure mode now also covers save()
        itself. If it fails, `lora.thumbnail` is restored to exactly
        what it was before this call, and — only if this call actually
        created a new physical copy, never for a passthrough source
        already located under workspace_root — that new copy is
        deleted on a best-effort basis. A cleanup failure never masks
        the original persistence error, only adds orphan information to
        it (mirrors WorkspaceManager.add_images()/rename()'s same
        principle).
        """

        lora = self._find(lora_id)

        if lora is None:
            return None

        workspace = self._workspace_manager.current_workspace
        workspace_root = workspace.root
        destination_folder = workspace_root / "models" / "loras" / lora.lora_id

        try:
            effective_path = WorkspaceStorage.copy_into_workspace(
                Path(source_path), destination_folder, workspace_root,
            )
        except WorkspaceStorageError:
            return None

        is_new_copy = os.path.normcase(str(effective_path)) != os.path.normcase(
            str(Path(source_path).resolve())
        )

        old_thumbnail = lora.thumbnail
        lora.thumbnail = str(effective_path)

        try:
            self._workspace_manager.save()
        except WorkspaceManagerError as exc:
            lora.thumbnail = old_thumbnail
            if is_new_copy:
                try:
                    effective_path.unlink()
                except OSError:
                    raise WorkspaceManagerError(
                        f"{exc} Additionally, the newly copied thumbnail file could not be "
                        f"cleaned up and remains orphaned on disk at {effective_path}."
                    ) from exc
            raise

        return lora.thumbnail

    def _find(self, lora_id: str) -> Optional[LoRA]:
        for lora in self.loras:
            if lora.lora_id == lora_id:
                return lora
        return None

    def _publish(self, event_name: str, lora: LoRA) -> None:

        if self._event_bus is None:
            return

        self._event_bus.publish(event_name, lora.to_dict())
