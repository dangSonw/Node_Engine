# Physics

Global [Time Scale](time.md) controls the fixed-step accumulator. The integration
step remains 1/60 second; scale zero preserves the world and partial-step remainder
until the next resumed frame.

The native Jolt module is implemented in `runtime/src/physics_world.cpp` and
`runtime/include/physics_world.hpp`. It is built with the shared runtime, and its
standalone native probe runs actual collision simulation. The scene bridge in
`runtime/src/physics_scene.cpp` exposes 36 physics nodes and runs the same 60 Hz
simulation in both native hosts. Six collision/trigger event nodes share the
same runtime. The Blockbench robot example exercises these nodes, real
collision response and game checkpoint restoration.

## Graph authoring and example

Open `examples/physics_demo/project.json` in the editor and press Play. Click the
viewport to focus input. W/A/D and the arrow keys apply force, Space applies an
upward impulse, R resets the robot, and S/L save/load the running game. Reopening
the game restores its saved checkpoint. Esc returns focus to the editor.

The graph creates a static box floor and a dynamic box body on the robot's parent
entity; its child holds the existing Blockbench glTF mesh. Add **Create Box Rigid
Body**, **Create Sphere Rigid Body** or **Create Capsule Rigid Body** to an execution
chain, and select the entity, local dimensions, motion type (`static`, `dynamic`,
`kinematic`), mass, sensor and continuous collision settings. Only one body may
be bound to each entity. Alternatively, select the entity in Hierarchy and use
**Add Rigid Body…** in Inspector. Scene colliders exist before Game Start; do not
also create a second body for the same entity in the graph.

## Scene colliders and prefabs

`examples/physics_authoring_demo/project.json` uses the same Blockbench robot,
ground and trigger, with their collider settings authored in the scene. The robot
and its mesh child form a prefab. Inspector supports box, sphere and Y-axis
capsule dimensions, static/kinematic/dynamic motion, mass, friction, restitution,
gravity multiplier, damping, collision mask, trigger, continuous collision and
enabled state. Dimensions are centered on the entity origin and use its local
scale. The existing entity Layer controls the body's collision layer.

Edits, removal, duplication and prefab Apply/Reset share scene Undo/Redo and
project persistence. Invalid settings and incompatible scale/hierarchy are
rejected before accepting the edit. Prefab variants and instance ownership retain
the complete `rigid_body` setting as one builtin property group. Compound and
mesh bodies use the authored `parts` schema described below and are validated
through the same scene/prefab path; per-part Inspector editing remains open.

These are **initial settings**. Runtime velocity, sleep, forces and node changes
belong to the live physics world; changing mass or damping during gameplay does
not rewrite the prefab's initial settings. Runtime Clone copies current body
state and the original settings. Reset restores the prefab's initial colliders
and clears their motion; Apply propagates authored settings while preserving the
live state of bodies whose settings did not change. New instances create their
bodies after applying parent transforms. Each physics-related prefab operation
first stages the scene and independent native physics world before changing live
Flecs handles, event subscriptions or timers. This staging cost grows with world
size; large-world editing/instantiation performance is not yet characterized.

Stop restores initial colliders at tick zero. Play advances them without adding
duplicates. Save/Load stores both initial settings and exact live body state;
restoration bypasses initial body creation and restores the native checkpoint.
Compound and triangle-mesh colliders now use the same authored scene, prefab,
native synchronization and checkpoint paths as primitive colliders. Collider
wireframe gizmos, per-part viewport handles and constraints remain open.

An authored compound body adds a `parts` array. Each part has `shape` (`box`,
`sphere`, or `capsule`), local `position`/quaternion `rotation`, dimensions and
empty `vertices`/`triangles` arrays. A mesh body uses one `mesh` part with finite
vertices and indexed triangles and must be static. Dynamic compound bodies may
contain convex primitive parts; a compound containing a mesh is static. Parts
are transformed by the entity's uniform world scale and survive prefab
Apply/Reset, cloning and scene physics checkpoints.

