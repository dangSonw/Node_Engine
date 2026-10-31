"""Real graph/native physics: frame partitioning, scene lifetime and save continuation."""
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene
from tests.test_native import native


def chain(b, source, *operations):
    for nid, label, values in operations:
        b.add(nid, label, **values)
        b.connect(source, 'Out', nid, 'In')
        source = nid
    return source


def run(native, b, scene=None, frames=0, extra=()):
    a, z = native(b.graph, scene=scene, frames=frames, extra=extra)
    assert a.returncode == z.returncode == 0, a.stderr + z.stderr
    result = json.loads(a.stdout)
    assert result == json.loads(z.stdout)
    return result


def test_fixed_force_matches_different_host_frame_rates(native):
    b = GraphBuilder(); b.add('start', 'On Game Start')
    chain(b, 'start', ('gravity', 'Set Physics Gravity', {'Gravity': [0, 0, 0]}),
          ('body', 'Create Sphere Rigid Body', {}), ('damping', 'Set Damping', {'Linear': 0, 'Angular': 0}))
    b.add('fixed', 'On Fixed Update')
    chain(b, 'fixed', ('force', 'Apply Force', {'Value': [1, 0, 0]}),
          ('counter', 'Set Variable', {'Name': 'ticks'}), ('delta', 'Set Variable', {'Name': 'step'}))
    b.add('ticks', 'Get Variable', Name='ticks'); b.add('inc', 'Add', B=1)
    b.connect('ticks', 'Value', 'inc', 'A').connect('inc', 'Value', 'counter', 'Value')
    b.add('dt', 'Get Delta Time'); b.connect('dt', 'Value', 'delta', 'Value')
    scene = default_scene(); scene['variables'] = {'ticks': 0., 'step': 0.}
    states = [run(native, b, scene, frames, ['--dt', str(dt)]) for frames, dt in ((60, 1/60), (30, 1/30), (120, 1/120))]
    for result in states:
        assert result['variables']['ticks'] == 60
        assert result['variables']['step'] == 1/60
        assert result['physics']['ticks'] == 60
        assert result['physics']['bodies']['player']['velocity'] == pytest.approx([1, 0, 0], abs=2e-6)
    assert all(s['physics'] == states[0]['physics'] and s['entities'] == states[0]['entities'] for s in states)


def test_dynamic_child_preserves_world_motion_under_transformed_parent(native):
    scene = default_scene(); scene['entities'][0].update(position=[1, 2, 0], parent='rig')
    scene['entities'].append(dict(id='rig', name='Rig', position=[4, 2, 1], rotation=[0, 90, 0], scale=[2, 2, 2]))
    b = GraphBuilder(); b.add('start', 'On Game Start')
    chain(b, 'start', ('gravity', 'Set Physics Gravity', {'Gravity': [0, 0, 0]}),
          ('body', 'Create Box Rigid Body', {}), ('damping', 'Set Damping', {'Linear': 0, 'Angular': 0}),
          ('velocity', 'Set Velocity', {'Value': [1, 0, 0]}))
    result = run(native, b, scene, 60)
    assert result['physics']['bodies']['player']['position'] == pytest.approx([5, 6, -1], abs=1e-5)
    assert result['entities']['player']['position'] == pytest.approx([1, 2, .5], abs=1e-5)


def test_scale_layer_activity_and_clone_are_observed_by_queries(native):
    b = GraphBuilder(); b.add('start', 'On Game Start')
    end = chain(b, 'start', ('body', 'Create Sphere Rigid Body', {'Motion': 'static'}),
                ('scale', 'Set Scale', {'Value': [4, 4, 4]}),
                ('layer', 'Set Entity Layer', {'Layer': 31}), ('store_hit', 'Set Entity Variable', {'Name': 'hit'}))
    b.add('ray', 'Physics Raycast Entity', Origin=[1.5, 5, 0], Displacement=[0, -10, 0], Mask=2**31)
    b.connect('ray', 'Value', 'store_hit', 'Value')
    end = chain(b, end, ('clone', 'Clone Entity', {}), ('hide', 'Set Entity Active', {'Active': False}),
                ('store_hidden', 'Set Entity Variable', {'Name': 'hidden'}), ('destroy_clone', 'Destroy Entity', {}),
                ('store_clear', 'Set Entity Variable', {'Name': 'clear'}))
    b.connect('ray', 'Value', 'store_hidden', 'Value').connect('ray', 'Value', 'store_clear', 'Value')
    b.connect('clone', 'Entity', 'destroy_clone', 'Entity')
    result = run(native, b)
    assert result['variables']['hit']['value'] == 'player'
    assert result['variables']['hidden']['value'] == 'spawned_1'
    assert result['variables']['clear']['value'] == ''
    assert list(result['physics']['bodies']) == ['player']
    assert not result['physics']['bodies']['player']['enabled']


@pytest.mark.parametrize('operation,values', [
    ('Create Box Rigid Body', {'Half Extents': [-1, .5, .5]}),
    ('Create Sphere Rigid Body', {'Mass': 0}),
    ('Create Capsule Rigid Body', {'Motion': 'unsupported'}),
    ('Physics Raycast Entity', {'Displacement': [0, 0, 0]}),
])
def test_invalid_physics_nodes_report_the_graph_node(native, operation, values):
    b = GraphBuilder(); b.add('start', 'On Game Start'); b.add('bad', operation, **values)
    if operation == 'Physics Raycast Entity':
        b.add('store', 'Set Entity Variable', Name='hit')
        b.connect('start', 'Out', 'store', 'In').connect('bad', 'Value', 'store', 'Value')
    else:
        b.connect('start', 'Out', 'bad', 'In')
    a, z = native(b.graph, frames=0)
    assert a.returncode == z.returncode == 1
    assert json.loads(a.stderr) == json.loads(z.stderr)
    assert json.loads(a.stderr)['node'] == 'bad'


def test_fixed_updates_share_budget_and_restore_frame_delta_on_failure(native):
    b = GraphBuilder(); b.add('fixed', 'On Fixed Update'); b.add('log', 'Print Log', Message='step')
    b.connect('fixed', 'Out', 'log', 'In')
    a, z = native(b.graph, frames=1, extra=['--dt', '1', '--budget', '4'])
    assert a.returncode == z.returncode == 1
    assert json.loads(a.stderr) == json.loads(z.stderr)
    assert 'budget' in json.loads(a.stderr)['message']
