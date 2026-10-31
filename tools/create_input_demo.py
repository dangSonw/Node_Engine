"""A Blockbench robot controlled by scene-owned actions and digital axes."""
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from editor.core.registry import ROOT
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene, save_json
from editor.core.compiler import compile_graph
from editor.core.codegen import export


def create():
    project = ROOT / 'examples/input_demo'
    (project / 'assets').mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'examples/components_demo/assets/robot.gltf', project / 'assets/robot.gltf')
    scene = default_scene()
    scene['entities'][0].update(name='Controlled robot', mesh='assets/robot.gltf')
    scene['input'] = {'version': 1, 'actions': {'turn': ['Space', 'MouseLeft'], 'reset': ['R']},
        'axes': {'horizontal': {'negative': ['A', 'Left'], 'positive': ['D', 'Right']},
                 'vertical': {'negative': ['W', 'Up'], 'positive': ['S', 'Down']}}}
    scene['variables'] = {'turn_count': 0., 'release_count': 0., 'horizontal': 0.,
                          'turn_held': {'type': 'bool', 'value': False}}
    b = GraphBuilder('Robot input playground')
    for nid, name, values in [
        ('update', 'On Update', {}), ('x', 'Get Input Axis', {'Axis': 'horizontal'}),
        ('z', 'Get Input Axis', {'Axis': 'vertical'}), ('direction', 'Make Vector3', {}),
        ('normalize', 'Normalize', {}), ('dt', 'Get Delta Time', {}), ('speed', 'Multiply', {'B': 3.}),
        ('delta', 'Vector Scale', {}), ('move', 'Translate', {}),
        ('held', 'Is Action Held', {'Action': 'turn'}), ('save_held', 'Set Boolean Variable', {'Name': 'turn_held'}),
        ('save_axis', 'Set Variable', {'Name': 'horizontal'}), ('sequence', 'Sequence', {}),
        ('turn', 'Is Action Pressed', {'Action': 'turn'}), ('turn_branch', 'Branch', {}),
        ('rotate', 'Rotate', {'Degrees': [0, 90, 0]}), ('count', 'Get Variable', {'Name': 'turn_count'}),
        ('increment', 'Add', {'B': 1}), ('save_count', 'Set Variable', {'Name': 'turn_count'}),
        ('sequence2', 'Sequence', {}), ('released', 'Is Action Released', {'Action': 'turn'}),
        ('released_branch', 'Branch', {}), ('release_count', 'Get Variable', {'Name': 'release_count'}),
        ('release_increment', 'Add', {'B': 1}), ('save_release', 'Set Variable', {'Name': 'release_count'}),
        ('reset', 'Is Action Pressed', {'Action': 'reset'}), ('reset_branch', 'Branch', {}),
        ('origin', 'Set Position', {}), ('rotation', 'Set Rotation', {'Value': [0, 0, 0]}),
    ]:
        b.add(nid, name, **values)
        index = len(b.graph['nodes']) - 1
        b.graph['nodes'][-1]['position'] = [(index % 6) * 260, (index // 6) * 240]
    for edge in [
        ('x','Value','direction','X'), ('z','Value','direction','Z'), ('direction','Value','normalize','Vector'),
        ('normalize','Value','delta','Vector'), ('dt','Value','speed','A'), ('speed','Value','delta','Scale'),
        ('delta','Value','move','Delta'), ('update','Out','move','In'), ('move','Out','save_held','In'),
        ('held','Value','save_held','Value'), ('save_held','Out','save_axis','In'), ('x','Value','save_axis','Value'),
        ('save_axis','Out','sequence','In'), ('sequence','First','turn_branch','In'),
        ('turn','Value','turn_branch','Condition'), ('turn_branch','True','rotate','In'),
        ('rotate','Out','save_count','In'), ('count','Value','increment','A'), ('increment','Value','save_count','Value'),
        ('sequence','Then','sequence2','In'), ('sequence2','First','released_branch','In'),
        ('released','Value','released_branch','Condition'), ('released_branch','True','save_release','In'),
        ('release_count','Value','release_increment','A'), ('release_increment','Value','save_release','Value'),
        ('sequence2','Then','reset_branch','In'), ('reset','Value','reset_branch','Condition'),
        ('reset_branch','True','origin','In'), ('origin','Out','rotation','In'),
    ]:
        b.connect(*edge)
    save_json(project / 'scenes/main.json', scene)
    save_json(project / 'graphs/gameplay.json', b.graph)
    save_json(project / 'project.json', {'version': 1, 'name': 'Robot input playground',
        'graph': 'graphs/gameplay.json', 'scene': 'scenes/main.json', 'assets': ['assets/robot.gltf']})
    save_json(project / 'input-replay.json', {'version': 1, 'events': [
        {'frame': 0, 'button': 'D', 'down': True}, {'frame': 5, 'button': 'Space', 'down': True},
        {'frame': 6, 'button': 'Space', 'down': False}, {'frame': 10, 'button': 'D', 'down': False},
        {'frame': 10, 'button': 'W', 'down': True}, {'frame': 20, 'release_all': True},
        {'frame': 21, 'button': 'MouseLeft', 'down': True}, {'frame': 21, 'button': 'MouseLeft', 'down': False},
    ]})
    export(compile_graph(b.graph, scene), project / 'generated')
    return project


if __name__ == '__main__':
    print(create())
