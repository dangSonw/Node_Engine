import json
from pathlib import Path

from editor.core.builder import GraphBuilder
from tests.test_native import native
from tests.test_animation_playback import scene
from tests.test_physics_scene import chain

ROOT = Path(__file__).resolve().parents[1]


def test_native_animation_blend_survives_interpreted_and_generated_paths(native):
    b = GraphBuilder('Animation blend')
    b.add('start', 'On Game Start')
    chain(b, 'start', ('wave', 'Play Animation', {'Clip': 'Wave'}),
          ('blend', 'Play Animation Blended', {'Clip': 'Walk', 'Blend': .5}))
    preview, game = native(b.graph, scene=scene(), frames=2,
                            extra=['--dt', '.1', '--project-root', str(ROOT)])
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    player = left['animation']['player']
    assert player['clip'] == 'Walk' and player['blend']['clip'] == 'Wave'
    assert player['blend']['duration'] == .5 and player['blend']['elapsed'] == .2
