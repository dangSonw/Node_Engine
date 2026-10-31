"""Transactional signature creation and navigable function graph authoring."""
from copy import deepcopy
import json
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QCheckBox, QLabel, QPushButton, QDialogButtonBox, QTableWidget, QTableWidgetItem,
    QComboBox, QSplitter, QWidget, QListWidget, QListWidgetItem, QStackedWidget,
    QScrollArea, QHeaderView)
from editor.core.data_types import TYPES, default_value, literal_valid
from editor.core.functions import new_function,signatures
from editor.core.events import new_event,signatures as event_signatures
from editor.core.compiler import compile_graph, GraphError
from .graph import GraphAdapter
from .node_code import NodeCodeDialog
from editor.core.node_code import generated_node_code, default_node_code


class FunctionsCommand(QUndoCommand):
    def __init__(self, window, definitions, label='Edit functions'):
        super().__init__(label)
        self.window = window
        self.before = deepcopy(window.adapter.functions)
        self.after = deepcopy(definitions)

    def redo(self):
        self.window.apply_functions(self.after)

    def undo(self):
        self.window.apply_functions(self.before)


class SignatureDefinitionsCommand(FunctionsCommand):
    def __init__(self,window,document):
        super().__init__(window,document.get('functions',[]))
        self.before_events=deepcopy(window.adapter.event_definitions)
        self.after_events=deepcopy(document.get('event_definitions',[]))

    def apply(self,definitions,events):
        if isinstance(self.window,FunctionEditorDialog): self.window.configure_definitions(definitions,events)
        else: self.window.adapter.configure_functions(definitions,events)
        self.window._signature_change_pending=True

    def redo(self): self.apply(self.after,self.after_events)
    def undo(self): self.apply(self.before,self.before_events)


def apply_signature_edit(window,after,function_id):
    """Native node commands preserve earlier Undo references to replaced call nodes."""
    changed={n['id'] for n in after['nodes'] if n['type']==function_id}
    apply_function_graph_edit(window,after,changed,changed,'Edit function signature')


def apply_function_graph_edit(window,after,removed,added,label):
    adapter=window.adapter; graph=adapter.graph
    document=next(f['graph'] for f in after['functions'] if f['id']==adapter.current_function) if adapter.current_function is not None else after
    changed={n['id']:n for n in document['nodes'] if n['id'] in added}
    selected={n.get_property('stable_id') for n in graph.selected_nodes()}
    failure=None
    adapter.loading=True; graph.begin_undo(label)
    try:
        for node in list(graph.all_nodes()):
            if node.get_property('stable_id') in removed: graph.delete_node(node)
        graph.undo_stack().push(SignatureDefinitionsCommand(window,after))
        from .graph import class_name
        for nid,data in changed.items():
            node=graph.create_node('obsidian.'+class_name(adapter.registry[data['type']]),name=data.get('label'),pos=data.get('position',[0,0]),selected=False)
            node.set_property('stable_id',nid,push_undo=False)
            node.set_property('embedded_code',data.get('code',''),push_undo=False)
            for name,value in data['values'].items(): node.set_property('value_'+name,deepcopy(value),push_undo=False)
            node.set_property('selected',nid in selected or nid not in removed,push_undo=False)
        nodes={n.get_property('stable_id'):n for n in graph.all_nodes()}
        for edge in document['links']:
            src,out=edge['from']; dst,inp=edge['to']
            if src in changed or dst in changed:
                source,target=nodes[src].outputs()[out],nodes[dst].inputs()[inp]
                source.connect_to(target)
                if target not in source.connected_ports(): raise ValueError(f'Could not restore wire {src}.{out} -> {dst}.{inp}')
    except Exception as error:
        failure=error
    finally:
        graph.end_undo()
        if failure is not None:
            stack=graph.undo_stack(); stack.undo()
            stack.command(stack.index()).setObsolete(True); stack.redo()
        adapter.loading=False
    window.finish_signature_edit()
    if failure is not None: raise ValueError(f'{label} rolled back: {failure}') from failure


