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

from typing import List, Optional

from src.engines.comfyui_engine import (
    DEMO_CHECKPOINT_NAME,
    ComfyUIEngine,
    ComfyUIEngineError,
)


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
    ):
        self._comfyui_engine = comfyui_engine
        self._checkpoint_name = checkpoint_name
        self._busy = False

    @property
    def busy(self) -> bool:
        return self._busy

    def generate(
        self,
        prompt_text: str,
        output_directory: str,
        reference_images: Optional[List[str]] = None,
    ) -> str:
        """
        Blocking call — delegates to ComfyUIEngine.generate_image().
        Returns the generated file's local path. Raises GenerationError
        if prompt_text is empty/whitespace-only, if a generation is
        already in progress, or if ComfyUIEngine fails.

        Mission 022: reference_images is an optional 0..N collection of
        local file paths, uploaded via ComfyUIEngine.upload_image()
        (Mission 021) before generate_image() runs — one call per path,
        in order, stopping immediately at the first failing upload
        (fail-fast: generate_image() is never reached if any upload
        fails). None/empty means no upload call happens at all, so the
        txt2img path stays byte-for-byte identical to before this
        parameter existed. The dict each upload_image() call returns is
        deliberately not kept — nothing consumes it yet; no workflow
        node references an uploaded image in this mission.
        """

        if not prompt_text or not prompt_text.strip():
            raise GenerationError("Prompt is empty")

        if self._busy:
            raise GenerationError("A generation is already in progress")

        self._busy = True
        try:
            for reference_path in (reference_images or []):
                self._comfyui_engine.upload_image(reference_path)

            return self._comfyui_engine.generate_image(
                prompt_text,
                output_directory,
                checkpoint_name=self._checkpoint_name,
            )
        except ComfyUIEngineError as error:
            raise GenerationError(str(error)) from error
        except OSError as error:
            raise GenerationError(str(error)) from error
        finally:
            self._busy = False
