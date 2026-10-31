# Validation report - 2026-10-26 (Asia/Saigon)

## Verified foundation

- All four original Markdown specifications read. The workspace initially had
  documentation only, with no pre-existing backend or Git repository.
- Persistent goal created and active; specialized systems remain later work.
- 268 concrete builtin node definitions registered, including element-type variants
  of collection operations. The earlier spatial milestone had 55 definitions.
  Tests cover core graphs, editor/IPC, scenes, asset dependencies, typed data,
  collections, integer/string operations, reusable functions, timers/custom events
  through Flecs, entity lifecycle/hierarchy and compiled/interpreted equivalence.
- Previous entity milestone full-suite run: **173 passed, zero failures/errors/skips in 492.22 seconds**,
  with process exit 0. It includes all earlier graph/data/function/timer/custom-event
  cases and the final entity/hierarchy and Inspector changes. Evidence:
  `artifacts/validation/pytest-ecs-final.xml`, `pytest-ecs-final.log` and
  `ecs-milestone.json`. The earlier intermediate run had 171 passes and one stale
  test assertion expecting 243 builtin definitions; its log/XML remain as
  `pytest-ecs.*`. That assertion now checks registry ID isolation instead of a
  historical count, and the complete final run above passes.
- Separate targeted runs passed **24 entity tests in 101.47 seconds**
  and **26 editor tests in 123.02 seconds**. Evidence:
  `ecs-tests-final.*` and `ecs-editor-final.*`. These overlapping groups are not
  added to the full-suite total. The prior 143-test event milestone remains
  recorded in `pytest.xml`, `pytest.log` and `events-milestone.json`.
- Component milestone full-suite run: **196 passed, one GUI failure out of 197**
  (`pytest-components-final.xml`, 534.50 seconds, exit 1). The failure was stale
  Windows clipboard notifications between GUI tests. The shared QApplication
  fixture now pumps queued events at test boundaries; the complete editor group
  subsequently passes **29 tests in 19.69 seconds**, exit 0
  (`components-editor-complete.xml/log`). This does not claim a fresh full-suite
  pass. The 21 component native tests and 31 real desktop/native checks also pass;
  overlapping groups are not added. See `components-milestone.json`.
- NodeGraphQt emits distutils deprecation warnings. The Windows COM diagnostic
  `0x8001010D` still appears during Qt window interaction; the final suite and GUI
  workflow continue and exit successfully. This diagnostic remains unresolved
  and recorded, not treated as Windows COM certification.
- Typed-link validation, cycles, finite numeric values, deterministic generation,
  Unicode save/load, unchanged-file timestamp preservation and bounded loops.
- Interpreter and generated C++ share typed runtime functions. Mutating data in
  while loops is re-evaluated; division-by-zero identifies the originating node.
- Original headless Core Demo: 120 frames with D held yields score 3, X ~6 and
  rotation Y 120 degrees. Byte-identical preview/export snapshots have SHA-256
  `B8520B6FBBE7D1E6731E526B77C19D1C9B695FA465587FD1F19628A3F9061CCD`.

## Real desktop and 3D checks

`tools/verify_desktop.py --build` passed all 13 integration checks, recorded with
runtime events in `artifacts/validation/desktop-checks.json`:

1. Native build initiated through the editor completes successfully.
2. A Qt heartbeat continues during the asynchronous CMake build.
3. SDL3 GPU native window embeds in the Qt viewport on Windows.
4. fastgltf imports the actual robot: 324 expanded vertices, 108 triangles.
5. Pause keeps the simulation frame unchanged.
6. A GPU readback image contains the rendered model, not a blank buffer.
7. A live transform IPC update changes the native entity snapshot.
8. Stop resets the frame and entity transforms.
9. Loading a missing model reports an error and preserves the previous scene.
10. Loading a meshless scene clears previous GPU geometry.
11. Terminating the owned runtime preserves the editor graph and scene.
12. Play successfully starts a fresh runtime after that crash.
13. A rejected IR reload never resumes the old scene by accident.

Editor tests also verify stable IDs through duplication/undo/redo/reload,
incompatible port rejection, inspector validation, dirty state, actual save/load,
fragmented/coalesced IPC frames, and failed process startup cleanup.

`tools/verify_scene_workflow.py` additionally passed all **18 scene-authoring
checks**. These cover the real New Project dialog, external-buffer model import,
entity creation/duplication/deletion, actual Ctrl+Z/Ctrl+Shift+Z, shared GPU meshes,
live inspector/undo changes, camera framing, native export, switching projects
during preview and reopening saved documents. Evidence is recorded in
`artifacts/validation/scene-workflow-checks.json`; the retained project is
`examples/scene_demo/project.json`. See `docs/scene-authoring.md` for scope.

Actual images were inspected visually:

- `artifacts/validation/editor-running.png`: Qt shell, graph, native robot viewport,
  entity inspector and logs.
- `artifacts/validation/robot-preview.bmp`: standalone GPU image of the robot.
- `artifacts/validation/robot-preview-120.bmp`: robot after 120 update frames.
- `artifacts/validation/scene-authoring.png`: two independent entities sharing one
  model, a five-node graph and Vietnamese entity names in the editor.

The early `editor-initial.png` uses Qt's offscreen backend, which rendered missing
font glyphs on this Windows installation. The real Windows backend was then
used and checked; text renders correctly. That early image is not final evidence.

## Independent exported game

The Blockbench project was built through the editor. A separate folder received
only node_game_view.exe, SDL3.dll, shaders and assets. It ran with PATH restricted
to Windows System32, from that folder, for 120 frames. The robot rotated exactly
90 degrees (45 degrees/second at a deterministic 60 Hz).

Both the GPU bitmap and JSON state were byte-identical to interpreter preview
after the same 120 frames (`robot-standalone-120.*` versus `robot-preview-120.*`).
The one-frame captures also match with bitmap SHA-256
`85147ADB760D1C74BE7E024CA69FEC3B68EAB1826BB7E86F60E6CABEBE6F5CF2`.

Executable import inspection reports SDL3.dll and Windows/UCRT libraries only;
no Python, Qt, libc++ or libunwind DLL dependency. This is a native game build,
not a Python wrapper used to run the game logic.

The retained Scene Authoring Demo was rebuilt and run through both native preview
and compiled game for 120 deterministic frames. Independent assertions confirm
left robot position `[-1, 0, 0]` / rotation `[0, 90, 0]`, and right robot position
`[1, 0, 0]` / rotation `[0, 0, 0]`. Both JSON state and GPU bitmap are byte-identical:

- State SHA-256: `a7c0292c7bf04305188d2df0c2efdac5063c5f4f1bbeb88293939351124de49e`.
- Bitmap SHA-256: `aba0df45acfadfdf952e318588ae44780ec5b7149ac982394421d0c644fe312f`.

Results are in `artifacts/validation/scene-parity-checks.json`, with captures and
states named `scene-preview-120.*` and `scene-compiled-120.*`.

## Typed data milestone

`tools/verify_collections_workflow.py` passed **21 Qt/native integration checks**:
typed variable dialog cells and dropdown, map totals, Unicode logs, entity-array
targeting, paused/running reload, undo, cancel, native rendering, word-order search,
GUI build, standalone preview/export and saved project reopening. Its retained
example is `examples/collections_demo/project.json`. See `docs/typed-data.md` for
precise semantics, supported types and remaining collection work.

At 120 deterministic frames the map total is integer 12, the log is `Vật phẩm: 12`,
and both robots rotate `[0, 90, 0]`. Preview and compiled state match; their GPU
bitmaps are byte-identical with SHA-256
`86045a71cecebac16b8481f0a12c556bb7e9bc87d6bb81e7e5a349f279be2831`.

Evidence is in `artifacts/validation/collections-workflow-checks.json`,
`collections-preview-120.*`, `collections-compiled-120.*`, `typed-variables.png`
and `collections-editor.png`. Both PNGs were inspected visually. The editor
capture focuses the update branch so the entity iteration nodes remain readable.

The native tests independently check expected results across all six element
types, signed-64-bit boundary values, strings containing Unicode and NUL,
non-aliasing of collections, nested For Each with source mutation, empty traversal,
instruction budgets, invalid indices/keys and type/overflow errors at source nodes.

Pytest also printed Windows COM diagnostic `0x8001010D` while exposing a Qt window;
execution continued, every assertion completed and the process exited 0. Windows'
own message formatter identifies it as an outgoing call during an input-synchronous
call. The diagnostic is retained in `pytest.log`, not hidden. The latest successful
full run has 30 warnings concerning NodeGraphQt's deprecated distutils version check. These results
do not constitute a full Windows accessibility/COM compatibility audit.

## Reusable functions milestone

Pure/action function graphs now have typed inputs/multiple results, nested calls,
early return, isolated call frames, static purity/scope/call-cycle checks and
qualified source-node errors. The editor adds signature creation, function graph
navigation and transactional body edits with undo/reload/save/reopen. See
`docs/functions.md` for exact semantics and current limits.

`tools/verify_functions_workflow.py` passed **26 Qt/native checks** (process exit 0).
It creates a pure integer Triple function through the real dialogs, edits nested
graphs, exercises mouse double-click navigation and inspector fields, and verifies
paused reload, undo/redo/cancel, GUI C++ build and project reopening. Canvas links
are connected through the graph adapter, not physical mouse wire drags.

The retained example is `examples/functions_demo/project.json`: two calls to Spin
Robot, which calls Rotation Delta. After 120 frames the robots rotate `[0,90,0]`
and `[0,-180,0]`; the left rotation is also returned into a typed vector variable.
The workflow's additional Triple(7) produces integer 21. Preview and compiled
snapshots match exactly, and both GPU bitmaps have SHA-256
`b628700502080211311b07ac90d2feea55e421acf53298cf077d0ea4895c6e70`.

Evidence: `functions-workflow-checks.json`, `functions-*-120.*`,
`functions-gui-build.log`, `function-signature.png` and `function-graph.png` under
`artifacts/validation`. The function graph screenshot was inspected visually.
`verify_function_embedding.py` separately verifies compositor-visible robot pixels
before/after a modal function editor (2,356 sampled pixels in both captures).
`functions-desktop-after.png` was inspected visually and includes the actual SDL
child viewport; window-only grabs can omit that foreign child surface.

Native function tests exercise all 18 parameter/result types, signed 64-bit and
Unicode/NUL roundtrips, nested pure/action calls, return inside loops, preservation
of caller locals, no-argument/void fallthrough and equal error/budget attribution.
Play also rejects stale runtime stamps/binaries, prefers a current shared build
when the local one is stale, and requests a build if neither is current.

One initial full test process printed 96 passing tests but exited with Windows
status `0xC0000409` during teardown. That run is **not counted as successful**;
its output is retained as `pytest-functions-initial-shutdown-failure.log`.
Graph controllers now have Qt ownership, function dialogs are disposed after use,
and tests dispose Qt widgets while Python callbacks are alive. The current
complete-suite status is reported at the beginning of this document.

## Timers and Flecs milestone

Eight nodes add named timers and On Timer Finished. Flecs 4.1.6 is pinned and
statically built from its upstream C source; actual entity observers receive
timer payloads. Scene transforms were flat at that milestone; the later entity
milestone below adds builtin Flecs components and hierarchy.

`tests/test_timers.py`: **15 passed in 83.84 seconds, exit 0**, including 13
native preview/export cases. Coverage includes owner/filter/payload scope,
repeat catch-up and listener ordering, pause/resume, cancel/restart, one-shot
lifetime, zero-second restart deferral, function scheduling, errors and budgets.
The editor test additionally rejects wires into static listener configuration.

`tools/verify_timers_workflow.py`: **21 checks passed, exit 0**. Real library
double-click and Inspector typing create/edit timers; Undo/Redo, pause/resume,
Stop/reset, fresh Play, save/reopen, responsive GUI build and embedded SDL robots
all passed. The desktop compositor image `timers-desktop.png` was inspected:
2,391 sampled robot-colored pixels, with both meshes visibly embedded in Qt.

Retained interaction project: `.cache/timers-5074f2aa/project.json`.
Clean example: `examples/timers_demo/project.json`. After 120 native frames,
independent 0.25/0.5-second timers yield exactly eight/four callbacks and Y
rotations +120/-120 degrees. Preview and compiled state match, including timer
remaining times, and their GPU bitmaps are byte-identical (SHA-256
`4b3f83f2d50e8b3e6803f4fef8c19e3504c0a8a5a479fe6f12bc1dcd81ac3a6f`).
Evidence: `timers-workflow-checks.json`, `timers-*-120.*`, `timers-gui-build.log`,
`timers.xml` and `timers.log` in `artifacts/validation`.

The initial native integration exposed a missing Windows dbghelp link and an old
CMake C-compiler cache incompatibility. Both were corrected before successful
builds; existing C-compiler choices are now preserved when upgrading a project.
The prior `.cache/functions-f541c003` project was rebuilt with its original
`cc.exe` cache choice: exit 0, fresh native stamp, equal 120-frame native
preview/export state, expected left rotation `[0,90,0]`, Triple(7)=21 and no timers.
Evidence: `timers-legacy-build.log` and `timers-legacy-*.json`.
This does not certify other operating systems. The existing C++20 `u8path` and
NodeGraphQt distutils deprecation warnings remain.

## Typed custom event milestone

Project event definitions generate five typed nodes each: On, Send, Broadcast,
Subscribe and Unsubscribe. They support all 18 existing payload types and actual
Flecs observer delivery. At that milestone the builtin registry had 243 definitions.

Native tests cover exact payload types/64-bit integers/Unicode/NUL, immutable
queued snapshots, sender/receiver/Get Self, deterministic listeners, broadcasts,
unsubscribe/resubscribe cancellation, event FIFO ordering across timer phases,
function calls, unhandled sends, errors, cyclic emissions and queue bounds.
Separate native tests build large strings at runtime and verify the 16 MiB
payload and 64 MiB queue storage limits fail at the sending node. Compiler and
editor checks cover static listener fields, scope, incompatible wires, pure
functions, definition isolation and unchanged live graphs after invalid loads.

`tools/verify_events_workflow.py`: **24 checks passed, exit 0**. It uses the real
Define Event dialog to author Notice(Count: int = 7), cancels a separate edit,
adds event nodes from the library and edits a payload in the Inspector. Shared
Undo/Redo, native receipt, subscription cancellation, Pause/Stop/fresh Play,
save/reopen and responsive native GUI build all passed. Connections use the
domain adapter's typed ports. The screenshot `events-desktop.png` was inspected
visually: both robot meshes are embedded in the Qt viewport, with 2,435 sampled
robot-colored pixels.

Retained interaction project: `.cache/events-53def688/project.json`.
Clean example: `examples/events_demo/project.json`. After 120 frames, preview
and exported game have equal full state, rotations `[0,180,0]` and `[0,-45,0]`,
and no pending deliveries. The interaction variant also receives Notice's
integer payload 7. Preview/export GPU bitmaps are byte-identical, SHA-256
`f2501483f23974adec1c31cf4cedcbd34ac5bf0a9aaf835a5495bc014b794c8b`.
Evidence: `events-workflow-checks.json`, `events-*-120.*`, `events-gui-build.log`,
`events-desktop.png` and `event-signature.png` under `artifacts/validation`.
The clean example also passes 120-frame headless preview/export parity with a
current native build fingerprint; `events-clean-preview.json` and
`events-clean-compiled.json` retain that separate verification.

An intermediate test-only fixture omitted a required output on a pure function;
that run exited 1 after 22 passes and is retained as
`events-initial-test-fixture-error.*`. The fixture was corrected and its isolated
check passed. The complete-suite result at the start of this report is the
authoritative regression result. Event-signature editing/migration and persistent
event queues are not included; [events.md](events.md) documents the current contract.

Clipboard checks found two editor integration issues: cached node classes could
paste definitions from another project, and Redo could restore the original
position instead of the pasted position. Paste now preflights current signatures,
function scope and typed links before changing the graph, imports no foreign
connection constraints, and records its placement in Undo. A mixed selection is
rejected atomically if any definition is unavailable or incompatible. Valid
event nodes retain their typed wires and positions through Undo/Redo. The final
24-test editor run includes these checks and the earlier duplicate-node test.

## Flecs entity and hierarchy milestone

Nineteen general nodes add runtime spawn/clone/destroy, name/tag queries, parent
relationships, inherited visibility and world position. Transform, Identity,
Mesh and Tags live in a real Flecs world shared with timers and custom events.
The renderer reads its components each frame. Scene snapshots retain metadata,
parents, variables and the generated-ID sequence; restoring one never reuses a
deleted generated ID. Timers and execution queues are not restored by scene load.

Destroying a parent deletes its subtree and cancels recipient subscriptions,
queued deliveries and timers. A self-destroying receiver stops its later handlers
without stopping unrelated recipients. Flecs observers capture listener lists;
graph execution occurs after the observer defer scope, allowing a callback to
spawn an entity and immediately access its components. Native regression cases
cover this previously crashing sequence, deterministic ID reuse prevention,
hierarchy cycles/depth, transform composition and preview/export equivalence.

The editor exposes nested Hierarchy entries and Parent, Visible and Tags fields.
Parent choices exclude descendants. Undo/Redo, subtree restoration and reopening
are covered by editor tests. Inspector commits preserve the active widget through
its key/mouse event; external edits and Undo/Redo rebuild fields from the document.
Delayed runtime shutdown callbacks are bound to the QObject lifetime.

`examples/entities_demo/project.json` uses the Blockbench robot: Play creates a
pivot and two robot instances, rotates the parent, and destroys one child after
one second. The 30-frame snapshot contains both robots; the 120-frame snapshot
contains one. `tools/verify_entities_workflow.py` checks actual Qt parent editing,
Undo/Redo, native GPU rendering, Stop/fresh Play and save/reopen, plus exact native
preview/export state and bitmap equality at both frame counts. See
[entities.md](entities.md) for the supported semantics and remaining work.

The final GUI run passes **27 checks with process exit 0**. Its desktop screenshot
was inspected: both runtime-created robots are visible in the embedded viewport,
with 1,174 sampled robot-colored compositor pixels. The retained interaction
project is `.cache/entities-570144d4/project.json`; the clean example is the one
listed above. Evidence: `entities-workflow-checks.json`,
`entities-workflow-final.log`, `entities-workflow-final.exit.txt`,
`entities-desktop.png` and `entities-{preview,compiled}-{30,120}.*`.
Matching GPU bitmap SHA-256 values are:

- 30 frames: `1d2c9c1ec3ab5c3b126325272882d14fc86dc70b7e928b40bf584af269ed0554`
- 120 frames: `e5c3ec3b65971981c9d0740624efbe6d26351b942ebc50276a7c95489667b345`

Windows COM diagnostic `0x8001010D` appears during Play in the successful GUI
run. All assertions complete and the process exits 0; this diagnostic remains
recorded rather than being described as resolved.

A separate current-root native check loads 5,001 authored entities (one parent
with 5,000 children), destroys their root through the graph and verifies zero
remaining entities. It passes in 0.832 seconds including process startup, load
and snapshot. This is a bounded headless hierarchy check, not a renderer or
arbitrary-scene performance claim. Evidence: `ecs-hierarchy-stress.json`.

## Typed entity components milestone

Scene-owned component schemas now generate attach/remove/has/enable/query and
typed property nodes. Actual Flecs pairs hold values and enabled state; clone
copies arrays/maps independently. Compiler and codegen rebuild definitions from
the scene, preventing registry leakage between projects. Definition/property
IDs survive display-name changes. Schema editing/migration through the UI remains
pending; property signatures stay fixed after creation.

Targeted verification passed **21 component tests in 66.69 seconds** and
**3 component editor tests in 1.78 seconds**. These cover malformed definitions
and instances, stable IDs, project/clipboard isolation, all 18 value types,
64-bit integers and Unicode/NUL, clone independence, repeated Add/Remove,
enabled-only queries, scene reload, missing-component diagnostics, action/pure
function context and immediate mutations inside Flecs event handlers. The editor
tests exercise definition/attachment dialogs, rejected values, Inspector edits,
Undo/Redo, save/reopen and switching to a project with no definitions.

`tools/verify_components_workflow.py` passed **31 real Qt/SDL checks**, process
exit 0, against the rebuilt native runtime. The example's timer calls a Damage
action function for each enabled Health component. Health falls from 100 to zero
at one second, its instance is disabled, the robot becomes hidden, and the
collector's Inventory.Items receives exactly one token. Subsequent queries do
not add another token. Stop and fresh Play restore authored values.

At **30 and 120 frames**, preview and generated C++ states match exactly and GPU
BMP files are byte-identical. Their SHA-256 values are:

- 30: `02cb284e038f8b77d1441d86e5a10985032cc6fbe5ce8e42bfeb72a3a87e9400`
- 120: `075cd13f2b66ee160da9bb04e9c68474a8b0fde8dec02abc4d20a8101b07dfc5`

`components-desktop.png` was visually inspected: graph, Inventory Inspector and
embedded native mesh are visible. The desktop compositor sample found 1,155
colored mesh pixels. The Inspector shows authored initial values; live runtime
inspection is not implemented. The retained interactive project is
`.cache/components-460399a0/project.json`; the reproducible source example is
`examples/components_demo/project.json`.

Evidence under `artifacts/validation/`: `components-native.xml/log`,
`components-ui-targeted.log`, `components-build.log`,
`components-workflow-checks.json`, `components-workflow.log`,
`components-workflow.exit.txt`, `components-desktop.png` and
`components-{preview,compiled}-{30,120}.{json,bmp}`. Targeted groups overlap the
full suite and must not be added to its total. The intermediate
`components-initial.log` and `components-targeted.log` retain failed test
expectations corrected before these successful runs.

## Tooling and Blockbench

- Shared Python 3.13.17; PySide6-Essentials 6.12.0, NodeGraphQt 0.6.44,
  setuptools 80.10.2 (required for its legacy distutils import).
- Shared LLVM-MinGW clang 23.1.4, CMake 4.4.4 and Ninja 1.13.2.
- SDL 3.4.18, GLM 1.0.1, nlohmann/json 3.12.0, fastgltf 0.9.1 and Flecs 4.1.6.
- Existing Blockbench Desktop 5.2.2; installed/pinned Blockbench headless MCP
  1.10.1. A real MCP handshake listed 23 tools. Create/edit/validate produced
  the nine-cube `.bbmodel` with zero reported errors and warnings.
- Server registration is verified separately from actual protocol operation.
  Discovery in the current Codex session may require reopening the session.
- The embedded glTF comes from a clearly scoped cube-fixture converter using the
  MCP-authored geometry. No claim is made of desktop UI glTF export.

## Remaining work and limits

The P0 slice and portions of P1 are implemented, **not the finished Node_Engine**.

- Flecs entities and hierarchy render with shared GPU geometry. Textures, skins,
  materials, full lighting and animation remain unimplemented. Builtin and typed
  user components and active/layer semantics are supported; component schema
  editing/migration, prefab Apply/Reset/template-edit propagation and complete running-game
  persistence remain pending.
- Typed scene variables, arrays/maps/sets, For Each and pure/action function subgraphs
  are implemented. Function extraction/macros/signature migration, structs/enums,
  nested collections, Sort/Filter/Map callbacks,
  seeded random and the remaining catalogue are pending. User-defined typed
  events and Send/Broadcast/Subscribe/Unsubscribe are implemented; signature
  editing/migration and persistent event queues remain pending.
  Named timers and scoped Flecs timer events are implemented; time scaling,
  latent Delay and persistent timer serialization remain pending.
- New-project/entity creation, scene edit undo and local glTF/GLB dependencies
  are implemented. Per-workspace layouts, full save/migration recovery and general
  resource management remain pending.
- Runtime crash recovery is manually triggered by Play; automatic restart,
  execution traces, breakpoints, watches and compiler-error navigation are pending.
- Static runtime is reused incrementally within a project; reuse of one prebuilt
  runtime library across projects and ccache availability need further work.
  Preview now checks native source/registry/binary fingerprints and automatically
  builds when no matching local/shared preview binary is available.
- Physical keyboard/focus transfer, resize/DPI matrices, large graph performance,
  build cancellation stress, Linux/X11/Wayland and other platforms are unverified.
- Physics, audio, game UI, specialized gameplay/networking and packaging UX remain
  later milestones. No publish, deploy, push or repository initialization performed.

## Entity activity and layers (2026-10-26)

Six additional builtin nodes bring the registry to 268. Flecs stores local Active
and Layer; effective activity follows ChildOf ancestry. Owned timers freeze their
remaining time, manual Pause remains independent, and inactive receivers discard
queued custom events without changing subscriptions. Reparenting refreshes these
rules immediately. Layer queries return sorted references with an ActiveOnly option.

The targeted suite passes **19 tests in 106.20 seconds**, exit 0
(`activity-targeted.xml/log`). An earlier run had three fixture failures caused
by an incorrect node display name; its log remains as `activity-native.*`.
The subsequent event-dispatch review kept current-delivery Unsubscribe semantics
separate from activation cancellation; the complete regression run includes both.

`tools/verify_activity_workflow.py` passes **37 real Qt/SDL checks**, exit 0
(`activity-workflow-visible.log`, `activity-workflow-visible.exit.txt`,
`activity-workflow-checks.json`). These include keyboard authoring, Undo/Redo,
save/reopen, inherited timer suspension, scene-level reactivation, layer queries,
Stop/reset, actual embedded rendering and native preview/export GPU parity.
An initial full-screen capture was occluded; it was removed. Final capture targets
the editor window and verifies viewport ownership with WindowFromPoint/IsChild.
`activity-desktop.png` was visually inspected and shows the editor with three
robots, the graph and Active/Layer Inspector. It contains 1,494 sampled colored
viewport pixels. The inactive frame-45 GPU image was also visually inspected.

| Frames | State | Preview/export bitmap SHA-256 |
|---|---|---|
| 15 | Three robots active | `14c5126dd889c7b934237e241c12bd5e81636168ee96f4faacdfdfbef234f3d1` |
| 45 | Group inactive; one robot rendered | `df4f1b15a8a75118180ca4e9b74ce0196aee2c87bd9a96bf8e592ee225a1d006` |
| 75 | Group active again; three robots rendered | `49bfe8425b5af74f419803570f61e06dccd53860de2a115ca15b62352dd2960c` |

All three state comparisons and bitmap byte comparisons match exactly. Sampled
colored pixels are 3,429 / 1,499 / 3,146 respectively. The shared root native build
is current. Full-suite status is tracked in `activity-milestone.json`; targeted
and desktop groups overlap the full suite and are not added to its total.

The complete regression run finished with **215 passed, 1 failed** out of 216
tests in 1,095.63 seconds, exit 1 (`pytest-activity-final.xml/log`). Its only
failure was the component registry test's hardcoded old builtin count (272
including its component, versus 278 after Active/Layer). The assertion now derives
the component contribution from the base registry. This correction happened after
the long run collected its tests; a separate rerun of that exact case passes
in 0.70 seconds (`activity-registry-count.xml`). This is a corrected-case rerun,
not a clean full-suite result. No additional test failures or errors occurred.
The Windows COM diagnostic `0x8001010d` still appeared during GUI tests without
terminating pytest; its underlying cause remains unproven.

Remaining boundaries: layers do not yet implement collision/render masks; prefab
inheritance/overrides and lifecycle events are next. This is not completion of the
full Node_Engine goal.

## Prefab asset authoring foundation (2026-10-26)

The version-1 asset library preserves authored base/nested dependencies and
property patches. It resolves variants, namespaces nested entity IDs, remaps
scalar/array/map entity references, and rejects dangling links, cycles, schema
collisions and invalid ID mappings. The capture/inspect CLI reads real projects
and saves/loads `.prefab.json` files with overwrite/path checks. A malformed
oversized transform integer now produces a validation error through the shared
scene helper rather than an uncaught OverflowError.

The focused run passes **47 tests**, exit 0 (`prefab-assets.xml`): 38 prefab
authoring tests, eight existing Active/Layer schema cases, and the corrected
component registry-count case. These are not added to the earlier full-suite
total. The asset tests cover reference aliasing between two instance candidates,
multi-level inherited changes with independent patches, nested references,
component/structural additions and removals, and real project file roundtrips.

`tools/create_prefab_assets_demo.py` was executed successfully. It saves three
assets beneath `examples/activity_demo/assets/prefabs`: Robot, Inactive Robot
(variant), and Robot Pair (nested). `tools.prefab_asset inspect` also validates
and resolves the saved files. Their mesh points to the existing Blockbench robot.
Resolved data and two distinct candidate ID mappings are retained as
`prefab-pair-resolved.json` and `prefab-instance-candidates.json` under
`artifacts/validation`. The original example manifest/scene/graph are not altered.

This is **authoring-layer evidence only**. No claim is made of native Flecs
prefab inheritance, editor prefab actions or runtime Instantiate/Apply/Reset.
Instance reconciliation, Undo/Redo, preview/export/GPU parity and recursive
destruction through those prefab operations still need implementation and tests.
The engine goal remains active; see [prefabs.md](prefabs.md) and the unchanged
end-to-end acceptance gates in [acceptance-audit.md](acceptance-audit.md).

## Native prefab instances and editor authoring (2026-10-26)

This extends the earlier authoring-only milestone. Scene compilation lowers
authored dependencies into ordered native descriptors, preserving original sources
and rejecting malformed instance mappings. The runtime creates actual Flecs
Prefab/IsA relationships for variants, nested templates and instance members.
Transform, Mesh/Visibility, Tags and Active/Layer inherit until written; writes own
copies. Mutable user component pairs follow Flecs' Override copy policy with typed
reference remapping. Native snapshots inspect actual Prefab tags, IsA targets and
ownership rather than inferring inheritance from matching values.

The five new nodes are Instantiate Prefab, Is Prefab Instance, Get Prefab Asset,
Get Prefab Root and Get Prefab Entity (273 builtin registry definitions total).
Instance roots own detached members for deletion, timers/event cleanup applies,
deleted child mappings remain reserved, and save/reload restores explicit ownership
including same-value writes. Normal scene queries exclude template entities.

Editor Scene actions now capture a subtree into an embedded prefab library and
instantiate assets via dialogs. The Inspector identifies prefab membership and
tracks builtin component ownership on edits. These actions, hierarchy deletion,
Undo/Redo and save/reopen preserve stable mappings. Native preview meshes include
the entire prefab library; a scene with no initial entities frames the first
spawned geometry. Portable file tools remain separate from the scene-embedded
library; no external file watcher/import UI is implied.

Recorded completed checks (separate runs, not a combined full-suite verdict):

- `prefab-native-initial.xml`: **10 passed**, exit 0, real headless C++ preview
  and generated-game equality; IsA/ownership, references, isolated mutation and
  removal, nested variants, tombstones, destruction/timer cleanup and error node IDs.
- `prefab-python.xml`: **52 passed**, exit 0, authoring and lowering validation.
- `prefab-editor.xml`: **24 passed**, exit 0, prefab menu/dialog/Inspector flow,
  transactional helpers and existing scene/activity/component editor regression.
- `prefab-editor-core-regression.xml`: **78 passed**, exit 0, all existing editor
  tests plus authoring/lowering tests on the final Python code. Its 52 prefab
  cases overlap the previous Python run and must not be counted twice.
- `prefab-build.log`: successful native SDL3/Vulkan build. Existing C++ `u8path`
  deprecation warnings remain; no native compilation errors occurred.
- `prefab-workflow-checks.json`: **35 passed** using visible Qt dialogs, actual
  Windows viewport ownership/compositor pixels, native snapshots, and standalone
  GPU execution. Both frame 30 and 90 have identical preview/export state and
  byte-identical BMP output. Captures contain robot geometry (2,285 and 1,883
  sampled colored pixels). Renderer events prove one unique template-only mesh
  loaded while the authored scene had zero mesh instances.
- `prefab-regression.xml`: **63 passed**, exit 0, existing entity/component/activity
  native regressions after the instantiation milestone.
- `prefab-editor-build-checks.json`: **12 passed**, including actual asynchronous
  Build Game, UI heartbeat, packaged mesh bytes and standalone execution from the
  build directory, with native preview/export equality and rendered geometry.

`examples/prefabs_demo/project.json` is the reproducible nested robot demo;
`tools/create_prefabs_demo.py` generates it. `tools/verify_prefabs_workflow.py`
checks editor authoring separately in a temporary project and writes desktop/GPU
images under `artifacts/validation/prefab-*`. The desktop capture was inspected
and its test window constrained to the available screen area to avoid clipping.

Both GUI pytest runs still printed the Windows COM diagnostic `0x8001010d` and
then completed with exit 0 and no failed/error test cases. The independent visible
workflow completed successfully without node errors. This evidence does not
establish the diagnostic's root cause or claim it is fixed.

