"""Live Apply must agree with authoring and preserve the ongoing simulation."""
from copy import deepcopy
import json
from types import SimpleNamespace
import pytest

from editor.core.builder import GraphBuilder
from editor.core.components import edit_instance
from editor.core.document import default_scene
from editor.core.prefab_edits import apply_prefab_overrides
from editor.core.prefabs import PrefabLibrary
from editor.core.scene import set_entity_property, validate_scene
from tests.test_activity import at_frame, counter
from tests.test_entities import pair
from tests.test_events import event
from tests.test_native import native
from tests.test_prefab_reset_native import scene_and_builder, chain
from tests.test_prefabs import by_id
from tests.test_prefab_nested import nested_scene, group_record, group_asset


def assert_authoring(native, scene, graph, member='player', keep=True):
    result = pair(native, graph, scene)
    baseline = pair(native, GraphBuilder(), scene)
    expected = apply_prefab_overrides(baseline['scene'], member, keep_placement=keep)
    expected = pair(native, GraphBuilder(), expected)
    assert result == expected
    validate_scene(result['scene'])
    assert pair(native, GraphBuilder(), result['scene']) == result
    return result


@pytest.mark.parametrize('keep', [True, False])
def test_apply_matches_authoring_propagates_nested_variants_and_preserves_masks(native, keep):
    scene, _ = scene_and_builder()
    # A containing asset and another instance of the base exercise both dependency paths.
    scene['prefab_assets'].append(dict(version=1, type='prefab', id='pair', name='Pair',
        root='group', entities=[dict(default_scene()['entities'][0], id='group')],
        nested=[dict(id='nested', prefab='variant', parent='group',
                     overrides={'root': {'components': {'1': {'properties': {'4': 'binding'}}}}})]))
    library = PrefabLibrary(scene['prefab_assets'])
    for aid, mapping in [('robot', {'root': 'third', 'e1': 'third_child'}),
                         ('pair', {'group': 'group', 'nested': 'nested', 'nested/e1': 'nested_child'})]:
        record = library.instantiate_entities(aid, mapping=mapping)
        scene['entities'].extend(record.pop('entities')); scene['prefab_instances'].append(record)
    scene = edit_instance(scene, 'third', 1, 'set', field=5, value=100)
    scene = edit_instance(scene, 'player', 1, 'set', field=5, value=42)
    scene = edit_instance(scene, 'player', 1, 'enable', value=False)
    scene = set_entity_property(scene, 'player', 'scale', [2, 3, 4])
    scene = set_entity_property(scene, 'child', 'position', [0, 7, 0])
    b = GraphBuilder(component_definitions=library.component_definitions)
    b.add('start', 'On Game Start')
    chain(b, [('apply', 'Apply Prefab Overrides', dict(Instance='child', KeepPlacement=keep))])
    result = assert_authoring(native, scene, b, 'child', keep)
    entities = by_id(result['scene'])
    assert entities['third']['components']['1']['properties']['5'] == 100
    assert entities['other']['components']['1']['properties']['5'] == 42
    assert entities['nested']['components']['1']['properties']['4'] == 'binding'
    assert entities['nested_child']['position'] == [0, 7, 0]
    assert result['prefab_state']['entities']['child']['owned_components'] == []


def test_apply_adopts_children_remaps_references_and_reserves_ids(native, monkeypatch):
    scene, b = scene_and_builder()
    added = dict(default_scene()['entities'][0], id='spawned_1', name='Added', parent='player')
    scene['entities'].append(added)
    scene = edit_instance(scene, 'player', 1, 'set', field=1, value='spawned_1')
    # Match the native deterministic allocation to compare the entire transaction.
    ids = iter(['1', 'spawned_2'])
    monkeypatch.setattr('editor.core.prefab_edits.uuid.uuid4', lambda: SimpleNamespace(hex=next(ids)))
    b.add('start', 'On Game Start')
    chain(b, [('apply', 'Apply Prefab Overrides', dict(Instance='player'))])
    result = pair(native, b, scene)
    initial = pair(native, GraphBuilder(), scene)
    expected = apply_prefab_overrides(initial['scene'], 'player')
    expected['entity_serial'] = 2
    assert result == pair(native, GraphBuilder(), expected)
    entities = by_id(result['scene'])
    assert entities['player']['components']['1']['properties']['1'] == 'spawned_1'
    assert entities['other']['components']['1']['properties']['1'] == 'spawned_2'
    assert entities['spawned_2']['parent'] == 'other'
    assert result['prefab_state']['entities']['spawned_1']['base'] == {'asset': 'robot', 'local': 'added_1'}
    validate_scene(result['scene'])


