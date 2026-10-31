"""Three Blockbench robots share a material; keys edit only the center instance."""
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from editor.core.registry import ROOT
from editor.core.builder import GraphBuilder
from editor.core.camera import default_camera
from editor.core.document import save_json
from editor.core.materials import new_asset
from editor.core.compiler import compile_graph
from editor.core.codegen import export


def create(directory=ROOT / 'examples/material_demo'):
    directory = Path(directory); (directory / 'assets').mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'examples/camera_demo/assets/robot.gltf', directory / 'assets/robot.gltf')
    material = dict(new_asset('Robot blue'), id='robot_blue', color=[.12, .45, 1], unlit=True)
    entities = [dict(id=eid, name=name, position=[x, 0, 0], rotation=[0, 20, 0], scale=[1, 1, 1],
        mesh='assets/robot.gltf', material={'asset': material['id'], 'overrides': {}})
        for eid, name, x in [('left', 'Shared material', -2.5), ('player', 'Editable instance', 0), ('right', 'Shared material', 2.5)]]
    entities.append(dict(id='camera', name='Material camera', position=[0, 2, 8], rotation=[0, 0, 0], scale=[1, 1, 1],
        camera=dict(default_camera(), projection='orthographic', size=6)))
    scene = dict(entities=entities, variables={}, material_assets=[material], active_camera='camera',
        input=dict(version=1, actions=dict(tint=['T'], fade=['F'], reset=['R'], original=['O']), axes={}))
    b = GraphBuilder('Material instances: T tint, F fade, R reset, O original')
    b.add('start', 'On Game Start'); b.add('aim', 'Camera Look At', Target=[0, .8, 0]); b.connect('start', 'Out', 'aim', 'In')
    actions = {'tint': [('Set Material', {'Material': 'robot_blue'}), ('Set Material Color', {'Color': [1, .18, .04]})],
        'fade': [('Set Material', {'Material': 'robot_blue'}), ('Set Material Alpha Mode', {'Mode': 'blend'}), ('Set Material Opacity', {'Opacity': .3})],
        'reset': [('Set Material', {'Material': 'robot_blue'})], 'original': [('Clear Material', {})]}
    for action, nodes in actions.items():
        b.add(action + '_update', 'On Update'); b.add(action + '_pressed', 'Is Action Pressed', Action=action)
        b.add(action + '_branch', 'Branch'); b.connect(action + '_update', 'Out', action + '_branch', 'In')
        b.connect(action + '_pressed', 'Value', action + '_branch', 'Condition')
        previous, port = action + '_branch', 'True'
        for index, (name, values) in enumerate(nodes):
            nid = action + '_' + str(index); b.add(nid, name, **values); b.connect(previous, port, nid, 'In'); previous, port = nid, 'Out'
    for index, node in enumerate(b.graph['nodes']): node['position'] = [(index % 5)*260, (index // 5)*240]
    save_json(directory / 'project.json', dict(version=1, name='Material instances', graph='graphs/gameplay.json', scene='scenes/main.json', assets=['assets/robot.gltf']))
    save_json(directory / 'scenes/main.json', scene); save_json(directory / 'graphs/gameplay.json', b.graph)
    save_json(directory / 'input-replay.json', {'version': 1, 'events': [
        {'frame': frame + released, 'button': key, 'down': not released}
        for frame, key in [(2, 'T'), (4, 'F'), (6, 'O'), (8, 'R')] for released in (0, 1)]})
    export(compile_graph(b.graph, scene), directory / 'generated')
    return directory


if __name__ == '__main__': print(create())
