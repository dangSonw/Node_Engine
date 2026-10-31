# Node_Engine development goal

Build a usable Python desktop visual game editor with a shared C++/SDL3 runtime,
following all four original documents. Prioritize reusable foundations before
specialized nodes. Do not publish, deploy or push without an explicit request.

The added 2026-10-30 priority before completing the two native game templates is
the mandatory startup project manager and portable, versioned `.nen` project
manifest. Startup/New/Open, recent projects, legacy conversion, engine-version
checks, relocation and native startup-scene execution are implemented; see
[project format](project-format.md) and the validation report. The original
five priorities, node-code workflow and two playable native games remain in scope.

## P0 - Complete vertical slice

- [x] Read specifications and audit the empty workspace.
- [x] Create the persistent development goal.
- [x] Registry with stable IDs, versioned graph/project files and validation.
- [x] On Start / Update, Branch / Sequence / Loop, constants, numeric and boolean
  math, variables, vectors, delta time, entity transforms, injected input, logs.
- [x] Python Obsidian shell, editable node graph, inspector and project save/load.
- [x] C++ runtime, deterministic headless execution and bounded instruction count.
- [x] Export typed C++ calls; build and compare preview/export state.
- [x] Blockbench example saved as .bbmodel and glTF/GLB; import and render it.
- [x] Actual GUI interaction and native-game checks with recorded evidence.

P0 scope is an initial vertical slice, not completion of the engine. The initial
sample is a static nine-cube robot; the later scene-authoring sample renders two
entities sharing this mesh. See validation-report.md
for exact evidence and remaining acceptance requirements.

## P1 - General game development

- [x] New project creation, entity CRUD, selected-entity import and scene edit undo.
- [x] Typed scene variables, homogeneous arrays, string-keyed maps and sets, integer/string
  operations, nested For Each, variable authoring and shared undo/reload.
- [x] Pure/action function graphs, typed parameters/results, nested calls, early
  return, graph navigation, undo and native preview/export parity.
- [x] Reject stale native preview binaries and rebuild when needed.
- [x] Named one-shot/repeating timers, pause/resume/stop and queries, scoped timer
  events through Flecs, deterministic bounded catch-up and native preview/export parity.
- [x] Typed custom events, queued Send/Broadcast, subscription control, scoped
  payloads, authoring/undo and native preview/export parity through Flecs observers.
- [x] Function signature rename/reorder/add/remove and compatible type/default
  edits; migrate root/nested calls and bodies with validation, one-step Undo/Redo,
  preserved earlier history, live preview reload and native export parity.
  See [functions](functions.md).
- [x] Validated selection-to-function extraction in Gameplay and function graphs:
  lazy dependencies, complete structured regions, captured results, continuation
  guards and shared Undo across function navigation. Pure extraction currently has
  one exposed result; action extraction has one entry/continuation. See functions.md.
- [x] Event signature rename/reorder/add/remove and compatible type/default edits;
  migrate Gameplay handlers and nested senders transactionally, preserve routing,
  earlier Undo history and scene isolation; editor/native/export parity. See events.md.
- General macros, broader extraction boundaries and remaining collection operations.
- [x] General scalar and logic math batch: modulo, power, square root, floor/ceil/round,
  tangent/atan2, inverse lerp/smoothstep/remap, equality and ordered comparisons,
  boolean XOR, integer bitwise operations, checked integer division/modulo/abs/min/max
  and the remaining integer comparisons. Vector component extraction, angle/project/
  reflect/rotate Vector3 nodes and Vector2/4 arithmetic are now covered. Quaternion,
  matrix, struct/enum and callback-based collection graphs remain in scope.
- [x] Five shared seeded random nodes (Set/Get Seed, Float, Integer, Boolean), captured
  execution outputs and checkpoint stream restoration; see [random.md](random.md).
- [x] Eighteen typed Random Item, Random Weighted Item and Shuffle Array nodes;
  captured value/index pairs and reproducible loot/deck draws in the robot demo.
- [x] Random Vector and Random Direction: box-bounded coordinates, uniform unit
  sphere directions, shared stream checkpoints and a visible 3D marker in the demo.
- [x] Shared frame time scaling, unscaled/real/fixed time queries and saved clocks;
  timer/physics/animation freeze with responsive input, and normal-speed audio.
