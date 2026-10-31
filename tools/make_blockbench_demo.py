"""Create a small 3D project; geometry is authored through Blockbench MCP."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.document import save_json, default_scene
from editor.core.registry import ROOT
from export_cube_fixture import convert

root = ROOT / 'examples/blockbench_demo'
convert(root / 'assets/robot.bbmodel', root / 'assets/robot.gltf')
b = GraphBuilder('Robot — rotate and move')
for nid, name, pos, values in [
    ('start', 'On Game Start', [0,-200], {}),
    ('hello', 'Print Log', [250,-200], {'Message': 'Robot ready - hold D to move'}),
    ('update', 'On Update', [0,0], {}),
    ('rotate', 'Rotate', [500,0], {}),
    ('dt', 'Get Delta Time', [0,160], {}),
    ('spin', 'Vector Scale', [250,140], {'Vector': [0,45,0]}),
    ('branch', 'Branch', [750,0], {}),
    ('key', 'Is Key Held', [500,220], {'Key': 'D'}),
    ('move', 'Translate', [1000,0], {}),
    ('speed', 'Vector Scale', [750,220], {'Vector': [1,0,0]}),
]:
    b.add(nid, name, **values)
    b.graph['nodes'][-1]['position'] = pos
for connection in [('start','Out','hello','In'), ('update','Out','rotate','In'),
                   ('dt','Value','spin','Scale'), ('spin','Value','rotate','Degrees'),
                   ('rotate','Out','branch','In'), ('key','Value','branch','Condition'),
                   ('branch','True','move','In'), ('dt','Value','speed','Scale'),
                   ('speed','Value','move','Delta')]:
    b.connect(*connection)
b.compile()
scene = default_scene()
scene['entities'][0].update(name='Test Robot', mesh='assets/robot.gltf')
save_json(root / 'graphs/gameplay.json', b.graph)
save_json(root / 'scenes/main.json', scene)
save_json(root / 'project.json', {'version':1, 'name':'Blockbench Robot', 'graph':'graphs/gameplay.json',
                               'scene':'scenes/main.json', 'assets':['assets/robot.gltf', 'assets/robot.bbmodel']})
