from copy import deepcopy
import math
import pytest
from PySide6.QtWidgets import QDialog

from editor.core.builder import GraphBuilder
from editor.core.compiler import GraphError, compile_graph
from editor.core.data_types import declaration
from editor.core.document import default_scene
from editor.core.projects import compile_project
from editor.core.scene import validate_scene, duplicate_entity, delete_entity
from editor.core.typed_schema import build_schema
from editor.ui.variables import VariablesDialog


def scene():
    result = default_scene()
    result['variables'] = dict(score=0.0, hp=declaration('int',100), lives=declaration('int',3))
    result['variable_scopes'] = dict(hp='entity', lives='global')
    return result


def test_compiler_checks_types_within_namespace_and_routes_implicit_nodes():
    b = GraphBuilder(); b.add('start', 'On Game Start')
    b.add('entity', 'Set Integer Variable', Name='hp', Value=2)
    b.add('global', 'Set Global String Variable', Name='hp', Value='global')
    b.add('scene', 'Set Scene Float Variable', Name='hp', Value=1.5)
    b.connect('start','Out','entity','In').connect('entity','Out','global','In').connect('global','Out','scene','In')
    ir = b.compile(scene())
    assert ir['variable_scopes']['hp'] == 'entity'
    invalid = deepcopy(b.graph)
    invalid['nodes'][1]['type'] = b.registry.by_name('Set String Variable').id
    invalid['nodes'][1]['values']['Value'] = 'bad'
    with pytest.raises(GraphError, match="Variable 'hp' is int, not string"):
        compile_graph(invalid, scene())


def test_project_rejects_conflicting_global_defaults_and_types():
    a, b = scene(), scene()
    b['variables']['lives'] = declaration('int',7)
    graph = dict(version=1,nodes=[],links=[])
    project = dict(version=2,entry_scene='a',scenes={name:dict(graph=graph,scene=value) for name,value in [('a',a),('b',b)]})
    with pytest.raises(ValueError, match='conflicting global declaration: lives'):
        compile_project(project)
    b['variables']['lives'] = declaration('int',3)
    builder = GraphBuilder(); builder.add('wrong', 'Get Global String Variable', Name='lives')
    project['scenes']['b']['scene'] = default_scene()
    project['scenes']['b']['graph'] = builder.graph
    with pytest.raises(GraphError, match='b/wrong'):
        compile_project(project)


def test_entity_initial_overrides_validate_clone_independence_and_delete():
    value = scene()
    value['entity_variables'] = {'player': {'hp':declaration('int',12)}}
    assert validate_scene(value) is value
    copied, owner = duplicate_entity(value,'player')
    copied['entity_variables'][owner]['hp']['value'] = 5
    assert copied['entity_variables']['player']['hp']['value'] == 12
    removed = delete_entity(copied,'player')
    assert 'player' not in removed['entity_variables']
    assert removed['entity_variables'][owner]['hp']['value'] == 5
    value['entity_variables']['missing'] = {}
    with pytest.raises(ValueError, match='owner does not exist'):
        validate_scene(value)


def test_entity_and_global_snapshot_types_are_validated():
    value = scene()
    value['entity_variables'] = {'player':{'hp':declaration('string','wrong')}}
    with pytest.raises(ValueError,match='scoped variable type mismatch'):
        validate_scene(value)
    value.pop('entity_variables')
    value['global_variables'] = {'lives':declaration('int',9)}
    with pytest.raises(ValueError,match='global state disagrees'):
        validate_scene(value)


@pytest.mark.parametrize('number', [math.nan, math.inf, -math.inf])
def test_scene_rejects_nonfinite_initial_variables(number):
    value = default_scene(); value['variables']['bad'] = number
    with pytest.raises(ValueError): validate_scene(value)


def test_variable_dialog_edits_scopes_and_user_value_types(app):
    schema = build_schema([dict(name='Stats',fields=[dict(name='hp',type='int',default=1)])],
                          [dict(name='Mode',values=['Idle','Run'])])
    variables = dict(score=0.0, stats=declaration('struct:Stats',{'hp':2},schema), mode=declaration('enum:Mode','Run',schema))
    dialog = VariablesDialog(variables, scopes={'score':'global'}, schema=schema)
    for row in range(dialog.table.rowCount()):
        if dialog.table.item(row,0).text() == 'stats':
            dialog.table.cellWidget(row,3).setCurrentText('entity')
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.result_variables == variables
    assert dialog.result_scopes == dict(score='global',stats='entity')