- [x] Optional unscaled named timers, mixed-domain callback ordering and saved
  timer clocks/modes; automatic resume countdown in the Blockbench demo.
- [x] On Late Update after physics/animation, same-frame camera follow, deferred
  late saves and frame-phase validation; actual editor and four-host integration.
- [x] Flecs scene storage with builtin components, hierarchy, runtime entity
  lifecycle, tag/name queries, inherited visibility and scene serialization.
- [x] Typed component definitions, attach/remove/has/query/property nodes,
  Inspector authoring, clone values and scene serialization.
- [x] Inherited Active, layer queries, suspended owner timers and inactive event
  delivery, Inspector Undo/Redo and native/GPU preview/export equivalence.
- [x] Entity Created/Enabled/Disabled events, inherited activity transitions,
  prefab recreation and staged edits, inactive receiver callbacks, exact saved
  queues, actual editor input and four-host native/GPU parity; see [entity lifecycle](entity-lifecycle.md).
- [x] Before-deletion callbacks, bounded deferred destruction, prefab revalidation
  after callback edits, latent-function integration and Save/Load without replay;
  actual editor and four-host native/GPU parity.
- Component schema editing/migration and remaining scene/application lifecycle events,
  prefab inheritance/overrides and complete game-state persistence.
- [x] Quit Application and On Application Quit, once-only boundary dispatch,
  bounded exit saves, preserved host intent across Load, editor process shutdown
  and actual Windows close/restart verification; see [application quit](application-quit.md).
- [x] Pause/Resume World, Is World Paused and Game Pause/Resume events, captured
  frame timing, idempotent ordered transitions, exact saved queues/pause state,
  unscaled input/UI work, native/GPU parity and physical editor controls.
  See [world pause](world-pause.md).
- [x] Named multi-scene projects, per-scene graphs, startup selection, Change/Reload,
  Scene Loaded/failure and status nodes, staged GPU/audio/UI replacement and exact
  cross-scene checkpoints. Actual editor authoring/input, asynchronous all-scene
  build snapshots and four-host parity are covered; see [scenes](scenes.md).
- Additive scenes, asynchronous loading, persistent-object transfer and scene-exit
  events remain open. Keep general editor/function/asset workflows ahead of P3.
- GLM transforms and camera controls; fastgltf asset import and SDL_GPU rendering.
- Lights, save/load and build packaging.
- [x] Basic RmlUi templates, 19 UI nodes/events, real desktop input and four-path
  relocated UI/state/GPU parity. Advanced category 18 work remains; see [ui.md](ui.md).
- [x] Versioned per-game save slots, typed variable batches and JSON records;
  desktop save/restart and relocated four-path state/file/GPU parity.
- [x] Bounded whole-game Save/Load at a frame boundary, strict program/resource
  identity and staged commit in both hosts. Four completion/failure event nodes
  brought the registry to 374 at that milestone. UI transient semantics, load latency and migration remain; see [persistence.md](persistence.md).
- [x] Basic scene audio assets, independent voices, loop/pause/resume/volume,
  SDL_mixer PCM parity and editor authoring. Buses/spatial audio/fades remain pending.
- [x] Static glTF/GLB base-color textures with PNG/JPEG, UV/color attributes,
  samplers/mips, alpha modes and linear/sRGB rendering, editor import and relocated export.
- [x] Reusable base-color material assets, instance parameter nodes and prefab dependencies.
- [x] Shared sprite atlases, frame/flip nodes, Inspector/library authoring and prefab dependencies.
- Material slots, PBR/normal maps, lights and sprite animation systems.
- [x] Keyboard/mouse action polling, digital axes, binding authoring and input replay.
- [x] Ordered keyboard/mouse/action entry callbacks, constant filters and scoped
  payloads, delayed input capture, checkpoint validation and neutral physical
  input after Load; actual editor and four-host replay verification.
- [x] Game-camera entities, projection/lens controls, Follow/Look At, authoring and prefab persistence.
- [x] Pointer position/delta/wheel use shared native frame state and version-2
  replay; see [input.md](input.md).
- [x] Cursor visibility and relative locking, saved requests in version-3 input
  checkpoints, physical editor/standalone lifecycle checks and a pinned SDL
  child-window focus adapter. Replay keeps cursor requests without grabbing the OS cursor.
