from editor.core.builder import GraphBuilder
from editor.core.codegen import CppEmitter
from editor.core.compiler import compile_graph
from editor.core.document import default_scene


def test_animation_notify_event_compiles_with_constant_filter_and_feature_metadata():
    scene = default_scene()
    scene["features"] = {"3d": {"animation": {"notifies": [
        {"clip": "Wave", "time": 0.25, "name": "footstep"}
    ]}}}
    graph = GraphBuilder("Notify"); graph.add("notify", "On Animation Notify", **{"Notify Filter": "footstep"})
    ir = compile_graph(graph.graph, scene)
    assert ir["events"]["animation_notify"][0]["filter"] == "footstep"
    assert "rt::BindAnimationNotify" in CppEmitter().generate(ir)


def test_animation_state_machine_lowers_to_native_transition():
    scene = default_scene()
    scene["features"] = {"3d": {"animation": {"states": {
        "idle": {"clip": "Idle", "loop": True},
        "move": {"clip": "Walk", "loop": True, "speed": 1.25},
    }}}}
    graph = GraphBuilder("State machine")
    graph.add("start", "On Game Start")
    graph.add("state", "Set Animation State", State="move", Blend=.3)
    graph.connect("start", "Out", "state", "In")
    ir = compile_graph(graph.graph, scene)
    assert "rt::SetAnimationState" in CppEmitter().generate(ir)
