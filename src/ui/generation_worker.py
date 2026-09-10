"""
GenerationWorker runs GenerationManager.generate() off the Qt main
thread. It is the only piece of this vertical that knows about Qt
threading — GenerationManager itself stays Qt-free (Mission 013
architecture audit). Owned by whichever Page starts a generation
(InferencePage), moved into a QThread via moveToThread(), and driven by
QThread.started -> run().

Both success and failure are translated into signals; no exception ever
crosses the thread boundary uncaught — GenerationManager already
normalizes ComfyUIEngine's own failures into GenerationError, and the
broad except below is a last-resort safety net for anything else.
"""

from PySide6.QtCore import QObject, Signal

from src.managers.generation_manager import GenerationError, GenerationManager


class GenerationWorker(QObject):

    finished = Signal(str)  # generated file's local path
    failed = Signal(str)  # error message

    def __init__(
        self,
        generation_manager: GenerationManager,
        prompt_text: str,
        output_directory: str,
        reference_images=None,
        reference_strength=None,
        width=None,
        height=None,
        steps=None,
        cfg=None,
        sampler_name=None,
        scheduler=None,
        seed=None,
        negative_prompt=None,
        lora_name=None,
        lora_strength=None,
        engine=None,
        checkpoint_name=None,
    ):
        super().__init__()
        self._generation_manager = generation_manager
        self._prompt_text = prompt_text
        self._output_directory = output_directory
        # Mission 022: copied defensively (not the same list object the
        # caller may still hold) so nothing InferencePage does to its
        # own selection state after this point — including clearing or
        # replacing it — can ever reach this already-launched cycle.
        # InferencePage already builds a fresh list per call, so this
        # copy is a structural guarantee rather than one resting on the
        # caller's discipline, consistent with how worker/thread are
        # already captured by value in InferencePage._cleanup_thread.
        self._reference_images = list(reference_images) if reference_images else []
        # Mission 024: a plain float is immutable — captured here at
        # construction time (before moveToThread()/thread.start(), same
        # as reference_images above), no defensive copy needed beyond
        # that capture itself.
        self._reference_strength = reference_strength
        # Mission 096: same capture-at-construction-time rationale as
        # reference_strength above — all immutable scalars, no defensive
        # copy needed. Each stays None here only when InferencePage
        # itself omits it (never expected in production: InferencePage
        # always resolves every one of these before constructing this
        # worker); None is forwarded straight through to
        # GenerationManager.generate(), which then falls back to its own
        # DEFAULT_* parameter values — this class never hardcodes a
        # generation-parameter default itself.
        self._width = width
        self._height = height
        self._steps = steps
        self._cfg = cfg
        self._sampler_name = sampler_name
        self._scheduler = scheduler
        self._seed = seed
        self._negative_prompt = negative_prompt
        # Mission 102: same capture-at-construction-time rationale as
        # every other optional parameter above. lora_name="" is a
        # meaningful, distinct value from None (explicit "no LoRA" vs.
        # "no override at all") — the `is not None` check below forwards
        # it into kwargs like any other non-None value, never treating
        # it as falsy/absent.
        self._lora_name = lora_name
        self._lora_strength = lora_strength
        # Mission 108: same capture-at-construction-time rationale as
        # every other optional parameter above. `engine` is a plain
        # ComfyUIEngine/ForgeEngine instance (duck-typed, never
        # isinstance-checked) forwarded unexamined to
        # GenerationManager.generate() — this class knows nothing about
        # which concrete engine type it is.
        self._engine = engine
        self._checkpoint_name = checkpoint_name

    def run(self) -> None:
        try:
            kwargs = {}
            if self._width is not None:
                kwargs["width"] = self._width
            if self._height is not None:
                kwargs["height"] = self._height
            if self._steps is not None:
                kwargs["steps"] = self._steps
            if self._cfg is not None:
                kwargs["cfg"] = self._cfg
            if self._sampler_name is not None:
                kwargs["sampler_name"] = self._sampler_name
            if self._scheduler is not None:
                kwargs["scheduler"] = self._scheduler
            if self._seed is not None:
                kwargs["seed"] = self._seed
            if self._negative_prompt is not None:
                kwargs["negative_prompt"] = self._negative_prompt
            if self._lora_name is not None:
                kwargs["lora_name"] = self._lora_name
            if self._lora_strength is not None:
                kwargs["lora_strength"] = self._lora_strength
            if self._engine is not None:
                kwargs["engine"] = self._engine
            if self._checkpoint_name is not None:
                kwargs["checkpoint_name"] = self._checkpoint_name

            path = self._generation_manager.generate(
                self._prompt_text,
                self._output_directory,
                reference_images=self._reference_images,
                reference_strength=self._reference_strength,
                **kwargs,
            )
        except GenerationError as error:
            self.failed.emit(str(error))
            return
        except Exception as error:  # last-resort safety net — must never cross the thread boundary
            self.failed.emit(str(error))
            return

        self.finished.emit(path)