- [x] Gamepad axes with configurable dead zones, connected-device queries and
  ordered button callbacks; hotplug, replay/checkpoint state, SDL virtual-device
  and embedded editor verification. See [gamepads](gamepad.md); physical hardware
  compatibility remains unverified.
- [x] Shared keyboard/mouse/gamepad action and digital/analog axis bindings,
  editor authoring with dead zone/inversion, exact polling/callback handoff and
  checkpoint restoration. See [input bindings](input-bindings.md).
- [x] Named input contexts with initial authoring, runtime enable/query nodes,
  overlapping membership, held-action rearming, scoped delivery cancellation and
  version-5 checkpoint continuation; actual editor and four-host verification.
  See [input contexts](input-contexts.md). Priority/consumption remains open.
- Durable player/device assignment, vibration/touch/sensors, runtime
  rebinding and full camera/cinematic playback; authored cinematic interpolation
  is now available as node 15016.
- Robust local-socket protocol, crash recovery, runtime property editing and trace.
- [x] Port-origin compatible search, explicit endpoint choice and one-step
  create/connect Undo/Redo in gameplay/function graphs; physical Windows gestures,
  Inspector validation, save/reopen and native execution verified.
- Command palette, full undo/redo and workspace persistence.

Already present in the initial slice: GLM transforms, camera orbit/zoom, static
fastgltf import, SDL_GPU viewport, basic framed IPC, crash restart, live transform
updates and a command palette. The scene-authoring milestone now adds multiple
rendered entities with shared GPU meshes and local glTF dependency copying. Seven
additional general spatial nodes brought the initial registry to 55. The typed-data
milestone provided 233 concrete definitions, including element-type variants
of collection operations. Function Input/Output bring the builtin count to 235;
project-owned function signatures generate their own call definitions. Eight timer
definitions bring the builtin count to 243. Each custom event generates five
project-owned node definitions. Nineteen entity/hierarchy nodes bring the builtin
count to 262. Flecs stores builtin scene components and ChildOf relationships and
routes timer/custom events using the same world and entity handles. Each user
component contributes six operations and two nodes per property, stored as real
Flecs component pairs. The Health/Inventory example verifies these with a timer
and action function in native preview and export. Six Active/Layer nodes bring the
builtin count to 268. The activity example passes 37 real desktop/native checks,
including inherited suspension and matching GPU output at three frame counts. Remaining
work includes component-schema migration, general macros, broader device/IME input testing,
per-workspace layouts, trace/debugger support and shared runtime build caching.

## P2 - Simulation and presentation

- [x] Jolt primitive bodies and 30 graph nodes, shared 60 Hz simulation with
  On Fixed Update, entity synchronization and exact game checkpoint continuation.
- [x] Collision/trigger Enter/Stay/Exit handlers, scoped contact payloads, entity
  lifecycle safety and checkpoint continuity.
- Physics Inspector/prefab authoring, additional
  query outputs/shape casts and generic character controller.
- **Animation asset foundation verified:** ozz skeleton construction and pose
  hierarchy, glTF/GLB TRS sampling and skin palettes, with analytic native checks
  and a rigged Blockbench Idle/Wave/Walk asset. See [animation.md](animation.md).
- **Animation playback integration:** 13 nodes bring the builtin count to **438**;
  per-entity clocks, independent skinned instances and exact checkpoint continuation
  run in interpreted/generated headless/graphical hosts. The Blockbench playground
  verifies separate Wave/Walk, pause/seek/reverse and fresh-process restore.
- Animation clip/skeleton Inspector controls, finished/notify events, ozz blending,
  animation graph and timeline; GPU skinning/crowd performance follow.
- SDL3_mixer audio, RmlUi / SDL3_ttf game UI, asset dependency handling.
- Debugger/watch/breakpoints, profiling, large-graph and DPI benchmarks.

## Next delivery order

1. **Delivered:** General components: scene-owned typed definitions and stable IDs, attach/
   remove/has/query/property nodes, Inspector authoring, scene serialization and
   clone behavior. The health/collectible example passes 31 desktop/native checks.
