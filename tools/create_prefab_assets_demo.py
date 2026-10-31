"""Rebuild the Blockbench-based prefab authoring fixtures (no native instances)."""
from editor.core.document import default_scene, load_project, save_json
from editor.core.prefabs import PrefabLibrary, capture_prefab, load_prefab_library
from editor.core.registry import ROOT


def main():
    project = ROOT / 'examples/activity_demo'
    _, _, scene = load_project(project / 'project.json')
    robot = capture_prefab(scene, 'player', 'Robot', asset_id='robot')
    robot['entities'][0]['position'] = [0, 0, 0]
    inactive = {'version': 1, 'type': 'prefab', 'id': 'inactive_robot', 'name': 'Inactive Robot',
                'base': 'robot', 'overrides': {'root': {'active': False, 'layer': 5}}}
    group = {'version': 1, 'type': 'prefab', 'id': 'robot_pair', 'name': 'Robot Pair', 'root': 'group',
             'entities': [dict(default_scene()['entities'][0], id='group', name='Robot Pair')],
             'nested': [{'id': 'left', 'prefab': 'robot', 'parent': 'group',
                         'overrides': {'root': {'position': [-2.2, 0, 0]}}},
                        {'id': 'right', 'prefab': 'inactive_robot', 'parent': 'group',
                         'overrides': {'root': {'position': [2.2, 0, 0]}}}]}
    assets = [robot, inactive, group]
    PrefabLibrary(assets)
    paths = []
    for asset in assets:
        relative = f"assets/prefabs/{asset['id']}.prefab.json"
        save_json(project / relative, asset)
        paths.append(relative)
    library = load_prefab_library(project, paths)
    resolved = library.resolve('robot_pair')
    by_id = {e['id']: e for e in resolved['entities']}
    assert len(by_id) == 3 and by_id['left']['active'] and not by_id['right']['active']
    assert by_id['left']['mesh'] == by_id['right']['mesh'] == 'assets/robot.gltf'
    assert (project / by_id['left']['mesh']).is_file()
    evidence = ROOT / 'artifacts/validation'
    save_json(evidence / 'prefab-pair-resolved.json', resolved)
    first = library.instantiate_entities('robot_pair', mapping={'group': 'group-a', 'left': 'left-a', 'right': 'right-a'})
    second = library.instantiate_entities('robot_pair', mapping={'group': 'group-b', 'left': 'left-b', 'right': 'right-b'})
    save_json(evidence / 'prefab-instance-candidates.json', [first, second])
    print('Validated 3 prefab asset files, 3 resolved entities and 2 distinct instance mappings.')
    print('Run tools.create_prefabs_demo for the native/editor instantiation example.')


if __name__ == '__main__':
    main()