def test_apply_removal_reparents_ordinary_children_retires_ids_and_cleans_delivery(native):
    scene, b = scene_and_builder([event('Ping', [{'name': 'Message', 'type': 'string'}])])
    scene['entities'].append(dict(default_scene()['entities'][0], id='extra', parent='other_child'))
    b.add('start', 'On Game Start')
    chain(b, [('timer', 'Start Timer', dict(Name='gone', Seconds=0, Owner='other_child')),
              ('send', 'Send Ping', dict(Recipient='other_child', Message='stale')),
              ('target', 'Set Links Target', dict(Entity='player', Value='')),
              ('friends', 'Set Links Friends', dict(Entity='player', Value=[])),
              ('slots', 'Set Links Slots', dict(Entity='player', Value={})),
              ('delete', 'Destroy Entity', dict(Entity='child')),
              ('apply', 'Apply Prefab Overrides', dict(Instance='player'))])
    b.add('on', 'On Ping', Receiver='other_child')
    chain(b, [('bad', 'Print Log', dict(Message='stale'))], 'on')
    b.add('tick', 'On Timer Finished', Receiver='other_child')
    chain(b, [('badtick', 'Print Log', dict(Message='stale timer'))], 'tick')
    result = pair(native, b, scene, frames=1)
    entities = by_id(result['scene'])
    assert set(entities) == {'player', 'other', 'extra'}
    assert entities['extra']['parent'] == 'other'
    assert result['logs'] == [] and result['timers'] == []
    assert {r['root']: r['retired'] for r in result['scene']['prefab_instances']} == {
        'player': {'e1': 'child'}, 'other': {'e1': 'other_child'}}
    validate_scene(result['scene'])


def test_apply_preserves_time_timers_queued_events_and_variant_equal_value_patch(native):
    scene, b = scene_and_builder([event('Ping', [{'name': 'Message', 'type': 'string'}])])
    scene['variables'] = {'ticks': {'type': 'int', 'value': 0}}
    b.add('start', 'On Game Start')
    chain(b, [('timer', 'Start Timer', dict(Name='tick', Seconds=.5, Repeat=True, Owner='child')),
              ('pin', 'Set Links Health', dict(Entity='other', Value=100)),
              ('variant', 'Apply Prefab Overrides', dict(Instance='other')),
              ('health', 'Set Links Health', dict(Entity='player', Value=25))])
    b.add('tick', 'On Timer Finished', Receiver='child'); counter(b, 'tick')
    sent = at_frame(b, 1, 'Send Ping', Recipient='child', Sender='other', Message='queued before apply')
    chain(b, [('apply', 'Apply Prefab Overrides', dict(Instance='player')),
              ('remaining', 'Set Variable', dict(Name='remaining'))], sent)
    b.add('read', 'Get Timer Remaining', Name='tick', Owner='child'); b.connect('read', 'Value', 'remaining', 'Value')
    b.add('ping', 'On Ping', Receiver='child'); b.add('log', 'Print Log')
    b.connect('ping', 'Out', 'log', 'In'); b.connect('ping', 'Message', 'log', 'Message')
    a, c = native(b.graph, scene=scene, frames=4, extra=['--dt', '.25'])
    assert a.returncode == c.returncode == 0, a.stderr+c.stderr
    result = json.loads(a.stdout); assert result == json.loads(c.stdout)
    assert result['time'] == 1 and result['frame'] == 4
    assert result['variables']['ticks']['value'] == 2 and result['variables']['remaining'] == .25
    assert result['timers'][0]['remaining'] == .5 and result['logs'] == ['queued before apply']
    assert by_id(result['scene'])['other']['components']['1']['properties']['5'] == 100
    assert by_id(result['scene'])['player']['components']['1']['properties']['5'] == 25
    variant = next(a for a in result['scene']['prefab_assets'] if a['id'] == 'variant')
    assert variant['overrides']['root']['components']['1']['properties']['5'] == 100


