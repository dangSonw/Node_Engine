"""Spawn a nested Blockbench robot prefab into an initially empty native scene."""
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.compiler import compile_graph
from editor.core.document import save_json
from editor.core.prefabs import load_prefab_library
from editor.core.registry import ROOT


def create():
    project = ROOT / 'examples/prefabs_demo'
    source = ROOT / 'examples/activity_demo'
    (project / 'assets/prefabs').mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / 'assets/robot.gltf', project / 'assets/robot.gltf')
    paths = [f'assets/prefabs/{aid}.prefab.json' for aid in ('robot', 'inactive_robot', 'robot_pair')]
    library = load_prefab_library(source, paths)
    for path in paths:
        shutil.copy2(source / path, project / path)
    # Authored sources remain in the scene so preview/export use the same
    # validated library; File > Register Prefab Files performs this in the editor.
    scene = {'version': 1, 'entities': [], 'variables': {},
             'component_definitions': library.component_definitions, 'prefab_assets': library.assets}
    b = GraphBuilder('Nested prefab robots', component_definitions=library.component_definitions)
    nodes = [
        ('start', 'On Game Start', {}),
        ('spawn', 'Instantiate Prefab', {'Prefab': 'robot_pair'}),
        ('left', 'Get Prefab Entity', {'LocalID': 'left'}),
        ('right', 'Get Prefab Entity', {'LocalID': 'right'}),
        ('enable', 'Set Entity Active', {'Active': True}),
        ('save_left', 'Set Entity Variable', {'Name': 'left'}),
        ('save_right', 'Set Entity Variable', {'Name': 'right'}),
        ('update', 'On Update', {}),
        ('get_left', 'Get Entity Variable', {'Name': 'left'}),
        ('get_right', 'Get Entity Variable', {'Name': 'right'}),
        ('rotate_left', 'Rotate', {'Degrees': [0, 1, 0]}),
        ('rotate_right', 'Rotate', {'Degrees': [0, -1, 0]}),
    ]
    for i, (nid, name, values) in enumerate(nodes):
        b.add(nid, name, **values)
        b.graph['nodes'][-1]['position'] = [(i % 4) * 300, (i // 4) * 240]
    for edge in [
        ('start', 'Out', 'spawn', 'In'), ('spawn', 'Out', 'enable', 'In'),
        ('spawn', 'Entity', 'left', 'Instance'), ('spawn', 'Entity', 'right', 'Instance'),
        ('right', 'Entity', 'enable', 'Entity'), ('enable', 'Out', 'save_left', 'In'),
        ('left', 'Entity', 'save_left', 'Value'), ('save_left', 'Out', 'save_right', 'In'),
        ('right', 'Entity', 'save_right', 'Value'),
        ('update', 'Out', 'rotate_left', 'In'), ('rotate_left', 'Out', 'rotate_right', 'In'),
        ('get_left', 'Value', 'rotate_left', 'Entity'), ('get_right', 'Value', 'rotate_right', 'Entity'),
    ]:
        b.connect(*edge)
    ir = compile_graph(b.graph, scene)
    save_json(project / 'scenes/main.json', scene)
    save_json(project / 'graphs/gameplay.json', b.graph)
    save_json(project / 'project.json', {'version': 1, 'name': 'Nested prefab robots',
        'graph': 'graphs/gameplay.json', 'scene': 'scenes/main.json', 'assets': ['assets/robot.gltf']})
    export(ir, project / 'generated')
    return project


if __name__ == '__main__':
    print(create())
