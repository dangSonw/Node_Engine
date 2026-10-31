# Original-scope acceptance audit

Checked against the working tree on 2026-10-30, after typed components and
entity activity/layers, prefab integration, keyboard/mouse actions/axes, cameras,
base-color materials, sprite atlases, basic audio, game UI, progress-data persistence
and bounded whole-game Save/Load, graph physics, character controllers, fixed-step
host integration, compatible port search, seeded random/checkpoint integration,
scaled/unscaled timers, late frame callbacks, animation completion, loop early exits,
persistent execution gates, serializable latent execution, editable Switch/lazy
Select, entity Created/Enabled/Disabled/Destroyed, input event entries, pointer reads,
cursor controls, shared gamepad bindings, input contexts, application quit, world pause,
named scene replacement, transactional function/event signature edits and validated
selection-to-function extraction. This is an
incomplete-engine audit, not a release verdict.
The original four specifications remain authoritative; implemented examples do
not replace their broader requirements. Execution evidence lives in
[validation-report.md](validation-report.md).

Earlier template smoke verification rebuilt and ran both
`templates/games/flappy_bird` and `templates/games/isometric_snake_3d` through
the native Preview and Game hosts with matching JSON state; their deterministic
Python traces pass `tests/test_template_games.py`. This proves starter-graph
execution and separate Python simulations. It does not prove complete native
Flappy Bird or Snake gameplay: scoring, collisions/death/restart, Snake body/food
rendering and interactive play still need implementation and acceptance.

## Requested priority scope (2026-10-30)

These are completion boundaries for the persistent goal, rather than a count of
registered nodes or validated feature documents.

| Priority | Implemented foundation | Still required for completion |
|---|---|---|
| 1. Typed data | Nested Struct/Enum Make/Break and typed Get/Set; nominal Struct/Enum arrays/maps/sets, collection operations and callbacks; named function/event ports and validated delayed checkpoint captures; scope storage/lifetime and checkpoints; project-wide Struct/Enum synchronization/refactors, stable IDs, legacy collision handling and shared Undo across scenes; see typed-data.md, project-types.md and variable-scopes.md | Nested collections and complete typed-data acceptance, including larger-project/GUI/performance coverage |
| 2. Complete 2D | Sprite/tilemap/state/sorting and initial texture resource paths | Runtime texture replacement/loading workflow, advanced UI authoring and complete playable 2D acceptance |
| 3. Advanced 3D | Material/light, collider and animation/camera foundations | Full Shader Graph rendering/authoring, richer lights/animation/IK workflows and complete visual/physics acceptance |
| 4. Large games | Grid navigation, AI state, local gameplay state and interval-save foundations | AI decisions, actual world streaming, multiplayer transport/replication, complete gameplay systems, reliable autosave restore, actual profiling and mod/plugin API |
| 5. Editor | Graph editing/refactoring foundations and code/compiler-error navigation | Debugger, CPU/GPU profiler, complete refactor/delete acceptance, IME/accessibility and full GUI matrix |
| Added. Node code | Dedicated C++ Code node, editable action hooks, separate code view and four-host native evidence | Completion/server features and live code replacement without rebuild remain outside the delivered hook workflow |
| Added before games. Project startup | Mandatory Unreal-style category/grid/preview browser, searchable projects, Blank 2D/3D, durable shared history and existing-project discovery; structured .nen, version checks, legacy conversion and relocation; startup GUI/native evidence | Installer/file association and migrations for future unknown formats are not included; external project locations require adding their folder; see project-format.md |
| Templates | Valid starter projects and separate deterministic Python traces | Full native Flappy Bird and isometric 3D Snake, scoring/death/restart, controls, visual review and packaged builds |

Blank 2D/3D remain starting presets. Their saved suggestion filters apply to the
node library, quick add, function editors and exact typed port search; they do
not restrict scene contents. One mixed scene with sprites, tilemap, skinned model,
shared physics and camera has matching state across all four native hosts and
matching GPU captures. See [node-workflows.md](node-workflows.md). This does not
complete either pipeline or imply a separate planar 2D physics backend.

## Technical specification