Remaining prefab work: live Apply/Reset, per-field override semantics, propagation
of template edits, structural entity/component reconciliation, external library
registration and their native/editor acceptance tests. This instantiation milestone
does not complete the full Prefab feature or the overall engine goal.

## Prefab authoring Apply/Reset and propagation (2026-10-26)

The editor now applies an instance's changes to its asset, updates affected base,
variant and nested instances, and restores an instance from its current template.
Entity/component additions and removals are reconciled; surviving IDs stay stable,
removed template IDs are retired/reserved, and reintroduced local IDs recover their
identity. Apply adopts ordinary added-child IDs and remaps typed references for
the other instances. Builtin overrides retain component ownership; user components
merge changes per property and Enabled flag. Apply/Reset keep root placement.
Native tag-set ordering is canonicalized before authored comparisons so a snapshot
roundtrip cannot introduce a false tag override.

Both editor actions are transactional and share Undo/Redo. Reset has a working
Cancel path. Invalid dependencies or external/deleted references reject the full
edit. Existing base/nested bindings are preserved, rather than flattened. These
are authoring operations: editing reloads the scene into the native preview and
resets transient gameplay state. The graph catalog's gameplay Apply/Reset nodes
are not yet implemented.

Completed evidence, with overlapping reruns kept separate:

- `prefab-reconciliation-python.xml`: **74 passed**, zero failures/errors/skips.
  Covers existing assets/lowering, reference and merge conflict cases, template
  propagation, retired IDs, deleted-member descendants, reset of component and
  hierarchy changes, actual menu/dialog/Inspector operations and save/reopen.
- `prefab-reconciliation-native.xml`: **12 passed**, zero failures/errors/skips.
  Includes the original ten native cases and two new execution/roundtrip cases
  covering applied/reconciled templates, real IsA/ownership, component overrides,
  reference remapping, retired-ID reservation and restoration. Preview and
  generated C++ game states match in every pair comparison.
- `prefab-edits-workflow-checks.json`: **24 passed** through the visible Qt editor,
  embedded native renderer and Build Game. Apply adds/removes template members,
  preserves an independent instance override and releases source ownership.
  Reset restores the same deleted member ID, Cancel preserves the document, and
  Undo/Redo restores exact native scene and IsA metadata. Save/reopen preserves all
  authored sources/mappings. The compositor shows 335 sampled geometry pixels.
- That workflow builds the edited project with 552 GUI heartbeat ticks. Both
  packaged GPU executables run from their own build directory, retain six scene
  entities and retired mappings, and produce identical states and BMP bytes at
  frame 30. The image contains 796 sampled geometry pixels; its SHA-256 is
  `4d294f5e2b01f7a22af7da7d8d23eb95890aa95cc73fd0f4a0dc618e9af54ed1`.
  No runtime node errors occurred during the authoring workflow.
- `prefab-edits-final-checks.json`: after removing two new missing-initializer
  warnings, both final native builds have current fingerprints and the same
  preview/export state and byte-identical GPU image as the verified workflow.
  `prefab-reconciliation-build.log` and `prefab-edits-final-build.log` record the
  successful final builds. Existing `u8path` deprecation warnings remain.

The desktop and standalone screenshots (`prefab-edits-desktop.png` and
`prefab-edits-compiled.png`) were visually inspected. The independent workflow
uses `tools/verify_prefab_edits_workflow.py`; its saved temporary project path is
recorded in the result JSON. It does not modify the original demo.

A parallel native build encountered a shader-copy `Permission denied` failure.
Inspection found both GPU executable post-build steps writing the same staging
directory. CMake now uses one asset-staging prerequisite shared by both targets.
Subsequent root and project builds succeeded. The GUI pytest run still emitted
the previously observed COM `0x8001010d` diagnostic and completed with exit 0;
this work does not establish or fix that diagnostic's cause.

Remaining prefab scope is explicit in [prefabs.md](prefabs.md): gameplay graph
Apply/Reset and propagation without resetting simulation, explicit same-value
user-property overrides, reconciliation of separately instantiated nested children,
and external library import/editor UI. Other original engine requirements remain
in [acceptance-audit.md](acceptance-audit.md). The persistent goal is still active.

## Gameplay prefab Reset and explicit component writes - 2026-10-26

The gameplay Reset node (8039) now has desktop/native verification. It restores
deleted members with the same IDs in the existing Flecs world, removes added
descendants, clears overrides, remaps references and rebinds observers. Surviving
timers, queued events, variables and simulation time continue. Destruction prevents
stale delivery to recreated members. Root placement is configurable; invalid
hierarchy/target requests fail before modifying the world.

`prefab-reset-workflow-checks.json` records **26 passing checks**. The visible
editor observes damage before frame 60 and restoration afterwards, keeps the same
runtime process and authored scene, counts the queued event once and verifies
Stop/save/reopen. The embedded compositor contains 1,000 sampled geometry pixels.
Native preview and compiled GPU output match at frames 30 and 90, before and
after Reset. The frame-90 bitmap SHA-256 is
`0613fbf783c31be3bab7a999e878314d3e131dc25efa097a10eb7ad0623eaafc`.
The desktop and standalone captures were visually inspected.
`prefab-reset-final-checks.json` repeats both GPU checkpoints after the component
override runtime changes and confirms identical state/bytes against these results.

Explicit component write masks now preserve same-value property/Enabled writes,
component additions and removal intent. Python authoring and native gameplay
record the same format. Reconciliation respects it, Apply clears source masks,
Reset clears restored masks, and snapshots/save/load retain remaining ownership.
The variant Apply case also pins equal property values in the authored asset.

- `prefab-overrides-python.xml` / `.log`: **97 passed**, covering asset resolution,
  lowering, template reconciliation, malformed metadata, explicit scalar/collection/
  entity-reference values, component-presence changes and real Inspector Undo/Redo
  and save/reopen. Existing NodeGraphQt deprecation warnings remain.
- `prefab-overrides-build.log`: successful rebuild of all four native executables.
- `prefab-overrides-native.xml`: 25 native tests passed; one new presence-mask
  test initially used the wrong generated Add/Remove node labels. After fixing
  those labels, `prefab-overrides-native-presence.xml` records that case passing
  separately (1 passed). This is evidence from two runs, not a fresh all-green suite run.
- `component-overrides-workflow-checks.json` / `.log`: **19 passing checks** in the
  visible editor and packaged native games. A deliberate 90-speed write remains 90
  after applying 45 from the second robot. Reset follows 45; Undo restores the
  explicit 90. Native reload, save/reopen and Build Game succeed.
- The edited project builds with **549 GUI heartbeat ticks**. Preview/export
  produce identical states and GPU bytes at frame 30. The component-driven robots
  rotate by 45 and 22.5 degrees. The capture contains **1,756 sampled colored
  pixels**, SHA-256
  `dc6fcbc43d34e65b9da175ba510e0d33461a4f198d94bd3a9f1457f30577d59e`.
  No native node errors occurred; both captures were visually inspected.

The component workflow records its editable temporary project path in the result
JSON. It does not change the original Blockbench/prefab examples. The persistent
edited scene is saved in `examples/prefab_overrides_demo`. Its graph was arranged
without changing compiled IR; a fresh native run from that example matches the
editor-built game's state and GPU bitmap (`component-overrides-example.*`). The
goal remains active: gameplay Apply/live template propagation, independent nested
reconciliation, external libraries and the later original requirements remain.

## Gameplay prefab Apply and live propagation - 2026-10-26

Node 8040 applies an instance's current values and structural changes to its
asset, resolves variants/nested dependencies and propagates them in the running
Flecs world. The C++ transaction matches the authoring rules, validates the
candidate before committing, preserves surviving entity/event handles, retains
other instances' overrides and reserves retired mappings. Subsequent Instantiate
and Reset use the updated template. Gameplay changes remain in the simulation;
Stop returns to the authored document.

Verified results:

- `prefab-apply-native.xml`: **9 passed**. Covers complete state equivalence
  with Python Apply for both placement modes, variants/nested bindings,
  scalar/Enabled masks, added-child adoption and typed-reference remapping,
  structural removal/reparenting/retirement, queued-event/timer continuity,
  variant equal-value patches, reload and invalid-target/reference/dependency errors.
- `prefab-apply-native-boundaries.xml`: **4 additional cases passed**, nine
  deselected. Covers Apply inside timer/event delivery, preservation of surviving
  listeners, component addition/removal versus independent overrides, and an
  asset without user components followed by runtime Instantiate. Together these
  two runs cover all 13 tests in `test_prefab_apply_native.py`.
- `prefab-apply-core.xml`: **33 passed** for core registry/compiler/code generation
  and prefab lowering. `prefab-apply-build-smoke.xml` separately records one
  existing Reset timer/event regression passing after integration.
- `prefab-apply-build.log`: all four native targets built successfully; existing
  `u8path` deprecation diagnostics remain. The built preview fingerprint matches.
- `prefab-apply-workflow-checks.json`: **39 passing checks** in the visible editor,
  embedded viewport and editor-built packaged executables. Three Blockbench robots
  demonstrate propagation, an explicitly pinned instance, and Reset to the new
  template. The same process and authored document survive, a timer continues and
  a queued event arrives once. An invalid Apply reports `bad_apply` and preserves
  the exact live scene and Flecs inheritance state.
- Editor **Build Game** completes with **470 GUI heartbeat ticks**, stages the
  robot asset and produces a current runtime. Both GPU executables run using
  packaged assets from their build directory. State and bitmap bytes match at
  frames **30, 90 and 150**, spanning edits, Apply and Reset. The frame-90 SHA-256
  is `e7ccd3d0a88f02881bda21a76f147893e2d89bfeebc3ff0b0b22e915fc04e478`;
  frame 150 is `a0318041eaad8190fbbd0acf3a939effc68d5ff4a53d9f8e331cafde73fe25ed`.
  The embedded compositor contains **1,299 sampled colored geometry pixels**.

Desktop and standalone captures were visually inspected. The reproducible demo
is `examples/prefab_apply_demo`; the workflow also records its isolated saved and
built copy under `.cache`. The original demos remain available. There are now
275 builtin node definitions. Independent nested-instance reconciliation, external
prefab library authoring, and the other original requirements remain open; this
delivery does not complete the engine goal.

## Linked adoption of independently instantiated prefab children - 2026-10-26

Editor and gameplay Apply can now capture complete child instances as nested
bindings. Source assets remain dependencies. Parent patches retain child edits,
including equal-value property/builtin ownership, and typed references are
remapped across the complete captured subtree. Live IDs and retired/tombstone IDs
move into the parent's membership; the standalone child record is consumed.
Later source edits still reach unmodified properties. Partial instance captures
and dependency cycles reject the transaction. Apply/Reset currently uses the
whole outer instance; per-binding selection remains open.

- `prefab-nested-authoring.xml`: **41 passed**, covering existing reconciliation
  and new linked adoption, multiple nested levels, cross-binding references,
  captured equal-value masks, future source propagation, tombstone/retired ID
  restoration, Reset and transactional rejection.
- `prefab-nested-editor.xml`: **8 passed**. Includes a regression for selecting a
  child serialized before its parent. Hierarchy selection now occurs after all
  items are attached, so the Inspector and prefab actions receive the selected
  entity. Existing NodeGraphQt deprecation warnings remain.
- `prefab-nested-native.xml` records **15 passing cases** before a misplaced test
  assertion stopped the run. The assertion was returned to its original test.
  `prefab-nested-native-boundaries.xml` records **5 passing cases**, including that
  original test, all three invalid-nesting cases and a new multilevel case with
  an ordinary child and cross-binding references. These two runs cover all **19
  current native cases**; they are not one fresh all-green suite run. The added
  success cases verify interpreter/generated-code equivalence, Python transaction
  equivalence, real IsA ownership, delivery continuity, subsequent source edits,
  tombstone/retired ID preservation, Reset, new Instantiate and snapshot reload.
- `prefab-nested-build.log`: all four native targets rebuilt successfully; the
  current preview fingerprint was checked against the source tree.
- `nested-prefab-workflow-checks.json`: **33 passing checks** in the visible
  editor, embedded viewport and editor-built game. Covers live adoption, child
  timer/queued-event continuity, subsequent source changes, captured overrides,
  Reset, editor Apply/Undo/Redo, actual save/shutdown/reopen, and exact scene/IsA
  equality after rejecting a partially detached child.
- Editor **Build Game** completes with **467 GUI heartbeat ticks**, packages the
  Blockbench mesh and a current runtime. Preview and compiled game states and GPU
  bytes match at frames **30, 90 and 150**. There are six live entities before
  adoption and eight afterwards. The frame-30 image SHA-256 is
  `51a057567700bcbe60ffe804b2bbc3e7b0ba4da328d4f353873e5a24d7d566d9`;
  frames 90 and 150 share
  `e7ccd3d0a88f02881bda21a76f147893e2d89bfeebc3ff0b0b22e915fc04e478`.
  The visible compositor contains **1,053 sampled colored geometry pixels**.

Desktop and standalone images were visually inspected. Reproduce using
`examples/nested_prefab_demo/project.json` and
`tools/verify_nested_prefab_workflow.py`. The workflow result records the isolated
build project path. External prefab library authoring, per-binding operations,
input/game cameras and the remaining original specifications are still open.

## Prefab file registration and cross-project import - 2026-10-26

The File menu now registers selected project-local `.prefab.json` files and imports
the registered library from another saved project. Libraries retain stable IDs,
variants, nested dependencies and component schemas. Import rewrites only builtin
mesh fields and copies the complete supported glTF/GLB dependency set into a unique
destination assets directory. Conflicts and invalid dependencies fail before the
scene changes; a failed copy removes its staging directory. Registration/import
shares the editor Undo/Redo stack. Copied files remain for Redo.

- `prefab-library-import.xml`: **35 passed**, covering new import/registration
  tests plus existing scene/asset and prefab editor regressions. New cases verify
  source immutability, typed-reference/string preservation, base/nested mesh
  rewriting, local glTF buffers/images, schema/ID conflicts, missing files,
  traversal rejection, disk-error rollback, empty libraries and editor save/reopen.
  Windows emitted a handled `0x8001010d` diagnostic during an existing modal test;
  the process completed with exit code zero and the XML reports all 35 cases passed.
- `prefab-import-boundaries.xml`: after the final path/destination guards,
  **12 passed, 1 skipped**. The additional real symlink case could not create a
  symlink with this Windows account; internal/external symlink behavior therefore
  remains unverified on this host. It is not counted as passing coverage.
- `prefab-import-malformed-project.xml`: **1 passed** after adding a source
  manifest object check. The import action reports an invalid JSON manifest shape
  in Console without changing the scene or undo history. This repeats and extends
  the existing menu case; it is not an additional unique test.
- `prefab-import-workflow-checks.json`: **22 passing checks** through real Qt file
  chooser dialogs, the visible editor, native embedded viewport and packaged game.
  Registration and import Undo/Redo restore the exact authored document. Import
  and Undo/Redo reload templates in the same native process. A duplicate library
  leaves the document and native prefab state unchanged. Two placed nested pairs
  retain separate IDs and real IsA relationships. Four Blockbench robots render.
- The source library directory was moved away before reopening and building the
  target. **Build Game** succeeded with **500 GUI heartbeat ticks**, and packaged
  the copied model plus all four current native executables. The original project
  graph and scene entities were not imported into the target.
- Packaged preview and compiled game state and GPU bitmap bytes match at frame
  **30**. The image SHA-256 is
  `9e9ef497f6f259bebd5879c6c6a2070dbf806760373df3e82b9fa2d025427048`.
  The embedded compositor contains **470 sampled colored geometry pixels**.
  `prefab-import-desktop.png` and `prefab-import-compiled.png` were visually inspected.

Reproduce with `tools/verify_prefab_import_workflow.py`; its result records the
isolated source/target workspace. Source refresh, conflicting-ID remapping,
dedicated asset editing, per-binding Apply/Reset, input/game cameras and the rest
of the original engine requirements remain open. The overall goal stays active.

## Keyboard/mouse actions, digital axes and real focus - 2026-10-26

Six general input nodes add button edges, action Held/Pressed/Released and digital
axes. Scene bindings are authored through a dropdown dialog with shared Undo/Redo,
save/reopen and native preview reload. The interpreter and generated game call
the same native input functions. All four executables support ordered, versioned
frame input replay. The new `examples/input_demo` moves the Blockbench robot with
WASD/arrows, turns it once per Space/left-mouse press and resets with R.

The actual keyboard test found that clicking the foreign SDL child HWND received
mouse events but left Windows keyboard focus in Qt. SDL now explicitly focuses
the child on click; Esc explicitly returns native focus to Qt before restoring
graph focus. Focus loss releases held input. Pause/Stop discard held input and
queued edges. These behaviors are directly exercised, not inferred from replay.

- `input-regressions.xml`: **63 passed** across input, core compiler, function,
  scene and native-build fingerprint tests. The input tests include actual C++
  interpretation/generated-code parity, multi-button handoff, repeat suppression,
  same-frame down/up edges, repeated query reads, opposing directions, release-all,
  malformed replay frames/buttons and invalid native scene bindings. An unknown
  dynamically supplied action reports the same originating node in both paths.
- `input-final.xml`: **13 input tests passed** again after normalizing numeric
  node IDs in static input-name diagnostics. This repeats the input cases above.
  A diagnostic 40-second faulthandler dump fired during the native replay test;
  execution continued and completed normally in 47.51 seconds, with no failures.
- `input-editor-regressions.xml`: **26 existing editor tests passed**, bringing
  the distinct regression cases for this delivery to **89**. The existing function
  dialog test emitted Windows/Qt diagnostic `0x8001010d`; the process exited zero
  and JUnit reports no errors or failures. NodeGraphQt also emits existing
  `distutils` deprecation warnings. These diagnostics are not counted as clean logs.
- `input-workflow-checks.json`: **30 passed** with real Windows keyboard/mouse,
  actual Qt binding dropdowns, the visible embedded viewport and packaged game.
  Ctrl+S remains isolated while native focus is active and works after Esc;
  Ctrl+Z restores the scene binding and native world. Clicking a Qt panel also
  clears input while D is still physically held. Pause/resume does not stick keys.
- Native malformed-input reload is deliberately rejected without changing the
  paused scene; it is the workflow's one expected `node_error`. The test payload
  is a deep copy of IR so the authoring document remains valid for save and build.
- **Build Game** completes with **498 GUI heartbeat ticks**. The packaged native
  preview and compiled game both replay **30 frames**, moving the robot to
  approximately `[0.5, 0, -0.5]` and turning twice. State and GPU bitmap bytes match.
  SHA-256: `1dd953809eb7623dc76d7e237a837b013a3880b3756202f27f2b252137251034`.
- `input-desktop.png` and `input-compiled.png` were visually inspected. The
  embedded view contains **4595 sampled colored geometry pixels**. The desktop
  capture includes the expected malformed-input rejection in Problems.

The registry now has **281 builtin definitions**. This closes the keyboard/mouse
button and digital-axis slice, including the current Windows focus gate. Game
cameras, gamepad/analog input, broader platform/IME checks, advanced prefabs,
presentation/persistence, physics/animation and the rest of the original scope
remain incomplete. The development goal remains active.

## Game-camera delivery (2026-10-26)

Thirteen camera definitions (15001–15013) bring the builtin registry to **294**.
Camera data is stored in the Flecs scene, including hierarchy, cloning, prefab
inheritance/overrides, Apply/Reset and snapshot reload. SDL_GPU selects the scene
camera or the preview-only orbit view. The Python editor adds Create Camera,
Choose Active Camera, an atomic lens dialog, Inspector activation and view toggle.
The new `examples/camera_demo` follows the controlled Blockbench robot; C toggles
perspective/orthographic while the two stationary robots show relative movement.

- `camera-final.xml`: **14 passed**, covering invalid lens boundaries, Qt dialog
  edits with clipping-plane validation, Undo/Redo/duplicate/delete/save, all camera
  node operations, C++ interpretation/export parity, rotated/nonuniformly scaled
  parents, world-space Look At, one-second exponential smoothing, source-node
  faults and camera prefab Apply/Reset/removal/roundtrip.
- The first combined `camera-tests.xml` run has **105 passed, 1 failed**. Its
  **92 existing core/prefab/authoring cases passed**. The failed new camera test
  edited a prefab's original entity even though a later Apply patch overrode that
  property; the corrected test edits the effective patch. All 14 camera cases
  then passed in `camera-final.xml`. These are overlapping runs, not 120 distinct
  successful cases. NodeGraphQt still emits its existing `distutils` warnings.
- `camera-regressions.xml`: **43 passed** across existing native prefab tests,
  editor behavior and runtime fingerprint checks. Together with the 92 existing
  core/prefab authoring cases and the 14 final camera cases, **149 distinct tests**
  have passing latest results. The existing function-dialog test again emitted
  Windows/Qt diagnostic `0x8001010d`; the process exited zero and JUnit records
  zero failures/errors. Its log is not warning-free. No test process was restarted
  or terminated to obtain that result.
- `camera-workflow-checks.json`: **36 passed** using the visible Windows editor,
  actual OS keyboard input and SDL child window. Movement changes both robot and
  following camera; C changes the native lens. Returning from editor orbit to the
  paused game camera restores identical pixels without changing game state.
- Scene camera creation, keyboard lens edits, active selection, Undo/Redo,
  deletion/restore, chooser selection, save/reopen and native reload are checked.
  Selecting another active camera reloads the same process. A selected inactive
  camera renders an empty view. The one deliberately malformed camera reload is
  rejected and preserves the previous live world.
- Editor **Build Game** finishes with **531 GUI heartbeat ticks**. Both packaged
  executables replay **30 frames** in each projection. Preview/export state and
  GPU bitmap bytes match within each projection; the two projections differ.
  The player ends approximately at `[0.5, 0, -0.5]`, with the following camera at
  `[0.455051548, 2, 5.622182560]`.
- Perspective BMP SHA-256:
  `b1fcb46ec8561150bae1de870bb542a3122a2acaec993edfdbdb40592cb47eac`.
  Orthographic BMP SHA-256:
  `71c73462f328bb724c71bfdb102ac6e97d9ab1ac7ed6f2211685f570b48b3a67`.
  The report names the isolated packaged project. The verifier compares movement
  with a numeric tolerance; ten floating-point increments do not equal 0.5 bitwise.
- `camera-desktop.png`, `camera-perspective-compiled.bmp` and
  `camera-orthographic-compiled.png` were visually inspected. The robot is visible
  in the embedded preview; the standalone captures show the moving robot between
  stationary landmarks. One landmark reaches the orthographic frame edge after
  movement. The desktop image is captured before the deliberate invalid reload.

This proves the current Windows basic-camera path. Multiple viewports/masks,
camera blending/shake/collision, rails/timelines, camera gizmos, other platforms
and the rest of the original specification remain open. The goal stays active.
## Static base-color textures and material import — 2026-10-26

This milestone extends the shared graphical renderer; it adds no node definitions.
The registry remains at 294. Dynamic/reusable material nodes and the remaining
engine acceptance gates are still open. The persistent development goal remains active.

- `texture-tests-final.xml`: **57 tests, 56 passed, one skipped**, no failures.
  Includes 29 actual GPU/image/asset tests and scene/prefab-import regression tests.
  The existing symlink-copy case was skipped because this Windows account lacks
  symlink creation privilege (WinError 1314). It is not counted as passed.
- Measured pixels verify external PNG, JPEG, data URIs, bufferView images in glTF
  and GLB, texture orientation, sRGB decoding/encoding, baseColorFactor × COLOR_0,
  repeat/mirrored/clamp addressing, mip minification, UV channel overrides,
  KHR_texture_transform rotation/scale/offset, opaque/mask/blend and transparent
  primitive depth ordering. Reversing transparent draw authoring order gives the
  same image. Embedded JPEG matches external JPEG exactly.
- Malformed images, oversize PNG headers, missing UV channels, mismatched UV
  counts, missing files, escaped image paths and invalid sampler filters are
  rejected. Oversize image dimensions are rejected before decoding.
- `texture-workflow-checks.json` records **20 real editor/native checks**:
  file-dialog GLB import with PNG/JPEG dependencies, selected-entity assignment,
  Undo/Redo, embedded Vulkan rendering, save/reopen and responsive editor build.
  The original import directory is moved away before preview. Deliberately
  corrupting a copied PNG fails reload while preserving the running process,
  previous scene snapshot and exact framebuffer; restoring the file recovers.
- The workflow copies only native executables, SDL3.dll, SDL3_image.dll, shaders,
  assets and preview IR into a separate directory containing spaces, and runs
  with that directory as cwd. Preview and generated game produce equal snapshots
  and byte-identical GPU BMPs. The package path, build heartbeat count and SHA-256
  are stored in the workflow JSON rather than inferred from a successful build.
  A separate clean-PATH run (System32 and Windows only) also reproduced the exact
  same bitmap hash for both executables; see `texture-clean-path.json`.
- `texture-native-build.log` and `texture-editor-build.log` record real CMake/
  LLVM-MinGW builds. `texture-relocated-compiled.png` is the standalone result;
  `texture-desktop.png` shows the native viewport inside the actual Qt editor.
- The pre-existing camera/Blockbench robot scene was also launched with the new
  renderer (`texture-legacy.png` and `texture-legacy-state.json`). All three robots
  remain visible. Color-space correction intentionally brightens former flat-color
  output, so historical screenshot hashes differ.

An early workflow assertion sampled outside the narrow embedded camera frustum.
It was corrected to sample a visible panel; pixel helpers now explicitly reject
out-of-frame sample coordinates. The gameplay camera was not altered to make the
assertion pass. The desktop artifact widens the splitter so the full board is visible.

Limits: static base-color rendering, fixed face lighting for non-unlit materials,
all faces rendered without backface culling, center-sorted transparent primitives
(intersecting transparency may show artifacts), Windows/Vulkan SDR_LINEAR only.
Runtime material nodes, material authoring, PBR/normal maps, dynamic lights,
Shader Graph/SDL_shadercross, sprites and broader platform certification are pending.
See [textures.md](textures.md) for formats, limits and reproduction commands.

## Reusable materials and instance nodes — 2026-10-26

Fifteen category-14 nodes (14001–14015) bring the builtin registry to **309**.
Scene-owned material assets, Inspector assignment/parameters, prefab dependencies
and per-entity runtime overrides now reach both native execution paths and the GPU.
This completes the base-color material slice; the overall engine goal stays active.

- `material-tests-initial.xml`: **22 passed**, including parameter/asset boundaries,
  transactional edits, conflicting IDs, cross-project prefab portability, real Qt
  dialogs and node picker, all 15 native nodes, independent instances, Clone,
  snapshot roundtrip and prefab Apply/Reset/explicit clear. Native interpreter
  and generated C++ results/errors are compared, including source-node identity.
- `material-gpu-final.xml`: **7 passed** against the real Windows/Vulkan renderer.
  Measured pixels show replacement of imported factors while retaining texture,
  UV and COLOR_0; opaque/mask/blend, fixed-light/unlit, reset/clear and independent
  instances sharing one GPU mesh. `material-texture-regression.xml` records
  **29 passed** existing texture/image/sampler/alpha regression cases.
- `material-regression.xml`: **119 passed, one skipped** across core, scene,
  prefab authoring and prefab import. The existing Windows symlink permission
  case remains skipped; this is not counted as a successful test.
- `material-prefab-native-regression.xml`: **44 passed**, covering existing native
  prefab Apply/Reset equivalence (both placement modes), prefab lowering and the
  editor regression module. Across the five reports, **221 distinct tests passed,
  one skipped, zero failed**; `material-validation-summary.json` records the total.
  The existing Windows/Qt `0x8001010d` diagnostic appeared when the function editor
  dialog was shown. The suite and an isolated repeat both exited zero and passed
  their assertions (`material-editor-enter-isolated.xml`). This known platform
  diagnostic is still unresolved and is not counted as an extra distinct test.
- `material-workflow-checks.json`: **36 actual Qt/native/build checks**. The
  dialogs create/edit stable material assets; Inspector assignment, Undo/Redo,
  save/reopen and instance edits work without hand-editing scene JSON. Editing a
  shared asset reloads within the existing native process. Undo/Redo restores
  exact framebuffer pixels. Changing the center robot leaves side-instance
  bindings and their screen regions unchanged.
- An intentionally missing material ID rejects native reload while retaining
  the prior snapshot and framebuffer. Valid reload recovers in the same process.
  The desktop capture includes this deliberately reported validation failure in
  the Problems pane; it does not indicate a failed final preview.
- The editor's asynchronous Build Game completed with **560 UI heartbeat ticks**.
  Only executables, SDL3.dll, SDL3_image.dll, shaders, assets, IR and input replay
  were copied to `.cache/material-3b66c134/relocated game`. Both native executables
  ran from that directory with only System32/Windows on PATH. At frames 3/5/7/9,
  tint/fade/imported/reset states and BMP bytes match exactly. All four states
  have distinct images. Hashes, paths and individual assertions are in the JSON.
- `material-native-build.log`, `material-demo-build.log` and
  `material-editor-build.log` record actual builds. The workspace example is
  `examples/material_demo/project.json`; root native binaries were rebuilt for
  this example. `material-tint-compiled.png`, `material-fade-compiled.png`,
  `material-original-compiled.png` and `material-reset-compiled.png` show the
  relocated export. The desktop and exported images were also visually inspected.
  A separate root-build smoke run with `--project-root examples/material_demo`
  confirms preview/export state and T-key replay for the unchanged example
  (`material-demo-preview.json`, `material-demo-compiled.json`). Root manual
  builds require that asset-root option; only editor Build Game stages assets
  into a portable build directory.

Two early workflow harness errors were corrected before the successful run:
keyboard navigation on a closed combo produced multiple real undo steps, so the
test now chooses once through the popup; the deliberately corrupted IR is now
deep-copied before mutation so it cannot alter the authoring scene. Neither failed
attempt is included in the 36 successful workflow assertions.

Limits: one override applies to all mesh primitives; imported textures/UVs stay
fixed, shared assets are immutable during gameplay, prefab ownership covers the
whole binding component. Material slots, texture parameter nodes, PBR, dynamic
lights and Shader Graph remain pending. Face shading and transparent primitive
center sorting retain the existing renderer limits; only Windows/Vulkan is verified.
See [materials.md](materials.md) for the authoring flow and exact node semantics.

## Sprite atlases and per-entity frames — 2026-10-26

Ten category-14 definitions (14101–14110) bring the builtin registry to **319**.
PNG/JPEG atlas assets, Inspector assignment/frame/flips, shared library editing,
prefab dependencies and native rendering now work in Preview and exported games.
The overall engine goal remains active.

- `sprites-complete-final.xml`: **48 passed** after the final path validation
  changes. Coverage includes atlas/schema boundaries, transactional edits,
  import and cross-project prefab copying, actual Qt library/Inspector controls,
  Undo/Redo, save/reopen, all ten native nodes, independent instances, Clone,
  snapshot roundtrips, prefab Apply/Reset and matching originating-node errors.
  Actual Windows/Vulkan pixel checks cover all four atlas frames, both flips,
  transparency, hierarchy/pivot/visibility, material tint/opacity, PNG/JPEG,
  linear-filter frame boundaries and malformed file/grid/path rejection.
- `sprites-regression.xml`: **83 passed, one skipped** across texture/material
  GPU behavior, prefab editing and prefab import. The existing Windows symlink
  permission case remains skipped. `sprites-core-regression.xml`: **92 passed**
  across core, scene, prefab resolution/lowering and nested prefabs.
  `sprites-validation-summary.json` records **223 distinct passed, one skipped,
  zero failed** across these three reports. Earlier overlapping runs are not
  added to that total.
- The Qt modal authoring test emitted the existing Windows `0x8001010d`
  diagnostic; the process continued, all assertions passed and exit status was
  zero. NodeGraphQt also reports two dependency deprecation warnings. Neither
  diagnostic is silently treated as a resolved platform issue.
- `sprite-workflow-checks.json`: **30 actual Qt/native/build checks**. Inspector
  frame and flip edits change the selected sprite in the same native process.
  Undo/Redo restores exact framebuffer pixels, independent shared-atlas entities
  keep their own frames, and save/reopen preserves the project.
- A deliberately invalid atlas grid rejects reload while retaining the previous
  snapshot and framebuffer. Valid reload recovers in the same process. The
  desktop screenshot retains the expected validation error in the Problems
  pane; the preview shown is the recovered valid scene.
- Build Game succeeded with **493 editor heartbeat ticks**. The generated
  package was copied to `.cache/sprite-14729b59/relocated game`, the source
  project was renamed, and both native executables ran with only Windows and
  System32 on PATH. At frame counts 3/5/7/9, frame/flip state and BMP bytes match
  exactly between interpreted Preview and compiled export. All four interaction
  checkpoints have distinct images; hashes and the package path are in the JSON.
