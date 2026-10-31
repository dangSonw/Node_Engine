"""Native navigation grid parity."""
import json
import pytest

from editor.core.builder import GraphBuilder
from editor.core.data_types import declaration
from editor.core.document import default_scene
from editor.core.feature_pipeline import NavigationGrid
from tests.test_native import native


def test_navigation_path_matches_python_and_both_native_hosts(native):
    scene = default_scene()
    scene['features'] = {'gameplay': {'navigation': {
        'grid': [4, 3], 'blocked': [[1, 0], [1, 1]],
    }}}
    scene['variables'] = {'path': declaration('array<vec2>', [])}
    b = GraphBuilder('Navigation path')
    b.add('start', 'On Game Start')
    b.add('path', 'Find Navigation Path', Start=[0, 0], Goal=[3, 0])
    b.add('save', 'Set Vector2 Array Variable', Name='path')
    b.connect('start', 'Out', 'save', 'In').connect('path', 'Path', 'save', 'Value')
    preview, game = native(b.graph, scene=scene, frames=1)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    expected = NavigationGrid(4, 3, {(1, 0), (1, 1)}).path((0, 0), (3, 0))
    assert left['variables']['path']['value'] == pytest.approx([[float(x), float(y)] for x, y in expected])