| Requirement | Current evidence | Remaining acceptance |
|---|---|---|
| Python node editor; native C++ preview and exported game share behavior | PySide6/NodeGraphQt editor, typed runtime, native equivalence tests and GPU comparisons | Extend the same guarantee to each remaining system |
| Stable registry as source for ports, interpreter adapters and generated calls | `nodes/registry.yaml`, registry/compiler/codegen and native tests; dynamic function/event/component IDs and validated function/event signature migration, including nested senders and scene isolation | Component-schema migration and plugin compatibility |
| Versioned graph/project/entity/asset documents | .nen container version 1 with engine compatibility/UUID; legacy project layouts 1/2; safe conversion, startup manager, scene selection, relocation and save/reopen tests | Broader schema migration and richer asset registry |
| Typed IR and validation before export | Compiler rejects incompatible links, cycles, invalid values and broken execution scope | Extend validation as new graph kinds/types arrive |
| Generated C++ with originating-node diagnostics | Shared typed calls, `#line` directives, runtime node-error identity | Full compiler-error-to-graph navigation and debugger trace acceptance |
| Deterministic writes and asynchronous CMake/Ninja build | Unchanged-file timestamps preserved; actual asynchronous build/heartbeat and cancellation checks | Shared prebuilt runtime/build cache, environment diagnostics and packaged toolchain experience |
| Out-of-process SDL viewport | Real Windows HWND embedding, native GPU captures, crash/restart and keyboard/mouse focus checks; Esc restores Qt shortcuts | Broader IME/DPI/device focus tests; X11 and fallback strategy where embedding is unsupported |
| Framed/versioned local IPC | Protocol version 1, fragmented/coalesced frame tests, acknowledgements and failure handling | `node_executed` tracing and broader malformed-message/reconnect stress |
| Export assets and standalone game | Static glTF assets copied into projects; native games run without Python/Qt; scene/prefab models outside assets and their GLB/glTF dependencies staged with collision protection | Complete distributable bundle, dependency manifest and clean-machine verification |
| Runtime faults preserve editor work | Budget, arithmetic/type errors, failed reload and process termination checks | Debug/watch/breakpoints and broader recovery cases |
| Per-node code inspection and embedded code editing | C++ Code node plus action hooks; separate generated-call/runtime-source tabs, line numbers, indentation, Ctrl+S, function-graph support, save/reopen and Undo/Redo; shared compiled hook across four hosts; stale snippets require rebuild; Clang Problems open the originating scene/node and code line | Live code replacement without rebuild, arbitrary script languages, completion and full debugger |

`clang-format` is optional in the original specification. Runtime build caching
and code formatting should not be represented as installed/verified merely
because CMake contains an optional discovery branch.

## Design flows and editor acceptance

| Flow or gate | Verified portion | Still incomplete or unproven |
|---|---|---|
| A: import animated GLB, create character, play animation, build | Static model import and entity authoring; native glTF/GLB skeleton/clip/skin evaluation; 14 shared playback/event nodes, live skinned instances, four-host state/pixel parity and exact animation checkpoints | Dedicated skeleton/clip Inspector references, asset clip browsing and animation timeline; see animation.md |
| B: drag data port to canvas, compatible search, auto-connect, undo | Windows physical drag opens typed, graph-scoped search; explicit endpoint selection, one-step create/connect Undo/Redo, preserved wires on cancel, Inspector rejection/correction and stable save/reopen; authored graph executes in native headless/embedded preview | Linux/IME/accessibility checks remain; see node-search.md |
| C: backend error, Problems navigation, highlight, rebuild | Runtime/compiler validation reports node IDs; Problems can focus graph nodes | Full graph-ID path, consistent persistent error highlights/tooltips and compile-error navigation |
| D: customize and restore workspace | Dock movement, saved QSettings layout, reset behavior | Independent named workspaces, migration recovery and complete acceptance evidence |
| Assets and scene selection | Entity hierarchy, Inspector, mesh assignment, shared meshes and dependency copying | Thumbnails/cache, drag/drop acceptance, viewport selection and multi-selection synchronization |
| Visible unavailable capabilities | Unsupported workspaces and morph animation fail explicitly; skinned playback and PNG/JPEG base-color textures render | Replace unavailable paths only when their backend is implemented and tested |
| Layout, accessibility and performance | Actual Windows editor screenshots, QTest actions, build responsiveness and Unicode values | 1366×768/1920×1080 systematic checks, IME/focus conflict, accessibility audit, 100/500/1000-node benchmarks, large asset browser and startup/idle profiling |
| Platforms | Windows/Vulkan native behavior | Linux high-DPI/X11/Wayland evidence; no claim of cross-platform certification |

The test-only QApplication event pumping handles queued platform notifications
between GUI tests. It is not a substitute for background workers in production.

## Node catalog coverage

The registry exposes 29 category names and currently has 1175 builtin definitions.
Most are concrete typed variants of common operations. Project-owned functions,
events and components add dynamic definitions. Category names or definition counts
do not prove that a category is complete.

