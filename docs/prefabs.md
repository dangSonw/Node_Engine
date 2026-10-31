# Prefab assets and native instances

`editor/core/prefabs.py` implements version-1 reusable asset documents. A prefab
retains its stable asset ID, local entity IDs, base dependency, nested dependencies
and explicit overrides. Resolution creates a derived view; it never overwrites
the original asset with flattened entities.

The shared C++ runtime now creates real Flecs Prefab/IsA instances, and the editor
can capture a subtree and instantiate assets with Undo/Redo and save/reopen.
Seven builtin nodes cover instantiation, instance lookup and gameplay Apply/Reset. Editor Apply/Reset
propagates authored changes through the dependency library and reconciles scene
instances. Gameplay Apply/Reset works in the running simulation; remaining override boundaries are
tracked in [acceptance-audit.md](acceptance-audit.md).

## File and reference rules

- Every `.prefab.json` has `version: 1`, `type: "prefab"`, stable `id` and display
  `name`. Asset/local IDs use 1–48 letters, digits, underscores or hyphens. Renaming
  a display name does not change either identity.
- A base asset declares `root` and `entities`. A variant declares `base`; its
  inherited root ID cannot change. Added `entities` have new local IDs. Inherited
  entity values are changed through `overrides`, avoiding ambiguous replacements.
- All resolved entities form one rooted hierarchy. Parent IDs and entity-valued
  component properties refer to local IDs. The existing scene limits apply,
  including 65,536 entities, 256 hierarchy levels and finite transforms.
- `component_definitions` packages the schemas used by a captured subtree. Shared
  component IDs must have identical definitions across a library/project; schema
  migration is a separate feature. Missing property values are filled from their
  typed defaults before reference remapping.
- Mesh paths remain relative to the project root. Capturing an asset does not copy
  mesh files or create a distributable bundle. General dependency packaging remains
  pending. Library loading constrains all prefab file paths to the project root,
  including resolved symlinks/junctions.
- A library supports at most 1,024 assets and 32 dependency levels. Missing
  dependencies, cycles, duplicate IDs/paths, unknown fields, invalid typed values,
  disconnected roots and dangling local references fail before use. Duplicate JSON
  keys and non-finite JSON constants are rejected when loading files.

Entity fields of type `entity`, `array<entity>` and `map<entity>` are remapped.
Ordinary string fields and map keys are preserved even when their text matches an
entity ID. Capturing a subtree rejects references outside it. The explicit
`--clear-external-references` option replaces those references with empty entity
references. There is no implicit link from a portable prefab to a particular scene.

## Overrides and nesting

An `overrides` entry is keyed by local entity ID. Ordinary entity properties are
replaced as a whole; component patches merge `enabled` and individual property
IDs. A component value of `null` removes that component; adding a component starts
with its schema defaults. An absent patch follows the base's current value.

```json
{
  "version": 1,
  "type": "prefab",
  "id": "inactive_robot",
  "name": "Inactive Robot",
  "base": "robot",
  "overrides": {"root": {"active": false, "layer": 5}}
}
```

`removed` lists local entity IDs and removes their descendants. It cannot remove
the root. References from surviving entities to removed entities must be repaired
explicitly in the same asset's overrides; they are never silently retargeted.

A nested binding has `id`, `prefab`, `parent` and optional `overrides`. Binding
overrides use the nested asset's own local IDs. Its root becomes the binding ID;
other local IDs become `binding/local`. Entity references are remapped into that
namespace. The outer asset can patch a resolved nested entity using this path,
including references between nested branches. Namespaces cannot collide.

Base changes are visible when an asset library is reloaded/resolved. More-derived patches
win. Removing a property patch resumes inheritance of that property. These are
asset-resolution rules. Authoring reconciliation updates scene instances; gameplay
Apply resolves the same dependency graph and propagates it inside the running Flecs world.

An instance candidate has a complete `local ID -> scene ID` mapping. Reusing that
mapping preserves identity across save/load; two fresh mappings never intentionally
share scene IDs. Supplied mappings must cover exactly the current local IDs and
contain unique, valid scene IDs. The reconciliation layer updates mappings after
template edits and retains removed IDs separately. The editor merges candidates
into a scene with an instance record; native scene loading then restores actual
Flecs inheritance.

## Run the authoring tools

From the repository root in PowerShell:

