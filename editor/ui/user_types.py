"""Struct/Enum definitions with transactional graph/scene refactoring."""
from copy import deepcopy
import json
from PySide6.QtCore import Qt
from PySide6.QtGui import QUndoCommand
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,
    QPushButton,QDialogButtonBox,QTableWidget,QTableWidgetItem,QComboBox,QListWidget,QListWidgetItem,QHeaderView)
from editor.core.data_types import TYPES,default_value
from editor.core.type_edits import definitions,edit_type
from editor.core.typed_schema import build_schema,with_types
from editor.core.components import with_components
from editor.core.registry import Registry
from .graph import class_name


class TypeSignatureDialog(QDialog):
    def __init__(self,kind,schema,parent=None,definition=None):
        super().__init__(parent)
        self.kind,self.schema,self.original=kind,schema,deepcopy(definition)
        self.definition=None; self.origins=None
        self.setWindowTitle(('Edit ' if definition else 'New ')+kind.title())
        layout=QVBoxLayout(self); layout.addWidget(QLabel('Name'))
        self.name_field=QLineEdit(definition['name'] if definition else 'My'+kind.title())
        self.name_field.setAccessibleName(kind.title()+' name'); layout.addWidget(self.name_field)
        self.table=QTableWidget(0,3 if kind=='struct' else 1)
        self.table.setHorizontalHeaderLabels(['Field','Type','Default (JSON)'] if kind=='struct' else ['Label'])
        self.table.setAccessibleName('Struct fields' if kind=='struct' else 'Enum labels')
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        controls=QHBoxLayout()
        for text,callback in [('Add field' if kind=='struct' else 'Add label',lambda:self.add_row()),
            ('Remove selected',lambda:self.table.removeRow(self.table.currentRow()) if self.table.currentRow()>=0 else None),
            ('Move up',lambda:self.move(-1)),('Move down',lambda:self.move(1))]:
            button=QPushButton(text); button.clicked.connect(callback); controls.addWidget(button)
        layout.addLayout(controls)
        self.error=QLabel(''); self.error.setWordWrap(True); layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        if definition:
            entries=definition['fields'] if kind=='struct' else definition['values']
            for entry in entries:
                name=entry['name'] if isinstance(entry,dict) else entry
                self.add_row(name,entry.get('type','float') if isinstance(entry,dict) else 'float',
                             entry.get('default') if isinstance(entry,dict) else None,origin=name)
        else: self.add_row('value' if kind=='struct' else 'Idle')
        self.resize(720,500)

    def add_row(self,name=None,kind='float',value=None,*,origin=None):
        row=self.table.rowCount(); self.table.insertRow(row)
        item=QTableWidgetItem(name or ('field' if self.kind=='struct' else 'Label')+str(row+1))
        item.setData(Qt.ItemDataRole.UserRole,origin); self.table.setItem(row,0,item)
        if self.kind=='struct':
            combo=QComboBox(); combo.addItems(self.schema.type_names())
            combo.setCurrentText(kind); combo.setAccessibleName('Field type'); self.table.setCellWidget(row,1,combo)
            item=QTableWidgetItem(json.dumps(default_value(kind,self.schema) if value is None else value,ensure_ascii=False))
            self.table.setItem(row,2,item)
            combo.currentTextChanged.connect(lambda t,i=item:i.setText(json.dumps(default_value(t,self.schema),ensure_ascii=False)))
        return row

    def move(self,delta):
        row=self.table.currentRow(); target=row+delta
        if row<0 or not 0<=target<self.table.rowCount(): return
        entries=[]
        for i in range(self.table.rowCount()):
            entries.append((self.table.item(i,0).text(),self.table.cellWidget(i,1).currentText() if self.kind=='struct' else 'float',
                            self.table.item(i,2).text() if self.kind=='struct' else None,self.table.item(i,0).data(Qt.ItemDataRole.UserRole)))
        entries[row],entries[target]=entries[target],entries[row]; self.table.setRowCount(0)
        for name,kind,value,origin in entries:
            index=self.add_row(name,kind,origin=origin)
            if self.kind=='struct': self.table.item(index,2).setText(value)
        self.table.setCurrentCell(target,0)

    def accept(self):
        try:
            entries=[]; origins={}
            used_values={v.get('value',i) if isinstance(v,dict) else i for i,v in enumerate((self.original or {}).get('values',[]))}
            for row in range(self.table.rowCount()):
                name=self.table.item(row,0).text().strip(); origin=self.table.item(row,0).data(Qt.ItemDataRole.UserRole)
                if origin is not None: origins[name]=origin
                if self.kind=='struct':
                    entries.append(dict(name=name,type=self.table.cellWidget(row,1).currentText(),default=json.loads(self.table.item(row,2).text())))
                else:
                    old=(self.original or {}).get('values',[])
                    match=next(((v.get('value',i) if isinstance(v,dict) else i) for i,v in enumerate(old) if (v['name'] if isinstance(v,dict) else v)==origin),None)
                    number=match if match is not None else max(used_values,default=-1)+1
                    used_values.add(number); entries.append(dict(name=name,value=number))
            definition=dict(name=self.name_field.text().strip(),**{'fields' if self.kind=='struct' else 'values':entries})
            for key in ('node_id','variable_id'):
                if self.original and key in self.original: definition[key]=self.original[key]
            # Validate the edited shape independently of defaults embedded elsewhere.
            structs,enums=deepcopy(list(self.schema.structs.values())),deepcopy(list(self.schema.enums.values()))
            group=structs if self.kind=='struct' else enums
            if self.original: group[:]=[d for d in group if d['name']!=self.original['name']]
            group.append(definition)
            if self.original:
                old_type=self.kind+':'+self.original['name']; new_type=self.kind+':'+definition['name']
                for d in structs:
                    for f in d['fields']:
                        if f['type']==old_type: f['type']=new_type
                        if d is not definition: f.pop('default',None)
            build_schema(structs,enums)
            self.definition,self.origins=definition,origins
        except (ValueError,TypeError,KeyError) as error:
            self.error.setText(str(error)); return
        super().accept()