- `sprites-build.log`, `sprite-editor-build.log` and `sprite-workflow-final.log`
  record the builds and checks. `sprite-desktop.png` and
  `sprite-frame-two-compiled.png` were visually inspected. The workspace example
  is `examples/sprite_demo/project.json`; Space changes frames and X/Y flip the
  top-left sprite. Root preview and compiled binaries were built for this example.

The first workflow attempt clicked outside the checkbox indicator and timed
out. The harness now clicks the indicator; it does not alter the editor's input
behavior. Only the completed run is counted above.

Limits: regular grid atlases on a double-sided XY quad, one binding per entity,
unlit alpha blending by default, no atlas mipmaps. Sprite animation clips/state
machines, arbitrary frame rectangles, sorting layers, nine-slice UI and runtime
file loading remain pending. Center-depth transparency sorting retains the
renderer limitations; these results certify Windows/Vulkan only.
See [sprites.md](sprites.md) for authoring and node semantics.

## Audio dependency preparation — 2026-10-26

The official SDL_mixer **3.2.4** MinGW archive is installed under
`deps/SDL3_mixer-3.2.4`, with its upstream SHA-256 verified and provenance/license
recorded in `upstream.txt`. At this preparation checkpoint the engine had no
gameplay audio integration; the integration results below supersede that status.

`tools/verify_audio_dependency.py` builds the native probe and runs it from an
isolated directory with only the staged SDL3/SDL3_mixer DLLs and Windows on PATH.
`audio-dependency-checks.json` records **nine passed checks**: WAV decoding and
known stereo PCM values, pause/silence/position retention, resume with half gain,
independent shared-asset mixing, stop, one-shot completion, looping, malformed
audio rejection and opening the default playback device through WASAPI.
The sample comparisons use the real offline mixer; opening the device creates
no playing tracks. This dependency probe alone does not verify audible output,
graph Preview/export parity, engine pause, reload, authoring or packaging.

## Sound library, voices and shared PCM — 2026-10-26

Fourteen category-17 definitions (17001–17014) bring the builtin registry to
**333**. Scene sound assets, independent named voices, playback/pause/resume/stop,
per-voice/master gain and state/duration queries now use SDL_mixer in all four
native executables. The editor imports and names sounds and selects assets in
node Inspectors. The overall engine goal remains active.

- `audio-complete-tests.xml`: **28 passed**, including 17 asset/editor/native-node
  cases and 11 decoding/PCM cases. These exercise the actual Qt dialog, Undo/Redo,
  save/reopen, all fourteen shared nodes, interpreter/generated-code equality,
  node error identity, voice replacement, exact stereo samples, fractional and
  zero timesteps, malformed paths/files and MP3 decoding. Two NodeGraphQt
  dependency deprecation warnings remain.
- A WAV containing a `smpl` loop initially failed because the decoder reported
  an infinite duration even when the Play Sound node specified `Loop=false`.
  The shared loader now ignores embedded loop metadata and leaves whole-file
  looping to the node. Two regression cases verify audible sample values and
  completion/silence for `Loop=false`, and continued samples for `Loop=true`.
- `audio-final-tests.xml` also records **71 passed regression cases** across
  native core behavior, scene/core validation, sprite GPU rendering and runtime
  build fingerprints. That earlier run had 16 audio cases pass and one test
  assertion fail: the assertion treated legacy float variables as typed objects.
  The corrected assertion checks the real float/bool representation and passes
  in `audio-complete-tests.xml`. Do not count these overlapping audio cases twice.
- `audio-workflow-checks.json`: **55 actual editor/native/build checks** after
  rebuilding the loop-metadata and error-attribution fixes. WASAPI opened a real playback stream; editor
  Pause froze simulation and mixer state, Resume delivered nonzero PCM and
  retained the live voice/process, and failed decoding preserved the previous
  scene/device. Library/Inspector edits, Undo/Redo and save/reopen passed.
  The desktop check exposed stale node attribution on asset-load errors. Runtime
  commands now clear the previous node cursor before execution, and Problems
  labels command failures as Runtime. Separate assertions verify that file-load
  errors have no unrelated node while actual gameplay errors retain their source.
- Build Game completed with **578 editor heartbeat ticks**. The package was
  copied to `.cache/audio-b345e138/relocated game`, its original project was
  renamed, and all four native executables ran with only Windows/System32 on
  PATH. At frames 8/16/26/34/42, headless/graphical Preview and compiled export
  matched state and WAV bytes exactly; the graphical pair also matched GPU bytes.
  PCM measurements independently prove pause/finished-effect silence, resumed
  playback, half voice gain, master mute, restart and Stop All silence.
- `audio-demo-build.log`, `audio-editor-build.log` and `audio-workflow.log` record
  successful builds/execution. `audio-validation-summary.json` indexes the
  reports and records the current runtime fingerprint. `audio-desktop.png` and
  `audio-compiled.png` were visually inspected. The desktop's Problems entries
  are the deliberately introduced corrupt-file and invalid-volume errors; its
  viewport is the recovered valid scene.

The sample project is `examples/audio_demo/project.json`. Its locally generated
tones require no third-party recordings. See [audio.md](audio.md) for controls,
node semantics and the import/build workflow.

Limits: WAV and MP3 are fixture-tested; Ogg/FLAC decoding still requires individual
format fixtures. PCM/device checks do not establish acoustic quality across
physical hardware. Files load synchronously into encoded memory, gameplay voices
are scene-wide, and loading a scene resets playback. Buses, spatial audio, fades,
streaming, completion events, runtime file loading and device changes remain open.

## Basic game UI integration — 2026-10-26

`tools/verify_ui_dependency.py` passes **103 checks** in
`artifacts/validation/ui-dependency-checks.json`. The report includes SHA-256 of
the module, adapter, shader and probe sources. It covers the actual native
`UiSession` and `UiRenderer` modules in a freshly relocated Unicode-named directory
with only Windows/System32 on PATH. Headless, SDR and SDR_LINEAR modes agree on
widget state; the GPU modes run real SDL/Vulkan rendering and readback.

Controls, queued click/change/submit payloads, Unicode text, disabled/hidden
interaction, literal text handling, failed-load rollback, independent sessions,
destroy/recreate and full library restart pass. Pixel checks cover CSS/PNG color,
UI/UI and UI/scene alpha, preserved nonblack scene background, scissor clipping,
progress, slider geometry, glyphs and resize anchors. `ui-probe-linear.png` was
visually inspected. The probe uses injected SDL/context events; it does not prove
physical IME or embedded editor focus behavior.

Findings fixed: plain `button` is not a disabled form control in RmlUi; the stock
GPU backend's sRGB colors were double-encoded on SDR_LINEAR; default file I/O and
raw Windows drive URLs did not support the tested Unicode resource paths. See
[ui.md](ui.md) for integration contracts and pinned dependency provenance.

The scene now owns reusable RML templates, edited with **Scene > UI Templates…**.
Nineteen native UI nodes and click/change/submit event entry points are registered,
lowered into typed IR and emitted as shared native calls. All four runtime entry
points prepare and update UI, dispatch queued events under the instruction budget,
and share the same widget functions. The builtin count is **352**.

`tools/verify_ui_workflow.py --desktop` passes **29 checks**, process exit 0.
`artifacts/validation/ui-workflow-checks.json` records the current native source
fingerprint, relocated package and GPU SHA-256 values. The actual Qt dialog edits
the template; Undo/Redo, template selection in Create Widget, save/reopen and
the embedded SDL viewport pass. Real Windows mouse/keyboard actions click Add
point, replace Player with `Đỗ Việt` using Ctrl+A/text entry, and press Enter.
The native snapshot confirms score 1, robot rotation 30 degrees, the player name
and greeting, with no gameplay movement or world-click input leakage.

That desktop run exposed a keyboard chord bug in the upstream SDL adapter: it
read current global modifier state after SDL could already have pumped key-up.
The shared session now translates the modifier flags stored on each key event.
Ctrl+A selection and Unicode input then worked in the embedded game; two native
GPU regression checks retain the queued-chord case. A probe setup was also
corrected to provide real button coordinates and explicitly position the caret
before asserting appended text.

Pause preserves the game/UI snapshot. Missing-image and outside-assets template
loads return errors while retaining the existing process and scene. Stop clears
document instances and Play recreates their defaults. **Build Game** succeeds
with **1,148 GUI heartbeat ticks**, stages assets/fonts/shaders/licenses and SDL
DLLs, and the test then moves the source project away. Headless interpreter,
headless compiled game, GPU Preview and GPU compiled game all run from the
Vietnamese-named package with a Windows-only PATH. At both four and ten frames,
complete snapshots match and the two GPU BMP files are byte-identical. The
checkpoints prove button disable/re-enable, checkbox, slider, progress and
Unicode submit behavior. `ui-editor.png` and `ui-compiled.png` retain captures;
the exported HUD/robot image was visually inspected.

Focused Python/core tests pass **29 tests**. UI lifetime/fault tests plus the build
stamp tests pass **9 tests**: destroying/recreating, hiding/showing or disabling a
control cancels remaining listeners; UI callbacks obey the instruction budget;
invalid value/container-text/size operations report their originating graph node.
CMake dependency changes invalidate the native build stamp.

This completes basic HUD integration, not all of category 18 or the full engine.
Visual layout authoring, remaining control/layout nodes, bindings, navigation,
UI animation/drag/drop, IME composition, accessibility, localization, HDR and
platform coverage remain open. The desktop entry check proves committed Unicode
text and keyboard handling, not a physical Vietnamese IME composition session.

The subsequent broader regression selection completed with **364 passed,
1 skipped, 86 warnings in 867.10 seconds** (`ui-regression.log`). It covered the
editor/core/UI and presentation modules, while excluding the repeated native
fixture suites listed in the original command. A handled Windows COM diagnostic
was printed during a Qt dialog test; the process continued and exited successfully.
This result predates the persistence changes below.

## Versioned progress-data persistence — 2026-10-26

Fifteen category 23 nodes now share the native runtime: Open Save Storage,
Create/Delete/List/Exists slots, single/batch Save/Load Variable, Save/Load JSON,
Get Save Version, Validate Save Data, and operation status/error queries. Storage
is isolated by a stable Game ID in SDL's user preference directory; a CLI save-root
override isolates tests. Typed envelopes, bounded parsing, an interprocess lock,
flushed temporary files and atomic replacement preserve the previous file on
handled write failures. Batch loads validate everything before replacing variables.

`persistence-tests.log` records **29 passed in 17.93 seconds**: 20 persistence
integration cases plus seven UI lifetime/fault and two runtime-build checks.
The persistence cases run real native Preview processes and exercise all 18
value forms, Unicode, int64 limits, transactional failures, corrupt/future files,
slot/JSON lifecycle, namespace/path boundaries, readonly replacement failure,
temporary cleanup and a competing process's exclusive lock.

`persistence-workflow-checks.json` records **47 passing checks**, `desktop=true`
and the native source fingerprint. Actual Qt Inspector Game ID edits, Undo/Redo
and save/reopen succeed. Real desktop Add/Save clicks persist score 1 and rotation
30 degrees; Stop/Play restores both. The fixture uses a unique Game ID, keeping
the ordinary demo's progress separate.

The packaged robot then runs as headless Preview, headless compiled game,
GPU Preview and GPU compiled game with a Windows-only PATH. All four save score
2, name `Player Việt` and rotation 60 degrees. After the package moves to a
Vietnamese-named directory, all four restore the same values on process restart.
After another change, the in-game Load button restores them again. All complete
state snapshots and saved file bytes agree; GPU BMP files match byte-for-byte at
save, restart and manual-load checkpoints. Both loading paths leave the stored
file unchanged. `persistence-restored.png` was visually inspected.

This delivers explicit saved progress, not a complete world/runtime checkpoint.
Full Save/Load Game, entity state restoration, timer/event restoration at a safe
frame boundary, autosave/results events, preferences/binary storage and migration
remain open. Cross-platform and power-loss durability need their own evidence.

## Native timer/event checkpoints — 2026-10-26

The internal `EventCheckpoint`/`RestoreEventCheckpoint` API preserves the logical
clock and deadlines at native long-double precision, timer insertion order,
paused/suspended state, custom-event subscription/cancellation/activity epochs,
typed payloads and the complete queue. Callbacks come from matching bindings in
the current executable. Reentrant checkpoint/restore is rejected during dispatch.
Staging validates before replacement and releases all temporary Flecs observers
and event identities on failure.

`tools/verify_event_checkpoint.py` builds the optional native acceptance probe
and passes **45 checks**, recorded in `event-checkpoint-checks.json` with source
and binary hashes. A distinct-world roundtrip continues for **160 frames** with
fractional deltas, pause/resume, activity/subscription toggles and repeating
timers; every checkpoint and callback log matches uninterrupted execution.
A separate writer exits before a reader process reconstructs callbacks and
reproduces the same trace. All 18 typed payload forms, Unicode, embedded NUL,
signed integer limits and a destroyed sender survive. Canceled envelopes remain
canceled, listener order/FIFO remain stable, and restored work retains its graph
node for budget errors. Reading leaves the saved bytes unchanged.

Thirty-two malformed-record cases preserve the target event-system pointer,
snapshot and live Flecs entity count. Repeated in-place restores do not accumulate
live native entities. Callback errors release the boundary guards, and a deleted
prefab child can be recreated with the same ID and receive timer/custom callbacks
again through its restored dormant bindings.

The targeted regression run passes **80 tests in 650.44 seconds**, exit 0
(`event-checkpoint-regression.log` and `.xml`). It covers timer semantics, typed
events, entity activity, progress-data persistence and build-stamp validation.
Timer/event/activity cases compile and run the real interpreter and generated
C++ game; this is not a Python simulation of those systems.

This verifies an internal subsystem on Windows. Full Save/Load Game nodes,
world/input/audio/UI restoration and host frame-boundary commit remain open.
The checkpoint probe does not claim editor/GPU integration or cross-platform
checkpoint compatibility, and the builtin node count remains 367.

## Scene/input/audio checkpoint continuation

`tools/verify_state_checkpoint.py` now passes **81 native checks** against the current
runtime. A writer saves at six different points and exits; a fresh process
restores all six and reproduces **389 continuation frames**. Scene snapshots,
prefab inheritance, component overrides/references, entity creation IDs, camera,
typed variables, keyboard/mouse edges, timer/event state and sound state match
the uninterrupted reference. A deleted mesh carrier leaves its mesh available
for later spawning. Reset recreates a deleted prefab child at the same ID.

All six WAV captures have equal SHA-256 hashes and equal bytes, including
22.05/44.1/48/96 kHz WAV and MP3 source playback, fractional sample clocks,
looping, pause/resume, natural EOF, explicit Stop, voice replacement and volume
changes. Decoder reconstruction happens in a separate mixer and emits no replay
audio to the device. Fifty-five malformed-record cases preserve the current
input, world or audio pointer/state, including a decoder-position mismatch that
fails after staging. Repeated successful audio restoration and playback after
checkpoint-recording exhaustion are also exercised. The original 62-check suite
did not cover a resampling failure caused by different replay chunk sizes; the
version-2 journal correction and combined test below supersede that approach.

Evidence: `state-checkpoint-checks.json`, with native/probe/binary hashes and six
PCM hashes; the corresponding files are in `state-checkpoint/`. The native build
was rebuilt and its recorded source fingerprint matches current runtime sources.
The targeted input/audio/scene/build regression suite passes **41 tests**, zero
skipped/failing, in **152.33 seconds** (`state-checkpoint-regression.log` / `.xml`).
The existing native event probe was rebuilt and still passes **45 checks**.

This is internal checkpoint groundwork on Windows. The public registry remains
367 nodes. Full Save/Load Game still needs remaining transient UI state semantics,
program/file compatibility, wiring in both hosts, and editor/export integration
checks. Audio reconstruction replays a bounded journal, but long-running playback
still needs a practical latency bound. Ogg/FLAC continuation remains unverified.

## UI checkpoint continuation — 2026-10-26

`tools/verify_ui_checkpoint.py` passes **105 checks**. A writer process saves
three checkpoints and exits. A reader process resolves its own templates and
callbacks, reproduces the saved UI fields and follows **21 continuation frames
per mode** in headless and GPU runs. The two modes produce identical state and
event traces. Six GPU BMP reference/restored pairs have identical bytes: all
three checkpoints immediately after restoration and after later interactions.
The cut-6 restored PNG was visually inspected for edited Unicode text, caret,
scrolling, slider, progress and disabled controls.

Coverage includes edited literal text, style declaration precedence, control
values and enablement, document stacking/visibility, document focus history,
selection ranges, scroll positions, hover, stale/live queued event generations,
destroy/recreate, no-template scenes and reentrant-call rejection. Malformed
records preserve the original UI and its subsequent input/callback behavior.
Unsigned counters near their maximum roundtrip; exhaustion rejects document
creation/hiding before mutation. Checkpoint errors do not dump saved UI values.

The small RmlUi focus-history adapter is now reproducible through CMake. A test
applies it to the exact clean pinned header, checks byte identity/idempotence,
and verifies an unknown header fails without being overwritten. Text controls
invalidate layout on value changes to keep multiline caret geometry current in
headless execution. The existing dependency probe was rebuilt and passes **103
checks** from an isolated package with clean PATH, in headless, SDR and
SDR_LINEAR modes. Authoring/native UI/build-stamp regressions pass **20 tests**.

Evidence: `ui-checkpoint-checks.json` (native/probe/binary hashes, all checks,
six image pairs), `ui-checkpoint/` (saved data, traces and captures),
`ui-checkpoint-regression.log` / `.xml`, `ui-checkpoint-runtime-build.log` and
`ui-dependency-checks.json`. The public node count remains 367.

