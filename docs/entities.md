# Flecs entities and hierarchy

The native scene now stores Transform, Identity, Mesh and Tags components in
Flecs 4.1.6. Timers and custom events use these same entity handles in the same
world. A string-to-handle index provides stable document references; it does not
hold a second copy of component state. The renderer queries Flecs components,
so new clones/spawns and deletions are reflected on the next render.

## General nodes

The entity milestone added nineteen builtin definitions (262 at that milestone;
the current registry also includes later activity and prefab nodes):

| Nodes | Behavior |
| --- | --- |
| Spawn Entity | Create a root entity from name, mesh and local position; return its reference on the Out path. |
| Clone Entity | Copy one entity's local transform, mesh, visibility, tags, parent and user component values; an empty Name keeps the source name. Children, handlers and timers are not cloned. |
| Destroy Entity | Destroy the entity and its descendants. Missing/empty references are a no-op. |
| Get Entity By ID | Return the matching live reference or an empty reference. |
| Get All Entities / Get Entity Count | Return live scene entities, excluding Flecs internal entities. Arrays use stable-ID lexical order. |
| Get/Set Entity Name | Read/write a display name without changing identity. |
| Find Entities By Name / Find Entities By Tag | Return all exact, case-sensitive matches in stable-ID order. |
| Add/Remove Entity Tag / Has Entity Tag | Add/remove/query a tag; duplicate Add and absent Remove are idempotent. |
| Set Parent / Get Parent / Get Children | Use Flecs ChildOf relationships. Empty Parent denotes scene roots. Get Children returns immediate children. |
| Get World Position | Compose the entire ancestor transform chain and return the world-space origin. |
| Set Entity Visibility / Is Entity Visible | Store local visibility; the query and renderer include inherited parent visibility. Visibility does not suspend gameplay. |

Spawn and Clone are actions with a typed result, not pure expressions. Their
reference can be wired only along their subsequent Out path, including nested
actions. Use an Entity variable to retain a reference for another lifecycle
event. Reusing the result never spawns another entity. Pure functions cannot
invoke these actions or context-dependent entity queries.

Mesh names must already be preloaded by an authored entity or prefab template. Empty
Mesh creates an unrendered entity, useful as a transform parent. A hidden authored
robot can serve as the mesh source for runtime clones. Loading arbitrary new
assets during simulation remains future resource-manager work.

## Hierarchy and transforms

Existing Position/Rotation/Scale nodes read and write local values. Rotation is
in degrees. World matrices compose `parent * T * Ry * Rx * Rz * S`, using GLM
double precision before conversion to GPU floats. Get World Position includes
parent translation, rotation and scale. Zero and negative scales are supported.

Set Parent retains the local transform; it can change world position. Detach by
setting Parent to the empty reference. Self-parenting, cycles, missing parents,
and paths deeper than 256 entities fail before changing the relationship. A
reparent also checks the depth of the affected subtree. Preserve-world reparenting,
world rotation/scale setters remain pending. See [prefabs](prefabs.md) for real
template inheritance and instance ownership.

The editor Inspector exposes Parent, Visible and JSON Tags. Parent choices omit
the selected entity and all its descendants. The Hierarchy displays nested
entities. Parent/visibility/tag edits, subtree deletion and restoration share the
graph undo history, save with the project and reset a running preview. Transform
edits continue to use the native property-update protocol. Drag/drop reparenting
and a large-scene model/view implementation remain pending. The authoring tree
shows saved scene entities; inspecting runtime-spawned entities is future work.

## Lifetime and serialization

IDs are deterministic `spawned_N` strings. The sequence never reuses a generated
ID during a scene run. Initial IDs are reserved, and serialized `entity_serial`
keeps dead references dead after restoring a scene snapshot. Stop/reload of the
original project starts a fresh simulation with its original ID sequence.
Entity getters fail at the originating graph node for stale references; use
Entity Exists before accessing an optional reference.

Destroying a subtree cancels its timers, pending recipient deliveries and event
subscriptions, after synchronous On Object Destroyed callbacks have returned.
Within these callbacks, repeated deletion of the pending receiver is a no-op;
other destructive requests wait until the current removal commits. For queued
events, if a listener destroys its own receiver, subsequent listeners for
that receiver do not run. Other recipients continue normally. Queued payloads
can still contain references that later become stale; the references are values,
not lifetime ownership. Deleting only the sender does not cancel another
receiver's already queued payload.

Flecs observers identify the listener snapshot. Graph handlers execute immediately
after `ecs_emit` returns, outside Flecs' observer defer scope. This lets a handler
spawn/clone an entity and read or mutate its new components in the same callback,
and avoids deleting a receiver during an active Flecs observer iterator.

Snapshot output retains the existing `entities` transform map and adds `scene`:
a version-one scene document containing current entities, local transforms,
parents, names, meshes, visibility, tags, activity, layers, typed user components,
variables and the entity ID sequence.
This document reloads through the same scene loader. It is a scene-state export,
not a full running-game checkpoint: clocks, frames, timers, event queues and
execution stacks are not restored from it.

Limits: 65536 live entities; IDs up to 128 UTF-8 bytes; names up to 512 bytes;
256 unique tags per entity, each up to 128 UTF-8 bytes. Names, IDs and tags must
be nonblank and contain no ASCII control characters. Scene documents are checked
before preview/export; native entry points also validate dynamic operations.
Generic component definition/attachment/property nodes and active/layer semantics
are implemented. Prefab instantiation, editor template reconciliation and gameplay
Apply/Reset without restarting simulation are available. Created/Enabled/Disabled/Destroyed
notifications are documented in [entity lifecycle](entity-lifecycle.md). Component
schema migration remains on the roadmap.
Destroying a prefab root also removes members that were
detached from its hierarchy; cloning a member creates an ordinary entity.

## Example and checks

Entity Active and Layer are now also authored in the Inspector and stored in
Flecs. See [activity and layers](activity.md) for inherited activity, timer/event
suspension, cloning and scene serialization.

```powershell
.\.venv\Scripts\python.exe -m editor.main examples/entities_demo/project.json
.\.venv\Scripts\python.exe -m pytest tests/test_entities.py tests/test_editor.py -q
.\.venv\Scripts\python.exe tools/verify_entities_workflow.py
```

Play creates a pivot and two Blockbench robot instances. The pivot rotates one
degree per update; a one-second timer destroys the temporary robot. At 30 fixed
frames both robots exist and the pivot is at 30 degrees. At 120 fixed frames one
robot survives and the pivot is at 120 degrees. The verifier checks the real
Qt/SDL viewport, parent authoring/undo, Stop/fresh Play, save/reopen, and exact
preview/export state and GPU image equivalence at both frame counts. It uses a
current root build with this example as NODE_ENGINE_GENERATED. Evidence resides
under `artifacts/validation/entities-*` and `ecs-*`.
