from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class SettingsPage(QWidget):

    def __init__(self, settings_manager):
        super().__init__()

        self.settings_manager = settings_manager

        layout = QVBoxLayout(self)

        title = QLabel("Settings")
        title.setStyleSheet("font-size:24px;font-weight:bold;")
        layout.addWidget(title)

        form = QFormLayout()

        self.theme_edit = QLineEdit()
        self.language_edit = QLineEdit()

        form.addRow("Thème :", self.theme_edit)
        form.addRow("Langue :", self.language_edit)

        layout.addLayout(form)

        self.save_button = QPushButton("Enregistrer")
        self.save_button.clicked.connect(self.save_settings)

        layout.addWidget(self.save_button)

        hint = QLabel(
            "Ces préférences sont enregistrées dans le Workspace. "
            "Leur application à l'interface sera prise en charge ultérieurement."
        )

        layout.addWidget(hint)

        layout.addStretch()

        self.theme_edit.setEnabled(False)
        self.language_edit.setEnabled(False)
        self.save_button.setEnabled(False)

    def save_settings(self):

        self.settings_manager.update(
            theme=self.theme_edit.text(),
            language=self.language_edit.text(),
        )

    def update_settings(self, payload=None):

        opened = payload is not None

        self.theme_edit.setEnabled(opened)
        self.language_edit.setEnabled(opened)
        self.save_button.setEnabled(opened)

        settings = self.settings_manager.settings

        self.theme_edit.setText(settings.theme)
        self.language_edit.setText(settings.language)
