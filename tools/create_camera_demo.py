"""Playable robot with a following camera and a projection toggle on C."""
from copy import deepcopy
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from editor.core.registry import ROOT
from editor.core.builder import GraphBuilder
from editor.core.document import load_project, save_json
from editor.core.camera import default_camera
from editor.core.compiler import compile_graph
from editor.core.codegen import export


def create():
    source = ROOT / 'examples/input_demo'
    project, graph, scene = load_project(source / 'project.json')
    destination = ROOT / 'examples/camera_demo'
    (destination / 'assets').mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / 'assets/robot.gltf', destination / 'assets/robot.gltf')
    shutil.copy2(source / 'input-replay.json', destination / 'input-replay.json')
    scene['entities'].append({'id': 'camera', 'name': 'Following camera',
        'position': [0, 2, 6], 'rotation': [0, 0, 0], 'scale': [1, 1, 1], 'camera': default_camera()})
    for index, position in enumerate([[-4, 0, -2], [4, 0, -2]]):
        landmark = deepcopy(scene['entities'][0])
        landmark.update(id=f'landmark_{index}', name=f'Landmark {index + 1}', position=position)
        scene['entities'].append(landmark)
    scene['active_camera'] = 'camera'
    scene['input']['actions']['projection'] = ['C']
    scene['variables']['camera_ortho'] = {'type': 'bool', 'value': False}
    b = GraphBuilder('Robot camera playground')
    b.graph = graph
    for nid, name, values in [
        ('camera_start', 'On Game Start', {}), ('initial_aim', 'Camera Look At', {'Target': [0, .7, 0]}),
        ('camera_update', 'On Update', {}), ('follow', 'Camera Follow', {'Rate': 6}),
        ('player_world', 'Get World Position', {}), ('aim_point', 'Vector Add', {'B': [0, .7, 0]}),
        ('aim', 'Camera Look At', {}), ('projection_pressed', 'Is Action Pressed', {'Action': 'projection'}),
        ('toggle_projection', 'Branch', {}), ('camera_mode', 'Get Boolean Variable', {'Name': 'camera_ortho'}),
        ('invert_mode', 'NOT', {}), ('save_mode', 'Set Boolean Variable', {'Name': 'camera_ortho'}),
        ('choose_projection', 'Branch', {}), ('ortho', 'Set Camera Orthographic', {'Height': 6}),
        ('perspective', 'Set Camera Perspective', {}),
    ]:
        b.add(nid, name, **values)
        index = len(b.graph['nodes']) - 1
        b.graph['nodes'][-1]['position'] = [(index % 6) * 260, (index // 6) * 240]
    for edge in [
        ('camera_start', 'Out', 'initial_aim', 'In'), ('camera_update', 'Out', 'follow', 'In'),
        ('follow', 'Out', 'aim', 'In'), ('player_world', 'Value', 'aim_point', 'A'),
        ('aim_point', 'Value', 'aim', 'Target'), ('aim', 'Out', 'toggle_projection', 'In'),
        ('projection_pressed', 'Value', 'toggle_projection', 'Condition'),
        ('toggle_projection', 'True', 'save_mode', 'In'), ('camera_mode', 'Value', 'invert_mode', 'Value'),
        ('invert_mode', 'Value', 'save_mode', 'Value'), ('save_mode', 'Out', 'choose_projection', 'In'),
        ('camera_mode', 'Value', 'choose_projection', 'Condition'),
        ('choose_projection', 'True', 'ortho', 'In'), ('choose_projection', 'False', 'perspective', 'In'),
    ]:
        b.connect(*edge)
    project['name'] = 'Robot camera playground'
    save_json(destination / 'project.json', project)
    save_json(destination / project['graph'], b.graph)
    save_json(destination / project['scene'], scene)
    export(compile_graph(b.graph, scene), destination / 'generated')
    return destination


if __name__ == '__main__':
    print(create())
