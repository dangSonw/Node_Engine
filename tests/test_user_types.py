from copy import deepcopy
import pytest
from editor.core.builder import GraphBuilder
from editor.core.compiler import GraphError
from editor.core.typed_schema import build_schema
from editor.ui.graph import GraphAdapter


def definitions():
    return [dict(name='Stats', fields=[dict(name='hp', type='int')])], [dict(name='Mode', values=['Idle','Run'])]


def test_schema_defaults_do_not_mutate_authored_definitions():
    structs,enums=definitions(); before=deepcopy(structs)
    schema=build_schema(structs,enums)
    assert structs==before
    assert schema.default_value('struct:Stats')==dict(hp=0)
    assert not schema.is_type('array<array<int>>')
    assert not schema.is_type('array<struct:Stats>')
    assert not schema.is_type('array<float')
    assert not schema.literal_valid(1,'enum:Mode')
    assert not schema.literal_valid({'\ud800':1},'map<int>')


@pytest.mark.parametrize('structs',[
    [dict(name='Loop',fields=[dict(name='again',type='struct:Loop')])],
    [dict(name='A',fields=[dict(name='b',type='struct:B')]),dict(name='B',fields=[dict(name='a',type='struct:A')])],
])
def test_recursive_structs_report_validation_error(structs):
    with pytest.raises(ValueError,match='Recursive Struct'):
        build_schema(structs,[])


def test_struct_literals_and_enum_constants_follow_schema():
    structs,enums=definitions()
    b=GraphBuilder(struct_definitions=structs,enum_definitions=enums)
    b.add('start','On Game Start'); b.add('save','Set Stats Variable',Name='stats',Value={'unknown':3})
    b.connect('start','Out','save','In')
    with pytest.raises(GraphError,match='requires struct:Stats'):
        b.compile()
    b=GraphBuilder(enum_definitions=enums); b.add('start','On Game Start')
    b.add('make','Make Mode',Value='Missing'); b.add('set','Set Mode Variable',Name='mode')
    b.connect('start','Out','set','In').connect('make','Value','set','Value')
    with pytest.raises(GraphError,match='Unknown enum:Mode label'):
        b.compile()


def test_user_type_graph_editor_roundtrip(app):
    structs,enums=definitions()
    b=GraphBuilder(struct_definitions=structs,enum_definitions=enums)
    b.add('start','On Game Start'); b.add('make','Make Stats',hp=7)
    b.add('set','Set Entity Stats Variable',Entity='player',Name='stats')
    b.connect('start','Out','set','In').connect('make','Value','set','Value')
    adapter=GraphAdapter(); adapter.load(b.graph)
    assert adapter.document()['struct_definitions']==structs
    assert adapter.document()['enum_definitions']==enums
    assert len(adapter.graph.all_nodes())==3
    assert adapter.registry.by_name('Get Stats Variable')
    assert b.compile()['events']['start'][0]['type']==adapter.registry.by_name('Set Entity Stats Variable').id
    from editor.core.codegen import CppEmitter
    assert 'SetUserVariable' in CppEmitter().generate(b.compile())
    # Another document may assign the same generated ID to a different signature.
    other=[dict(name='Other',fields=[dict(name='text',type='string')])]
    c=GraphBuilder(struct_definitions=other); c.add('make','Make Other',text='reopened')
    adapter.load(c.graph)
    node=adapter.graph.all_nodes()[0]
    assert 'text' in node.inputs() and 'hp' not in node.inputs()
    assert adapter.document()['struct_definitions']==other
    adapter.graph.widget.close()


def test_editor_scene_type_declarations_survive_graph_only_reloads(app):
    structs,enums=definitions()
    b=GraphBuilder(struct_definitions=structs,enum_definitions=enums)
    b.add('make','Make Stats',hp=12)
    b.graph.pop('struct_definitions'); b.graph.pop('enum_definitions')
    adapter=GraphAdapter(); adapter.load(b.graph,struct_definitions=structs,enum_definitions=enums)
    saved=adapter.document()
    assert 'struct_definitions' not in saved
    adapter.load(saved)
    assert adapter.registry.by_name('Make Stats')
    adapter.graph.widget.close()


def test_callback_references_participate_in_function_cycle_checks():
    from editor.core.functions import new_function
    f = new_function('Recursive callback', [dict(name='Item',type='int')], [dict(name='Result',type='int')], True)
    inner = GraphBuilder(functions=[f],function=f['id'])
    inner.add('entry','Function Input'); inner.add('return','Function Output')
    inner.add('map','Map Integer Array',Array=[1],Callback=f['id'])
    inner.add('first','Get Integer Item',Index=0)
    inner.connect('map','Value','first','Array').connect('first','Value','return','Result')
    f['graph'] = inner.graph
    with pytest.raises(GraphError,match='Recursive call cycle'):
        GraphBuilder(functions=[f]).compile()


def test_callback_ids_cannot_be_replaced_by_ignored_data_wires():
    from editor.core.functions import new_function
    f = new_function('Identity', [dict(name='Item',type='int')], [dict(name='Result',type='int')], True)
    f['graph']['links'] = [{'from':['entry','Item'],'to':['return','Result']}]
    b = GraphBuilder(functions=[f])
    b.add('start','On Game Start'); b.add('map','Map Integer Array',Array=[1],Callback=f['id'])
    b.add('dynamic','Integer',Value=f['id']); b.connect('dynamic','Value','map','Callback')
    b.add('store','Set Integer Array Variable',Name='items')
    b.connect('map','Value','store','Value').connect('start','Out','store','In')
    with pytest.raises(GraphError,match='constant function ID'):
        b.compile()


def test_graph_defined_variable_type_is_saved_as_a_valid_scene(app,tmp_path):
    from PySide6.QtCore import QSettings, QTimer
    from editor.core.document import create_project, load_project, save_json
    from editor.ui.main_window import MainWindow
    from editor.ui.variables import VariablesDialog
    manifest=create_project(tmp_path/'project','Graph type variable')
    structs,enums=definitions()
    b=GraphBuilder(struct_definitions=structs,enum_definitions=enums)
    save_json(manifest.parent/'graphs/gameplay.json',b.graph)
    window=MainWindow(manifest,settings=QSettings(str(tmp_path/'ui.ini'),QSettings.Format.IniFormat))
    window.show()
    baseline=window.signature()
    def fill():
        dialog=app.activeModalWidget()
        if isinstance(dialog,VariablesDialog):
            dialog.add_row('stats','struct:Stats',dict(hp=24),'global')
            dialog.accept()
    QTimer.singleShot(100,fill)
    window.edit_variables()
    assert window.scene['variables']['stats']==dict(type='struct:Stats',value=dict(hp=24))
    window.actions['Undo'].trigger(); assert window.signature()==baseline
    window.actions['Redo'].trigger(); assert window.save_project()
    assert load_project(manifest)[2]['variables']['stats']['value']==dict(hp=24)
    window.open_project(manifest)
    assert window.scene['variable_scopes']['stats']=='global'
    window.close()