```powershell
.venv\Scripts\python.exe -m tools.prefab_asset capture --project examples/activity_demo/project.json --root group --name "Robot Group" --id robot_group --output assets/prefabs/robot_group.prefab.json

.venv\Scripts\python.exe -m tools.prefab_asset inspect --project examples/activity_demo/project.json --prefab robot_group assets/prefabs/robot_group.prefab.json

.venv\Scripts\python.exe -m tools.create_prefab_assets_demo

.venv\Scripts\python.exe -m tools.prefab_asset inspect --project examples/activity_demo/project.json --prefab robot_pair assets/prefabs/robot.prefab.json assets/prefabs/inactive_robot.prefab.json assets/prefabs/robot_pair.prefab.json
```

Capture refuses an existing output unless `--replace` is explicit. It validates the
saved asset against the project's component schemas. These tools do not modify the
project manifest, scene or gameplay graph. Register the files through the editor
as described below; opening a project alone does not register arbitrary files.

The reproducible fixtures use the existing Blockbench robot mesh: a base robot,
an inactive variant and a pair containing two nested instances. Resolution and two
distinct candidate mappings are saved under `artifacts/validation/prefab-*.json`.
The native demo below uses the same assets and meshes.

## Editor and native workflow

- Select an entity, then **Scene → Create Prefab from Entity…** to capture its
  subtree into the scene's prefab library. Capture rejects external entity
  references; the CLI provides the explicit clearing option.
- **Scene → Instantiate Prefab…** places an asset at the scene root. The Inspector
  shows its asset/local ID and edits the instance. Capture, instantiate, delete,
  property edits and membership metadata use the shared Undo/Redo stack.
- These editor assets are saved inside the scene's `prefab_assets` array. File
  registration and cross-project import are available in the File menu. There
  is no automatic file watcher or dedicated per-asset editor yet. In the demo, the
  embedded sources are authoritative; changing the copied fixture files alone
  does not update the embedded library.
- Compile/export produces dependency-ordered `prefab_templates` from the authored
  sources. Stale derived descriptors are rebuilt, never trusted as authoritative.
  `prefab_instances` retains mappings, deleted-child tombstones and builtin
  component ownership through save/load. Tombstone IDs cannot be shared or reused.

| Node | Behavior |
|---|---|
| Instantiate Prefab | Creates the complete hierarchy, remaps typed references and returns its root; Position overrides the root's local position and Parent defaults to scene root |
| Is Prefab Instance | True for any live member, false for ordinary or missing entities |
| Get Prefab Asset | Returns the owning asset's stable ID, or an empty string |
| Get Prefab Root | Returns the owning instance root, or an empty entity reference |
| Get Prefab Entity | Looks up a local ID using any member of the instance; absent/deleted members return an empty reference |
| Reset Prefab Instance | Restores the owning instance inside the current simulation; KeepPlacement retains the root transform by default |
| Apply Prefab Overrides | Applies the owning instance to its asset and propagates changes to dependent instances in the live simulation; KeepPlacement excludes root placement by default |

The templates are actual `world.prefab()` entities. Variant/nested template nodes
and live instance members have real IsA relationships. Normal scene counts,
rendering and component queries exclude templates. Transform, Mesh/Visibility,
Tags and Active/Layer follow Flecs inheritance until written; a write owns a copy
of that whole component. Even a same-value write remains owned after save/load.
These are component-granularity overrides; a same-value builtin write still owns
that component. Authoring Apply/Reset is described below.
Identity and instance metadata never inherit. Mutable user component pairs use
Flecs' default Override copy policy, and their entity-valued properties are
remapped into each instance. Their values, removals and Enabled flags remain
independent and survive snapshots. Editor template propagation merges user data
at property granularity, retaining explicit writes even when their values match
the previous template. See component overrides below.

ChildOf describes the editable live hierarchy. Separate instance membership
allows a root to destroy all its members, including a child reparented elsewhere,
and any descendants of those members. Deleting a child leaves its reserved mapping
as a tombstone. Clone Entity continues to create an ordinary standalone entity;
use Instantiate Prefab to retain template membership.

Snapshots include `prefab_state`, reporting actual Flecs Prefab tags, IsA targets
and `owns<T>()` results. This evidence does not infer inheritance from equal values.
The renderer preloads meshes from the entire library, including templates with no
initial live entities, then frames the first spawned geometry.

```powershell
.venv\Scripts\python.exe -m tools.create_prefabs_demo
tools\build.ps1 -Project examples/prefabs_demo/project.json
.venv\Scripts\python.exe -m editor.main examples/prefabs_demo/project.json
.venv\Scripts\python.exe tools/verify_prefabs_workflow.py
```

