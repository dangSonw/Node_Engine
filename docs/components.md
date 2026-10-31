# Typed entity components

Components provide reusable entity data such as Health, Inventory, movement
settings or quest state. Their definitions belong to the scene; all gameplay
and action-function graphs in that scene share the same schemas. The native
Flecs world stores each instance as a `(ComponentData, schema)` pair. The
interpreter and generated C++ call the same native component operations.

## Authoring

1. Choose **Scene > Define Component…**. Enter a unique display name and property
   names, types and defaults. Property names use ASCII letters, digits and `_`,
   and must begin with a letter or `_`.
2. Select an entity and choose **Scene > Add Component…**, or use the Inspector
   button. The instance starts with the declared defaults.
3. Edit property values as JSON in the Inspector. Strings use quotes, arrays use
   brackets and maps use objects. Invalid values leave the document unchanged
   and show an error on the field.
4. Use Enabled or Remove on the component. Definition creation, attach/remove,
   values and Enabled changes share the graph's Undo/Redo history. Save/reopen
   preserves them, and project switching clears the old project's definitions.

The Inspector edits the authored initial scene. It does not display live runtime
property changes. Editing component data while preview is active resets the
preview from the edited scene. Stop restores initial data; a fresh Play starts
a new run. Runtime snapshots expose the actual current component values.

Property signatures are fixed after creation in this version. Schema editing,
deletion/migration with dependent graphs, reusable schema assets and prefab
overrides remain future work. Undo can remove a newly created definition.

## Nodes and semantics

Each definition contributes six general nodes and two nodes per property.
For a Health component with an integer Points property:

| Node | Result |
| --- | --- |
| Add Health Component | Attach defaults if absent; repeated Add preserves existing values and Enabled state. |
| Remove Health Component | Detach the component. Removing an absent component from a live entity is a no-op. |
| Has Health Component | Test attachment, including disabled instances. Missing entities return false. |
| Set Health Enabled | Change the instance's logical Enabled flag without discarding values. |
| Is Health Enabled | True only when the entity has an enabled Health instance. |
| Find Entities With Health | Query actual Flecs pairs, returning stable entity references sorted by ID. EnabledOnly defaults to true. |
| Get Health Points | Read an integer value, including while disabled. |
| Set Health Points | Write a checked integer value, including while disabled. |

Enabled controls filtering by the component query. It does not suspend entity
events, timers, transforms or rendering. The sample explicitly changes entity
visibility when Health reaches zero. Whole-entity active/layer behavior is a
separate planned system.

Get/Set/Enable require an attached component on a live entity; failures identify
the originating graph node. Use Has before optional access. Data queries read
scene state and therefore belong in gameplay or action functions, not pure
functions. Flecs event handlers can attach, read, write and remove components
in the same callback.

Clone Entity copies each component's enabled state and all values. Collections
are independent value copies. Entity references inside them retain their IDs;
they do not clone or own the referenced entities. Destroy Entity removes all
attached data with the entity.

## Types and stable identities

Supported types are float, signed 64-bit int, bool, UTF-8 string, vec3 and entity,
plus homogeneous arrays, string-keyed maps and insertion-ordered unique sets of
those ten types: 40 types total.
Integers retain exact 64-bit values; strings preserve Unicode and embedded NUL.
Nested collections and arbitrary structs are not supported yet.

A scene accepts up to 256 definitions, with IDs 1–3999 and up to 32 properties
each. Property IDs are 1–32. Both component and property IDs persist in JSON.
Display-name changes do not change node identities, although authoring schema
changes through the UI and migrating property types are not implemented.

Dynamic node IDs use `600000 + component_id * 100 + slot`. Slots 0–5 are the six
general operations; Get/Set slots are `10 + property_id * 2` and the following
slot. This range is disjoint from builtin, custom-event and function IDs. Scene
definitions are authoritative when compiling; an old registry cannot inject a
component from another project.

Python authoring uses the same documents:

```python
from editor.core.builder import GraphBuilder
from editor.core.components import new_component, edit_instance
from editor.core.document import default_scene

health = new_component('Health', [{'name': 'Points', 'type': 'int', 'default': 100}])
scene = default_scene()
scene['component_definitions'] = [health]
scene = edit_instance(scene, 'player', health['id'], 'add')
graph = GraphBuilder(component_definitions=[health])
graph.add('start', 'On Game Start')
graph.add('damage', 'Set Health Points', Value=75)
graph.connect('start', 'Out', 'damage', 'In')
ir = graph.compile(scene)
```

Scene snapshots include definitions and attached values. Reloading that scene
preserves component data and enabled flags. This is scene serialization, not a
complete suspended-game save: execution stacks and pending timers/events are not
restored by this mechanism.

On prefab instances, successful component writes also preserve explicit ownership
of the affected property or Enabled flag, including equal-value writes. Add/remove
records component presence; adding an existing component remains a no-op. These
masks survive native snapshots and editor save/load. Template propagation respects
them, and prefab Reset releases them. See [prefab overrides](prefabs.md).

## Verified example

Component Enabled and entity Active are independent flags. Component queries
filter Enabled only; Is Entity Active can additionally filter by ancestor activity.
See [activity](activity.md) for runtime suspension rules.

Open `examples/components_demo/project.json` and press Play. Every 0.25 seconds,
a timer queries enabled Health components and invokes the Damage action
function. The left robot starts at 100 Points, loses 25 per pulse, then disables
Health and hides at one second. The right robot receives exactly one token in
its Inventory.Items array and keeps rotating. Later queries skip the disabled
Health instance.

The verification script `tools/verify_components_workflow.py` passed 31 real
Qt/SDL checks, including definition creation, attachment, Inspector editing,
Undo/Redo, save/reopen, runtime behavior, Stop/reset and embedded desktop pixels.
Preview and exported C++ produce equal states and byte-identical GPU bitmaps at
30 and 120 frames. Evidence: `artifacts/validation/components-workflow-checks.json`,
`components-workflow.log`, `components-workflow.exit.txt` and
`components-desktop.png`. See validation-report.md for full-suite results.