| Original categories | Current coverage | General gaps to address |
|---|---|---|
| 01 Events, 02 Flow, 05 Time | Start/Update/Fixed/Late Update, entity Created/Enabled/Disabled with inherited activity, inactive receiver delivery and restored queues; synchronous Destroyed before deletion, deferred nested removals and prefab revalidation after callback edits, collision/trigger Enter/Stay/Exit, custom events, scaled/unscaled named timers, structured branching/loops with scoped Break/Continue; integer/string Switch with editable stable cases and 40 lazy Select variants; per-owner Do Once/Do N/Gate/Flip Flop/Multi Gate with controls and checkpoints in Gameplay/action functions; Multi Gate has 1-8 active outputs, sequential/random cycles and saved route/RNG state; Delay/Wait Until/Retriggerable Delay preserve loop/function/event captures with exact staged checkpoint restoration; 25 seeded random nodes with saved streams; five clock nodes with shared scale, real/unscaled/fixed queries and exact checkpoint continuation; mixed timer ordering and saved clock modes; late camera/animation observations and deferred game saves; once-only Application Quit cleanup with bounded saves, normal window/IPC close and restart verification; Pause/Resume World and transition events with saved pause state, unscaled menu/input work and independent editor debugging pause; Scene Loaded/failure callbacks with per-scene bindings and checkpoint continuation | Scene-exit events; worker-thread async flow, dedicated countdown nodes and procedural noise; arbitrary output-port authoring beyond the fixed Multi Gate ports |
| 03 Data, 04 Math | Scalars, modulo/power/square root, rounding, trigonometry, interpolation/remapping, comparisons, boolean XOR, integer arithmetic/bitwise operations, Vector2/3/4 arithmetic and Vector3 component extraction, angle/project/reflect/rotate operations, quaternion construction/normalization/multiplication/slerp/rotation, matrix identity/multiply/inverse/transform construction and point/direction transforms, point/bounds tests, closest-point queries, ray-plane/sphere/bounds intersections, triangle closest point, sphere/bounds overlap, plane distance, 2D segment tests, bounds extrema, screen/world projection, typed arrays/maps/sets with For Each Array/Map/Set, concat and slice, string operations, named Struct/Enum values and typed Sort/Filter/Map callbacks | Nested collections, arbitrary callback graph interfaces and additional geometry primitives |
| 06 Functions | Typed pure/action functions and nested calls; scene-local signature migration; Gameplay/nested selection extraction with copied lazy dependencies, retained external reads, captured parameters/results, complete structured regions and continuation guards; shared Undo across function navigation, preview reload, save/reopen and four-host export parity | General macros, arbitrary multi-entry/multi-exit collapse and independent multiple pure-result extraction; deletion/refactoring, richer navigation and interfaces/delegates; existing saves/live frames are not migrated across changed programs |
| 07 Scene, 08 Entity, 09 Spatial | Flecs entities, hierarchy, components, activity/layer and transforms; prefab capture, native IsA/Instantiate/lookup, editor/gameplay Apply/Reset, live template propagation, explicit overrides, linked adoption of nested children and file/library import UI; named per-scene graphs, startup selection, staged Change/Reload and cross-scene checkpoint restoration with actual editor/build/four-host checks | Additive scenes, async loading and persistent-object transfer; per-binding Apply/Reset selection, dedicated prefab asset editing/refresh, spatial queries |
| 10 Input, 15 Camera | Keyboard/mouse actions, digital axes, bindings/replay, ordered key/mouse/action callbacks with scoped filters, saved delayed input and actual editor focus/Load reconciliation; pointer position/delta/wheel; cursor visibility/relative lock; gamepad device queries, normalized axes/dead zones and button callbacks with hotplug/replay/checkpoints and SDL virtual-device tests through the real embedded host; shared keyboard/mouse/gamepad action and analog-axis binding authoring; named context authoring and runtime enable/query with held-action rearming and version-5 checkpoint continuation; four-host state/GPU parity; game-camera entities, lens/projection, Follow/Look At, World To Screen/Screen To World, authored cinematic keyframe interpolation via node 15016, authoring/prefab persistence and editor orbit toggle | Physical gamepad/driver compatibility, durable player/device assignment, vibration/touch/sensors, runtime rebinding, multiple viewports, camera masks/blending/collision and full cinematic playback/rail integration; see input.md, gamepad.md and camera.md |
| 11 Physics, 12 Character, 13 Animation | Jolt 5.6.0 primitive, compound and static indexed-mesh bodies, filtering, forces and queries; 36 physics nodes plus six collision/trigger handlers, shared 60 Hz stepping and exact checkpoint continuation; ray and sphere/box/capsule casts return six captured hit outputs; sphere/box/capsule overlaps return sorted entity arrays; entity Inspector and inherited prefab collider settings with staged runtime edits; native scene synchronization and checkpoint roundtrip for authored compound/mesh parts; real editor and four-path Blockbench gameplay verification, including contact saves; eight CharacterVirtual nodes with scene/prefab authoring, clone/resize lifecycle, movement/ground/step/slope response, exact airborne/crouched checkpoint continuations and actual four-host/editor gameplay; character collision/trigger callbacks, callback destruction/recreation and exact contact-triggered Save/Load; 18 animation/IK nodes with per-entity clocks, skinning, scoped completion/notify callbacks, authored state transitions, safe clip transitions, native clip blending, planar two-bone IK and exact checkpoint continuation | Clip/skeleton Inspector and timeline; extended movement modes and crowd performance; collider gizmos, per-part offset handles, constraints, retargeting, root motion and full skeletal IK; see physics.md, characters.md and animation.md |
| 14 Rendering, 16 VFX, 17 Audio, 18 Game UI | Static/skinned glTF/GLB, textures/materials, sprite atlases and state-machine frame updates, sound assets and shared SDL_mixer PCM; RmlUi templates, 19 UI nodes/events, desktop input and relocated four-path parity; validated tilemaps, sprite sorting, runtime texture file upload, feature metadata roundtrip, and a native scene-feature metallic/roughness BRDF with emissive color, imported normal textures and up to four directional/point lights | Runtime GPU texture replacement, material slots, clustered multi-light scaling, authored Shader Graph/SDL_shadercross, advanced sprites/VFX; advanced audio; visual UI authoring, remaining layout/control nodes, property binding, navigation/animation, IME/accessibility; see materials.md, sprites.md, audio.md, ui.md and feature-pipeline.md |
| 23 Persistence, 24 Assets, 26 Platform | Editor project/scene persistence, glTF import; versioned per-game slots, all 40 typed variable forms, atomic batch save/load and JSON records; bounded Save/Load Game with deferred requests, strict SHA-256 program/assets identity, both host loops and version-2 slots; authored autosave interval writes a real `autosave` checkpoint in both native hosts; completion/failure events with scoped Slot/Error and restored bindings, four-path state/GPU parity; actual editor Build/Save/Load, relocated fresh-process state/PCM/GPU parity and rollback; SDL dummy/WASAPI device, capture and text-input handoff; animation playback restoration; scene/prefab model dependency hashing beyond the assets directory; Quit Application and host intent preserved across checkpoint commit | Remaining transient UI semantics, bounded-latency audio reconstruction, entity saves, migration/preferences/binary storage; complete dependency packaging, async resources and platform services |
| 27 Debug, 28 Editor automation | Logs, assertions, C++ Code and editor commands; begin/end/get samples use the game clock | Trace/watch/breakpoints, actual CPU/GPU profiler, profiler UI and automation nodes |
| 19–22, 25, 29 Specialized gameplay/systems | Navigation 19001, AI state 19002–19004, chunk-coordinate selection 19005, Combat 20001–20003, Quest 21005–21008 and local authority/value journal 22001–22005 have native implementations | Actual world load/unload and resource lifecycle, AI decision runtime, network transport/session replication, checkpoint restore for the replication journal, procedural generation and specialized extensions |