This is subsystem evidence, not full-game Save/Load acceptance. Pointer buttons
must be released and select menus closed. Selection direction, preferred caret
column/blink, double-click history, IME, gestures and CSS animation/transition
progress are not captured. The combined transaction below adds device/input/capture
handoff; host-loop/GPU integration, program/resource compatibility and bounded
audio restore latency remain open; see [persistence.md](persistence.md#native-ui-checkpoints).

## Combined game checkpoint and audio replay correction — 2026-10-26

The shared native API stages scene/identity, input, events/timers, sound, UI and
game clock into an independent context. It rejects graph/callback reentrancy and
program-identity mismatches, validates exact recapture, and commits only after
preparation. Interpreter and generated graph entry points track execution depth.
Host logs, storage settings/status and instruction budget are retained. UI cursor
and keyboard requests remain inactive during staging; after commit, only the new
UI controls the window. Audio output/capture ownership moves without reopening,
and queued PCM from the previous game state is discarded.

The combined test exposed a flaw in the previous audio checkpoint: replaying
4,000 mixed samples as 2,048 + 1,952 differed from the original five 800-sample
requests at 44.1 kHz. Playback position was one source frame behind and subsequent
PCM differed. Audio checkpoint version 2 records playback controls and exact
request sizes, with run-length compression. It rebuilds the entire mixer in
chronological order, including paused tracks' buffered data and replaced voices.
Version 1 is rejected. Replay records are bounded and validated before execution;
recording exhaustion disables checkpoints without interrupting playback. The
limits and remaining latency constraint are documented in [audio.md](audio.md).

`tools/verify_game_checkpoint.py` passes **46 checks** with the dummy driver and
again with **WASAPI** (`--audio-driver wasapi`). Each run saves at six cuts,
terminates the writer, and matches **132 continuation frames** in a fresh reader.
All seven reference/restored WAV pairs match bytes and SHA-256, including a
capture file continued across context replacement. The tests cover fractional,
variable and zero timesteps, input edges, destroyed entities, timers/events/UI,
voice replacement, looping, gain/mute, pause/resume and empty scenes. Ten damaged
records preserve live subsystem pointers/state, the active output stream and
keyboard input, including late UI failure after audio reconstruction. Abandoned
candidates and repeated commits are verified, as are both directions of text
keyboard activation. WASAPI status reports a connected, unpaused stream with
queued PCM; this does not certify acoustic quality.

Evidence: `game-checkpoint-checks.json`, `game-checkpoint-device-checks.json`, and
the matching directories containing saved records and WAVs. Reports contain the
current native fingerprint, probe-source hash and executable hash. The root
runtime was rebuilt (`game-checkpoint-runtime-build.log`) and its stamp is current.
The state and UI probes were rerun against that fingerprint: **81 state checks**,
**105 UI checkpoint checks** and **103 packaged UI dependency checks** pass.
The audio/UI/function/progress-persistence/build regression suite passes **82
tests in 323.32 seconds**, with no failures or skips and two existing NodeGraphQt
deprecation warnings (`game-checkpoint-regression.log` / `.xml`).

This validates an internal transaction, not public Save/Load Game acceptance.
The probe supplies a fixture identity; production IR/resource fingerprinting,
GPU resource preparation/commit, host-loop and slot integration, remaining UI
transient semantics and practical audio-load latency are still open. The registry
remains at 367 definitions, and the full-engine goal remains incomplete.

## Public whole-game save/load — 2026-10-27

Three public nodes bring the registry to **370 definitions**: Save Game, Load
Game and Game Save Pending. Requests return Accepted and run after the current
graph/frame boundary. Both native hosts share program/resource identification,
version-2 slot storage and independent staging/commit. Existing progress records
survive the slot upgrade. GPU loads validate and reuse the prepared asset catalog;
audio output/capture and window text input transfer with the context. Build Game
now removes stale files from its generated asset copy.

The initial four-path test exposed two distinct issues. Monitor UI density is
legitimate host state (1.25 here versus the headless default 1.0); all remaining
save fields match and cross-density loads pass. An actually unfocused RmlUi
context failed exact restoration because its root has no owner document and
public Focus() cannot focus it. The pinned adapter now dispatches the normal
blur transition and clears the root focus chain. The old focus-history adapter
upgrades reproducibly; clean, repeated and unknown-header checks pass. A real
game-camera entity is used for GPU continuation comparisons; editor orbit and
initial auto-framing are host state, not game checkpoint state.

Evidence verified against native fingerprint
`22ac69a995589195649f1d7675f989bb801e4c2fd6e8a3ff26a5087be7431b20`:

- **68 checks** in `game-save-checks.json`: four interpreted/generated,
  headless/GPU paths, separate processes, Unicode package relocation, startup
  and UI-callback loads, unchanged slot files, equal continuation PCM and
  byte-identical game-camera GPU captures. Source resource SHA-256 matches
  Python hashlib; packaged PicoSHA2 license is present.
- **14 checks** in `game-save-editor-checks.json`: Inspector/Undo/Redo/reopen,
  responsive Qt Build Game, stale asset removal and current native stamp.
  Windows-MCP clicked actual embedded Save and Load buttons. The simulation
  rewound successfully; the standalone editor-built game then loaded the same
  Preview slot at saved frame **3296**, with exact variables and unchanged bytes.
- **14 native request/slot checks** in `game-save-probe-checks.json`: deferred
  state capture, duplicate request rejection, version-1 upgrade/coexistence,
  host-preparation rollback, catalog mismatch, cancellation, storage changes,
  invalid slots, changed assets and retry after resources are restored.
- **83 regression tests** passed in **195.25 seconds**, without failures/skips,
  with two existing NodeGraphQt deprecation warnings. They cover core lowering,
  audio authoring/native paths, UI documents, existing progress persistence,
  malformed whole-game loads, binary/Unicode resource hashes, runtime stamps,
  pinned-header upgrades and asset staging. Reports: `game-save-regression.log`
  and `.xml`.
- Existing UI checkpoint verification still passes **105 checks**. The combined
  probe now passes **48 checks** with both dummy and WASAPI audio, including the
  new unfocused-UI case, **132 continuation frames** and seven equal PCM pairs.
  Reports: `ui-checkpoint-checks.json`, `game-checkpoint-checks.json`,
  `game-checkpoint-device-checks.json`.

The playable example is `examples/game_save_demo/project.json`; see
`game-save-editor.png` and the `game-save/` native artifacts. These are bounded
Save/Load results. Audio restoration cost grows with journal length; unsupported
UI transient state, completion/failure events, autosave and schema migration
remain open. The overall engine goal is still active and incomplete.

## Save/load result events — 2026-10-27

Four category-23 handlers (23101–23104) now report completed or failed Save Game
and Load Game requests. The registry contains 374 builtin definitions. Result
handlers use the existing Flecs queue, scoped Slot/Error payloads, stable listener
ordering and the shared instruction budget. Only accepted, processed requests
emit results. Hosts dispatch after processing and clearing old input on load;
requests made by a handler wait for the next boundary. Callback faults remain
graph errors after the I/O operation has finished.

Verified native fingerprint:
`4b8c8c9c1c23c71dd9aead0666f7d1c51136b214007bde4d599a03067805d9fe`.

- `save-events-checks.json`: **82 checks** passed. Eight scenarios run in all
  four headless/windowed interpreted/generated hosts from a standalone Unicode
  directory: save, startup load, repeated manual load, invalid save, missing load,
  retry after failure, UI-button request and malformed subscription rollback.
  State matches across all hosts; all eight GPU pairs are byte-identical. The
  visible failed-load screenshot was also inspected: the robot keeps rendering
  and the HUD displays the error legibly.
- `save-events-regression.xml`: **64 passed**, two existing NodeGraphQt
  deprecation warnings, 45.46 seconds. Includes graph/compiler validation,
  persistence corruption/rollback, resource hashes, native freshness, asset
  staging, UI event lifetimes and actual Qt event-port connection/Undo/Redo/
  disk-reopen checks.
- `save-events-tests.xml`: eleven result-handler tests passed initially. The
  chain test had assumed an undeclared score existed in the saved scene; its
  fixture now declares score before saving. The corrected test passed separately
  (`save-events-chain-tests.xml`, 148.18 seconds). All **12 cases** have passing
  coverage, including native interpreter/generated parity, output scoping,
  rejection without notification, shared-budget faults, stable ordering,
  custom-event coexistence and Save → deferred Load without repeated OnStart.
- The existing save workflow still passes **68 checks**, including state,
  cross-process files, PCM and GPU parity (`game-save-checks.json`). The event
  checkpoint probe still passes **45 checks** and **160 continuation frames**
  (`event-checkpoint-checks.json`).

The example is `examples/game_save_events_demo/project.json`; root generated game
binaries currently target this example. The original save-workflow verification
ran before switching that generated target; rebuild its example before rerunning
its verifier. Editor Build Game and WASAPI handoff were verified at the preceding
milestone and were not repeated for this event-only change. Autosave, migration,
practical audio restoration latency and the broader engine roadmap remain open.
Runtime identity changed, so checkpoints from the previous runtime are rejected
without overwriting their files.

## Jolt native physics foundation — 2026-10-27

The shared build now includes Jolt Physics 5.6.0 and the independent
`rt::PhysicsWorld` module. It provides static/dynamic/kinematic box, sphere and
capsule bodies, forces/impulses, material response, collision filters, sensors,
ray/overlap queries and per-step contact events. No physics nodes have been added
to the registry yet; the builtin count remains 374. See [physics.md](physics.md)
for the API boundary and remaining integration requirements.

Verified against runtime fingerprint
`83296848cc3547fcdb4f1db53e8e24166d6b974d88e550eb35c4865cb5577329`:

- `physics-checks.json`: **91 checks** using real native simulation. Includes
  ground contact for three primitives, mass/force/torque, gravity/damping,
  friction/bounce, CCD against a thin wall, masks/layer 31, sensor queries,
  motion transitions, sleeping supports, disable/reenable, removal/recreation,
  validation before mutations and the 4096-body limit/reuse.
- `physics-asserts-checks.json`: the same **91 checks** with Jolt's internal
  assertions enabled in a separate optimized build. Compiler definitions were
  inspected to confirm the assertion and deterministic/double-precision options.
- All body poses **and contact payloads** match exactly across **240 frames**
  in independent worlds and independent processes. Release and assertion-build
  traces also match, SHA-256
  `e22849ded33d5cadb14cd6875f1303f7f409eda2d61bdc7bbeca0a1bff635f78`.
  This is Windows/Clang evidence; it does not establish other-platform parity.
- `physics-dependency-tests.xml`: **4 passed**, including a clean extraction of
  the real hash-checked archive, preservation of an existing install, rejection
  of a changed archive, path traversal and symlinks. The built license matches
  the pinned upstream license byte for byte.
- `physics-python-regression.xml`: **22 passed** for compiler/registry/export
  and runtime build identity. Dependency provenance files now participate in the
  Python build fingerprint. The checkpoint identity definition is attached only
  to its consuming C++ source; inspection of Ninja confirms one occurrence,
  so identity updates no longer invalidate every runtime translation unit.
- `physics-runtime-build.log`: all four native hosts rebuilt successfully;
  the root Preview binary matches the current source/binary stamp.
- `save-events-checks.json`: **82 current checks** after rebuilding, with
  relocated interpreted/generated headless and SDL hosts, state parity, repeated
  Save/Load, error/retry/rollback and equal GPU images for all eight scenarios.

Testing exposed and fixed sleeping bodies floating after support removal. Nearby
bodies now wake on relevant support edits. The module also preserves sleeping
contacts through precise shape queries, so sleeping does not itself emit a false
Exit; teleporting a sleeping body away emits exactly one Exit. Disabling bodies
preserves their velocities, and same-ID replacement keeps separate old/new
contacts with Exit before Enter.

At this foundation milestone, physics scene/prefab authoring, graph nodes, shared
host stepping, physics-aware Save/Load and a playable four-path physics example
remained unimplemented. The checkpoint integration below supersedes that part of
the limitation; graph/editor/host integration remains open.

## Physics checkpoint and game transaction — 2026-10-27

Physics checkpoints now preserve body topology/configuration, native ID allocation
and reuse, enabled/active order, pending forces, velocities, sleep/contact state,
ignored pairs and contact events. The pinned Jolt binary record is preflighted
before restoration, and a separate candidate must recapture exactly before it
replaces the live world. Game checkpoint version 2 includes optional native
physics in the existing independent stage/commit transaction. Legacy checkpoint
envelopes remain usable for independent progress-data writes and replacement by
a fresh Save Game; they are rejected for loading.

Verified runtime fingerprint:
`246b60cf18efe136f98e9a1aa19cb4772c90d164581a8afc21cbd0916cd26537`.

- `physics-checks.json` and `physics-asserts-checks.json`: **154 checks each**.
  Eight saved worlds reproduce **880 continuation frames** in independent worlds
  and a fresh process. Scenarios cover forces, disabled bodies, resting stacks,
  changed materials/mass, removed supports, wrapped body generations, CCD and
  kinematic targets. Twenty-five malformed records leave the live world exact.
  The ordinary simulation trace still matches all **240 frames** across processes.
- Release and assertion-enabled builds produce identical trace and checkpoint
  fixture bytes. The checkpoint fixture SHA-256 is
  `e88c25c661cc777ef600fbdb876f09598da5e8cf069aadbb01d6293e98ec42ac`;
  the ordinary trace hash remains the one recorded above.
- `game-checkpoint-checks.json` and `game-checkpoint-device-checks.json`:
  **67 checks each**, **132 continuation frames**, and seven exact WAV pairs,
  with SDL dummy and actual WASAPI output respectively. The record includes
  physics state at every comparison. Failure cases preserve all live subsystem
  pointers, sound output and text input; deferred saves/loads and legacy envelope
  replacement preserve independent progress records.
- `save-events-checks.json`: **82 checks** after the runtime rebuild, across
  relocated interpreted/generated headless and SDL hosts. All eight scenario
  pairs have identical GPU images, with matching state and result events.
  This demo has no authored physics; its role is regression coverage for the
  existing Save/Load graph flow.
- `physics-python-regression.xml`: **26 passed**, covering the registry/compiler,
  runtime identity and dependency installer. `physics-persistence-regression.xml`:
  **32 passed**, covering progress slots and real native whole-game Save/Load.
- `physics-runtime-build.log`: all four native hosts rebuilt successfully.
  The Preview build stamp and all five native report fingerprints match the
  current sources. Existing `std::filesystem::u8path` deprecation warnings remain.

At that checkpoint milestone, physics was exposed through the native API only: scene/Inspector/prefab
authoring, registry nodes, shared fixed-step host integration, transform
synchronization and a playable physics example remain to be implemented and
verified. The graph/host milestone below supersedes part of that limitation.
These checks do not certify cross-platform determinism. The full
Node_Engine goal remains active.

## Physics graph, fixed-step hosts and Blockbench playground — 2026-10-27

Thirty physics nodes and On Fixed Update bring the builtin registry to **405**.
Both native hosts run the same 60 Hz scene bridge, synchronize entity hierarchy,
scale, layer and inherited activity, and copy/remove bodies with entity lifecycle.
Game checkpoints now preserve scene bindings and fractional fixed-step time with
the native Jolt state. The playable example uses the existing Blockbench robot,
a static floor, force/impulse input and Save/Load.

Verified runtime fingerprint:
`d019baf39ed86ef26bbc5aee9e08c7580e3e3ee8590fb32e6914208020ab4928`.

- `physics-scene-checks.json`: **63 checks**, running relocated headless Preview,
  generated headless game, graphical Preview and generated graphical game. The
  graph creates and advances both bodies; Save/Load in a fresh process matches
  uninterrupted future state exactly. Separate 5 ms frames preserve fractional
  step remainders. Invalid bindings reject the checkpoint without changing the
  live game. State and GPU bytes match interpreted/generated execution.
- `physics-editor-checks.json`: **25 checks** through actual Qt and embedded SDL.
  Create/connect fixed-update and force nodes; Undo/Redo, validate/save/reopen;
  Play/Pause/Stop/restart; click to focus the native viewport and apply force with
  the physical D key. The verifier now confirms the actual focused HWND instead
  of relying on cross-thread SetFocus. `physics-editor.png` records the real UI.
  The demo HUD now sets its document size explicitly, so percentage-based layout
  fits the editor viewport; it ignores pointer input as a display-only overlay.
- `physics-scene-tests.xml`: **12 passed** in **287.81 seconds**, with no failures
  or skips: eight native graph cases plus four dependency cases. The graph tests
  compare interpreted/generated programs at 30/60/120 FPS, transformed-parent
  motion, scaled colliders, layer filtering, activity, clone/removal, and rejected
  invalid dimensions/scale. All three frame rates produce the same one-second
  state and 60 fixed ticks. A clean Jolt build exceeded the former 180-second
  fixture timeout; the native fixture allows 600 seconds, and this full rerun
  supersedes the earlier partial failure log.
- `physics-graph-regression.xml`: **49 passed** for core/compiler/runtime-build
  and editor behavior. Existing NodeGraphQt warnings remain. Windows also emits
  a `0x8001010d` faulthandler diagnostic during the function-input dialog test;
  pytest completes with all cases passing and exit code zero. This diagnostic
  is not proof of a clean Windows COM lifecycle and remains to investigate.
- `physics-checks.json` and `physics-asserts-checks.json`: **154 checks each** on
  this runtime revision, 240 ordinary trace frames and 880 checkpoint continuation
  frames. Release and assertions-enabled trace/checkpoint fixture bytes match.
- `game-checkpoint-device-checks.json`: **67 checks**, 132 continuation frames
  and seven equal PCM pairs using actual WASAPI. The separate dummy-driver
  report is from the previous checkpoint revision; it was not rerun here.
- `save-events-checks.json`: **82 checks** rerun against this runtime, retaining
  four-host state/GPU equivalence and result-handler behavior for the existing
  Save/Load example. `physics-demo-build.log` records the final demo build.

The current Preview build stamp and the six current native reports above match
the source fingerprint. Screenshots were inspected for the rendered robot/floor
and readable HUD. These results do not complete physics Inspector/prefab collider
authoring, collision/trigger graph handlers, hit point/normal outputs, general
shape casts, character controllers, mesh colliders, constraints or animation.
Old saves with a different runtime/program identity remain incompatible; there
is no migration. Windows is the verified platform. The full goal remains active.

## Collision/trigger graph handlers — 2026-10-27

Six Enter/Stay/Exit nodes now deliver collision and trigger contacts to global or
entity-scoped graph handlers, bringing the registry to **411**. The shared scene
step synchronizes poses before routing a stable contact batch through the Flecs
event queue. Scoped handlers receive Entity/Other, world Point and an oriented
Normal. Receiver destruction/activity cancels delivery, custom events use the
same queue, and callback work shares the frame budget. Empty worlds continue
stepping so the last removed contact can emit Exit.

The new Blockbench example is `examples/physics_events_demo/project.json`.
It displays collision/trigger status and saves a separate `first-contact` slot
from Collision Enter. C loads that slot; S/L retain the regular manual slot.
See [physics.md](physics.md) for receiver, ordering and snapshot semantics.

Verified runtime fingerprint:
`1eca8a9a5aa7fe26ce87637fb1a0398c91d578aef95fd75a91d0f6e5b44b43ab`.

- `physics-events-checks.json`: **91 checks** from
  `tools/verify_physics_scene.py --events`. The relocated example runs through
  interpreted/generated headless and graphical hosts with identical state/GPU
  bytes. The workflow observes collision and trigger handlers, resumes regular
  and fractional-step saves, then resumes the separate collision-triggered slot
  through its actual Load Game node. The latter reproduces the uninterrupted
  future with no repeated Enter. A physics subscription changed to disabled is
  rejected before commit; corrupted body bindings still preserve the live game.
- `physics-events-editor-checks.json`: **26 checks** from
  `tools/verify_physics_editor.py --events`. Actual Qt graph authoring connects a
  trigger handler, validates, saves and reopens it, and verifies Undo/Redo. The
  embedded SDL Preview emits collision/trigger events, freezes on Pause, moves
  under the physical D key after a real focus click, and rebuilds its three
  colliders on Stop/Play. `physics-events-editor.png` shows the HUD and robot.
- `physics-events-core-regression.xml`: **22 passed** for registry/compiler,
  generated adapters and runtime build identity. The four existing persistence
  event scope/codegen cases also pass in `physics-events-compiler-regression.xml`.
- `game-checkpoint-device-checks.json`: **67 checks**, **132 continuation frames**
  and seven equal PCM pairs, rerun with WASAPI after the event-system changes.
- `save-events-checks.json`: **82 checks** rerun for existing save-result handlers,
  including relocated four-path state/GPU equivalence and corrupted subscription
  rollback. These checks ran at the stated source fingerprint; shared report
  filenames can be superseded by the later milestones below.

The earlier native Jolt-only and ordinary physics scene reports describe the
previous runtime revision; they were not rerun for this event-dispatch change.
Dedicated Inspector/prefab collider authoring, fuller raycast outputs, shape
casts, controllers, mesh colliders, constraints and animation remain open. The
full Node_Engine goal remains active.

## Scene and prefab collider authoring — 2026-10-27

`rigid_body` initial settings now belong to scene entities and inherited Flecs
prefab components. The entity Inspector exposes Add/Edit/Remove for primitive
colliders and validates settings and scaled dimensions before accepting edits.
Undo/Redo, prefab ownership, runtime Instantiate/Apply/Reset/Clone, fresh scene
load and checkpoint restoration preserve these settings. Runtime mass/velocity
and contact state remain separate from initial authored settings.

Physics-related prefab operations stage the final scene and a cloned native
world before modifying live handles or event/timer ownership. A regression found
that Apply's staging scene needed initialized audio/UI metadata for Snapshot;
the shared scene loader now supplies all subsystems. Invalid operations are
checked for their actual validation error, as well as unchanged scene/physics.

Current runtime fingerprint:
`e7f336d89df3b9bda166b55eec334de839899ddda2062b3e55d3aa75365d7b19`.

- `physics-authoring-checks.json`: **95 checks** from
  `tools/verify_physics_scene.py --authoring`, through relocated interpreted and
  generated headless/graphical hosts. Authored colliders, prefab metadata, real
  contact handlers, regular/contact/fractional-step saves and failed-load rollback
  preserve exact state and GPU pixels across fresh processes.
- `physics-authoring-editor-checks.json`: **35 checks** from
  `tools/verify_physics_editor.py --authoring`. Real Qt clicks exercise the
  Inspector dialog, invalid input, Add/Remove, inherited ownership, Undo/Redo,
  save/reopen, embedded simulation, physical keyboard force, Pause and Stop/Play.
  Screenshots: `physics-authoring-dialog.png`, `physics-authoring-editor.png`.
- `physics-authoring-transactions.json`: **7 native checks** using
  `build/node_game_checkpoint_probe.exe --physics-authoring examples/physics_authoring_demo`.
  Invalid Instantiate/Reset/Apply preserve ID allocation, native bodies and timers;
  missing runtime bodies stay removed on checkpoint restore, Reset preserves
  unrelated velocity, and Reset is valid inside a collision callback.
- `game-checkpoint-device-checks.json`: **67 checks**, **132 continuation frames**,
  seven identical PCM pairs, rerun with WASAPI after the scene-loading fix.
- `collider-authoring-core.xml`: **95 passed** for existing core compiler,
  prefab authoring/ownership and runtime build identity checks.
- `collider-authoring-native.xml`: **32 passed in 401.43 seconds**, comprising
  19 authoring cases and all 13 contact-event regressions. Native interpreted
  and generated programs cover the three shapes, body availability at Game Start,
  prefab spawn/reset/clone/apply, invalid parent scale, contact payload scope,
  receiver lifetime, custom event ordering and budget failures.

The example is `examples/physics_authoring_demo/project.json`. Collider wireframe
gizmos, offset/compound shapes, richer query outputs/casts, controllers, animation,
large-world performance and Linux acceptance remain incomplete. The older
ordinary physics and save-result-event reports cover their recorded revisions;
they are not freshly rerun by this milestone. The full goal remains active.

## Raycast results and primitive shape queries — 2026-10-27

Four graph nodes, **Physics Raycast**, **Physics Sphere Cast**, **Physics Box
Cast** and **Physics Capsule Cast**, expose Hit, Entity, Point, Normal, Fraction
and Distance from one native query. Shared action-result handling now supports
multiple typed outputs in the interpreter, generated adapters and generated
gameplay, including inside action functions. Existing scalar action results and
Physics Raycast Entity remain supported. The builtin registry contains 415 nodes.

Runtime fingerprint:
`f8bbb6aa1269cee454ac1dd0e92d7bfd84e5516c81f770990088428ebc714110`.

- `physics-query-native-checks.json`: **173 checks**, 240 deterministic trace
  frames and 880 fresh-process checkpoint continuation frames. New checks cover
  all three cast shapes, box/capsule orientation, initial overlap, stationary
  shapes, sensors, layer 31, exclusion, disabled targets, far-origin contact
  precision and invalid input. Queries leave bodies, contacts and checkpoint
  bytes unchanged. Existing physics trajectories and checkpoint scenarios pass.
- `physics-queries-tests.xml`: **15 passed in 234.82 seconds**. Both native
  execution paths return the six expected values, preserve captured results
  after body removal, return fresh miss outputs, track live filter/activity
  changes, reject invalid parameters with originating-node diagnostics and
  return the tuple through an action function. Compiler checks reject result
  reads from an unrelated handler and generate exactly one native call.
- `physics-queries-core.xml`: **22 passed** for existing registry/compiler,
  deterministic export and runtime build identity cases.
- `physics-queries-checks.json`: **111 checks** through relocated headless and
  graphical interpreted/generated hosts. Each probe reports an analytically
  correct floor contact, outward normal, fraction and distance and updates its
  HUD row. Regular, contact-triggered and fractional-step checkpoint continuations
  reproduce full state and GPU bytes; corrupted bindings/subscriptions fail
  before changing the running game.
- `physics-queries-editor-checks.json`: **40 checks** through the actual Qt
  editor and embedded SDL game. The editor creates and wires all six query
  outputs, supports Undo/Redo and save/reopen, executes their typed values,
  displays all four live probes, moves the robot with a physical D key, pauses
  exactly and restores initial colliders on Stop/Play. The screenshot is
  `physics-queries-editor.png`; the actual keyboard run advances 24 physics ticks
  and moves the robot about 0.476 metres along X.

The playable example is `examples/physics_queries_demo/project.json`, created by
`tools/create_physics_queries_demo.py`. The native build succeeds against that
project. `physics-queries-summary.json` records report/source hashes and current
build identity. The editor screenshot was visually inspected: robot, floor and
four live distance readouts are visible.

All tests above cover this Windows host. Queries translate a fixed orientation;
they do not implement rotational sweeps or character sliding/grounding. Collider
gizmos, box/capsule all-hits overlaps, controllers, mesh colliders, constraints,
animation and the wider acceptance audit remain open. The complete engine goal
remains active.

## Oriented overlap arrays and Python authoring validation — 2026-10-27

**Physics Overlap Box** and **Physics Overlap Capsule** join the existing sphere
query, bringing the builtin count to 417. Queries use oriented narrow-phase
geometry and return sorted unique entity arrays. All three overlap forms and
primitive casts share validated native query-shape construction. Queries create
no body and observe current scene transforms, activity, layers and body settings.

Runtime fingerprint:
`a2bc1b1a972746eacaefc921d941bc9a3c6837d2ff36480b75f821171ac1211d`.

- `physics-overlap-native-checks.json`: **196 checks**, 240 deterministic frames
  and 880 fresh-process checkpoint continuation frames. New cases cover rotated
  box/capsule geometry, rejection of bounding-box corner false positives,
  deterministic result order, trigger/layer/exclusion policies, empty results,
  disabled/removed bodies, far-origin precision, invalid parameters and unchanged
  checkpoint bytes. The existing ray, cast, sphere-overlap, motion and checkpoint
  scenarios pass against the same source fingerprint.
- `physics-overlap-tests.xml`: **11 passed in 241.23 seconds** through native
  interpreted/generated graphs. A captured array feeds For Each while the graph
  destroys its targets; a later query is empty and the captured value remains
  intact. Further cases cover parent movement/activity, body enabling, layer 31,
  cloning/exclusion and invalid input in an otherwise empty world. The original
  sphere node participates in the array/destruction regression.
- `physics-overlaps-checks.json`: **137 checks** through relocated interpreted
  and generated headless/graphical hosts. Three controlled scenarios observe
  the initial region contents, movement outside both volumes and reset/fall back
  into them. The box includes the center trigger; the horizontal capsule omits
  it. Exact entity arrays and HUD counts match in all four hosts. Existing
  regular/contact/fractional-step saves resume identically; malformed loads
  preserve the game. Full state and GPU bytes match across paths.
- `physics-overlaps-editor-checks.json`: **41 checks** in the actual Qt editor
  and embedded SDL Preview. Both new array outputs connect to typed variables,
  survive Undo/Redo/save/reopen and execute. The HUD reports two box bodies and
  one capsule body while the robot rests in both volumes. A physical D key moves
  it about 0.476 metres over 24 physics ticks; Pause and Stop/Play preserve their
  existing semantics. `physics-overlaps-editor.png` was visually inspected.
- `physics-overlap-core.xml`: **24 passed** for registry/compiler/export/build
  identity and strict Python builder inputs. `GraphBuilder.add()` now rejects
  unknown data-input names and execution-port constants before changing the
  graph. This prevents a mistyped Clone Entity `Entity` argument from silently
  falling back to the default `Source`. The corrected clone scenario above uses
  `Source='alpha'`. Regenerating the overlap demo with this validation leaves
  graph, scene, IR and generated C++ bytes unchanged.

The example is `examples/physics_overlaps_demo/project.json`; its generator is
`tools/create_physics_overlaps_demo.py`. Both workflow verifiers accept
`--overlaps`. `physics-overlaps-summary.json` ties the reports, source hashes and
current build identity together.

The evidence is from Windows. Character movement, collider gizmos and compound
shapes, mesh colliders, constraints, animation and the broader acceptance audit
remain incomplete. These detection volumes do not implement character motion;
the full engine goal stays active.

## Native CharacterVirtual foundation — 2026-10-27

Jolt CharacterVirtual now attaches to an existing kinematic capsule in
`PhysicsWorld`. Movement, jumping, grounding, wall sliding, steps, slopes, moving
supports, dynamic-body pushing and clearance-checked crouching use the native
controller. Its stable capsule body remains visible to casts, overlaps and other
bodies. Filters honor both body masks, ignored pairs, activity and triggers.
This is a native foundation; the builtin registry remains at **417 nodes**.

Runtime fingerprint:
`80549caf584a64ed62621f98345b1779569cb7d2c1398f471f0571827d824a33`.

- `character-checks.json`: **124 checks**, including **8 checkpoints** and
  **1120 fresh-process continuation frames**. Actual trajectories cover walking,
  jump/landing, ceiling contact, wall sliding, high-speed sweeps, steps, walkable
  and steep slopes, moving/removed supports and pushing a dynamic body. Resizing
  preserves foot height and leaves the complete world unchanged when standing
  is blocked. Invalid operations and malformed checkpoints preserve the original
  world. Checkpoints cover queued jumping, midair motion, disabled input,
  crouching, moving supports, wall contact, removed support and penetration.
- `character-asserts-checks.json`: the same **124 checks**, **8 checkpoints** and
  **1120 continuation frames** pass in the independent native build with
  `JPH_ENABLE_ASSERTS`. Both runs preserve saved bytes and compare the complete
  restored physics state on every continuation frame.
- `character-physics-regression.json`: **196 checks**, **240 deterministic
  frames** and **880 fresh-process checkpoint continuation frames** pass for the
  existing rigid-body, raycast, cast, overlap, filter and checkpoint behavior.
- `character-runtime-build.log`: the full runtime and the existing overlap
  example build successfully. The recorded preview binary matches the current
  source fingerprint.
- `character-legacy-workflow-checks.json`: **137 checks** pass for the existing
  overlap example through relocated interpreted/generated headless and graphical
  hosts. Region arrays, HUD values, contacts, fractional-step saves and failed-load
  rollback remain correct; full state and GPU images match across execution paths.
  This is a fresh copy of `physics-overlaps-checks.json` at the fingerprint above.

Worlds with characters use physics checkpoint version 2, preserving configuration,
desired velocity, a queued jump and native contact/ground state. Worlds without
characters retain version 1. Restore validates the pinned native binary layout,
rebuilds an independent world and requires exact recapture before committing.
The game-level same-program/assets compatibility boundary remains unchanged.

`character-foundation-summary.json` records the report/source/binary hashes and
current build identity. API and limitations are documented in
[characters.md](characters.md).

Character graph nodes, scene/scale/clone/prefab integration, Inspector authoring,
Stop/Play and whole-game character Save/Load are **not yet delivered**. The
graphical regression uses the existing rigid-body Blockbench demo, not a playable
character controller. No new editor-character or Linux acceptance is claimed.
The complete engine goal remains active; these integration steps precede mesh
colliders, constraints and animation.

## Character nodes, authoring and playable Blockbench demo — 2026-10-27

Eight **Character & Movement** nodes bring the builtin registry to **425**:
Create/Remove/Has Character, Character Move, Character Jump, Character Resize,
Configure Character and Character Ground Check. Ground Check captures six typed
results from one native query; Jump and Resize expose success booleans. Scene
entities optionally store controller settings inside their collider definition,
using existing Inspector validation, Undo/Redo and prefab ownership.

Runtime fingerprint:
`7c710401341d308f24e6127f3295b1d15b3baf50217aea843c8cd3a6eb6cd236`.

Scene synchronization supports uniform scale changes and keeps the visual entity,
native capsule and local binding consistent when resizing under a parent. Clone
copies movement/settings with a fresh body identity. Prefab instantiation/reset
recreates the controller, and Stop/Play restores initial settings. Checkpoint
restoration rejects inconsistent character dimensions, poses or activity before
committing a loaded game.

- `character-scene-tests.xml`: **20 passed in 233.35 seconds**. Python validation,
  inherited prefab edits and the character dialog are checked alongside native
  interpreted/generated creation, movement, captured ground outputs, a grounded
  jump queued once, clone/removal, parent-scaled resize, live scale changes,
  prefab instantiate/reset and originating-node errors.
- `character-authoring-regression.xml`: **34 passed** for the existing core
  registry/compiler/export and Python collider/prefab validation cases selected
  by the recorded command; six native authoring cases were excluded from this
  particular regression run.
- `character-scene-checks.json`: **153 checks** through relocated interpreted and
  generated headless/graphical hosts. The robot lands, stops at a wall, climbs a
  low step, cannot enter a low roof standing, crouches to pass beneath it and
  refuses to stand while obstructed. Airborne and crouched saves resume in fresh
  processes with identical full game state; fractional-step continuation and
  malformed/inconsistent load rollback pass. Interpreted/generated GPU captures
  also match, including the corrected two-line ground/posture HUD.
- `character-editor-checks.json`: **40 checks** through actual Qt authoring and
  embedded SDL Preview. The Inspector rejects invalid slopes and preserves prefab
  ownership through Undo/Redo; six ground-result ports are wired, saved, reopened
  and executed. Configure Character changes the live slope setting. Physical
  D/C/V/Space keys move, crouch, stand and jump. Pause freezes state exactly;
  Stop/Play restores one authored controller. The recorded D movement is about
  **0.95 metres across 22 physics ticks**. `character-editor.png` and the dialog
  screenshot were visually inspected.
- `character-graph-native-checks.json` and
  `character-graph-asserts-checks.json`: **124 checks each**, **8 checkpoints** and
  **1120 exact fresh-process continuation frames** in the normal and
  `JPH_ENABLE_ASSERTS` builds. Existing character trajectories, contact-dependent
  continuation and failed-operation rollback remain valid after scene integration.
- `character-graph-physics-regression.json`: **196 checks**, **240 deterministic
  frames** and **880 checkpoint continuation frames** for existing primitive
  bodies, motion, filters, ray/cast/overlap queries and restoration.

`examples/character_demo/project.json`, produced by `tools/create_character_demo.py`,
is the playable example. W/A/D/arrows move, Space jumps, C crouches, V tries to
stand and S/L save/load. The full native build succeeds against this project.
`character-graph-summary.json` ties source/report hashes, the current build and
the relocated package binaries to this milestone.

This is Windows evidence. Extended movement modes/acceleration, animated/root
motion, character contact-event gameplay coverage, larger crowds, collider
gizmos/compound shapes, mesh colliders, constraints and Linux remain open. The
original-scope acceptance audit and full engine goal remain active.

## Character collision/trigger callbacks and landing saves — 2026-10-27

A native regression reproduced missing character landing events: the virtual
controller rested on the floor, but its kinematic capsule did not request contact
generation against static bodies. Attaching a character now enables that Jolt
policy; detaching restores the ordinary body's policy and invalidates its contact
cache. Existing collision/trigger handlers deliver capsule manifolds, with no
second callback system or new node type. The registry remains at **425**.

Runtime fingerprint:
`362fd2ef07f272a50d7730a68d9a8621bf565656337f399142cd5faee68a7ad0`.

- `character-contact-baseline.json`: records the pre-fix failure of the native
  landing Enter/Stay regression at the previous runtime revision.
- `character-contact-native-checks.json` and
  `character-contact-asserts-checks.json`: **143 checks each**, with **8 saved
  scenarios** and **1120 exact fresh-process continuation frames**. Contact cases
  cover one landing Enter followed by Stay, oriented payloads, static triggers,
  walking out of a volume, disabling/re-enabling, detaching/re-attaching, ignored
  pairs, mask changes, removal/recreation and stable wall contacts. Independent
  restores immediately after detach and reattach preserve the next contact
  transition. The second build enables Jolt's internal assertions.
- `character-contact-tests.xml`: **19 passed in 249.66 seconds**. The existing
  graph contact suite now runs for ordinary bodies and characters. Both native
  execution paths agree on global/scoped payloads, cancellation when callbacks
  destroy/deactivate receivers, Exit-before-Enter on recreation, custom-event
  ordering and originating-node diagnostics for callback budget exhaustion.
- `character-events-checks.json`: **175 checks** in relocated interpreted/generated
  headless/graphical hosts. Native floor/wall/trigger contacts update graph counters
  and HUD text. The first collision callback saves only after completing its
  physics step; fresh-process continuation matches the uninterrupted game without
  repeating Enter. Airborne/crouched/fractional-step saves, invalid-load rollback
  and state/GPU equivalence retain their previous coverage.
- `character-events-editor-checks.json`: **42 checks** in the actual Qt editor
  and embedded SDL game. Inspector/graph Undo/Redo/save/reopen, configuration,
  physical movement/crouch/stand/jump, Pause and Stop/Play pass. Landing/trigger
  callbacks update the HUD, and a physical jump emits floor Exit while retaining
  the trigger contact. The desktop screenshot was visually inspected.

`examples/character_events_demo/project.json` is generated by
`tools/create_character_events_demo.py`. It extends the character playground with
a center trigger and six contact handlers. K loads the first-landing checkpoint;
C/V keep their crouch/stand bindings and S/L use the normal slot. Both character
workflow verifiers accept `--events` and keep separate reports for this example.
The complete native build succeeds against it. `character-events-summary.json`
records the source/report hashes and matching relocated binaries/assets.

Character contacts follow capsule manifolds, including Jolt's speculative margin;
Character Ground Check remains the walkable-support query. Existing runtime and
asset identity requirements still govern game-save compatibility. Larger crowds,
extended movement modes, animation, broader editor/physics acceptance and Linux
remain open. The full engine goal remains active.

## Compatible node search and one-step connection Undo — 2026-10-27

Design Flow B is now implemented for gameplay and function graphs. A port dragged
into empty canvas opens the shared search, limited to exact compatible types and
the current graph's permitted nodes. Each result identifies its endpoint, so Add
A and Add B are distinct choices. Selecting a result creates and connects at the
drop location as one undo transaction. Occupied single ports retain their previous
wire on cancel and restore it on Undo; stable IDs/positions survive Redo and saves.
Search supports keyboard filtering/navigation, explicit empty results and Esc.

The work also reproduced an existing editor/compiler discrepancy: physics and UI
listener configuration ports accepted wires even though compilation requires
Inspector constants. `NodeSpec.constant_inputs` now supplies the same rule to
compiler validation, direct editor connections and search filtering. The baseline
failure is recorded in `port-search-event-baseline.log`.

Verified on Windows with NodeGraphQt **0.6.44** and PySide6 **6.12.0**:

- `port-search-tests.xml`: **47 passed**, comprising 13 new search/gesture cases,
  27 existing editor regressions and 7 existing physics/UI compiler cases.
  Coverage includes float/bool/vector/exec ports, collection function signatures,
  pure function restrictions, direct compatible/incompatible connections,
  replacement/cancel/Undo/Redo, event constants, locked/deleted origins,
  keyboard search, MainWindow save/reopen and function-editor modal behavior.
  The run printed the previously observed Windows COM `0x8001010d` diagnostic
  while showing a Qt widget; it completed with exit 0 and no JUnit failures.
- `port-search-editor-checks.json`: **24 checks** using actual Windows mouse and
  keyboard input in MainWindow. Drag opens the typed search, typing filters Add's
  two ports, Down/Enter chooses B, Ctrl+Z removes both node and link, Redo restores
  exact identity, and Inspector rejects invalid numeric input before accepting
  its correction. A second drag followed by Esc preserves graph/history.
  Saved/reopened source computes **2.5 + 3.5 = 6** in the native headless
  interpreter and the embedded SDL preview. The source and screenshot hashes,
  dependency versions and isolated project path are in the report.
- `port-search-dialog.png` and `port-search-editor.png` were visually inspected:
  both compatible endpoints are legible, and the final graph/Inspector show the
  authored nodes, wires and corrected value.
- After the shared graph adapter change, the character contact editor workflow
  was rerun and retains its **42 passing checks**. The character package was also
  rebuilt after its shortened HUD caption, and its four-host workflow retains
  **175 checks** with source/package hashes recorded in `character-events-summary.json`.

The registry stays at **425** and native runtime sources are unchanged by this UI
milestone. This verifies the specified Windows authoring flow; Linux/IME/screen
readers, larger-graph performance and the remaining engine systems still require
their own evidence. See `node-search.md` and `acceptance-audit.md`; the complete
engine goal remains active.

## Native animation assets and skeleton evaluation — 2026-10-27

The new `node_animation` library imports glTF/GLB TRS clips and skins, validates
their hierarchy and accessors, samples authored curves and evaluates the complete
node hierarchy with ozz-animation 0.17.0. Source curves retain STEP boundaries,
quaternion shortest-arc LINEAR interpolation and time-scaled CUBICSPLINE tangents.
GLM skin evaluation applies inverse binds without doubling the mesh transform.
Assets are immutable and sampling has no instance history.

The pinned ozz source archive is SHA-256 checked, with commit provenance and MIT
license recorded. `animation-dependency-install.json` confirms a real isolated
installation and preservation of an existing install. CMake now requires 3.30;
the installed 4.4.4 built the probe and all four engine executables successfully.
The upstream license is staged in `build/licenses/ozz-animation.txt`.

Current native fingerprint:
`49ff3b660b9f26a8f267ad4e300528add75737b8cd1cd9b765ae9592e6f00cc1`.

- `animation-assets-checks.json`: **56 checks** against a freshly built native
  probe. Analytic cases cover node order, hierarchy, interpolation, time wrapping,
  inverse binds, skin influences, sparse/strided accessors and independent-process
  results. External buffers, data URIs, GLB and Unicode paths agree. Malformed
  trees, skins, channels, times, quaternions, accessor ranges and escaping paths
  fail explicitly. Source and probe hashes match the checked revision.
- `animation-texture-regression.xml`: **29 passed in 13.94 seconds**, rerun after
  the final full build. Existing GPU color/UV/texture, transparency, GLB and
  invalid-asset behavior remains verified. These are static rendering checks.
- `examples/animation_assets/robot.gltf` and `robot.glb` derive from the existing
  nine-cube Blockbench model, with six joints and Idle, Wave and Walk clips.
  Native checks prove rest-bind identity, independent limb motion and identical
  glTF/GLB poses. Regeneration produces byte-identical files.

`animation-foundation-summary.json` binds these reports, the runtime/probe
binaries, source hashes and generated assets to this milestone. The earlier
physics, checkpoint and editor reports remain evidence for their recorded
revisions; this milestone does not claim to rerun those entire suites.

Playback nodes, per-entity clocks, animated rendering, editor clip controls and
animation checkpoint state are **not connected yet**. The existing renderer still
rejects skinned models explicitly. The robot folder is an asset fixture, not a
playable project. Blending, root motion and other specialized animation work follow
the shared runtime integration. See `animation.md`; the engine goal stays active.

## Animation gameplay nodes, renderer and checkpoints — 2026-10-27

The shared runtime now connects the asset foundation to both host loops and
thirteen gameplay nodes (IDs 13001–13013), bringing the registry to **438**.
Imported clips have independent per-entity clocks, reverse/zero speed, looping,
pause/resume, seeking and completion that retains the final pose. Stop restores
the bind pose. Clone copies playback by value; inactivity freezes clocks while
invisibility does not. Destroy and model replacement discard obsolete players.

The renderer skins on the CPU and streams a separate SDL_GPU vertex buffer for
each visible instance, retaining shared textures, indices and original geometry.
It supports up to sixteen influences, normalized integer weights and unskinned
node TRS animation. Face lighting and transparent primitive centers are updated
after deformation. Model/skin accessor ranges, sparse indices and invalid weights
fail explicitly. Animated geometry has a 500,000 expanded-vertex limit.

Animation fields participate in staged whole-game restoration. Testing found and
fixed the slot envelope's former ten-field limit. Earlier checkpoint containers
remain accessible to progress-variable/JSON nodes; full-game restoration still
requires the matching state schema and runtime/assets identity.

Final native fingerprint:
`c4e7da3ac3e9a0666f802db14ac5f1de069c429f7dec76a1867fdd982c91556c`.

- `animation-playback-tests.xml`: **12 passed**, exercising all playback nodes
  through interpreter and generated C++ calls, loop/reverse/completion/zero speed,
  clone/activity/visibility/destruction and original-node error attribution.
- `animation-gpu-tests.xml`: **10 passed**. GPU pixels match independently baked
  geometry for a rotated skin, quantized weights across two influence sets and
  unskinned mesh-node translation. Seven malformed-skin cases fail explicitly.
- `animation-regressions.xml`: **45 passed**, including existing static GPU,
  failed-save/identity/rollback checks and older-container progress-data access.
- `animation-assets-checks.json`: **56 native asset checks**, rerun after the
  robot shoulder pivots were aligned with the original Blockbench cube joints.
- `animation-playback-checks.json`: **121 checks** in all four native hosts,
  relocated to a Unicode directory with developer tools removed from PATH.
  Complete snapshots and GPU pixels match. Independent Wave/Walk clocks, Pause,
  Stop, reverse and seek are exercised. Fresh-process restoration reproduces the
  entire state and rendered poses; invalid time/clip/model/flags preserve the live
  game and slot. Changing one robot leaves the other robot's pixels unchanged.
- `animation-editor-checks.json`: **36 checks** in the actual Qt editor and
  embedded SDL preview. Animation node authoring, wire Undo/Redo, save/reopen,
  physical P/T/3/S/L keyboard input, host Pause and Stop/Play pass. The native
  viewport is focused by a real mouse click. The test handles Windows foreground
  activation restrictions by briefly exposing its own window before clicking.
- `animation-playback/robots.png` and `animation-editor.png` were visually
  inspected. Shoulder pivots and the responsive instruction panel were corrected
  from the initial captures, then the affected workflow/editor checks were rerun.

`examples/animation_demo/project.json` is the playable source project. The local
standalone package is `artifacts/demos/animation-playground`; its executable ran
from that directory and produced the expected complete snapshot. The package
contains the staged native dependencies, shaders, fonts and licenses.
`animation-playback-summary.json` records source/report/package hashes.

The graph/native/GPU tests establish this playback subset. Dedicated clip/skeleton
Inspector references, Animation workspace/timeline, finished/notify events,
blending/state machines, root motion, IK, GPU skinning and crowd performance remain
open. Orbit auto-framing currently uses bind-pose bounds. Checkpoint resource
coverage at this milestone used the standard imported `assets/` layout. The
2026-10-28 follow-up below closes the external-model identity gap. The complete
engine goal remains active.

## 2026-10-28 — model resources outside assets, build staging and Unicode paths

`GameProgramIdentity` now includes model files referenced by scene entities and
compiled prefab templates outside `assets/`. It hashes the declared external
glTF/GLB buffers and images, decodes URI filenames, rejects unavailable files,
links and paths escaping the model directory, and shares the existing 4096-file /
1 GiB resource budget. Embedded data remains covered by the model hash. The full
standard assets library is still hashed. Changing an external resource invalidates
the saved identity; relocation with unchanged bytes remains compatible.

`stage_assets` receives the compiled scene from the real Build worker and copies
these models/dependencies with their project-relative paths. A generated ownership
manifest permits replacing or removing prior staged files while rejecting unrelated
build-file collisions and manual changes. Input/dependency errors leave the prior
output intact. Whole-directory replacement across a process or machine crash is
not atomic; rebuild or use a fresh build directory after an interruption.

The Unicode regression exposed an existing command-line encoding bug in the
headless host. SDL's entry wrapper now supplies UTF-8 arguments, and IR/output
streams use filesystem UTF-8 paths. GPU screenshots also pass UTF-8 to SDL_SaveBMP.

Current runtime fingerprint:
`82f9c9d5d03cc50be8cf1e4d466096650b37730c5b3fb9ad29639487b7219fb3`.

- `model-resources-tests.xml`: **91 passed, 1 skipped**. Covers scene and
  unspawned-prefab glTF/GLB dependency identities, same-size edits, relocation,
  invalid URI/missing-file rejection, staged-file lifecycle and collision safety,
  actual Save/Load rejection without slot mutation, Unicode project/model paths,
  source-versus-staged GPU pixel equality, existing persistence, texture rendering,
  import and build-stamp regressions. The skipped case needs Windows symlink
  creation privilege. The native identity probe is explicitly rebuilt by its
  fixture because it is excluded from the normal CMake all target.
- `animation-playback-checks.json`: **121 checks** rerun on the current build;
  interpreted/generated headless and graphical state/pixel/save parity.
- `animation-editor-checks.json`: **36 checks** rerun in the actual Qt editor,
  including physical keyboard control and embedded viewport Save/Load. The first
  attempt overlapped other graphical checks and lost focus; the isolated rerun
  passed. Desktop-input checks must run without competing test windows.
- `artifacts/demos/animation-playground/Play.cmd --frames 2` runs the refreshed
  compiled package. `model-resources-deliverable.json` contains two active robot
  players at frame 2; the matching BMP captures the rendered result.
- `model-resources-summary.json` records the current source, report and package
  hashes. `animation-playback-summary.json` is refreshed and labels the additional
  older native/asset tests as evidence from the previous milestone.

The model dependency identity gap is closed for the supported glTF/GLB paths.
Animation authoring/blending, broader UI persistence semantics, complete
distribution packaging and the other acceptance-audit items remain open.

## 2026-10-28 — deterministic seeded random nodes and saved continuation

Added five general category-05 nodes: Set Random Seed, Get Random Seed, Random
Float, Random Integer and Random Boolean (IDs 5020–5024). Registry total: **443**.
Draws use execution ports and captured outputs, preserving a single result across
multiple downstream consumers and requiring valid execution scope. The native
implementation shares a per-game SplitMix64 stream; explicit uint64 arithmetic,
53-bit float samples, overflow-safe interpolation and integer rejection sampling
cover the supported ranges. Equal bounds and probability 0/1 consume no draw.

Whole-game checkpoints now include the algorithm, signed original seed and exact
current stream state. Strict restoration stages the record before commit. Older
10/11-field checkpoint envelopes remain readable through progress-variable/JSON
nodes; whole-game compatibility still requires the matching runtime fingerprint.
Stop/reload resets the stream and Play reruns startup seed nodes.

Current native fingerprint:
`6df4ef08e08f4589b8d19ade689f7ed0051df67ab9f31aea6d759bc35068d452`.

- `random-native-tests.xml`: **10 passed** using real interpreted/generated C++
  builds. Covers fixed reference outputs, reseeding/captured outputs, signed
  seed extremes, full-width integer ranges, extreme finite float bounds,
  no-draw constants, invalid ranges/probabilities and original-node diagnostics.
- `random-boundary-tests.xml`: **1 passed** in an additional native build for the
  large-span rejection branch and adjacent representable floating-point bounds.
- `random-regressions.xml`: **53 passed**, including game Save/Load corruption
  rollback, earlier progress containers, external model identities/staging/GPU
  parity, compiler validation, codegen and authoring API regressions.
- `random-workflow-checks.json`: **124 passed** in relocated Unicode paths on
  headless Preview, compiled headless game, graphical Preview and compiled game.
  Reset reproduces pose/dice/state. Fresh-process Load reproduces all snapshot
  fields, future draws and GPU pixels. Wrong algorithm/seed/state/missing/extra
  fields preserve live RNG, entities, variables and slot bytes in all four hosts.
  The initial test scheduled replay relative to process age; corrected it to
  simulation-frame numbering, which resumes from the checkpoint's saved frame.
- `random-editor-checks.json`: **39 passed** in the actual Qt/embedded SDL editor.
  New-node Undo/Redo, graph save/reopen, physical Space/R/S/L, exact restoration,
  Stop and restart work. The verifier's cleanup originally used a nonexistent
  RuntimeClient.stop method; normal window teardown fixed it and reruns passed.
- `artifacts/demos/random-playground/Play.cmd` runs the packaged compiled game.
  A 16-frame replay reproduced dice value 3 and the matching robot placements;
  `random-deliverable.json` and its BMP are the recorded output. Native and editor
  screenshots were visually inspected. `random-summary.json` records current
  source, report, binary/package hashes and exact test counts.

The editable project is `examples/random_demo/project.json`, generated through
Python GraphBuilder by `tools/create_random_demo.py`. See `docs/random.md` for
bounds and reproducibility semantics. Category 05 still lacks vector/direction,
item/shuffle/weighted operations and independent streams. Animation authoring,
other foundation gaps and the complete-engine goal remain open.

## 2026-10-28 — typed random selection, weighted loot and array shuffle

Added Random Item, Random Weighted Item and Shuffle Array for float, int, bool,
string, vec3 and entity arrays: 18 category-05 definitions, bringing the registry
to **461**. Each selection captures Value and zero-based Index together. Array
inputs remain unchanged; duplicate entries are retained. Uniform selection uses
the existing unbiased integer sampler, and shuffling uses Fisher–Yates. Weighted
selection rejects negative/nonfinite/all-zero/mismatched weights and scales by
the largest weight to avoid overflowing a raw sum. Constant choices and empty
or singleton shuffles consume no draw. All operations share the seeded stream
and existing whole-game checkpoint continuation.

Native fingerprint:
`9101789ead66b95505c65dad65e44b0319f892bdd00c6dabe6be3e1bd7851dfc`.

- `random-collections-native.xml`: **8 passed**, exercising all six element
  types in actual interpreted/generated C++, value/index capture, input
  preservation, duplicates, constants, invalid arrays and execution/type checks.
- `random-collections-scalar.xml`: **11 passed**, extracted unchanged from the
  scalar cases in `random-collections-initial.xml`. The initial combined run's
  collection assertion compared vector string representations (`1` vs `1.0`);
  corrected to numeric sequence comparison, then reran all eight collection tests.
- `random-collections-regressions.xml`: **36 passed**, covering registry/compiler
  validation, deterministic code generation and actual native Save/Load rollback,
  old progress envelopes, model identity and external-resource relocation.
- `random-collections-inspector.xml`: **6 passed**, including a fix for Inspector
  fields remaining attached to a deleted/undone node. Removal now clears them;
  restoring and selecting the node allows editing again.
- `random-collections-probe.json`: **22 passed**. The direct C++ probe checks
  fixed selection/permutation references, invalid-input state preservation,
  constants, subnormal weights, overflowing raw weight sums and restored streams.
  In 40,000 draws per sampler, uniform counts were `[9935,10212,9780,10073]`;
  weights proportional to `0:2:1:1` produced `[0,19876,10158,9966]`.
- `random-workflow-checks.json`: **136 passed**, including the new item/index
  and deck checks in relocated Unicode paths across all four native hosts.
  Reseeding, fresh-process saved continuation, malformed-save rollback and exact
  state/GPU parity now include the loot choices and shuffled deck.
- `random-editor-checks.json`: **76 passed** in the actual Qt/embedded SDL editor.
  All 18 nodes can be created and undone; Inspector clears on removal. Physical
  Space/R/S/L, graph save/reopen, Stop and restart retain expected behavior.
  Both the editor and standalone screenshots were inspected visually.
- The refreshed `artifacts/demos/random-playground/Play.cmd` ran with a restricted
  system PATH and reproduced the four-host reference state and GPU bytes for
  the same 16-frame replay. Output is `random-deliverable.json` and `.bmp`.

The Python-authored demo now shows uniform item selection, Potion/Shield/Sword
loot with weights 6:3:1 and a shuffled four-card deck alongside the robot/dice.
`random-summary.json` records current source, report and package hashes; the
previous scalar-only summary is retained as `random-scalar-summary.json`.
See [random.md](random.md) for floating-point probability limits and reference
semantics. Random vectors/directions, noise, other foundation gaps and all
remaining items in the original-scope audit are still open. Linux remains
unverified; the full engine goal remains active.

## 2026-10-28 — random box vectors and unit sphere directions

Added two category-05 action nodes, Random Vector (5025) and Random Direction
(5026), bringing the registry to **463**. Random Vector samples finite per-axis
intervals in X/Y/Z order, skips constant axes and validates all bounds before
advancing state. It shares the existing float sampler, including finite extreme
endpoints and exclusive upper bounds. Random Direction samples uniform height
and azimuth to produce a unit sphere direction with two draws. Both capture
their vec3 output and use the same seed/checkpoint stream.

Native fingerprint:
`bc7642e13c8f93717f63e63c022258859edff4b665f6cc7229bb83f3f4c28105`.

- `random-spatial-native.xml`: **19 passed** using actual interpreted/generated
  C++ builds. Includes the 11 existing scalar cases plus spatial references,
  axis order, constant axes, extreme and adjacent ranges, captured outputs after
  subsequent draws, reseeding, invalid-axis diagnostics and execution scope.
- `random-spatial-regressions.xml`: **36 passed** for registry/compiler/codegen
  and native persistence rollback, legacy progress records and asset identities.
- `random-spatial-probe.json`: **58 passed**, retaining the 22 collection checks
  and adding invalid/nonfinite axes with unchanged RNG state, constant vectors,
  box bounds/means, finite unit directions, first/second moments, height bands,
  octants and restored vector/direction continuation. With 40,000 spatial samples,
  maximum squared-length error was `4.44e-16`; direction second moments were
  `[0.33606,0.33108,0.33287]`, and the ten equal-area bands contained between
  3,878 and 4,120 samples each.
- `random-workflow-checks.json`: **148 passed** across headless/graphical
  Preview and compiled hosts in relocated Unicode paths. The new checks validate
  vector bounds, unit length and marker placement. Fresh-process Load restores
  future directions, complete state and GPU output exactly on this Windows host.
- `random-editor-checks.json`: **79 passed**, including creation of both nodes,
  physical Space/R/S/L, marker placement, graph save/reopen and Stop/restart.
- Refreshed standalone `artifacts/demos/random-playground/Play.cmd` reproduced
  the four-host reference snapshot and GPU bytes for the 16-frame replay with
  a restricted system PATH. Native and editor screenshots were visually inspected.

The Python-authored Blockbench demo uses Random Vector for the main robot's
position and a small robot at `origin + direction * 1.8`, with the origin 0.8
units above the main robot. The current source/report/package hashes are in
`random-summary.json`; the preceding milestone is retained as
`random-collections-summary.json`. No promise of cross-platform bitwise
trigonometric equality is made. Noise, time scaling, the remaining foundation
and specialized systems, and Linux verification remain open. The original
engine goal stays active.

## 2026-10-28 — shared time scaling and checkpointed game clocks

Added five category-05 nodes (5030–5034): Set/Get Time Scale, Get Unscaled Delta
Time, Get Real Time and Get Fixed Delta Time. Registry total: **468**. Both native
hosts capture scale once at frame start; mid-frame changes apply next frame.
Timers, animation and the fixed physics accumulator receive the scaled delta.
Scale zero suspends timers, including zero-duration callbacks, and fixed physics;
Update/input/UI handlers remain available. Audio uses the unscaled step.

The live SDL host keeps the existing 0.1-second simulation-step cap after stalls,
while the separate real clock accumulates the full elapsed interval. Fixed
physics integration stays at 1/60 second. Whole-game clocks now persist scale,
real time and the unscaled delta alongside existing frame/time/delta fields.
Restoration validates the complete record before committing. Earlier clock
schemas remain readable as progress-data containers, but whole-game identity
still requires the matching runtime revision.

Native fingerprint:
`ec3a8a7ceb4b01739d940d984781412ec1489d433eb908f3e37a960d74e966e1`.

- `time-native.xml`: **8 passed**, compiled and interpreted C++ execution for
  0/0.25/1/2 scales, timer counts, fixed ticks/delta, real/unscaled queries,
  next-frame changes, input-driven resume, invalid scales and zero-duration
  timers at both frozen scale and an ordinary zero host delta.
- `time-regressions.xml`: **36 passed** for compiler/registry/codegen and native
  Save/Load corruption rollback, resource identities and historical progress
  containers with the actual older four-field clock shape.
- `time-probe.json`: **18 passed** in direct C++. Invalid/nonfinite scales and
  steps, excessive catch-up, overflow and exhausted frame counters preserve
  state. A two-second stall advances real time by two seconds while a capped
  0.1-second step at quarter speed advances game time by 0.025 seconds.
- `time-workflow-checks.json`: **188 passed** across headless/graphical Preview
  and generated games, relocated to Unicode paths. Analytic clock/tick/timer and
  animation checks cover slow/normal/fast modes. Frozen worlds and GPU pixels
  remain unchanged while audio and host frames advance. Input resumes physics.
  A frozen checkpoint loaded in a fresh process matches uninterrupted complete
  state and GPU pixels; malformed scale/real-time/delta/missing/extra fields
  preserve live clocks/world and slot bytes. Audio PCM is identical across
  equal-duration normal/slow/fast/frozen runs.
- `time-editor-checks.json`: **54 passed** in the real Qt/embedded SDL editor:
  five-node creation/Undo, save/reopen, physical 0/1/2/3/S/L, exact frozen world
  comparison, real/audio advancement, saved freeze restoration and Stop/restart.
- `artifacts/demos/time-playground/Play.cmd` ran under a restricted system PATH
  and matched the 75-frame reference state and GPU bytes. The editable project
  is `examples/time_demo/project.json`, created through Python GraphBuilder by
  `tools/create_time_demo.py`. Native and editor screenshots were inspected.

`time-summary.json` records source, binary/package and report hashes. See
[time.md](time.md) for clock phases, audio/UI behavior and the one-second scaled
frame limit. Unscaled timers, countdown/delay operations, remaining general and
specialized systems and Linux verification remain open. The full goal is active.

## 2026-10-28 — independent named-timer clocks

Start Timer (5010) now has a Boolean `Unscaled` input, default false for existing
graphs. The registry remains at **468** definitions. Both hosts always advance
the timer subsystem; individual scaled timers remain suspended at scale zero.
Unscaled timers use the capped unscaled host step, while Editor Pause, manual
Pause Timer and owner activity retain their existing suspension rules.

Callbacks from both clocks are ordered by their expiration position within the
host frame, with creation order breaking exact ties. Stop/replacement cancels
old pending callbacks across clock modes, and callback starts/resumes enter the
next batch. Event checkpoint version 2 saves both clocks and each timer's mode;
staging rejects malformed clock/mode fields without replacing live state.
The internal version-1 reader preserves old timers as scaled. Whole-game runtime
compatibility requirements remain unchanged.

Native fingerprint:
`754c1a1173ba6e6797881252b7ed20c5a3b6048a212a6efdb75ac1ac968eb4b5`.

- `unscaled-timer-workflow-checks.json`: **175 passed** through interpreted and
  generated headless/graphical hosts under a restricted system PATH and relocated
  Unicode directory. Analytic rotations/countdowns, freeze and automatic resume,
  manual pause, exact fresh-process Save/Load and malformed-clock/mode rollback
  pass. Matching host states and GPU pixels were compared directly.
- `unscaled-timer-editor-checks.json`: **50 passed** in the actual Qt/SDL editor:
  Inspector Boolean validation, old-graph defaults, Undo/Redo, save/reopen, physical
  keyboard controls, separate frozen/moving robots, Editor Pause, Save/Load,
  automatic two-second resume and Stop/restart. The screenshot was inspected.
- `unscaled-timer-probe.json`: **50 passed** in native C++, including two-clock
  precision, 120-frame mixed continuation, manual and owner suspension, legacy
  event-record conversion, invalid delta rollback and existing event lifetime,
  cancellation, payload, budget and boundary checks.
- `unscaled-timer-event-write.json` and `unscaled-timer-event-read.json`: **3
  passed**; a writer exits and a new reader reproduces the 160-frame event trace,
  now including unscaled, paused, inactive-owner and destroyed-owner timers.
- `unscaled-timer-core.xml`: **21 passed** for the shared compiler/registry core.
- `unscaled-timer-package.json`: **3 passed**. The standalone `Play.cmd` runs
  without Python/Qt under a restricted PATH and matches the reference complete
  state and GPU image. Package files are hashed in that report.

`unscaled-timer-native.xml` records **34 passed, zero failures/errors/skips**
from `tests/test_unscaled_timers.py`, `tests/test_timers.py` and
`tests/test_game_time.py`. These exercise real generated/interpreted C++ for
mixed timer ordering, replacement/cancellation across modes, zero-duration resume,
owner suspension, manual pause, dynamic Boolean inputs, old timer graphs,
instruction limits, callback errors and scaled/fixed clocks. The three clean
module builds and tests completed in 1,670.60 seconds. The finalized
`unscaled-timer-summary.json` binds these results to source/report hashes.

Editable example: `examples/unscaled_timer_demo/project.json`, generated by
`tools/create_unscaled_timer_demo.py`. Standalone:
`artifacts/demos/unscaled-timer-playground/Play.cmd`. See [timers.md](timers.md)
for clock semantics. Latent Delay, dedicated Countdown nodes, other incomplete
engine systems and Linux verification remain open. The full goal remains active.

## 2026-10-28 — On Late Update and same-frame camera follow

Added On Late Update (1005), bringing the builtin registry to **469**. Both native
hosts run this once after timer dispatch, all fixed steps and animation advance,
then drain its custom events before advancing public frame/time counters. It
continues at Time Scale zero and stops with Editor Pause. Camera Follow can now
read the final physical pose of the same frame. Timers created late start counting
in the next frame, and game Save/Load requests retain the normal deferred boundary.

The shared frame-event validator checks required start/update and optional
fixed/late arrays before loading or replacing a world. Existing graphs/IR without
a late phase remain usable, and generated C++ emits an empty handler for them.
Failed reload leaves the live world intact.

Native fingerprint:
`aa2444e536af32f67bb10819c9e55d5acb355cb02def938a6c66a6bf48776c65`.

- `late-update-native.xml`: **29 passed, zero failures/errors/skips** in 445.22
  seconds. Eight tests execute real interpreted/generated C++ for zero/one/two
  fixed steps before Late Update, frame delta/counter observations, physical
  camera follow, timer deferral, callback error identity, same-frame custom-event
  delivery and old graphs without Late Update. The remaining 21 cover the shared
  compiler/registry/code generator core.
- `late-update-workflow-checks.json`: **123 passed** across the four native
  headless/graphical interpreted/generated paths, relocated to Unicode paths
  under a restricted system PATH. Checks compare analytic displacement, pre/post
  physics observations, camera alignment, advanced animation time, frozen late
  callbacks, physical input replay, and fresh-process Save/Load requested from
  Late Update. Complete states and GPU images match between paths and restored
  versus uninterrupted execution.
- `late-update-editor-checks.json`: **51 passed** in the actual Qt/embedded SDL
  editor. Library double-click creates the new entry; Undo/Redo/save/reopen work.
  Physical input reverses movement, freezes/resumes, saves and loads. Camera
  alignment, animation observations, Editor Pause and Stop/restart pass. A
  deliberately malformed late phase reports an error while preserving the world;
  the inspected screenshot shows that expected error with the surviving scene.
- `late-update-probe.json`: **24 passed** in direct C++, retaining clock-validation
  coverage and adding required/optional frame-array validation and old-IR acceptance.
- `late-update-package.json`: **3 passed**. The standalone launcher runs without
  Python/Qt under a restricted PATH and exactly matches reference state and GPU
  capture. Package files are hashed.

Editable project: `examples/late_update_demo/project.json`. Python authoring:
`tools/create_late_update_demo.py`. Standalone:
`artifacts/demos/late-update-playground/Play.cmd`. The runtime and editor captures
were visually inspected. `late-update-summary.json` records source, report and
package evidence. See [frame-events.md](frame-events.md) for ordering and limits.

Entity/application lifecycle events, latent flow operations and the other
requirements in the original-scope audit remain open. Linux remains unverified.
The complete engine goal stays active.

## Animation completion callbacks — 2026-10-28

Added On Animation Finished (13014), bringing the registry to **470** builtin
definitions. Python authoring, graph validation, generated C++, interpreted
runtime and the Inspector share the same entity/clip filters and scoped outputs.
Completion runs after animation advancement and before Late Update; callbacks
can start another clip or change entity lifetime. Zero-duration, non-looping Play
queues immediate completion after the calling graph. Restore does not replay it.

Evidence in `artifacts/validation/`:

- `animation-finished-tests.xml`: **37 passed, zero failures/errors/skips** in
  339.96 seconds. Sixteen tests cover static filters, scoped outputs, forward and
  reverse completion, looping/zero speed, pause/activity/time freeze and resume,
  captured payloads, Late Update ordering, Stop/seek behavior, clone/destruction
  during callbacks, zero-duration Save/Load and callback budget attribution.
  Twenty-one tests cover the shared compiler/registry/code generation core.
- `animation-finished-workflow-checks.json`: **148 passed** across interpreted
  and generated headless/SDL hosts, relocated to Unicode paths under a restricted
  system PATH. Includes Wave -> Idle, independent looping Walk, pause/resume,
  reverse/freeze/stop, completion-triggered saves, exact fresh-process restoration
  both midway through a clip and after its completion, and invalid filter
  restoration rollback. Full states and GPU images match across paths.
- `animation-finished-editor-checks.json`: **50 passed** in the real Qt/embedded
  SDL editor. Library creation, Inspector filter edits, Undo/Redo, save/reopen,
  physical keys, paused animation saves, restored completion delivery, host
  Pause and Stop/restart pass. A malformed native filter rejects reload while
  preserving the running world; the screenshot includes that expected error.
- `animation-finished-event-probe.json`: **59 passed** after explicitly rebuilding
  `node_event_probe`. Nine new direct C++ checks cover pending completion payloads,
  preserved filters/scopes, rejection without mutation or Flecs leaks, invalid
  native filters, deleted receiver/global payload behavior, prefab recreation and
  stale activity epochs. Fifty existing timer/custom-event checkpoint checks
  continue to pass.
- `animation-finished-package.json`: **3 passed**. `Play.cmd` runs with the system
  PATH and no Python/Qt dependency, matching four-host state and GPU output.

Editable project: `examples/animation_finished_demo/project.json`. Python source:
`tools/create_animation_finished_demo.py`. Standalone launcher:
`artifacts/demos/animation-finished-playground/Play.cmd`. Runtime and editor
captures were visually inspected. `animation-finished-summary.json` records
source, binary, report and package hashes. See [animation.md](animation.md) for
callback semantics and the reproduction commands.

Animation notify markers, blending/state machines and dedicated clip/skeleton
Inspector/timeline authoring remain open, along with the other requirements in
the original-scope audit. Linux remains unverified. The full goal stays active.

## Break and Continue loop control — 2026-10-28

Added Break Loop (2005) and Continue Loop (2006), bringing the registry to **472**
builtins. Both work in For/While/all typed For Each bodies, including action
functions. Scope validation rejects controls outside the current graph's loop
Body. The interpreter propagates bounded control results, and C++ export uses
native break/continue statements. Nested loops consume their own controls;
Function Output still returns from the whole function.

Evidence in `artifacts/validation/`:

- `loop-control-tests.xml`: **44 passed, zero failures/errors/skips** in 319.74
  seconds. Twenty-three tests cover loop scope, shared invalid paths, function
  isolation, raw IR validation, conditional controls and Sequence tails in all
  three loop kinds, inner Break/outer Continue, snapshot-array mutation, early
  Return/caller locals, empty loops and budget diagnostics. Thirteen execute real
  native interpreted/generated games. Twenty-one additional tests cover the
  shared compiler/registry/code generation core.
- `loop-control-workflow-checks.json`: **96 passed** across interpreted/generated
  headless/SDL hosts, relocated to Unicode paths under a restricted system PATH.
  The scanner skips non-target/inactive entities and stops after the first match.
  Visit counters prove both skipped and unvisited paths; no-match and subsequent
  calls clear stale results. Fresh-process Save/Load followed by a new scan
  reproduces complete state and GPU pixels exactly.
- `loop-control-editor-checks.json`: **48 passed** in actual Qt/embedded SDL.
  Both nodes are created through the function library with Undo/Redo. An unscoped
  Break blocks Save with a diagnostic; Undo repairs it. Project save/reopen,
  physical availability/scan keys, selection enlargement, Save/Load, Pause and
  Stop/restart pass. Function and editor screenshots were visually inspected.
- `loop-control-package.json`: **3 passed**. The standalone Play.cmd runs using
  the system PATH, with no Python/Qt dependency, and matches the reference's
  entire state and GPU capture.

Editable project: `examples/loop_control_demo/project.json`. Python authoring:
`tools/create_loop_control_demo.py`. Standalone:
`artifacts/demos/loop-control-playground/Play.cmd`. The evidence/source hashes are
recorded in `loop-control-summary.json`. See [flow-control.md](flow-control.md)
for exact semantics, limitations and reproduction commands.

Do Once/Do N, Gate/Flip Flop/Multi Gate, Delay/Wait Until and async tasks remain
open, together with the other original-scope requirements. Linux remains
unverified. The full engine goal stays active.

## Persistent flow gates - 2026-10-28

Do Once (2007), Do N (2008), Gate (2009) and Flip Flop (2010) bring the registry
to **476** builtin definitions. The compiler retains the destination exec port
and scopes captured Counter/Is A values to emitted branches. Both native paths
use the same owner/node state, validate control inputs, and propagate loop and
function exits. Entity destruction and prefab removal clear owned state; cloning
starts fresh. Stop/reload resets it. Checkpoint restoration validates the state
in a staged context before committing the game.

Editor connections can return to Reset/Open/Close/Toggle without creating an
execution cycle. The compiler separately validates data and execution paths;
In feedback remains invalid. Flow binding discovery examines executable blocks,
so a Map or function default containing `op: flow` remains ordinary game data.

Evidence in `artifacts/validation/`:

- `stateful-flow-tests.xml`: **35 passed**, zero failures/errors/skips, in
  **328.42 seconds**. Fourteen flow cases cover repeated entry, reset feedback,
  quotas and dynamic limits, open/close/toggle, alternating captured branches,
  unused-input evaluation, owner/function isolation, clone/destruction, loop
  continuation, function returns, diagnostics and Map/default data. Native cases
  execute both interpreted and generated games. Twenty-one shared core tests
  cover registry/compiler/code generation.
- `stateful-flow-persistence-tests.xml`: **35 passed**, zero failures/errors/skips.
  Progress data, damaged slots, identity checks, atomic rollback, locking,
  legacy envelopes and relocated resources pass against the final runtime.
  The game-save fixture now compiles the source project instead of copying
  generated IR with an outdated timer signature. Legacy fixtures remove fields
  introduced after their claimed schema version.
- `stateful-flow-editor-tests.xml`: **29 passed**, zero failures/errors/skips.
  Typed-port rejection, connection roundtrips, Undo/Redo, functions, Inspector,
  clipboard and IPC regressions pass. The existing modal-input test still emits
  Windows/Qt diagnostic `0x8001010d`; both the suite and its isolated rerun exit
  zero and pass their assertions. NodeGraphQt also emits deprecation warnings.
- `stateful-flow-native-checks.json`: **32 passed**. Direct native calls cover
  exact quotas including INT64_MAX, first-use Gate state, explicit commands on
  inactive owners, clone/destruction, nine malformed-checkpoint cases with
  atomic rejection, invalid control calls, scene reset and fresh-process future
  decisions. Literal maps and function defaults do not register flow nodes.
- `stateful-flow-game-checkpoint-checks.json`: **67 passed**, with **132 exact
  continuation frames** and seven byte-identical reference/restored PCM pairs.
  This rerun uses SDL's dummy audio driver; it does not repeat the earlier
  physical WASAPI verification.
- `stateful-flow-workflow-checks.json`: **132 passed** across four relocated
  interpreted/generated headless/SDL hosts with restricted system PATH. Exact
  behavior, fresh-process Save/Load, continued gate decisions, unchanged saved
  bytes and malformed-state rollback pass. All states and corresponding GPU
  pixels agree, including the uninterrupted/restored scene.
- `stateful-flow-editor-checks.json`: **65 passed** in actual Qt/embedded SDL.
  The Library creates all four nodes; Inspector quota edits, Undo/Redo, Reset
  feedback, invalid In feedback, save/reopen, physical O/N/G/F/R/S/L input,
  Pause/Stop/restart and rejected-program rollback pass. Connection creation in
  this verifier uses real adapter ports, not physical mouse wire dragging.
  The final editor screenshot and standalone robot capture were visually checked.
- `stateful-flow-package.json`: **3 passed**. The standalone Play.cmd runs with
  system PATH and no Python/Qt, matching the reference's entire state and pixels.

This milestone records **99 pytest cases and 299 native/editor/workflow/package
checks**. `stateful-flow-summary.json` ties the evidence to source and binary
hashes. Editable project: `examples/stateful_flow_demo/project.json`. Python
authoring: `tools/create_stateful_flow_demo.py`. Standalone:
`artifacts/demos/stateful-flow-playground/Play.cmd`.

See [flow-control.md](flow-control.md) for exact state/owner semantics and limits.
Full-game saves remain runtime/schema-specific; no migration is claimed.
Multi Gate, Delay/Wait Until, async flow, the other original-scope requirements
and Linux verification remain open. The full engine goal stays active.

## Multi Gate route cycles - 2026-10-28

Multi Gate (2011) brings the registry to **477** builtin definitions. It uses the
shared flow state with 1-8 active outputs, sequential or random selection without
repeats, a configurable first route, looping, Reset and a scoped zero-based Index.
Random selection uses the existing seeded generator. Switching modes preserves
visited routes; changing the active route count starts a fresh cycle. Owner,
function, clone/destruction and Stop semantics match the other persistent gates.

Game checkpoints now include Multi Gate's active route count, visited mask and
next sequential cursor. They restore alongside the shared random stream. Invalid
progress, a cursor following an unvisited route, out-of-range bits, incompatible
bindings, unknown owners, invalid flags, extra fields and duplicate state entries
reject the staged load before live-world replacement.

Evidence in `artifacts/validation/`:

- `multi-gate-tests.xml`: **49 passed**, zero failures/errors/skips, in **459.08
  seconds**. Fourteen new native cases verify all eight outputs, one-route and
  nonzero-start cycles, exhaustion/looping, seeded random selection without
  repeats, reset/unused-input evaluation, changing counts/modes, scoped Index,
  Break/Continue, function/owner sharing, clone/destruction and input errors.
  Fourteen existing flow cases and 21 shared core cases remain green.
- `multi-gate-persistence-tests.xml`: **35 passed**, zero failures/errors/skips.
  Existing progress data, malformed saves, atomic rollback, file locking,
  legacy envelopes, program/resource identity and relocated assets still pass.
- `multi-gate-prior-flow-checks.json`: **32 passed** after rebuilding the direct
  native probe, including old gate semantics, integer quota boundaries, owner
  lifetime, malformed checkpoint rejection and fresh-process continuation.
- `multi-gate-game-checkpoint-checks.json`: **67 passed**, **132 exact continuation
  frames** and seven byte-identical reference/restored PCM pairs. This run uses
  dummy audio; physical WASAPI output was not repeated for this milestone.
- `multi-gate-workflow-checks.json`: **204 passed** in four relocated native
  interpreted/generated headless/SDL hosts with restricted system PATH.
  Sequential and random tours, switching modes, enabling Loop after exhaustion,
  reset/seed replay, a save halfway through a random cycle, fresh-process future
  cycles and eight malformed-checkpoint variants pass. Corresponding complete
  states and GPU captures agree, including uninterrupted/restored routes and HUD.
- `multi-gate-editor-checks.json`: **54 passed** in actual Qt/embedded SDL.
  Library creation exposes all eight outputs; Inspector count/start edits,
  Undo/Redo, last-output Reset wiring and save/reopen pass. Physical Space/M/T/R/S/L
  input traverses and exhausts a cycle, enables looping, switches to random,
  saves mid-cycle and reproduces later choices after loading. Pause, Stop and
  restart pass. Wires in this verifier use adapter ports; physical mouse wire
  dragging was not re-certified. The editor screenshot was visually inspected.
- `multi-gate-package.json`: **3 passed**. The standalone launcher runs with only
  system PATH and no Python/Qt, matching the reference state and GPU pixels.

Total: **84 pytest cases and 360 native/editor/workflow/package checks**.
`multi-gate-summary.json` records source, binary, evidence and package hashes.
The final robot capture was visually inspected. Editable project:
`examples/multi_gate_demo/project.json`; Python authoring:
`tools/create_multi_gate_demo.py`; standalone:
`artifacts/demos/multi-gate-playground/Play.cmd`.

Multi Gate currently has eight fixed output ports, not arbitrary port authoring.
Delay/Wait Until, Retriggerable Delay, async execution, the remaining original
requirements and Linux verification are still open. The engine goal stays active.

## Serializable latent flow - 2026-10-29

Delay (2012), Wait Until (2013) and Retriggerable Delay (2014) bring the registry to
**480** builtin definitions. Each event entry can suspend independently, including
inside For/While/typed For Each and action functions. The shared native scheduler
retains event payloads, parameters, scoped results, loop snapshots and callers.
Exported games use generated typed expression/action callbacks. Existing graphs
without latent operations retain direct native execution.

Owner lifetime, inactive-owner suspension, scaled/unscaled time, zero-delay
yielding, duplicate-entry suppression and retrigger replacement are defined in
[flow-control.md](flow-control.md). Whole-game restoration stages the complete
continuation stack with the world and other subsystems; malformed state cannot
replace live state. There are no worker threads or public task handles in this
delivery.

Evidence in `artifacts/validation/`:

- `latent-flow-tests.xml`: **43 passed**, zero failures/errors/skips. Fifteen
  latent cases cover independent entries, exact frame timing, reentry, condition
  polling, retriggering, captured For Each items and function results, suspended
  Break/Continue and While/Sequence, time scaling, owner destruction/inactivity,
  clone isolation, original-node errors, unused duration evaluation and custom
  event payloads. The 28 existing persistent-gate/Multi Gate cases also pass.
- `latent-flow-retrigger-test.xml`: **1 passed**. A second caller replaces a
  pending function invocation and returns its new parameter to the correct caller.
- `latent-flow-regression-tests.xml`: **56 passed**, zero failures/errors/skips:
  21 shared compiler/core cases and 35 progress/whole-game persistence cases.
- `latent-flow-workflow-checks.json`: **208 passed** in four relocated native
  interpreted/generated headless/SDL hosts with restricted system PATH. The
  robot waits for input, visits four stations through a delayed function in For
  Each, and saves with two pending chains. Fresh-process restoration reproduces
  all final state and GPU pixels. Twelve malformed checkpoint variants reject
  without changing the live world or save bytes: program, owner, position,
  parameter, local, loop, wait, duration, duplicate, serial, extra field and caller.
- `latent-flow-editor-checks.json`: **57 passed** in actual Qt/embedded SDL.
  All three nodes can be created from Library, undone/redone and saved/reopened.
  Inspector duration editing, physical Space/R/S/L input, Pause while suspended,
  Save/Load inside a function, completion, Stop and restart pass. This run uses
  the authored graph's wires; it does not re-certify physical mouse wire dragging.
- `latent-flow-game-checkpoint-checks.json`: **67 passed**, **132 exact
  continuation frames** and seven matching PCM pairs in the existing whole-game
  regression probe. This run uses dummy audio; WASAPI was not repeated.
- `latent-flow-package.json`: **3 passed**. The standalone launcher runs with
  system PATH and no Python/Qt, matching the four-host reference state and GPU.

Total: **100 pytest cases and 335 native/editor/workflow/package checks**.
The editor and final robot screenshots were visually inspected. Package contents
and current native sources were verified against their recorded hashes.
`latent-flow-summary.json` records the final source, binary and evidence hashes.

Editable project: `examples/latent_flow_demo/project.json`; Python authoring:
`tools/create_latent_flow_demo.py`; standalone:
`artifacts/demos/latent-flow-playground/Play.cmd`.

Worker-thread async execution, task cancellation/coordination nodes, other
original-scope requirements and Linux verification remain open. The full engine
goal remains active.

## Editable Switch and lazy Select - 2026-10-29

Switch Integer (2015), Switch String (2016) and 18 Select variants bring the
registry to **500** builtin definitions. Switch supports up to 256 per-instance
cases plus Default, exact integer/string matching and stable case IDs. Both
Gameplay and function Inspectors provide case editing. Reordering or changing
values preserves wires; removing a case removes its wire within the same undo
transaction. Earlier connection commands remain valid after undoing a case edit.
Duplicate, copy/paste and save/reopen preserve metadata and dynamic ports.

Select covers all six scalar/reference/vector types and their arrays/maps. It
evaluates its condition once per use and only evaluates the chosen input. Both
inputs remain statically typed and scoped. Generated C++ and interpreted code use
the same native selection helper. Switch branches preserve lexical loop/return
behavior, and suspended branches retain their choice through whole-game Save/Load.

Evidence in `artifacts/validation/`:

- `switch-select-tests.xml`: **18 passed**, zero failures/errors/skips, in
  **354.61 seconds**. Native interpreter/generated parity covers signed 64-bit
  boundary cases, Unicode/NUL strings, case sensitivity, Default/empty tables,
  all 18 Select types with both conditions, skipped invalid expressions, pure
  and action functions, delayed branches with Break/Continue, invalid metadata
  and the 256-case boundary.
- `switch-editor-tests.xml`: **25 passed**, zero failures/errors/skips: four
  editor cases and 21 shared core cases. Real Qt adapters test edit/reorder/remove
  wiring, multi-step Undo/Redo including earlier connection commands, roundtrip,
  duplicate, paste, forged clipboard rejection, case-dialog validation and the
  function Inspector/pure-function library. Existing NodeGraphQt deprecation
  warnings remain.
- `switch-select-regression-tests.xml`: **49 passed**, zero failures/errors/skips,
  in **333.34 seconds**: 35 progress/whole-game persistence cases and 14 function
  regressions. Legacy slot access, invalid-load rollback, program/resource
  identity, typed functions and current generated/interpreted execution remain
  verified.
- `switch-select-workflow-checks.json`: **192 passed** across four relocated
  interpreted/generated headless/SDL hosts with restricted system PATH. All
  integer routes and String Switch facing, Default, changed input during a delay,
  mirrored Select results and fresh-process checkpoint continuation match. Six
  corrupted saved-stack variants reject without replacing live state or changing
  saved bytes. Corresponding full states and GPU captures agree.
- `switch-select-editor-checks.json`: **59 passed** in actual Qt/embedded SDL.
  Library creation and Undo/Redo cover both Switch nodes and representative
  scalar/array/map Select nodes. Inspector case editing uses the real dialog and
  keyboard events; IDs/wires survive reordering and Undo/Redo. Dynamic ports
  support compatible-node search. Physical 1/3/9/Space/M/S/L input, Pause,
  Save/Load inside a selected branch, Default and Stop pass. The authored graph
  supplies the wires; physical mouse wire dragging was not re-certified.
- `switch-select-package.json`: **3 passed**. The standalone launcher runs with
  system PATH and no Python/Qt, matching the reference state and GPU capture.

Total: **92 pytest cases and 254 native/editor/workflow/package checks**. The
editor and robot screenshots were visually inspected. `switch-select-summary.json`
records current native, source, binary, evidence and package hashes.

Editable project: `examples/switch_select_demo/project.json`; Python authoring:
`tools/create_switch_select_demo.py`; standalone:
`artifacts/demos/switch-select-playground/Play.cmd`.

Switch currently matches integer/string values. Enum/state-machine dispatch and
range/pattern matching remain separate work. Worker-thread async tasks, broader
original-scope requirements and Linux verification remain open. Physical audio
was not repeated for this flow-control milestone. The full engine goal is active.

## Entity Created/Enabled/Disabled - 2026-10-29

The registry now has **503 builtin nodes**. Three entry nodes share the existing
Flecs event system and typed native implementation in interpreted Preview and
generated C++. They capture Entity/Active, include inherited parent transitions,
allow inactive owned receivers, cover clone/camera/prefab creation and prefab
Reset/Apply, and preserve pending deliveries across staged checkpoint restoration.
Initial notifications run once before Game Start; Load does not recreate them.
See [entity-lifecycle.md](entity-lifecycle.md) for ordering and limits.

Final evidence in `artifacts/validation`:

- `entity-lifecycle-tests.xml`: **13 passed**, zero failures/errors/skips, in
  **278.016 seconds**. Scope/constant validation and real generated/interpreted
  games cover initial inactive receivers, spawn/clone/camera, rapid toggles,
  reparenting, no-op activity writes, reactivation from callbacks, destroyed
  receiver cancellation, bounded emissions, prefab recreation/Apply and delayed
  function captures. Initial test-fixture errors were corrected before this run.
- `entity-lifecycle-regression-tests.xml`: **57 passed**, zero failures/errors/skips,
  in **34.558 seconds**: 21 core cases, one activity Inspector case, and 35
  progress/whole-game persistence cases. Two existing NodeGraphQt deprecation
  warnings remain. This is a targeted regression run, not a new full-suite claim.
- `entity-lifecycle-event-checkpoint-checks.json`: **87 passed**, including the
  existing event/timer/animation checkpoint regressions and 160-frame fresh-process
  replay. Added checks cover version-3 lifecycle queues, invalid payload/receiver
  states, no world/observer mutation on rejected restoration, deleted owner
  cancellation, queue bounds, and physics-prefab staging. Invalid sphere scale
  rejects before emitting or changing the scene; successful staged creation and
  Reset emit each lifecycle transition once.
- `entity-lifecycle-workflow-checks.json`: **132 passed** in four relocated
  native headless/SDL interpreted/generated hosts with a restricted system PATH.
  Parent activity, inactive clone, prefab descendants, destruction, Reset,
  Save/Load in a fresh process and future ID allocation match. Five malformed
  save variants reject without changing live scene/state or saved bytes. Full
  states and corresponding GPU captures match across execution paths.
- `entity-lifecycle-editor-checks.json`: **57 passed** in real Qt/embedded SDL.
  Library creation of all three nodes, typed ports, static Receiver, Inspector
  editing, Undo/Redo and save/reopen pass. Physical T/N/C/X/R/S/L input exercises
  inherited activity, spawn/clone/destroy, Reset and Save/Load. Pause preserves
  counters; Stop clears lifecycle initialization and fresh Play starts it once.
- `entity-lifecycle-package.json`: **3 passed**. The standalone Play.cmd runs
  with system PATH and no Python/Qt; its state and GPU capture match the reference.

Total: **70 pytest cases and 279 native/editor/workflow/package checks**.
The editor and robot screenshots were visually inspected. The final
`entity-lifecycle-summary.json` records native/source/binary/evidence/package
hashes and confirms zero failures/errors/skips in both test reports.

Editable project: `examples/entity_lifecycle_demo/project.json`; authoring script:
`tools/create_entity_lifecycle_demo.py`; standalone:
`artifacts/demos/entity-lifecycle-playground/Play.cmd`.

On Object Destroyed remains pending: its before-deletion contract requires
reentrant deletion and prefab transaction handling. Scene Loaded, Pause/Resume,
Quit, Linux, large-scene performance and the broader original engine scope remain
open. Physical audio and mouse wire dragging were not repeated for this milestone.
The full development goal remains active.


## 2026-10-29: Before-deletion entity callbacks

The registry now contains **504 builtin nodes**. On Object Destroyed (1009)
dispatches through Flecs synchronously before removing a live entity, including
inactive objects, child cascades, detached prefab members and Reset/Apply removals.
Callbacks read the original object and can create loot. Repeated self-destruction
is idempotent; nested destructive edits run from a bounded FIFO after commit.
Prefab staging validates again after callbacks to retain scene/physics edits.
Latent action functions preserve caller state across synchronous callback entry.
The complete contract and error limits are in [entity-lifecycle.md](entity-lifecycle.md).

Verified on Windows in this milestone:

- `entity-destroyed-tests.xml`: **12 passed**, zero failures/errors/skips,
  in **317.896 s**. Covers scope/constant Receiver validation, active
  and inactive global/owned delivery, readable Unicode names, cascade and nested
  deletion, new children, illegal reparenting, prefab Reset/Apply, detached members,
  suspended functions with exact int64 parameters, global versus owned waits,
  and a fresh-process save requested from the callback. Both native headless
  implementations run the graph scenarios.
- `entity-destroyed-regression-tests.xml`: **59 passed**, zero
  failures/errors/skips, in **1442.216 s**. Rechecks existing entity
  lifecycle, latent-flow scheduling and native prefab Apply/Reset behavior.
- `entity-destroyed-event-checkpoint-checks.json`: **100 passed**, including
  existing timer/custom/animation checkpoints and **160** exact fresh-process
  continuation frames. Added checks verify callback-time checkpoint rejection,
  forged queued Destroyed rejection without replacing the live world, dead owned
  bindings, send/broadcast rejection, callback-error cleanup, instruction/queue
  limits and staged physics edits that preserve callback velocity changes/loot.
- `entity-destroyed-workflow-checks.json`: **132 passed** across interpreted and
  compiled headless/SDL hosts in a relocated Unicode folder with restricted PATH.
  Active/inactive removals, prefab Reset/Apply/cascades, callback loot, invalid
  checkpoints and exact fresh-process continuation agree in complete state;
  corresponding SDL GPU captures agree pixel-for-pixel.
- `entity-destroyed-editor-checks.json`: **47 passed** in actual Qt/embedded SDL.
  Library creation, typed ports, constant Receiver editing, Undo/Redo and reopen
  work. Physical keys exercise inactive clone removal, prefab edits, loot,
  Pause, Save/Load and repeated continuation. Stop/fresh Play emit no stale
  destruction. Both the editor screenshot and standalone robot image were viewed.
- `entity-destroyed-package.json`: **3 passed**. `Play.cmd` runs with a restricted
  system PATH; complete state and captured pixels equal the four-host reference.

Total: **71 pytest cases + 282 native/editor/workflow/package
checks**. The runtime fingerprint is `47c1be2700b8b5fbb828b58ef40afe700d762d68910171395014635f0114d74f`. Source, binary, evidence and package
hashes are recorded in `artifacts/validation/entity-destroyed-summary.json`.

Editable project: `examples/entity_destroyed_demo/project.json`; authoring script:
`tools/create_entity_destroyed_demo.py`; standalone launcher:
`artifacts/demos/entity-destroyed-playground/Play.cmd`. T toggles activity, N/C
spawn or clone, A adds a loot-bearing child, R resets, P applies, X destroys and
S/L save/load. The HUD exposes removal counts, last name/activity and spawned loot.

Limits: callback side effects are not rolled back after a callback/revalidation
error, although structural deletion is not committed and deferred destructive
requests are cleared. Delayed global callbacks must check captured stale entity
references. Scene Loaded, Pause/Resume and Quit events remain open. This is a
targeted regression run, not a rerun of every engine test. Linux, large-scene
performance and physical audio were not tested in this milestone. The overall
engine goal remains active and incomplete.


## 2026-10-29: Ordered keyboard, mouse and action events

The registry contains **509 builtin nodes**. Five input entries (10008–10012)
deliver keyboard press/release, mouse button and mapped action press/release
transitions through the shared Flecs queue. Constant filters are validated in
Python and native binding; outputs are scoped and survive latent execution.
Quick taps retain original transition order, key repeat is suppressed, and two
held alternatives produce one action press and one final release.

Interactive SDL Load now clears stale saved held keys without synthetic callbacks;
deterministic replay preserves them for exact continuation. Qt focus changes
restore the native Qt HWND and explicitly queue release-all over IPC. Real
desktop tests exposed both a HUD that consumed game clicks and missing embedded
SDL focus-loss notifications; the demo now passes pointer events through, and
clicking a Qt panel releases held gameplay input exactly once. The HUD also wraps
inside a narrow editor viewport.

Verification on Windows:

- `input-events-tests.xml`: **12 passed** in **258.839 s**,
  zero failures/errors/skips. Covers invalid filters, constant/scoped ports,
  original event ordering, rapid taps/repeat/alternative handoff, filtered listener
  order, captured Down versus final Held, Delay/retriggered captures, held startup
  without artificial presses and originating-node budget errors. Native interpreted
  and generated executions are compared.
- `input-events-regression-tests.xml`: **37 passed** in
  **332.564 s**, zero failures/errors/skips, for previous input polling,
  scene bindings/dialog history, compiler/core behavior and runtime fingerprints.
  After the focus fix, the real input dialog regression was rerun separately:
  `input-events-focus-regression-tests.xml`, **1 passed** in
  **1.385 s**. This is **49 distinct pytest cases**, with
  **50 executions** including that rerun.
- `input-events-event-checkpoint-checks.json`: **116 passed**, retaining existing
  timer/custom/animation/entity lifecycle checks and **160** exact
  fresh-process continuation frames. New cases preserve ordered pending input,
  filter identity and global scope; reject forged names/directions/subscriptions
  without mutation or Flecs leaks; test queue limits, raw-input validation and
  discarding queued callbacks on input clear.
- `input-events-workflow-checks.json`: **116 passed** in four relocated native
  hosts with a Unicode package directory and restricted PATH. Covers quick taps,
  held alternatives, callback-triggered Save with a pending captured action,
  fresh-process Load and subsequent retriggering/movement, and malformed input
  checkpoint rollback. Complete state matches across hosts; interpreted/generated
  GPU pixels and restored/uninterrupted rendering match.
- `input-events-editor-checks.json`: **85 passed** in actual Qt/embedded SDL.
  All five Library entries, typed ports, constant filter editing, Undo/Redo and
  project reopen work. Physical mouse/keyboard test repeat, alternative handoff,
  Pause/Resume, Save/Load, reusing the Save key after Load, focus release and
  Stop/fresh Play. The test uses physical window coordinates at 125% DPI. The
  editor and standalone screenshots were visually inspected.
- `input-events-package.json`: **3 passed**. The standalone launcher runs with
  only the system PATH and reproduces the reference state and GPU capture.

Total: **49 distinct pytest cases + 320 native/editor/workflow/package checks**.
Runtime fingerprint: `39e3aee081b225e529e8a390857f38c788c4fd5c499fbd0820361a25801a5a8c`. Source, binary, evidence and package hashes are in
`artifacts/validation/input-events-summary.json`.

Editable project: `examples/input_events_demo/project.json`; Python authoring:
`tools/create_input_events_demo.py`; standalone:
`artifacts/demos/input-events-playground/Play.cmd`. Space/left mouse turn, A/D or
arrows move, R resets pose and S/L save/load. The HUD shows event counts and the
action payload retained by a retriggerable delay.

Limits: the shared queue remains bounded to 4,096 deliveries / 64 MiB. Filters
are static; input contexts, consumption, runtime rebinding, pointer-position/
delta/wheel, gamepads and analog input remain open. Text/IME, other keyboard
layouts, Linux, broader DPI/device coverage and large input storms were not
certified. Physical audio and the full engine test suite were not rerun. Existing
NodeGraphQt distutils deprecation warnings remain. The overall goal stays active.


## 2026-10-29: Pointer position, motion and wheel

The registry contains **512 builtin nodes**. Get Mouse Position, Get Mouse Delta
and Get Mouse Wheel (10013-10015) expose Vector3 (X,Y,0) through the shared native
input state and generated adapters. Fractional coordinates are retained; motion
and two-axis wheel accumulate in original event order, reset each frame and are
not consumed by reads. Button/wheel events update position even without motion.
Version-2 replay and input checkpoints preserve pointer state, with legacy
button-only replay and standalone version-1 input-checkpoint reading retained.
Full-game saves still require exact program/resource compatibility.

SDL samples the physical cursor on Play/Resume and successful Load without
manufacturing motion or wheel input. RmlUi-consumed motion/scroll stay out of
gameplay while position remains readable. Focus release and Pause discard
transient impulses; replay retains exact checkpoint continuation.

Verification on Windows:

- `pointer-regression-tests.xml`: **51 passed** in **699.202 s**, no failures,
  errors or skips. Includes two native interpreted/generated pointer tests for
  fractional accumulation, absolute-only samples, release ordering, empty-frame
  reset, startup neutrality, repeated reads and Late Update parity. The existing
  keyboard/mouse/action, scoped/delayed event, input-dialog, compiler/core and
  runtime-build regressions also pass.
- `pointer-event-checkpoint-checks.json`: **139 checks**, including **23** new
  pointer checks. Covers atomic malformed-checkpoint/raw-input rejection,
  non-finite values, accumulation overflow, version-1 upgrade and version-2 replay
  validation. Existing event/lifecycle checks and **160** fresh-process event
  continuation frames remain passing.
- `pointer-workflow-checks.json`: **112 checks** across interpreted/generated
  headless and SDL hosts in a relocated Unicode directory with restricted PATH.
  A save retains nonzero frame delta/wheel and a held drag. A fresh process
  restores and continues to the exact uninterrupted state; complete states and
  GPU captures agree across hosts. Malformed pointer shape/type/missing-field
  records reject without replacing live gameplay or changing saved bytes.
- `pointer-editor-checks.json`: **53 checks** in actual Qt/embedded SDL, at 125%
  DPI. Library creation, typed vector outputs, Undo/Redo and project roundtrips
  pass. Real cursor movement matches window client coordinates, drag rotates the
  robot, both wheel axes have the expected signs, Pause discards input and Resume
  resamples position without replay. Physical Save/Load preserves pose/totals
  while using the current cursor, a scrolling RmlUi region consumes wheel/motion,
  Qt panel wheel input stays outside gameplay, and Stop/fresh Play resets totals.
- `pointer-package.json`: **3 checks**. `Play.cmd` runs using only system PATH
  and reproduces the full reference state and GPU pixels from the included replay.

Total: **51 pytest cases + 307 native/editor/workflow/package checks**.
Native fingerprint: `c15606060e659fd6decb39db63edb938a4495f6ba691d7399daf8939b2ad862d`. Source, binary, evidence and package hashes are in
`artifacts/validation/pointer-summary.json`. Editor and standalone screenshots
were visually inspected.

Editable demo: `examples/pointer_demo/project.json`; Python authoring:
`tools/create_pointer_demo.py`; standalone:
`artifacts/demos/pointer-playground/Play.cmd`. Left-drag rotates the Blockbench
robot, wheel moves it nearer/farther, R resets pose and S/L save/load. The HUD
shows absolute position, per-frame impulses and accumulated motion/scroll.

Limits: cursor hiding/locking, relative mouse mode, gamepad/analog, contexts and
rebinding remain open. Linux, broader DPI/device/IME coverage and actual flipped
or high-resolution touchpad hardware were not verified. SDL's documented flipped
wheel normalization is implemented; fractional replay is verified. Physical
audio and the complete engine test suite were not rerun. NodeGraphQt distutils
deprecation warnings remain. The whole-engine goal stays active.


## 2026-10-29: Cursor visibility and relative locking

The registry has **514 builtin nodes**. Set Cursor Visible (10016) and Lock Cursor
(10017) share native actions and typed generated adapters. Lock holds the absolute
pointer anchor while accepting unbounded relative motion and hides the OS cursor.
Unlock restores the visibility request. Input checkpoint version 3 preserves
both requests and their node origin; standalone version-1/2 records upgrade with
visible/unlocked defaults. Full-game compatibility remains exact.

The SDL host releases the physical cursor on Pause, focus loss, editor Esc, graph
errors, Stop and shutdown. Pause/Load retain logical intent; focus and the explicit
editor release latch decide whether it can apply. Locked pointer events bypass
RmlUi. Replay executes logical requests without grabbing the user's cursor.

Actual desktop testing exposed SDL's top-level-only focus condition for the Qt
child HWND. Windows now builds pinned SDL 3.4.18 source with a small, hash-checked
focus adapter; SDL itself still handles relative input and confinement. Unknown
source bytes fail configuration. See [adapter details](sdl-embedded-focus.md).

Verification on this Windows host:

| Evidence in artifacts/validation | Result |
|---|---|
| cursor-regression-tests.xml | **26 pytest cases passed**, 390.965 s; no errors/failures/skips. Native interpreted/generated locked-anchor behavior, cursor registry/compiler/core, runtime-build checks and exact/idempotent/drift-rejecting SDL patch. |
| cursor-event-checkpoint-checks.json | **154 checks**, including 15 cursor checks; strict malformed cursor rollback, logical mode/origin roundtrip, legacy upgrade, existing pointer/event checks and 160 fresh-process continuation frames. |
| cursor-workflow-checks.json | **124 checks** in interpreted/generated headless/SDL hosts, relocated Unicode path and restricted PATH. Nonzero saved impulses, locked anchor, later unlock, exact fresh-process continuation, corrupt-load rollback, full-state and GPU parity. |
| cursor-editor-checks.json | **90 checks** in real Qt/embedded SDL at 125% DPI. Library/ports/Undo/Redo/save/reopen; both SDL focus flags and Windows confinement; 1,684 relative X units across a 421-unit viewport through a pointer-consuming overlay; hide/show/lock/unlock, Pause/Resume, Save/Load, Esc/reclaim, focus loss, graph error, Stop and shutdown. |
| cursor-standalone-checks.json | **16 checks**, physical exported-game keys without editor IPC, standalone Escape graph, close while locked, and a focused replay with logical lock/hidden requests that leaves the OS cursor free and visible. |
| cursor-pointer-editor-checks.json | **53 existing physical pointer regression checks** on the new SDL build: fractional/client coordinates, drag, two-axis wheel, UI interception, Save/Load and lifecycle. |
| cursor-input-events-editor-checks.json | **85 existing input-event editor checks** on the new SDL build, including action callbacks, focus, delayed input, Pause/Load and Stop/fresh Play. |
| cursor-game-checkpoint-checks.json / cursor-game-checkpoint-device-checks.json | **67 checks each**, dummy and actual WASAPI device; 132 continuation frames per run, exact PCM handoff, whole-context staged commit and rollback. |
| cursor-sdl-fetch.json | **2 checks**, archive hash validation/extraction reproduces the exact upstream focus source and installed provenance. |
| cursor-package.json | **3 checks**, Play.cmd runs with system-only PATH and reproduces the complete reference state and GPU pixels. |

Total: **26 pytest cases + 661 verification checks** (the audio checks run once
per backend). The portable SDL adapter test was rerun after its fixture stopped
depending on the download cache; its separate passing XML is retained and not
counted twice. The earlier pre-source-SDL cursor test/probe runs and failed GUI
diagnostics are historical attempts, not the final evidence for this milestone.
The GUI injector now holds the viewport click long enough for normal Windows
input delivery and asserts explicit focus reclamation.

Native fingerprint: `f68191bcd77b43d071df2587bda4197fa17ddae7f30912a3b46ddd32d5a32df6`. `artifacts/validation/cursor-summary.json` records
source, evidence, native binary, patched SDL and package hashes. Both the editor
capture and standalone robot image were visually inspected. The Problems entry
in the editor image is the deliberately injected recovery-test assertion.

Editable demo: `examples/cursor_demo/project.json`; authoring:
`tools/create_cursor_demo.py`; standalone launcher:
`artifacts/demos/cursor-playground/Play.cmd`. K/U lock/unlock, H/V hide/show,
relative movement or left-drag rotates, wheel moves, R resets and S/L save/load.
The package includes a deterministic replay and the SDL license. Rebuild the
cursor project before running `tools/package_cursor_demo.py`.

Limits: Windows 125% DPI is verified; Linux/Wayland, other DPI/multi-monitor
configurations, gamepads, analog devices and IME remain unverified. Gamepad input,
runtime rebinding and advanced camera systems are still open. The complete engine
test suite was not rerun; this is targeted regression evidence. Upstream C++
deprecation warnings remain. The whole-engine goal remains **active**.


## 2026-10-29: Gamepad axes, device queries and button events

The registry has **517 builtin nodes**. Get Connected Controllers (10018), Get
Gamepad Axis (10019) and On Gamepad Button (10020) share the native input/event
state across interpreted and generated execution. Up to 16 live devices expose
six normalized axes with an adjustable axial dead zone. Button callbacks preserve
ordered down/up edges and their controller ID through Delay and whole-game saves.
Replay version 3 accepts connection/axis/button records; versions 1 and 2 remain
accepted. Input checkpoint version 4 adds device state with atomic validation;
standalone versions 1, 2 and 3 upgrade to an empty gamepad inventory.

The SDL host enumerates and hotplugs real gamepads, gates gameplay on viewport
focus/running state, and keeps physical samples current while unfocused. Resume
and Load resample analog values and require release/repress of already-held
buttons. Gamepad reconciliation preserves the mouse click that restores focus;
remapping one device does not swallow another device's button release. Replay
does not open physical gamepads. Test-only virtual-device commands are confined
to the separate host probe executable and are absent from production hosts.

Verification on this Windows host:

| Evidence in artifacts/validation | Result |
|---|---|
| gamepad-input-tests.xml | **8 pytest cases passed**: compiler validation, scoped payloads, native interpreted/generated replay, device queries, axis dead zones, ordered edges, latent controller identity and runtime error attribution. |
| gamepad-fast-regressions.xml | **30 pytest cases passed**: core/runtime-build checks and six repeated compiler cases. Both XML files have zero errors/failures/skips. |
| gamepad-native-checks.json | **52 checks**: strict raw batches/input/event checkpoints, rollback, legacy upgrade, limits, normalization, device lifecycle, actual SDL virtual controllers, remap isolation and mouse-hold preservation. |
| gamepad-editor-checks.json | **101 checks** in real Qt/embedded SDL at 125% DPI: library/ports, Undo/Redo/save/reopen, native focus, virtual hotplug, analog motion/dead zone, button edges, Pause/Resume, focus loss, Save/Load, unplug/reconnect, latent payload, Stop/fresh Play and shutdown. |
| gamepad-workflow-checks.json | **157 checks** across interpreted/generated headless/SDL hosts in a relocated Unicode directory with restricted PATH. Exact complete-state and GPU parity, fresh-process restore, invalid-save rollback, legacy replay, and a delayed callback retaining controller 7 after disconnect and Load while controller 12 is connected. |
| gamepad-event-checkpoint-checks.json | **154 existing event/input/cursor checks**, including 160 fresh-process continuation frames and atomic malformed-data rejection. |
| gamepad-cursor-editor-checks.json | **90 physical cursor regression checks**, including actual relative confinement, focus/lifecycle, UI interception and recovery. |
| gamepad-pointer-editor-checks.json | **53 physical pointer regression checks**, including coordinates, drag/wheel, UI interception and Save/Load. |
| gamepad-input-events-editor-checks.json | **85 existing input-event editor checks**, including actions, delayed input, focus, Pause/Load and fresh Play. |
| gamepad-game-checkpoint-checks.json | **67 checks with actual WASAPI**, 132 continuation frames, exact PCM handoff, whole-context staged commit and rollback. |
| gamepad-package.json | **4 checks**: Play.cmd with system-only PATH, complete reference state, GPU pixels and a 180-frame Replay.cmd run without hardware. All 32 package files are hashed. |

Total: **32 distinct pytest cases (38 executions) + 763 verification checks**.
The six compiler cases repeated in the fast regression are counted once. Earlier
failed GUI diagnostics and intermediate native builds are historical attempts,
not the final evidence. All nine final verification reports carry native
fingerprint `f8a7efc7a6b8f54c222566e28e407c938f660fd2bded2bac99ca9159ce9b3e4f`.

`artifacts/validation/gamepad-summary.json` freezes source, evidence, binary and
package hashes. The editor capture and standalone robot image were visually
inspected. Editable demo: `examples/gamepad_demo/project.json`; authoring:
`tools/create_gamepad_demo.py`; standalone: `artifacts/demos/gamepad-playground/Play.cmd`.
Left stick moves, South turns, A/D move by keyboard, R resets and S/L save/load.
`Replay.cmd` exercises the supplied deterministic trace without a gamepad.
Rebuild the gamepad project before running `tools/package_gamepad_demo.py`.

Limits: the gamepad backend was exercised with SDL virtual controllers; no
physical USB/Bluetooth controller was connected, so individual hardware models,
wireless reconnect and mapping databases are not certified. Windows 125% DPI
was checked; other platforms/DPI/device configurations need separate evidence.
Gamepad action/axis binding authoring, durable player assignment, vibration,
touch/sensors, runtime rebinding/input contexts and advanced cameras remain
open. The whole engine test suite was not rerun. This milestone completes the
basic gamepad input path, not the entire engine; the goal remains **active**.


## 2026-10-29: Shared keyboard, mouse and gamepad bindings

The existing action/axis nodes now accept scene binding version 2: mixed keyboard,
mouse and gamepad buttons, digital D-pad directions, analog axes, per-binding
dead zone and inversion. Version 1 remains supported. Controller 0 in a binding
aggregates any connected device; analog chooses the greatest magnitude with the
lowest connection ID winning ties. Digital and analog contributions add and clamp
to [-1,1]. The low-level Get Gamepad Axis node retains its existing default-device
semantics. No node types were added; the registry remains **517 builtins**.

Mapped action edges derive from the aggregate held state at each input transition.
Switching from one held alternative to another does not invent presses/releases;
the last alternative released, including unplug, emits one release. Raw callbacks
precede mapped callbacks. Checkpoint version 4 retains version-2 definitions,
raw devices and polling edges; event/latent state retains queued callbacks and
captured Action values. Invalid data and definitions inconsistent with the saved
scene reject during staging without replacing the live game.

The existing binding dialog has Keyboard / mouse and Gamepad tabs. Gamepad rows
choose Action, Axis buttons or Analog axis with controller/dead-zone/inversion
controls. Accept remains one scene Undo/Redo operation, reloads the same native
process, and persists through save/reopen/export. An initial authoring regression
found an unintended default button on a reopened negative-only D-pad row; the
final implementation and roundtrip test preserve both directions exactly.

| Evidence in artifacts/validation | Result |
|---|---|
| input-bindings-tests.xml | **37 pytest cases passed**, 392.919 s: old/new schema validation, malformed gamepad fields, dialog error correction/Undo/Redo/save/reopen, native interpreted/generated mixed-device traces, old replay and runtime error attribution. |
| input-bindings-core-tests.xml | **24 pytest cases passed**, 9.042 s: core compiler/registry and native build freshness regressions. |
| input-bindings-native-checks.json | **90 checks**: prior gamepad/native/SDL virtual-device cases plus any/exact controller selection, analog ties/clamping/inversion, D-pad aggregation, keyboard/two-controller handoff, ordered raw/mapped callbacks, disconnect, strict malformed binding/checkpoint rejection and saved queued delivery. |
| input-bindings-event-checkpoint-checks.json | **154 event/input/cursor regression checks**, including 160 fresh-process continuation frames. |
| input-bindings-workflow-checks.json | **124 checks** across interpreted/generated headless/SDL hosts, relocated Unicode directory and restricted PATH: mixed-device gameplay, legacy keyboard replay, exact fresh-process Save/Load, invalid/incompatible binding rollback, full state and GPU parity. |
| input-bindings-editor-checks.json | **98 checks** in real Qt/embedded SDL: keyboard edits the button to East and dead zone to 0.25, invalid input remains editable, live reload keeps the process, Undo/Redo/save/reopen, analog/D-pad movement, physical keyboard-to-gamepad-to-mouse handoff, Pause/focus rearming, Save/Load, unplug/reconnect and Stop/fresh Play. |
| input-bindings-input-events-editor-checks.json | **85 existing physical input-event editor regression checks**, including action callbacks, delayed payloads, focus and Save/Load. |
| input-bindings-dialog-checks.json | **4 checks**: actual Gamepad tab selection and monitor fit, saved values visible, screenshot and unchanged exact configuration roundtrip. |
| input-bindings-package.json | **4 checks**: both launchers with system-only PATH, complete reference state/GPU equality and hardware-free 180-frame replay. |

Total: **61 distinct pytest cases + 559 verification checks**. Both final XML files
have zero errors/failures/skips. Native fingerprint: `746320def0f2dd213187023dbf07cac585869321ede60721ffc5d7a63051a64c`. All seven verification
reports use this fingerprint. `input-bindings-summary.json` freezes source,
evidence, native binaries and all 32 packaged files. The actual dialog/editor
captures and standalone robot image were visually inspected.

Editable project: `examples/input_bindings_demo/project.json`; authoring:
`tools/create_input_bindings_demo.py`; standalone:
`artifacts/demos/input-bindings-playground/Play.cmd`; hardware-free trace:
`artifacts/demos/input-bindings-playground/Replay.cmd`. Packaged defaults use South
and dead zone 0.2; the isolated editor acceptance project intentionally edits
these to East and 0.25. Its authored HUD still describes the demo defaults.

Limits: physical USB/Bluetooth gamepads and mapping databases are not certified;
gamepad delivery used SDL virtual devices through the actual host. Windows at
125% DPI was verified, not other platforms/DPI configurations. Runtime rebinding
nodes, contexts, analog-to-action thresholds, durable multiplayer device assignment
and separately persisted user binding preferences remain open. The full engine
test suite and audio regression were not rerun for this input-only change.
The complete engine goal remains **active**.


## 2026-10-29: Input contexts and held-action rearming

Two shared native nodes, Set Input Context Enabled (10021) and Is Input Context
Enabled (10022), bring the registry to **519 builtins**. Scene input version 3
adds initial enabled flags and named action/axis membership. Unassigned controls
remain available; overlapping membership uses any-enabled semantics. No context
priority or input consumption is introduced.

Disabling an action cancels pending mapped deliveries and remaining listeners in
an in-flight delivery; a logically held action emits one cleanup release.
Re-enabling suppresses an already-held action until every alternative is neutral.
Axes resume immediately. Raw input remains usable for menu controls and already
dispatched delayed graphs continue. Input checkpoint version 5 preserves runtime
enabled flags and suppression separately from authoring defaults; standalone
older input records remain readable. Full-game compatibility remains strict.

The binding dialog now has a Contexts tab and an asynchronous member selector.
Actual authoring tests create both nodes from the Library, edit initial state and
membership, reload the same native process, Undo/Redo and save/reopen. The isolated
editor test starts gameplay disabled and removes trigger from the context to
prove unassigned axes still work. The shipped demo starts enabled and assigns all
three axes. M controls its menu; S/L still save/load while gameplay is disabled.

| Evidence in artifacts/validation | Result |
|---|---|
| input-contexts-tests.xml | **25 pytest cases passed**, 385.711 s: strict schemas, dialog roundtrip/Undo/Redo, literal/dynamic invalid names, native interpreted/generated context and rearming traces. |
| input-contexts-regressions.xml | **57 pytest cases passed**, 14.106 s: existing non-native input, core compiler/registry and build freshness regression selection. |
| input-contexts-native-checks.json | **130 checks**: existing SDL virtual-device/mixed-input cases plus overlapping contexts, raw bypass, suppression handoff, in-flight cancellation, queued cleanup release, malformed atomic rollback and legacy reader coverage. |
| input-contexts-event-checkpoint-checks.json | **154 event/input/cursor checks**, including 160 fresh-process continuation frames. |
| input-contexts-workflow-checks.json | **164 checks**: four relocated native hosts with restricted PATH, exact fresh-process continuation from disabled and suppressed-held saves, malformed/incompatible rollback, state and GPU parity. |
| input-contexts-editor-checks.json | **77 checks** in actual Qt/embedded SDL: node creation, context authoring, unchanged process reload, Undo/Redo/save/reopen, physical M/S/L, SDL virtual-pad gating, Load, Pause, focus loss and fresh Play defaults. |
| input-contexts-bindings-editor-checks.json | **98 existing mixed-input editor regression checks**, including button/dead-zone edits, physical keyboard/mouse handoff, gamepad movement, Save/Load and hotplug. |
| input-contexts-package.json | **4 checks**: standalone Play and Replay under system-only PATH, complete reference-state/GPU equality, and expected 180-frame replay result. |

Total: **82 distinct pytest cases + 627 verification checks**. Both final XML
files have zero errors/failures/skips. Native fingerprint: `418bb757a6966cc672de70125805fe25d78593fa40ac95eaab2dce44f7fdf492`. All six
verification reports use this fingerprint. `input-contexts-summary.json` freezes
source files, evidence, ten native binaries and all 32 packaged files. Actual
member/table/editor captures and the standalone robot/menu were visually checked.

The pytest GUI exercise emitted a handled Windows COM diagnostic `0x8001010d`
during Qt event processing; the process continued and all 25 tests passed. The
separate full editor verifier passed on the same final sources. Early verifier
failures were repaired before acceptance: generated setter adapters needed its
registry context flag; UI gesture tests needed a selected Library item and clicks
on checkbox indicators. Captures wait for repaint before recording changed values.

Editable project: `examples/input_contexts_demo/project.json`; generator:
`tools/create_input_contexts_demo.py`; standalone launchers:
`artifacts/demos/input-contexts-playground/Play.cmd` and `Replay.cmd`.

Limits: physical USB/Bluetooth gamepads and mapping databases remain unverified;
gamepads used SDL virtual devices through the actual host. Other platforms/DPI
configurations were not tested. Runtime rebinding, priority/consumption,
analog-to-action thresholds, durable player assignment and separate binding
preferences remain open. The full engine suite and unrelated audio regressions
were not rerun. The complete engine goal remains **active**.


## 2026-10-29: Normal application quit and exit saves

Quit Application (26001) and On Application Quit (1010) bring the registry to
**521 builtins**. Requests finish their current graph/startup/frame before the
shared native shutdown helper dispatches cleanup once, drains immediate events
and bounded pending saves, and finalizes state/GPU/audio output. Normal window
close, SDL Quit, IPC quit and command-line frame limits share this path. Editor
Stop/reload reset the simulation without application cleanup; paused started
sessions do clean up. A never-started/reset preview does not save on close.

Quit intent and the dispatch guard are host state, excluded from checkpoints and
preserved across a live Load commit. A new process can resume an exit save without
closing immediately. A Load requested alongside Quit completes before cleanup;
new Load requests from inside cleanup reject. Cleanup has its own instruction
budget and at most 64 pending save requests, preventing callback-save cycles.
Latent work and timers are not awaited. Callback errors retain their source node,
exit unsuccessfully and do not retry cleanup. The editor's asynchronous shutdown
grace period is now ten seconds with an explicit log if recovery force-kills it.

The animated Blockbench demo saves on Q or normal window close, shows completion
and failure status, and resumes with L after restarting. The final counter is
updated before I/O, including on a failed save. Both new nodes create from the
Library, Undo/Redo and save/reopen through the normal authoring path.

| Evidence in artifacts/validation | Result |
|---|---|
| application-quit-tests.xml | **16 pytest cases passed**, 479.071 s: optional phase/codegen, startup/update/fixed/late boundaries, once-only dispatch, custom callbacks, action functions, latent non-waiting, actual exit saves, rejected shutdown Load, malformed IR, origin errors and bounded save cycles in both native paths. |
| application-quit-regressions.xml | **53 pytest cases passed**, 32.118 s: core/compiler, build freshness and the existing editor/IPC regression suite. |
| application-quit-native-checks.json | **35 checks**: prior clock bounds and frame-phase validation plus pending host intent across commit, once-only and failed-callback guards, graph-boundary rejection, checkpoint exclusion and fresh-state reset. |
| application-quit-game-checkpoint-checks.json | **67 combined checkpoint checks**, including **132 continuation frames** and matching PCM bytes across native state/audio/UI/physics staging and fresh-process restoration; SDL dummy audio backend. |
| application-quit-workflow-checks.json | **133 checks** in four relocated hosts under system-only PATH: requested/natural/menu exit, completed-frame save, new-process resume, simultaneous Load+Quit, failed save storage, full state and final GPU parity, and SDL quit-handler failure reporting. |
| application-quit-editor-checks.json | **57 checks**: actual Library/Undo/Redo/save/reopen, physical movement and Q, malformed reload rollback, preserved editor/graph, restart and L, paused IPC quit, reset-preview close, standalone physical Alt+F4 and asynchronous editor close. |
| application-quit-package.json | **4 checks**: Play/Replay with system-only PATH, complete reference-state/GPU equality, and early quit at frame 13 instead of the 120-frame cap. |

Total: **69 distinct pytest cases + 296 verification checks**. Both final XML
files have zero errors/failures/skips. Native fingerprint: `3fd6b29291f8c5cd5bc945e90af4e434ac025083043cbaa5a4b28dded57360cc`. All five
verification reports match it. `application-quit-summary.json` freezes source,
evidence, nine native binaries and all 32 packaged files. The actual editor,
successful/failed save and standalone-close captures were visually inspected.
Initial test-authoring mismatches (generated string spelling, continuation-task
shape and the Accepted output port) were fixed before the final native rerun.

Editable project: `examples/application_quit_demo/project.json`; generator:
`tools/create_application_quit_demo.py`; standalone launchers:
`artifacts/demos/application-quit-playground/Play.cmd` and `Replay.cmd`.

Limits: normal shutdown is verified on Windows. Force-kill, crashes, power loss
and OS shutdown deadlines cannot guarantee callbacks or saved data. Cleanup does
not veto closure; games requiring save success before closing should Quit from
On Save Completed. No asynchronous shutdown waiting/veto API, Scene Loaded,
Game Pause/Resume events or remaining platform settings are delivered here.
Other platforms, physical gamepads and real audio hardware were not retested;
the audio regression used SDL dummy output. The full engine suite was not rerun.
The complete engine goal remains **active**.


## 2026-10-29: World pause, resume and saved lifecycle state

Pause World (7001), Resume World (7002), Is World Paused (7003), On Game Pause
(1017) and On Game Resume (1018) bring the registry to **526 builtins**. The pause
flag is separate from Time Scale, takes simulation effect at the next frame, and
freezes physics, animation and scaled timer/Delay progress. Input/UI, Update/Late
Update, unscaled clocks/timers/Delay and audio continue. Repeated requests do not
duplicate callbacks; real transitions use the existing bounded, ordered event queue.
The editor's debugging Pause/Play remains independent and Stop resets the world.

Whole-game staging preserves the pause flag and pending transition deliveries,
rejects malformed clock flags without changing live state, and does not synthesize
events on Load. Older compatible version-2 clock records without the field default
to unpaused. Program/resource identity checks still apply. The Blockbench demo
shows three independent animation/timer/physics robots, transition counters,
unscaled work and P/R/S/L/Q controls authored through Python GraphBuilder.

| Evidence in artifacts/validation | Result |
|---|---|
| world-pause-tests.xml | **12 pytest cases**: binding/codegen and latent lowering; idempotence and stable ordering; immediate queries; scale 0/0.25/2; current-frame boundaries; unscaled timer and Delay resume; bounded opposing callbacks; actual paused Save/Load; action-function return ordering and malformed native IR metadata rejection. |
| world-pause-regressions.xml | **53 pytest cases**: core/compiler, runtime build freshness and existing editor/IPC behavior. |
| world-pause-native-checks.json | **60 checks**: shared clock/quit regressions plus pause timing, once-only queued events, exact staging/commit, pending delivery restoration, absence of synthetic callbacks, malformed flags/rollback, legacy clock defaults, new-scene reset and strict IR handler validation. |
| world-pause-game-checkpoint-checks.json | **67 checkpoint checks**, **132 continuation frames**, matching restored PCM; combined audio/UI/physics/resource handoff with SDL dummy output. |
| world-pause-workflow-checks.json | **162 checks** in four relocated hosts under system-only PATH: frozen/resumed simulation, input and unscaled audio/timers, changed scale while paused, fresh-process saved continuation, malformed clock rollback, quit while paused, complete host-state and GPU parity. |
| world-pause-editor-checks.json | **56 checks** through actual Library creation/Undo/Redo, save/reopen, physical P/R/S/L, independent editor debug pause, Stop/Play, rejected reload, preserved graph and a real editor screenshot. |
| world-pause-package.json | **4 checks**: both standalone launchers with system-only PATH and exact reference-state/GPU equality. |

Total: **65 distinct pytest cases + 349 verification checks**. All final reports
pass; XML files have zero errors/failures/skips. Native fingerprint: `9d0e6629cd2af204a4568d1c7437a2bebe27966f3a63e98687fcc4b357b6797c`.
`world-pause-summary.json` freezes the source/evidence, nine binaries and all
34 package files. Editor and paused/resumed GPU captures were
visually inspected. Test authoring was corrected to respect nonpersistent logs,
float-variable serialization and resampling transient frame state after Load.
The final native pytest rerun used the existing clean-built CMake directory with
normal dependency tracking and rebuilt changed native/generated units; the cache
runner is recorded in the source manifest.

Editable project: `examples/world_pause_demo/project.json`; standalone launchers:
`artifacts/demos/world-pause-playground/Play.cmd` and `Replay.cmd`. Public behavior
and boundary rules are documented in `docs/world-pause.md`.

Limits: pause affects the current single world and simulation time, not arbitrary
graph writes. Independently paused worlds and multi-scene management/Scene Loaded
remain unimplemented. Windows was verified; Linux, physical gamepads and audio
device compatibility were not retested. The audio regression used SDL dummy output.
This is targeted validation, not a full-engine test rerun. The full original-scope
engine goal remains **active**.


## 2026-10-29: Named project scenes, staged replacement and cross-scene saves

Eight scene nodes bring the registry to **534 builtins**: Scene Loaded/Load Failed,
Change/Reload Scene, active/name queries and operation status/error. Version-2
projects contain separate scene and graph documents with a chosen startup scene;
legacy projects upgrade when a scene is added. The editor creates/selects scenes,
preserves unsaved work through its normal Save/Discard/Cancel flow, selects the
open scene for Preview and the startup scene for Build, and identifies runtime
errors by scene/node. Generated scene callbacks have separate C++ namespaces.

Replacement is deferred to a frame boundary. It prepares entities, bindings,
GPU models, audio and UI before committing, preserves game clocks/pause/storage,
and discards old scene simulation and latent tasks. Scene Loaded initializes the
new world; Game Start runs once per session. Whole-game Load stages the saved
scene's bindings/resources and resumes without replaying either entry event.
Quit cancels a pending scene request; Save/Load and Change/Reload cannot both be
pending at the same boundary. Public behavior and limits: [scenes.md](scenes.md).

| Evidence in artifacts/validation | Result |
|---|---|
| scene-project-core.xml | **64 pytest cases**: manifest/version/path checks, legacy upgrade, protected new documents, immutable all-scene snapshots, scene-qualified errors, editor scene/startup selection, unsaved build edits and missing inactive documents, plus core/compiler/build-freshness/editor/IPC regressions. |
| scene-session-tests.xml | **23 native pytest cases**: 11 scene cases cover deferred transitions, reload, pause/clock preservation, conflicting requests, failure payloads, isolated function IDs, latent initialization, target-scene Load callbacks, corrupted metadata and cross-scene checkpoints; 12 World Pause regression cases also pass. Interpreted and generated execution are compared. |
| scene-session-assets.xml | **8 pytest cases passed, 1 skipped**: asset deletion/rebuild, external destination rejection, GLB/glTF prefab dependencies, changed/removed files and rollback for missing, escaping, colliding or edited resources. File-symlink rejection could not be rerun because this Windows process lacks permission to create the test symlink. |
| scene-session-time-checks.json | **60 checks**: shared clock, quit and world-pause transaction regressions. |
| scene-session-checkpoint-checks.json | **67 checks**, **132 continuation frames**: combined physics, animation, event, UI, audio/device/capture staging and new-process restoration; SDL dummy backend with matching PCM. |
| scene-session-workflow-checks.json | **160 checks** across four relocated hosts under system-only PATH: initial menu, change/return/reload, pause, unknown IDs, full-state cross-scene restoration, corrupt-save rollback, quit precedence, matching GPU frames and audio captures. |
| scene-session-editor-checks.json | **60 checks**: all eight nodes through actual Library/Undo/Redo; New/Choose Scene dialogs and startup persistence; physical C/M/R/S/L/P/U; opening audio output on the first audible scene, keeping the authored graph separate from runtime transitions, failed-asset retry/rollback and invalid-project reload preservation. |
| scene-session-build-checks.json | **12 checks**: actual asynchronous MainWindow Build Game from a clean directory, continuing Qt event processing; all-scene snapshot with an unsaved edit; subsequent source/graph edits excluded; non-entry scene model outside assets staged; built interpreted/generated games agree with system-only PATH. |
| scene-session-package.json | **4 checks**: Play/Replay launchers run without Python/Qt on PATH and match the full reference state and final GPU pixels. |

Total: **95 distinct pytest cases passed + 363 verification checks**. Final XML
files have zero errors/failures and one explicit symlink-permission skip. Native fingerprint:
`519a213167b8b366bfc980f3fd76269af068bd820542ecc050f054f8ca846b3b`.
`scene-session-summary.json` records source, evidence, nine binaries and the 34
standalone package files. The final editor and menu/level GPU captures were
visually inspected; the HUD wraps within a narrow embedded viewport.

The first native run used a clean CMake build. A missing compiler scope declaration
for Scene Load Failed payloads was fixed; a fresh pytest process reran the final
native matrix using that completed build directory with normal dependency tracking.
Save envelope validation was extended for scene metadata, and physical-input
verification waits for simulation advancement after scene resource preparation.
The original initial-run failure is retained in `scene-session-initial-native.*`;
the final passing matrix is `scene-session-tests.xml`.

Editable project: `examples/scene_session_demo/project.json`. Standalone launchers:
`artifacts/demos/scene-playground/Play.cmd` and `Replay.cmd`.

Limits: one active world with replacement; no additive scenes, asynchronous
loading/progress, persistent objects, scene-exit event or scene rename/delete UI.
Bulk scene replacement does not dispatch object-destruction callbacks. Entire
project/runtime/resource identity must match a whole-game save. Windows/Vulkan
and this desktop's keyboard/audio output were exercised; Linux, other devices and
platforms were not verified. This is targeted validation; the complete engine
suite and original-scope goal remain unfinished. The goal remains **active**.

## Function signature editing — 2026-10-29

**Graph > Edit Function Signature…** now edits the function name, port names/order,
types and input defaults, including adding/removing eligible ports. It migrates
the current scene's root calls, nested calls and Function Input/Output wiring in
one validated transaction. Stable IDs, authored literals, positions and custom
labels are retained; connected ports and non-default literals cannot be discarded.
One Undo step restores the migration, and older edits still reference their
original nodes. Canvas failure rollback is exercised by an injected creation error.
No native nodes were added: the registry remains **534**.

| Evidence in artifacts/validation | Result |
|---|---|
| function-signatures-core.xml | **88 pytest cases** for editor/core/project/Switch/function regressions and the first 14 migration cases. |
| function-signatures-edits.xml | **15 migration cases**: rename/reorder/name swaps, nested wiring, compatible/incompatible types, defaults, protected literals, dialog validation, unchanged Apply, earlier Undo history, save/reopen and injected canvas rollback. Fourteen overlap the core report; the additional case protects Function Output literals. |
| function-signatures-native.xml | **34 pytest cases**, including four new migration cases and function/latent-flow regressions. Production C++ interpreted/generated results match for all 18 renamed/reordered input/output types, nested calls, compatible type/default edits and a delayed function saved and restored in fresh native processes. A clean CMake build was retained outside pytest's temporary-directory cleanup; total run 586.57 seconds. |
| function-signatures/editor-checks.json | **31 checks** through the actual MainWindow, signature/search/body dialogs, Inspector, Library and embedded native GPU preview: one-step migration Undo/Redo, previous history, rejected removal/type edits, Cancel/no-op, defaults, pause/running reload, save/reopen and rendered robots. QTest keyboard/mouse events drive Qt controls; this does not claim new physical-device input coverage. |
| function-signatures/export-checks.json | **14 checks**: saved editor document equals export IR; CMake targets that generated source; relocated headless/SDL interpreted/generated hosts agree in complete state; GPU pixels match; standalone launcher runs with system-only PATH and matches the reference. |

Total: **114 distinct pytest cases passed + 45 integration checks**, with zero
failures/errors/skips in the three final XML reports. The core/Enter runs also
printed a Windows COM `0x8001010d` diagnostic during Qt event pumping; the processes
continued, returned zero and all assertions passed. This is retained in their logs,
not represented as a test failure or as a fixed platform issue.

Native fingerprint is unchanged:
`519a213167b8b366bfc980f3fd76269af068bd820542ecc050f054f8ca846b3b`.
`function-signatures-summary.json` records the source, reports, native binaries and
30 standalone-package files. Dialog/body/editor/GPU images were visually inspected.
The saved example was byte-compared with the actual editor-authored project.

Editable example: `examples/function_signature_demo/project.json`.
Standalone: `artifacts/demos/function-signatures/Play.cmd`. Two Blockbench robots
use Turn Robot → Angular Step after renaming/reordering their ports. Existing call
rates remain 60/-90 despite changing the new-call default to 6. At 120 fixed frames,
their rotations are `[0,120,0]` and `[0,-180,0]`, with the captured return matching.

Limits: one scene's definitions per edit; Pure/Action kind is immutable. Applying
reloads preview state instead of migrating running call frames. Existing saves
still require matching program/resource identity. Function extraction/macros,
deletion/refactoring and event/component signature migration remain open.
Windows/Vulkan was exercised; this is targeted verification, not a complete-engine
regression or cross-platform release. The original-scope goal remains **active**.

## Selection-to-function extraction — 2026-10-29

**Graph > Extract Function…** and the function editor's **Extract Function…** button
now turn a selection into a typed reusable function. Literal inputs become call
arguments, external event/loop/action values become captured parameters, and action
results become return ports. Upstream pure expressions are copied into the body
to retain evaluation at their original point of use. Expressions needed by later
outside consumers remain in the caller. Complete loops, Sequence regions, nested
calls and Delay retain their behavior. Branch/Gate paths that stop without reaching
the outside continuation get a `Continue` result and caller-side Branch; an internal
Sequence supplies the false fallback without evaluating unavailable action results.

Applying is one Undo step and preserves earlier edits. The function editor shares
Undo history across graph navigation, including when Undo removes the current
definition. Saving the function editor applies its edits in one outer transaction.
Cancel, rejected boundaries, paused/running preview reload, Library reuse and
save/reopen are exercised. No runtime nodes were added: **534 builtins** remain.

| Evidence in artifacts/validation | Result |
|---|---|
| function-extraction-core.xml | **60 passing cases**: initial 16 extraction cases plus signature and editor regressions. Extraction covers pure literals, copied lazy dependencies, mutable reads, retained outside reads, nested definitions and rejected unsafe boundaries. |
| function-extraction-editor-tests.xml | **22 passing cases**: initial three extraction editor cases, 15 signature cases and four Switch cases; this overlaps the core report. |
| function-extraction-final-core.xml | **35 passing cases**: final 16 extraction core, four extraction editor and 15 signature tests. Includes guard helper/wire Undo/Redo, earlier history, shared function-navigation Undo and dialog validation/Cancel. |
| function-extraction-native.xml | **13 passing cases** in 257.56 seconds: interpreted/generated parity before and after extraction, lazy unused overflow, reads across Delay, retained outside reads, For/ForEach/While/Sequence, external loop/event captures, multiple action returns, fresh-process restoration of a suspended extracted invocation, Branch true/false, DoOnce and closed Gate. |
| function-extraction-guarded-result.xml | **Two additional passing native cases**: delayed captured return reaches its original continuation only when the selected branch is true; false produces no outside write and neither path leaks a suspended task. Thirteen unrelated native cases were deselected for this focused run. |
| function-extraction/editor-checks.json | **27 checks** through actual MainWindow, extraction dialogs, nested function navigation, Library and embedded GPU preview. Root extraction, nested extraction, Undo/Redo, Cancel/rejection, paused/running reload, typed result use and save/reopen pass. QTest events drive Qt controls; this does not claim new physical-device input coverage. |
| function-extraction/export-checks.json | **16 checks**: saved editor source equals export IR, CMake targets that source, four relocated headless/SDL interpreted/generated hosts have identical complete state, the unextracted reference has that same state, GPU pixels match, and the standalone launcher works with system-only PATH. |

Total after deduplicating overlapping reports: **83 distinct pytest cases passed
+ 43 integration checks**. All five final XML reports have zero failures/errors/
skips. Some Qt test logs also contain Windows COM `0x8001010d` diagnostics during
event pumping; their processes continued and returned zero. This remains a platform
diagnostic, not a claimed fix. The native test build is retained in
`.cache/function-signature-native` and reused with normal CMake dependency tracking.

The native source fingerprint remains
`519a213167b8b366bfc980f3fd76269af068bd820542ecc050f054f8ca846b3b`.
`function-extraction-summary.json` records source, final reports, seven native
binaries and the 30 standalone files. Dialog/body/editor/GPU captures were visually
inspected. The saved demo was byte-compared with the actual editor-authored files.

Editable example: `examples/function_extraction_demo/project.json`. Three Gameplay
nodes become **Spin Pair** and the nested **Rotation Delta** calculation calls the
extracted **Angular Product**. Two Blockbench robots still rotate at 45/-90 degrees
per second; at 120 fixed frames their rotations are `[0,90,0]` and `[0,-180,0]`.
Standalone launcher: `artifacts/demos/function-extraction/Play.cmd`.

Limits: pure extraction currently needs one exposed result and context-free
computation; action extraction needs one entry and at most one outside continuation.
Partial structured paths, shared tails that would create an early return and
unrelated entries/exits are rejected. General macros and broader extraction remain
open. Stateful node identities move into the function's scope; existing function/
Owner sharing rules apply when reusing it. Preview reloads instead of migrating
live frames; old whole-game saves still require matching program/resource identity.
Windows/Vulkan was exercised. This is targeted verification, not a complete-engine
regression or cross-platform release. The original-scope goal remains **active**.

## Event signature editing — 2026-10-29

**Graph > Edit Event Signature…** now edits names, parameter names/order, types and
defaults, and adds/removes eligible parameters. Any selected On/Send/Broadcast/
Subscribe/Unsubscribe node opens its own event; otherwise a searchable picker lists
the current scene's events. Applying validates and migrates Gameplay handlers,
root senders and senders nested in action functions in one transaction. Stable IDs,
positions, custom labels, fixed Sender/Receiver/Recipient routing and initial
subscription settings remain intact. Existing sender values retain their parameter
identity through swaps/reordering and changed defaults; new senders use new defaults.
Connected parameters and non-default literals cannot be discarded. No builtin node
was added: the registry remains **534**.

Applying is one Undo step, preserving earlier node history. An injected canvas
creation failure restores both event/function definitions and nodes/wires. Cancel
and unchanged Apply add no history. Library creation, nested function authoring,
save/reopen and paused/running native reload use the updated signature. A two-scene
test with identical event IDs checks the complete compiled project, byte-preserved
inactive graph, save and switching back to each scene.

| Evidence in artifacts/validation | Result |
|---|---|
| event-signatures-core.xml | **85 passing cases**: the initial 17 event-edit cases plus 68 function-signature, extraction, editor and Switch regressions. |
| event-signatures-edits.xml | **18 passing cases**, superseding the earlier event-edit module: all five roles, nested sender wires, fixed routing, swaps/custom labels, protected removals, defaults/types, invalid identity/mappings, no-op, dialog validation, Undo/Redo, rollback, save/reopen and the additional actual two-scene isolation test. One earlier test was renamed; counts use the latest complete module result rather than counting both names. |
| event-signatures-native.xml | **29 passing cases** in 232.78 seconds: event regressions plus four new native migration cases. All 18 payload types preserve exact values through rename/reverse-order migration; nested senders retain defaults and routing; compatible type/new-default edits produce independent expected values; a renamed event handler suspended by Delay saves and restores its payload/sender in fresh processes, with exact keyboard/custom subscriptions. Interpreted/generated state and errors agree. |
| event-signatures/editor-checks.json | **22 checks** through actual MainWindow/Inspector, signature/search/body dialogs, Library and embedded native GPU preview: all-role selection, nested broadcaster migration, one-step Undo/Redo with earlier history, rejected edits, Cancel/no-op, paused/running reload, subscriptions, fresh defaults and save/reopen. QTest events drive Qt controls; this does not claim new physical-device input coverage. |
| event-signatures/export-checks.json | **16 checks**: editor document equals export IR; CMake targets that generated source; four relocated headless/SDL interpreted/generated hosts agree in complete state; the original event graph has that same state; expected robot rotations, matching GPU pixels and the standalone launcher pass with system-only PATH. |

Total using the latest complete result for each module: **115 distinct pytest
cases passed + 38 integration checks**. The three final XML reports have zero
failures/errors/skips. The initial native fixtures omitted an initial sum variable
and the scene needed to validate an entity receiver; a later expectation also
omitted the builtin keyboard subscription from the complete event snapshot. These
test fixtures were corrected, and the full 29-case matrix was rerun successfully.
Both earlier runs remain in `event-signatures-initial-native*` for inspection.
The core Qt run also printed the existing Windows COM `0x8001010d` diagnostic;
it continued and returned zero. This is not represented as a fixed platform issue.

The native fingerprint remains
`519a213167b8b366bfc980f3fd76269af068bd820542ecc050f054f8ca846b3b`.
`event-signatures-summary.json` records source, evidence, seven native binaries and
30 standalone-package files. The four editor-authored project/graph/scene/asset
files were byte-compared with the delivered example. Signature/body and native GPU
images were visually inspected. Native tests reused the persistent CMake build
with normal dependency tracking in `.cache/function-signature-native`.

Editable example: `examples/event_signature_demo/project.json`. **Publish Turn**
broadcasts the renamed **Rotate Notice**, whose parameters are reordered to
Note/Degrees. Changing the new Degrees default to 5 preserves the existing 15-degree
broadcast and 90-degree targeted boost. At 120 fixed frames the player reaches
`[0,210,0]`; the partner unsubscribes at one second and remains `[0,-45,0]`.
Standalone launcher: `artifacts/demos/event-signatures/Play.cmd`.

Limits: edits affect one scene. Preview reloads rather than migrating queued/live
deliveries or suspended calls. Old game saves require matching program/resource
identity. Event deletion/dynamic handlers and component-schema migration remain
open. Windows/Vulkan was exercised; this is targeted verification, not a complete
engine or cross-platform release. The original-scope goal remains **active**, with
the remaining geometry and collection nodes prioritized
before specialized work.

## 2026-10-29 — general scalar and logic math batch

The registry now contains **561 builtin definitions**. The 27-node batch adds
Modulo, Power, Sqrt, Floor, Ceil, Round, Tan, Atan2, Inverse Lerp, SmoothStep,
Remap Range, float equality and ordered comparisons, boolean XOR, integer bitwise
operations, checked integer division/modulo/absolute value/minimum/maximum and the
remaining integer comparisons. The shared C++ runtime and generated dispatch use
the same typed functions for preview and exported games. Divide/modulo by zero,
integer division overflow, negative square roots, zero interpolation ranges and
non-finite results report errors at the originating node.

The native probe exercised all 27 outputs in one graph and compared the
interpreted preview with the generated game: **27/27 values matched**, including
negative rounding and signed integer division/modulo. Four invalid-domain graphs
(float modulo, square root, integer division and integer modulo) returned matching
errors and originating node IDs in both hosts. The registry/core checks passed
after generation; the equivalent fresh native CMake build and runtime probe were
run from the existing Windows native fixture build.

Remaining Math & Geometry work includes geometry intersection/bounds nodes,
rotation helpers and additional collection
types. This batch does not complete the full 721-row catalog or the original
engine goal.

## 2026-10-29 — Vector3 geometry foundation

The registry now contains **568 builtin definitions**. Seven general Vector3 nodes
were added: Vector X/Y/Z, Angle Between, Project Vector, Reflect Vector and Rotate
Vector. `Rotate Vector` follows the runtime's existing YXZ Euler order and degree
convention. Projecting onto a zero vector returns zero; angle and reflection reject
zero-length inputs with an error attached to the source node.

A Windows native probe compared the interpreted preview and generated game for all
seven nodes: **7/7 values matched**, including component extraction, π/2 angle,
projection, reflection and a 90-degree Z rotation. Two invalid-domain graphs also
returned identical errors and originating node IDs in both hosts. The registry,
codegen and core/runtime checks passed after the generated adapter update.

The YAML port name `On` is quoted so PyYAML preserves it as a string during graph
authoring. Remaining general work includes geometry intersections/bounds and
collection types before the specialized categories.

## 2026-10-29 — Vector2/Vector4 value foundation

The registry now contains **650 builtin definitions**. Vector2 and Vector4 are
first-class runtime values with JSON serialization, scene variable declarations,
typed arrays/maps, generated adapters and editor pin colors. Sixteen general
arithmetic nodes cover construction, add, subtract, scale, magnitude, normalize,
dot product and distance for both types.

Core/runtime checks passed (**24/24**) and typed data checks passed (**14/14**).
The native probe compared preview and generated game execution for eight Vector2/
Vector4 nodes: **8/8 values matched**, including typed variable persistence and
normalization results. A follow-up native graph also round-tripped Vector2 and
Vector4 arrays/maps and retrieved typed items identically in both hosts.

## 2026-10-29 — Quaternion and Matrix foundation

The registry now contains **729 builtin definitions** and supports **30 value
types**: ten scalar forms plus homogeneous arrays and string-keyed maps. Quaternion
and Matrix4 are first-class values in Python validation, editor pins, JSON scene
variables, event/function payloads, generated C++ literals, native storage and
typed collection families.

Thirteen general nodes were added: quaternion Euler and axis-angle construction,
multiply, normalize, inverse, slerp and vector rotation; matrix identity,
multiply, inverse, point/direction transforms and transform-matrix construction.
The focused native graph compared `node_preview.exe` and `node_game.exe` with
identical JSON output. It exercised 13 stored results, including a 90-degree
rotation, transformed point `[12, 23, 0]`, transformed direction `[2, 3, 0]`,
and `M * inverse(M) = identity`. The permanent parity case is in
`tests/test_native.py`.

The CMake build completed with the 729-node generated adapter set. Full acceptance
is still open for geometry intersections/bounds, collection sets/structs/enums,
and the specialized systems listed in the original audit.

## 2026-10-29 — General geometry foundation

The registry now contains **737 builtin definitions**. Eight general geometry
nodes were added: Point In Bounds, Closest Point On Segment, Closest Point On
Bounds, Ray Plane Intersection, Ray Sphere Intersection Distance, Line Segments
Intersect 2D, Bounds Min and Bounds Max.

The native graph covered all eight nodes and compared the interpreter and generated
game with identical JSON output. It verified inclusive bounds, segment and box
clamping, a ray/plane hit at `[0, 0, 0]`, a sphere hit distance of `4`, crossing
2D segments, and extrema `[-1, -2, 0]` / `[3, 5, 4]`. The generated adapter set
was rebuilt and the standalone source was restored after the compiled-game check.

The permanent parity case is in `tests/test_native.py`. The remaining general
math gaps are screen/world projection, additional geometry primitives and
collection sets/structs/enums.

## 2026-10-29 — Camera projection foundation

The registry now contains **739 builtin definitions**. Two general camera nodes
were added: `World To Screen` (15014) and `Screen To World` (15015). They use the
same camera pose and projection matrices as the renderer, with top-left-origin
viewport pixels and normalized depth in the `[0, 1]` range.

A Windows native graph changed the camera to orthographic mode, projected world
point `[0, 2, 0]` into `[480, 320]` for a `[960, 640]` viewport, then unprojected
the center point at the matching depth. `node_preview.exe` and `node_game.exe`
returned identical JSON; the recovered world point was `[0, 2, -8.88e-16]`, the
expected floating-point roundoff. The permanent parity case is in
`tests/test_native.py`, and the native build completed successfully.

Remaining general gaps are additional geometry primitives and collection
sets/structs/enums. Full camera acceptance still has multiple viewports, masks,
blending, collision avoidance and cinematics open.

## 2026-10-29 — General geometry extension

The registry now contains **743 builtin definitions**. Four additional general
geometry nodes were added: `Ray Bounds Intersection Distance` (4128), `Closest
Point On Triangle` (4129), `Sphere Overlaps Bounds` (4130) and `Distance To Plane`
(4131). They share the existing finite-value and domain validation rules.

The native graph compared preview and generated game output for all four nodes:
ray-to-box distance `4`, triangle closest point `[0.25, 0.25, 0]`, sphere/bounds
overlap `true` and signed plane distance `2`. Both hosts returned identical JSON,
and the standalone generated source was restored after the game run. The
permanent parity case remains in `tests/test_native.py`.

The remaining general foundation gap is structs/enums plus callback-based
collection operations and additional specialized geometry. Camera blending, masks, collision avoidance
and cinematics remain open as documented above.

## 2026-10-29 — Typed Set foundation

The registry now contains **833 builtin definitions** and supports **40 value
types**: ten scalars plus homogeneous arrays, string-keyed maps and
insertion-ordered unique sets. The set family adds 80 typed nodes across
Create, Add, Remove, Contains, Length and Clear operations, plus Get/Set
variable nodes. Select now has 40 typed variants, including all ten set forms.

Set literals reject duplicate elements during Python validation. Native storage,
JSON scene/save values, generated C++ literals, editor pins and collection
iteration preserve uniqueness and insertion order. The generated adapter set
was rebuilt successfully.

A Windows native graph created an integer set, attempted a duplicate add,
added and removed values, then checked Contains, Length and Clear. The restored
variables were `items=[2,3,4]`, `contains=true`, `length=3` and `cleared=[]`.
`node_preview.exe` and `node_game.exe` returned byte-equivalent JSON for this
graph. Python type/core checks passed **41/41**. The permanent parity case is in
`tests/test_native.py`; the isolated pytest native fixture could not configure
within its 1200-second timeout, so the parity result above was run directly
against the completed project build.

The remaining general typed-data gaps are structs, enums, callback-based
collection operations and broader collection sorting/filtering/mapping.

## 2026-10-29 — Array concat and slice foundation

The registry now contains **863 builtin definitions**, adding 20 typed array
nodes: `Concat {label} Arrays` and `Slice {label} Array` for all ten scalar
element types. Concat preserves both input orders and enforces the collection
limit. Slice uses a checked half-open range `[Start, End)` and returns a new
value without aliasing the source.

The permanent parity case is in `tests/test_native.py`. A direct Windows
native graph concatenated `[1,2]` and `[3,4]`, sliced `[1,4)`, and restored
`result=[2,3,4]`. `node_preview.exe` and `node_game.exe` both succeeded and
returned byte-equivalent JSON with SHA-256
`1DE42ED4F5D41F3E89B789CF87247B58C00D3DCE3B4ACE2167F0578E2D818FF0`.
Python type/core/editor checks passed **45/45** and the project targets built
successfully.

## 2026-10-29 — For Each Set iteration

The registry now contains **843 builtin definitions**, adding ten typed
`For Each {label} Set` nodes (IDs 2350–2359). The compiler and native
continuation scheduler snapshot both arrays and sets when the loop starts;
resumed Set loops read the captured insertion-ordered values. The existing
`ArrayLength`/`ArrayGet` codegen path now has Set overloads, so the same
typed body works for both collection kinds.

The permanent coverage is in `tests/test_native.py` and checks an integer Set
`[3,1,2]` produces the visited array `[3,1,2]`. A direct Windows build ran
the exported graph through both `node_preview.exe` and `node_game.exe`; both
returned the same SHA-256 (`CC13C106AD2C5EE10844762276207E9F6E5368D19C116962CD2F6E7CCB83FCE2`)
and the expected insertion order. The Python type/core/editor suite passed
**45/45**; the isolated native pytest fixture remains limited by its clean
dependency configure timeout.

## 2026-10-29 — For Each Map iteration

The registry now contains **873 builtin definitions**, adding ten typed
`For Each {label} Map` nodes (IDs 2360–2369). Map loops snapshot their input at
entry, iterate deterministic sorted string keys, and expose `Key`, `Item` and
`Index` only inside the loop body. Array and Set loop behavior remains unchanged.

The permanent parity case is in `tests/test_native.py`. It iterates the integer
map `{"z":3,"a":1,"m":2}` and restores keys `["a","m","z"]` plus values
`[1,2,3]` through both preview and generated-game paths. The native fixture is
verified the case with **1 passed** after rebuilding its clean Jolt dependency
tree. The project `node_game` and `node_preview` targets also built successfully;
the Python type/core/editor checks passed **45/45**.

## 2026-10-30 — Shared embedded C++ and node code editor

The registry has **935 builtin definitions**, including **C++ Code (27006)**.
Action/action-result hooks are compiled once into `node-code.generated.cpp` and
registered per scene/type/node/source. Interpreted and generated execution use
the same callback, including latent continuations. Preview rejects uncompiled
snippets and the editor checks the project's hook fingerprint before reuse.

The node dialog now has line numbers, indentation, Ctrl+S and separate generated
call/runtime implementation views. Function graph editing is supported. Clang
diagnostics retain scene/node/snippet line through `#line`; Problems opens that
code line. Comments/raw strings/numeric separators are handled by structural
validation, and markers inside comments or strings do not replace the runtime call.

Direct evidence:

- `tests/test_node_code_native.py`: **5 passed**, verifying post-call effects,
  action-result mutation/output capture, Delay continuation post-call statements,
  rejection of changed uncompiled code and dedicated code nodes across scenes.
  The first reusable native build recompiled dependencies; total 497.51 seconds.
- The real compiler diagnostic case in the same module passed separately:
  undeclared `missing_symbol` is reported at `level/bad-code`, snippet line 2.
- Python/Qt regression command below: **100 passed, 94 warnings** in 78.38 seconds.
  Includes real modal save, graph Undo/Redo, save/reopen, duplicate/paste,
  function graph transactions, Problems navigation and project-specific stamps.
- `examples/embedded_code_demo/project.json` was exported, rebuilt and run for
  **120 frames** through `node_preview`, `node_game`, `node_view`, `node_game_view`.
  Complete JSON states match: `updates=120`, robot Y rotation=120 degrees and the
  expected log entry. Graphical screenshots match byte for byte, SHA-256
  `9140c203912687d5bda45084e243b8e8fc4c3b0213d83748f89e04b336aa0362`.
- Local artifacts: `.work/node-code-gui-proof/demo-verification.json`, four
  `demo-*.json` snapshots, `demo-preview.bmp`, `demo-game.bmp`, the build logs,
  `python-tests.log`, and visually reviewed `node-code-editor.png`.

```powershell
.venv/Scripts/python.exe -m pytest tests/test_node_code.py tests/test_runtime_build.py tests/test_editor.py tests/test_function_edits.py tests/test_function_extraction_editor.py tests/test_core.py tests/test_feature_pipeline.py tests/test_template_games.py -q --tb=short
$env:NODE_ENGINE_NATIVE_TEST_BUILD = 'C:/Users/son/AppData/Local/Temp/pytest-of-son/pytest-354/native0'
.venv/Scripts/python.exe -m pytest tests/test_node_code_native.py -q --tb=short
```

Windows batch Qt runs also logged handled COM exception `0x8001010d` through
pytest's faulthandler while reporting a zero exit code and all assertions passing.
The isolated visible-parent modal tests passed cleanly. This remains a GUI
reliability observation, not evidence of a complete accessibility/IME matrix.

These checks certify the embedded-code workflow and robot example. They do not
complete the five broad pipeline priorities or turn the two starter game
templates into fully playable native games. Those remain in the active goal and
the priority table in `acceptance-audit.md`.

The final generated-code view also displays actual graph arguments and the
surrounding event/flow/function body rather than only a signature. Its node-editor
suite passed **22 tests** in 19.33 seconds after that change; the new case verifies
OnStart, Branch and Set Time Scale navigation and emitted literal `0.5`.

## 2026-10-30 — Native variable scopes and ownership

Scope declarations now select separate runtime storage. Global values survive
scene changes/reloads; scene values reset on entry; entity values have live owners,
independent clone copies and deletion cleanup. Explicit Global/Scene/Entity nodes
cover the 40 builtin value types (240 variants, IDs 50000–50239), bringing the
builtin registry to **1175** definitions. Legacy nodes resolve authored scopes.
Whole-game saves preserve the namespaces together, including shadowed names;
progress saves preserve scope and named Struct/Enum tags and commit loads atomically.

`tests/test_variable_scopes_native.py` passed **7 cases** in 200.87 seconds:
scene roundtrip, entity isolation/clone/destruction, three namespaces with one
name and different types, whole-game checkpoint restoration, progress save/load,
stale-owner rejection and named Struct/Enum persistence. A further native batch
passed **4 cases** in 54.79 seconds: scoped Reload Scene, both legacy movement
parity variants and the existing scene-clock/reload lifecycle case.

The Python/Qt regression suite passed **125 cases** in 79.76 seconds. Actual
keyboard-driven scope selection, shared Undo/Redo and save/reopen assertions are
recorded in `.work/scopes-editor-proof/checks.json`; the selector screenshot was
visually reviewed. Struct/Enum values are also editable in the variable table
when their definitions are present in the scene.

All four native hosts ran the scope/collection scene for **120 frames** with
identical complete JSON state. It preserves `global_steps=120`, player entity HP
12, an explicit scene HP of 1.5, global string HP and a Vector3 array transferred
from global storage into the enemy's independent storage. The two GPU captures
match byte for byte: SHA-256
`ac86910990a23006612b211b6d36b0daff08aa87a8c88ae5b68b6af601e2ca5c`.
Artifacts are in `.work/scopes-gpu-proof/`, including `checks.json`, four host
snapshots, `view-preview.bmp`, `view-game.bmp`, generated sources and build logs.

Logs: `.work/node-code-gui-proof/scope-native-final.log`,
`scope-reload-legacy.log`, `scope-python-regression.log`.
The reusable test build is now the persistent workspace directory
`.work/pytest-collider-final/native0`; temporary pytest directories can be removed
by unrelated test-session cleanup and should not serve as long-lived caches.

Remaining typed-data work includes richer Struct/Enum graph authoring and
collection coverage. Scope acceptance does not complete the full engine goal.

## 2026-10-30 — Native Struct/Enum and collection callback execution

The native interpreter now evaluates Make/Break Struct, enum construction and
Sort/Filter/Map expressions directly instead of falling through to builtin node
dispatch. Generated C++ uses the same checked field/enum helpers and instruction
ticks. Nested fields retain their named types. Each declared Struct/Enum has
automatic and explicit Global/Scene/Entity Get/Set nodes (project-owned IDs
800000–808191; the builtin count remains 1175).

An initial **15-case native regression batch passed** in 263.99 seconds: nested
Struct/Enum storage and checkpoints, nontrivial Sort/Filter/Map results, Map
identity across all ten scalar types (including UTF-8/NUL and large integers),
dynamic invalid enum labels, eight scope cases, both movement parity variants
and nested typed functions. Subsequent restore validation rejects changed type
definitions, malformed struct fields and invalid enum labels before committing
saved values. The final **9-case native batch passed** in 310.44 seconds,
including three corrupted-save cases, all four expression cases and two named/
scoped persistence regressions. These batches overlap; their counts are not an
aggregate of unique tests.

The Python/Qt regression passed **131 cases** in 165.53 seconds. The final focused
batch passed **20 cases** in 11.99 seconds (six native cases deliberately excluded
from this Python/Qt batch). These checks cover recursive struct definitions, schema-owned defaults without document
mutation, invalid literals, callback-call cycles, ignored callback-wire rejection,
generated code, type-port colors and replacement of stale editor node classes.
The actual MainWindow proof opens eight typed nodes, navigates generated code,
saves and reopens their definitions. Its screenshot was visually inspected:
`.work/user-types-editor-proof/editor.png`; assertions and project files are
beside it. Graph-owned types used by Scene Variables are copied into the scene's
declarations so that saved scene files validate independently; Undo/Redo and
save/reopen are tested through the real modal dialog.

Logs: `.work/node-code-gui-proof/typed-execution-final.log`,
`user-values-restore-native.log`, `user-types-regression.log`,
`user-types-final-python.log` and `user-types-editor.log`.
The broad Windows Qt batch still emits the previously recorded handled COM
exception trace; assertions pass and its exit code is zero. The standalone
MainWindow proof exits cleanly. This does not close the full GUI/IME matrix.

Remaining priority-one work: definition authoring/refactoring with stable type
identities, project-wide definition synchronization, named function/event ports
and user-defined collection element types. Unsupported types now fail validation
instead of reaching unsupported native storage. The broader engine pipelines and
the complete native Flappy Bird/Snake templates remain open in the goal.

## Struct/Enum authoring and stable identities - 2026-10-30

Scene > Structs and Enums now creates, edits, renames and deletes active-scene
definitions. Field origins migrate values and Make/Break wires; stable type-node
and variable-family IDs survive reorder/refactor and retired IDs are not reused.
Referenced/destructive deletions are rejected. The shared Undo transaction keeps
earlier graph history and rolls back failed graph recreation. High component IDs
are retained by the typed registry and dispatched to components when they do not
identify a user-variable family; new component allocation avoids reserved type IDs.

The milestone's Python/Qt regression passed 162 cases, its final focused batch
passed 12 cases and its final native batch passed 3 cases. These overlapping
counts are not unique-test totals. The actual modal editor proof passed all
5 assertions, including save/reopen, nested values, stable IDs and shared Undo.
Screenshots in `.work/type-authoring-proof/` were visually inspected.
Logs are `.work/node-code-gui-proof/type-edit-regression.log`,
`type-editor-final-python.log`, `type-edit-final-native.log` and
`type-authoring-gui.log`. Project-wide synchronization, named function/event ports
and collections of user-defined elements still remain open.

## Startup project manager and .nen manifests - 2026-10-30

This user-added priority was implemented before completing the native game
templates. Starting editor.main now opens the project manager, including when a
project path is supplied. New/Open/recent projects precede editor construction.
New projects use a .nen manifest with UUID, container version, engine creation/
save/minimum versions and the named-scene layout. The project has graphs/scenes
and models/textures/audio/ui/prefabs asset folders. Compiler, native build paths
and prefab-library import accept .nen; relative documents survive relocation.
Legacy JSON layouts 1/2 remain supported. Explicit conversion retains original
files, rejects occupied targets and respects Save/Discard/Cancel. Compatible
optional metadata survives saves; unsupported/newer requirements are rejected.

The combined final Python/Qt regression passed **184 cases**, with **1 skipped**
because this Windows account cannot create the required symlink. A subsequent
graph-document root validation check and launcher/core batch passed **38 cases**.
Native interpreter and generated C++ game ran the same .nen two-scene project and
agreed exactly on startup scene `level`, score 42 and state: **1 native case passed**.
The final native rerun took 19.02 seconds. The earlier native run also passed;
these are overlapping runs, not additional unique cases.

`tools/verify_project_launcher.py` exercised the real startup entry point, New
dialog, Unicode Inspector edit, Save, Project Manager/recent history, incompatible
engine rejection without writes, and saved-project reopen/compilation: **6/6
checks passed**, process exit 0. Assertions/project files are in
`.work/project-launcher-proof/checks.json`; welcome, incompatible-version and
reopened-editor screenshots were visually inspected. No GUI crash occurred in
this standalone proof. The broad pytest Qt process still prints the previously
recorded handled Windows COM trace and dependency deprecation warnings while
returning exit 0; the full GUI/IME matrix remains open.

All five changed generators (collections, events, functions and the two game
templates) created fresh, readable .nen projects and compiled their snapshots.
Both freshly generated template manifests also passed the actual compiler CLI.
Results are in `.work/project-format-generators/checks.json`. Existing template
folders now have .nen manifests; their old project.json files remain as backups.
This does not complete their native gameplay.

Logs: `.work/project-launcher-final-regression.log`,
`project-launcher-final-boundary.log`, `project-launcher-final-native.log`, and
`project-launcher-gui.log`. See project-format.md for structure, compatibility
policy and the lack of installer/file association. The full development goal
remains active; advanced pipelines, large-game systems and complete native
Flappy Bird/isometric Snake are not certified by these startup checks.

## Project Browser layout and persistent history - 2026-10-30

The user's requested UI correction precedes resuming broader engine work. The
browser now follows Unreal's category/grid/details arrangement, with native Qt
thumbnail cards, search/sort, a preview pane and footer Open/Create controls.
Existing projects, engine versions and last-open dates are visible. Blank 2D/3D
creation uses the same browser; 2D creates a validated orthographic camera.
Original Qt-drawn placeholder art is used, not Unreal artwork.

The former ten-path settings list is backed by an independent 100-entry history
file, actual UTC open timestamps, atomic writes and an interprocess lock. Old
settings strings/lists are imported. Discovery restores access to older projects
in known or explicitly added folders without inventing historic open dates.
Converted .nen history collapses its legacy backup entry without deleting files.
Injected settings isolate verification history from normal user settings.

The browser/project/function/event GUI regression passed **74 cases** in 66.14
seconds. The subsequent interaction batch passed **9 cases** in 1.50 seconds,
covering restart persistence in a separate process, legacy order, keyboard open,
added-folder persistence, no creation on template activation, real 2D creation
and primary controls within a 960x570 window. These batches overlap. The final
browser/project batch, including backup-history collapse, passed **38 cases** in
19.39 seconds: `.work/project-browser-release-tests.log`.
The standalone entry-point flow again passed all **6/6 checks**, exit 0, with
screenshots/project/assertions in `.work/project-browser-release-proof/`.
The default and compact recent/new-project layouts were visually inspected;
working captures are also in `.work/project-browser-design/`.

Logs: `.work/project-browser-final-regression.log`,
`project-browser-interaction-tests.log`, `project-browser-release-tests.log`, and
`project-browser-release-proof.log`. Windows pytest still sometimes prints the
previously noted handled COM notification trace; the standalone proof exits cleanly.
This milestone does not certify full engine GUI/IME acceptance or complete the
native game templates. The original goal remains active.


## 2D/3D presets and compatible suggestions - 2026-10-30

Kept Blank 2D and Blank 3D as camera/authoring defaults, with one runtime and
project format. Registry workflow metadata now drives a saved Node Library
selector: 2D + shared, 3D + shared, all compatible. Quick add, port search and
function editors use the same suggestion filter. Existing hybrid nodes survive
filter changes and reopen, and compilation is unchanged by the preference.
Unknown node types, mismatched Vector2/Vector3 links and invalid function scope
are rejected before replacement of the active graph. Resource requirements
remain runtime-validated; this is not a guarantee against arbitrary game logic
errors or an implementation of separate planar physics.

The final project/preset batch passed **46 cases**; the graph/editor batch passed
**54 cases** (overlapping suites). The real startup/New/Save/history/reopen flow
passed **6/6 checks**, exit 0. Screenshots were visually reviewed. Logs are
`.work/workflow-final-project-tests.log`, `.work/workflow-graph-regression.log`
and `.work/workflow-project-browser-proof.log`.

Both orthographic and perspective hybrid scenes passed native interpreted/Game
parity (**2 cases** in `.work/hybrid-named-regression.log`; that intermediate
batch also recorded two unrelated stale test-fixture failures, addressed in the
next named-port batch). The same orthographic project was rebuilt with all four
native hosts: node_preview, node_game, node_view, node_game_view. After 30 frames,
all state matched exactly and the two GPU captures were pixel-identical at
960x640. Sprite state, tilemap, six-joint Wave clip, box/sphere bodies and the
camera ran in one graph. Assertions and the reviewed rendered image live in
`.work/hybrid-scene-proof/checks.json` and `hybrid.png`; process logs are in
`.work/hybrid-four-host-proof.log`. The project is a verification fixture, not a
completed game template. Full GUI/IME coverage and both native games remain open.


## Named function/event ports follow-up - 2026-10-30

Returned to priority 1 after the project-browser/workflow correction. The named
port/signature/type-editor/extraction Python and Qt batch passed **63 cases** in
110.34 seconds (`.work/named-ports-release-python.log`). This closes the prior
extraction fixture assumption and empty signature-schema defaults regressions.
The all-40-builtin-type function/event fixtures now partition signatures within
the existing 32-port limit and explicitly select automatic scene-variable nodes,
instead of accidentally selecting explicit global setters by registry order.
Project-wide type synchronization and user-defined collection elements remain
required; named-port support does not complete priority 1 or the whole goal.


The final native follow-up passed **7 cases** in 126.00 seconds, covering all
40 builtin function/event value types and five named Struct/Enum cases including
nested delayed frames, queued payloads, checkpoint resume and invalid restoration
rollback. Both native backends matched. Log:
`.work/named-ports-release-native.log`. These close the four previously recorded
function/event regression failures without increasing signature limits.


## Project-wide Struct/Enum synchronization - 2026-10-30

The project manifest now owns an optional type library. Editing Structs/Enums
collects all scenes, remaps legacy ID collisions, reserves component IDs across
the project and migrates gameplay/function/event ports, literals and nested
values together. One Undo includes inactive documents and project metadata,
including Undo after Save. New scenes inherit the canonical schema. Legacy
same-name/different-definition conflicts offer local scene renaming in the editor
before synchronization. Embedded C++ rewriting remains manual.

Changed scene/graph files are prepared together before Save, with the manifest
published last, exception rollback and detection of external file changes.
Multi-file power-loss/crash recovery is not certified. Unknown or conflicting
local/project schemas are rejected; source files are retained on failed edits.

The final project/type/editor/workflow regression passed **63 cases** in 92.86
seconds (`.work/project-types-release-regression.log`). The core migration batch
passed **16 cases** before the subsequent conflict workflow and manifest-save
boundary additions; these are overlapping batches, not additive totals.
The actual Qt library/signature dialogs, project Undo/Redo, Save, inactive-scene
reopen and newly-created-scene inheritance passed **8/8 checks**, exit 0. Saved
projects, assertions and reviewed screenshots are in
`.work/project-types-release-proof/`; log: `.work/project-types-release-proof.log`.

The interpreted/generated native batch passed **2 cases** in 42.89 seconds
(`.work/project-types-release-native.log`): project startup compatibility plus
refactored nominal globals across a scene change and Save/Load. The checkpoint
returns health=42 after it was mutated to 99; native states match exactly.
The replay stops at the restoration boundary because restoring the game clock
also replays later scheduled input, as expected. User-defined collection
payloads remain the next priority-1 gap; broad GUI/performance acceptance and
both complete native games remain open. The full development goal stays active.


Subsequent checks passed **15 schema/identity/editor/save-boundary cases** in
48.19 seconds (`.work/project-types-final-boundaries.log`), including malformed
project libraries, implicit IDs that could otherwise retarget nodes, and failures
while replacing either a scene or the final manifest. The final actual Qt proof
again passed **8/8** with no errors in `.work/project-types-final-proof/`.
The on-disk .nen project/native checkpoint rerun passed **1 case** in 25.61 seconds
(`.work/project-types-file-native.log`). These are overlapping checks. Undo now
updates only type-owned project metadata, retaining later node-suggestion and
startup-scene choices; the targeted Undo/type-editor batch is recorded in
`.work/project-types-undo-regression.log`.

## Struct/Enum collection follow-up - 2026-10-30

Nominal arrays, maps and sets now support typed variable scopes, operations,
Select, For Each and Sort/Filter/Map callbacks. Empty values keep their nominal
type. Function/event selectors, nested Struct fields, queued payloads, Delay,
checkpoint restoration and project refactors use the same schemas. Recursive
Structs and nested collections remain unsupported.

The current Python/editor batch passed **58 cases**, including nominal values,
type refactors, project libraries, variable authoring and the node code dialog:
`.work/user-collections-resumed-python.log`. The native collection run passed
**9 cases** and exposed four invalid diagnostic fixtures that assigned two types
to one variable name. After using distinct names, all **4 diagnostic cases**
passed in `.work/user-collections-error-identity-final.log`. The initial mixed
result is retained in `.work/user-collections-resumed-native.log`; these two
runs cover the module's 13 cases. They exercise 56 Struct/Enum operations,
callbacks, typed function ports, queued/delayed checkpoints, invalid save rollback,
error node identity and global/entity storage across cloning and scene changes.

The actual Qt authoring/code/refactor/save/reopen proof passed **8/8**, zero
errors: `.work/user-collections-final-proof/checks.json`. The corrected authored
hook uses the native `rt::Print` API. The four-host build succeeded in
`.work/user-collections-final-build.log`; a fresh run of that saved .nen project
passed **27 checks** in `.work/user-collections-four-host/checks.json`. All four
complete native states match, including sorted nominal values and one execution
of the edited C++ hook. Both graphical framebuffer captures match. The node code
dialog screenshot was visually inspected. This fixture proves collection/code
integration; it does not certify full gameplay, large-project performance,
accessibility/IME, either unfinished game template or the overall engine goal.
