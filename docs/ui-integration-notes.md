# Repository audit and integration decisions

Audit: 2026-10-25. The initial workspace contained only `spec.md`, `design.md`,
`node_index.md`, and `node_index_lib.md`; no source, existing API, tests or Git
repository existed. The design's reference to an existing backend is therefore
an assumption, not an implementation to preserve.

The editor is Python/PySide6, with NodeGraphQt behind an adapter. Games execute
in a separate C++/SDL3 process, without Qt or Python. Preview and exported code
must call the same typed runtime functions. Node IDs are stable integers and a
single registry drives editor ports, interpreter adapters and code generation.

The dependency table's QtNodes recommendation conflicts with spec.md's
NodeGraphQt; use NodeGraphQt, as the explicit Python editor requirement takes
precedence. Optional large UI libraries are not needed. Native QDockWidget and
QSettings implement the Obsidian shell.

Current milestone: both a headless C++ semantic runner and an SDL3 callback/GPU
application. The Windows native window embeds through QWindow.fromWinId and
createWindowContainer. The Qt editor owns a QLocalServer; the runtime connects
over a Windows named pipe. Messages are length-prefixed UTF-8 JSON (uint32 LE,
protocol version 1, maximum 16 MiB). The visual runtime collects SDL button events,
including focus-loss releases, before each update; all four executables support
frame-indexed input replay. Scene-owned keyboard/mouse actions and digital axes
share typed native functions and an Undo/Redo binding dialog. On Windows, clicking
the foreign child HWND explicitly sets native focus; Esc returns it to Qt before
restoring graph focus. Qt focus changes now restore the native Qt HWND and send
a release-all input transition over IPC, because embedded SDL does not reliably
emit a window-focus event when a Qt panel is clicked. See input.md for semantics
and the real desktop verification.
The SDL 3.4.18 Windows build now includes a hash-checked child-window focus adapter
so relative mouse mode also sees native focus and constrains the actual cursor.
Locked pointer events bypass RmlUi; keyboard propagation retains its existing UI
policy. Pause, editor Esc, focus loss, graph errors and shutdown release the OS
cursor while preserving game requests where appropriate. See
[SDL adapter](sdl-embedded-focus.md) and [input](input.md).
Gamepad devices now feed that same native frame input and event queue. SDL retains
background hardware samples so returning focus can read the current stick position;
the host gates their gameplay delivery on focus/running state. Physical Pause/Load
reconcile live devices and suppress previously held buttons. Virtual-controller
acceptance uses a separate probe executable built from the production app source;
its test-control IPC commands are absent from the shipping hosts. See [gamepads](gamepad.md).
The binding dialog now adds a Gamepad tab for digital buttons and analog axes.
Both tabs author the same scene action/axis names; version 1 stays supported and
gamepad rows use version 2. Undo/Redo, validation, scene reload and export reuse
the existing path. The shared native input layer computes aggregate action edges
for every physical transition, including unplug, and combines digital/analog axis
values. No new parallel gameplay evaluator or node family is introduced. See
[input bindings](input-bindings.md).
The third binding tab authors named input contexts with initial enabled state
and member selection. Two runtime nodes gate shared action/axis reads and mapped
callbacks, with held-action rearming and staged checkpoint restoration. Raw input
remains available for menu keys. The member selector opens asynchronously inside
the existing scene dialog; acceptance uses the same Undo/Redo/reload transaction.
See [input contexts](input-contexts.md).
The native app now handles Quit Application, normal window close and IPC shutdown
at a frame boundary, dispatches On Application Quit once and drains bounded exit
saves. The editor stays open when its game quits and asynchronously waits for
cleanup when the editor itself closes. Stop/reload remain simulation resets.
See [application quit](application-quit.md) for persistence and timeout semantics.

World Pause leaves native input/UI dispatch, Update and Late Update running with
scaled delta zero, enabling menus and Resume controls. Editor Pause continues to
suspend the complete loop without generating game lifecycle events. Both modes,
physical P/R/S/L, malformed reload rollback, Library Undo/Redo and paused save
restoration are verified through the actual editor; see [world pause](world-pause.md).
Flecs 4.1.6 now routes owner-specific timer and typed custom events through native
observers. Project-defined event signatures generate typed editor nodes and
native handlers; Send/Broadcast queue immutable payloads with deterministic
subscription cancellation. Define Event participates in shared Undo/Redo;
action function graphs inherit the project's event definitions.
Flecs now owns Transform, Identity, Mesh, Tags and Activity components and ChildOf relations;
the stable-ID lookup contains handles only. Renderer queries include runtime
spawns/clones. Scene-owned typed user components are stored as Flecs pairs with
deep value copies, property nodes and Inspector authoring. Active ancestry gates
rendering and owned timer/event delivery. Prefab assets resolve variants and nested
dependencies; native instances use real Flecs IsA and own components on mutation.
Editor capture/placement, shared undo, save/reopen and native/GPU parity are
verified. Editor Apply/Reset propagates authored templates and reloads the native
scene. Gameplay Reset restores the live instance without resetting simulation,
and explicit component/property writes survive snapshots and template propagation.
Gameplay Apply propagates templates in the live world; independent nested-instance
reconciliation, external-library authoring, and runtime entity inspection remain pending. The current Python package
uses PySide6-Essentials, which contains Qt Widgets and avoids unused WebEngine.

