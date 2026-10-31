"""Changes to shared assets must not destroy independent instance authoring."""
from copy import deepcopy
import pytest

from editor.core.components import edit_instance
from editor.core.document import default_scene
from editor.core.prefabs import PrefabLibrary, instantiate_scene_prefab
from editor.core.prefab_edits import apply_prefab_overrides, reconcile_prefab_assets, reset_prefab_instance
from editor.core.scene import create_entity, delete_entity, entity, set_entity_property, validate_scene
from tests.test_prefabs import robot, variant


def pair_scene():
    asset = robot()
    scene = {'entities': [], 'variables': {}, 'prefab_assets': [asset, variant()],
             'component_definitions': asset['component_definitions']}
    scene, first = instantiate_scene_prefab(scene, 'robot', position=[-3, 0, 0])
    scene, second = instantiate_scene_prefab(scene, 'robot', position=[3, 0, 0])
    return scene, first, second


def replace_root(assets, **values):
    result = deepcopy(assets)
    base = next(a for a in result if a['id'] == 'robot')
    next(e for e in base['entities'] if e['id'] == 'root').update(values)
    return result


@pytest.mark.parametrize('field', [1, 2, 3, 4, 5])
def test_same_value_component_write_survives_template_updates(field):
    scene, first, second = pair_scene()
    value = deepcopy(entity(scene, first)['components']['1']['properties'][str(field)])
    original = deepcopy(scene)
    scene = edit_instance(scene, first, 1, 'set', value, field)
    scene = edit_instance(scene, first, 1, 'enable', True)
    assert scene != original and entity(scene, first) == entity(original, first)
    updated = {'enabled': False, 'properties': {'1': '', '2': [], '3': {}, '4': 'new', '5': 25}}
    changed = reconcile_prefab_assets(scene, replace_root(scene['prefab_assets'], components={'1': updated}))
    own = entity(changed, first)['components']['1']
    assert own['enabled'] is True and own['properties'][str(field)] == value
    assert entity(changed, second)['components']['1'] == updated
    assert changed['prefab_instances'][0]['component_overrides']['root']['1'] == {
        'enabled': True, 'properties': [field]}
    reset = reset_prefab_instance(changed, first)
    assert entity(reset, first)['components']['1'] == updated
    assert 'component_overrides' not in reset['prefab_instances'][0]


def test_explicit_presence_removal_and_property_ownership_survive_component_changes():
    scene, first, second = pair_scene()
    child = scene['prefab_instances'][0]['mapping']['e1']
    scene = edit_instance(scene, child, 1, 'remove')  # Absent now; remain absent on future source additions.
    scene = edit_instance(scene, first, 1, 'remove')
    scene = edit_instance(scene, first, 1, 'add')
    scene = edit_instance(scene, second, 1, 'set', 100, 5)
    owned = deepcopy(entity(scene, first)['components']['1'])
    assets = replace_root(scene['prefab_assets'], components={})
    base = next(a for a in assets if a['id'] == 'robot')
    next(e for e in base['entities'] if e['id'] == 'e1')['components'] = {'1': owned}
    changed = reconcile_prefab_assets(scene, assets)
    assert entity(changed, first)['components']['1'] == owned
    assert entity(changed, second)['components']['1']['properties']['5'] == 100
    assert not entity(changed, child)['components']
    assert '1' in entity(changed, changed['prefab_instances'][1]['mapping']['e1'])['components']
    assert changed['prefab_instances'][0]['component_overrides']['root']['1'] == {'present': True}
    assert changed['prefab_instances'][0]['component_overrides']['e1']['1'] == {'present': False}


def test_applying_equal_value_to_variant_pins_that_property_against_future_base_changes():
    scene, first, _ = pair_scene()
    scene, derived = instantiate_scene_prefab(scene, 'variant')
    scene = edit_instance(scene, derived, 1, 'set', 100, 5)
    applied = apply_prefab_overrides(scene, derived)
    asset = next(a for a in applied['prefab_assets'] if a['id'] == 'variant')
    assert asset['overrides']['root']['components']['1']['properties'] == {'5': 100}
    assert 'component_overrides' not in applied['prefab_instances'][-1]
    base_values = deepcopy(entity(scene, first)['components'])
    base_values['1']['properties'].update({'1': 'e1', '2': [], '3': {}, '5': 50})
    changed = reconcile_prefab_assets(applied, replace_root(applied['prefab_assets'], components=base_values))
    assert entity(changed, first)['components']['1']['properties']['5'] == 50
    assert entity(changed, derived)['components']['1']['properties']['5'] == 100