The category also provides Remove/Has Rigid Body, Set/Get Body Type and Mass,
Set/Get Velocity and Angular Velocity, Apply Force/Impulse/Torque, Set Gravity
Scale/Damping, Wake/Sleep/Is Awake, Set/Is Body Simulation Enabled, Set Physics
Material, Set Collision Mask, Ignore Collision Pair, Set Physics Gravity, Raycast
Entity, Overlap Sphere and Move Kinematic Body. Raycast Entity returns an empty
entity on a miss; Overlap Sphere returns sorted unique entity references.

## Raycast and shape casts

**Physics Raycast**, **Physics Sphere Cast**, **Physics Box Cast** and
**Physics Capsule Cast** each have In/Out execution ports and six typed outputs:

| Output | Meaning |
|---|---|
| Hit | Whether the query found an enabled body allowed by its filters |
| Entity | Closest hit's entity reference; empty on a miss |
| Point | World contact point on the target; zero on a miss |
| Normal | Unit surface normal pointing out of the target; zero on a miss |
| Fraction | Fraction of Displacement travelled, from 0 to 1; 1 on a miss |
| Distance | Length of Displacement multiplied by Fraction, in metres |

Connect the query to an execution chain. Its six results are captured together,
once per execution; they remain available on its Out path, including inside an
action function. Later scene edits do not change that captured result. The
compiler rejects connections that use it before the query or in another event.
The existing pure **Physics Raycast Entity** remains available for old graphs.

Origin is a world position. Displacement includes direction and maximum travel
distance: `[0,-10,0]` probes ten metres downward. The ray requires nonzero travel.
Sphere Radius, Box Half Extents and Capsule Radius/Half Height are world sizes;
capsule Half Height describes half the cylindrical segment, excluding its caps.
Box and capsule Rotation uses world Euler degrees in Y-X-Z order, matching entity
rotation. A cast translates that fixed orientation along Displacement; it does
not rotate during travel. The query creates no rigid body and consumes no body ID.

All four queries accept an unsigned 32-bit Mask, Sensors and Exclude entity.
Mask tests the target's layer; Sensors includes triggers when true. They observe
current transforms, hierarchy/activity and runtime body settings. Use Exclude
for the moving character or camera's own body. Check Hit before using Point or
Normal; Distance on a miss is the full requested travel distance.

A cast beginning overlapped reports Fraction and Distance zero, with a target
contact point and outward normal. Zero displacement is valid for shape casts and
checks initial overlap; it is not an all-hits overlap query. A ray starting inside
a solid reports its origin and a normal opposite the ray direction. Shape casts
can return a zero normal for a geometrically degenerate zero-motion overlap.

`examples/physics_queries_demo/project.json` uses the authored robot prefab and
shows four ground probes on the HUD. Each origin follows the robot center plus
0.5 metres, travels ten metres down, excludes the robot and ignores the center
trigger. The graph stores all six results, branches on Hit and displays distance
or `clear`. W/A/D/arrows apply force, Space jumps, R resets, S/L save/load and C
loads the last contact checkpoint. For character movement with sliding, step
climbing and grounding, use the separate [character example](characters.md).

## Overlap volumes

**Physics Overlap Sphere**, **Physics Overlap Box** and **Physics Overlap Capsule**
return an `array<entity>` of every matching body. Results contain no duplicates
and are sorted by entity ID, independent of body creation order. A miss returns
an empty array. These nodes use narrow-phase primitive geometry, so a body merely
inside a rotated shape's axis-aligned bounding box is not sufficient to match.

Center, dimensions and Rotation use the same world units and Y-X-Z Euler degrees
as shape casts. Box takes Half Extents; capsule takes Radius and the cylindrical
segment's Half Height. Mask, Sensors and Exclude follow the query rules above.
Disabled/inactive bodies are omitted; parent transforms, layer changes, cloning
and removal are observed on the next query. A query needs no entity or collider
of its own and leaves body allocation, contacts and simulation time unchanged.

These are pure data nodes: each read evaluates the current world. Store Value in
**Set Entity Array Variable** to capture it once for multiple consumers or before
changing the scene. Use **Entity Array Length**, **Entity Array Contains** or
**For Each Entity** to consume the array. Captured entity references can outlive
their targets; use Entity Exists before accessing a target that may be removed.