class TypeLibraryDialog(QDialog):
    def __init__(self,graph,scene,parent=None,*,snapshot=None,scene_id='main'):
        super().__init__(parent); self.setWindowTitle('Structs and Enums')
        self.result_graph,self.result_scene=deepcopy(graph),deepcopy(scene)
        self.result_snapshot=None; self.scene_id=scene_id
        if snapshot is not None:
            from editor.core.project_types import synchronize_types
            try: self.result_snapshot=synchronize_types(snapshot)
            except Exception:
                self.deleteLater(); raise
            document=self.result_snapshot['scenes'][scene_id] if 'scenes' in self.result_snapshot else self.result_snapshot
            self.result_graph,self.result_scene=document['graph'],document['scene']
            self.setWindowTitle('Project Structs and Enums')
        layout=QVBoxLayout(self); self.list=QListWidget(); self.list.setAccessibleName('User types'); layout.addWidget(self.list)
        controls=QHBoxLayout()
        for text,callback in [('New Struct',lambda:self.edit('struct')),('New Enum',lambda:self.edit('enum')),
                              ('Edit selected',self.edit_selected),('Delete selected',self.delete_selected)]:
            button=QPushButton(text); button.clicked.connect(callback); controls.addWidget(button)
        layout.addLayout(controls)
        self.error=QLabel('Changes update every scene, function, event, value and graph wire in this project.' if snapshot is not None
                          else 'Renames update fields, values and graph wires. Referenced types cannot be deleted.')
        self.error.setWordWrap(True); layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.refresh(); self.resize(760,520)

    def refresh(self,select=None):
        self.list.clear()
        for kind,group in zip(('struct','enum'),definitions(self.result_graph,self.result_scene)):
            for definition in group:
                item=QListWidgetItem(definition['name']+' ('+kind+')'); item.setData(Qt.ItemDataRole.UserRole,(kind,definition['name']))
                self.list.addItem(item)
                if definition['name']==select: self.list.setCurrentItem(item)

    def edit_selected(self):
        item=self.list.currentItem()
        if item: self.edit(*item.data(Qt.ItemDataRole.UserRole))

    def edit(self,kind,original=None):
        schema=build_schema(*definitions(self.result_graph,self.result_scene))
        definition=(schema.structs if kind=='struct' else schema.enums).get(original)
        dialog=TypeSignatureDialog(kind,schema,self,definition)
        accepted=dialog.exec()==QDialog.DialogCode.Accepted
        if accepted: self.apply_definition(kind,dialog.definition,original=original,origins=dialog.origins)
        dialog.deleteLater()

    def apply_definition(self,kind,definition,*,original=None,origins=None):
        try:
            if self.result_snapshot is not None:
                from editor.core.project_types import edit_project_type
                snapshot=edit_project_type(self.result_snapshot,kind,definition,original=original,origins=origins)
                document=snapshot['scenes'][self.scene_id] if 'scenes' in snapshot else snapshot
                graph,scene=document['graph'],document['scene']
            else:
                graph,scene=edit_type(self.result_graph,self.result_scene,kind,definition,original=original,origins=origins)
        except (ValueError,TypeError,KeyError) as error:
            self.error.setText(str(error)); return False
        self.result_graph,self.result_scene=graph,scene
        if self.result_snapshot is not None: self.result_snapshot=snapshot
        self.error.setText('Changes will be applied together when you press OK.')
        self.refresh(definition['name'] if definition else None); return True

    def delete_selected(self):
        item=self.list.currentItem()
        if item:
            kind,name=item.data(Qt.ItemDataRole.UserRole); self.apply_definition(kind,None,original=name)


