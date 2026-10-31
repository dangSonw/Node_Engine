"""Separate code view/editor for a selected graph node."""

import re

from PySide6.QtCore import QRegularExpression, Qt, QRect, QSize, Signal, QEvent
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QPainter, QTextCursor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from editor.core.node_code import (
    default_node_code, embedded_code_for, runtime_source_excerpt,
    validate_embedded_code, CALL_MARKER,
)


class LineNumbers(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.number_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_numbers(event)


class CodeEditor(QPlainTextEdit):
    """Native Qt text editing, with line numbers and four-space indentation."""
    save_requested=Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.numbers = LineNumbers(self)
        self.blockCountChanged.connect(self.update_number_width)
        self.updateRequest.connect(self.update_numbers)
        self.update_number_width()

    def number_width(self):
        return 14 + self.fontMetrics().horizontalAdvance('9') * len(str(max(1, self.blockCount())))

    def update_number_width(self, *_):
        self.setViewportMargins(self.number_width(), 0, 0, 0)

    def update_numbers(self, rect, delta):
        if delta:
            self.numbers.scroll(0, delta)
        else:
            self.numbers.update(0, rect.y(), self.numbers.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_number_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        rect = self.contentsRect()
        self.numbers.setGeometry(QRect(rect.left(), rect.top(), self.number_width(), rect.height()))

    def paint_numbers(self, event):
        painter = QPainter(self.numbers)
        painter.fillRect(event.rect(), self.palette().alternateBase())
        painter.setPen(self.palette().text().color())
        painter.setFont(self.font())
        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        while block.isValid() and top <= event.rect().bottom():
            height = round(self.blockBoundingRect(block).height())
            if block.isVisible() and top + height >= event.rect().top():
                painter.drawText(0, top, self.numbers.width() - 6, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, str(block.blockNumber() + 1))
            top += height
            block = block.next()

    def event(self,event):
        if event.type()==QEvent.Type.ShortcutOverride and event.matches(QKeySequence.StandardKey.Save):
            event.accept(); return True
        return super().event(event)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Save):
            self.save_requested.emit(); event.accept(); return
        plain = event.modifiers() in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ShiftModifier)
        if not self.isReadOnly() and plain and event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            cursor = self.textCursor()
            unindent = event.key() == Qt.Key.Key_Backtab or bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            if not cursor.hasSelection() and not unindent:
                cursor.insertText(' ' * (4 - cursor.positionInBlock() % 4))
            else:
                first = self.document().findBlock(cursor.selectionStart()).blockNumber()
                last = self.document().findBlock(max(cursor.selectionStart(), cursor.selectionEnd() - 1)).blockNumber()
                cursor.beginEditBlock()
                for number in range(last, first - 1, -1):
                    block = self.document().findBlockByNumber(number)
                    cursor.setPosition(block.position())
                    if unindent:
                        count = 1 if block.text().startswith('\t') else min(4, len(block.text()) - len(block.text().lstrip(' ')))
                        cursor.setPosition(block.position() + count, QTextCursor.MoveMode.KeepAnchor)
                        cursor.removeSelectedText()
                    else:
                        cursor.insertText('    ')
                cursor.endEditBlock()
            event.accept()
            return
        if not self.isReadOnly() and plain and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            prefix = self.textCursor().block().text()[:self.textCursor().positionInBlock()]
            indentation = re.match(r'[ \t]*', prefix)[0] + ('    ' if prefix.rstrip().endswith('{') else '')
            cursor = self.textCursor()
            cursor.beginEditBlock()
            cursor.insertText('\n' + indentation)
            cursor.endEditBlock()
            self.setTextCursor(cursor)
            return
        super().keyPressEvent(event)

    def go_to_line(self, line, column=1):
        block = self.document().findBlockByNumber(max(0, min(self.blockCount() - 1, line - 1)))
        cursor = QTextCursor(block)
        prefix = block.text().encode('utf-8')[:max(0, column - 1)].decode('utf-8', errors='ignore')
        offset = len(prefix.encode('utf-16-le')) // 2
        cursor.setPosition(block.position() + min(offset, max(0, block.length() - 1)))
        self.setTextCursor(cursor)
        self.centerCursor()
        self.setFocus()


