"""
GenerationManager coordinates a single image generation request against
ComfyUIEngine. Deliberately Qt-free (Mission 013 architecture audit): it
exposes one blocking call, meant to run off the Qt main thread by a
caller it knows nothing about — no QObject, no signal, no thread
handling here. It also knows nothing about Workspace/Domain: it returns
the generated file's path and nothing else, leaving the decision of
what to do with that path (Workspace.images vs anywhere else) entirely
to its caller.

No Domain collection, no active_id, no history, no queue, no Job — a
single transient `busy` flag is the only state, preventing a second
concurrent generation, the same "runtime-only, never persisted" shape
already used by every other Manager's active_*_id, just a bool instead
of an id.
"""

from typing import List, NamedTuple, Optional, Union

from src.engines.comfyui_engine import (
    DEMO_CHECKPOINT_NAME,
    ComfyUIEngine,
    ComfyUIEngineError,
)

# Mission 056: the only reference role with a real generation mechanism
# today — build_img2img_workflow() (Mission 023), unchanged. Deliberately
# the sole role constant in this codebase: future roles (identity,
# clothing, environment, style, a more specialized pose/composition...)
# each require their own dedicated engine mechanism (IP-Adapter,
# ControlNet, ...) that does not exist yet, so they are not declared as
# constants here — doing so now would be a dead taxonomy nothing can
# use. A future mission adding a real second mechanism adds its own
# constant then, alongside its own branch in generate() below.
REFERENCE_ROLE_POSE_COMPOSITION = "pose_composition"


class Reference(NamedTuple):
    """
    A single typed reference image for a generation request (Mission
    056) — colocated here rather than in src/domain/ because it is
    never persisted, has no id, and belongs to no Manager-owned
    collection (same placement rationale as CharacterContext in
    prompt_assistant_manager.py). Strictly minimal: a path and an
    explicit role, nothing else — no strength, weight, mask, engine
    config, or provider field. Those belong to a future adapter, only
    if a real need for them appears. A role's actual generation
    mechanism is resolved entirely inside GenerationManager.generate()
    below; ComfyUIEngine/comfyui_workflows.py never learn about roles.
    """

    path: str
    role: str


class GenerationError(Exception):
    """
    Raised by GenerationManager on any failure to fulfil a generation
    request — an empty prompt, a generation already in progress, or a
    failure surfaced by ComfyUIEngine (ComfyUIEngineError, or a plain
    OSError from a local filesystem failure — see
    ComfyUIEngine.download_output()'s own documented behavior).
    Normalizes both into a single Manager-level exception type, the
    same pattern WorkspaceManagerError already uses to wrap
    WorkspaceStorageError.
    """


