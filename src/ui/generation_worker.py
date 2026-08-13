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
    ):
        super().__init__()
        self._generation_manager = generation_manager
        self._prompt_text = prompt_text
        self._output_directory = output_directory

    def run(self) -> None:
        try:
            path = self._generation_manager.generate(self._prompt_text, self._output_directory)
        except GenerationError as error:
            self.failed.emit(str(error))
            return
        except Exception as error:  # last-resort safety net — must never cross the thread boundary
            self.failed.emit(str(error))
            return

        self.finished.emit(path)
