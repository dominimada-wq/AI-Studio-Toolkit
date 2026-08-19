from PySide6.QtWidgets import QListWidget


class Sidebar(QListWidget):

    def __init__(self):
        super().__init__()

        self.setFixedWidth(220)

        self.pages = [
            ("🏠 Dashboard", "dashboard"),
            ("🎭 Characters", "characters"),
            ("🖼 Images", "images"),
            ("📁 Datasets", "datasets"),
            ("🧠 Models", "models"),
            ("🧩 Workflows", "workflows"),
            ("🎯 LoRA", "lora"),
            ("📝 Prompts", "prompts"),
            ("🚀 Training", "training"),
            ("✨ Inference", "inference"),
            ("⚙ Settings", "settings"),
        ]

        for title, _ in self.pages:
            self.addItem(title)

    def page_name(self, index):
        if index < 0 or index >= len(self.pages):
            return None
        return self.pages[index][1]

    def select_page(self, name):
        # Mission 033: reverse lookup of page_name() above, so callers
        # (MainWindow) never hardcode a numeric row index — self.pages
        # stays the single source of truth for the Sidebar/stack
        # positional alignment.
        for index, (_, page_name) in enumerate(self.pages):
            if page_name == name:
                self.setCurrentRow(index)
                return True
        return False