from copy import deepcopy
import pytest
from PySide6.QtCore import QSettings,Qt
from PySide6.QtWidgets import QDialog
from editor.core.function_edits import migrate_signature
from editor.core.functions import new_function,ENTRY,RETURN
from editor.core.compiler import compile_graph,GraphError
from editor.core.document import create_project,load_project,default_scene
from editor.ui.main_window import MainWindow
from editor.ui.functions import FunctionSignatureDialog,apply_signature_edit
from tests.test_functions import double_function,action_function,graph,port
from tests.test_core import node,link


def fixture():
    pure=double_function(); action=action_function(pure)
    doc=graph([node('start',1001),node('call',action['id'],Number=7),node('store',3111,Name='result'),node('direct',pure['id'],Number=3)],
        [link('start','Out','call','In'),link('call','Out','store','In'),link('call','Result','store','Value')],[pure,action])
    return doc,pure,action


def renamed(f):
    new=deepcopy(f); new['name']='Renamed '+f['name']; new['inputs'][0]['name']='Amount'; new['outputs'][0]['name']='Doubled'
    return new,dict(inputs={'Amount':'Number'},outputs={'Doubled':'Result'})


def test_rename_updates_nested_calls_and_entry_return_wires_without_mutation():
    doc,pure,action=fixture(); before=deepcopy(doc); new,origins=renamed(pure)
    after,impact=migrate_signature(doc,pure['id'],new,origins)
    assert doc==before and impact==dict(calls=2,graphs=2)
    assert after['nodes'][-1]['values']=={'Amount':3}
    assert link('entry','Amount','twice','A') in after['functions'][0]['graph']['links']
    assert link('twice','Value','return','Doubled') in after['functions'][0]['graph']['links']
    nested=after['functions'][1]['graph']
    assert link('entry','Number','double','Amount') in nested['links']
    assert link('double','Doubled','set','Value') in nested['links']
    assert [f['id'] for f in after['functions']]==[pure['id'],action['id']]
    compile_graph(after)


def test_simultaneous_name_swap_and_order_preserve_port_identity():
    f=new_function('Pair',[port('A','int'),port('B','int')],[port('First','int'),port('Second','int')],True)
    f['graph']['links']=[link('entry','A','return','First'),link('entry','B','return','Second')]
    doc=graph([node('pair',f['id'],A=2,B=9)],functions=[f]); new=deepcopy(f)
    new['inputs']=[port('B','int'),port('A','int')]; new['outputs']=[port('Second','int'),port('First','int')]
    after,_=migrate_signature(doc,f['id'],new,dict(inputs={'B':'A','A':'B'},outputs={'Second':'First','First':'Second'}))
    assert after['nodes'][0]['values']=={'B':2,'A':9}
    assert after['functions'][0]['graph']['links']==[link('entry','B','return','Second'),link('entry','A','return','First')]
    compile_graph(after)


@pytest.mark.parametrize('side',['inputs','outputs'])
def test_connected_port_removal_is_transactional(side):
    doc,pure,_=fixture(); before=deepcopy(doc); candidate=deepcopy(pure)
    candidate[side]=[port('Replacement','int')]
    with pytest.raises(GraphError,match='Cannot remove'): migrate_signature(doc,pure['id'],candidate,dict(inputs={},outputs={}))
    assert doc==before


def test_type_change_checks_call_literals_and_all_body_links():
    doc,pure,_=fixture(); new=deepcopy(pure); new['inputs'][0]['type']='float'
    with pytest.raises(GraphError,match='Type mismatch'): migrate_signature(doc,pure['id'],new)
    f=new_function('Identity',[port('A','float')],[port('B','float')],True)
    f['graph']['links']=[link('entry','A','return','B')]
    f['graph']['nodes'][1]['values']={'B':0.}
    doc=graph([node('call',f['id'],A=0.)],functions=[f]); new=deepcopy(f)
    new['inputs'][0]['type']=new['outputs'][0]['type']='int'
    after,_=migrate_signature(doc,f['id'],new); assert after['nodes'][0]['values']=={'A':0}
    assert type(after['nodes'][0]['values']['A']) is int
    doc['nodes'][0]['values']['A']=2.5
    with pytest.raises(GraphError,match='authored value'): migrate_signature(doc,f['id'],new)


def test_new_ports_and_defaults_keep_existing_call_values():
    doc,pure,_=fixture(); new=deepcopy(pure); new['inputs'][0]['default']=100
    new['inputs'].append(dict(name='Unused',type='string',default='Việt'))
    after,_=migrate_signature(doc,pure['id'],new)
    assert after['nodes'][-1]['values']=={'Number':3,'Unused':'Việt'}
    reduced=deepcopy(new); reduced['inputs'].pop()
    restored,_=migrate_signature(after,pure['id'],reduced)
    assert restored['nodes'][-1]['values']=={'Number':3}
    after['nodes'][-1]['values']['Unused']='authored'
    with pytest.raises(GraphError,match='authored value'): migrate_signature(after,pure['id'],reduced)


@pytest.mark.parametrize('bad',['id','kind','unknown_origin','duplicate_origin'])
def test_reject_invalid_identity_or_mapping(bad):
    doc,pure,_=fixture(); new,origins=renamed(pure)
    if bad=='id': new['id']+=1
    if bad=='kind': new['pure']=False
    if bad=='unknown_origin': origins['inputs']['Amount']='missing'
    if bad=='duplicate_origin':
        new['inputs'].append(port('Other','int')); origins['inputs']['Other']='Number'
    with pytest.raises(ValueError): migrate_signature(doc,pure['id'],new,origins)


