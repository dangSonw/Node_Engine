from copy import deepcopy
import json
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QLineEdit, QDialog
from editor.core.typed_schema import build_schema
from editor.core.functions import new_function,signatures
from editor.core.events import new_event
from editor.core.builder import GraphBuilder
from editor.core.compiler import compile_graph,GraphError
from editor.core.document import create_project,save_json,default_scene
from editor.core.function_edits import migrate_signature
from editor.core.event_edits import migrate_event_signature
from editor.core.function_extraction import extract_function
from editor.core.type_edits import edit_type
from editor.core.codegen import CppEmitter
from editor.ui.functions import FunctionSignatureDialog,FunctionEditorDialog
from editor.ui.events import EventSignatureDialog
from editor.ui.main_window import MainWindow


def types():
    structs=[dict(name='Stats',fields=[dict(name='hp',type='int',default=7)])]
    enums=[dict(name='Mode',values=['Idle','Run'])]
    return structs,enums,build_schema(structs,enums)


def echo(*,pure=True):
    structs,enums,schema=types()
    f=new_function('Echo',inputs=[dict(name='Stats',type='struct:Stats'),dict(name='Mode',type='enum:Mode')],
                   outputs=[dict(name='Result',type='struct:Stats'),dict(name='State',type='enum:Mode')],pure=pure,schema=schema)
    body=GraphBuilder(functions=[f],function=f['id'],struct_definitions=structs,enum_definitions=enums)
    body.add('entry','Function Input'); body.add('return','Function Output')
    body.connect('entry','Stats','return','Result').connect('entry','Mode','return','State')
    if not pure: body.connect('entry','Out','return','In')
    f['graph']=body.graph
    return f,structs,enums


def root():
    f,structs,enums=echo()
    event=new_event('Stats ready',[dict(name='Data',type='struct:Stats'),dict(name='State',type='enum:Mode')],schema=build_schema(structs,enums))
    b=GraphBuilder(functions=[f],event_definitions=[event],struct_definitions=structs,enum_definitions=enums)
    b.add('start','On Game Start'); b.add('call','Echo',Stats=dict(hp=42),Mode='Run')
    b.add('send','Broadcast Stats ready'); b.connect('start','Out','send','In')
    b.connect('call','Result','send','Data').connect('call','State','send','State')
    b.add('event','On Stats ready'); b.add('save','Set Stats Variable',Name='stats')
    b.connect('event','Out','save','In').connect('event','Data','save','Value')
    return b,f,event


def test_named_ports_compile_defaults_and_codegen():
    b,f,event=root(); ir=b.compile()
    spec=b.registry[f['id']]
    assert [p.default for p in spec.data_inputs]==[dict(hp=7),'Idle']
    code=CppEmitter().generate(ir)
    assert 'ValidateTypedValue' in code and 'struct:Stats' in code and 'enum:Mode' in code
    for damage in (lambda f:f['inputs'][0].update(type='struct:Unknown'),
                   lambda f:f['inputs'][0].update(default=dict(hp='bad')),
                   lambda f:f['inputs'][1].update(default='Bad')):
        changed=deepcopy(f); damage(changed)
        with pytest.raises(ValueError): signatures([changed],build_schema(*types()[:2]))
    with pytest.raises(ValueError): signatures([f])


def test_named_signature_migration_and_type_refactor_preserve_values_and_wires():
    b,f,event=root()
    replacement=deepcopy(f); replacement['inputs'][0]['name']='Actor'
    doc,_=migrate_signature(b.graph,f['id'],replacement,dict(inputs={'Actor':'Stats','Mode':'Mode'},outputs={'Result':'Result','State':'State'}))
    assert next(n for n in doc['nodes'] if n['id']=='call')['values']['Actor']==dict(hp=42)
    new_event=deepcopy(event); new_event['parameters'][0]['name']='Payload'
    doc,_=migrate_event_signature(doc,event['id'],new_event,dict(Payload='Data',State='State'))
    doc,scene=edit_type(doc,default_scene(),'struct',dict(name='Vitals',fields=[dict(name='health',type='int',default=7)]),
                        original='Stats',origins=dict(health='hp'))
    assert doc['functions'][0]['inputs'][0]['type']=='struct:Vitals'
    assert doc['event_definitions'][0]['parameters'][0]['type']=='struct:Vitals'
    assert next(n for n in doc['nodes'] if n['id']=='call')['values']['Actor']==dict(health=42)
    compile_graph(doc,scene)


