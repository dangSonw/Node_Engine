"""Portable prefab authoring, typed references, inheritance and nested assets."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from editor.core.document import default_scene, save_json
from editor.core.prefabs import PrefabLibrary, capture_prefab, load_prefab, load_prefab_library
from editor.core.scene import validate_scene


def reference_scene():
    scene = default_scene()
    scene['component_definitions'] = [{'id': 1, 'name': 'Links', 'properties': [
        {'id': 1, 'name': 'Target', 'type': 'entity', 'default': ''},
        {'id': 2, 'name': 'Friends', 'type': 'array<entity>', 'default': []},
        {'id': 3, 'name': 'Slots', 'type': 'map<entity>', 'default': {}},
        {'id': 4, 'name': 'Label', 'type': 'string', 'default': ''},
        {'id': 5, 'name': 'Health', 'type': 'int', 'default': 100},
    ]}]
    root = scene['entities'][0]
    root['components'] = {'1': {'enabled': True, 'properties': {
        '1': 'child', '2': ['player', 'child', ''],
        '3': {'player': 'child', 'empty': ''}, '4': 'player'}}}
    root['mesh'] = 'assets/robot.gltf'
    root['tags'] = ['actor']
    scene['entities'].append(dict(deepcopy(root), id='child', name='Child', parent='player', components={}))
    scene['entities'].append(dict(deepcopy(root), id='outside', name='Outside', components={}))
    return scene


def robot():
    return capture_prefab(reference_scene(), 'player', 'Rô-bốt', asset_id='robot')


def variant(aid='variant', **updates):
    return dict(version=1, type='prefab', id=aid, name=aid, base='robot', **updates)


def by_id(resolved):
    return {e['id']: e for e in resolved['entities']}


def test_capture_subtree_and_two_instances_remap_typed_references_only():
    scene = reference_scene(); before = deepcopy(scene)
    asset = capture_prefab(scene, 'player', 'Robot', asset_id='robot')
    library = PrefabLibrary([asset])
    assert scene == before
    assert by_id(library.resolve('robot'))['root']['components']['1']['properties']['5'] == 100
    left = library.instantiate_entities('robot', mapping={'root': 'left', 'e1': 'left-child'}, position=[-2, 0, 0])
    right = library.instantiate_entities('robot', mapping={'root': 'right', 'e1': 'right-child'}, position=[2, 0, 0])
    for instance in (left, right):
        root = by_id(instance)[instance['root']]
        fields = root['components']['1']['properties']
        assert fields['1'] == instance['mapping']['e1']
        assert fields['2'] == [instance['root'], instance['mapping']['e1'], '']
        assert fields['3'] == {'player': instance['mapping']['e1'], 'empty': ''}
        assert fields['4'] == 'player'
        assert by_id(instance)[instance['mapping']['e1']]['parent'] == instance['root']
    assembled = {'entities': left['entities'] + right['entities'], 'variables': {},
                 'component_definitions': library.component_definitions}
    validate_scene(assembled)
    assert left['root'] != right['root'] and asset['entities'][0]['id'] != 'left'


@pytest.mark.parametrize('field,value', [('1', 'outside'), ('2', ['child', 'outside']),
                                        ('3', {'same': 'outside', 'kept': 'child'})])
def test_capture_external_references_require_explicit_policy(field, value):
    scene = reference_scene()
    scene['entities'][0]['components']['1']['properties'][field] = value
    before = deepcopy(scene)
    with pytest.raises(ValueError, match='External entity reference'):
        capture_prefab(scene, 'player', 'Robot')
    cleared = capture_prefab(scene, 'player', 'Robot', external_references='clear')
    result = by_id(PrefabLibrary([cleared]).resolve(cleared['id']))['root']['components']['1']['properties'][field]
    assert result == {'1': '', '2': ['e1', ''], '3': {'same': '', 'kept': 'e1'}}[field]
    assert scene == before


def test_variants_propagate_base_edits_preserve_patches_and_reset_by_removing_patch():
    base = robot()
    derived = variant(overrides={'root': {'layer': 7, 'components': {'1': {'properties': {'5': 200}}}}})
    grandchild = variant('elite', overrides={'e1': {'active': False}})
    grandchild['base'] = 'variant'
    initial = PrefabLibrary([grandchild, derived, base]).resolve('elite')
    assert initial['dependencies'] == ['robot', 'variant'] and initial['dependency_depth'] == 3
    changed = deepcopy(base)
    next(e for e in changed['entities'] if e['id'] == 'root')['tags'] = ['changed']
    next(e for e in changed['entities'] if e['id'] == 'root')['components']['1']['properties']['5'] = 80
    updated = by_id(PrefabLibrary([derived, changed, grandchild]).resolve('elite'))
    assert updated['root']['tags'] == ['changed']
    assert updated['root']['layer'] == 7 and updated['root']['components']['1']['properties']['5'] == 200
    assert updated['root']['components']['1']['properties']['1'] == 'e1' and not updated['e1']['active']
    del derived['overrides']['root']['components']
    reset = by_id(PrefabLibrary([changed, derived, grandchild]).resolve('elite'))
    assert reset['root']['components']['1']['properties']['5'] == 80 and reset['root']['layer'] == 7


def test_nested_prefabs_keep_namespaces_and_independent_overrides():
    base = robot()
    parent = {'version': 1, 'type': 'prefab', 'id': 'squad', 'name': 'Squad', 'root': 'group',
              'entities': [dict(default_scene()['entities'][0], id='group')],
              'nested': [{'id': 'one', 'prefab': 'robot', 'parent': 'group',
                          'overrides': {'root': {'position': [-2, 0, 0]}}},
                         {'id': 'two', 'prefab': 'robot', 'parent': 'group',
                          'overrides': {'e1': {'active': False}}}],
              'overrides': {'two': {'layer': 4}}}
    library = PrefabLibrary([parent, base])
    result = by_id(library.resolve('squad'))
    assert set(result) == {'group', 'one', 'one/e1', 'two', 'two/e1'}
    assert result['one']['parent'] == result['two']['parent'] == 'group'
    assert result['one/e1']['active'] and not result['two/e1']['active']
    assert result['one']['position'] == [-2, 0, 0] and result['two']['layer'] == 4
    assert result['one']['components']['1']['properties']['1'] == 'one/e1'
    assert result['two']['components']['1']['properties']['2'] == ['two', 'two/e1', '']
    ids = {k: f'instance-{i}' for i, k in enumerate(sorted(result))}
    candidate = library.instantiate_entities('squad', mapping=ids)
    assert by_id(candidate)[ids['two']]['components']['1']['properties']['1'] == ids['two/e1']
    assert library.resolve('squad')['entities'] == list(result.values())


def test_component_add_remove_and_structural_removal_require_reference_repair():
    base = robot()
    derived = variant(overrides={'e1': {'components': {'1': {'properties': {'5': 20}}}},
                                 'root': {'components': {'1': None}}})
    result = by_id(PrefabLibrary([base, derived]).resolve('variant'))
    assert result['root']['components'] == {} and result['e1']['components']['1']['properties']['5'] == 20
    broken = variant(removed=['e1'])
    with pytest.raises(ValueError, match='reference targets missing'):
        PrefabLibrary([base, broken])
    broken['overrides'] = {'root': {'components': {'1': {'properties': {'1': '', '2': ['root'], '3': {}}}}}}
    assert set(by_id(PrefabLibrary([base, broken]).resolve('variant'))) == {'root'}


def test_structural_additions_removals_and_immutable_input():
    base = robot()
    variant_ = variant(entities=[dict(default_scene()['entities'][0], id='new', parent='e1')])
    removed = variant('trimmed', removed=['e1'], overrides={'root': {'components': {'1': None}}})
    removed['base'] = 'variant'
    assets = [base, variant_, removed]; before = deepcopy(assets)
    lib = PrefabLibrary(assets)
    assert set(by_id(lib.resolve('variant'))) == {'root', 'e1', 'new'}
    assert set(by_id(lib.resolve('trimmed'))) == {'root'}
    view = lib.resolve('variant'); view['entities'][0]['name'] = 'MUTATED'
    lib.assets[0]['name'] = 'MUTATED'
    lib.component_definitions[0]['name'] = 'MUTATED'
    assert assets == before and all(e['name'] != 'MUTATED' for e in lib.resolve('variant')['entities'])


@pytest.mark.parametrize('change,match', [
    ({'version': True}, 'version'), ({'version': 2}, 'version'),
    ({'id': '../bad'}, 'Prefab ID'), ({'name': ''}, 'name'),
    ({'root': 'missing'}, 'root is missing'), ({'base': []}, 'base'),
    ({'overrides': []}, 'overrides'), ({'removed': ['root']}, 'remove the prefab root'),
    ({'removed': ['missing']}, 'Removal targets'), ({'removed': [2]}, 'unique strings'),
    ({'overrides': {'e1': {'id': 'other'}}}, 'unsupported fields'),
    ({'overrides': {'e1': {'parent': 'e1'}}}, 'cycle'),
    ({'overrides': {'e1': {'parent': ''}}}, 'exactly one root'),
    ({'overrides': {'e1': {'mesh': False}}}, 'Prefab mesh'),
    ({'overrides': {'e1': {'position': [10**400, 0, 0]}}}, 'finite'),
    ({'overrides': {'root': {'components': {'1': {'properties': {'5': 'bad'}}}}}}, 'Invalid component property'),
    ({'overrides': {'e1': {'components': {'1': None}}}}, 'absent component'),
    ({'overrides': {'missing': {'layer': 2}}}, 'Override targets'),
    ({'nested': [{'id': 'e1', 'prefab': 'small'}]}, 'collision'),
])
def test_invalid_assets_fail_before_mutation(change, match):
    asset = robot(); asset.update(change); before = deepcopy(asset)
    small = capture_prefab(default_scene(), 'player', 'Small', asset_id='small')
    with pytest.raises(ValueError, match=match): PrefabLibrary([asset, small])
    assert asset == before


@pytest.mark.parametrize('dependency', ['base', 'nested'])
def test_dependency_cycle_missing_and_depth_limit_independent_of_input_order(dependency):
    a = robot(); b = variant('second')
    if dependency == 'base': a['base'] = 'second'
    else: a['nested'] = [{'id': 'loop', 'prefab': 'second', 'parent': 'root'}]
    with pytest.raises(ValueError, match='dependency cycle'): PrefabLibrary([a, b])
    b['base'] = 'missing'
    with pytest.raises(ValueError, match='Missing prefab dependency'): PrefabLibrary([b])
    chain = [robot()]
    for i in range(32):
        item = variant(f'v{i}'); item['base'] = chain[-1]['id']; chain.append(item)
    for ordered in (chain, list(reversed(chain))):
        with pytest.raises(ValueError, match='exceed 32 levels'): PrefabLibrary(ordered)
    assert PrefabLibrary(chain[:32]).resolve('v30')['dependency_depth'] == 32


@pytest.mark.parametrize('mapping', [{}, {'root': 'a'}, {'root': 'a', 'e1': 'a'},
                                   {'root': '', 'e1': 'b'}, {'root': 'a', 'e1': 'b', 'extra': 'c'}])
def test_instance_mapping_cannot_lose_alias_or_retarget_ids(mapping):
    with pytest.raises(ValueError, match='mapping|IDs'):
        PrefabLibrary([robot()]).instantiate_entities('robot', mapping=mapping)


def test_instance_placement_is_checked_and_existing_mapping_is_reusable():
    lib = PrefabLibrary([robot()])
    one = lib.instantiate_entities('robot', parent='existing-parent')
    again = lib.instantiate_entities('robot', mapping=one['mapping'], parent='existing-parent')
    assert one == again
    with pytest.raises(ValueError, match='outside the instance'):
        lib.instantiate_entities('robot', mapping=one['mapping'], parent=one['root'])
    with pytest.raises(ValueError, match='finite'):
        lib.instantiate_entities('robot', position=[float('inf'), 0, 0])


def test_real_asset_files_keep_dependencies_roundtrip_and_validate_project_paths(tmp_path):
    base, derived = robot(), variant(overrides={'e1': {'layer': 31}})
    for asset in (base, derived):
        save_json(tmp_path / 'assets/prefabs' / (asset['id'] + '.prefab.json'), asset)
    paths = ['assets/prefabs/variant.prefab.json', 'assets/prefabs/robot.prefab.json']
    library = load_prefab_library(tmp_path, paths)
    assert load_prefab(tmp_path / paths[0])['base'] == 'robot'
    assert by_id(library.resolve('variant'))['e1']['layer'] == 31
    assert not save_json(tmp_path / paths[0], derived)
    with pytest.raises(ValueError, match='within the project'): load_prefab_library(tmp_path, ['../outside.json'])
    with pytest.raises(ValueError, match='Duplicate prefab asset path'): load_prefab_library(tmp_path, [paths[0], paths[0]])
    broken = tmp_path / 'bad.prefab.json'; broken.write_text('{"id":"a","id":"b"}')
    with pytest.raises(ValueError, match='Duplicate JSON key'): load_prefab(broken)
    broken.write_text('{"version":NaN}')
    with pytest.raises(ValueError, match='Non-finite'): load_prefab(broken)


def test_component_schema_collision_does_not_reinterpret_stable_ids():
    first = robot(); second = deepcopy(first); second['id'] = 'other'
    second['component_definitions'][0]['properties'][4]['type'] = 'float'
    with pytest.raises(ValueError, match='Conflicting component definition'):
        PrefabLibrary([first, second])
    with pytest.raises(ValueError, match='Duplicate prefab ID'): PrefabLibrary([first, first])


def test_cli_captures_and_inspects_actual_project_without_replacing_files(tmp_path, capsys):
    from editor.core.document import create_project
    from tools.prefab_asset import main
    project = create_project(tmp_path / 'game', 'My game')
    before = project.read_bytes()
    args = ['capture', '--project', str(project), '--root', 'player', '--name', 'Player',
            '--id', 'player-template', '--output', 'assets/player.prefab.json']
    main(args)
    result = json.loads(capsys.readouterr().out)
    path = Path(result['path'])
    assert result['entities'] == 1 and path.exists()
    original = path.read_bytes()
    with pytest.raises(SystemExit) as error: main(args)
    assert error.value.code == 2 and 'already exists' in capsys.readouterr().err
    assert path.read_bytes() == original and project.read_bytes() == before
    main(['inspect', '--project', str(project), '--prefab', 'player-template', 'assets/player.prefab.json'])
    assert json.loads(capsys.readouterr().out)['root'] == 'root'
    bad = args[:-1] + ['../escape.prefab.json']
    with pytest.raises(SystemExit): main(bad)
    assert not (tmp_path / 'escape.prefab.json').exists()
