# Create a connected node

Drag an input or output port into empty graph space. The search lists compatible
nodes from the current gameplay or function graph. Each row names the exact port,
its type and its category; for example, `Add · B: float · Math & Geometry`.

Type to filter by any of those words. Up/Down selects a row; Enter creates the
node at the drop location and connects the selected port. Double-click also
selects a result. Recently used node types are ranked first within that adapter
session. Esc cancels; an empty search explicitly reports that it has no matches.

Creation and connection are one Undo transaction. When starting from an occupied
input or an execution output, the existing wire stays intact until a replacement
is selected. Cancel preserves both the graph and undo history. Undo of a replacement
restores the previous wire and removes the new node; Redo restores its same stable
ID, position and connection. The new node becomes the Inspector selection.

Compatibility uses registry signatures and the current function's restrictions.
Pure functions cannot offer side effects, event handlers or recursive self calls.
Project-owned function/event/component nodes use their current signatures; arrays
and maps must match their complete type. There are no implicit type conversions.
Listener configuration inputs (timer, custom event, physics and UI filters) are
Inspector constants and cannot accept wires, either through search or direct drag.

Direct port-to-port connections keep their normal behavior. Drops onto nodes or
existing wires do not open this search. Existing library and Tab search remain
available for creating unconnected nodes.

## Integration and verification

`GraphViewer` extends the installed NodeGraphQt live-connection hook; it restores
any temporarily detached visual wire before opening the shared `SearchDialog`.
`GraphAdapter` obtains choices from `available_specs()` and records creation and
the connection in the existing shared QUndoStack. Domain graph/IR formats and
native calls are unchanged. `NodeSpec.constant_inputs` is shared by compiler
validation and editor connection rules.

Run these after changing graph gestures or upgrading NodeGraphQt:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_port_search.py tests/test_editor.py -q
.venv/Scripts/python.exe -X utf8 tools/verify_port_search.py
```

The desktop verifier uses actual Windows mouse/keyboard input, including DPI
coordinate conversion. It checks typed search, explicit port selection, physical
Undo/Escape, Inspector rejection/correction, save/reopen and native interpreted
headless/embedded execution of the authored graph. It writes reports/screenshots
under `artifacts/validation/port-search-*` and an isolated project under `.cache/`.
Linux gestures, screen-reader behavior and IME composition require separate checks.
