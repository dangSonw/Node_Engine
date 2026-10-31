"""Read, edit and preview Markdown inside the currently opened project."""
from pathlib import Path
from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QKeySequence, QShortcut, QDesktopServices, QTextDocument, QTextCursor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget, QListWidgetItem,
    QLineEdit, QPlainTextEdit, QTextBrowser, QPushButton, QLabel, QInputDialog, QMessageBox,
)
from editor.core.document import write_text_if_changed
from editor.core.project_markdown import markdown_path, markdown_files
from .theme import stylesheet


class LocalMarkdownBrowser(QTextBrowser):
    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root = Path(root).resolve()
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setStyleSheet('QTextBrowser {background:#10141b;color:#f0f3f9;border:0;padding:12px;font-size:14px;}')
        self.document().setDefaultStyleSheet('th,td {padding:6px;} h1 {color:#5dd6e8;} h2 {color:#a78bfa;} a {color:#5dd6e8;}')

    def loadResource(self, resource_type, url):
        resolved = self.document().baseUrl().resolved(url)
        if resource_type == QTextDocument.ResourceType.ImageResource:
            if not resolved.isLocalFile() or not Path(resolved.toLocalFile()).resolve().is_relative_to(self.root):
                return None
        return super().loadResource(resource_type, url)

    def fit_images(self):
        document = self.document()
        block = document.begin()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid() and fragment.charFormat().isImageFormat():
                    fmt = fragment.charFormat().toImageFormat()
                    image = document.resource(QTextDocument.ResourceType.ImageResource, document.baseUrl().resolved(QUrl(fmt.name())))
                    if hasattr(image, 'width') and image.width() > 0:
                        width = min(image.width(), max(80, self.viewport().width()-40))
                        fmt.setWidth(width)
                        fmt.setHeight(width*image.height()/image.width())
                        cursor = QTextCursor(document)
                        cursor.setPosition(fragment.position())
                        cursor.setPosition(fragment.position()+fragment.length(), QTextCursor.MoveMode.KeepAnchor)
                        cursor.setCharFormat(fmt)
                iterator += 1
            block = block.next()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.fit_images)


