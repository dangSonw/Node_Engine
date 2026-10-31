"""Native AI state machine parity and scene snapshot persistence."""
import json

from editor.core.builder import GraphBuilder
from editor.core.data_types import declaration
from editor.core.document import default_scene
from tests.test_native import native


def test_ai_state_nodes_match_in_both_native_hosts(native):
    scene = default_scene()
    scene['features'] = {'gameplay': {'ai': {'state': 'idle'}}}
    scene['variables'] = {
        'state': declaration('string', ''),
        'chase': declaration('bool', False),
    }
    b = GraphBuilder('AI state')
    b.add('start', 'On Game Start')
    b.add('set', 'Set AI State', Entity='player', State='chase')
    b.add('split', 'Sequence')
    b.add('get', 'Get AI State', Entity='player')
    b.add('is', 'Is AI State', Entity='player', State='chase')
    b.add('save_state', 'Set String Variable', Name='state')
    b.add('save_is', 'Set Boolean Variable', Name='chase')
    b.connect('start', 'Out', 'set', 'In')
    b.connect('set', 'Out', 'split', 'In')
    b.connect('split', 'First', 'save_state', 'In')
    b.connect('split', 'Then', 'save_is', 'In')
    b.connect('get', 'Value', 'save_state', 'Value')
    b.connect('is', 'Value', 'save_is', 'Value')
    preview, game = native(b.graph, scene=scene, frames=1)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    assert left['variables']['state']['value'] == 'chase'
    assert left['variables']['chase']['value'] is True
    assert left['scene']['ai_states'] == {'player': 'chase'}

