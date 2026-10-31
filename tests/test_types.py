from copy import deepcopy
import pytest
from editor.core.builder import GraphBuilder
from editor.core.compiler import compile_graph, GraphError, validate
from editor.core.data_types import literal_valid, declaration, variable, INT_MIN, INT_MAX, TYPES
from editor.core.document import default_scene, save_json
from editor.core.scene import validate_scene
from editor.core.registry import Registry


@pytest.mark.parametrize('value,kind', [(True,'int'), (1.0,'int'), (INT_MAX+1,'int'), (INT_MIN-1,'int'),
    ([1,True],'array<float>'), ([1.5],'array<int>'), ({'a':False},'map<int>'),
    ([[1,2]],'array<vec3>'), ([[1,2,3]],'array<vec2>'), ([[1,2,3]],'array<vec4>'),
    ([[1,2,3]],'array<quat>'), ([[1,2,3]],'array<mat4>'),
    ([1,1],'set<int>'), ([[1,2,3],[1,2,3]],'set<vec3>'),
    ([1]*65537,'array<int>'), ('\ud800','string')])
def test_invalid_typed_literals(value,kind):
    assert not literal_valid(value,kind)


def test_scene_variables_preserve_explicit_types_and_legacy_numbers(tmp_path):
    scene=default_scene()
    scene['variables']={'legacy':4, 'score':declaration('int',INT_MAX),
        'ready':declaration('bool',True), 'name':declaration('string','Tên nhân vật'),
        'uv':declaration('vec2',[1.5,-2.0]),
        'color':declaration('vec4',[1.0,.5,.25,1.0]),
        'rotation':declaration('quat',[0.0,0.0,0.0,1.0]),
        'transform':declaration('mat4',[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]),
        'waypoints':declaration('array<vec3>',[[1,2,3],[4,5,6]]),
        'uvs':declaration('array<vec2>',[[1,2],[3,4]]),
        'colors':declaration('array<vec4>',[[1,0,0,1],[0,1,0,1]]),
        'targets':declaration('map<entity>',{'player':'player'})}
    assert validate_scene(scene) is scene
    assert variable(scene['variables']['legacy']) == ('float',4)
    assert variable(scene['variables']['score']) == ('int',INT_MAX)
    for bad in (True, 'text', [1,2,3], {'type':'array<int>','value':[1.5]}, {'type':'unknown','value':0}):
        broken=deepcopy(scene)
        broken['variables']['bad']=bad
        with pytest.raises(ValueError,match='bad:'):
            validate_scene(broken)
    save_json(tmp_path/'typed-scene.json',scene)
    import json
    assert json.loads((tmp_path/'typed-scene.json').read_text('utf-8')) == scene


def test_declared_variable_type_conflict_reports_original_node():
    b=GraphBuilder()
    b.add('start','On Game Start')
    b.add('write','Set Variable',Name='ready')
    b.connect('start','Out','write','In')
    scene=default_scene()
    scene['variables']['ready']=declaration('bool',True)
    with pytest.raises(GraphError) as error:
        b.compile(scene)
    assert error.value.problems[0].node == 'write'
    assert 'bool' in str(error.value) and 'float' in str(error.value)


def test_foreach_outputs_are_lexically_scoped_to_body():
    b=GraphBuilder()
    b.add('start','On Game Start')
    b.add('loop','For Each Integer',Array=[1,2,3])
    b.add('store','Set Integer Variable')
    b.connect('start','Out','loop','In').connect('loop','Done','store','In')
    b.connect('loop','Item','store','Value')
    assert not validate(b.graph)
    with pytest.raises(GraphError,match='only available inside'):
        b.compile()
    b.graph['links'][1]['from'][1]='Body'
    ir=b.compile()
    expression=ir['events']['start'][0]['body'][0]['args'][1]
    assert expression == {'op':'local','node':'loop','port':'Item','type':'int'}


def test_registry_family_ids_types_and_names_are_stable():
    r=Registry()
    assert r.by_name('Get Integer Variable').id == 3101
    assert r.by_name('For Each Entity').id == 2305
    assert r.by_name('For Each Integer Set').id == 2351
    assert r.by_name('For Each Matrix4 Set').id == 2359
    assert r.by_name('For Each Integer Map').id == 2361
    assert r.by_name('For Each Matrix4 Map').id == 2369
    assert r.by_name('Get Vector3 Map Variable').id == 3404
    assert r.by_name('Get Integer Set Variable').id == 3601
    assert r.by_name('Create Vector2 Set').id == 3626
    assert r.by_name('Clear Matrix4 Set').id == 3679
    assert r.by_name('Concat Integer Arrays').id == 3701
    assert r.by_name('Slice Matrix4 Array').id == 3719
    assert r.by_name('Select Vector3 Set').id == 2134
    assert r.by_name('Get Vector2 Variable').id == 3106
    assert r.by_name('Get Vector4 Variable').id == 3107
    assert r.by_name('Get Quaternion Variable').id == 3108
    assert r.by_name('Get Matrix4 Variable').id == 3109
    assert r.by_name('Create Vector2 Array').id == 3226
    assert r.by_name('Create Vector4 Array').id == 3227
    assert r.by_name('Create Quaternion Array').id == 3228
    assert r.by_name('Create Matrix4 Array').id == 3229
    assert r.by_name('Point In Bounds').id == 4120
    assert r.by_name('Bounds Max').id == 4127
    assert r.by_name('World To Screen').id == 15014
    assert r.by_name('Screen To World').id == 15015
    assert r.by_name('Ray Bounds Intersection Distance').id == 4128
    assert r.by_name('Closest Point On Triangle').id == 4129
    assert r.by_name('Sphere Overlaps Bounds').id == 4130
    assert r.by_name('Distance To Plane').id == 4131
    assert r[3004].variable_type == 'float'  # Existing graph IDs remain valid.
    assert len({n.name for n in r.nodes.values()}) == len(r.nodes)
    assert all(p.type in (*TYPES,'exec') for n in r.nodes.values() for p in (*n.inputs,*n.outputs))
    assert all(literal_valid(p.default,p.type) for n in r.nodes.values() for p in n.data_inputs)