@pytest.mark.parametrize('mask', [{}, {'enabled': False}, {'enabled': 1}, {'present': False},
    {'present': 1}, {'properties': []}, {'properties': [True]}, {'properties': [5, 5]},
    {'properties': ['5']}, {'properties': [6]}, {'unknown': True}])
def test_reject_invalid_explicit_component_override_metadata(mask):
    scene, _, _ = pair_scene()
    scene['prefab_instances'][0]['component_overrides'] = {'root': {'1': mask}}
    with pytest.raises(ValueError):
        validate_scene(scene)


def test_delete_member_clears_explicit_overrides_and_rejects_stale_metadata():
    scene, first, _ = pair_scene()
    child = scene['prefab_instances'][0]['mapping']['e1']
    scene = edit_instance(scene, child, 1, 'add')
    removed = delete_entity(scene, child)
    assert 'e1' not in removed['prefab_instances'][0]['component_overrides']
    removed['prefab_instances'][0]['component_overrides']['e1'] = {'1': {'present': True}}
    with pytest.raises(ValueError, match='live prefab member'):
        validate_scene(removed)


def test_apply_updates_other_instances_keeps_placement_and_individual_properties():
    scene, first, second = pair_scene()
    scene = edit_instance(scene, first, 1, 'set', 80, 5)
    scene = set_entity_property(scene, first, 'layer', 7)
    scene = edit_instance(scene, second, 1, 'set', 'own label', 4)
    # A same-value builtin write deliberately owns the whole Activity component.
    scene = set_entity_property(scene, second, 'active', True)
    before = deepcopy(scene)
    changed = apply_prefab_overrides(scene, first)
    assert scene == before
    assert entity(changed, first)['position'] == [-3, 0, 0]
    assert entity(changed, second)['position'] == [3, 0, 0]
    assert entity(changed, first)['layer'] == 7 and entity(changed, second)['layer'] == 0
    assert changed['prefab_instances'][0]['owned_components']['root'] == ['transform']
    for root in (first, second):
        assert entity(changed, root)['components']['1']['properties']['5'] == 80
    assert entity(changed, second)['components']['1']['properties']['4'] == 'own label'
    template = next(e for e in PrefabLibrary(changed['prefab_assets']).resolve('robot')['entities'] if e['id'] == 'root')
    assert template['position'] == [0, 0, 0] and template['layer'] == 7
    assert template['components']['1']['properties']['1'] == 'e1'
    reset = reset_prefab_instance(changed, second)
    assert entity(reset, second)['layer'] == 7
    assert entity(reset, second)['components']['1']['properties']['4'] == 'player'
    assert reset['prefab_instances'][1]['owned_components']['root'] == ['transform']
    assert entity(reset, second)['position'] == [3, 0, 0]


def test_apply_preserves_variant_and_nested_sources_and_propagates_base_change():
    scene, first, second = pair_scene()
    scene['prefab_assets'][1]['overrides'] = {'root': {'layer': 5}}
    scene['prefab_assets'].append({'version': 1, 'type': 'prefab', 'id': 'pair', 'name': 'Pair',
        'root': 'group', 'entities': [dict(default_scene()['entities'][0], id='group')],
        'nested': [{'id': 'left', 'prefab': 'robot', 'parent': 'group'},
                   {'id': 'right', 'prefab': 'variant', 'parent': 'group'}]})
    scene, variant_root = instantiate_scene_prefab(scene, 'variant')
    scene, nested_root = instantiate_scene_prefab(scene, 'pair')
    original_variant = deepcopy(scene['prefab_assets'][1]); original_nested = deepcopy(scene['prefab_assets'][2])
    scene = set_entity_property(scene, first, 'layer', 8)
    scene = set_entity_property(scene, first, 'tags', ['new'])
    changed = apply_prefab_overrides(scene, first)
    assets = {a['id']: a for a in changed['prefab_assets']}
    assert assets['variant'] == original_variant and assets['pair'] == original_nested
    nested = changed['prefab_instances'][3]['mapping']
    assert entity(changed, variant_root)['layer'] == entity(changed, nested['right'])['layer'] == 5
    assert entity(changed, nested['left'])['layer'] == 8
    assert entity(changed, nested['right'])['tags'] == ['new']
    # Applying to a variant changes its patch, not the base source.
    changed = set_entity_property(changed, variant_root, 'layer', 12)
    changed = apply_prefab_overrides(changed, variant_root)
    assert entity(changed, first)['layer'] == 8
    assert entity(changed, nested['right'])['layer'] == 12
    assert next(a for a in changed['prefab_assets'] if a['id'] == 'variant')['base'] == 'robot'


