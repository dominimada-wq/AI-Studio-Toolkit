import os
import uuid
from pathlib import Path
from typing import List, NamedTuple, Optional

from src.core.event_bus import EventBus
from src.domain.image import Image
from src.domain.workspace import Workspace
from src.infrastructure.storage.workspace_storage import (
    WorkspaceStorage,
    WorkspaceStorageError,
    WorkspaceRenamePermissionError as _StorageRenamePermissionError,
)

WORKSPACE_CREATED = "workspace.created"
WORKSPACE_OPENED = "workspace.opened"
WORKSPACE_SAVED = "workspace.saved"
WORKSPACE_CLOSED = "workspace.closed"
WORKSPACE_RENAMED = "workspace.renamed"


class ImportResult(NamedTuple):
    """
    Return type of WorkspaceManager.add_images()/DatasetManager.
    add_images() (Mission 028). added is the number of new Image
    entries actually created; failed and skipped are the source paths
    (in batch order) that respectively could not be copied (see
    WorkspaceStorage.copy_into_workspace()) or were deliberately
    ignored as duplicates — a duplicate is never reported under
    failed, so a caller can never mistake a harmless skip for an
    error.
    """
    added: int
    failed: List[str]
    skipped: List[str]


class CollisionInfo(NamedTuple):
    """
    One entry of WorkspaceManager/DatasetManager.preview_collisions()'s
    result (Mission 028 second smoke test): `source` would collide with
    a name already taken in the destination folder if imported as-is;
    `suggested_name` is the same collision-free name add_images() would
    have picked silently by default (e.g. "photo_1.jpg") — offered to
    the user as an editable, non-binding starting point, never applied
    without confirmation for a UI-driven import.
    """
    source: str
    suggested_name: str


class RemovalPreview(NamedTuple):
    """
    Read-only result of WorkspaceManager.preview_image_removal()
    (Mission 046): `deletable` holds every requested path resolving to
    a Workspace.images entry that is both physically inside
    workspace_root and still present on disk — real filesystem
    deletion will occur for these; `reference_only` holds every other
    match (external to the Workspace, and/or missing from disk) — only
    the Workspace.images entry will be dropped, no filesystem call.
    Deliberately a single bucket for "external" and "missing": in both
    cases nothing is actually deleted from disk, and the caller must
    describe the consequence, never invent an origin for a missing
    file. A path's mere presence in Workspace.images is never treated
    as a guarantee of physical ownership — see
    test_external_paths_are_strictly_unchanged/test_legacy_project_
    json_with_external_reference_still_loads_unchanged.
    """
    deletable: List[str]
    reference_only: List[str]


class RemovalResult(NamedTuple):
    """
    Return type of WorkspaceManager.remove_images() (Mission 046,
    extended Mission 066). `blocked_by` is non-empty only when at least
    one requested path is still referenced by a Dataset (any Character
    of the current Workspace) — in that case the whole call is a
    no-op: every other field is empty, nothing is mutated, nothing is
    saved. Otherwise `deleted`/`reference_only` mirror
    preview_image_removal()'s classification for exactly the paths
    that were actually found in Workspace.images and removed.

    Mission 066: reaching this return value at all already means
    Workspace.images/project.json no longer reference any of these
    paths — that logical removal is unconditional and already durable
    once persisted (see remove_images()'s persistence-first order).
    `deletion_failed` is the (normally empty) subset of `deleted`-shaped
    candidates whose physical file could not actually be unlinked from
    disk (e.g. locked by another process) — these become orphaned
    files, never a reason to reintroduce them into the Workspace.
    """
    deleted: List[str]
    reference_only: List[str]
    blocked_by: dict
    deletion_failed: List[str]


class WorkspaceManagerError(Exception):
    """
    Raised by WorkspaceManager when a workspace operation fails.
    Wraps infrastructure-level errors (e.g. WorkspaceStorageError) so
    that callers — in particular the UI — never need to import
    anything from src.infrastructure directly.
    """


