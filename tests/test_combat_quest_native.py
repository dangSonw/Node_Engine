"""Native combat and quest progression parity."""
import json

from editor.core.builder import GraphBuilder
from editor.core.data_types import declaration
from editor.core.document import default_scene
from tests.test_native import native


def test_combat_and_quest_nodes_match_in_both_native_hosts(native):
    scene = default_scene()
    scene['entities'].append({'id': 'enemy', 'name': 'Enemy', 'position': [1., 0., 0.],
                              'rotation': [0., 0., 0.], 'scale': [1., 1., 1.]})
    scene['features'] = {'gameplay': {
        'combat': {'entities': {'enemy': {'health': 20.0, 'shield': 5.0}}},
        'quests': {'tutorial': {'objectives': {'coins': 2}}},
    }}
    scene['variables'] = {
        'health': declaration('float', 0.0),
        'alive': declaration('bool', False),
        'quest_active': declaration('bool', False),
        'quest_complete': declaration('bool', False),
    }
    b = GraphBuilder('Combat quest')
    b.add('start', 'On Game Start')
    b.add('damage', 'Apply Damage', Target='enemy', Amount=10.0)
    b.add('split', 'Sequence')
    b.add('health', 'Get Health', Target='enemy')
    b.add('save_health', 'Set Float Variable', Name='health')
    b.add('save_alive', 'Set Boolean Variable', Name='alive')
    b.add('start_quest', 'Start Quest', Quest='tutorial')
    b.add('advance', 'Advance Quest', Quest='tutorial', Objective='coins', Amount=2)
    b.add('split_quest', 'Sequence')
    b.add('active', 'Is Quest Active', Quest='tutorial')
    b.add('complete', 'Is Quest Complete', Quest='tutorial')
    b.add('save_active', 'Set Boolean Variable', Name='quest_active')
    b.add('save_complete', 'Set Boolean Variable', Name='quest_complete')
    for a, o, d, i in [
        ('start', 'Out', 'damage', 'In'), ('damage', 'Out', 'split', 'In'),
        ('split', 'First', 'save_health', 'In'), ('health', 'Value', 'save_health', 'Value'),
        ('save_health', 'Out', 'save_alive', 'In'), ('damage', 'Alive', 'save_alive', 'Value'),
        ('split', 'Then', 'start_quest', 'In'), ('start_quest', 'Out', 'advance', 'In'),
        ('advance', 'Out', 'split_quest', 'In'), ('split_quest', 'First', 'save_active', 'In'),
        ('split_quest', 'Then', 'save_complete', 'In'), ('active', 'Value', 'save_active', 'Value'),
        ('complete', 'Value', 'save_complete', 'Value'),
    ]:
        b.connect(a, o, d, i)
    preview, game = native(b.graph, scene=scene, frames=1)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    assert left['variables']['health']['value'] == 15.0
    assert left['variables']['alive']['value'] is True
    assert left['variables']['quest_active']['value'] is True
    assert left['variables']['quest_complete']['value'] is True
    assert left['scene']['health']['enemy'] == 15.0
    assert left['scene']['quests']['tutorial']['complete'] is True