`examples/physics_overlaps_demo/project.json` defines two detection volumes in
the graph, both centered at `[0,1,0]` and excluding the ground. The box has half
extents `[1,3,1]` and includes triggers, so it always reports the center trigger
and also the robot while intersecting it. The capsule has radius 1, half height
2 and a 90-degree Z rotation; its horizontal volume ignores triggers. Each
query stores its complete array and updates a HUD count. Move with D to leave
the regions, then R to reset and fall back into both. The counts also survive
Save/Load through the existing graph and physics checkpoint path.

Use **On Fixed Update** for sustained forces and other simulation work. It runs
at 60 Hz, with `Get Delta Time` equal to 1/60 second, after frame Update and timer
dispatch and before audio. Hosts accumulate frame time and preserve the remainder;
a frame can run zero or several fixed updates. The callback runs even without any
rigid bodies, shares the frame's instruction budget, and restores the frame delta
after returning. A one-second host-frame limit bounds catch-up to 60 steps.

Scene transforms, inherited Active and layer changes synchronize before queries,
body operations and simulation. Dynamic and kinematic poses write back in parent
order, so child world motion is preserved under transformed parents. Boxes follow
entity scale. All scales must be positive, ancestors must have uniform scale, and
spheres/capsules also require uniform world scale. Unsupported scales report an
error. Removing an entity removes its body at synchronization; cloning copies
body settings, current velocity and enabled/sleep state. Explicit body disabling
and inherited entity inactivity both suspend simulation and queries.

## Collision and trigger graph events

**On Collision Enter/Stay/Exit** and **On Trigger Enter/Stay/Exit** receive real
Jolt contacts after each fixed step, once scene poses have been synchronized.
Any contact with a sensor uses the Trigger family; the Collision family covers
non-sensor pairs. Stay continues while bodies sleep. Removing or disabling a body
produces Exit on the next step, including when no bodies remain in the world.

Set the Inspector's constant **Receiver** to an authored entity, or leave it empty
to listen globally. A scoped listener receives **Entity** (its receiver), **Other**,
**Point** (world position, metres) and **Normal** (from Entity toward Other).
`Get Self` resolves to that receiver during the callback. A global listener runs
once per pair, with Entity/Other in lexical ID order; its Self is empty. The two
scoped receivers see opposite normals. Exit retains the last contact point and
normal; either entity reference can already be destroyed, so use Entity Exists
before operating on it.

Delivery uses the existing Flecs event system and bounded queue. Each native step
captures a stable contact batch, ordered by pair, with Exit before Enter for a
removed/recreated pair. Each contact queues the global listener, then the first
and second scoped receivers; listeners for one receiver run in node-ID order.
The queue drains between contacts. This lets a handler send custom events, apply
forces or change scene entities without running inside a Jolt callback. Removing
or deactivating a receiver cancels its remaining deliveries; global handlers
still receive that step's historical contact batch. Effects on contacts appear
in a later step. Callbacks share the frame instruction budget and fixed delta.

Subscriptions follow receiver lifetime/activity automatically. They participate
in the existing checkpoint binding identity and are validated before committing
a load. Saves requested from a contact handler run at the host frame boundary,
after delivery has drained. Restoring a contact checkpoint resumes Stay without
replaying its previously delivered Enter.

`examples/physics_events_demo/project.json` adds a center trigger and HUD status
to the Blockbench robot. Collision Enter also saves a separate `first-contact`
slot; C loads that collision checkpoint, while S/L keep using the regular slot.
The trigger has no visible mesh; it spans x/z from -1 to +1 metre and y from -2
to +4 metres. The robot's collider extent affects when it enters/exits the zone.

## Dependency and simulation

Jolt Physics 5.6.0 is pinned to commit
`e77f175595e64cb44218cc9d9d56fc365ad0e36a`. The source archive SHA-256 is
`0af9beea51637ef805e624fe838ea2870f7b68cd48cbe1615c853bd9bcf4f1d7`.
`tools/fetch_jolt.py` checks this digest and extraction paths and refuses to
replace an existing dependency. Provenance lives in
`deps/JoltPhysics-5.6.0/upstream.txt`; CMake stages its MIT license as
`licenses/Jolt.txt`.