class WorkspaceRenamePermissionError(WorkspaceManagerError):
    """
    Raised by rename() specifically when the initial folder rename
    fails with access denied (see WorkspaceRenamePermissionError in
    workspace_storage.py — Mission 027, confirmed via Process Explorer
    to be explorer.exe holding handles on the project's subfolders, not
    an application-side resource leak). current_workspace is left
    strictly untouched in this case (the physical rename never
    succeeded), exactly like any other failure of the initial rename
    step. Kept distinct from WorkspaceManagerError so the UI can show an
    actionable message without ever misclassifying an unrelated
    failure (target already exists, disk full, ...) as this one.
    """


class WorkspaceManager:
    """
    Single source of truth for the current workspace.
    """

    def __init__(self, event_bus: Optional[EventBus] = None):
        self.current_workspace: Optional[Workspace] = None
        self._event_bus = event_bus

    @property
    def opened(self) -> bool:
        return self.current_workspace is not None

    def create(self, folder) -> Workspace:

        folder = Path(folder)

        workspace = Workspace(name=folder.name, root=folder)

        try:
            WorkspaceStorage.create_directories(folder)
            WorkspaceStorage.save(folder, workspace.to_dict())
        except WorkspaceStorageError as exc:
            raise WorkspaceManagerError(str(exc)) from exc

        self.current_workspace = workspace

        self._publish(WORKSPACE_CREATED)

        return workspace

    def open(self, folder) -> Optional[Workspace]:

        folder = Path(folder)

        try:
            data = WorkspaceStorage.load(folder)
        except WorkspaceStorageError as exc:
            raise WorkspaceManagerError(str(exc)) from exc

        if data is None:
            # A failed open must never close the workspace that is
            # currently open — leave current_workspace untouched.
            return None

        self.current_workspace = Workspace.from_dict(data, root=folder)

        self._publish(WORKSPACE_OPENED)

        return self.current_workspace

    def save(self) -> None:

        if self.current_workspace is None:
            return

        try:
            WorkspaceStorage.save(
                self.current_workspace.root,
                self.current_workspace.to_dict(),
            )
        except WorkspaceStorageError as exc:
            raise WorkspaceManagerError(str(exc)) from exc

        self._publish(WORKSPACE_SAVED)

    def rename(self, new_name: str) -> bool:
        """
        Renames the current project (Mission 027): the physical folder,
        Workspace.name, and every internal path (Workspace.images,
        Character.datasets[].images, Workspace.models, Workspace.workflows,
        Character.loras[].files/thumbnail) rewritten to the new root.
        Paths located outside the old root, and every Character.name, are
        never touched.

        Deliberately idempotent, mirroring CharacterManager.update()'s
        contract: returns False (no I/O, no event) if new_name already
        matches both the folder's actual current name and Workspace.name.
        No content validation is performed here (that is the UI's
        responsibility, see RenameProjectDialog) — only filesystem
        preconditions are checked, via WorkspaceStorage.

        self.current_workspace is deliberately never mutated until both
        the physical rename and the project.json save have fully
        succeeded — see MISSION_027.md section 7 for the full rationale.
        On any failure, current_workspace is either left byte-for-byte
        untouched, or (rename succeeded, save failed) a best-effort
        filesystem rollback is attempted; either way no partial state is
        ever exposed and WORKSPACE_RENAMED is never published.
        """

        if self.current_workspace is None:
            raise WorkspaceManagerError("No workspace is currently open")

        workspace = self.current_workspace
        old_root = workspace.root
        old_root_resolved = old_root.resolve()
        old_name = workspace.name

        folder_needs_rename = new_name != old_root.name
        name_needs_update = new_name != old_name

        if not folder_needs_rename and not name_needs_update:
            return False

        new_root = (old_root.parent / new_name) if folder_needs_rename else old_root

        # Pure computation — current_workspace is not mutated by this call.
        new_data = self._build_renamed_payload(
            workspace, old_root_resolved, new_root, new_name
        )

        if folder_needs_rename:
            try:
                WorkspaceStorage.rename_folder(old_root, new_root)
            except _StorageRenamePermissionError as exc:
                # current_workspace is still exactly what it was before
                # this call — the physical rename never happened. Distinct
                # type so the UI can show an actionable message (Mission
                # 027 smoke test diagnostic: explorer.exe holding handles
                # on the project's subfolders, see MISSION_027.md section
                # 20) instead of a generic technical error.
                raise WorkspaceRenamePermissionError(str(exc)) from exc
            except WorkspaceStorageError as exc:
                raise WorkspaceManagerError(str(exc)) from exc

        try:
            WorkspaceStorage.save(new_root, new_data)
        except WorkspaceStorageError as exc:
            if folder_needs_rename:
                try:
                    WorkspaceStorage.rename_folder(new_root, old_root)
                except WorkspaceStorageError as rollback_exc:
                    permission_hint = (
                        " This rollback failure is itself an access-denied "
                        "error, most likely for the same reason as a plain "
                        "rename failure (another application — commonly a "
                        "Windows Explorer window — has a subfolder of the "
                        "project open); closing it and retrying may resolve "
                        "this without any manual recovery."
                        if isinstance(rollback_exc, _StorageRenamePermissionError)
                        else ""
                    )
                    raise WorkspaceManagerError(
                        "Rename failed while saving project.json "
                        f"({exc}), and the automatic rollback also failed "
                        f"({rollback_exc}). The project folder is now "
                        f"named '{new_root.name}' on disk at {new_root}, "
                        f"but project.json inside it was not updated and "
                        f"still reflects the previous name '{old_name}'. "
                        f"The application's in-memory state was left "
                        f"unchanged and still points to {old_root}, which "
                        f"no longer exists on disk. Manual recovery "
                        f"required: rename the folder back to "
                        f"'{old_name}' yourself, or reopen the project "
                        f"from its current location ({new_root}) and "
                        f"retry.{permission_hint}"
                    ) from rollback_exc
            raise WorkspaceManagerError(str(exc)) from exc

        self.current_workspace = Workspace.from_dict(new_data, root=new_root)

        self._publish(WORKSPACE_RENAMED)

        return True

    def _build_renamed_payload(
        self, workspace: Workspace, old_root_resolved: Path, new_root: Path, new_name: str
    ) -> dict:
        """
        Pure computation (no I/O, no mutation of `workspace`): returns a
        fresh to_dict()-shaped payload with `name` replaced and every
        path-bearing field remapped from under old_root_resolved to
        new_root via _remap_path(). Fields outside old_root_resolved, and
        Character.name, are left byte-for-byte unchanged.
        """

        data = workspace.to_dict()
        data["name"] = new_name

        for image in data["images"]:
            image["file_path"] = self._remap_path(
                image["file_path"], old_root_resolved, new_root
            )

        for character in data["characters"]:
            for dataset in character["datasets"]:
                for image in dataset["images"]:
                    image["file_path"] = self._remap_path(
                        image["file_path"], old_root_resolved, new_root
                    )
            for lora in character["loras"]:
                lora["files"] = [
                    self._remap_path(path, old_root_resolved, new_root)
                    for path in lora["files"]
                ]
                lora["thumbnail"] = self._remap_path(
                    lora["thumbnail"], old_root_resolved, new_root
                )

        for model in data["models"]:
            model["file_path"] = self._remap_path(
                model["file_path"], old_root_resolved, new_root
            )

        for workflow in data["workflows"]:
            workflow["file_path"] = self._remap_path(
                workflow["file_path"], old_root_resolved, new_root
            )

        return data

    @staticmethod
    def _remap_path(path_str: str, old_root_resolved: Path, new_root: Path) -> str:
        """
        Returns path_str unchanged if it is empty (a legitimate "no file
        associated yet" value, e.g. Model.file_path/Workflow.file_path)
        or located outside old_root_resolved. Otherwise returns the
        equivalent path under new_root. Comparison is component-by-
        component (Path.parts), never a raw string prefix check, with
        each component normalized via os.path.normcase() — a deliberate,
        explicit case-insensitive/separator-normalized comparison
        (Windows/NTFS semantics), not relied upon implicitly from
        pathlib's own cross-version behavior.
        """

        if not path_str:
            return path_str

        candidate = Path(path_str).resolve()

        old_parts = old_root_resolved.parts
        candidate_parts = candidate.parts

        if len(candidate_parts) < len(old_parts):
            return path_str

        prefix = [os.path.normcase(part) for part in candidate_parts[: len(old_parts)]]
        old_normalized = [os.path.normcase(part) for part in old_parts]

        if prefix != old_normalized:
            return path_str

        remainder = candidate_parts[len(old_parts):]
        return str(new_root.joinpath(*remainder)) if remainder else str(new_root)

    def close(self) -> None:
        self.current_workspace = None
        self._publish(WORKSPACE_CLOSED)

    def preview_collisions(self, paths: list) -> List["CollisionInfo"]:
        """
        Read-only prediction (Mission 028 second smoke test) of every
        source in `paths` that would collide with a name already taken
        in <workspace_root>/images/ if add_images() were called on it
        right now — i.e. every source add_images() would otherwise
        silently rename via WorkspaceStorage.resolve_collision_free_name()
        without asking. The UI (ImagesPage) calls this before importing
        so it can show the user a single confirmation dialog instead of
        letting the automatic suffix ("photo.jpg" -> "photo_1.jpg")
        happen unannounced — the automatic behavior itself remains the
        underlying safety net (still used verbatim whenever add_images()
        is called without a `renames` decision, e.g. every existing
        test and any other programmatic caller).

        An already-internal source (WorkspaceStorage.is_inside(), see
        add_images()) can never collide — reused as-is, never even
        considered here. A source that duplicates another one already
        present earlier in the same `paths` list is only reported once.
        `also_avoid` tracks names already provisionally claimed by an
        earlier entry in this same batch, since nothing has actually
        been written to disk yet at preview time — without it, two
        brand-new external files sharing a name would both silently
        appear collision-free here, only for the second one to still
        be auto-suffixed unannounced once add_images() actually runs
        them sequentially for real.
        """

        if self.current_workspace is None:
            return []

        workspace_root = self.current_workspace.root
        destination_folder = workspace_root / "images"

        seen_sources = set()
        claimed_names = set()
        collisions = []

        for path in paths:
            source = Path(path)
            resolved_source = os.path.normcase(str(source.resolve()))

            if resolved_source in seen_sources:
                continue
            seen_sources.add(resolved_source)

            if WorkspaceStorage.is_inside(source, workspace_root):
                continue

            resolved_target = WorkspaceStorage.resolve_collision_free_name(
                source, destination_folder, also_avoid=claimed_names
            )
            claimed_names.add(resolved_target.name)

            if resolved_target.name != source.name:
                collisions.append(CollisionInfo(source=str(path), suggested_name=resolved_target.name))

        return collisions

    def add_images(self, paths: list, renames: Optional[dict] = None) -> ImportResult:
        """
        Copies each path in `paths` into <workspace_root>/images/
        (Mission 028) — a source already located anywhere under
        Workspace.root (e.g. a generated image already under
        outputs/, Mission 013/014's Accept flow; or a file re-selected
        directly from images/) is recognized as already-internal and
        reused as-is, never copied onto itself (see
        WorkspaceStorage.copy_into_workspace()). Best-effort across the
        whole batch: one failing file never blocks the rest. Nothing
        is ever persisted to project.json for a file whose copy
        failed. Each accepted path becomes its own Image (Mission 011:
        Workspace owns its own Image pool, independent from
        Dataset.images).

        `renames` (Mission 028 second smoke test — see
        preview_collisions() and ImportCollisionDialog): an optional
        {source_path: destination_filename} map for sources whose
        collision the caller already resolved with the user. Left out,
        a colliding source still falls back to the original silent
        collision-safe suffix (WorkspaceStorage.copy_into_workspace()'s
        own default) — that automatic behavior is a property of the
        underlying primitive, deliberately kept for any caller that
        never asked the user (tests, programmatic use); only the UI
        import flow (ImagesPage) now always asks first via
        preview_collisions() before ever reaching this point with an
        unresolved collision.

        Distinguishes three outcomes per source path, never conflating
        a harmless duplicate with an error — see ImportResult: added
        (new Image created), skipped (exact duplicate within this
        call, or a path that already resolves to an Image already
        present in this pool), failed (the copy itself could not be
        completed, diagnosable via ImportResult.failed).
        """

        if self.current_workspace is None:
            return ImportResult(added=0, failed=[], skipped=[])

        renames = renames or {}
        workspace_root = self.current_workspace.root
        destination_folder = workspace_root / "images"

        existing = {
            os.path.normcase(str(Path(image.file_path).resolve()))
            for image in self.current_workspace.images
            if image.file_path
        }

        seen_in_batch = set()
        new_images = []
        failed = []
        skipped = []

        for path in paths:
            resolved_source = os.path.normcase(str(Path(path).resolve()))

            if resolved_source in seen_in_batch:
                skipped.append(path)
                continue
            seen_in_batch.add(resolved_source)

            try:
                effective_path = WorkspaceStorage.copy_into_workspace(
                    Path(path), destination_folder, workspace_root,
                    target_name=renames.get(path),
                )
            except WorkspaceStorageError:
                failed.append(path)
                continue

            effective_key = os.path.normcase(str(effective_path))

            if effective_key in existing:
                skipped.append(path)
                continue
            existing.add(effective_key)

            new_images.append(Image(image_id=str(uuid.uuid4()), file_path=str(effective_path)))

        if new_images:
            self.current_workspace.images.extend(new_images)
            self.save()

        return ImportResult(added=len(new_images), failed=failed, skipped=skipped)

    def images_referenced_by_datasets(self, paths: List[str]) -> dict:
        """
        Read-only (Mission 046): returns {dataset_name: [matching
        paths]} for every Dataset — across every Character of the
        current Workspace, not only the principal one (cardinality is
        technically unconstrained, Missions 026/036) — whose own Image
        pool contains at least one entry resolving to one of `paths`.
        An empty dict means none of `paths` is currently referenced by
        any Dataset. Pure Domain traversal of Workspace.characters —
        never calls into DatasetManager/CharacterManager, avoiding any
        circular Manager dependency.
        """

        if self.current_workspace is None:
            return {}

        resolved_targets = {
            os.path.normcase(str(Path(path).resolve())) for path in paths
        }

        referenced_by = {}

        for character in self.current_workspace.characters:
            for dataset in character.datasets:
                matches = [
                    image.file_path for image in dataset.images
                    if image.file_path
                    and os.path.normcase(str(Path(image.file_path).resolve())) in resolved_targets
                ]
                if matches:
                    referenced_by[dataset.name] = referenced_by.get(dataset.name, []) + matches

        return referenced_by

    def preview_image_removal(self, paths: List[str]) -> RemovalPreview:
        """
        Read-only (Mission 046): classifies each of `paths` without any
        mutation — see RemovalPreview for the exact deletable/
        reference_only distinction. Callers (ImagesPage) use this to
        build an accurate confirmation message before remove_images()
        is ever invoked; it never checks Dataset references itself —
        see images_referenced_by_datasets() for that, called first and
        separately by the caller.
        """

        if self.current_workspace is None:
            return RemovalPreview(deletable=[], reference_only=[])

        workspace_root = self.current_workspace.root
        deletable = []
        reference_only = []

        for path in paths:
            candidate = Path(path)
            if WorkspaceStorage.is_inside(candidate, workspace_root) and candidate.exists():
                deletable.append(path)
            else:
                reference_only.append(path)

        return RemovalPreview(deletable=deletable, reference_only=reference_only)

    def remove_images(self, paths: List[str]) -> RemovalResult:
        """
        Mission 046: removes every Workspace.images entry matching one
        of `paths`. Atomic — if images_referenced_by_datasets(paths) is
        non-empty, the whole call is a no-op (RemovalResult.blocked_by
        set, nothing else mutated, no save()); the Manager remains the
        sole authority on this, re-checking it here regardless of
        whatever the caller already verified, same principle as
        DatasetManager.delete()/is_referenced_by_training().

        Mission 066: persistence-first order — classification never
        touches the filesystem, only Workspace.images is mutated and
        saved first; every real Path.unlink() is attempted only after
        save() has actually succeeded. An empirical audit (see
        MISSION_066.md) showed the previous unlink-then-save order
        could permanently destroy a file while project.json, on a
        save() failure, kept referencing it — the exact inconsistency
        this order is designed to make impossible. If save() fails, the
        original Workspace.images list is restored verbatim (same
        Image objects, same order) and the exception re-raised — no
        file has been touched, so no partial/dirty state survives the
        failure. If save() succeeds, the logical removal is already
        durable; each deletable candidate's Path.unlink() is then
        attempted independently (never let one failure stop the
        others), and any that fails becomes an orphaned file on disk —
        preferable to a destroyed file with a dangling persisted
        reference, and reported back via
        RemovalResult.deletion_failed rather than rolled back (rolling
        Workspace.images back at this point would resurrect an already
        successfully persisted removal, the opposite of what a
        filesystem-only failure should do). A path resolving outside
        workspace_root, or already missing from disk, is classified
        reference_only exactly as before and never has unlink()
        attempted on it.
        """

        if self.current_workspace is None:
            return RemovalResult(deleted=[], reference_only=[], blocked_by={}, deletion_failed=[])

        blocked_by = self.images_referenced_by_datasets(paths)
        if blocked_by:
            return RemovalResult(deleted=[], reference_only=[], blocked_by=blocked_by, deletion_failed=[])

        workspace_root = self.current_workspace.root
        resolved_targets = {
            os.path.normcase(str(Path(path).resolve())) for path in paths
        }

        to_delete = []
        reference_only = []
        remaining_images = []

        for image in self.current_workspace.images:

            resolved_key = (
                os.path.normcase(str(Path(image.file_path).resolve()))
                if image.file_path else None
            )

            if resolved_key not in resolved_targets:
                remaining_images.append(image)
                continue

            candidate = Path(image.file_path)
            if WorkspaceStorage.is_inside(candidate, workspace_root) and candidate.exists():
                to_delete.append(image.file_path)
            else:
                reference_only.append(image.file_path)

        if not to_delete and not reference_only:
            return RemovalResult(deleted=[], reference_only=[], blocked_by={}, deletion_failed=[])

        original_images = self.current_workspace.images
        self.current_workspace.images = remaining_images

        try:
            self.save()
        except WorkspaceManagerError:
            self.current_workspace.images = original_images
            raise

        deleted = []
        deletion_failed = []
        for file_path in to_delete:
            try:
                Path(file_path).unlink()
                deleted.append(file_path)
            except OSError:
                deletion_failed.append(file_path)

        return RemovalResult(
            deleted=deleted, reference_only=reference_only, blocked_by={}, deletion_failed=deletion_failed
        )

    def _publish(self, event_name: str) -> None:

        if self._event_bus is None:
            return

        payload = (
            self.current_workspace.to_dict()
            if self.current_workspace is not None
            else None
        )

        self._event_bus.publish(event_name, payload)
