from copy import deepcopy
from pathlib import Path
import json
import pytest
from editor.core.registry import Registry
from editor.core.compiler import GraphError, compile_graph, validate
from editor.core.document import load_graph, save_json, default_scene
from editor.core.codegen import CppEmitter, export


def node(nid, type_id, **values):
    return {"id": nid, "type": type_id, "values": values}


def link(src, out, dst, inp):
    return {"from": [src, out], "to": [dst, inp]}


def sample():
    return {"version": 1, "nodes": [
        node("start", 1001), node("set", 3005, Name="score", Value=0),
        node("loop", 2003, Count=3), node("get", 3004, Name="score"),
        node("add", 4001, B=1), node("inc", 3005, Name="score"),
        node("update", 1002), node("seq", 2002), node("rotate", 9004, Degrees=[0, 1, 0]),
        node("branch", 2001), node("key", 10001, Key="D"), node("move", 9003),
        node("dt", 5001), node("scale", 4022, Vector=[3, 0, 0]),
    ], "links": [
        link("start", "Out", "set", "In"), link("set", "Out", "loop", "In"),
        link("loop", "Body", "inc", "In"), link("get", "Value", "add", "A"),
        link("add", "Value", "inc", "Value"), link("update", "Out", "seq", "In"),
        link("seq", "First", "rotate", "In"), link("seq", "Then", "branch", "In"),
        link("key", "Value", "branch", "Condition"), link("branch", "True", "move", "In"),
        link("dt", "Value", "scale", "Scale"), link("scale", "Value", "move", "Delta"),
    ]}


def test_registry_stable_unique_categories():
    r = Registry()
    assert len(r.categories) == 29
    assert r[1001].name == "On Game Start"
    assert r[9003].function == "Translate"
    assert all(n.category in r.categories for n in r.nodes.values())


def test_valid_graph_compiles_without_mutating_input():
    graph = sample()
    before = deepcopy(graph)
    ir = compile_graph(graph, default_scene())
    assert graph == before
    assert ir["events"]["start"][1]["op"] == "for"
    assert len(ir["events"]["update"]) == 2
    assert ir["events"]["update"][1]["op"] == "branch"


def test_type_mismatch_reports_destination():
    graph = sample()
    graph["links"].append(link("key", "Value", "add", "B"))
    assert any(p.node == "add" and "Type mismatch" in p.message for p in validate(graph))
    with pytest.raises(GraphError):
        compile_graph(graph)


@pytest.mark.parametrize("link_to_add,label", [
    (link("add", "Value", "add", "B"), "Data cycle"),
    (link("inc", "Out", "loop", "In"), "Execution cycle"),
])
def test_cycles_rejected(link_to_add, label):
    graph = sample()
    graph["links"].append(link_to_add)
    assert any(label in p.message for p in validate(graph))


def test_unknown_node_preserves_document_and_blocks_compile():
    graph = sample()
    graph["nodes"][0]["type"] = 999999
    before = deepcopy(graph)
    assert validate(graph)
    assert graph == before


def test_multiple_data_sources_rejected():
    graph = sample()
    graph["links"].append(link("dt", "Value", "add", "A"))
    assert any("multiple sources" in p.message for p in validate(graph))


def test_exec_fanout_requires_sequence():
    graph = sample()
    graph["links"].append(link("start", "Out", "inc", "In"))
    assert any("use Sequence" in p.message for p in validate(graph))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "3"])
def test_invalid_numeric_literals(value):
    graph = sample()
    graph["nodes"][1]["values"]["Value"] = value
    assert any(p.node == "set" for p in validate(graph))


def test_unicode_roundtrip_and_deterministic_export(tmp_path):
    graph = sample()
    graph["name"] = "Thử nghiệm chuyển động"
    path = tmp_path / "đồ thị.json"
    save_json(path, graph)
    assert load_graph(path) == graph
    ir = compile_graph(graph, default_scene())
    source = export(ir, tmp_path)
    first, timestamp = source.read_bytes(), source.stat().st_mtime_ns
    export(ir, tmp_path)
    assert source.read_bytes() == first
    assert source.stat().st_mtime_ns == timestamp
    assert b"SDL" not in first
    assert b"rt::Translate" in first


def test_future_version_rejected(tmp_path):
    path = tmp_path / "future.json"
    save_json(path, {"version": 99, "nodes": [], "links": []})
    with pytest.raises(ValueError, match="Unsupported"):
        load_graph(path)


def test_codegen_repeatable_with_same_emitter():
    ir = compile_graph(sample(), default_scene())
    emitter = CppEmitter()
    assert emitter.generate(ir) == emitter.generate(ir)


def test_bad_id_cannot_inject_cpp():
    graph = sample()
    graph["nodes"][0]["id"] = "bad\n#include <something>"
    assert any("Node ID" in p.message for p in validate(graph))


@pytest.mark.parametrize("graph", [[], {"version": 1}, {"nodes": [None], "links": []}])
def test_malformed_graph_returns_diagnostics(graph):
    assert validate(graph)


@pytest.mark.parametrize('values', [{'Entity':'alpha'}, {'In':True}])
def test_builder_rejects_mistyped_and_execution_input_values_without_changing_graph(values):
    from editor.core.builder import GraphBuilder
    builder=GraphBuilder(); builder.add('start','On Game Start')
    before=json.loads(json.dumps(builder.graph))
    with pytest.raises(ValueError,match=r'clone \(Clone Entity\): unknown data input'):
        builder.add('clone','Clone Entity',**values)
    assert builder.graph==before
    builder.add('clone','Clone Entity',Source='player')
    builder.connect('start','Out','clone','In')
    assert builder.compile()['events']['start'][0]['args'][0]['value']=='player'
