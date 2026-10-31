from copy import deepcopy
import pytest
from PySide6.QtCore import QSettings,Qt
from PySide6.QtWidgets import QDialog
from editor.core.builder import GraphBuilder
from editor.core.events import node_id
from editor.core.event_edits import migrate_event_signature
from editor.core.functions import new_function
from editor.core.compiler import compile_graph,GraphError
from editor.core.document import create_project,load_project,default_scene
from editor.ui.events import EventSignatureDialog,apply_event_signature_edit
from editor.ui.main_window import MainWindow
from tests.test_events import event
from tests.test_core import link


def fixture():
    e=event('Message',[dict(name='Number',type='int',default=7),dict(name='Note',type='string',default='old')])
    f=new_function('Publish',[dict(name='Value',type='int')]); f['id']=1000001
    b=GraphBuilder(functions=[f],function=f['id'],event_definitions=[e]); b.add('entry','Function Input'); b.add('nested','Broadcast Message')
    b.connect('entry','Out','nested','In').connect('entry','Value','nested','Number'); f['graph']=b.graph
    b=GraphBuilder(functions=[f],event_definitions=[e]); b.add('start','On Game Start'); b.add('send','Send Message',Number=23,Sender='player')
    b.add('on','On Message'); b.add('save','Set Integer Variable',Name='answer'); b.add('source','Set Entity Variable',Name='sender')
    b.add('subscribe','Subscribe Message'); b.add('unsubscribe','Unsubscribe Message'); b.add('call','Publish',Value=17)
    b.connect('start','Out','send','In').connect('send','Out','subscribe','In').connect('subscribe','Out','call','In')
    b.connect('on','Out','save','In').connect('on','Number','save','Value').connect('save','Out','source','In').connect('on','Sender','source','Value')
    for n in b.graph['nodes']: n['label']=b.registry[n['type']].name
    return b.graph,e


def renamed(e):
    e=deepcopy(e); e['name']='Notice'; e['parameters']=[dict(name='Text',type='string',default='new'),dict(name='Amount',type='int',default=3)]
    return e,{'Text':'Note','Amount':'Number'}


def test_all_roles_nested_senders_and_fixed_ports_migrate_without_mutation():
    doc,e=fixture(); before=deepcopy(doc); new,origins=renamed(e)
    edited,impact=migrate_event_signature(doc,e['id'],new,origins,default_scene())
    assert doc==before and impact==dict(nodes=5,graphs=2)
    nodes={n['id']:n for n in edited['nodes']}
    assert nodes['send']['values']=={'Amount':23,'Text':'old','Sender':'player'}
    assert nodes['on']['values']=={} and nodes['subscribe']['label']=='Subscribe Notice' and nodes['unsubscribe']['label']=='Unsubscribe Notice'
    assert nodes['send']['type']==node_id(e['id'],'send') and nodes['on']['label']=='On Notice'
    assert link('on','Amount','save','Value') in edited['links'] and link('on','Sender','source','Value') in edited['links']
    assert link('entry','Value','nested','Amount') in edited['functions'][0]['graph']['links']
    compile_graph(edited,default_scene())


def test_parameter_name_swap_retains_identity_and_custom_labels():
    doc,e=fixture(); new=deepcopy(e); new['parameters'][0]['name']='Note'; new['parameters'][1]['name']='Number'
    doc['nodes'][1]['label']='Keep this label'
    edited,_=migrate_event_signature(doc,e['id'],new,{'Note':'Number','Number':'Note'})
    assert edited['nodes'][1]['values']=={'Note':23,'Number':'old','Sender':'player'}
    assert edited['nodes'][1]['label']=='Keep this label'
    assert link('on','Note','save','Value') in edited['links']


@pytest.mark.parametrize('location',['handler','nested_sender','literal'])
def test_removal_protects_wires_and_authored_values(location):
    doc,e=fixture(); new=deepcopy(e)
    if location=='literal':
        new['parameters']=[p for p in e['parameters'] if p['name']!='Note']; doc['nodes'][1]['values']['Note']='authored'
    else:
        for n in doc['nodes']:
            if n['id']=='send': n['values']['Number']=7
        if location=='nested_sender': doc['links']=[l for l in doc['links'] if l['from']!=['on','Number']]
        new['parameters']=[p for p in e['parameters'] if p['name']!='Number']
    before=deepcopy(doc)
    with pytest.raises(GraphError,match='Cannot remove'): migrate_event_signature(doc,e['id'],new)
    assert doc==before


