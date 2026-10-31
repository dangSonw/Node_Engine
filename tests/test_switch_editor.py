import json
from copy import deepcopy
from PySide6.QtWidgets import QApplication
from editor.ui.graph import GraphAdapter
from editor.ui.switches import SwitchCasesDialog
from editor.core.builder import GraphBuilder


def document():
    b=GraphBuilder(); b.add('start','On Game Start'); b.add('switch','Switch Integer')
    b.add('a','Print Log',Message='a'); b.add('b','Print Log',Message='b')
    b.connect('start','Out','switch','In').connect('switch','Case case_0','a','In').connect('switch','Case case_1','b','In')
    return b.graph


def find(adapter,nid):
    return next(n for n in adapter.graph.all_nodes() if n.get_property('stable_id')==nid)


def test_case_edits_keep_wires_and_undo_preceding_connections(app):
    a=GraphAdapter(); a.load(document()); original=a.document(); node=find(a,'switch')
    cases=[dict(id='case_1',value=42),dict(id='case_0',value=-1)]
    node=a.edit_switch_cases(node,cases); after=a.document()
    assert after['links']==original['links'] and list(node.outputs())==['Case case_1','Case case_0','Default']
    node=a.edit_switch_cases(node,cases[:1]); assert len(a.document()['links'])==2
    a.graph.undo_stack().undo(); assert a.document()==after
    a.graph.undo_stack().undo(); assert a.document()==original
    a.graph.undo_stack().redo(); a.graph.undo_stack().redo(); assert len(a.document()['links'])==2
    a.graph.undo_stack().undo(); a.graph.undo_stack().undo()
    # A connection command created before a case edit must still own live ports.
    find(a,'switch').outputs()['Default'].connect_to(find(a,'a').inputs()['In'])
    a.edit_switch_cases(find(a,'switch'),cases); a.graph.undo_stack().undo(); a.graph.undo_stack().undo()
    assert a.document()==original


def test_switch_roundtrip_duplicate_and_paste_keep_case_identity(app):
    a=GraphAdapter(); a.load(document()); a.edit_switch_cases(find(a,'switch'),[dict(id='case_0',value=17)])
    original=a.document(); reopened=GraphAdapter(); reopened.load(original); assert reopened.document()==original
    for node in a.graph.all_nodes(): node.set_selected(True)
    a.duplicate(); copies=a.document(); assert len(copies['nodes'])==8
    switches=[n for n in copies['nodes'] if n['type']==2015]; assert switches[0]['cases']==switches[1]['cases']
    a.graph.undo_stack().undo(); assert a.document()==original
    for node in a.graph.all_nodes(): node.set_selected(True)
    a.graph.copy_nodes(a.graph.selected_nodes()); clipboard=QApplication.clipboard().text()
    a.paste(); assert len(a.document()['nodes'])==8
    a.graph.undo_stack().undo(); assert a.document()==original
    corrupted=json.loads(clipboard); switch=next(n for n in corrupted['nodes'].values() if n['custom']['type_id']==2015)
    switch['output_ports'][0]['name']='forged'
    QApplication.clipboard().setText(json.dumps(corrupted)); errors=[]; a.diagnostic.connect(errors.append)
    a.paste(); assert a.document()==original and errors


def test_case_dialog_reorders_removes_and_rejects_duplicate_values(app):
    a=GraphAdapter(); n=a.add(2015); dialog=SwitchCasesDialog(a.registry[2015],n.get_property('switch_cases'))
    dialog.table.setCurrentCell(0,0); dialog.move(1); assert dialog.table.item(1,0).data(256)=='case_0'
    dialog.table.item(0,0).setText('0'); dialog.accept(); assert dialog.result()==0 and 'unique' in dialog.error.text()
    dialog.table.item(0,0).setText('999999999999999999999999'); dialog.accept(); assert dialog.result()==0
    dialog.remove_case(); dialog.table.item(0,0).setText('-7'); dialog.accept()
    assert dialog.result()==1 and dialog.cases==[dict(id='case_1',value=-7)]


def test_function_inspector_and_pure_library_support_new_nodes(app):
    from editor.core.functions import new_function
    from editor.core.document import default_scene
    from editor.ui.functions import FunctionEditorDialog
    from PySide6.QtWidgets import QPushButton
    f=new_function('Routes'); b=GraphBuilder(functions=[f],function=f['id']); b.add('entry','Function Input')
    b.add('switch','Switch String'); b.connect('entry','Out','switch','In'); f['graph']=b.graph
    dialog=FunctionEditorDialog([f],f['id'],default_scene()); node=find(dialog.adapter,'switch'); dialog.inspect(node)
    assert any(w.accessibleName()=='Edit Switch cases' for w in dialog.findChildren(QPushButton))
    dialog.adapter.edit_switch_cases(node,[dict(id='play',value='Play')]); assert dialog.inspected in dialog.adapter.graph.all_nodes()
    dialog.adapter.graph.undo_stack().undo(); assert dialog.inspected is None
    dialog.reject(); dialog.deleteLater()
    pure=new_function('Selection',pure=True,outputs=[dict(name='Result',type='int')])
    adapter=GraphAdapter(functions=[pure],current_function=pure['id'])
    assert len([s for s in adapter.available_specs() if s.kind=='select'])==40
    assert not any(s.kind=='switch' for s in adapter.available_specs())
