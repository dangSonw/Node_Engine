"""Gameplay Reset executes in the existing Flecs world in both execution paths."""
from copy import deepcopy
import json
import pytest

from editor.core.builder import GraphBuilder
from editor.core.document import default_scene
from editor.core.prefab_edits import reset_prefab_instance
from editor.core.prefabs import PrefabLibrary
from editor.core.scene import validate_scene
from tests.test_activity import at_frame, counter
from tests.test_events import event
from tests.test_entities import pair
from tests.test_native import native
from tests.test_prefabs import by_id, robot, variant


def scene_and_builder(events=()):
    library = PrefabLibrary([robot(), variant(overrides={'root': {'layer': 5}})])
    records, entities = [], []
    for aid, root, child, position in [('robot', 'player', 'child', [-3, 0, 0]),
                                       ('variant', 'other', 'other_child', [3, 0, 0])]:
        record = library.instantiate_entities(aid, mapping={'root': root, 'e1': child}, position=position)
        entities.extend(record.pop('entities')); records.append(record)
    scene = dict(version=1, entities=entities, variables={}, prefab_assets=library.assets,
                 component_definitions=library.component_definitions, prefab_instances=records)
    return scene, GraphBuilder(component_definitions=library.component_definitions, event_definitions=events)


def chain(b, steps, previous='start'):
    for nid, name, values in steps:
        b.add(nid, name, **values); b.connect(previous, 'Out', nid, 'In'); previous = nid
    return previous


@pytest.mark.parametrize('keep', [True, False])
def test_reset_matches_authoring_restores_components_references_and_placement(native, keep):
    scene, b = scene_and_builder()
    items = by_id(scene)
    items['player'].update(name='Override', rotation=[12, 23, 34], scale=[2, 3, 4], layer=12,
                           tags=['own'], visible=False, active=False, mesh='')
    items['player']['components']['1'].update(enabled=False, properties={'1': 'other', '5': 17})
    items['child'].update(position=[9, 8, 7], components=deepcopy(items['player']['components']))
    items['other']['layer'] = 8
    b.add('start', 'On Game Start')
    chain(b, [('reset', 'Reset Prefab Instance', dict(Instance='child', KeepPlacement=keep))])
    result = pair(native, b, scene)
    expected = reset_prefab_instance(scene, 'player', keep_placement=keep)
    baseline = pair(native, GraphBuilder(), expected)
    assert result == baseline
    state = by_id(result['scene'])
    assert state['player']['components']['1']['properties']['1'] == 'child'
    assert state['player']['components']['1']['properties']['5'] == 100
    assert 'components' not in state['child']
    assert state['other']['layer'] == 8
    assert result['prefab_state']['entities']['player']['owned_components'] == (['transform'] if keep else [])
    validate_scene(result['scene'])
    assert pair(native, GraphBuilder(), result['scene']) == result


def test_reset_preserves_running_timers_queued_events_time_and_variables(native):
    scene, b = scene_and_builder([event('Ping', [{'name': 'Message', 'type': 'string'}])])
    scene['variables'] = {'ticks': {'type': 'int', 'value': 0}}
    b.add('start', 'On Game Start')
    chain(b, [('timer', 'Start Timer', dict(Name='tick', Seconds=.5, Repeat=True, Owner='child')),
              ('move', 'Set Position', dict(Entity='child', Value=[9, 8, 7])),
              ('initial', 'Print Log', dict(Message='initial'))])
    b.add('tick', 'On Timer Finished', Receiver='child'); counter(b, 'tick')
    at = at_frame(b, 1, 'Send Ping', Recipient='child', Sender='other', Message='queued before reset')
    chain(b, [('reset', 'Reset Prefab Instance', dict(Instance='child')),
              ('remaining', 'Set Variable', dict(Name='remaining')),
              ('after', 'Print Log', dict(Message='reset done'))], at)
    b.add('read', 'Get Timer Remaining', Name='tick', Owner='child'); b.connect('read', 'Value', 'remaining', 'Value')
    b.add('ping', 'On Ping', Receiver='child'); b.add('log', 'Print Log')
    b.connect('ping', 'Out', 'log', 'In'); b.connect('ping', 'Message', 'log', 'Message')
    a, c = native(b.graph, scene=scene, frames=4, extra=['--dt', '.25'])
    assert a.returncode == c.returncode == 0, a.stderr + c.stderr
    result = json.loads(a.stdout); assert result == json.loads(c.stdout)
    assert result['frame'] == 4 and result['time'] == 1
    assert result['variables']['ticks']['value'] == 2
    assert result['variables']['remaining'] == .25
    assert result['timers'][0]['remaining'] == .5
    assert result['logs'] == ['initial', 'reset done', 'queued before reset']
    assert result['prefab_state']['entities']['child']['owned_components'] == []
    assert by_id(result['scene'])['child']['position'] == [0, 0, 0]