@pytest.mark.parametrize('failure', ['missing', 'external', 'detached', 'dependent'])
def test_apply_rejects_invalid_requests_at_original_node(native, failure):
    scene, b = scene_and_builder()
    if failure == 'external':
        scene = edit_instance(scene, 'player', 1, 'set', field=1, value='other')
    elif failure == 'detached':
        scene = set_entity_property(scene, 'child', 'parent', '')
    elif failure == 'dependent':
        scene['prefab_assets'][1]['overrides']['e1'] = {'name': 'Dependent child'}
        scene['entities'] = [e for e in scene['entities'] if e['id'] != 'child']
        for field, value in [(1, ''), (2, []), (3, {})]:
            scene = edit_instance(scene, 'player', 1, 'set', field=field, value=value)
    b.add('start', 'On Game Start')
    chain(b, [('bad_apply', 'Apply Prefab Overrides', dict(Instance='missing' if failure == 'missing' else 'player'))])
    a, c = native(b.graph, scene=scene, frames=0)
    assert a.returncode == c.returncode == 1
    error = json.loads(a.stderr); assert error == json.loads(c.stderr)
    assert error['node'] == 'bad_apply'
    assert {'missing': 'live prefab', 'external': 'External', 'detached': 'detached', 'dependent': 'missing local'}[failure] in error['message']


@pytest.mark.parametrize('trigger', ['event', 'timer'])
def test_apply_inside_delivery_keeps_surviving_listener_handles(native, trigger):
    scene, b = scene_and_builder([event('Ping')])
    b.add('start', 'On Game Start')
    name, values = ('Send Ping', dict(Recipient='child')) if trigger == 'event' else (
        'Start Timer', dict(Name='tick', Seconds=0, Owner='child'))
    chain(b, [('send', name, values)])
    for listener in ('a', 'z'):
        b.add(listener, 'On Ping' if trigger == 'event' else 'On Timer Finished', Receiver='child')
    chain(b, [('rename', 'Set Entity Name', dict(Entity='child', Name='Applied inside callback')),
              ('apply', 'Apply Prefab Overrides', dict(Instance='player'))], 'a')
    chain(b, [('last', 'Print Log', dict(Message='same delivery continued'))], 'z')
    result = pair(native, b, scene, frames=1)
    assert result['logs'] == ['same delivery continued']
    assert by_id(result['scene'])['other_child']['name'] == 'Applied inside callback'


def test_component_presence_changes_propagate_without_losing_independent_edits(native):
    scene, b = scene_and_builder()
    scene = edit_instance(scene, 'other', 1, 'set', field=5, value=77)
    scene = edit_instance(scene, 'player', 1, 'remove')
    scene = edit_instance(scene, 'child', 1, 'add')
    scene = edit_instance(scene, 'other_child', 1, 'remove')
    b.add('start', 'On Game Start')
    chain(b, [('apply', 'Apply Prefab Overrides', dict(Instance='player'))])
    result = assert_authoring(native, scene, b)
    entities = by_id(result['scene'])
    assert 'components' not in entities['player'] and 'components' not in entities['other_child']
    assert entities['other']['components']['1']['properties']['5'] == 77
    assert entities['child']['components']['1']['properties']['5'] == 100