2. **Active/Layer delivered; prefab integration in progress:** versioned assets,
   variant/nested resolution, typed-reference remapping, real Flecs Prefab/IsA,
   runtime Instantiate/lookup and editor capture/placement are implemented
   (see [prefabs.md](prefabs.md)). Five prefab nodes bring the builtin count to 273.
   Actual editor Undo/Redo/save/reopen and native/GPU parity pass 35 workflow checks.
   Editor Apply/Reset now reconciles entity/component additions/removals and
   propagates template changes, retaining stable IDs and instance overrides.
   Gameplay Reset now restores members inside the live world while preserving
   surviving timers/events and simulation state. Explicit user-property, Enabled
   and component-presence overrides survive authoring and native serialization.
   Gameplay Apply now resolves and propagates template changes inside the live
   world, preserving surviving delivery handles and simulation state. Seven prefab
   nodes bring the builtin count to 275. Apply now adopts independently placed
   prefab children as linked nested bindings, preserving IDs, overrides and live
   delivery handles. Project-local file registration and cross-project library
   import now copy glTF dependencies, preserve typed references and support
   Undo/Redo/save/reopen. Per-binding Apply/Reset selection and dedicated external
   asset editing/refresh remain pending. Editor
   authoring operations alone do not complete this milestone.
3. **Digital input and basic game-camera controls delivered:** keyboard/mouse actions,
   digital axes, binding authoring and deterministic input replay now exist in
   shared native preview/export. The robot playground passes 30 real Windows
   desktop/build/replay checks, including matching GPU bytes and keyboard focus
   recovery. Six new nodes bring the builtin count to 281. See [input.md](input.md).
   Thirteen camera nodes bring the builtin count to 294. Camera entities support
   perspective/orthographic lenses, Follow/Look At, hierarchy, prefab Apply/Reset,
   editor authoring and preview view switching. See [camera.md](camera.md) and the
   recorded native/desktop/GPU checks. Broader device input, camera rails/blending
   and advanced prefab operations remain open alongside this work.
4. Basic presentation and persistence: textures/materials, sprites, game UI/audio,
   versioned save/load and standalone packaging. Deliver a small playable example
   that can be built and reopened through the editor without hand-editing JSON.
   **Static texture import delivered:** PNG/JPEG, embedded/external images, UV/color
   attributes, samplers/mips, alpha modes and linear/sRGB output are implemented.
   The editor and a relocated game package are verified; see [textures.md](textures.md).
   **Reusable base-color materials delivered:** scene asset library, instance
   parameters, prefab dependency capture/import and 15 shared native nodes bring
   the registry to 309. Actual Qt/native/export checks cover authoring, instance
   isolation, failed-reload recovery and four replay checkpoints; see [materials.md](materials.md).
   **Sprite foundation delivered:** shared PNG/JPEG atlases, per-entity frames
   and flips, Inspector/library authoring and prefab persistence; 10 nodes bring
   the registry to 319. See [sprites.md](sprites.md) for the verification boundary.
   **Basic audio delivered:** SDL_mixer 3.2.4, scene sound assets, independent
   voices, playback controls and per-voice/master volume. Fourteen nodes bring
   the registry to 333. Actual editor/device/relocated-build checks compare PCM
   and state through all four native paths; see [audio.md](audio.md).
   **Basic game UI delivered:** RmlUi template authoring, 19 shared native nodes
   and event handlers bring the registry to 352. Real desktop clicks, Ctrl+A,
   Unicode entry/Enter, Pause/Stop, failed-load rollback and relocated four-path
   state/event/GPU parity pass; see [ui.md](ui.md). Advanced layout/navigation,
   IME, accessibility and UI animation remain open.
   **Progress-data persistence delivered:** 15 nodes bring the builtin count to
   367. Per-game slots, all 30 value types, atomic batch writes/loads, JSON records,
   corruption/type/version checks and process locking are implemented. The robot
   saves its score, name and rotation through actual desktop clicks; restart and
   relocated four-path state/file/GPU parity pass 47 workflow checks.
   **Timer/event checkpoint groundwork verified:** the internal native API
   preserves timer precision/order, cancellation epochs and typed queued messages.
   Forty-five checks include a fresh-process 160-frame continuation, failed-load
   rollback and prefab-owner recreation. These APIs now back the public Save/Load nodes.
   **Scene/input/audio checkpoints verified:** reserved entity IDs and preloaded
   meshes survive deletion; input retains same-frame edges; sound restores decoder
   phase, voice order and pause/stop state. Six fresh-process restore points match
   389 continuation frames and PCM bytes (81 checks). The version-2 audio journal
   fixes chunk-dependent resampling restoration; replay cost still grows with
   history. See [persistence.md](persistence.md).
   **UI checkpoint groundwork verified:** templates/instances, edits, controls,
   scrolling, document/focus history and queued generations survive fresh-process
   restoration (105 checks, 21 continuation frames per mode, six equal GPU image
   pairs). CMake reproduces the pinned RmlUi adapter on a clean dependency copy.
   Transient caret/gesture/animation state still needs defined save semantics.
   **Combined transaction groundwork verified:** independent stage/exact recapture
   and context commit preserve host storage/logs and hand over SDL output, capture
   and text input (46 checks, 132 continuation frames, seven equal PCM pairs).
   Both SDL dummy and actual WASAPI device handoff pass; unfocused-UI restoration
   now brings the combined probe to 48 checks.
   **Bounded Save/Load Game delivered:** deferred graph requests, version-2 slots,
   SHA-256 program/resource compatibility and both host loops are integrated.
   Three nodes bring the registry to 370. The four-path relocated process/UI
   callback workflow passes 68 checks with matching continuation PCM and game-camera
   GPU pixels. Actual editor authoring/Build Game and desktop Save/Load pass
   14 checks; the standalone game reads the embedded Preview slot.
   **Save/load result events delivered:** four global completion/failure handlers
   expose scoped Slot/Error payloads, work after context restoration and can queue
   the next request without recursive processing. The registry now has 374 nodes.
   The result-event demo passes 82 four-path state/GPU checks, including failures,
   retry, repeated loads, UI callbacks and corrupted subscription rollback.
   Next: practical audio restore latency, complete transient UI save semantics,
   schema migration and complete packaging. Authored interval autosave now writes
   the native `autosave` checkpoint through the normal deferred persistence path.
   Buses/spatial audio/fades remain later work.
   Material slots, runtime texture-file
   loading, sprite animation systems and Shader Graph/PBR remain later work.
