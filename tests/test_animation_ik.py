"""Native two-bone IK graph parity."""
import json
import pytest

from editor.core.builder import GraphBuilder
from editor.core.data_types import declaration
from editor.core.document import default_scene
from editor.core.feature_pipeline import solve_two_bone_ik
from tests.test_native import native


def test_two_bone_ik_matches_python_contract_in_both_native_hosts(native):
    b = GraphBuilder('Two bone IK')
    b.add('start', 'On Game Start')
    b.add('ik', 'Solve Two Bone IK', Root=[0, 0], Target=[1, 1],
          **{'Upper Length': 1.0, 'Lower Length': 1.0})
    b.add('save', 'Set Vector2 Variable', Name='elbow')
    b.connect('start', 'Out', 'save', 'In').connect('ik', 'Elbow', 'save', 'Value')
    scene = default_scene()
    scene['variables'] = {'elbow': declaration('vec2', [0, 0])}
    preview, game = native(b.graph, scene=scene, frames=1)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    assert left['variables']['elbow']['value'] == pytest.approx(solve_two_bone_ik((0, 0), (1, 1), 1, 1))