def test_structural_apply_adopts_ids_remaps_references_and_propagates_additions():
    scene, first, second = pair_scene()
    scene, added = create_entity(scene, 'New member')
    scene = set_entity_property(scene, added, 'parent', first)
    scene = edit_instance(scene, first, 1, 'set', added, 1)
    scene = edit_instance(scene, first, 1, 'set', [first, added], 2)
    scene = edit_instance(scene, first, 1, 'set', {'literal-key': added}, 3)
    updated = apply_prefab_overrides(scene, first)
    a, b = updated['prefab_instances']
    local = next(k for k, v in a['mapping'].items() if v == added)
    assert b['mapping'][local] != added
    for record in (a, b):
        fields = entity(updated, record['root'])['components']['1']['properties']
        assert fields['1'] == record['mapping'][local]
        assert fields['2'] == [record['root'], record['mapping'][local]]
        assert fields['3'] == {'literal-key': record['mapping'][local]}
        assert entity(updated, record['mapping'][local])['parent'] == record['root']
    validate_scene(updated)


def test_removed_template_ids_are_retired_and_readdition_restores_same_identity():
    scene, first, second = pair_scene()
    old_assets = deepcopy(scene['prefab_assets'])
    child = scene['prefab_instances'][0]['mapping']['e1']
    other_child = scene['prefab_instances'][1]['mapping']['e1']
    scene = delete_entity(scene, child)
    for field, value in [(1, ''), (2, [first]), (3, {})]:
        scene = edit_instance(scene, first, 1, 'set', value, field)
    removed = apply_prefab_overrides(scene, first)
    assert len(removed['entities']) == 2
    assert removed['prefab_instances'][0]['retired'] == {'e1': child}
    assert removed['prefab_instances'][1]['retired'] == {'e1': other_child}
    restored = reconcile_prefab_assets(removed, old_assets)
    assert restored['prefab_instances'][0]['mapping']['e1'] == child
    assert restored['prefab_instances'][1]['mapping']['e1'] == other_child
    assert entity(restored, child)['parent'] == first
    assert all('retired' not in r for r in restored['prefab_instances'])


def test_new_descendants_of_deleted_member_stay_tombstones_until_reset():
    scene, first, second = pair_scene()
    record = scene['prefab_instances'][0]
    scene = delete_entity(scene, record['mapping']['e1'])
    assets = deepcopy(scene['prefab_assets'])
    assets[0]['entities'].append(dict(default_scene()['entities'][0], id='grandchild', parent='e1'))
    updated = reconcile_prefab_assets(scene, assets)
    a, b = updated['prefab_instances']
    assert a['mapping']['grandchild'] not in {e['id'] for e in updated['entities']}
    assert entity(updated, b['mapping']['grandchild'])['parent'] == b['mapping']['e1']
    restored = reset_prefab_instance(updated, first)
    assert entity(restored, a['mapping']['grandchild'])['parent'] == a['mapping']['e1']


def test_reset_restores_detached_deleted_members_and_removes_added_instances():
    scene, first, second = pair_scene()
    child = scene['prefab_instances'][0]['mapping']['e1']
    scene = set_entity_property(scene, child, 'parent', '')
    scene, nested = instantiate_scene_prefab(scene, 'variant', parent=child)
    nested_child = scene['prefab_instances'][2]['mapping']['e1']
    scene = set_entity_property(scene, nested_child, 'parent', '')
    reset = reset_prefab_instance(scene, first, keep_placement=False)
    assert entity(reset, first)['position'] == [0, 0, 0]
    assert entity(reset, child)['parent'] == first
    assert {e['id'] for e in reset['entities']} == {e['id'] for e in scene['entities']} - {nested, nested_child}
    assert len(reset['prefab_instances']) == 2
    assert entity(reset, second)['position'] == [3, 0, 0]
    removed = delete_entity(reset, child)
    restored = reset_prefab_instance(removed, first)
    assert entity(restored, child)['parent'] == first