def test_apply_without_user_components_updates_newly_instantiated_prefabs(native):
    asset = dict(version=1, type='prefab', id='box', name='Box', root='root',
                 entities=[dict(default_scene()['entities'][0], id='root')])
    record = PrefabLibrary([asset]).instantiate_entities('box', mapping={'root': 'player'})
    scene = dict(entities=record.pop('entities'), variables={}, prefab_instances=[record], prefab_assets=[asset])
    b = GraphBuilder(); b.add('start', 'On Game Start')
    chain(b, [('rename', 'Set Entity Name', dict(Entity='player', Name='New name')),
              ('apply', 'Apply Prefab Overrides', dict(Instance='player')),
              ('spawn', 'Instantiate Prefab', dict(Prefab='box'))])
    result = pair(native, b, scene)
    assert {e['name'] for e in result['scene']['entities']} == {'New name'}
    assert set(result['entities']) == {'player', 'spawned_1'}
    assert result['prefab_state']['entities']['spawned_1']['base'] == {'asset': 'box', 'local': 'root'}
    validate_scene(result['scene'])


def test_nested_adoption_preserves_delivery_and_follows_later_source_edits(native, monkeypatch):
    scene = nested_scene()
    scene = edit_instance(scene, 'r', 1, 'set', field=5, value=100)
    scene = set_entity_property(scene, 'c', 'active', True)
    b = GraphBuilder(component_definitions=scene['component_definitions'], event_definitions=[event('Ping')])
    b.add('start', 'On Game Start')
    chain(b, [('timer', 'Start Timer', dict(Name='nested', Seconds=0, Owner='c')),
              ('send', 'Send Ping', dict(Recipient='c')),
              ('apply', 'Apply Prefab Overrides', dict(Instance='a'))])
    b.add('tick', 'On Timer Finished', Receiver='c')
    chain(b, [('timer_log', 'Print Log', dict(Message='nested timer survived'))], 'tick')
    b.add('on', 'On Ping', Receiver='c')
    chain(b, [('event_log', 'Print Log', dict(Message='nested event survived'))], 'on')
    result = pair(native, b, scene, frames=1)
    assert sorted(result['logs']) == ['nested event survived', 'nested timer survived']
    assert group_record(result['scene'])['mapping'] == {'root': 'a', 'nested_1': 'r', 'nested_1/e1': 'c'}
    assert set(r['root'] for r in result['scene']['prefab_instances']) == {'a', 'b', 'independent'}
    assert result['prefab_state']['entities']['c']['base'] == {'asset': 'group', 'local': 'nested_1/e1'}
    assert result['prefab_state']['entities']['c']['owned_components'] == []
    ids = iter(['1', 'spawned_1', 'spawned_2'])
    monkeypatch.setattr('editor.core.prefab_edits.uuid.uuid4', lambda: SimpleNamespace(hex=next(ids)))
    baseline = pair(native, GraphBuilder(), scene)
    expected = apply_prefab_overrides(baseline['scene'], 'a'); expected['entity_serial'] = 2
    expected = pair(native, GraphBuilder(), expected)
    assert result['scene'] == expected['scene'] and result['prefab_state'] == expected['prefab_state']
    # A later edit of the dependency propagates through its real IsA templates.
    b = GraphBuilder(component_definitions=scene['component_definitions']); b.add('start', 'On Game Start')
    chain(b, [('health', 'Set Links Health', dict(Entity='independent', Value=40)),
              ('active', 'Set Entity Active', dict(Entity='independent_child', Active=False)),
              ('rename', 'Set Entity Name', dict(Entity='independent_child', Name='Updated child')),
              ('apply', 'Apply Prefab Overrides', dict(Instance='independent'))])
    updated = pair(native, b, result['scene'])
    entities = by_id(updated['scene'])
    assert entities['r']['components']['1']['properties']['5'] == 100
    assert entities['independent']['components']['1']['properties']['5'] == 40
    assert entities['c']['active'] is True and entities['independent_child']['active'] is False
    assert entities['c']['name'] == 'Updated child'
    validate_scene(updated['scene'])


