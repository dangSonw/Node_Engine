"""Scene variable authoring. A successful dialog is one undoable scene edit."""
from copy import deepcopy
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QDialogButtonBox, QLabel,
    QStyledItemDelegate, QComboBox, QAbstractItemView)
from editor.core.data_types import TYPES, variable, variable_name_valid, declaration, default_value, literal_valid


class TypeDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, *, schema=None):
        super().__init__(parent)
        self.schema = schema
        self.types = schema.type_names() if schema else list(TYPES)

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItems(self.types)
        return editor

    def setEditorData(self, editor, index):
        editor.setCurrentText(index.data())

    def setModelData(self, editor, model, index):
        kind = editor.currentText()
        model.setData(index, kind)
        value_index = model.index(index.row(), 2)
        try:
            valid = literal_valid(json.loads(value_index.data()), kind, self.schema)
        except (ValueError, TypeError):
            valid = False
        if not valid:
            model.setData(value_index, json.dumps(default_value(kind, self.schema), ensure_ascii=False))


class VariablesDialog(QDialog):
    def __init__(self, variables, parent=None, *, scopes=None, schema=None):
        super().__init__(parent)
        self.setWindowTitle('Scene Variables')
        self.resize(760, 460)
        self.result_variables = deepcopy(variables)
        self.scopes = deepcopy(scopes or {})
        self.result_scopes = deepcopy(self.scopes)
        self.schema = schema
        layout = QVBoxLayout(self)
        hint = QLabel('Scene values reset on scene entry. Global values survive scene changes. Entity values initialize each live entity independently.\n'
                      'Changing initial values resets the active preview. Double-click a cell to edit.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.table = QTableWidget(0, 4)
        self.table.setAccessibleName('Scene variables')
        self.table.setHorizontalHeaderLabels(['Name', 'Type', 'Initial value (JSON)', 'Scope'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 190)
        self.table.setColumnWidth(1, 160)
        self.type_delegate = TypeDelegate(self.table, schema=schema)
        self.table.setItemDelegateForColumn(1, self.type_delegate)
        layout.addWidget(self.table)
        for name, entry in sorted(variables.items()):
            kind, value = variable(entry, schema)
            self.add_row(name, kind, value, self.scopes.get(name, 'scene'))
        controls = QHBoxLayout()
        add = QPushButton('Add Variable')
        add.clicked.connect(self.add_variable)
        remove = QPushButton('Remove Selected')
        remove.clicked.connect(self.remove_selected)
        controls.addWidget(add)
        controls.addWidget(remove)
        controls.addStretch()
        layout.addLayout(controls)
        self.error = QLabel('')
        self.error.setWordWrap(True)
        self.error.setStyleSheet('color: #F37C91;')
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def add_row(self, name, kind, value, scope='scene'):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for column, text in enumerate((name, kind, json.dumps(value, ensure_ascii=False))):
            self.table.setItem(row, column, QTableWidgetItem(text))
        selector = QComboBox()
        selector.addItems(['scene', 'global', 'entity'])
        selector.setCurrentText(scope)
        selector.setAccessibleName(f'Scope for {name}')
        self.table.setCellWidget(row, 3, selector)
        return row

    def add_variable(self):
        names = {self.table.item(row, 0).text() for row in range(self.table.rowCount())}
        name, index = 'variable', 2
        while name in names:
            name, index = f'variable_{index}', index + 1
        row = self.add_row(name, 'float', 0.0)
        self.table.setCurrentCell(row, 0)
        self.table.editItem(self.table.item(row, 0))

    def remove_selected(self):
        for row in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(row)

    def accept(self):
        result = {}
        scopes = {}
        for row in range(self.table.rowCount()):
            try:
                name, kind, text = (self.table.item(row, col).text() for col in range(3))
                if not variable_name_valid(name):
                    raise ValueError('Name must be nonempty text, without NUL, at most 512 UTF-8 bytes')
                if name in result:
                    raise ValueError(f'Duplicate variable: {name}')
                if kind not in self.type_delegate.types:
                    raise ValueError(f'Unsupported type: {kind}')
                result[name] = declaration(kind, json.loads(text), self.schema)
                scope = self.table.cellWidget(row, 3).currentText()
                if scope != 'scene' or self.scopes.get(name) == 'scene':
                    scopes[name] = scope
            except (ValueError, TypeError) as error:
                self.error.setText(f'Row {row + 1}: {error}')
                self.table.setCurrentCell(row, 2)
                return
        self.result_variables = result
        self.result_scopes = scopes
        super().accept()
