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
            ("🎯 LoRA", "lora"),
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