def test_add_remove_defaults_preserve_existing_values():
    doc,e=fixture(); new=deepcopy(e); new['parameters'][0]['default']=100
    new['parameters'].append(dict(name='Unused',type='array<int>',default=[1,2]))
    edited,_=migrate_event_signature(doc,e['id'],new)
    assert edited['nodes'][1]['values']['Number']==23 and edited['nodes'][1]['values']['Unused']==[1,2]
    assert edited['functions'][0]['graph']['nodes'][1]['values']['Number']==7
    reduced=deepcopy(new); reduced['parameters'].pop(); reduced['parameters'].pop(1)
    edited,_=migrate_event_signature(edited,e['id'],reduced)
    assert edited['nodes'][1]['values']=={'Number':23,'Sender':'player'}


def test_types_validate_every_wire_and_authored_literal():
    doc,e=fixture(); new=deepcopy(e); new['parameters'][0]['type']='float'
    with pytest.raises(GraphError,match='Type mismatch'): migrate_event_signature(doc,e['id'],new)
    e=event(parameters=[dict(name='Value',type='float',default=0.)]); b=GraphBuilder(event_definitions=[e]); b.add('send','Send Ping')
    new=deepcopy(e); new['parameters'][0]=dict(name='Value',type='int',default=4)
    edited,_=migrate_event_signature(b.graph,e['id'],new); assert edited['nodes'][0]['values']['Value']==4
    b.graph['nodes'][0]['values']['Value']=2.5
    with pytest.raises(GraphError,match='authored value'): migrate_event_signature(b.graph,e['id'],new)


@pytest.mark.parametrize('bad',['id','unknown','duplicate','reserved','origins_type','unknown_event'])
def test_invalid_signature_and_parameter_mapping(bad):
    doc,e=fixture(); new,origins=renamed(e); eid=e['id']
    if bad=='id': new['id']+=1
    if bad=='unknown': origins['Amount']='Missing'
    if bad=='duplicate': origins['Text']='Number'
    if bad=='reserved': new['parameters'][0]['name']='Sender'
    if bad=='origins_type': origins=[]
    if bad=='unknown_event': eid+=1
    with pytest.raises(ValueError): migrate_event_signature(doc,eid,new,origins)


def test_unchanged_signature_does_not_materialize_defaults():
    doc,e=fixture(); new=deepcopy(e)
    edited,impact=migrate_event_signature(doc,e['id'],new)
    assert edited==doc and impact==dict(nodes=0,graphs=0)


def test_dialog_tracks_reordered_parameters_and_validates_without_side_effects(app):
    doc,e=fixture(); original=deepcopy(doc)
    dialog=EventSignatureDialog([e],event_id=e['id'],validator=lambda d,o:migrate_event_signature(doc,e['id'],d,o['inputs']))
    table=dialog.tables['inputs']; assert table.rowCount()==2 and len(dialog.tables)==1
    table.item(0,0).setText('Amount'); table.setCurrentCell(1,0); dialog.move_port('inputs',-1)
    assert table.item(1,0).data(Qt.ItemDataRole.UserRole)=='Number'
    dialog.name_field.setText('Notice'); dialog.accept()
    assert dialog.result()==QDialog.DialogCode.Accepted and dialog.port_origins['inputs']=={'Note':'Note','Amount':'Number'}
    assert dialog.definition['id']==e['id'] and doc==original; dialog.deleteLater()
    dialog=EventSignatureDialog([e],event_id=e['id'],validator=lambda d,o:migrate_event_signature(doc,e['id'],d,o['inputs']))
    dialog.tables['inputs'].removeRow(0); dialog.accept()
    assert dialog.result()!=QDialog.DialogCode.Accepted and 'Cannot remove' in dialog.error.text()
    dialog.reject(); assert doc==original; dialog.deleteLater()


