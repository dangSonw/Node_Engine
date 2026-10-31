"""Applying a hierarchy retains nested asset dependencies and stable scene IDs."""
from copy import deepcopy
import pytest

from editor.core.components import edit_instance
from editor.core.document import default_scene
from editor.core.prefab_edits import apply_prefab_overrides, reconcile_prefab_assets, reset_prefab_instance
from editor.core.prefabs import PrefabLibrary, instantiate_scene_prefab
from editor.core.scene import delete_entity, entity, set_entity_property, validate_scene
from tests.test_prefabs import robot, variant


def nested_scene():
    group = dict(version=1, type='prefab', id='group', name='Group', root='root',
                 entities=[dict(default_scene()['entities'][0], id='root', mesh='')])
    library = PrefabLibrary([group, robot(), variant()])
    scene = dict(entities=[], variables={}, prefab_assets=library.assets,
                 component_definitions=library.component_definitions, prefab_instances=[])
    for aid, mapping, parent in [('group', {'root': 'a'}, ''), ('group', {'root': 'b'}, ''),
                                  ('robot', {'root': 'r', 'e1': 'c'}, 'a'),
                                  ('robot', {'root': 'independent', 'e1': 'independent_child'}, '')]:
        record = library.instantiate_entities(aid, mapping=mapping, parent=parent)
        scene['entities'].extend(record.pop('entities')); scene['prefab_instances'].append(record)
    return validate_scene(scene)


def group_record(scene, root='a'):
    return next(r for r in scene['prefab_instances'] if r['root'] == root)


def group_asset(scene):
    return next(a for a in scene['prefab_assets'] if a['id'] == 'group')


def test_capture_nested_binding_preserves_sources_ids_overrides_and_future_propagation():
    scene = nested_scene()
    scene = edit_instance(scene, 'r', 1, 'set', 100, 5)  # Equal-value write still pins Health.
    scene = set_entity_property(scene, 'c', 'active', True)
    scene = set_entity_property(scene, 'r', 'position', [2, 3, 4])
    before = deepcopy(scene)
    applied = apply_prefab_overrides(scene, 'a')
    assert scene == before
    assert {r['root'] for r in applied['prefab_instances']} == {'a', 'b', 'independent'}
    asset = group_asset(applied); binding, = asset['nested']; prefix = binding['id']
    assert binding == dict(id=prefix, prefab='robot', parent='root')
    assert len(asset['entities']) == 1  # Nested entities remain authored dependencies.
    assert next(a for a in applied['prefab_assets'] if a['id'] == 'robot') == robot()
    for root in ('a', 'b'):
        record = group_record(applied, root)
        nested = entity(applied, record['mapping'][prefix])
        assert nested['parent'] == root and nested['position'] == [2, 3, 4]
        assert nested['components']['1']['properties']['1'] == record['mapping'][prefix+'/e1']
    assert group_record(applied)['mapping'][prefix] == 'r'
    assert group_record(applied)['mapping'][prefix+'/e1'] == 'c'
    again = apply_prefab_overrides(applied, 'a')
    assert group_asset(again) == asset
    assets = deepcopy(applied['prefab_assets'])
    base = next(a for a in assets if a['id'] == 'robot')
    next(e for e in base['entities'] if e['id'] == 'root')['components']['1']['properties']['5'] = 40
    next(e for e in base['entities'] if e['id'] == 'e1').update(active=False, name='New source name')
    updated = reconcile_prefab_assets(applied, assets)
    assert entity(updated, 'r')['components']['1']['properties']['5'] == 100
    assert entity(updated, 'independent')['components']['1']['properties']['5'] == 40
    assert entity(updated, 'c')['active'] is True
    assert entity(updated, 'independent_child')['active'] is False
    assert entity(updated, 'c')['name'] == 'New source name'
    reset = reset_prefab_instance(delete_entity(updated, 'c'), 'a')
    assert entity(reset, 'c')['name'] == 'New source name'
    fresh, root = instantiate_scene_prefab(reset, 'group')
    assert entity(fresh, group_record(fresh, root)['mapping'][prefix])['components']['1']['properties']['5'] == 100


def test_multilevel_independent_instances_and_cross_binding_references():
    scene = nested_scene()
    scene, grandchild = instantiate_scene_prefab(scene, 'variant', parent='c')
    grandchild_record = deepcopy(scene['prefab_instances'][-1])
    scene = edit_instance(scene, 'r', 1, 'set', grandchild, 1)
    scene = edit_instance(scene, grandchild, 1, 'set', ['a', 'r'], 2)
    scene = edit_instance(scene, grandchild, 1, 'set', {'a': 'c'}, 3)
    scene['prefab_instances'].reverse()  # Ownership cannot depend on list order.
    applied = apply_prefab_overrides(scene, 'a')
    assert len(group_asset(applied)['nested']) == 2
    mapping = group_record(applied)['mapping']
    assert set(mapping.values()) == {'a', 'r', 'c', *grandchild_record['mapping'].values()}
    nested_local = next(k for k, v in mapping.items() if v == 'r')
    grandchild_local = next(k for k, v in mapping.items() if v == grandchild)
    for root in ('a', 'b'):
        record = group_record(applied, root)
        child = entity(applied, record['mapping'][nested_local])
        grand = entity(applied, record['mapping'][grandchild_local])
        assert child['components']['1']['properties']['1'] == grand['id']
        assert grand['parent'] == record['mapping'][nested_local+'/e1']
        assert grand['components']['1']['properties']['2'] == [root, child['id']]
        assert grand['components']['1']['properties']['3'] == {'a': record['mapping'][nested_local+'/e1']}


def test_nested_tombstones_and_retired_ids_survive_adoption_and_reintroduction():
    scene = nested_scene()
    scene['prefab_instances'][2]['retired'] = {'old': 'old_id'}
    scene = delete_entity(scene, 'c')
    for field, value in [(1, ''), (2, []), (3, {})]:
        scene = edit_instance(scene, 'r', 1, 'set', value, field)
    applied = apply_prefab_overrides(scene, 'a')
    prefix = group_asset(applied)['nested'][0]['id']
    assert group_record(applied)['retired'] == {prefix+'/e1': 'c', prefix+'/old': 'old_id'}
    assets = deepcopy(applied['prefab_assets'])
    next(a for a in assets if a['id'] == 'group')['removed'] = []
    restored = reconcile_prefab_assets(applied, assets)
    assert group_record(restored)['mapping'][prefix+'/e1'] == 'c'
    assert entity(restored, 'c')['parent'] == 'r'
    assert group_record(restored)['retired'] == {prefix+'/old': 'old_id'}


@pytest.mark.parametrize('case', ['detached_member', 'foreign_child', 'self_dependency'])
def test_invalid_nested_capture_is_transactional(case):
    scene = nested_scene()
    if case == 'detached_member':
        scene = set_entity_property(scene, 'c', 'parent', '')
    elif case == 'foreign_child':
        scene = set_entity_property(scene, 'independent_child', 'parent', 'a')
    else:
        scene, _ = instantiate_scene_prefab(scene, 'group', parent='r')
    before = deepcopy(scene)
    with pytest.raises(ValueError, match='part of another prefab instance|dependency cycle'):
        apply_prefab_overrides(scene, 'a')
    assert scene == before
