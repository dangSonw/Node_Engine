import pytest

from editor.core.document import default_scene
from editor.core.scene import set_entity_property, validate_scene
from editor.core import sprite_states


def scene_with_states():
    scene = default_scene()
    scene['sprite_assets'] = [{"version": 1, "type": "sprite", "id": "atlas", "name": "Atlas",
                               "texture": "assets/atlas.png", "columns": 2, "rows": 2,
                               "width": 1.0, "height": 1.0, "pivot": [0.5, 0.5], "filter": "nearest"}]
    asset = sprite_states.new_asset('atlas', 'Player states')
    asset.update(id='player_states', states={'idle': [0, 1], 'jump': [2, 3]}, initial='idle', fps=10.0, loop=True)
    scene['sprite_state_assets'] = [asset]
    scene['entities'][0]['sprite'] = {'asset': 'atlas', 'frame': 0, 'flip_x': False, 'flip_y': False}
    scene['entities'][0]['sprite_state'] = {'asset': 'player_states', 'state': 'idle'}
    return scene


def test_sprite_state_asset_and_binding_validation():
    scene = scene_with_states()
    assert validate_scene(scene) is scene
    changed = set_entity_property(scene, 'player', 'sprite_state', {'asset': 'player_states', 'state': 'jump'})
    assert changed['entities'][0]['sprite_state']['state'] == 'jump'
    bad = scene_with_states(); bad['sprite_state_assets'][0]['states']['bad'] = [99]
    with pytest.raises(ValueError, match='frame'):
        validate_scene(bad)


def test_sprite_state_runtime_helper_cycles_and_stops():
    from editor.core.feature_pipeline import SpriteStateMachine
    machine = SpriteStateMachine({'idle': [0, 1], 'jump': [2]}, 'idle')
    assert machine.update(1 / 12) == 1
    machine.transition('jump')
    assert machine.update(.5) == 2
