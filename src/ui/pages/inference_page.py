from pathlib import Path

from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QMessageBox,
)

from src.ui.generation_worker import GenerationWorker

# Mission 013: images produced from this page belong to Workspace.images
# (Mission 011 ownership model) — this subfolder is a plain runtime
# destination for ComfyUIEngine's download, not a new persisted field;
# Workspace/WorkspaceStorage are untouched.
GENERATED_IMAGES_SUBFOLDER = "outputs"


class InferencePage(QWidget):

    def __init__(self, generation_manager, workspace_manager):
        super().__init__()

        self._generation_manager = generation_manager
        self._workspace_manager = workspace_manager
        self._thread = None
        self._worker = None

        layout = QVBoxLayout(self)

        title = QLabel("Inference")
        title.setStyleSheet("font-size:24px;font-weight:bold;")

        layout.addWidget(title)

        self.generate_button = QPushButton("Générer")
        self.generate_button.clicked.connect(self._on_generate_clicked)

        layout.addWidget(self.generate_button)

        self.prompt = QTextEdit()

        self.prompt.setPlaceholderText("Prompt...")

        layout.addWidget(self.prompt)

    def _on_generate_clicked(self):

        prompt_text = self.prompt.toPlainText()

        if not prompt_text.strip():
            QMessageBox.warning(
                self,
                "Prompt vide",
                "Saisissez un prompt avant de générer."
            )
            return

        if not self._workspace_manager.opened:
            QMessageBox.warning(
                self,
                "Aucun projet ouvert",
                "Ouvrez ou créez un projet avant de générer."
            )
            return

        output_directory = str(
            Path(self._workspace_manager.current_workspace.root) / GENERATED_IMAGES_SUBFOLDER
        )

        self.generate_button.setEnabled(False)

        thread = QThread()
        worker = GenerationWorker(self._generation_manager, prompt_text, output_directory)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(self._on_generation_finished)
        worker.failed.connect(self._on_generation_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        # worker/thread are captured by value here (not re-read from
        # self._worker/self._thread when this fires, which may be much
        # later) — this is what makes it impossible for this cycle's
        # deferred cleanup to ever act on a newer cycle's objects, even
        # if the user starts a second generation before this callback
        # runs (see _cleanup_thread's docstring).
        thread.finished.connect(lambda: self._cleanup_thread(worker, thread))

        self._thread = thread
        self._worker = worker

        thread.start()

    def _on_generation_finished(self, path):

        # WorkspaceManager.add_images() runs here, on the Qt main
        # thread (this slot is invoked via a queued connection from the
        # worker's thread) — never from the worker itself, since
        # Workspace/WorkspaceManager are plain Python objects with no
        # thread-safety guarantee (Mission 013 architecture decision).
        self._workspace_manager.add_images([path])

        self.generate_button.setEnabled(True)

        QMessageBox.information(
            self,
            "Génération terminée",
            "Image générée avec succès."
        )

    def _on_generation_failed(self, message):

        self.generate_button.setEnabled(True)

        QMessageBox.critical(
            self,
            "Erreur de génération",
            message
        )

    def _cleanup_thread(self, worker, thread):
        """
        Runs once this specific cycle's thread has fully stopped
        (thread.finished). worker/thread are the exact objects created
        for this cycle, captured by value at connect() time in
        _on_generate_clicked() — never read from self._worker/
        self._thread here, so a second generation the user already
        started (whose objects now live in self._worker/self._thread)
        can never be torn down by this, older, callback.

        self._worker/self._thread are only reset to None if they still
        point at *this* cycle's objects — if a newer cycle has already
        replaced them, those newer references are left untouched.
        """
        worker.deleteLater()
        thread.deleteLater()

        if self._worker is worker:
            self._worker = None

        if self._thread is thread:
            self._thread = None

    def shutdown(self):
        """
        Called from MainWindow.closeEvent() so a generation in progress
        never leaves a dangling thread behind when the application
        closes (Mission 013 — minimal handling, no cancellation).
        """
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
