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

    def run(self) -> None:
        try:
            path = self._generation_manager.generate(
                self._prompt_text,
                self._output_directory,
                reference_images=self._reference_images,
            )
        except GenerationError as error:
            self.failed.emit(str(error))
            return
        except Exception as error:  # last-resort safety net — must never cross the thread boundary
            self.failed.emit(str(error))
            return

        self.finished.emit(path)
