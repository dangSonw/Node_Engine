"""Compile malformed scenes safely and keep authored templates authoritative."""
from copy import deepcopy
import pytest
from editor.core.builder import GraphBuilder
from editor.core.compiler import compile_graph
from editor.core.prefabs import PrefabLibrary, prepare_scene_prefabs
from tests.test_prefabs import robot, variant


def scene():
    return {'entities': [], 'variables': {}, 'prefab_assets': [variant(), robot()]}


@pytest.mark.parametrize('entities', [None, {}, [None], [{}], [{'id': []}], [{'id': 'a'}]])
def test_malformed_prefab_scene_reports_validation_error(entities):
    data = scene(); data['entities'] = entities
    with pytest.raises(ValueError):
        compile_graph(GraphBuilder().graph, data)


def test_missing_entities_and_detached_compiled_templates_are_rejected():
    data = scene(); del data['entities']
    with pytest.raises(ValueError, match='Scene requires'):
        prepare_scene_prefabs(data)
    with pytest.raises(ValueError, match='authored prefab assets'):
        prepare_scene_prefabs({'entities': [], 'variables': {}, 'prefab_templates': []})


def test_lowering_orders_dependencies_and_rebuilds_stale_templates_without_mutation():
    data = scene(); data['prefab_templates'] = [{'id': 'stale'}]; before = deepcopy(data)
    compiled = prepare_scene_prefabs(data)
    assert data == before
    assert [t['id'] for t in compiled['prefab_templates']] == ['robot', 'variant']
    assert compiled['prefab_templates'][1]['bases']['root'] == {'asset': 'robot', 'local': 'root'}
    assert compiled['component_definitions'] == robot()['component_definitions']


@pytest.mark.parametrize('edit,match', [
    (lambda r: r['mapping'].update(e1='a'), 'unique'),
    (lambda r: r.update(root='b'), 'live mapped root'),
    (lambda r: r.update(owned_components={'root': ['identity']}), 'owned component'),
    (lambda r: r.update(owned_components={'root': ['mesh', 'mesh']}), 'owned component'),
    (lambda r: r.update(owned_components={'unknown': []}), 'owned component'),
])
def test_malformed_instance_metadata_is_rejected(edit, match):
    data = scene(); library = PrefabLibrary(data['prefab_assets'])
    record = library.instantiate_entities('robot', mapping={'root': 'a', 'e1': 'b'})
    data['entities'] = record.pop('entities'); edit(record); data['prefab_instances'] = [record]
    with pytest.raises(ValueError, match=match):
        prepare_scene_prefabs(data)


def test_tombstones_reserve_ownership_and_disallow_overlapping_instances():
    data = scene(); library = PrefabLibrary(data['prefab_assets'])
    record = library.instantiate_entities('robot', mapping={'root': 'a', 'e1': 'b'})
    data['entities'] = [e for e in record.pop('entities') if e['id'] == 'a']
    data['prefab_instances'] = [record]
    assert prepare_scene_prefabs(data)['prefab_instances'][0]['mapping']['e1'] == 'b'
    second = library.instantiate_entities('variant', mapping={'root': 'c', 'e1': 'b'})
    data['entities'] += [e for e in second.pop('entities') if e['id'] == 'c']
    data['prefab_instances'].append(second)
    with pytest.raises(ValueError, match='cannot share entity IDs'):
        prepare_scene_prefabs(data)
