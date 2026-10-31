"""Native profiling sample nodes and snapshot metrics."""
import json

from editor.core.builder import GraphBuilder
from editor.core.data_types import declaration
from editor.core.document import default_scene
from tests.test_native import native


def test_profile_sample_nodes_match_in_both_native_hosts(native):
    scene = default_scene()
    scene['variables'] = {'elapsed': declaration('float', 0.0)}
    b = GraphBuilder('Profiling')
    b.add('start', 'On Game Start')
    b.add('begin', 'Begin Profile Sample', Name='startup')
    b.add('end', 'End Profile Sample', Name='startup')
    b.add('save', 'Set Variable', Name='elapsed')
    b.connect('start', 'Out', 'begin', 'In').connect('begin', 'Out', 'end', 'In').connect('end', 'Out', 'save', 'In').connect('end', 'Seconds', 'save', 'Value')
    preview, game = native(b.graph, scene=scene, frames=1)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    assert left['variables']['elapsed']['value'] == 0.0
    assert left['profiling']['samples']['startup'] == 0.0