5. General collision/physics and animation, then the specialized P3 systems.
   **Native physics foundation verified:** Jolt 5.6.0 now provides primitive rigid
   bodies, forces/impulses, material response, layer/mask filtering, ray/overlap
   queries and contact/trigger events. Independent native simulations reproduce
   240-frame body/contact traces. See [physics.md](physics.md).
   **Physics checkpoint integration:** body topology/ID allocation, forces,
   sleep/contact state and current events now restore in an independent world;
   game checkpoint version 2 commits physics with the other native subsystems.
   Fresh-process checks cover eight scenarios and 880 exact continuation frames.
   **Graph/host physics delivered:** 30 primitive-body, force, motion, filter and
   query nodes plus On Fixed Update bring the registry to **405**. Both hosts step
   at 60 Hz, synchronize hierarchy/scale/layer/activity and preserve accumulator
   and bindings in Save/Load. The Blockbench robot passes 63 relocated four-path
   state/GPU checks and 25 real editor checks, including physical keyboard input,
   Pause/Stop, graph Undo/Redo and reopening. Native 30/60/120 FPS runs produce the
   same one-second physical state.
   **Contact events delivered:** six collision/trigger Enter/Stay/Exit nodes bring
   the builtin count to **411**, using Flecs delivery with global/scoped receivers,
   point/normal payloads and receiver lifetime cancellation. The contact demo
   passes 91 four-path checks, including fresh-process restore from a save queued
   by Collision Enter and rollback for tampered subscriptions.
   **Scene/Inspector collider authoring:** initial body settings are stored in
   scene entities and inherited prefab components. Add/Edit/Remove, Undo/Redo,
   variants, runtime Instantiate/Apply/Reset/Clone and checkpoint restoration use
   the shared native scene/physics path. The authored robot demo passes 95
   relocated four-path checks and 35 actual editor checks. Physics prefab edits
   stage an independent world before mutating live handles. Compound convex and
   static indexed-mesh colliders now use this same path; collider gizmos and
   per-part offset editing remain open.
   **Complete closest-hit queries:** Raycast and Sphere/Box/Capsule Cast bring the
   builtin count to **415**. Each execution captures Hit, Entity, Point, Normal,
   Fraction and Distance together, through interpreted/generated code and action
   functions. Oriented casts support initial overlap and layer/sensor/exclusion
   filters. The robot example displays four live ground probes and preserves
   results through game checkpoints.
   **Primitive overlap queries:** Box and oriented Capsule join Sphere, bringing
   the builtin count to **417**. Each query returns a sorted unique entity array
   with live layer/activity/sensor/exclusion filtering. Captured arrays compose
   with collection nodes and For Each; the robot example detects entering and
   leaving two regions and preserves results through checkpoints.
   **Character native foundation:** Jolt CharacterVirtual attaches to a capsule
   with stable body identity, supports movement/jump/grounding, sliding, steps,
   slopes, moving supports and clearance-checked resizing. Independent-world and
   fresh-process checkpoints preserve pending input and native contacts. See
   [characters.md](characters.md).
   **Character graph/editor integration:** eight nodes bring the builtin count to
   **425**. Scene/Inspector character settings inherit through collider prefabs;
   movement/jump/ground queries, clearance-checked resize, clone and Stop/Play use
   both native paths. The Blockbench playground passes four-host movement and
   airborne/crouched Save/Load checks, plus real editor authoring and keyboard
   movement. Character capsule contacts now use the existing collision/trigger
   callbacks, with receiver destruction/recreation handling and exact continuation
   from a callback-triggered save. Animation now adds 13 shared playback nodes,
   skinned rendering, independent instances and checkpoint continuation, for **438**
   builtins. Next: clip/skeleton Inspector controls and animation events, collider
   gizmos/per-part editing and constraints; extended movement modes follow the
   general foundations.