`cmake/PhysicsDependencies.cmake` uses a static library, double precision
positions, Jolt's deterministic build option and a single-thread job system.
Optional SIMD extensions, GPU compute, sample applications and upstream test
targets are disabled. Physics instances own independent worlds and must be
called on the host simulation thread. The application owns fixed-step timing;
the module accepts one step from 1 microsecond to 100 milliseconds.

## Native capabilities

- Static, dynamic and kinematic rigid bodies, including transitions after creation.
- Box, sphere and Y-axis capsule colliders; compound convex parts; static indexed
  triangle-mesh colliders; quaternion rotation and world positions.
- Linear/angular velocity, force/torque, impulse, mass/inertia, gravity scale,
  damping, friction/restitution, sleep/wake and kinematic targets.
- Discrete or continuous linear collision detection, sensors, collision layers
  0–31, unsigned masks and explicit ignored entity pairs.
- Closest ray hit with entity, point, normal and fraction; sphere, oriented box
  and oriented capsule overlaps with sorted unique entity IDs. Queries can include sensors and exclude
  one entity. A ray beginning inside a shape returns fraction zero and a normal
  opposite its direction.
- Sphere, oriented box and oriented capsule sweeps with the same closest-hit
  filters, target contact point, outward normal and travel fraction; initial
  overlaps and zero-displacement shape queries are supported.
- Per-step contact enter/stay/exit with canonical entity order and oriented
  normals. Events are collected after simulation, outside Jolt callbacks.
  Sleeping contacts remain present while precise shape queries still find them.
  Removing/recreating the same entity emits the old exit before the new enter.
- Disabling a body removes it from simulation/queries and preserves velocity
  for reactivation. Moving/removing/disabling a support wakes nearby bodies.
  Invalid inputs are rejected before applying operations.

All dimensions and positions are in metres, velocity in metres/second and angular
velocity in radians/second. Caps are 4096 bodies and 16384 contact constraints.
Shapes accept dimensions from 0.001 to 100000; position components are bounded
to ±1e9, mass to 0.001–1e9, gravity components to ±1e5, gravity scale to ±1000,
damping to 0–1000, friction to 0–10 and restitution to 0–1. Velocity input
components must be within ±10000; Jolt clamps actual body speeds to its default
500 m/s linear and approximately 47.12 rad/s angular limits. Force/torque/impulse
components are bounded to ±1e12. Quaternions must be finite and nonzero and are
normalized. Sensor and shape settings are selected at creation.

Simulation capacity errors stop the step with an error; a step that has already
started is not transactional.

## Physics checkpoints

`PhysicsWorld::checkpoint()` captures body topology and settings, native body IDs,
slot generations, retired IDs, activation order, disabled bodies, velocities,
pending force/torque, sleep state, contact caches, ignored pairs and gameplay
contact events. The engine owns ID allocation so removing/recreating bodies after
a load follows the same sequence as uninterrupted simulation.

`restore()` validates the record and builds a separate world. It preflights the
entire Jolt binary layout, restores the state, and requires exact recapture before
swapping the candidate into the live object. A failed restore preserves the live
world. Limits are 4096 bodies, 16384 contact manifolds, 65536 ignored pairs or
retired IDs, 16 MiB of native state and 48 MiB of serialized physics state. Retired
IDs clear after a successful step. This codec requires the pinned Jolt 5.6.0,
double-precision, little-endian build and supports primitive, compound and mesh
bodies without constraints. A dependency/layout change requires a codec version change.

The [character controller](characters.md) adds a version-2 physics-world
record when controllers are present. Worlds containing only ordinary rigid
bodies retain version 1. Character nodes and Inspector authoring use this same
world state, with additional checks for scene/controller consistency on load.

