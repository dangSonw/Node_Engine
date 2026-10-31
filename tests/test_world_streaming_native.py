"""Native authored world streaming selection parity."""
import json

from editor.core.builder import GraphBuilder
from editor.core.data_types import declaration
from editor.core.document import default_scene
from editor.core.feature_pipeline import WorldStreamer
from tests.test_native import native


def test_world_streaming_node_matches_python_and_both_native_hosts(native):
    scene = default_scene()
    scene['features'] = {'gameplay': {'world_streaming': {
        'radius': 1, 'chunks': [[0, 0], [2, 0], [1, 1], [-1, -1]],
    }}}
    scene['variables'] = {'loaded': declaration('array<vec2>', [])}
    b = GraphBuilder('World streaming')
    b.add('start', 'On Game Start')
    b.add('stream', 'Update World Streaming', Center=[0, 0])
    b.add('save', 'Set Vector2 Array Variable', Name='loaded')
    b.connect('start', 'Out', 'stream', 'In').connect('stream', 'Loaded', 'save', 'Value').connect('stream', 'Out', 'save', 'In')
    preview, game = native(b.graph, scene=scene, frames=1)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    expected = WorldStreamer(1).update((0, 0), [(0, 0), (2, 0), (1, 1), (-1, -1)])
    assert left['variables']['loaded']['value'] == [[float(x), float(y)] for x, y in expected]
    assert left['scene']['streamed_chunks'] == [[float(x), float(y)] for x, y in expected]