The demo starts with zero scene entities. Its graph instantiates a Robot Pair,
enables the initially inactive right robot, and rotates the two in opposite
directions. The 108-triangle Blockbench mesh is shared by both.

## Registering and importing libraries

Use **File → Register Prefab Files…** to select one or more project-local
`.prefab.json` files. Select each base/nested dependency too, unless it is already
registered in this scene. Their models and dependencies must live under the
project's `assets/` directory so Build Game can package them. Validation rejects
missing dependencies, duplicate IDs, conflicting component schemas and paths
outside the project before changing the scene.

Use **File → Import Prefab Library…** to select another saved `project.json`.
This imports its scene's complete registered prefab library and component schemas.
The destination keeps its graph, entities, variables and instance records. The
source project's unregistered files are not discovered automatically; register
and save them in that project first.

Model resources are copied once per source path into a new
`assets/prefab-library-<id>/` directory. External glTF/GLB buffer/image dependencies
retain their relative layout. As with Import Model, dependency URIs must stay
inside the model's directory tree. Only builtin mesh fields in authored entities,
variant patches and nested binding patches are rewritten; typed entity references,
component strings and map keys keep their meaning. Existing IDs and schemas must
be compatible: conflicting prefab IDs or component definitions reject the whole
import, with the error shown in Console. There is no implicit replacement or ID
renumbering. Model geometry support is still checked by the native renderer.

Both operations are one shared Undo/Redo transaction and refresh a live preview.
Undo removes the library registration and its added schemas. Copied files remain
available for Redo, just as with Import Model. Save persists the library snapshot
inside the destination scene; later file/source-project edits do not update it.
After saving, Instantiate Prefab, Apply/Reset, reopening and Build Game use the
destination's copies. A failed validation or copy leaves the scene unchanged and
cleans the incomplete import directory. Dedicated asset editing, external refresh
and conflict remapping are still future work.

## Verification

`tests/test_prefab_import.py` covers library/schema collisions, dependency files,
typed path rewriting, import rollback, file registration and editor Undo/Redo.
`tools/verify_prefab_import_workflow.py` exercises actual file dialogs, live native
reload, nested placement, moving away the source, and an editor-built GPU game.

`tests/test_prefabs.py` exercises captures, two-instance reference remapping,
multi-level inheritance and override removal, independent nested overrides,
structural/component additions and removals, malformed dependencies, schema
conflicts, immutable inputs, actual file roundtrips and CLI overwrite/path guards.
See [validation-report.md](validation-report.md) for recorded results and the
remaining native/editor acceptance work.

`test_prefabs_lowering.py`, `test_prefabs_native.py` and `test_prefabs_editor.py`
cover compilation, real IsA/ownership, isolation and remapping, native roundtrips,
nested variants, destruction/timer cleanup, invalid graph-node diagnostics,
editor dialogs and transactional scene edits. The desktop workflow additionally
compares native states and GPU bytes at frames 30 and 90. The additional editing
workflow is described below. Gameplay Apply/Reset have separate native and desktop checks.

## Apply, Reset and template reconciliation in the editor

Select any member, then use **Scene → Apply Prefab Overrides** to update the
owning instance's asset. This applies the whole instance, including ordinary added
children, deleted members, parent changes, names, tags and component edits. Other
instances of that asset, its variants and containing nested assets are updated
together. The base/nested source relationships remain intact; applying to a
variant or containing asset changes that asset's patches, not its dependencies.

**Scene → Reset Prefab Instance…** restores the whole instance from its current
asset: deleted members return with the same IDs, added descendants are removed,
and component additions/removals/values are reset. The dialog supports Cancel.
Both commands keep the root's complete local transform and scene parent. They
are one shared Undo/Redo operation and survive save/reopen. The Python API's
`keep_placement=False` also resets the root transform or applies it to the asset.

`editor/core/prefab_edits.py` provides `apply_prefab_overrides`,
`reset_prefab_instance` and `reconcile_prefab_assets`. The latter accepts a complete
replacement library, so an asset and its dependents can be edited atomically.
All operations build and validate a separate candidate scene before committing.
The editor reloads the authored scene into the native preview; this resets the
running simulation, including its timers and transient state.

Reconciliation rules:

- Surviving local IDs retain their scene IDs. Added members get independent IDs
  for each instance; Apply adopts the source's existing ordinary-child IDs.
- A member explicitly deleted from one instance stays a tombstone during normal
  propagation. New descendants of that missing member also remain absent until
  Reset restores them.
- A removed template member is removed from all instances. Its ID moves into the
  optional `retired` mapping, which Python and native snapshots preserve and
  reserve. Reintroducing that same local ID restores its identity.