def test_reset_component_additions_removals_and_field_overrides():
    scene, first, second = pair_scene()
    child = scene['prefab_instances'][0]['mapping']['e1']
    scene = edit_instance(scene, first, 1, 'remove')
    scene = edit_instance(scene, child, 1, 'add')
    reset = reset_prefab_instance(scene, child)
    assert entity(reset, first)['components']['1']['properties']['1'] == child
    assert entity(reset, child)['components'] == {}
    changed = reconcile_prefab_assets(scene, replace_root(scene['prefab_assets'], layer=9))
    assert entity(changed, first)['components'] == {}  # A local removal survives a source edit.
    assert '1' in entity(changed, child)['components']


def test_propagation_reparents_local_additions_when_template_parent_is_removed():
    scene, first, second = pair_scene()
    other_child = scene['prefab_instances'][1]['mapping']['e1']
    scene, added = create_entity(scene, 'Local extra')
    scene = set_entity_property(scene, added, 'parent', other_child)
    child = scene['prefab_instances'][0]['mapping']['e1']
    scene = delete_entity(scene, child)
    for field, value in [(1, ''), (2, []), (3, {})]:
        scene = edit_instance(scene, first, 1, 'set', value, field)
    changed = apply_prefab_overrides(scene, first)
    assert entity(changed, added)['parent'] == second
    assert added not in changed['prefab_instances'][1]['mapping'].values()


def test_invalid_dependencies_external_refs_and_cross_instance_apply_are_transactional():
    scene, first, second = pair_scene()
    external = edit_instance(scene, first, 1, 'set', second, 1)
    before = deepcopy(external)
    with pytest.raises(ValueError, match='External or deleted entity reference'):
        apply_prefab_overrides(external, first)
    assert external == before
    scene, nested = instantiate_scene_prefab(scene, 'robot', parent=first)
    before = deepcopy(scene)
    with pytest.raises(ValueError, match='dependency cycle'):
        apply_prefab_overrides(scene, first)
    assert scene == before
    assets = deepcopy(scene['prefab_assets']); assets[1]['base'] = 'missing'
    with pytest.raises(ValueError, match='Missing prefab dependency'):
        reconcile_prefab_assets(scene, assets)
    assert scene == before


def test_new_root_transform_keeps_placement_with_real_owned_metadata():
    scene, first, second = pair_scene()
    scene, third = instantiate_scene_prefab(scene, 'robot')
    changed = reconcile_prefab_assets(scene, replace_root(scene['prefab_assets'], position=[12, 0, 0]))
    assert entity(changed, third)['position'] == [0, 0, 0]
    assert changed['prefab_instances'][2]['owned_components']['root'] == ['transform']


def test_native_tag_order_does_not_become_an_override_during_propagation():
    scene, first, second = pair_scene()
    scene = reconcile_prefab_assets(scene, replace_root(scene['prefab_assets'], tags=['z', 'a']))
    # Native snapshots sort the set, regardless of the order in authored sources.
    for root in (first, second):
        entity(scene, root)['tags'] = ['a', 'z']
    changed = reconcile_prefab_assets(scene, replace_root(scene['prefab_assets'], tags=['updated']))
    assert entity(changed, first)['tags'] == entity(changed, second)['tags'] == ['updated']
    assert all('tags' not in r['owned_components']['root'] for r in changed['prefab_instances'])


def test_removing_base_member_with_dependent_patch_reports_conflict_without_data_loss():
    scene, first, second = pair_scene()
    scene['prefab_assets'][1]['overrides'] = {'e1': {'layer': 3}}
    child = scene['prefab_instances'][0]['mapping']['e1']
    scene = delete_entity(scene, child)
    for field, value in [(1, ''), (2, []), (3, {})]:
        scene = edit_instance(scene, first, 1, 'set', value, field)
    original = deepcopy(scene)
    with pytest.raises(ValueError, match='Override targets missing local entity'):
        apply_prefab_overrides(scene, first)
    assert scene == original


@pytest.mark.parametrize('retired', [{'e1': 'gone'}, {'gone': 'shared'}, {'gone': ''}, {'gone': 'same', 'other': 'same'}])
def test_invalid_retired_metadata_rejected(retired):
    scene, first, second = pair_scene()
    scene['prefab_instances'][0]['retired'] = retired
    if retired == {'gone': 'shared'}:
        scene['prefab_instances'][1]['retired'] = {'different': 'shared'}
    with pytest.raises(ValueError, match='Retired prefab|cannot share'):
        validate_scene(scene)