class FunctionSignatureDialog(QDialog):
    def __init__(self, definitions, parent=None, *, event_mode=False, function_id=None, validator=None, schema=None):
        super().__init__(parent)
        from editor.core.typed_schema import build_schema
        registry=getattr(getattr(parent,'adapter',None),'registry',None)
        self.schema=schema if schema is not None else getattr(registry,'type_schema',None) or build_schema([],[])
        self.event_mode = event_mode
        self.original=next((deepcopy(f) for f in definitions if f['id']==function_id),None)
        self.validator=validator
        self.result_document=None
        self.port_origins=None
        kind = 'Event' if event_mode else 'Function'
        self.setWindowTitle(f'Edit {kind} Signature' if self.original else 'Define Event' if event_mode else 'Create Function')
        self.definitions = deepcopy(definitions)
        self.definition = None
        layout = QVBoxLayout(self)
        self.name_field = QLineEdit(self.original['name'] if self.original else 'My '+kind)
        self.name_field.setAccessibleName(kind+' name')
        self.pure = QCheckBox('Pure calculation (no scene state or side effects)')
        if self.original and not event_mode:
            self.pure.setChecked(self.original['pure']); self.pure.setEnabled(False)
            self.pure.setToolTip('Create another function to change between Pure and Action')
        layout.addWidget(QLabel('Name'))
        layout.addWidget(self.name_field)
        if not event_mode:
            layout.addWidget(self.pure)
        else:
            self.pure.hide()
        self.tables = {}
        for side in (('inputs',) if event_mode else ('inputs','outputs')):
            layout.addWidget(QLabel('Parameters' if event_mode else side.title()))
            table = QTableWidget(0,3 if side=='inputs' else 2)
            table.setHorizontalHeaderLabels(['Name','Type','Default (JSON)'] if side=='inputs' else ['Name','Type'])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.setAccessibleName('Event parameters' if event_mode else f'Function {side}')
            self.tables[side] = table
            layout.addWidget(table)
            row = QHBoxLayout()
            add, remove = QPushButton('Add parameter' if event_mode else 'Add '+side[:-1]), QPushButton('Remove selected')
            add.clicked.connect(lambda _, s=side: self.add_port(s))
            remove.clicked.connect(lambda _, t=table: t.removeRow(t.currentRow()) if t.currentRow()>=0 else None)
            row.addWidget(add); row.addWidget(remove)
            for label,delta in [('Move up',-1),('Move down',1)]:
                button=QPushButton(label); button.clicked.connect(lambda _,s=side,d=delta:self.move_port(s,d)); row.addWidget(button)
            layout.addLayout(row)
            if self.original:
                for port in self.original['parameters' if event_mode else side]: self.add_port(side,port['name'],port['type'],port.get('default'),origin=port['name'])
        self.error = QLabel('Applying checks all senders and handlers. Connected parameters or authored values cannot be discarded.' if event_mode and self.original
                            else 'Event nodes appear in Events & Signals. Edit the signature later from the Graph menu.' if event_mode
                            else 'Applying checks all call sites and function graphs. Connected ports or authored values cannot be discarded.' if self.original
                            else 'Function signatures and bodies can be edited later from the Graph menu.')
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        if self.original: self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Apply')
        layout.addWidget(self.buttons)
        self.resize(690,600)

    def add_port(self, side, name=None, type_name='float', value=None, *, origin=None):
        table = self.tables[side]
        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row,0,QTableWidgetItem(name or f'{"Arg" if side=="inputs" else "Result"}{row+1}'))
        table.item(row,0).setData(Qt.ItemDataRole.UserRole,origin)
        combo = QComboBox()
        combo.addItems(self.schema.type_names())
        combo.setCurrentText(type_name)
        table.setCellWidget(row,1,combo)
        if side=='inputs':
            item = QTableWidgetItem(json.dumps(default_value(type_name,self.schema) if value is None else value,ensure_ascii=False))
            table.setItem(row,2,item)
            combo.currentTextChanged.connect(lambda t: item.setText(json.dumps(default_value(t,self.schema),ensure_ascii=False)))

    def move_port(self,side,delta):
        table=self.tables[side]; row=table.currentRow(); target=row+delta
        if row<0 or not 0<=target<table.rowCount(): return
        rows=[(table.item(i,0).text(),table.cellWidget(i,1).currentText(),table.item(i,2).text() if side=='inputs' else None,
               table.item(i,0).data(Qt.ItemDataRole.UserRole)) for i in range(table.rowCount())]
        rows[row],rows[target]=rows[target],rows[row]; table.setRowCount(0)
        for name,kind,text,origin in rows:
            self.add_port(side,name,kind,origin=origin)
            if text is not None: table.item(table.rowCount()-1,2).setText(text)
        table.setCurrentCell(target,0)

    def accept(self):
        try:
            ports = {}
            for side, table in self.tables.items():
                ports[side] = []
                for row in range(table.rowCount()):
                    p = {'name':table.item(row,0).text().strip(), 'type':table.cellWidget(row,1).currentText()}
                    if side=='inputs':
                        p['default'] = json.loads(table.item(row,2).text())
                    ports[side].append(p)
            if self.original:
                self.definition={**deepcopy(self.original),'name':self.name_field.text().strip(),
                                 **({'parameters':ports['inputs']} if self.event_mode else ports)}
                (event_signatures if self.event_mode else signatures)([self.definition if f['id']==self.original['id'] else f for f in self.definitions],self.schema)
                self.port_origins={side:{table.item(row,0).text().strip():table.item(row,0).data(Qt.ItemDataRole.UserRole)
                    for row in range(table.rowCount()) if table.item(row,0).data(Qt.ItemDataRole.UserRole) is not None}
                    for side,table in self.tables.items()}
                if self.validator: self.result_document,_=self.validator(self.definition,self.port_origins)
            elif self.event_mode:
                self.definition = new_event(self.name_field.text().strip(), ports['inputs'], self.definitions,schema=self.schema)
            else:
                self.definition = new_function(self.name_field.text().strip(), ports['inputs'], ports['outputs'],
                                               self.pure.isChecked(), self.definitions,schema=self.schema)
        except (ValueError, TypeError) as e:
            self.error.setText(str(e))
            return
        super().accept()