class CppHighlighter(QSyntaxHighlighter):
    """Small dependency-free highlighter suitable for the embedded editor."""

    def __init__(self, document):
        super().__init__(document)
        self.rules = []
        keyword = QTextCharFormat(); keyword.setForeground(QColor("#C9A7FF")); keyword.setFontWeight(QFont.Weight.Bold)
        type_format = QTextCharFormat(); type_format.setForeground(QColor("#72D9E8"))
        number = QTextCharFormat(); number.setForeground(QColor("#E8C46A"))
        comment = QTextCharFormat(); comment.setForeground(QColor("#71809A")); comment.setFontItalic(True)
        string = QTextCharFormat(); string.setForeground(QColor("#9DDBA1"))
        for word in ("auto", "const", "if", "else", "for", "while", "return", "true", "false", "nullptr"):
            self.rules.append((QRegularExpression(rf"\b{word}\b"), keyword))
        for word in ("rt", "std", "Ctx", "EntityRef", "Vec2", "Vec3", "Vec4", "Json"):
            self.rules.append((QRegularExpression(rf"\b{word}\b"), type_format))
        self.rules += [
            (QRegularExpression(r"\b[0-9]+(?:\.[0-9]+)?\b"), number),
            (QRegularExpression(r"//[^\n]*"), comment),
            (QRegularExpression(r'"[^"\\]*(?:\\.[^"\\]*)*"'), string),
        ]

    def highlightBlock(self, text):
        for expression, format_ in self.rules:
            match = expression.match(text)
            while match.hasMatch():
                self.setFormat(match.capturedStart(), match.capturedLength(), format_)
                match = expression.match(text, match.capturedStart() + match.capturedLength())


class NodeCodeDialog(QDialog):
    def __init__(self, spec, node, parent=None, *, diagnostic=None, generated_code=None):
        super().__init__(parent)
        self.spec = spec
        self.node = node
        self.result_code = None
        text, self.editable = embedded_code_for(node, spec)
        self.default = CALL_MARKER if self.editable else default_node_code(spec)
        self.setWindowTitle(f"Node Code · {spec.name}")
        self.resize(820, 620)

        layout = QVBoxLayout(self)
        heading = QLabel(f"<b>{spec.name}</b>  ·  node {node.get_property('stable_id')}")
        heading.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(heading)
        hint = QLabel(
            "C++ integration hook. Use ctx and read-only input_0, input_1, … in port order. "
            "Place {{call}} once to run the generated call; without it the call runs after your code. "
            "For nodes with outputs, result holds the return value after {{call}}. Build checks C++ types."
            if self.editable else
            "This node is shown as generated code. Only action nodes currently accept an embedded C++ hook."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        tabs = QTabWidget()
        tabs.setObjectName("NodeCodeTabs")
        self.editor = CodeEditor()
        self.editor.setObjectName("NodeCodeEditor")
        self.editor.setAccessibleName(f"Embedded code for {spec.name}")
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.editor.setFont(QFont("Cascadia Code", 10))
        self.editor.setPlainText(text)
        self.editor.setReadOnly(not self.editable)
        CppHighlighter(self.editor.document())
        tabs.addTab(self.editor, "Embedded code")
        self.generated_call = CodeEditor()
        self.generated_call.setReadOnly(True)
        self.generated_call.setFont(self.editor.font())
        self.generated_call.setPlainText(generated_code[0] if generated_code else default_node_code(spec))
        self.generated_call.setAccessibleName('Generated runtime call')
        CppHighlighter(self.generated_call.document())
        tabs.addTab(self.generated_call, 'Generated C++')
        if generated_code:
            self.generated_call.go_to_line(generated_code[1])
        self.runtime_source = CodeEditor()
        self.runtime_source.setObjectName("NodeRuntimeSource")
        self.runtime_source.setReadOnly(True)
        self.runtime_source.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.runtime_source.setFont(QFont("Cascadia Code", 10))
        self.runtime_source.setPlainText(runtime_source_excerpt(spec))
        CppHighlighter(self.runtime_source.document())
        tabs.addTab(self.runtime_source, "Runtime implementation")
        layout.addWidget(tabs, 1)

        self.error = QLabel("")
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #F37C91;")
        layout.addWidget(self.error)
        actions = QHBoxLayout()
        reset = QPushButton("Reset to generated")
        reset.setAccessibleName("Reset node code")
        reset.clicked.connect(lambda: self.editor.setPlainText(self.default))
        check = QPushButton("Validate")
        check.setAccessibleName("Validate node code")
        check.clicked.connect(self.validate)
        actions.addWidget(reset)
        actions.addWidget(check)
        actions.addStretch(1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setAccessibleName("Save node code")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        if not self.editable:
            self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)
            reset.setEnabled(False)
            check.setEnabled(False)
        actions.addWidget(self.buttons)
        layout.addLayout(actions)
        save = QShortcut(QKeySequence.StandardKey.Save, self)
        save.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        save.activated.connect(self.accept)
        self.editor.save_requested.connect(self.accept)
        self.editor.setFocus()
        if diagnostic:
            self.error.setText(f"Line {diagnostic['line']}, column {diagnostic['column']}: {diagnostic['message']}")
            self.editor.go_to_line(diagnostic['line'], diagnostic['column'])

    def validate(self):
        diagnostics = validate_embedded_code(self.editor.toPlainText(), editable=self.editable)
        if diagnostics:
            self.error.setText("\n".join(f"Line {d.line}: {d.message}" for d in diagnostics))
            self.editor.go_to_line(diagnostics[0].line)
            return False
        self.error.setText("Code is valid for editor checks; the native compiler will check symbols and types on Build.")
        return True

    def accept(self):
        if not self.editable:
            return
        if not self.validate():
            return
        text = self.editor.toPlainText()
        self.result_code = "" if text.strip() == self.default.strip() else text
        super().accept()

