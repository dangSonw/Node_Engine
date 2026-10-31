"""Authored colliders survive scene/prefab editing and real native execution."""
from copy import deepcopy
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene
from editor.core.physics import default_body, validate_body
from editor.core.scene import entity, set_entity_property, validate_scene
from editor.core.prefabs import capture_prefab, instantiate_scene_prefab
from editor.core.prefab_edits import apply_prefab_overrides, reset_prefab_instance
from tests.test_native import native
from tests.test_physics_scene import chain, run


def prefab_scene():
    source = default_scene(); source['entities'][0]['rigid_body'] = default_body()
    asset = capture_prefab(source, 'player', 'Physics box', asset_id='box')
    scene = default_scene(); scene['prefab_assets'] = [asset]
    return scene


@pytest.mark.parametrize('key,value', [('radius', 0), ('mass', True), ('mask', -1),
    ('mask', 2**32), ('sensor', 1), ('motion', 'unknown'), ('friction', float('nan')),
    ('half_extents', [.5, .5]), ('shape', 'mesh')])
def test_invalid_settings_reject_atomically(key, value):
    scene = default_scene(); before = deepcopy(scene)
    body = dict(default_body(), **{key: value})
    with pytest.raises(ValueError): set_entity_property(scene, 'player', 'rigid_body', body)
    assert scene == before


def test_prefab_apply_reset_and_explicit_removal_preserve_body_ownership():
    scene = prefab_scene()
    scene, first = instantiate_scene_prefab(scene, 'box', position=[-3, 0, 0])
    scene, second = instantiate_scene_prefab(scene, 'box', position=[3, 0, 0])
    scene = set_entity_property(scene, first, 'rigid_body', dict(default_body(), shape='sphere', mass=2.))
    applied = apply_prefab_overrides(scene, first)
    assert entity(applied, second)['rigid_body']['shape'] == 'sphere'
    removed = set_entity_property(applied, second, 'rigid_body', None)
    assert entity(removed, first)['rigid_body'] is not None
    assert entity(reset_prefab_instance(removed, second), second)['rigid_body']['mass'] == 2


@pytest.mark.parametrize('scale,shape', [([0,1,1],'box'), ([-1,1,1],'box'), ([1,2,1],'sphere')])
def test_invalid_scaled_colliders_reject_scene(scale, shape):
    scene = default_scene(); scene['entities'][0].update(scale=scale, rigid_body=dict(default_body(), shape=shape))
    with pytest.raises(ValueError): validate_scene(scene)


@pytest.mark.parametrize('shape', ['box', 'sphere', 'capsule'])
def test_authored_body_exists_before_game_start_and_simulates_in_both_hosts(native, shape):
    scene = default_scene(); scene['entities'][0]['rigid_body'] = dict(default_body(), shape=shape)
    b = GraphBuilder(); b.add('start', 'On Game Start'); b.add('has', 'Has Rigid Body')
    chain(b, 'start', ('store', 'Set Boolean Variable', {'Name': 'ready'}))
    b.connect('has','Value','store','Value')
    result = run(native, b, scene, 60)
    assert result['variables']['ready']['value'] is True
    assert result['physics']['bodies']['player']['shape'] == shape
    assert result['entities']['player']['position'][1] < -4
    assert result['scene']['entities'][0]['rigid_body'] == scene['entities'][0]['rigid_body']


def test_spawn_reset_and_clone_keep_separate_native_bodies(native):
    scene = prefab_scene()
    b = GraphBuilder(); b.add('start', 'On Game Start')
    chain(b, 'start', ('spawn', 'Instantiate Prefab', {'Prefab':'box', 'Position':[0,4,0]}),
          ('mass','Set Mass',{'Entity':'spawned_1','Value':9}),
          ('clone','Clone Entity',{'Source':'spawned_1'}),
          ('remove','Remove Rigid Body',{'Entity':'spawned_1'}),
          ('reset','Reset Prefab Instance',{'Instance':'spawned_1'}))
    result = run(native, b, scene, 1)
    bodies = result['physics']['bodies']
    assert set(bodies) == {'spawned_1','spawned_2'}
    assert bodies['spawned_1']['mass'] == 1 and bodies['spawned_2']['mass'] == 9
    assert all(b['position'][1] < 4 for b in bodies.values())


def test_runtime_prefab_apply_rebuilds_changed_colliders_and_preserves_unrelated_motion(native):
    scene = prefab_scene()
    scene, first = instantiate_scene_prefab(scene, 'box', position=[-3,2,0])
    scene, second = instantiate_scene_prefab(scene, 'box', position=[3,2,0])
    scene = set_entity_property(scene, first, 'rigid_body', dict(default_body(), shape='sphere', radius=.8, mass=2.))
    b = GraphBuilder(); b.add('start', 'On Game Start')
    chain(b, 'start', ('velocity','Set Velocity',{'Entity':first,'Value':[1,0,0]}),
          ('apply','Apply Prefab Overrides',{'Instance':first}))
    result = run(native, b, scene, 0)
    bodies = result['physics']['bodies']
    assert bodies[first]['shape'] == bodies[second]['shape'] == 'sphere'
    assert bodies[first]['mass'] == bodies[second]['mass'] == 2
    assert bodies[first]['velocity'] == [1,0,0]


