"""Native authored cinematic camera interpolation parity."""
import json
import pytest

from editor.core.builder import GraphBuilder
from editor.core.data_types import declaration
from editor.core.document import default_scene
from editor.core.feature_pipeline import CinematicCamera
from tests.test_native import native


def test_cinematic_camera_interpolation_matches_python_and_both_hosts(native):
    scene = default_scene()
    scene['features'] = {'3d': {'cinematic_camera': [
        {'time': 0.0, 'value': [0.0, 1.0, 2.0]},
        {'time': 2.0, 'value': [4.0, 5.0, 6.0]},
    ]}}
    b = GraphBuilder('Cinematic camera')
    b.add('start', 'On Game Start')
    b.add('time', 'Float', Value=1.0)
    b.add('sample', 'Evaluate Cinematic Camera')
    b.add('save', 'Set Vector3 Variable', Name='camera_position')
    b.connect('start', 'Out', 'save', 'In').connect('time', 'Value', 'sample', 'Time').connect('sample', 'Value', 'save', 'Value')
    scene['variables'] = {'camera_position': declaration('vec3', [0, 0, 0])}
    preview, game = native(b.graph, scene=scene, frames=1)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    assert left['variables']['camera_position']['value'] == pytest.approx(
        list(CinematicCamera(scene['features']['3d']['cinematic_camera']).evaluate(1.0)))