def test_canvas_undo_older_edits_nested_definitions_and_save_reopen(app,tmp_path):
    doc,e=fixture(); path=create_project(tmp_path/'game','Events'); w=MainWindow(path,QSettings(str(tmp_path/'ui.ini'),QSettings.IniFormat))
    try:
        w.adapter.load(doc); original=next(n for n in w.adapter.graph.all_nodes() if n.get_property('stable_id')=='send')
        original.set_property('value_Number',31); before=w.adapter.document(); count=w.adapter.graph.undo_stack().count()
        new,origins=renamed(e); after,_=migrate_event_signature(before,e['id'],new,origins,w.scene)
        after['links'].sort(key=lambda x:(x['from'],x['to'])); apply_event_signature_edit(w,after,e['id'])
        assert w.adapter.document()==after and w.adapter.graph.undo_stack().count()==count+1
        w.adapter.graph.undo_stack().undo(); assert w.adapter.document()==before
        w.adapter.graph.undo_stack().undo(); assert original.get_property('value_Number')==23
        w.adapter.graph.undo_stack().redo(); w.adapter.graph.undo_stack().redo(); assert w.adapter.document()==after
        fresh=w.adapter.add(node_id(e['id'],'send')); assert fresh.get_property('value_Amount')==3 and fresh.get_property('value_Text')=='new'
        w.adapter.graph.undo_stack().undo(); assert w.adapter.document()==after
        assert w.save_project() and load_project(path)[1]==after
        w.open_project(path); assert w.adapter.document()==after and w.validate_graph()
    finally: w.dirty=False; w.close(); w.deleteLater()


def test_canvas_failure_rolls_back_events_functions_and_prior_history(app,tmp_path,monkeypatch):
    doc,e=fixture(); path=create_project(tmp_path/'game','Events'); w=MainWindow(path,QSettings(str(tmp_path/'ui.ini'),QSettings.IniFormat))
    try:
        w.adapter.load(doc); original=next(n for n in w.adapter.graph.all_nodes() if n.get_property('stable_id')=='send')
        original.set_property('value_Number',31); before=w.adapter.document(); stack=w.adapter.graph.undo_stack(); count=stack.count()
        new,origins=renamed(e); after,_=migrate_event_signature(before,e['id'],new,origins,w.scene)
        monkeypatch.setattr(w.adapter.graph,'create_node',lambda *a,**k:(_ for _ in ()).throw(ValueError('Injected creation failure')))
        with pytest.raises(ValueError,match='rolled back'): apply_event_signature_edit(w,after,e['id'])
        assert w.adapter.document()==before and stack.count()==count
        stack.undo(); assert original.get_property('value_Number')==23
        stack.redo(); assert w.adapter.document()==before
    finally: w.dirty=False; w.close(); w.deleteLater()


def test_current_scene_migration_leaves_identical_event_id_in_other_scene_unchanged(app,tmp_path):
    from editor.core.document import save_json
    from editor.core.projects import add_scene,compile_project
    doc,e=fixture(); path=create_project(tmp_path/'game','Two scenes')
    save_json(path.parent/'graphs/gameplay.json',doc); add_scene(path,'level'); other=path.parent/'graphs/level.json'
    save_json(other,doc); saved_other=other.read_bytes()
    w=MainWindow(path,QSettings(str(tmp_path/'ui.ini'),QSettings.IniFormat))
    try:
        new,origins=renamed(e); after,_=migrate_event_signature(w.adapter.document(),e['id'],new,origins,w.scene)
        apply_event_signature_edit(w,after,e['id']); programs=compile_project(w.snapshot_project())['scenes']
        assert programs['main']['event_definitions'][0]['name']=='Notice'
        assert programs['level']['event_definitions'][0]['name']=='Message'
        assert w.save_project() and other.read_bytes()==saved_other
        assert w.switch_scene('level') and w.adapter.event_definitions==[e]
        assert w.switch_scene('main') and w.adapter.event_definitions==[new]
    finally: w.dirty=False; w.close(); w.deleteLater()