Seeded scalar and collection randomness are delivered; missing collection primitives can accompany a delivery
that needs them. Extra node counts alone do not move a milestone ahead of these
end-to-end requirements. Each delivery keeps interpreter/generated-code parity
and records actual GUI/native verification before being marked complete.

Core loop control now includes **Break Loop / Continue Loop** for For, While and
all typed For Each nodes, with lexical scope validation, function isolation,
budget diagnostics, actual editor authoring and four-host robot selection plus
Save/Load/GPU parity. **Do Once, Do N, Gate and Flip Flop** add persistent
per-node/per-owner state, multi-input controls, reset feedback, scoped results,
entity lifetime cleanup and exact staged checkpoint restoration. The registry
now contains **873** builtins, including typed array/map/set families for 40 value
types, For Each over arrays/maps/sets, array concat/slice, the 27-node general scalar and logic math batch,
seven Vector3 geometry nodes, 16 Vector2/Vector4 arithmetic nodes and twelve
bounds/intersection geometry nodes,
eight scene-management nodes, five world-pause nodes, two application-quit nodes, two input-context nodes, three gamepad nodes, two cursor controls, three pointer reads, five keyboard/mouse/action entry nodes, four entity lifecycle events, two camera projection nodes and
**Multi Gate** with 1-8 active outputs,
sequential/random selection without repeats, configurable starts, looping and
exact route/RNG checkpoint continuation. **Delay, Wait Until and Retriggerable
Delay** now preserve suspended loops, action functions, scoped values and event
payloads across whole-game Save/Load, through shared native scheduling and typed
generated callbacks. **Switch Integer/String** now have editable per-node cases
with stable wiring, and **40 Select variants** evaluate only their chosen input.
Both support action functions and suspended graph restoration; the case editor
supports Undo/Redo, duplicate/paste and project roundtrips. Worker-thread async
flow remains open;
see [flow-control.md](flow-control.md).

## P3 - Specialized systems (after the general foundations)

- AI behavior trees, combat, quests and progression remain open; authored grid
  navigation, a persisted AI state machine, authored world streaming, combat
  damage/health and quest progression now have native nodes, and inventory has
  native add/remove/count/has nodes with capacity and scene-snapshot persistence.
- Multiplayer/replication, procedural generation, vehicles and advanced IK/VFX.
- Specialized graph compilers, plugins, advanced renderer effects and platforms.

## Completion rule

The [original-scope acceptance audit](acceptance-audit.md) records which technical,
editor-flow and catalog requirements are still incomplete or unproven.

Saved files and node counts are not completion evidence. Every delivered feature
requires a real test or an explicit unavailable status. Windows can be verified
on this host; Linux/Wayland and physical device tests require their own evidence.
The goal stays active until the remaining acceptance requirements are satisfied.