The GPU renderer supports multiple static mesh entities with triangle geometry
and material base colors, PNG/JPEG textures, UV transforms, samplers/mipmaps and
opaque/mask/blend modes (see textures.md). Instances share one GPU allocation per
mesh asset in the scene. Skins are rejected explicitly. Replacement prepares every new
mesh before swapping resources, so a failed import preserves the previous scene.
Loading a meshless scene clears old GPU geometry. Camera framing accounts for
transformed bounds and narrow viewports. Runtime material nodes, lighting and animation
remain separate milestones; Flecs hierarchy and typed components are implemented.

Graph and scene edits share the NodeGraphQt QUndoStack via domain SceneCommands.
Entity IDs survive rename/undo/save and change on duplication. Selection updates
do not push commands from within undo/redo. The adapter removes NodeGraphQt's
competing window-wide undo accelerators; the editor owns those shortcuts.
Scene transforms update the runtime through IPC, including undo. Structural edits
request an IR reload; playback resumes only after a successful acknowledgement.
Imported files remain resources when mesh assignment is undone. Relative buffer
and image dependencies are copied with glTF/GLB files after dependency preflight.

Layout state is saved through QSettings; independent layouts per workspace and
migration recovery are pending. BuildService invokes CMake asynchronously, with an
owned process-tree cancel action; shared precompiled runtime reuse across projects
is pending. A capture_done event confirms GPU readback and file output completed;
capture command acknowledgement alone does not prove a usable image exists.

No existing UI screenshot or compatibility migration can be recorded before
version 1, because no implementation existed. Unsupported systems must be
marked unavailable, with no successful placeholder actions.

## Integration map

| Action | Boundary | Verification |
|---|---|---|
| Create/connect/edit node | registry -> graph document -> validation | typed links, undo, round-trip |
| Drag port to empty canvas | live wire -> current graph signatures -> typed endpoint search -> shared undo transaction | physical Windows drag/keyboard, cancel/replacement preservation, Inspector validation, stable save/reopen and native preview; see node-search.md |
| Preview | validated IR -> native runtime | real process, logs, frames |
| Build | IR -> generated calls -> CMake/Ninja | compiler exit status, executable |
| Import model | asset importer -> project asset manifest | real Blockbench sample |
| Play/Pause/Stop | runtime client -> runtime state | state acknowledgement |
| Named timers | registry -> typed runtime scheduler -> Flecs observer -> handler | native parity, pause/reset, GPU demo |
| Typed custom events | project signature -> typed nodes -> bounded queue -> Flecs observer | 18 payload types, subscription cancellation, GUI authoring, native/GPU parity |
| Prefab capture/instantiate | scene asset library -> compiled templates -> Flecs Prefab/IsA | real Qt dialogs, stable mappings, owned components, Undo/Redo, snapshot roundtrip and GPU equality |
| Prefab authoring Apply/Reset | scene transaction -> dependency reconciliation -> native scene reload | live IsA/ownership, structural changes, retired IDs, Cancel/Undo/Redo, save/reopen and editor-built GPU parity |
| Gameplay prefab Reset | registry -> shared typed runtime -> existing Flecs world | restored IDs/IsA, timer/event continuity, stale-delivery cleanup and native/GPU parity |
| Gameplay prefab Apply | C++ transaction -> dependency resolution -> validated candidate -> existing Flecs world | authoring equivalence, propagation/overrides, surviving listeners, rejected transaction state, and editor-built GPU parity |
| Nested prefab adoption | complete child instance -> source binding and parent patches -> containing instance membership | retained IDs/source dependencies, child delivery continuity, cross-binding references, Undo/Redo/save/reopen and GPU equivalence |
| Prefab file/library import | file/project selection -> validated dependency library -> staged model copies -> one scene undo command | registration, source independence, library/schema conflicts, rollback, live reload and packaged preview/export parity |
| Explicit component writes | Inspector or gameplay node -> property/presence masks -> snapshot/reconciliation | equal-value writes, independent instances, Undo/Redo, save/reopen and packaged GPU parity |
| Input bindings | scene actions/axes -> SDL transitions -> shared polling nodes | physical Windows keyboard/mouse, Esc/Qt focus recovery and deterministic native replay |
| Game cameras | scene/Inspector lens -> Flecs camera -> shared Follow/Look At -> SDL_GPU matrices | active selection Undo/Redo/reload, prefab persistence, physical projection toggle and packaged GPU parity |
| Material library and instances | asset/Inspector transaction -> Flecs material binding -> per-draw GPU uniforms | real dialogs/selection, Undo/Redo pixels, independent instances, prefab dependencies, reload recovery and relocated game parity |
| Save workspace | QMainWindow -> QSettings | restart/restore |

## Development order

See `roadmap.md`. This document records actual boundaries and deviations as they
are implemented; it does not claim that the integration map already works.
