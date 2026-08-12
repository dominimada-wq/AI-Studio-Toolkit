from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class SettingsPage(QWidget):

    def __init__(self, settings_manager, application_settings_manager):
        super().__init__()

        self.settings_manager = settings_manager
        self.application_settings_manager = application_settings_manager

        layout = QVBoxLayout(self)

        title = QLabel("Settings")
        title.setStyleSheet("font-size:24px;font-weight:bold;")
        layout.addWidget(title)

        # --- Workspace section ---

        workspace_title = QLabel("Workspace")
        workspace_title.setStyleSheet("font-size:16px;font-weight:bold;")
        layout.addWidget(workspace_title)

        workspace_form = QFormLayout()

        self.theme_edit = QLineEdit()
        self.language_edit = QLineEdit()

        workspace_form.addRow("Thème :", self.theme_edit)
        workspace_form.addRow("Langue :", self.language_edit)

        layout.addLayout(workspace_form)

        self.save_button = QPushButton("Enregistrer")
        self.save_button.clicked.connect(self.save_settings)

        layout.addWidget(self.save_button)

        workspace_hint = QLabel(
            "Ces préférences sont enregistrées dans le Workspace. "
            "Leur application à l'interface sera prise en charge ultérieurement."
        )

        layout.addWidget(workspace_hint)

        # --- Application section ---

        application_title = QLabel("Application")
        application_title.setStyleSheet("font-size:16px;font-weight:bold;")
        layout.addWidget(application_title)

        application_form = QFormLayout()

        self.python_path_edit = QLineEdit()
        self.comfyui_path_edit = QLineEdit()
        self.onetrainer_path_edit = QLineEdit()

        application_form.addRow("Python :", self.python_path_edit)
        application_form.addRow("ComfyUI :", self.comfyui_path_edit)
        application_form.addRow("OneTrainer :", self.onetrainer_path_edit)

        layout.addLayout(application_form)

        self.application_save_button = QPushButton("Enregistrer")
        self.application_save_button.clicked.connect(self.save_application_settings)

        layout.addWidget(self.application_save_button)

        application_hint = QLabel(
            "Ces chemins sont propres à cette installation et indépendants du Workspace."
        )

        layout.addWidget(application_hint)

        layout.addStretch()

        self.theme_edit.setEnabled(False)
        self.language_edit.setEnabled(False)
        self.save_button.setEnabled(False)

        # Application Settings exist independently of any Workspace and
        # are already loaded by the time this Page is constructed — this
        # populates the section immediately, it is not a reactive refresh.
        self.update_application_settings()

    def save_settings(self):

        self.settings_manager.update(
            theme=self.theme_edit.text(),
            language=self.language_edit.text(),
        )

    def save_application_settings(self):

        self.application_settings_manager.update(
            python_path=self.python_path_edit.text(),
            comfyui_path=self.comfyui_path_edit.text(),
            onetrainer_path=self.onetrainer_path_edit.text(),
        )

    def update_settings(self, payload=None):

        opened = payload is not None

        self.theme_edit.setEnabled(opened)
        self.language_edit.setEnabled(opened)
        self.save_button.setEnabled(opened)

        settings = self.settings_manager.settings

        self.theme_edit.setText(settings.theme)
        self.language_edit.setText(settings.language)

    def update_application_settings(self, payload=None):

        settings = self.application_settings_manager.settings

        self.python_path_edit.setText(settings.python_path)
        self.comfyui_path_edit.setText(settings.comfyui_path)
        self.onetrainer_path_edit.setText(settings.onetrainer_path)