class ProjectMarkdownDialog(QDialog):
    def __init__(self, project_path, parent=None):
        super().__init__(parent)
        self.root = Path(project_path).resolve().parent
        self.current_path = None
        self.loaded_bytes = None
        self.setObjectName('ProjectMarkdownDialog')
        self.setStyleSheet(stylesheet())
        self.setWindowTitle('Project Markdown — ' + self.root.name)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint)
        self.resize(1320, 860)
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.path_label = QLabel('Chọn hoặc tạo tài liệu .md')
        self.path_label.setTextFormat(Qt.TextFormat.PlainText)
        bar.addWidget(self.path_label, 1)
        for label, callback in [('New .md', self.new_document), ('Save', self.save_document), ('Close', self.close)]:
            button = QPushButton(label)
            button.setAutoDefault(False)
            button.clicked.connect(callback)
            bar.addWidget(button)
        layout.addLayout(bar)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Tìm file Markdown trong project…')
        self.search.setAccessibleName('Search project Markdown')
        layout.addWidget(self.search)
        split = QSplitter()
        self.files = QListWidget()
        self.files.setAccessibleName('Project Markdown files')
        self.editor = QPlainTextEdit()
        self.editor.setAccessibleName('Markdown source')
        self.editor.setPlaceholderText('Viết Markdown ở đây…')
        self.editor.setEnabled(False)
        self.preview = LocalMarkdownBrowser(self.root)
        self.preview.setAccessibleName('Markdown preview')
        split.addWidget(self.files)
        split.addWidget(self.editor)
        split.addWidget(self.preview)
        split.setSizes([220, 480, 620])
        layout.addWidget(split, 1)
        self.status = QLabel('Nguồn Markdown ở giữa · Preview bên phải · Ctrl+S lưu file .md · Ảnh lấy từ đường dẫn tương đối trong project')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(180)
        self.timer.timeout.connect(self.update_preview)
        self.editor.textChanged.connect(lambda: self.timer.start())
        self.editor.document().modificationChanged.connect(self.update_title)
        self.search.textChanged.connect(self.filter_files)
        self.files.itemActivated.connect(self.choose_file)
        self.files.itemClicked.connect(self.choose_file)
        self.preview.anchorClicked.connect(self.follow_link)
        save = QShortcut(QKeySequence('Ctrl+S'), self)
        save.activated.connect(self.save_document)
        self.refresh_files()
        paths = markdown_files(self.root)
        if paths:
            self.open_document(paths[0])

    def update_title(self, *_):
        relative = self.current_path.relative_to(self.root).as_posix() if self.current_path else 'Chọn tài liệu .md'
        self.path_label.setText(relative + ('  * chưa lưu' if self.editor.document().isModified() else ''))

    def refresh_files(self):
        self.files.clear()
        for path in markdown_files(self.root):
            item = QListWidgetItem(path.relative_to(self.root).as_posix())
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.files.addItem(item)
        self.filter_files(self.search.text())

    def filter_files(self, query):
        for index in range(self.files.count()):
            item = self.files.item(index)
            item.setHidden(query.casefold() not in item.text().casefold())

    def choose_file(self, item):
        self.open_document(item.data(Qt.ItemDataRole.UserRole))

    def confirm_unsaved(self):
        if not self.editor.document().isModified():
            return True
        answer = QMessageBox.question(self, 'Markdown chưa lưu', 'Lưu thay đổi trước khi đóng hoặc chuyển tài liệu?',
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        return self.save_document() if answer == QMessageBox.StandardButton.Save else True

    def open_document(self, relative, *, confirm=True):
        try:
            path = markdown_path(self.root, relative)
            if path == self.current_path:
                return True
            if confirm and not self.confirm_unsaved():
                return False
            data = path.read_bytes()
            text = data.decode('utf-8-sig')
            self.current_path, self.loaded_bytes = path, data
            self.editor.setEnabled(True)
            self.editor.setPlainText(text)
            self.editor.document().setModified(False)
            self.update_title()
            self.update_preview()
            return True
        except (OSError, UnicodeError, ValueError) as error:
            self.status.setText('Không mở được: ' + str(error))
            return False

    def new_document(self):
        if not self.confirm_unsaved():
            return
        name, okay = QInputDialog.getText(self, 'New Markdown', 'Đường dẫn .md trong project:', text='docs/notes.md')
        if not okay:
            return
        try:
            path = markdown_path(self.root, name.strip())
            if path.exists():
                raise ValueError('File đã tồn tại. Chọn trong danh sách để sửa.')
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('x',encoding='utf-8',newline='\n') as file:
                file.write('# ' + path.stem + '\n\n')
            self.refresh_files()
            self.open_document(path, confirm=False)
        except (OSError, ValueError) as error:
            self.status.setText('Không tạo được: ' + str(error))

    def save_document(self):
        if self.current_path is None:
            return False
        try:
            path = markdown_path(self.root, self.current_path)
            if not path.exists() or path.read_bytes() != self.loaded_bytes:
                raise ValueError('File trên đĩa đã thay đổi hoặc bị xóa. Sao chép nội dung đang sửa rồi mở lại để tránh ghi đè.')
            write_text_if_changed(path, self.editor.toPlainText())
            self.loaded_bytes = path.read_bytes()
            self.editor.document().setModified(False)
            self.update_title()
            self.status.setText('Đã lưu ' + path.relative_to(self.root).as_posix())
            return True
        except (OSError, ValueError) as error:
            self.status.setText('Không lưu được: ' + str(error))
            return False

    def update_preview(self):
        if self.current_path:
            scroll = self.preview.verticalScrollBar().value()
            self.preview.document().setBaseUrl(QUrl.fromLocalFile(str(self.current_path.parent) + '/'))
            self.preview.setSearchPaths([str(self.current_path.parent)])
            self.preview.setMarkdown(self.editor.toPlainText())
            self.preview.fit_images()
            self.preview.verticalScrollBar().setValue(scroll)

    def follow_link(self, url):
        if url.scheme() == 'node' and url.path().isdigit() and hasattr(self.parent(), 'adapter'):
            from .node_help import NodeHelpDialog
            registry = self.parent().adapter.registry
            if int(url.path()) in registry.nodes:
                NodeHelpDialog(registry, self, spec=registry[int(url.path())]).show()
        elif url.scheme() in ('https', 'http'):
            QDesktopServices.openUrl(url)
        elif not url.scheme() or url.isLocalFile():
            resolved = self.preview.document().baseUrl().resolved(url)
            if url.fragment() and not url.path():
                self.preview.scrollToAnchor(url.fragment())
            elif resolved.isLocalFile() and self.open_document(resolved.toLocalFile()) and url.fragment():
                self.preview.scrollToAnchor(url.fragment())

    def closeEvent(self, event):
        if self.confirm_unsaved():
            event.accept()
        else:
            event.ignore()

    def reject(self):
        if self.confirm_unsaved():
            super().reject()