- Instance-only children survive ordinary propagation. When their template
  parent disappears they move to the nearest surviving ancestor. Reset removes
  additions, including added prefab instances and their detached members.
- Owned builtin components preserve all their fields during propagation. Apply
  and Reset clear ownership on the source/restored members, except retained root
  placement. Names and parent edits compare against the previous template.
- User component changes merge per property and Enabled flag. Added/removed
  components stay independent; arrays and maps are atomic property values.
  Explicit writes, including equal values, retain ownership until Apply or Reset.

An Apply with external/deleted entity references or detached members that do not
form a subtree is rejected without changing the scene. Fully contained independent
prefab children are adopted as nested asset bindings, as described below. Capturing
only part of another instance is rejected; reparent its members together first.
Updating a source that invalidates
a dependent override/reference also rejects the transaction; edit that dependent
in the same replacement library. Nothing silently discards the dependent patch.

```powershell
.venv\Scripts\python.exe tools/verify_prefab_edits_workflow.py
```

This opens the real editor, applies structural/value edits while inspecting live
Flecs state, verifies Reset/Cancel/Undo/Redo and save/reopen, then uses Build Game
and compares standalone GPU output. `tests/test_prefab_edits.py` covers reference
and merge conflicts; native tests also roundtrip retired mappings and ensure the
runtime never reuses a retired ID.

## Gameplay Reset without restarting simulation

Node **Reset Prefab Instance** (8039) accepts any live member and restores its
whole owning instance. Deleted members regain their original IDs. Added children
and added prefab instances are removed, including their detached members.
Builtin component ownership and explicit user-component overrides are cleared;
typed entity references are restored using the instance mapping.

`KeepPlacement=true` retains the root's local transform. False restores its
template transform. Both modes keep the scene parent. Invalid targets, hierarchy
cycles, removed root parents and entity/depth limits fail before changing the
scene. The graph reports the originating Reset node.

The operation retains the current Flecs world, frame/time, variables, surviving
owners' timers and queued custom events. Removed owners lose timers and queued
deliveries. Restored members rebind their event/timer observers, while stale
deliveries to destroyed native entities are discarded. It does not reload IR or
restart the runtime process. Editor menu Reset still edits the authored scene
and uses the existing preview reload path.

Open `examples/prefab_reset_demo/project.json`: frame 20 deletes the left robot
and enlarges the right; frame 60 restores both. A repeating timer keeps counting,
and a custom event queued immediately before Reset is delivered once afterwards.

```powershell
.venv\Scripts\python.exe tools/verify_prefab_reset_workflow.py
```

## Explicit user-component overrides

Inspector and gameplay component writes record intent separately from values.
Setting Health to 100 when the template already contains 100 pins that property;
a later template update to 50 leaves the instance at 100. Unwritten properties
continue to follow the template. Enabled, scalar values, vectors, arrays, maps
and typed entity references use the same rule; collections remain atomic.

Instance records optionally contain `component_overrides`, keyed by local entity
ID, then component ID. A mask contains `properties: [property IDs]`, `enabled:
true` (ownership of the Enabled flag), or `present: true/false` for explicit
component addition/removal. Presence ownership pins the complete component or
its absence. Adding an already attached component is a no-op. Removing an absent
component records its absence against later source additions.

Older scenes without these masks retain value-difference inference. Scene
validation and native loading reject unknown fields/IDs, duplicate property IDs,
non-boolean presence, missing members and masks that contradict attached values.
Snapshots, export, save/reopen and Undo/Redo preserve masks. Clones are ordinary
entities without prefab ownership. Destroying a member removes its masks; Reset
clears them and follows the current template. Apply clears the source instance's
masks and preserves other instances' masks. Applying an equal-value property to
a variant creates an explicit asset patch, so future base changes respect it.

```powershell
.venv\Scripts\python.exe tools/verify_component_overrides_workflow.py
```

The workflow uses two Blockbench robots with a Motion.Speed component. It pins
one instance at 90, applies 45 from the other, verifies native propagation,
Reset/Undo and save/reopen, and builds the project through the editor. The output
project is recorded in the workflow result JSON under `artifacts/validation`.
Its verified edited scene is also available as
`examples/prefab_overrides_demo/project.json`, with the same compiled IR.

Still pending: selecting a nested binding as its own Apply/Reset boundary, and a
dedicated prefab asset editor/external refresh. Current Apply/Reset operates on the complete
owning instance. The prefab milestone and overall engine goal remain incomplete.