def test_compound_and_mesh_colliders_simulate_and_roundtrip_in_native_hosts(native, tmp_path):
    """Compound convex parts and a static triangle mesh must reach Jolt, not only validation."""
    scene = default_scene()
    compound_parts = [
        {'shape': 'box', 'position': [-.45, 0, 0], 'rotation': [1, 0, 0, 0],
         'half_extents': [.45, .25, .45], 'radius': .5, 'half_height': .5,
         'vertices': [], 'triangles': []},
        {'shape': 'sphere', 'position': [.45, .35, 0], 'rotation': [1, 0, 0, 0],
         'half_extents': [.5, .5, .5], 'radius': .35, 'half_height': .5,
         'vertices': [], 'triangles': []},
    ]
    mesh_part = {'shape': 'mesh', 'position': [0, 0, 0], 'rotation': [1, 0, 0, 0],
                 'half_extents': [.5, .5, .5], 'radius': .5, 'half_height': .5,
                 'vertices': [[-4, 0, -4], [4, 0, -4], [4, 0, 4], [-4, 0, 4]],
                 'triangles': [[0, 2, 1], [0, 3, 2]]}
    scene['entities'][0].update(position=[0, 2, 0], rigid_body=dict(
        default_body(), shape='compound', motion='dynamic', parts=compound_parts))
    scene['entities'].append({'id': 'mesh_ground', 'name': 'Mesh Ground', 'position': [0, -1, 0],
                              'rotation': [0, 0, 0], 'scale': [1, 1, 1],
                              'rigid_body': dict(default_body(), shape='mesh', motion='static',
                                                 parts=[mesh_part])})
    b = GraphBuilder('Mesh and compound colliders')
    b.add('start', 'On Game Start')
    b.add('storage', 'Open Save Storage', **{'Game ID': 'compound-mesh'})
    b.connect('start', 'Out', 'storage', 'In')
    b.add('quit', 'On Application Quit')
    b.add('save', 'Save Game', Slot='shape')
    b.connect('quit', 'Out', 'save', 'In')
    b.add('load_key', 'On Key Pressed', Filter='L')
    b.add('load', 'Load Game', Slot='shape')
    b.connect('load_key', 'Out', 'load', 'In')
    first, first_game = native(b.graph, scene=scene, frames=60,
                               extra=['--save-root', str(tmp_path)])
    assert first.returncode == first_game.returncode == 0, first.stderr + first_game.stderr
    result = json.loads(first.stdout)
    second, second_game = native(b.graph, scene=scene, frames=1,
                                 extra=['--key', 'L', '--save-root', str(tmp_path)])
    assert second.returncode == second_game.returncode == 0, second.stderr + second_game.stderr
    loaded = json.loads(second.stdout)
    loaded_game = json.loads(second_game.stdout)
    bodies = result['physics']['bodies']
    assert bodies['player']['shape'] == 'compound'
    assert bodies['mesh_ground']['shape'] == 'mesh'
    # The compound body rests on the mesh instead of falling through it. The
    # exact center depends on the mesh contact margin, so assert the stronger
    # invariant (bounded above the plane and no continuing downward velocity).
    assert result['entities']['player']['position'][1] > -1.5
    assert abs(result['physics']['bodies']['player']['velocity'][1]) < .1
    assert result['scene']['entities'][1]['rigid_body']['parts'][0]['shape'] == 'mesh'
    assert loaded['persistence']['success']
    assert {k: v['shape'] for k, v in loaded['physics']['bodies'].items()} == {
        k: v['shape'] for k, v in loaded_game['physics']['bodies'].items()}
    slots = list((tmp_path / 'compound-mesh').glob('slot-*.json'))
    assert len(slots) == 1
    checkpoint = json.loads(slots[0].read_text(encoding='utf-8'))['checkpoint']['physics']['world']['bodies']
    saved = {row['settings']['id']: row['settings'] for row in checkpoint}
    assert saved['player']['shape'] == 'compound' and len(saved['player']['parts']) == 2
    assert saved['mesh_ground']['shape'] == 'mesh' and len(saved['mesh_ground']['parts'][0]['triangles']) == 2


def test_invalid_runtime_parent_scale_reports_instantiate_node(native):
    scene = prefab_scene(); scene['entities'][0]['scale'] = [2,1,1]
    b = GraphBuilder(); b.add('start','On Game Start')
    chain(b,'start',('spawn','Instantiate Prefab',{'Prefab':'box','Parent':'player'}))
    a,z = native(b.graph,scene=scene,frames=0)
    assert a.returncode == z.returncode == 1
    error=json.loads(a.stderr); assert error == json.loads(z.stderr)
    assert error['node']=='spawn' and 'uniform scale' in error['message']
