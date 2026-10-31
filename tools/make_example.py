"""Regenerate the demonstration using the public Python graph authoring API."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.document import save_json, default_scene
from editor.core.registry import ROOT

b = GraphBuilder("Core Demo")
for nid, kind, values in [
    ("start", "On Game Start", {}), ("set", "Set Variable", {"Name": "score", "Value": 0}),
    ("loop", "For Loop", {"Count": 3}), ("get", "Get Variable", {"Name": "score"}),
    ("add", "Add", {"B": 1}), ("inc", "Set Variable", {"Name": "score"}),
    ("update", "On Update", {}), ("seq", "Sequence", {}),
    ("rotate", "Rotate", {"Degrees": [0, 1, 0]}), ("branch", "Branch", {}),
    ("key", "Is Key Held", {"Key": "D"}), ("move", "Translate", {}),
    ("dt", "Get Delta Time", {}), ("scale", "Vector Scale", {"Vector": [3, 0, 0]}),
]:
    b.add(nid, kind, **values)
for connection in [
    ("start", "Out", "set", "In"), ("set", "Out", "loop", "In"),
    ("loop", "Body", "inc", "In"), ("get", "Value", "add", "A"),
    ("add", "Value", "inc", "Value"), ("update", "Out", "seq", "In"),
    ("seq", "First", "rotate", "In"), ("seq", "Then", "branch", "In"),
    ("key", "Value", "branch", "Condition"), ("branch", "True", "move", "In"),
    ("dt", "Value", "scale", "Scale"), ("scale", "Value", "move", "Delta"),
]:
    b.connect(*connection)
b.compile()
directory = ROOT / "examples/core_demo"
save_json(directory / "graphs/gameplay.json", b.graph)
save_json(directory / "scenes/main.json", default_scene())
save_json(directory / "project.json", {
    "version": 1, "name": "Core Demo", "graph": "graphs/gameplay.json", "scene": "scenes/main.json", "assets": []
})