class FunctionExtractionDialog(QDialog):
    def __init__(self,document,selection,scene,parent=None,*,current_function=None):
        super().__init__(parent)
        from editor.core.function_extraction import extract_function
        self.setWindowTitle('Extract Function')
        self.scene=scene
        name='Extracted Function'; index=2; names={f['name'].casefold() for f in document.get('functions',[])}
        while name.casefold() in names: name=f'Extracted Function {index}'; index+=1
        self.result_document,self.info=extract_function(document,selection,name,scene,current_function=current_function)
        layout=QVBoxLayout(self); self.name_field=QLineEdit(name); self.name_field.setAccessibleName('Extracted function name')
        layout.addWidget(QLabel('Function name')); layout.addWidget(self.name_field)
        info=self.info
        text=[('Pure' if info['pure'] else 'Action')+f' function · {len(info["removed"])} nodes replaced',
              'Inputs: '+(', '.join(p['name']+': '+p['type'] for p in info['inputs']) or 'none'),
              'Outputs: '+(', '.join(p['name']+': '+p['type'] for p in info['outputs']) or 'none')]
        if info['copied']: text.append('Copied data dependencies (evaluated when used): '+', '.join(info['copied']))
        if info['retained']: text.append('Data nodes kept in this graph for external reads: '+', '.join(info['retained']))
        if info['guarded']: text.append('A continuation Branch preserves paths that stop without executing the next node.')
        text.append('The new call and definition apply together as one Undo step. Input/output names can be edited later.')
        summary=QLabel('\n\n'.join(text)); summary.setWordWrap(True); layout.addWidget(summary)
        self.error=QLabel(); self.error.setWordWrap(True); layout.addWidget(self.error)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Extract')
        self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject); layout.addWidget(self.buttons)
        self.resize(650,360)

    def accept(self):
        name=self.name_field.text().strip(); fid=self.info['function_id']
        next(f for f in self.result_document['functions'] if f['id']==fid)['name']=name
        graph=next((f['graph'] for f in self.result_document['functions'] if any(n['id']==self.info['call_id'] for n in f['graph']['nodes'])),self.result_document)
        next(n for n in graph['nodes'] if n['id']==self.info['call_id'])['label']=name
        if self.info['guarded']:
            next(n for n in graph['nodes'] if n['id']==self.info['added'][1])['label']='Continue '+name
        try: compile_graph(self.result_document,self.scene)
        except ValueError as error: self.error.setText(str(error)); return
        super().accept()


