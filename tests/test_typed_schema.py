"""User value types, callback collections and variable scopes."""
from editor.core.builder import GraphBuilder
from editor.core.codegen import CppEmitter
from editor.core.data_types import declaration
from editor.core.functions import ENTRY, RETURN, new_function
from editor.core.scene import validate_scene
from editor.core.typed_schema import build_schema


def port(name, type_name):
    return {"name": name, "type": type_name}


def test_struct_enum_schema_and_scoped_variables_roundtrip():
    structs = [{"name": "Stats", "fields": [
        {"name": "hp", "type": "int", "default": 10},
        {"name": "title", "type": "string", "default": "Hero"},
    ]}]
    enums = [{"name": "Mode", "values": ["Idle", "Run"]}]
    scene = {"version": 1, "entities": [], "variables": {
        "stats": declaration("struct:Stats", {"hp": 20, "title": "Bird"}),
        "mode": declaration("enum:Mode", "Run"),
    }, "struct_definitions": structs, "enum_definitions": enums,
    "variable_scopes": {"stats": "scene", "mode": "global"}}
    assert validate_scene(scene) is scene
    schema = build_schema(structs, enums)
    assert schema.default_value("struct:Stats") == {"hp": 10, "title": "Hero"}
    assert schema.literal_valid("Idle", "enum:Mode")


def test_struct_nodes_lower_and_emit_native_types():
    structs = [{"name": "Stats", "fields": [{"name": "hp", "type": "int", "default": 1}]}]
    b = GraphBuilder(struct_definitions=structs)
    b.add("start", "On Game Start")
    b.add("make", "Make Stats", hp=7)
    b.add("break", "Break Stats")
    b.add("set", "Set Integer Variable", Name="hp")
    b.connect("start", "Out", "set", "In").connect("make", "Value", "break", "Value").connect("break", "hp", "set", "Value")
    ir = b.compile({"version": 1, "entities": [], "variables": {"hp": declaration("int", 0)},
                    "struct_definitions": structs})
    assert ir["events"]["start"][0]["args"][1]["op"] == "struct_get"
    assert "StructValue" in CppEmitter().generate(ir)


def test_map_callback_requires_typed_pure_function_and_lowers():
    callback = new_function("Identity", [port("Item", "int")], [port("Result", "int")], True)
    callback["graph"]["links"] = [{"from": ["entry", "Item"], "to": ["return", "Result"]}]
    b = GraphBuilder(functions=[callback])
    b.add("start", "On Game Start")
    b.add("map", "Map Integer Array", Array=[1, 2, 3], Callback=callback["id"])
    b.add("set", "Set Integer Array Variable", Name="items")
    b.connect("start", "Out", "set", "In").connect("map", "Value", "set", "Value")
    ir = b.compile({"version": 1, "entities": [], "variables": {"items": declaration("array<int>", [])}})
    expression = ir["events"]["start"][0]["args"][1]
    assert expression["op"] == "collection_callback" and expression["mode"] == "MapArray"
    assert f"Function_{callback['id']}" in CppEmitter().generate(ir)