def test_type_refactor_migrates_function_return_literals():
    f,structs,enums=echo(pure=False)
    f['graph']['links']=[link for link in f['graph']['links'] if link['to'][1] not in ('Result','State')]
    next(n for n in f['graph']['nodes'] if n['id']=='return')['values']=dict(Result=dict(hp=24),State='Run')
    b=GraphBuilder(functions=[f],struct_definitions=structs,enum_definitions=enums)
    doc,scene=edit_type(b.graph,default_scene(),'struct',dict(name='Vitals',fields=[dict(name='health',type='int',default=7)]),
                        original='Stats',origins=dict(health='hp'))
    assert next(n for n in doc['functions'][0]['graph']['nodes'] if n['id']=='return')['values']['Result']==dict(health=24)
    compile_graph(doc,scene)


def test_extract_nominal_result_and_event_capture():
    b,f,event=root()
    source=deepcopy(b.graph)
    source['links']=[link for link in source['links'] if link['to']!=['send','State']]
    doc,info=extract_function(source,['call'],'Extract Echo')
    assert info['pure'] and any(port['type']=='struct:Stats' for port in info['outputs'])
    doc,info=extract_function(b.graph,['save'],'Capture payload')
    assert not info['pure'] and any(port['type']=='struct:Stats' for port in info['inputs'])
    compile_graph(doc)


def test_signature_dialog_named_defaults_and_rejection(app):
    structs,enums,schema=types()
    dialog=FunctionSignatureDialog([],schema=schema)
    dialog.add_port('inputs','Stats','struct:Stats'); dialog.add_port('outputs','State','enum:Mode')
    assert json.loads(dialog.tables['inputs'].item(0,2).text())==dict(hp=7)
    dialog.tables['inputs'].item(0,2).setText('{"hp":"bad"}')
    dialog.accept(); assert dialog.result()!=QDialog.DialogCode.Accepted and 'invalid default' in dialog.error.text()
    dialog.tables['inputs'].item(0,2).setText('{"hp":42}'); dialog.accept()
    assert dialog.definition['inputs'][0]['default']==dict(hp=42)
    event=EventSignatureDialog([],schema=schema); event.add_port('inputs','Mode','enum:Mode'); event.accept()
    assert event.definition['parameters'][0]['default']=='Idle'
    dialog.deleteLater(); event.deleteLater()


def test_named_function_editor_and_inspector_save_reopen(app,tmp_path):
    b,f,event=root(); path=create_project(tmp_path/'named','Named ports')
    save_json(path.parent/'graphs/gameplay.json',b.graph)
    window=MainWindow(path,QSettings(str(tmp_path/'settings.ini'),QSettings.Format.IniFormat))
    try:
        node=next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')=='call')
        window.inspect_node(node)
        field=next(w for w in window.inspector.findChildren(QLineEdit) if w.property('domain_property')=='value_Stats')
        field.setText('{"bad":1}'); field.editingFinished.emit()
        assert node.get_property('value_Stats')==dict(hp=42)
        field.setText('{"hp":24}'); field.editingFinished.emit()
        assert window.save_project() and window.open_project(path)
        scene=deepcopy(window.scene); scene['struct_definitions']=b.graph['struct_definitions']; scene['enum_definitions']=b.graph['enum_definitions']
        dialog=FunctionEditorDialog(window.adapter.functions,f['id'],scene,window,event_definitions=window.adapter.event_definitions)
        assert dialog.adapter.registry.by_name('Function Input').outputs[0].type=='struct:Stats'
        assert dialog.validate_functions()
        dialog.reject(); dialog.deleteLater()
    finally:
        window.dirty=False; window.close(); window.deleteLater()