class GenerationManager:

    def __init__(
        self,
        comfyui_engine: ComfyUIEngine,
        checkpoint_name: str = DEMO_CHECKPOINT_NAME,
        lora_name: str = "",
        lora_strength: float = 1.0,
    ):
        self._comfyui_engine = comfyui_engine
        self._checkpoint_name = checkpoint_name
        # Mission 059: same "read once at construction, no hot reload"
        # contract already established for checkpoint_name — see
        # MainWindow's own composition-root comment.
        self._lora_name = lora_name
        self._lora_strength = lora_strength
        self._busy = False

    @property
    def busy(self) -> bool:
        return self._busy

    def generate(
        self,
        prompt_text: str,
        output_directory: str,
        reference_images: Optional[List[Union[str, Reference]]] = None,
        reference_strength: Optional[float] = None,
    ) -> str:
        """
        Blocking call — delegates to ComfyUIEngine.generate_image().
        Returns the generated file's local path. Raises GenerationError
        if prompt_text is empty/whitespace-only, if more than one
        reference image is given, if the single reference's role has
        no generation mechanism, if a generation is already in
        progress, or if ComfyUIEngine fails.

        lora_name/lora_strength (Mission 059) are set once at
        construction, like checkpoint_name — no per-call parameter,
        same "no hot reload" contract already established for the
        checkpoint. Forwarded to every call regardless of
        reference_images, entirely independent of that mechanism.

        reference_images is an optional 0..N collection — the
        collection itself is designed for 0..N typed references
        (Mission 056), but the generation capacity actually delivered
        stays 0..1 *actionable* reference: more than one element is
        rejected explicitly (see below), never silently merged or
        reduced to reference_images[0].

        Each element is either a plain str (a legacy local file path)
        or a Reference(path, role) (Mission 056). A plain str is
        normalized in-memory to role=REFERENCE_ROLE_POSE_COMPOSITION —
        existing callers passing bare paths keep working unchanged,
        with byte-for-byte identical behavior to before this mission.
        A role other than REFERENCE_ROLE_POSE_COMPOSITION is rejected
        immediately, before any upload — there is no silent fallback
        to the one working mechanism for a role it was never designed
        for.

        None/empty means no upload call happens at all and the txt2img
        path stays byte-for-byte identical to before Mission 021/022/
        023 existed. The one actionable path is uploaded via
        ComfyUIEngine.upload_image() (Mission 021) and the dict it
        returns is forwarded, unexamined, to
        ComfyUIEngine.generate_image()'s reference_image parameter
        (Mission 023) — this method never inspects that dict's keys,
        constructs a node input, or otherwise knows anything about
        ComfyUI's JSON graph format; that knowledge stays in
        src/engines/workflows/. More than one reference is rejected
        before any upload is attempted (fail-fast on the collection
        itself) — the multi-reference collection genuinely exists
        (Reference/reference_images accept it structurally), only
        simultaneous multi-reference *generation* does not exist yet;
        a future mechanism able to use several references would lift
        this specific check without changing reference_images' shape
        anywhere else in the call chain.

        reference_strength (Mission 024) is a generic 0.0-1.0 concept —
        this method never imports or references DEFAULT_IMG2IMG_DENOISE.
        It is only forwarded (as generate_image()'s denoise= keyword,
        the one point where this concept's ComfyUI-native name is used)
        when a reference is actually present and a value was actually
        given; otherwise generate_image()/build_img2img_workflow() fall
        back to their own existing default unchanged. This is what
        guarantees, structurally rather than conventionally, that the
        historical default behavior (Mission 023) is never altered.
        """

        if not prompt_text or not prompt_text.strip():
            raise GenerationError("Prompt is empty")

        if reference_images and len(reference_images) > 1:
            raise GenerationError(
                "Multiple reference images are represented "
                f"({len(reference_images)} received), but simultaneous "
                "multi-reference generation is not supported yet"
            )

        reference_path = None
        if reference_images:
            candidate = reference_images[0]
            if isinstance(candidate, Reference):
                role, reference_path = candidate.role, candidate.path
            else:
                role, reference_path = REFERENCE_ROLE_POSE_COMPOSITION, candidate
            if role != REFERENCE_ROLE_POSE_COMPOSITION:
                raise GenerationError(
                    f"Reference role {role!r} has no generation mechanism yet "
                    f"(only {REFERENCE_ROLE_POSE_COMPOSITION!r} is supported)"
                )

        if self._busy:
            raise GenerationError("A generation is already in progress")

        self._busy = True
        try:
            reference_image = None
            extra_kwargs = {}
            if reference_path is not None:
                reference_image = self._comfyui_engine.upload_image(reference_path)
                if reference_strength is not None:
                    extra_kwargs["denoise"] = reference_strength

            return self._comfyui_engine.generate_image(
                prompt_text,
                output_directory,
                checkpoint_name=self._checkpoint_name,
                reference_image=reference_image,
                lora_name=self._lora_name,
                lora_strength=self._lora_strength,
                **extra_kwargs,
            )
        except ComfyUIEngineError as error:
            raise GenerationError(str(error)) from error
        except OSError as error:
            raise GenerationError(str(error)) from error
        finally:
            self._busy = False
