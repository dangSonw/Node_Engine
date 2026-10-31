"""Reproducible four-frame sprite atlas and a keyboard-driven animation example."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtGui import QColor, QImage
from editor.core.builder import GraphBuilder
from editor.core.camera import default_camera
from editor.core.codegen import export
from editor.core.compiler import compile_graph
from editor.core.document import save_json
from editor.core.registry import ROOT
from editor.core.sprites import new_asset, binding


def create(directory=ROOT / 'examples/sprite_demo'):
    directory = Path(directory); (directory / 'assets').mkdir(parents=True, exist_ok=True)
    image = QImage(64, 64, QImage.Format_RGBA8888)
    colors = [[(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (0, 0, 0, 0)],
              [(255, 255, 0, 255), (255, 0, 255, 255), (0, 255, 255, 255), (255, 255, 255, 255)],
              [(255, 128, 0, 255)] * 4, [(128, 0, 255, 255)] * 4]
    for y in range(64):
        for x in range(64):
            frame = (y // 32) * 2 + x // 32
            quadrant = ((y % 32) // 16) * 2 + (x % 32) // 16
            image.setPixelColor(x, y, QColor(*colors[frame][quadrant]))
    assert image.save(str(directory / 'assets/atlas.png'))
    asset = dict(new_asset('assets/atlas.png', 'Four-frame atlas'), id='atlas', columns=2, rows=2, width=2., height=2.)
    entities = [dict(id=eid, name=eid.title(), position=[x, y, 0], rotation=[0, 0, 0], scale=[1, 1, 1],
        sprite=dict(binding('atlas'), frame=frame)) for eid, x, y, frame in
        [('player', -1.5, 1.5, 0), ('second', 1.5, 1.5, 1), ('third', -1.5, -1.5, 2), ('fourth', 1.5, -1.5, 3)]]
    entities.append(dict(id='camera', name='Sprite Camera', position=[0, 0, 8], rotation=[0, 0, 0], scale=[1, 1, 1],
        camera=dict(default_camera(), projection='orthographic', size=8)))
    scene = dict(version=1, entities=entities, variables={}, sprite_assets=[asset], active_camera='camera',
        input=dict(version=1, actions={'next': ['Space'], 'flip_x': ['X'], 'flip_y': ['Y']}, axes={}))
    b = GraphBuilder('Sprite atlas: Space next frame, X/Y toggle flip')
    for action in ('next', 'flip_x', 'flip_y'):
        b.add(action, 'On Update'); b.add(action+'_pressed', 'Is Action Pressed', Action=action)
        b.add(action+'_branch', 'Branch'); b.connect(action, 'Out', action+'_branch', 'In')
        b.connect(action+'_pressed', 'Value', action+'_branch', 'Condition')
    b.add('frame', 'Get Sprite Frame'); b.add('increment', 'Integer Add', B=1)
    b.add('within', 'Integer Less', B=4); b.add('wrap', 'Branch'); b.add('set_frame', 'Set Sprite Frame'); b.add('reset_frame', 'Set Sprite Frame', Frame=0)
    b.connect('frame', 'Value', 'increment', 'A'); b.connect('increment', 'Value', 'within', 'A')
    b.connect('within', 'Value', 'wrap', 'Condition'); b.connect('next_branch', 'True', 'wrap', 'In')
    b.connect('increment', 'Value', 'set_frame', 'Frame'); b.connect('wrap', 'True', 'set_frame', 'In'); b.connect('wrap', 'False', 'reset_frame', 'In')
    for axis, other in [('X', 'Y'), ('Y', 'X')]:
        key = 'flip_'+axis.lower()
        b.add(key+'_get', 'Get Sprite Flip '+axis); b.add(key+'_not', 'NOT'); b.add(key+'_other', 'Get Sprite Flip '+other)
        b.add(key+'_set', 'Set Sprite Flip'); b.connect(key+'_get', 'Value', key+'_not', 'Value')
        b.connect(key+'_not', 'Value', key+'_set', 'Flip '+axis); b.connect(key+'_other', 'Value', key+'_set', 'Flip '+other)
        b.connect(key+'_branch', 'True', key+'_set', 'In')
    for i, node in enumerate(b.graph['nodes']): node['position'] = [(i % 5)*260, (i // 5)*220]
    save_json(directory / 'project.json', dict(version=1, name='Sprite atlas', graph='graphs/gameplay.json', scene='scenes/main.json', assets=['assets/atlas.png']))
    save_json(directory / 'scenes/main.json', scene); save_json(directory / 'graphs/gameplay.json', b.graph)
    save_json(directory / 'input-replay.json', {'version': 1, 'events': [
        {'frame': frame + released, 'button': key, 'down': not released}
        for frame, key in [(2, 'Space'), (4, 'X'), (6, 'Y'), (8, 'Space')]
        for released in (0, 1)]})
    export(compile_graph(b.graph, scene), directory / 'generated')
    return directory


if __name__ == '__main__': print(create())