def test_unchanged_signature_does_not_materialize_implicit_defaults():
    doc,pure,_=fixture(); new=deepcopy(pure); new['inputs'][0]['default']=0
    after,impact=migrate_signature(doc,pure['id'],new)
    assert after==doc and impact==dict(calls=0,graphs=0)


def test_return_literals_migrate_and_cannot_be_silently_discarded():
    f=new_function('Constant',outputs=[port('Value','int')],pure=True)
    f['graph']['nodes'][1]['values']={'Value':23}
    doc=graph([],functions=[f]); new=deepcopy(f); new['outputs'][0]['name']='Result'
    after,_=migrate_signature(doc,f['id'],new,dict(inputs={},outputs={'Result':'Value'}))
    assert after['functions'][0]['graph']['nodes'][1]['values']=={'Result':23}
    with pytest.raises(GraphError,match='authored value'):
        migrate_signature(doc,f['id'],new,dict(inputs={},outputs={}))


def test_dialog_tracks_origins_through_reorder_and_blocks_invalid_edits(app):
    doc,pure,_=fixture()
    dialog=FunctionSignatureDialog(doc['functions'],function_id=pure['id'],
        validator=lambda f,o:migrate_signature(doc,pure['id'],f,o))
    assert not dialog.pure.isEnabled()
    table=dialog.tables['inputs']; table.item(0,0).setText('Amount'); dialog.add_port('inputs','Extra','string','text')
    table.setCurrentCell(1,0); dialog.move_port('inputs',-1)
    assert table.item(1,0).data(Qt.ItemDataRole.UserRole)=='Number'
    dialog.tables['outputs'].item(0,0).setText('Doubled'); dialog.name_field.setText('New name'); dialog.accept()
    assert dialog.result()==QDialog.DialogCode.Accepted and dialog.definition['id']==pure['id']
    assert dialog.port_origins['inputs']=={'Amount':'Number'} and dialog.result_document['functions'][0]['inputs'][0]['name']=='Extra'
    dialog.deleteLater()
    blocked=FunctionSignatureDialog(doc['functions'],function_id=pure['id'],validator=lambda f,o:migrate_signature(doc,pure['id'],f,o))
    blocked.tables['inputs'].removeRow(0); blocked.accept()
    assert blocked.result()!=QDialog.DialogCode.Accepted and blocked.result_document is None and 'Cannot remove' in blocked.error.text()
    blocked.reject(); blocked.deleteLater()


def test_signature_undo_retains_prior_node_history_and_save_reopen(app,tmp_path):
    path=create_project(tmp_path/'game','Functions'); w=MainWindow(path,QSettings(str(tmp_path/'layout.ini'),QSettings.IniFormat))
    doc,_,action=fixture(); w.adapter.load(doc)
    try:
        call=next(n for n in w.adapter.graph.all_nodes() if n.get_property('stable_id')=='call')
        call.set_property('value_Number',11)
        before=w.adapter.document(); candidate,origins=renamed(action)
        after,_=migrate_signature(before,action['id'],candidate,origins,w.scene)
        after['links'].sort(key=lambda edge:(edge['from'],edge['to']))
        stack=w.adapter.graph.undo_stack(); count=stack.count()
        apply_signature_edit(w,after,action['id'])
        assert stack.count()==count+1 and w.adapter.document()==after
        changed=next(n for n in w.adapter.graph.all_nodes() if n.get_property('stable_id')=='call')
        assert set(changed.inputs())=={'In','Amount'} and set(changed.outputs())=={'Out','Doubled'}
        stack.undo(); assert w.adapter.document()==before
        stack.undo(); assert call.get_property('value_Number')==7
        stack.redo(); assert w.adapter.document()==before
        stack.redo(); assert w.adapter.document()==after
        fresh=w.adapter.add(action['id']); assert 'Amount' in fresh.inputs() and 'Number' not in fresh.inputs()
        stack.undo(); assert w.adapter.document()==after
        assert w.save_project(); assert load_project(path)[1]==after
        w.open_project(path); assert w.adapter.document()==after
        assert w.validate_graph()
    finally:
        w.dirty=False; w.close(); w.deleteLater()


def test_failed_canvas_edit_rolls_back_and_keeps_previous_history(app,tmp_path,monkeypatch):
    path=create_project(tmp_path/'game','Functions'); w=MainWindow(path,QSettings(str(tmp_path/'layout.ini'),QSettings.IniFormat))
    doc,_,action=fixture(); w.adapter.load(doc)
    try:
        call=next(n for n in w.adapter.graph.all_nodes() if n.get_property('stable_id')=='call')
        call.set_property('value_Number',11); before=w.adapter.document(); count=w.adapter.graph.undo_stack().count()
        candidate,origins=renamed(action); after,_=migrate_signature(before,action['id'],candidate,origins,w.scene)
        def fail(*args,**kwargs): raise ValueError('Injected canvas creation failure')
        monkeypatch.setattr(w.adapter.graph,'create_node',fail)
        with pytest.raises(ValueError,match='rolled back'): apply_signature_edit(w,after,action['id'])
        assert w.adapter.document()==before and w.adapter.graph.undo_stack().count()==count
        w.adapter.graph.undo_stack().undo(); assert call.get_property('value_Number')==7
        w.adapter.graph.undo_stack().redo(); assert w.adapter.document()==before
    finally:
        w.dirty=False; w.close(); w.deleteLater()