def extract_selection(window,document,scene,*,current_function=None):
    selected=[n.get_property('stable_id') for n in window.adapter.graph.selected_nodes()]
    dialog=None
    try:
        dialog=FunctionExtractionDialog(document,selected,scene,window,current_function=current_function)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            apply_function_graph_edit(window,dialog.result_document,set(dialog.info['removed']),set(dialog.info['added']),'Extract function')
            window.adapter.focus(dialog.info['call_id'])
    except ValueError as error:
        if isinstance(window,FunctionEditorDialog): window.message.setText(str(error))
        else: window.console.appendPlainText(str(error)); window.output_tabs.setCurrentWidget(window.console)
    finally:
        if dialog: dialog.deleteLater()


class FunctionEditorDialog(QDialog):
    def keyPressEvent(self, event):
        # Enter commits an inspector field. Saving the whole editing transaction
        # is an explicit button action, even if a Qt button gains default status.
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):
            event.accept()
            return
        super().keyPressEvent(event)

    def __init__(self, definitions, function_id, scene, parent=None, *, event_definitions=()):
        super().__init__(parent)
        self.setWindowTitle('Function Graphs')
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint)
        self.definitions = deepcopy(definitions)
        self.event_definitions = deepcopy(list(event_definitions))
        self.scene = deepcopy(scene)
        self.result_definitions = None
        self.undo_stack=QUndoStack(self)
        self._signature_change_pending=False
        self.undo_stack.indexChanged.connect(self.finish_signature_edit)
        self.adapters = {}
        self.current_id = function_id
        self.inspected = None
        layout = QVBoxLayout(self)
        navigation = QHBoxLayout()
        self.breadcrumb = QLabel()
        self.chooser = QComboBox()
        self.chooser.setAccessibleName('Function graph')
        for f in self.definitions:
            self.chooser.addItem(f['name'],f['id'])
        navigation.addWidget(self.breadcrumb,1)
        navigation.addWidget(self.chooser)
        layout.addLayout(navigation)
        split = QSplitter()
        library = QWidget()
        library_layout = QVBoxLayout(library)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search nodes…')
        self.node_workflow = QComboBox()
        self.node_workflow.setAccessibleName('Function node suggestions')
        for label, value in [('All compatible nodes', 'all'), ('2D + shared nodes', '2d'), ('3D + shared nodes', '3d')]:
            self.node_workflow.addItem(label, value)
        self.node_workflow.setCurrentIndex(self.node_workflow.findData(
            getattr(getattr(parent, 'adapter', None), 'node_workflow', 'all')))
        self.library = QListWidget()
        library_layout.addWidget(self.search)
        library_layout.addWidget(self.node_workflow)
        library_layout.addWidget(self.library)
        split.addWidget(library)
        self.graphs = QStackedWidget()
        split.addWidget(self.graphs)
        inspector = QWidget()
        self.form = QFormLayout(inspector)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(inspector)
        split.addWidget(self.scroll)
        split.setSizes([210,760,250])
        layout.addWidget(split,1)
        self.message = QLabel('Double-click a function call to enter its graph. Save applies all edited functions as one undo step.')
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        validate = self.buttons.addButton('Validate', QDialogButtonBox.ButtonRole.ActionRole)
        validate.clicked.connect(self.validate_functions)
        self.extract_button=self.buttons.addButton('Extract Function…',QDialogButtonBox.ButtonRole.ActionRole)
        self.extract_button.clicked.connect(self.extract_selection)
        help_button=self.buttons.addButton('Node Help (F1)',QDialogButtonBox.ButtonRole.ActionRole)
        help_button.clicked.connect(self.show_node_help)
        for button in self.buttons.buttons():
            button.setAutoDefault(False)
            button.setDefault(False)
        layout.addWidget(self.buttons)
        self.chooser.currentIndexChanged.connect(lambda i:self.navigate(self.chooser.itemData(i)))
        self.library.itemActivated.connect(lambda item:self.adapter.add(item.data(Qt.ItemDataRole.UserRole)))
        self.search.textChanged.connect(self.filter_library)
        self.node_workflow.currentIndexChanged.connect(lambda:self.navigate(self.current_id))
        for key, callback in [('Ctrl+Z',lambda:self.adapter.graph.undo_stack().undo()),
                              ('Ctrl+Shift+Z',lambda:self.adapter.graph.undo_stack().redo()),
                              ('Ctrl+C',lambda:self.adapter.graph.copy_nodes()), ('Ctrl+V',lambda:self.adapter.paste()),
                              ('Ctrl+D',lambda:self.adapter.duplicate()),
                              ('Ctrl+Alt+C',self.edit_node_code),
                              ('Delete',lambda:self.adapter.graph.delete_nodes(self.adapter.graph.selected_nodes())),
                              ('Home',self.frame_all),('F1',self.show_node_help),('Tab',lambda:self.search.setFocus())]:
            binding = QShortcut(QKeySequence(key),self.graphs)
            binding.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            binding.activated.connect(callback)
        self.navigate(function_id)
        self.resize(1280,800)

    @property
    def adapter(self):
        return self.adapters[self.current_id]

    def show_node_help(self):
        from .node_help import open_help
        return open_help(self, self.adapter)

    def navigate(self, function_id):
        if function_id not in {f['id'] for f in self.definitions}:
            return
        f = next(f for f in self.definitions if f['id']==function_id)
        if function_id not in self.adapters:
            adapter = GraphAdapter(self,self.definitions,function_id,self.event_definitions,
                                   component_definitions=(self.scene or {}).get('component_definitions', []),
                                   struct_definitions=(self.scene or {}).get('struct_definitions', []),
                                   enum_definitions=(self.scene or {}).get('enum_definitions', []),undo_stack=self.undo_stack)
            adapter.load(f['graph'],clear_history=False,
                         struct_definitions=(self.scene or {}).get('struct_definitions', []),
                         enum_definitions=(self.scene or {}).get('enum_definitions', []))
            adapter.selected.connect(self.inspect)
            adapter.changed.connect(self.refresh_selection)
            adapter.graph.property_changed.connect(self.refresh_inspector)
            adapter.graph.node_double_clicked.connect(lambda n:self.navigate(n.get_property('type_id')))
            self.adapters[function_id] = adapter
            self.graphs.addWidget(adapter.graph.widget)
        self.current_id = function_id
        self.adapter.node_workflow = self.node_workflow.currentData()
        self.graphs.setCurrentWidget(self.adapter.graph.widget)
        self.breadcrumb.setText(f'Gameplay › {f["name"]}   ·   {"Pure" if f["pure"] else "Action"}')
        self.chooser.blockSignals(True)
        self.chooser.setCurrentIndex(self.chooser.findData(function_id))
        self.chooser.blockSignals(False)
        self.library.clear()
        for spec in self.adapter.suggested_specs():
            item = QListWidgetItem(spec.name)
            item.setData(Qt.ItemDataRole.UserRole,spec.id)
            self.library.addItem(item)
        self.filter_library(self.search.text())
        self.inspect(None)

    def configure_definitions(self,definitions,event_definitions=None):
        self.definitions=deepcopy(definitions)
        if event_definitions is not None: self.event_definitions=deepcopy(event_definitions)
        ids={f['id'] for f in definitions}
        for fid,adapter in self.adapters.items():
            if fid in ids: adapter.configure_functions(definitions,self.event_definitions)
        self._signature_change_pending=True

    def finish_signature_edit(self,*_):
        if not self._signature_change_pending or any(a.loading for a in self.adapters.values()): return
        self._signature_change_pending=False
        self.chooser.blockSignals(True); self.chooser.clear()
        for f in self.definitions: self.chooser.addItem(f['name'],f['id'])
        self.chooser.blockSignals(False)
        if self.current_id not in {f['id'] for f in self.definitions}: self.current_id=self.definitions[0]['id']
        self.navigate(self.current_id)

    def extract_selection(self):
        document=dict(version=1,nodes=[],links=[],functions=self.snapshot(),event_definitions=self.event_definitions)
        extract_selection(self,document,self.scene,current_function=self.current_id)

    def frame_all(self):
        self.adapter.clear_selection()
        self.adapter.graph.fit_to_selection()

    def filter_library(self, text):
        words = text.casefold().split()
        for i in range(self.library.count()):
            item = self.library.item(i)
            item.setHidden(not all(w in item.text().casefold() for w in words))

    def refresh_selection(self):
        if self.inspected is not None and self.inspected not in self.adapter.graph.all_nodes():
            self.inspect(None)

    def edit_node_code(self, checked=False, *, diagnostic=None):
        node = self.inspected or next(iter(self.adapter.graph.selected_nodes()), None)
        if node is None:
            self.message.setText('Select a node first.')
            return False
        spec = self.adapter.registry[node.get_property('type_id')]
        try:
            document = dict(version=1, nodes=[], links=[], functions=self.snapshot(), event_definitions=self.event_definitions)
            ir = compile_graph(document, self.scene)
            generated = generated_node_code(ir, f'{self.current_id}/{node.get_property("stable_id")}', spec)
        except ValueError as error:
            generated = ('// Generated code requires a valid graph.\n// ' + str(error).replace('\n', '\n// ') + '\n' + default_node_code(spec), 1)
        dialog = NodeCodeDialog(spec, node, self, diagnostic=diagnostic, generated_code=generated)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        node.set_property('embedded_code', dialog.result_code or '')
        return True

    def inspect(self, node):
        self.inspected = node
        while self.form.rowCount():
            self.form.removeRow(0)
        if node is None:
            self.form.addRow(QLabel('Select a node to edit its input defaults.'))
            return
        spec = self.adapter.registry[node.get_property('type_id')]
        self.form.addRow(QLabel(spec.name))
        code = QPushButton('View / Edit Node Code…')
        code.setAccessibleName('View or edit selected node code')
        code.clicked.connect(self.edit_node_code)
        self.form.addRow(code)
        if spec.kind == 'switch':
            from .switches import case_button
            self.form.addRow(case_button(self.adapter,node,self))
        for p in spec.data_inputs:
            value = node.get_property('value_'+p.name)
            field = QLineEdit(value if p.type in ('string','entity') else json.dumps(value,ensure_ascii=False))
            field.setAccessibleName(f'{spec.name} {p.name}')
            field.setProperty('domain_property','value_'+p.name)
            field.setToolTip(p.type)
            def commit(port=p, widget=field, target=node):
                try:
                    value = widget.text() if port.type in ('string','entity') else json.loads(widget.text())
                    if not literal_valid(value,port.type,getattr(self.adapter.registry,'type_schema',None)):
                        raise ValueError(f'Expected {port.type}')
                    target.set_property('value_'+port.name,value)
                    widget.setStyleSheet('')
                except (ValueError,TypeError) as e:
                    widget.setStyleSheet('border:1px solid #F37C91')
                    self.message.setText(str(e))
            field.editingFinished.connect(commit)
            self.form.addRow(p.name,field)

    def refresh_inspector(self, node, name, value):
        if node is self.inspected:
            for field in self.scroll.findChildren(QLineEdit):
                if field.property('domain_property') == name:
                    field.setText(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False))

    def snapshot(self):
        definitions = deepcopy(self.definitions)
        for f in definitions:
            if f['id'] in self.adapters:
                f['graph'] = self.adapters[f['id']].document()
        return definitions

    def validate_functions(self):
        definitions = self.snapshot()
        try:
            compile_graph({'version':1,'nodes':[],'links':[],'functions':definitions,
                           'event_definitions':self.event_definitions},self.scene)
        except GraphError as e:
            self.message.setText(str(e))
            p = e.problems[0]
            if '/' in p.node:
                fid,nid = p.node.split('/',1)
                if fid.isdigit():
                    self.navigate(int(fid))
                    self.adapter.focus(nid)
            return False
        self.message.setText('Functions valid')
        return True

    def accept(self):
        if self.validate_functions():
            self.result_definitions = self.snapshot()
            super().accept()
