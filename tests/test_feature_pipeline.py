from editor.core.feature_pipeline import (
    AIController, Autosave, CinematicCamera, Combatant, EditorDebugState,
    Inventory, NavigationGrid, PBRMaterial, Profiler, ShaderGraph,
    SpriteStateMachine, TileMap, WorldStreamer, solve_two_bone_ik,
)
import pytest


def test_2d_pipeline_tilemap_sprite_and_runtime_order():
    tilemap = TileMap(4, 4, {"ground": [0] * 16})
    tilemap.set("ground", 1, 2, 4)
    assert tilemap.get("ground", 1, 2) == 4
    assert (1, 1) in tilemap.neighbors(1, 2)
    sprite = SpriteStateMachine({"idle": [0, 1], "jump": [2]}, "idle")
    sprite.transition("jump")
    assert sprite.update(0.2) == 2


def test_3d_pipeline_material_shader_animation_ik_and_cinematic():
    assert PBRMaterial(metallic=.2, roughness=.7).validate()
    ShaderGraph([{"id": "uv"}, {"id": "out"}], [["uv", "out"]]).validate()
    assert solve_two_bone_ik((0, 0), (1, 1), 1, 1)[0] >= 0
    camera = CinematicCamera([{"time": 0, "value": [0, 0]}, {"time": 1, "value": [10, 0]}])
    assert camera.evaluate(.5) == (5.0, 0.0)


def test_game_systems_navigation_inventory_combat_autosave_and_replication():
    assert NavigationGrid(4, 4, {(1, 0)}).path((0, 0), (2, 0))
    ai = AIController(); ai.set_state("chase"); assert ai.state == "chase"
    stream = WorldStreamer(1); assert stream.update((0, 0), [(0, 0), (2, 0)]) == [(0, 0)]
    inventory = Inventory(1); assert inventory.add("seed") and not inventory.add("water")
    fighter = Combatant(10, 3); fighter.damage(5); assert fighter.health == 8 and fighter.shield == 0
    save = Autosave(1); assert not save.update(.5) and save.update(.5)


def test_editor_debugger_profiler_and_safe_graph_delete():
    debug = EditorDebugState(); debug.watch("score", 3); debug.set_accessibility_label("node", "Score")
    graph = {"nodes": [{"id": "a"}, {"id": "b"}], "links": [{"from": ["a", "Out"], "to": ["b", "In"]}]}
    assert debug.delete_nodes(graph, ["a"])["links"] == []
    profiler = Profiler(); profiler.begin("frame", 1.0); assert profiler.end("frame", 1.25) == .25


def test_feature_document_rejects_invalid_runtime_contracts_and_refactors_debug_state():
    from editor.core.feature_pipeline import validate_feature_document
    document = {"features": {"2d": {"tilemap": {"width": 2, "height": 1,
        "layers": {"ground": [0, -1]}, "runtime_textures": ["assets/a.png"]}},
        "3d": {"pbr": {"metallic": .2, "roughness": .6},
               "lights": [{"kind": "directional", "intensity": 2}]},
        "gameplay": {"navigation": {"grid": [4, 4], "blocked": [[1, 1]]},
                     "replication": {"authority": "server"}},
        "editor": {"ime": True}}}
    assert validate_feature_document(document) is document
    with pytest.raises(ValueError):
        validate_feature_document({"features": {"2d": {"runtime_textures": ["../outside.png"]}}})
    with pytest.raises(ValueError):
        validate_feature_document({"features": {"3d": {"shader_graph": {
            "nodes": [{"id": "a"}, {"id": "b"}], "edges": [["a", "b"], ["b", "a"]]}}}})
    debug = EditorDebugState(); debug.breakpoint("a"); debug.watch("a", 1)
    changed = debug.rename_node({"nodes": [{"id": "a"}, {"id": "b"}],
                                 "links": [{"from": ["a", "Out"], "to": ["b", "In"]}]}, "a", "renamed")
    assert changed["links"][0]["from"][0] == "renamed" and "renamed" in debug.breakpoints