`Ctx::physics` and `Ctx::physics_scene` participate in game checkpoint version 2.
The physics field wraps the native world, local shape bindings, observed entity
transforms, fixed-step remainder and tick count. Game staging restores these
independently with the scene, input, timers/events, audio and UI; commit replaces
them together. `LoadScene` clears the previous physics world. Game checkpoints
also retain the strict program/runtime/assets identity check. Legacy game
checkpoint version 1 is incompatible with loading; progress-data operations can
still preserve it in a slot, and a new Save Game can replace it while retaining
the slot's independent variables and JSON. The outer save-slot version remains 2.

Save requests synchronize entity edits before capturing physics. Load preserves
the current program's fixed-update callback and resumes at the exact stored
remainder, including checkpoints taken between physics steps. Old saves with a
different runtime/program identity are rejected; there is no save migration yet.

## Verification and remaining work

Run `tools/verify_physics.py` with the project Python. It builds the native probe,
checks actual body trajectories, materials, filters, lifecycle and query results,
and compares all body poses and contact events over 240 frames in independent
worlds and independent processes. Eight saved simulation scenarios also run 880
continuation frames in a fresh process, comparing full state hashes every frame.
They include pending forces, stacked/sleeping contacts, disabled bodies, changed
materials/mass, removed supports, reused body IDs, CCD and kinematic targets.
Malformed records must leave the running world unchanged. The report and trace are saved under
`artifacts/validation/physics-checks.*` with source and binary fingerprints.

`tools/physics_probe/CMakeLists.txt` is an isolated build entry with Jolt's internal
assertions enabled. Configure it with the same compiler/Ninja and Release build
type, then pass its build directory to `verify_physics.py --build ... --output ...`.
This probe does not require SDL or the editor.

`tools/verify_physics_scene.py` checks the relocated robot example through
headless and graphical interpreted/generated hosts: real motion, two bodies,
fresh-process Save/Load continuation, fractional-step checkpoints, rollback for
corrupted bindings and identical state/GPU output. `tools/verify_physics_editor.py`
checks real Qt graph authoring, Undo/Redo/save/reopen, embedded SDL simulation,
Pause/Stop/restart and physical keyboard movement. Reports and a desktop screenshot
are under `artifacts/validation/physics-scene-*` and `physics-editor-*`.
Pass `--events` to either verifier to exercise the collision/trigger example;
these reports use the `physics-events` and `physics-events-editor` names. The
four-host workflow also resumes the actual collision-triggered save and rejects
tampered physics subscriptions. `tests/test_physics_events.py` covers scoped
payloads/normals, lifecycle, callback destruction/deactivation, remove/recreate
ordering, custom-event dispatch and callback budget faults.

`tests/test_physics_scene.py` checks 30/60/120 FPS equivalence, transformed-parent
motion, scale/layer/activity changes, clone/removal and invalid graph parameters
through real native interpreted/generated programs. See [validation-report.md](validation-report.md)
for the current results and limits.

The `--authoring` option on both workflow verifiers exercises scene/prefab
settings, including contact checkpoint continuation. `tests/test_physics_authoring.py`
covers validation, prefab ownership, native spawn/reset/clone/apply and parent scales.

Pass `--queries` to both workflow verifiers for the four live probes, typed graph
connections, Undo/Redo/save/reopen and actual embedded Preview. The relocated
workflow checks analytical floor distances, every result output and the HUD in
all four native hosts, together with existing regular/contact/fractional-step
Save/Load continuation. Reports use `physics-queries` prefixes.
`tests/test_physics_queries.py` checks snapshot consistency after body removal,
fresh miss outputs, live filters, invalid inputs, result scope and function calls
through interpreted/generated native execution.

Pass `--overlaps` to both workflow verifiers for the overlap-region example.
The four-host workflow checks entry/exit/reset, exact entity arrays and HUD
counts in addition to checkpoint continuation and state/GPU equivalence.
The editor workflow wires both array outputs, checks Undo/Redo/save/reopen and
executes them in embedded Preview. `tests/test_physics_overlaps.py` covers
composing a captured result with For Each and destruction, repeated reads after
scene edits, parent/activity/layer/body filters, clone/exclusion and invalid
inputs, through both native execution paths.

Remaining acceptance includes collider gizmos and per-part offset handles,
extended character movement, constraints and animation. The current evidence covers Windows;
it does not certify those missing paths or cross-platform determinism.
