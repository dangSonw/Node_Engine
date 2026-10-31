"""Typed component definition authoring."""
import json
from PySide6.QtWidgets import QDialog, QLabel, QPushButton
from editor.core.components import new_component
from .functions import FunctionSignatureDialog


class ComponentSignatureDialog(FunctionSignatureDialog):
    def __init__(self, definitions, parent=None, *, reserved_nodes=()):
        super().__init__(definitions, parent, event_mode=True)
        self.reserved_nodes=set(reserved_nodes)
        self.setWindowTitle('Define Component')
        self.name_field.setText('My Component')
        self.name_field.setAccessibleName('Component name')
        self.tables['inputs'].setAccessibleName('Component properties')
        for label in self.findChildren(QLabel):
            if label.text() == 'Parameters':
                label.setText('Properties')
        for button in self.findChildren(QPushButton):
            if button.text() == 'Add parameter':
                button.setText('Add property')
        self.error.setText('Define typed data to attach to entities. Property signatures stay fixed after creation. Each property adds Get and Set nodes.')

    def accept(self):
        try:
            table = self.tables['inputs']
            properties = [{'name': table.item(row, 0).text().strip(),
                           'type': table.cellWidget(row, 1).currentText(),
                           'default': json.loads(table.item(row, 2).text())}
                          for row in range(table.rowCount())]
            self.definition = new_component(self.name_field.text().strip(), properties, self.definitions, reserved_nodes=self.reserved_nodes)
        except (ValueError, TypeError) as error:
            self.error.setText(str(error))
            return
        QDialog.accept(self)
