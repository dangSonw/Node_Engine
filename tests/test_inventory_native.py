"""Native inventory node parity and scene snapshot persistence."""
import json

from editor.core.builder import GraphBuilder
from editor.core.data_types import declaration
from editor.core.document import default_scene
from tests.test_native import native


def test_inventory_nodes_match_in_both_native_hosts(native):
    scene = default_scene()
    scene['features'] = {'gameplay': {'inventory': {'capacity': 2}}}
    scene['variables'] = {
        'coin_count': declaration('int', 0),
        'water_count': declaration('int', 0),
    }
    b = GraphBuilder('Inventory')
    b.add('start', 'On Game Start')
    b.add('coin', 'Add Inventory Item', Entity='player', Item='coin', Count=3)
    b.add('gem', 'Add Inventory Item', Entity='player', Item='gem', Count=1)
    b.add('water_add', 'Add Inventory Item', Entity='player', Item='water', Count=1)
    b.add('split', 'Sequence')
    b.add('coin_count', 'Get Inventory Count', Entity='player', Item='coin')
    b.add('water_count', 'Get Inventory Count', Entity='player', Item='water')
    b.add('save_coin', 'Set Integer Variable', Name='coin_count')
    b.add('save_water', 'Set Integer Variable', Name='water_count')
    b.connect('start', 'Out', 'coin', 'In')
    b.connect('coin', 'Out', 'gem', 'In')
    b.connect('gem', 'Out', 'water_add', 'In')
    b.connect('water_add', 'Out', 'split', 'In')
    b.connect('split', 'First', 'save_coin', 'In')
    b.connect('split', 'Then', 'save_water', 'In')
    b.connect('coin_count', 'Value', 'save_coin', 'Value')
    b.connect('water_count', 'Value', 'save_water', 'Value')
    preview, game = native(b.graph, scene=scene, frames=1)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    assert left['variables']['coin_count']['value'] == 3
    assert left['variables']['water_count']['value'] == 0
    assert left['scene']['inventories'] == {'player': {'coin': 3, 'gem': 1}}

