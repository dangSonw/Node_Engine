"""Nominal collection schema, authoring, callback contracts and project refactors."""
from copy import deepcopy
import pytest
from editor.core.builder import GraphBuilder
from editor.core.typed_schema import build_schema
from editor.core.compiler import GraphError
from editor.core.codegen import CppEmitter
from editor.core.type_edits import edit_type,stable_definitions
from editor.core.project_types import synchronize_types
from editor.core.document import default_scene
from editor.core.functions import new_function
from editor.ui.graph import GraphAdapter
from PySide6.QtCore import QSettings,QTimer
from PySide6.QtWidgets import QApplication
from editor.ui.main_window import MainWindow
from editor.ui.variables import VariablesDialog
from editor.core.document import create_project,load_project


def definitions():
    return [dict(name='Stats',fields=[dict(name='hp',type='int',default=7)])],[dict(name='Mode',values=['Idle','Run'])]


@pytest.mark.parametrize('kind,value',[('array',[{'hp':3}]),('map',{'a':{'hp':3}}),('set',[{'hp':3}])])
def test_collection_schema_defaults_nested_fields_and_invalid_values(kind,value):
    structs,enums=definitions(); structs.append(dict(name='Bag',fields=[dict(name='items',type=f'{kind}<struct:Stats>')]))
    schema=build_schema(structs,enums)
    assert schema.is_type(f'{kind}<struct:Stats>') and schema.literal_valid(value,f'{kind}<struct:Stats>')
    assert schema.default_value('struct:Bag')=={'items':{} if kind=='map' else []}
    assert not schema.literal_valid([{'hp':'bad'}],f'{kind}<struct:Stats>')
    assert not schema.is_type(f'{kind}<struct:Missing>')
    assert not schema.is_type('array<array<struct:Stats>>')
    assert not schema.literal_valid(['Wrong'],'array<enum:Mode>')


def test_recursive_collection_structs_and_duplicate_nominal_set_elements_are_rejected():
    with pytest.raises(ValueError,match='Recursive'):
        build_schema([dict(name='Loop',fields=[dict(name='children',type='array<struct:Loop>')])],[])
    schema=build_schema(*definitions())
    assert not schema.literal_valid([{'hp':3},{'hp':3}],'set<struct:Stats>')
    assert schema.literal_valid([],'array<struct:Stats>')


def test_collection_nodes_have_stable_ids_and_native_codegen_and_exact_ports(app):
    structs,enums=stable_definitions(*definitions())
    b=GraphBuilder(struct_definitions=structs,enum_definitions=enums)
    b.add('start','On Game Start'); b.add('append','Append Stats Item',Array=[],Item={'hp':3})
    b.add('save','Set Stats Array Variable',Name='items')
    b.connect('start','Out','save','In').connect('append','Value','save','Value')
    assert all(n['type']<0 for n in b.graph['nodes'][1:])
    code=CppEmitter().generate(b.compile())
    assert 'UserCollectionValue' in code and 'DispatchUserCollection' in code
    adapter=GraphAdapter(struct_definitions=structs,enum_definitions=enums); adapter.load(b.graph)
    try:
        append=next(n for n in adapter.graph.all_nodes() if n.get_property('stable_id')=='append')
        matches=adapter.compatible_ports(append.outputs()['Value'])
        assert matches and all(p.type=='array<struct:Stats>' for s,p in matches)
        assert adapter.document()['struct_definitions']==b.graph['struct_definitions']
    finally: adapter.deleteLater()


def test_refactor_migrates_collection_ports_literals_defaults_and_ids():
    structs,enums=definitions(); schema=build_schema(structs,enums)
    f=new_function('Identity',[dict(name='Items',type='array<struct:Stats>',default=[{'hp':8}])],
        [dict(name='Result',type='array<struct:Stats>')],pure=True,schema=schema)
    f['graph']['links']=[{'from':['entry','Items'],'to':['return','Result']}]
    b=GraphBuilder(struct_definitions=structs,enum_definitions=enums,functions=[f])
    b.add('start','On Game Start'); b.add('append','Append Stats Item',Array=[{'hp':3}],Item={'hp':4})
    b.add('save','Set Stats Array Variable',Name='items'); b.connect('start','Out','save','In').connect('append','Value','save','Value')
    scene=default_scene(); scene['struct_definitions']=structs; scene['enum_definitions']=enums
    scene['variables']={'lookup':dict(type='map<struct:Stats>',value={'a':{'hp':6}})}
    graph,changed=edit_type(b.graph,scene,'struct',dict(name='Vitals',fields=[dict(name='health',type='int',default=7)]),
                            original='Stats',origins=dict(health='hp'))
    assert graph['nodes'][1]['type']==b.graph['nodes'][1]['type']
    assert graph['nodes'][1]['values']==dict(Array=[dict(health=3)],Item=dict(health=4))
    assert graph['functions'][0]['inputs'][0]['type']=='array<struct:Vitals>'
    assert changed['variables']['lookup']==dict(type='map<struct:Vitals>',value={'a':dict(health=6)})


def test_enum_collection_labels_refactor_in_variables_and_node_literals():
    structs,enums=definitions();b=GraphBuilder(struct_definitions=structs,enum_definitions=enums)
    b.add('start','On Game Start');b.add('set','Set Mode Set Variable',Name='modes',Value=['Run','Idle'])
    b.connect('start','Out','set','In')
    scene=default_scene();scene['variables']={'queued':dict(type='array<enum:Mode>',value=['Run','Idle'])}
    scene['struct_definitions'],scene['enum_definitions']=structs,enums
    graph,changed=edit_type(b.graph,scene,'enum',dict(name='State',values=['Idle','Sprint']),
        original='Mode',origins=dict(Idle='Idle',Sprint='Run'))
    assert graph['nodes'][1]['values']['Value']==['Sprint','Idle']
    assert changed['variables']['queued']==dict(type='array<enum:State>',value=['Sprint','Idle'])


def test_variable_dialog_copies_graph_owned_element_schema_into_scene(app,tmp_path):
    path=create_project(tmp_path/'Game','Graph-owned types')
    window=MainWindow(path,QSettings(str(tmp_path/'settings.ini'),QSettings.Format.IniFormat))
    structs,enums=definitions(); b=GraphBuilder(struct_definitions=structs,enum_definitions=enums)
    window.adapter.load(b.graph)
    checks=[]
    def enter():
        dialog=QApplication.activeModalWidget()
        try:
            assert isinstance(dialog,VariablesDialog)
            assert 'array<struct:Stats>' in dialog.type_delegate.types
            dialog.add_row('items','array<struct:Stats>',[dict(hp=42)])
            dialog.accept();checks.append(dialog.result())
        finally:
            if not checks: dialog.reject()
    try:
        QTimer.singleShot(0,enter);window.edit_variables()
        assert checks and window.scene['struct_definitions'][0]['name']=='Stats'
        assert window.save_project() and load_project(path)[2]['variables']['items']['value']==[dict(hp=42)]
    finally:
        window.dirty=False;window.close();window.deleteLater()
