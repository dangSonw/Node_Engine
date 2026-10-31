"""Native automatic checkpoint scheduling."""
import json

from editor.core.builder import GraphBuilder
from editor.core.document import default_scene
from tests.test_native import native


def test_authored_autosave_writes_a_real_checkpoint_in_both_hosts(native, tmp_path):
    scene = default_scene()
    scene['features'] = {'gameplay': {'autosave': {'interval': 0.01}}}
    b = GraphBuilder('Autosave')
    b.add('start', 'On Game Start')
    preview, game = native(b.graph, scene=scene, frames=2,
                           extra=['--save-root', str(tmp_path)])
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    assert left['persistence']['game_id'] == 'autosave'
    assert left['persistence']['success'] is True
    assert left['scene']['autosave']['interval'] == 0.01