## Gameplay Apply and live propagation

Node **Apply Prefab Overrides** (8040) accepts any live member and applies the
whole owning instance. It captures ordinary added children, member removals,
hierarchy/name changes, builtin components and typed user data. It preserves
authored base/nested dependencies and applies their overrides when rebuilding
derived templates. Source ownership is released; other instances retain their
explicit masks and value differences. The existing component granularity applies
to builtin Transform, Mesh, Tags and Activity.

`KeepPlacement` defaults to true: the source root's local transform is excluded
from the applied template and existing root placement is retained. False applies
that transform too. Scene parenting of roots stays local to the scene. Added
members retain the source's IDs; other instances receive reserved deterministic
IDs. Removed template members retire their mappings. Ordinary children of removed
members move to their nearest surviving ancestor. Explicitly deleted members in
other instances remain tombstones; Reset follows the newly applied template.

The shared C++ runtime builds the complete transaction, resolves dependencies and
validates a separate candidate world before mutating the live world. It preserves
surviving entity handles, the scene event target, simulation time, variables,
timers, subscription preferences and queued events. Removed entities lose their
timers and queued deliveries; activity changes suspend/invalidate delivery by the
normal activity rules. It also works from timer/custom-event callbacks without
invalidating surviving listeners. A subsequent Instantiate uses the updated asset.

External/deleted references, detached members, partial nested-instance captures,
dependency conflicts and invalid resulting hierarchies reject the
transaction at the original graph node. Gameplay Apply changes only the current
simulation's library; snapshots contain it, while Stop restores the authored scene.
Persisting gameplay state to a save file remains a separate roadmap requirement.

```powershell
.venv\Scripts\python.exe -m tools.create_prefab_apply_demo
tools\build.ps1 -Project examples/prefab_apply_demo/project.json
.venv\Scripts\python.exe -m editor.main examples/prefab_apply_demo/project.json
.venv\Scripts\python.exe tools/verify_prefab_apply_workflow.py
```

The three-robot demo edits the left robot at frame 20 and applies it at frame 60.
The middle robot follows the new scale and Motion.Speed; the right keeps explicit
equal-value overrides. Reset at frame 120 makes the right follow the updated
template. An owned timer continues and an event queued immediately before Apply
is delivered once. The workflow also rejects an invalid Apply and compares the
exact scene/IsA state before and after rejection, then builds and runs both GPU
paths at frames 30, 90 and 150.

## Adopting independently placed prefab children

Apply now captures a complete independently instantiated child as a `nested`
binding to its source asset. It preserves base/variant dependencies instead of
copying the resolved child entities into the parent's authored `entities` list.
Multiple separately placed descendants, including several hierarchy levels, are
supported in one transaction. The child's source asset is unchanged.

Each binding receives its own local namespace. Current child edits become patches
on the containing asset, including equal-value component writes and explicit
builtin ownership. Unmodified properties continue to follow later source changes.
Typed entity references can cross the captured bindings within the complete
parent subtree. References outside that subtree still reject Apply.

Live IDs, deleted-child tombstones and retired IDs move into the containing
instance's mapping/retired mapping. The consumed standalone instance records are
removed. This is a membership change: after Apply, Get Prefab Root returns the
outer root, and Apply/Reset on an adopted member operates on that outer instance.
The source dependency remains available in the authored binding and compiled
template bases. Independently selecting a nested binding for Apply/Reset is still
pending; there are no overlapping instance records.

Other instances of the containing asset receive their own newly allocated members.
Gameplay retains existing entity/event handles during adoption, including timers
and queued deliveries owned by a child. Reset follows the captured structure.
Undo in the editor restores the standalone child records; Redo and save/reopen
retain the exact resulting membership. The hierarchy also selects children
correctly when serialized before their parents.

Capturing only part of another instance or introducing an asset dependency cycle
rejects the complete transaction before touching the live scene. An entire nested
instance must be inside the selected outer subtree; detached members need repair.

`examples/nested_prefab_demo/project.json` starts with two groups and separately
placed robots. At frame 60, Apply on the left group captures its child and adds a
robot to the middle group. A source edit at frame 100 propagates an unmodified
name while retaining the captured scale and pinned speed. Reset at frame 120
restores the captured scale after a temporary gameplay edit. The child's timer
and queued event keep running.

```powershell
.venv\Scripts\python.exe -m tools.create_nested_prefab_demo
tools\build.ps1 -Project examples/nested_prefab_demo/project.json
.venv\Scripts\python.exe tools/verify_nested_prefab_workflow.py
```