## Next concrete acceptance gates

The prefab asset resolver has direct tests for base/nested dependencies, typed
references, structural/component patches and file roundtrips. Native tests now
read real Flecs Prefab tags, IsA targets and component ownership. The Blockbench
demo starts empty, spawns a nested pair and matches preview/export state and GPU
bytes. Editor capture/placement, deletion, Undo/Redo and save/reopen are verified.
These results close the initial instantiation gate below; prefab editing remains
incomplete.

1. **Verified initial integration:** reusable scene-embedded prefab assets: create from a subtree, instantiate twice, retain stable
   local-to-scene ID mappings, remap internal references, and preserve external
   references by an explicit policy. Use real Flecs prefab/IsA semantics where
   applicable. The explicit capture policy rejects external references; CLI users
   may explicitly clear them. Project-local file registration and cross-project
   library import UI now copy model dependencies and preserve library identities.
2. **Partially delivered:** editor Apply/Reset and authored template propagation
   now reconcile entity/component additions/removals, preserve overrides, retain
   dependency links and reserve retired IDs. Gameplay Apply/Reset, runtime template
   propagation without restarting simulation, and explicit same-value user-property
   overrides are now implemented. Apply adopts complete independent child instances
   as nested bindings, retaining source dependencies, overrides and live IDs.
   Per-binding Apply/Reset selection and dedicated external asset editing/refresh remain open.
   Keep native/editor/GPU parity gates for these
   remaining behaviors; authoring tests cannot prove gameplay operations.
3. Keyboard/mouse actions and digital axes now have an interactive robot example,
   30 real Windows desktop/build checks and deterministic GPU replay parity.
   Basic game cameras now also have a playable following-camera example and
   desktop/native/GPU checks. Broader device input and advanced cameras remain, followed by presentation,
   persistence/packaging, physics/animation and the later specialized systems in
   [roadmap.md](roadmap.md).

Keep the persistent goal active until all original-scope requirements have
appropriate direct evidence. A passing regression suite certifies the cases it
contains; it cannot certify these missing systems.
