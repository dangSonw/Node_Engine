"""Switch case authoring shared by Gameplay and function inspectors."""
from copy import deepcopy
import json
import uuid
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QLabel
from NodeGraphQt.constants import PortTypeEnum
from editor.core.switches import checked_cases, default_cases, case_port, node_spec


def validate_serialized_ports(spec, data):
    for side in ('input', 'output'):
        expected = getattr(spec, side+'s')
        ports = data.get(side+'_ports')
        if not isinstance(ports, list) or len(ports) != len(expected):
            raise ValueError('Copied Switch ports disagree with its cases')
        for port, p in zip(ports, expected):
            multi = p.type == 'exec' if side == 'input' else p.type != 'exec'
            if not isinstance(port, dict) or port.get('name') != p.name or port.get('multi_connection') is not multi or port.get('locked', False) is not False or port.get('display_name') is not True:
                raise ValueError('Copied Switch has undeclared port settings')


def configure_node(node, cases, registry):
    # Only configure a fresh node. Replacing the node in an undo macro keeps
    # earlier connection commands' Port objects alive for subsequent Undo/Redo.
    from .graph import class_name, port_painter
    from .theme import PIN_COLORS
    base = registry[node.get_property('type_id')]
    cases = checked_cases(base, cases)
    spec = node_spec(registry, dict(type=base.id, cases=cases))
    if any(port.connected_ports() for port in node.output_ports()):
        raise ValueError('Configure Switch cases before connecting outputs')
    node.set_port_deletion_allowed(True)
    for port in list(node.output_ports()): node.delete_output(port)
    node.set_property('switch_cases', cases, push_undo=False)
    labels = {case_port(c): repr(c['value']) for c in cases}
    for p in spec.outputs:
        port = node.add_output(p.name, multi_output=False, color=PIN_COLORS['exec'], painter_func=port_painter('exec'))
        label = labels.get(p.name, 'Default')
        node.view.get_output_text_item(port.view).setPlainText(label[:48] + ('…' if len(label)>48 else ''))
        port.view.setToolTip(p.name + ': ' + label)
        for other in registry.nodes.values():
            for inp in other.inputs:
                if inp.type != 'exec' or other.constant_inputs:
                    node.add_reject_port_type(port, dict(port_name=inp.name, port_type=PortTypeEnum.IN.value, node_type=f'obsidian.{class_name(other)}'))
    node.view.draw_node()


class SwitchCasesDialog(QDialog):
    def __init__(self, spec, cases, parent=None):
        super().__init__(parent)
        self.spec = spec
        self.setWindowTitle(spec.name + ' — Cases'); self.resize(540,380)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Values must be unique. Reordering or editing preserves wires.\nRemoving a case removes its wire; Undo restores both. Default always remains.'))
        self.table = QTableWidget(0,1); self.table.setHorizontalHeaderLabels(['Case value ('+spec.data_inputs[0].type+')'])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAccessibleName('Switch cases'); layout.addWidget(self.table)
        for case in cases: self.add_case(case)
        buttons = QHBoxLayout(); layout.addLayout(buttons)
        for label, callback in [('Add',self.add_case),('Remove',self.remove_case),('Move up',lambda:self.move(-1)),('Move down',lambda:self.move(1))]:
            button=QPushButton(label); button.clicked.connect(callback); buttons.addWidget(button)
        self.error=QLabel(); self.error.setWordWrap(True); layout.addWidget(self.error)
        box=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept); box.rejected.connect(self.reject); layout.addWidget(box)

    def add_case(self, case=None):
        if self.table.rowCount()>=256: return
        if not isinstance(case,dict):
            used={self.table.item(i,0).text() for i in range(self.table.rowCount())}; i=0
            while str(i) in used: i+=1
            case=dict(id=uuid.uuid4().hex,value=i if self.spec.data_inputs[0].type=='int' else str(i))
        row=self.table.rowCount(); self.table.insertRow(row)
        item=QTableWidgetItem(str(case['value'])); item.setData(Qt.ItemDataRole.UserRole,case['id'])
        self.table.setItem(row,0,item); self.table.setCurrentCell(row,0)

    def remove_case(self):
        row=self.table.currentRow()
        if row>=0: self.table.removeRow(row)

    def move(self, offset):
        row=self.table.currentRow(); target=row+offset
        if row<0 or not 0<=target<self.table.rowCount(): return
        first=self.table.takeItem(row,0); second=self.table.takeItem(target,0)
        self.table.setItem(target,0,first); self.table.setItem(row,0,second); self.table.setCurrentCell(target,0)

    def accept(self):
        try:
            cases=[]
            for i in range(self.table.rowCount()):
                item=self.table.item(i,0); value=item.text()
                if self.spec.data_inputs[0].type=='int': value=json.loads(value)
                cases.append(dict(id=item.data(Qt.ItemDataRole.UserRole),value=value))
            self.cases=checked_cases(self.spec,cases)
        except (ValueError,TypeError) as error:
            self.error.setText(str(error)); return
        super().accept()


def case_button(adapter, node, parent):
    button=QPushButton('Edit Cases…',parent); button.setAccessibleName('Edit Switch cases')
    def edit():
        spec=adapter.registry[node.get_property('type_id')]
        dialog=SwitchCasesDialog(spec,deepcopy(node.get_property('switch_cases')),parent)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            adapter.edit_switch_cases(node,dialog.cases)
    button.clicked.connect(edit)
    return button
