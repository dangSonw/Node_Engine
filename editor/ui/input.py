"""Keyboard, mouse and gamepad bindings without hand-editing scene JSON."""
from copy import deepcopy
from itertools import zip_longest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QComboBox, QPushButton, QDialogButtonBox, QHeaderView, QAbstractItemView,
    QTabWidget, QWidget, QLineEdit, QCheckBox, QListWidget, QListWidgetItem)
from editor.core.input import BUTTONS, GAMEPAD_BUTTONS, GAMEPAD_AXES, empty_input, validate_input


class InputDialog(QDialog):
    def __init__(self, bindings, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Input Actions and Axes')
        self.resize(1000, 560)
        self.result_input = deepcopy(bindings)
        layout = QVBoxLayout(self)
        hint = QLabel('Actions combine keyboard, mouse and gamepad buttons. Axes combine digital and analog values, clamped to [−1, 1].\n'
                      'Repeat a name to add alternatives. Gamepad controller 0 means any device; analog uses the strongest value (lowest ID wins ties).\n'
                      'Names are case sensitive and must match graph nodes. Editing bindings resets preview. '
                      'Escape returns focus to the editor.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        keyboard = QWidget(); keyboard_layout = QVBoxLayout(keyboard)
        gamepad = QWidget(); gamepad_layout = QVBoxLayout(gamepad)
        self.tabs.addTab(keyboard, 'Keyboard / mouse'); self.tabs.addTab(gamepad, 'Gamepad')
        contexts = QWidget(); contexts_layout = QVBoxLayout(contexts); self.tabs.addTab(contexts, 'Contexts')
        context_hint = QLabel('Unassigned actions/axes are always available. Assigned bindings work while any of their contexts is enabled.\n'
            'Nodes can change enabled state at runtime. Re-enabling an action requires releasing buttons already held; axes resume immediately.')
        context_hint.setWordWrap(True); contexts_layout.addWidget(context_hint)
        self.context_table = QTableWidget(0,3)
        self.context_table.setAccessibleName('Input contexts')
        self.context_table.setHorizontalHeaderLabels(['Context name','Initially enabled','Actions / axes'])
        self.context_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.context_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        contexts_layout.addWidget(self.context_table)
        for name,context in sorted(bindings.get('contexts',{}).items()): self.add_context(name,context)
        context_controls = QHBoxLayout()
        add_context = QPushButton('Add Context'); add_context.clicked.connect(lambda:self.add_context())
        remove_context = QPushButton('Remove Selected'); remove_context.clicked.connect(lambda:self.remove_selected(self.context_table))
        context_controls.addWidget(add_context); context_controls.addWidget(remove_context); contexts_layout.addLayout(context_controls)
        self.table = QTableWidget(0, 4)
        self.table.setAccessibleName('Input bindings')
        self.table.setHorizontalHeaderLabels(['Kind', 'Name', 'Negative button (axis)', 'Button / positive'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        keyboard_layout.addWidget(self.table)
        self.gamepad_table = QTableWidget(0, 7)
        self.gamepad_table.setAccessibleName('Gamepad bindings')
        self.gamepad_table.setHorizontalHeaderLabels(['Kind', 'Name', 'Negative', 'Button / axis', 'Controller (0: any)', 'Dead zone', 'Invert'])
        self.gamepad_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.gamepad_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        gamepad_layout.addWidget(self.gamepad_table)
        for name, buttons in sorted(bindings['actions'].items()):
            for key in buttons:
                if isinstance(key, str): self.add_row('Action', name, '', key)
                else: self.add_gamepad_row('Action', name, positive=key['button'], controller=key['controller'])
        for name, axis in sorted(bindings['axes'].items()):
            for negative, positive in zip_longest([b for b in axis['negative'] if isinstance(b,str)],
                                                 [b for b in axis['positive'] if isinstance(b,str)], fillvalue=''):
                self.add_row('Axis', name, negative, positive)
            for direction in ('negative', 'positive'):
                for key in axis[direction]:
                    if isinstance(key, dict):
                        values=dict(negative='',positive='',controller=key['controller']); values[direction]=key['button']
                        self.add_gamepad_row('Axis buttons', name, **values)
            for pad in axis.get('gamepads', []):
                self.add_gamepad_row('Analog axis', name, positive=pad['axis'], controller=pad['controller'],
                    dead_zone=pad['dead_zone'], invert=pad['invert'])
        controls = QHBoxLayout()
        for label, kind in [('Add Action', 'Action'), ('Add Axis', 'Axis')]:
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, k=kind: self.add_row(k))
            controls.addWidget(button)
        remove = QPushButton('Remove Selected')
        remove.clicked.connect(self.remove_selected)
        controls.addWidget(remove)
        keyboard_layout.addLayout(controls)
        pad_controls = QHBoxLayout()
        for label, kind in [('Add Action', 'Action'), ('Add Button Axis', 'Axis buttons'), ('Add Analog Axis', 'Analog axis')]:
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, k=kind: self.add_gamepad_row(k))
            pad_controls.addWidget(button)
        remove = QPushButton('Remove Selected')
        remove.clicked.connect(lambda: self.remove_selected(self.gamepad_table))
        pad_controls.addWidget(remove)
        gamepad_layout.addLayout(pad_controls)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet('color: #F37C91;')
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def add_row(self, kind='Action', name=None, negative=None, positive=None):
        row = self.table.rowCount()
        self.table.insertRow(row)
        selector = QComboBox()
        selector.addItems(['Action', 'Axis'])
        selector.setCurrentText(kind)
        selector.setAccessibleName(f'Binding {row + 1} kind')
        self.table.setCellWidget(row, 0, selector)
        self.table.setItem(row, 1, QTableWidgetItem(name if name is not None else ('jump' if kind == 'Action' else 'horizontal')))
        for col, value in [(2, negative if negative is not None else ('A' if kind == 'Axis' else '')),
                           (3, positive if positive is not None else ('D' if kind == 'Axis' else 'Space'))]:
            combo = QComboBox()
            combo.addItems(['', *BUTTONS])
            combo.setCurrentText(value)
            combo.setAccessibleName(f'Binding {row + 1} {"negative" if col == 2 else "positive"} button')
            self.table.setCellWidget(row, col, combo)
        negative_combo = self.table.cellWidget(row, 2)
        negative_combo.setEnabled(kind == 'Axis')
        def changed(kind, button=negative_combo):
            button.setEnabled(kind == 'Axis')
            if kind == 'Action':
                button.setCurrentText('')
        selector.currentTextChanged.connect(changed)
        return row

    def add_gamepad_row(self, kind='Action', name=None, negative='', positive=None, controller=0, dead_zone=.15, invert=False):
        table=self.gamepad_table; row=table.rowCount(); table.insertRow(row)
        selector=QComboBox(); selector.addItems(['Action', 'Axis buttons', 'Analog axis']); selector.setCurrentText(kind)
        table.setCellWidget(row,0,selector)
        table.setItem(row,1,QTableWidgetItem(name if name is not None else ('jump' if kind=='Action' else 'horizontal')))
        neg=QComboBox(); neg.addItems(['', *GAMEPAD_BUTTONS]); neg.setCurrentText(negative)
        pos=QComboBox(); table.setCellWidget(row,2,neg); table.setCellWidget(row,3,pos)
        device=QLineEdit(str(controller)); zone=QLineEdit(str(dead_zone)); flip=QCheckBox('Invert')
        flip.setChecked(invert)
        table.setCellWidget(row,4,device); table.setCellWidget(row,5,zone); table.setCellWidget(row,6,flip)
        device.setToolTip('0: any connected gamepad. Positive ID: only that connection; reconnecting may change it.')
        zone.setToolTip('Axial dead zone in [0, 1); remaining magnitude is rescaled to 1.')
        def changed(value):
            analog=value=='Analog axis'; previous=pos.currentText()
            pos.clear(); pos.addItems(['', *(GAMEPAD_AXES if analog else GAMEPAD_BUTTONS)])
            pos.setCurrentText(previous if previous in (GAMEPAD_AXES if analog else GAMEPAD_BUTTONS) else ('LeftX' if analog else 'South'))
            neg.setEnabled(value=='Axis buttons'); zone.setEnabled(analog); flip.setEnabled(analog)
            if value!='Axis buttons': neg.setCurrentText('')
        changed(kind)
        if positive is not None: pos.setCurrentText(positive)
        selector.currentTextChanged.connect(changed)
        for col,label in [(0,'kind'),(2,'negative button'),(3,'button or axis'),(4,'controller'),(5,'dead zone'),(6,'invert')]:
            table.cellWidget(row,col).setAccessibleName(f'Gamepad binding {row+1} {label}')
        return row

    def remove_selected(self, table=None):
        table = table if isinstance(table, QTableWidget) else self.table
        for row in sorted({i.row() for i in table.selectedIndexes()}, reverse=True):
            table.removeRow(row)

    def add_context(self,name=None,context=None):
        table=self.context_table; row=table.rowCount()
        if name is None:
            names={table.item(r,0).text() for r in range(row)}; name='gameplay'; index=1
            while name in names: name=f'gameplay{index}'; index+=1
        context=context or dict(enabled=True,actions=[],axes=[])
        table.insertRow(row); table.setItem(row,0,QTableWidgetItem(name))
        enabled=QCheckBox('Enabled'); enabled.setChecked(context['enabled']); enabled.setAccessibleName(f'Context {row+1} initially enabled')
        table.setCellWidget(row,1,enabled)
        members=QPushButton(); table.setCellWidget(row,2,members)
        members.setProperty('members',deepcopy({k:context[k] for k in ('actions','axes')}))
        self.show_context_members(members)
        members.clicked.connect(lambda:self.edit_context_members(members))
        return row

    def show_context_members(self,button):
        members=button.property('members')
        button.setText(f"{len(members['actions'])} actions / {len(members['axes'])} axes — Edit…")

    def edit_context_members(self,button):
        names={'actions':set(),'axes':set()}
        for table in (self.table,self.gamepad_table):
            for row in range(table.rowCount()):
                name=table.item(row,1).text()
                if name: names['actions' if table.cellWidget(row,0).currentText()=='Action' else 'axes'].add(name)
        selected=button.property('members'); dialog=QDialog(self); dialog.setWindowTitle('Context bindings'); dialog.resize(560,420)
        layout=QVBoxLayout(dialog); columns=QHBoxLayout(); layout.addLayout(columns); lists={}
        for group in ('actions','axes'):
            column=QVBoxLayout(); column.addWidget(QLabel(group.title())); widget=QListWidget(); lists[group]=widget
            widget.setAccessibleName('Context '+group); column.addWidget(widget); columns.addLayout(column)
            for name in sorted(names[group] | set(selected[group])):
                item=QListWidgetItem(name if name in names[group] else name+' (missing)')
                item.setData(Qt.ItemDataRole.UserRole,name); item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if name in selected[group] else Qt.CheckState.Unchecked); widget.addItem(item)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        def finished(code):
            if code==QDialog.DialogCode.Accepted:
                result={group:[widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(widget.count()) if widget.item(i).checkState()==Qt.CheckState.Checked] for group,widget in lists.items()}
                button.setProperty('members',result); self.show_context_members(button)
            dialog.deleteLater()
        dialog.finished.connect(finished)
        dialog.open()

    def accept(self):
        result = empty_input()
        result['version'] = max(self.result_input['version'], 2 if self.gamepad_table.rowCount() else 1)
        try:
            for row in range(self.table.rowCount()):
                kind = self.table.cellWidget(row, 0).currentText()
                name = self.table.item(row, 1).text()
                negative, positive = (self.table.cellWidget(row, c).currentText() for c in (2, 3))
                if kind == 'Action':
                    if not positive:
                        raise ValueError(f'Row {row + 1}: choose an action button')
                    result['actions'].setdefault(name, []).append(positive)
                else:
                    if not negative and not positive:
                        raise ValueError(f'Row {row + 1}: choose an axis button')
                    axis = result['axes'].setdefault(name, {'negative': [], 'positive': []})
                    if negative:
                        axis['negative'].append(negative)
                    if positive:
                        axis['positive'].append(positive)
            for row in range(self.gamepad_table.rowCount()):
                table=self.gamepad_table
                kind=table.cellWidget(row,0).currentText(); name=table.item(row,1).text()
                negative,positive=(table.cellWidget(row,c).currentText() for c in (2,3))
                text=table.cellWidget(row,4).text()
                if not text.isascii() or not text.isdecimal():
                    raise ValueError(f'Gamepad row {row+1}: controller needs a whole number, 0 for any')
                controller=int(text)
                if kind=='Action':
                    result['actions'].setdefault(name,[]).append(dict(button=positive,controller=controller))
                else:
                    axis=result['axes'].setdefault(name,dict(negative=[],positive=[]))
                    if kind=='Analog axis':
                        axis.setdefault('gamepads',[]).append(dict(axis=positive,controller=controller,
                            dead_zone=float(table.cellWidget(row,5).text()),invert=table.cellWidget(row,6).isChecked()))
                    else:
                        if not negative and not positive: raise ValueError(f'Gamepad row {row+1}: choose an axis button')
                        for direction,button in [('negative',negative),('positive',positive)]:
                            if button: axis[direction].append(dict(button=button,controller=controller))
            if self.context_table.rowCount() or result['version']==3:
                result['version']=3; result['contexts']={}
                for row in range(self.context_table.rowCount()):
                    table=self.context_table; name=table.item(row,0).text()
                    if name in result['contexts']: raise ValueError(f'Duplicate input context: {name}')
                    result['contexts'][name]=dict(table.cellWidget(row,2).property('members'),enabled=table.cellWidget(row,1).isChecked())
            self.result_input = validate_input(result)
        except ValueError as error:
            self.error.setText(str(error))
            return
        super().accept()
