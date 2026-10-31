import pytest

from editor.core.document import default_scene
from editor.core.scene import validate_scene
from editor.core.tilemaps import new_asset


def sprite_asset():
    return {"version": 1, "type": "sprite", "id": "atlas", "name": "Atlas",
            "texture": "assets/atlas.png", "columns": 2, "rows": 2,
            "width": 1.0, "height": 1.0, "pivot": [0.5, 0.5], "filter": "nearest"}


def test_tilemap_asset_and_sorting_order_survive_scene_validation():
    scene = default_scene()
    scene["sprite_assets"] = [sprite_asset()]
    scene["tilemap_assets"] = [new_asset("atlas", "Level", 2, 2)]
    scene["tilemap_assets"][0]["tiles"] = [0, 1, -1, 3]
    scene["entities"][0].update(sorting_layer="actors", sorting_order=7)
    assert validate_scene(scene) is scene


def test_tilemap_rejects_atlas_overflow_and_bad_sorting_order():
    scene = default_scene(); scene["sprite_assets"] = [sprite_asset()]
    tilemap = new_asset("atlas", "Level", 1, 1); tilemap["tiles"] = [4]
    scene["tilemap_assets"] = [tilemap]
    with pytest.raises(ValueError, match="outside"):
        validate_scene(scene)
    scene["tilemap_assets"] = [new_asset("atlas", "Level", 1, 1)]
    scene["entities"][0]["sorting_order"] = 2_000_000
    with pytest.raises(ValueError, match="sorting_order"):
        validate_scene(scene)