class TypeStateCommand(QUndoCommand):
    def __init__(self,window,graph,scene,*,project=None,documents=None):
        super().__init__('Edit user types'); self.window=window
        self.before=(window.adapter.document(),deepcopy(window.scene),deepcopy(window.project),deepcopy(window.project_documents))
        self.after=(deepcopy(graph),deepcopy(scene),deepcopy(window.project if project is None else project),
                    deepcopy(window.project_documents if documents is None else documents))

    def apply(self,state):
        document,scene,project,documents=state; window=self.window; adapter=window.adapter
        for key in ('type_definitions','retired_type_ids'):
            if key in project: window.project[key]=deepcopy(project[key])
            else: window.project.pop(key,None)
        window.project_documents=deepcopy(documents)
        window.scene=deepcopy(scene)
        adapter.scene_structs,adapter.scene_enums=deepcopy(scene.get('struct_definitions',[])),deepcopy(scene.get('enum_definitions',[]))
        adapter.struct_definitions=deepcopy(document.get('struct_definitions',[])); adapter.enum_definitions=deepcopy(document.get('enum_definitions',[]))
        adapter.registry=with_types(with_components(Registry(),scene.get('component_definitions',[])),*definitions(document,scene))
        adapter.configure_functions(document.get('functions',[]),document.get('event_definitions',[]))
        window._signature_change_pending=True; window._type_change_pending=True

    def redo(self): self.apply(self.after)
    def undo(self): self.apply(self.before)


def apply_type_edit(window,document,scene,*,project=None,documents=None):
    adapter=window.adapter; graph=adapter.graph
    selected={n.get_property('stable_id') for n in graph.selected_nodes()}
    failure=None; adapter.loading=True; graph.begin_undo('Edit structs and enums')
    try:
        for node in list(graph.all_nodes()): graph.delete_node(node)
        graph.undo_stack().push(TypeStateCommand(window,document,scene,project=project,documents=documents))
        mapping={}
        for data in document['nodes']:
            node=graph.create_node('obsidian.'+class_name(adapter.registry[data['type']]),name=data.get('label'),pos=data.get('position',[0,0]),selected=False)
            node.set_property('stable_id',str(data['id']),push_undo=False)
            node.set_property('embedded_code',data.get('code',''),push_undo=False)
            if adapter.registry[data['type']].kind=='switch':
                from editor.core.switches import default_cases
                from .switches import configure_node
                configure_node(node,data.get('cases',default_cases(adapter.registry[data['type']])),adapter.registry)
            for name,value in data.get('values',{}).items(): node.set_property('value_'+name,deepcopy(value),push_undo=False)
            node.set_property('selected',str(data['id']) in selected,push_undo=False); mapping[str(data['id'])]=node
        for link in document['links']:
            src,out=link['from']; dst,inp=link['to']; a,b=mapping[str(src)].outputs()[out],mapping[str(dst)].inputs()[inp]
            a.connect_to(b)
            if b not in a.connected_ports(): raise ValueError('Could not restore graph wire')
    except Exception as error: failure=error
    finally:
        graph.end_undo()
        if failure is not None:
            stack=graph.undo_stack(); stack.undo(); stack.command(stack.index()).setObsolete(True); stack.redo()
        adapter.loading=False
    window.finish_signature_edit()
    if failure is not None: raise ValueError('Type edit rolled back: '+str(failure)) from failure