def test_nested_tombstones_references_reset_and_fresh_instances(native):
    scene = nested_scene()
    scene['prefab_instances'][2]['retired'] = {'old': 'old_id'}
    b = GraphBuilder(component_definitions=scene['component_definitions']); b.add('start', 'On Game Start')
    chain(b, [('target', 'Set Links Target', dict(Entity='r', Value='a')),
              ('friends', 'Set Links Friends', dict(Entity='r', Value=['a', 'r'])),
              ('slots', 'Set Links Slots', dict(Entity='r', Value={'a': 'r'})),
              ('delete', 'Destroy Entity', dict(Entity='c')),
              ('apply', 'Apply Prefab Overrides', dict(Instance='a')),
              ('reset', 'Reset Prefab Instance', dict(Instance='r')),
              ('spawn', 'Instantiate Prefab', dict(Prefab='group'))])
    result = pair(native, b, scene)
    assert group_record(result['scene'])['retired'] == {'nested_1/e1': 'c', 'nested_1/old': 'old_id'}
    assert 'c' not in by_id(result['scene'])
    for record in result['scene']['prefab_instances']:
        if record['prefab'] != 'group':
            continue
        root, child = record['root'], record['mapping']['nested_1']
        props = by_id(result['scene'])[child]['components']['1']['properties']
        assert props['1'] == root and props['2'] == [root, child] and props['3'] == {'a': child}
    assert pair(native, GraphBuilder(), result['scene'])['scene'] == result['scene']
    validate_scene(result['scene'])


@pytest.mark.parametrize('failure', ['detached_member', 'foreign_child', 'cycle'])
def test_nested_rejection_reports_originating_node(native, failure):
    scene = nested_scene()
    if failure == 'detached_member':
        scene = set_entity_property(scene, 'c', 'parent', '')
    elif failure == 'foreign_child':
        scene = set_entity_property(scene, 'independent_child', 'parent', 'a')
    else:
        scene = set_entity_property(scene, 'b', 'parent', 'r')
    b = GraphBuilder(component_definitions=scene['component_definitions']); b.add('start', 'On Game Start')
    chain(b, [('bad_nested', 'Apply Prefab Overrides', dict(Instance='a'))])
    a, c = native(b.graph, scene=scene, frames=0)
    assert a.returncode == c.returncode == 1
    error = json.loads(a.stderr); assert error == json.loads(c.stderr)
    assert error['node'] == 'bad_nested'
    assert ('dependency cycle' if failure == 'cycle' else 'part of another prefab instance') in error['message']


def test_multilevel_nested_adoption_with_ordinary_child_and_cross_binding_references(native):
    scene = nested_scene()
    record = PrefabLibrary(scene['prefab_assets']).instantiate_entities('variant', mapping={'root': 'z', 'e1': 'z_child'}, parent='c')
    scene['entities'].extend(record.pop('entities')); scene['prefab_instances'].append(record)
    scene['entities'].append(dict(default_scene()['entities'][0], id='extra', parent='z_child'))
    scene = edit_instance(scene, 'r', 1, 'set', field=1, value='z')
    scene = edit_instance(scene, 'z', 1, 'set', field=2, value=['a', 'r', 'extra'])
    scene['prefab_instances'].reverse()
    b = GraphBuilder(component_definitions=scene['component_definitions']); b.add('start', 'On Game Start')
    chain(b, [('apply', 'Apply Prefab Overrides', dict(Instance='a'))])
    result = pair(native, b, scene)
    assert group_record(result['scene'])['mapping'] == {
        'root': 'a', 'nested_1': 'r', 'nested_1/e1': 'c', 'nested_2': 'z', 'nested_2/e1': 'z_child', 'added_1': 'extra'}
    bindings = group_asset(result['scene'])['nested']
    assert bindings == [dict(id='nested_1', prefab='robot', parent='root'),
                        dict(id='nested_2', prefab='variant', parent='nested_1/e1')]
    for root in ('a', 'b'):
        mapping = group_record(result['scene'], root)['mapping']
        items = by_id(result['scene'])
        assert items[mapping['nested_1']]['components']['1']['properties']['1'] == mapping['nested_2']
        assert items[mapping['nested_2']]['components']['1']['properties']['2'] == [root, mapping['nested_1'], mapping['added_1']]
        assert items[mapping['added_1']]['parent'] == mapping['nested_2/e1']
    assert pair(native, GraphBuilder(), result['scene'])['scene'] == result['scene']
    validate_scene(result['scene'])