def test_reset_resurrects_same_ids_rebinds_observers_without_old_events_or_timers(native):
    scene, b = scene_and_builder([event('Ping', [{'name': 'Message', 'type': 'string'}])])
    b.add('start', 'On Game Start')
    previous = 'start'
    for index in range(3):
        previous = chain(b, [
            (f'old{index}', 'Send Ping', dict(Recipient='child', Message='stale')),
            (f'timer{index}', 'Start Timer', dict(Name='old', Seconds=0, Owner='child')),
            (f'delete{index}', 'Destroy Entity', dict(Entity='child')),
            (f'reset{index}', 'Reset Prefab Instance', dict(Instance='player')),
            (f'subscribe{index}', 'Subscribe Ping', dict(Recipient='child')),
        ], previous)
    chain(b, [('fresh', 'Send Ping', dict(Recipient='child', Message='fresh')),
              ('timer', 'Start Timer', dict(Name='new', Seconds=.5, Owner='child')),
              ('spawn', 'Spawn Entity', dict(Name='Unrelated'))], previous)
    b.add('ping', 'On Ping', Receiver='child'); b.add('log', 'Print Log')
    b.connect('ping', 'Out', 'log', 'In'); b.connect('ping', 'Message', 'log', 'Message')
    b.add('tick', 'On Timer Finished', Receiver='child'); b.add('ticklog', 'Print Log')
    b.connect('tick', 'Out', 'ticklog', 'In'); b.connect('tick', 'Name', 'ticklog', 'Message')
    result = pair(native, b, scene, frames=31)
    assert result['logs'] == ['fresh', 'new']
    assert result['timers'] == []
    assert set(result['entities']) == {'player', 'child', 'other', 'other_child', 'spawned_1'}
    assert by_id(result['scene'])['player']['components']['1']['properties']['2'] == ['player', 'child', '']
    assert result['scene']['prefab_instances'][1]['mapping'] == {'root': 'player', 'e1': 'child'}


@pytest.mark.parametrize('trigger', ['event', 'timer'])
def test_reset_inside_delivery_does_not_run_stale_listeners_for_recreated_owner(native, trigger):
    scene, b = scene_and_builder([event('Ping')])
    b.add('start', 'On Game Start')
    name, values = ('Send Ping', dict(Recipient='child')) if trigger == 'event' else (
        'Start Timer', dict(Name='tick', Seconds=0, Owner='child'))
    chain(b, [('send', name, values)])
    for listener in ('a', 'z'):
        b.add(listener, 'On Ping' if trigger == 'event' else 'On Timer Finished', Receiver='child')
    chain(b, [('delete', 'Destroy Entity', dict(Entity='child')),
              ('reset', 'Reset Prefab Instance', dict(Instance='player')),
              ('done', 'Print Log', dict(Message='restored'))], 'a')
    chain(b, [('stale', 'Print Log', dict(Message='stale listener'))], 'z')
    result = pair(native, b, scene, frames=1)
    assert result['logs'] == ['restored']
    assert 'child' in result['entities']


def test_reset_removes_added_nested_instance_and_detached_members_but_keeps_original_member(native):
    scene, b = scene_and_builder()
    b.add('start', 'On Game Start')
    chain(b, [('extra', 'Spawn Entity', dict(Name='Extra')),
              ('parent_extra', 'Set Parent', dict(Child='spawned_1', Parent='player')),
              ('nested', 'Instantiate Prefab', dict(Prefab='variant', Parent='spawned_1')),
              ('detach', 'Set Parent', dict(Child='spawned_3', Parent='')),
              ('move_child', 'Set Parent', dict(Child='child', Parent='spawned_1')),
              ('timer', 'Start Timer', dict(Name='removed', Seconds=10, Owner='spawned_3')),
              ('reset', 'Reset Prefab Instance', dict(Instance='child')),
              ('new', 'Spawn Entity', dict(Name='New'))])
    result = pair(native, b, scene)
    assert set(result['entities']) == {'player', 'child', 'other', 'other_child', 'spawned_4'}
    assert result['timers'] == [] and len(result['scene']['prefab_instances']) == 2
    assert by_id(result['scene'])['child']['parent'] == 'player'
    validate_scene(result['scene'])
    assert pair(native, GraphBuilder(), result['scene']) == result


@pytest.mark.parametrize('target', ['', 'missing', 'ordinary'])
def test_reset_rejects_invalid_target_at_original_node(native, target):
    scene, b = scene_and_builder()
    scene['entities'].append(dict(default_scene()['entities'][0], id='ordinary'))
    b.add('start', 'On Game Start')
    chain(b, [('bad_reset', 'Reset Prefab Instance', dict(Instance=target))])
    a, c = native(b.graph, scene=scene, frames=0)
    assert a.returncode == c.returncode == 1
    error = json.loads(a.stderr); assert error == json.loads(c.stderr)
    assert error['node'] == 'bad_reset' and 'live prefab instance member' in error['message']


def test_reset_rejects_cycle_from_retained_root_parent(native):
    scene, b = scene_and_builder()
    items = by_id(scene); items['child'].pop('parent'); items['player']['parent'] = 'child'
    b.add('start', 'On Game Start')
    chain(b, [('bad_reset', 'Reset Prefab Instance', dict(Instance='player'))])
    a, c = native(b.graph, scene=scene, frames=0)
    assert a.returncode == c.returncode == 1
    error = json.loads(a.stderr); assert error == json.loads(c.stderr)
    assert error['node'] == 'bad_reset' and 'hierarchy cycle' in error['message']
