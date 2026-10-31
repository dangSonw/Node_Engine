"""Keyboard-accessible search shared by graph and editor commands."""
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel


class SearchDialog(QDialog):
    def __init__(self, items, title, parent, *, hint='', empty_text='No matches. Try another search.'):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, 420)
        self.items = items
        self.result_value = None
        layout = QVBoxLayout(self)
        if hint:
            label = QLabel(hint)
            label.setWordWrap(True)
            layout.addWidget(label)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Type to search…')
        self.search.setAccessibleName(title + ' search')
        self.list = QListWidget()
        self.list.setAccessibleName(title + ' results')
        self.empty = QLabel(empty_text)
        self.empty.setWordWrap(True)
        layout.addWidget(self.search)
        layout.addWidget(self.empty)
        layout.addWidget(self.list)
        self.search.textChanged.connect(self.filter)
        self.list.itemActivated.connect(self.choose)
        self.search.returnPressed.connect(lambda: self.choose(self.list.currentItem()))
        self.search.installEventFilter(self)
        self.filter('')
        self.search.setFocus()

    def filter(self, query):
        self.list.clear()
        for label, value in self.items:
            if all(word in label.casefold() for word in query.casefold().split()):
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, value)
                self.list.addItem(item)
        self.list.setCurrentRow(0)
        self.empty.setVisible(self.list.count() == 0)

    def eventFilter(self, watched, event):
        if watched is self.search and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                delta = 1 if event.key() == Qt.Key.Key_Down else -1
                self.list.setCurrentRow(max(0, min(self.list.count()-1, self.list.currentRow()+delta)))
                return True
        return super().eventFilter(watched, event)

    def choose(self, item):
        if item:
            self.result_value = item.data(Qt.ItemDataRole.UserRole)
            self.accept()
