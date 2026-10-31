# Node_Engine / Obsidian Studio

Python visual game editor under construction, following spec.md, design.md,
node_index.md and node_index_lib.md. The development goal remains **active**.

The working milestone is a **desktop graph editor with a native scene preview**.
Python authors/validates graphs and generates C++; interpretation and compiled
execution call the same native typed functions. The SDL3/Vulkan preview embeds
in the PySide6 editor on Windows. The exported game does not require Python or Qt.
The full engine is still under development; supported boundaries are below.

Start with `python -m editor.main` to open the **Project Manager** first. Create
a new project or open a `.nen` file/recent project before entering the editor.
New projects have a `.nen` manifest with project identity, engine compatibility
and relative references to scenes/graphs/assets. Existing `project.json` files
remain supported; **File > Convert to .nen…** retains the original as a backup.
See [project structure and versions](docs/project-format.md).

**Help > Node Help…** or **F1** on a selected node opens the offline reference:
purpose, current typed IO, steps, native node preview and real template graph
examples. It also works in function graphs. See [Help](docs/node-help.md).
**File > Project Markdown…** (**Ctrl+Shift+M**) reads, creates, edits and previews
project-local `.md` files with tables, code and relative images. New projects get
a README and a project `.gitignore`; both game templates include `docs/guide.md`.
Follow the complete [Flappy Bird guide](docs/games/flappy-bird.md) or
[Isometric Snake guide](docs/games/isometric-snake.md), including every node and
wire. See [workspace output and cleanup](docs/workspace-hygiene.md).

The Project Manager now follows Unreal's category/grid/preview layout, with
search, sorting, Blank 2D/3D creation and persistent recent history. Existing
projects are discovered in known folders; use **Add project folder…** for other
locations. Previously untracked projects appear as existing projects without
invented open dates.

Blank 2D/3D are starting presets for camera settings and node suggestions. The
same scene and gameplay graph can combine sprites, tilemaps and animated models.
**Node Library > Node suggestions** offers 2D + shared, 3D + shared, or all
compatible nodes. Port search also checks exact value types; loading validates
graphs before replacing the current graph. See [2D/3D workflows](docs/node-workflows.md).

Drag a node port into empty graph space to search compatible nodes and choose
the exact port to connect. Creation and connection use one Undo step; Esc cancels.
This also works inside function graphs. See [connected node search](docs/node-search.md).

`examples/entity_lifecycle_demo/project.json` adds **On Object Created, Enabled
and Disabled**. T toggles a parent and its Blockbench robot children, N spawns a
prefab, C clones, X destroys the last spawn, R resets a prefab, and S/L save/load
the exact event state. Inactive receivers still receive lifecycle notifications.
See [entity lifecycle events](docs/entity-lifecycle.md).

`examples/entity_destroyed_demo/project.json` adds **On Object Destroyed**. The
callback reads the object before deletion and drops loot, including during
prefab Reset/Apply. A attaches a temporary child, P applies prefab overrides;
the other keys match the lifecycle example. The standalone launcher is
`artifacts/demos/entity-destroyed-playground/Play.cmd`.

`examples/input_events_demo/project.json` adds keyboard, mouse and mapped action
entry nodes. Space/left mouse rotate the robot, A/D move it and S/L save/load,
including a suspended input callback. Quick taps retain transition order; the
native package is `artifacts/demos/input-events-playground/Play.cmd`.
See [input](docs/input.md).

`examples/pointer_demo/project.json` reads mouse position, relative motion and
two-dimensional scroll. Left-drag rotates the Blockbench robot; wheel moves it
nearer/farther; S/L save/load. The native launcher is
`artifacts/demos/pointer-playground/Play.cmd`.

`examples/cursor_demo/project.json` adds **Set Cursor Visible** and **Lock Cursor**.
K/U lock/unlock, H/V hide/show, relative motion rotates the robot, and S/L save/load.
Esc releases the cursor; editor Pause, focus loss and errors release it too.
The standalone launcher is `artifacts/demos/cursor-playground/Play.cmd`.
See [cursor behavior](docs/input.md#cursor-visibility-and-relative-lock).

`examples/gamepad_demo/project.json` adds **Get Gamepad Axis**, **On Gamepad Button**
and **Get Connected Controllers**. Left stick moves, South turns, and S/L save/load
including delayed controller payloads. The standalone launcher is
`artifacts/demos/gamepad-playground/Play.cmd`; its replay also runs without hardware.
See [gamepads](docs/gamepad.md) for dead zones, focus handling and verification limits.

`examples/input_bindings_demo/project.json` shares the same actions and axes across
keyboard, mouse, D-pad and analog sticks. Edit them in **Scene > Input Actions and
Axes**. The standalone demo is `artifacts/demos/input-bindings-playground/Play.cmd`;
`Replay.cmd` runs without hardware. See [input bindings](docs/input-bindings.md).

`examples/input_contexts_demo/project.json` adds **Set Input Context Enabled** and
**Is Input Context Enabled**. M toggles gameplay controls and the menu; S/L still
save/load. Closing the menu requires releasing held action buttons before a new
press. Author groups in the **Contexts** tab of the binding dialog. Run
`artifacts/demos/input-contexts-playground/Play.cmd` or its hardware-free replay.
See [input contexts](docs/input-contexts.md).

`examples/application_quit_demo/project.json` adds **Quit Application** and
**On Application Quit**. Q saves the robot through the quit callback and closes
the game; reopening and pressing L resumes that checkpoint. Normal window close
uses the same cleanup path. Run `artifacts/demos/application-quit-playground/Play.cmd`
or its hardware-free Replay.cmd. See [application quit](docs/application-quit.md).

`examples/world_pause_demo/project.json` adds **Pause/Resume World**, **Is World
Paused** and **On Game Pause/Resume**. P/R freeze/resume animation, physics and
scaled timers while UI, audio and unscaled work continue; S/L retain that state
across Save/Load. Run `artifacts/demos/world-pause-playground/Play.cmd` or Replay.cmd.
See [world pause](docs/world-pause.md).

`examples/scene_session_demo/project.json` adds **named scenes with separate
graphs**, Change/Reload Scene and scene lifecycle/status nodes. Use **Scene >
New Scene… / Choose Scene… / Use as Startup Scene** in the editor. C enters the
level, M returns to the menu, R reloads, and S/L restore the complete saved scene.
Run `artifacts/demos/scene-playground/Play.cmd` or Replay.cmd.
See [scenes](docs/scenes.md).

`examples/stateful_flow_demo/project.json` demonstrates Do Once, Do N, Gate and
Flip Flop on an animated Blockbench robot. O lifts once, N steps up to three
times, G toggles rotation, F alternates size, R resets and S/L save/load the
entire game including gate state. See [flow control](docs/flow-control.md).

`examples/multi_gate_demo/project.json` uses Multi Gate to tour four stations:
Space chooses a route, M toggles random selection without repeats, T toggles
looping, R resets the tour/seed and S/L save/load the partial cycle and random
stream. The node supports 1-8 active routes with a captured Index output.

`examples/random_demo/project.json` demonstrates seeded random position, dice
rolls, a bonus robot, item/weighted-loot choices, shuffled cards and a small robot
marking a random unit direction. Space draws,
R resets seed 42, and S/L save/load the exact
random stream. Preview and generated games share the sequence; see [random nodes](docs/random.md).

`examples/time_demo/project.json` demonstrates shared time scale across an
animated robot, a timer-driven robot and a physics body. Keys 0/1/2/3 select
freeze/quarter/normal/double speed; S/L save and restore both clocks and scale.
Input remains responsive while frozen. See [game clocks](docs/time.md).

`examples/unscaled_timer_demo/project.json` compares scaled and unscaled timers
on two Blockbench robots. 0 freezes game time while the right robot keeps turning;
R freezes and automatically resumes after two seconds. 1/2/3 select
normal/quarter/double speed, P/U pause/resume the right timer, and S/L save/load.
Start Timer exposes an optional Unscaled input. See [timers](docs/timers.md).

`examples/late_update_demo/project.json` follows a moving, animated Blockbench
robot with a camera from **On Late Update**, after the current frame's physics
and animation. A/D change direction, Space stops movement, 0/1/2 control time,
and S/L save/load from late callbacks. See [frame events](docs/frame-events.md).

`examples/input_demo/project.json` is an interactive Blockbench robot: click the
viewport, move with WASD/arrows, turn with Space/left mouse, and reset with R.
**Scene > Input Actions and Axes…** edits bindings with Undo/Redo. Esc returns
keyboard focus to the editor. See [input and replay](docs/input.md).

`examples/camera_demo/project.json` adds a camera that follows the robot and
looks at it. Press C to switch perspective/orthographic. **Scene > Create Camera**,
**Choose Active Camera…** and Inspector **Edit Camera…** author camera entities.
Uncheck **View > Game Camera** for free editor orbit. See [game cameras](docs/camera.md).

`examples/material_demo/project.json` shares a material across three Blockbench
robots. T tints the center instance, F fades it, O restores its imported materials,
and R resets the shared assignment. **Scene > Materials…** edits the asset library;
the Inspector assigns materials and edits instance parameters with Undo/Redo.
See [materials and nodes](docs/materials.md).

`examples/sprite_demo/project.json` demonstrates a shared four-frame atlas.
Space advances the top-left sprite; X/Y toggle flips. **Scene > Sprites…** imports
images and edits atlas dimensions; the Inspector assigns sprites and frames.
See [sprites and nodes](docs/sprites.md).

`examples/audio_demo/project.json` plays a looping tone and an independent short
effect. Space plays the effect; P/R pause/resume, S stops, V lowers volume,
M mutes and L restarts. **Scene > Sounds…** imports audio; Play Sound nodes select
assets and name independently controlled voices. See [audio and nodes](docs/audio.md).

`examples/ui_demo/project.json` displays a HUD over the Blockbench robot. Add point
increases its score and rotation; Enter submits a player name, the slider changes
a graph variable, and the checkbox enables the button. **Scene > UI Templates…**
creates or edits reusable RML templates. See [game UI and nodes](docs/ui.md).

`examples/persistence_demo/project.json` saves the robot's score, player name and
rotation. Click Add point, enter a name, then Save; Load or restart the game to
restore progress. Fifteen persistence nodes support per-game slots, typed
variable batches and JSON records. See [persistence](docs/persistence.md).

`examples/game_save_events_demo/project.json` adds **On Save/Load Completed/Failed**
handlers that update the HUD after processing. Use Save/Load or S/L; F/M demonstrate
invalid-save and missing-load errors. The four native paths pass 82 state/GPU
checks; details and boundaries are in [persistence](docs/persistence.md).

`examples/game_save_demo/project.json` saves the running robot, camera, timer,
sound, HUD and game clock. Click Save/Load or press S/L; reopening loads the saved
checkpoint. Save/Load requests finish after the current graph/frame. This initial
implementation requires the same program/assets and has documented UI/audio
limits; see [game checkpoints](docs/persistence.md#save-and-load-the-running-game).

`examples/physics_demo/project.json` places the Blockbench robot on a collidable
floor. W/A/D or arrows apply force, Space jumps, R resets, and S/L save/load the
running physics simulation. Its graph uses rigid-body nodes and `On Fixed Update`;
see [physics](docs/physics.md) for supported shapes, scales and remaining work.

`examples/physics_authoring_demo/project.json` authors the robot, floor and trigger
colliders in the entity Inspector and keeps the robot as a prefab. Add/Edit/Remove
Rigid Body, Undo/Redo and prefab Apply/Reset use the same native physics as graph
creation; Save/Load preserves initial settings and live motion separately.

`examples/physics_events_demo/project.json` adds collision/trigger Enter/Stay/Exit
handlers and HUD status. C loads the checkpoint saved automatically on collision;
S/L retain the regular save slot. Handlers support an entity receiver or the whole
scene, with typed entity, contact-point and normal outputs.

`examples/character_demo/project.json` uses a Jolt character controller: W/A/D or
arrows move, Space jumps, C crouches and V tries to stand beneath the low roof.
S/L save/load the running character. Enable **Character controller** in the
entity's collider dialog; eight character nodes share scene/prefab lifecycle and
both native execution paths. See [characters](docs/characters.md).

`examples/character_events_demo/project.json` adds collision/trigger callbacks and
HUD status. K reloads the checkpoint created on the robot's first landing; S/L
retain the regular game save slot.

## Open the 3D example

~~~powershell
.\.venv\Scripts\python.exe -m editor.main examples\blockbench_demo\project.json
~~~

Click **Open Project** in the manager, then **Play** to see the robot rotate at 45 degrees/second. The native viewport
reads D to move right; right drag orbits the camera, the wheel zooms, and Esc
returns focus to the graph. Pause freezes execution; Stop resets the scene.
Tab adds nodes, Home frames the graph, and Ctrl+S saves the project. Select a
node/entity to edit its properties in the inspector. Ctrl+B builds the game;
Build > Run Built Game launches the resulting standalone executable.

To start your own game, use **File > New Project** (Ctrl+N) and choose a new folder.
The Scene menu creates, duplicates, renames and deletes entities. Select an entity
before Import Model to assign the model to it; with no selection, import creates
an entity. Double-click a glTF/GLB in Assets to instantiate it again. Scene and
graph edits share Undo/Redo; Ctrl+Z works in the hierarchy and graph while text
fields keep their normal text-editing behavior. Imported files remain in the asset
library when an assignment is undone. Structural scene changes reset the preview.

`examples/scene_demo/project.json` is a second example authored through the editor:
two independently transformed robots sharing one GPU mesh, including an external
glTF buffer dependency. Its graph rotates only the left robot.

`examples/collections_demo/project.json` demonstrates typed state: it totals an
integer inventory map, prints a Vietnamese message, and rotates the entity array's
members through For Each. Use **Scene > Scene Variables…** to edit initial values,
then undo/redo or save/reopen them. See [typed data](docs/typed-data.md) for semantics.

`examples/functions_demo/project.json` reuses one **Spin Robot** action function
for two targets with different speeds, calling a pure **Rotation Delta** graph.
Use **Graph > New Function…** to create typed functions and double-click a call's
body to edit/navigate its graph. Save applies function edits as one undo step.
**Graph > Edit Function Signature…** renames/reorders ports and updates all callers
and function bodies in the current scene with validation and Undo/Redo. Connected
ports and non-default literals are protected from removal. Try the migrated
`examples/function_signature_demo/project.json` or run
`artifacts/demos/function-signatures/Play.cmd`.
Select nodes and use **Graph > Extract Function…** to create a reusable function;
the function editor has the same command for nested selections. Complete structured
action regions and single-result pure calculations preserve lazy data evaluation
and Undo history. Try `examples/function_extraction_demo/project.json` or
`artifacts/demos/function-extraction/Play.cmd`.
See [functions](docs/functions.md) for scope, return semantics and verification.

`examples/timers_demo/project.json` rotates two robots through **On Timer Finished**
events, every 0.25 and 0.5 seconds. Start/Stop/Pause/Resume Timer and timer queries
work in both preview and exported games. Empty Owner means the scene; an entity
ID gives that entity its own timer names. See [timers](docs/timers.md).

`examples/events_demo/project.json` broadcasts a typed Turn event to two robots,
then unsubscribes one receiver and sends a targeted turn to the other. Use
**Graph > Define Event…** to define payload parameters; On/Send/Broadcast/
Subscribe/Unsubscribe nodes appear in Events & Signals. See [events](docs/events.md)
for queue ordering, payload types and subscription behavior.

**Graph > Edit Event Signature…** migrates an event's typed payload across handlers
and root/nested senders with validation and one-step Undo/Redo. Existing values and
routing survive rename/reorder/default edits. Try
`examples/event_signature_demo/project.json` or run
`artifacts/demos/event-signatures/Play.cmd`.

`examples/entities_demo/project.json` creates two robots and a transform parent
at Play, then destroys one robot with a timer. Flecs stores scene components and
ChildOf relationships; the renderer discovers runtime-created entities. Parent,
visibility and tags are editable in the Inspector with Undo/Redo. See
[entities and hierarchy](docs/entities.md) for lifecycle and serialization rules.

`examples/components_demo/project.json` uses Health and Inventory components.
A timer damages the left robot through an action function; at zero Health it
hides and gives the collector one token. Use **Scene > Define Component…**, then
select an entity and **Add Component…**. Typed Get/Set nodes appear automatically.
The Inspector edits initial values and Enabled state with Undo/Redo. See
[components](docs/components.md) for query, clone and serialization behavior.

`examples/activity_demo/project.json` switches a parent robot group off and on
while an independent robot keeps moving. Inactive descendants stop rendering and
their owned timers suspend. The Inspector authors Active and Layer; layer queries
can select active members. See [activity and layers](docs/activity.md).

`examples/prefabs_demo/project.json` starts empty and instantiates a nested robot
pair with real Flecs prefab inheritance. Both robots share the Blockbench mesh
and rotate in opposite directions. **Scene > Create Prefab from Entity…** and
**Instantiate Prefab…** author reusable scene assets and instances with Undo/Redo.
See [prefabs](docs/prefabs.md) for ownership, persistence and remaining work.

**File > Register Prefab Files…** adds selected `.prefab.json` files from the
current project, including their base/nested dependencies. **File > Import Prefab
Library…** copies a saved project's registered library and glTF resources into
the current project. Both support Undo/Redo; save to retain the imported library.
The destination can be built after the source project is moved away.

`examples/prefab_reset_demo/project.json` deletes and enlarges prefab members,
then restores them using **Reset Prefab Instance** while a timer and queued event
continue running. Component writes now preserve explicit instance overrides,
even when the assigned value equals the template, through Apply/Reset and save/load.

`examples/prefab_overrides_demo/project.json` contains two robots sharing one
prefab. The template's Motion.Speed is 45; the left robot explicitly keeps 90.
Play rotates them at their independent speeds. Select the left robot and use
**Scene > Reset Prefab Instance…** to follow the template; Undo restores 90.

`examples/prefab_apply_demo/project.json` applies gameplay changes from the left
robot to the template. The middle follows; the right keeps explicit overrides
until Reset. Timers and queued events continue throughout. Its visible editor,
Build Game and packaged preview/export paths are verified at three frame counts.

`examples/nested_prefab_demo/project.json` captures a separately placed robot into
its parent prefab as a linked nested binding. Other parent instances receive the
robot; later source edits propagate while captured overrides remain. The adopted
child keeps its entity ID, timer and queued event. Apply/Reset then targets the
complete outer instance; per-binding selection remains pending.

The robot's nine cubes were created and validated through Blockbench MCP 1.10.1.
Its `.bbmodel` source is in `examples/blockbench_demo/assets`. A deliberately
limited cube-fixture converter creates its embedded glTF; this is not an export
performed by the Blockbench desktop application's glTF exporter. See
[Blockbench setup](docs/blockbench.md) for the verified MCP installation.

## Run the verified example (Windows PowerShell)

From the workspace root:

~~~powershell
.\tools\build.ps1
.\build\node_preview.exe --ir examples\core_demo\generated\game.ir.json --frames 120 --key D
.\build\node_game.exe --frames 120 --key D
.\.venv\Scripts\python.exe -u -m pytest -q
~~~

The demo initializes score to zero, increments it three times in a structured
loop, rotates the player each frame and translates it while D is held. At
120 frames / 60 Hz, score is 3, X is approximately 6 and Y rotation is 120°.
The headless --key option injects a held key for deterministic CLI tests.
The visual runtime reads live SDL keyboard state.

To export your own graph:

~~~powershell
.\.venv\Scripts\python.exe -m editor.cli path\graph.json --scene path\scene.json --output path\generated
.\.venv\Scripts\python.exe -m editor.cli --project path\project.json --output path\generated
~~~

The Python editor.core.builder.GraphBuilder API constructs the same versioned
documents. `add()` rejects unknown data-input names before changing the graph;
for example, Clone Entity takes `Source`, not `Entity`. Execution ports are wired
with `connect()`, not supplied as constant values. The source registry is nodes/registry.yaml; add a definition there
and the typed function in the runtime to implement a node. Generated adapter
files must not be edited manually.

The latent-flow example is `examples/latent_flow_demo/project.json`, authored by
`tools/create_latent_flow_demo.py`. Run `artifacts/demos/latent-flow-playground/Play.cmd`
for the standalone robot tour: Space starts, R restarts a signal delay, S/L save
and restore while a function is waiting. See [flow-control.md](docs/flow-control.md).

The Switch/Select example is `examples/switch_select_demo/project.json`, with
standalone launcher `artifacts/demos/switch-select-playground/Play.cmd`.
1/2/3/9 choose a route, Space applies after a delay, M mirrors it, and S/L
save/load while the function is waiting. Switch cases are editable in the Inspector.

## Current status and next work

- 1175 concrete builtin node definitions, including variants of array/map/set operations
  and Function Input/Output, plus project-defined function calls and five nodes
  for each custom event, plus six operations and two nodes per property for each
  scene-owned component:
  events, structured flow/For Each over arrays, maps and insertion-ordered sets, persistent execution gates, editable Switch cases, lazy typed Select, resumable Delay/Wait Until,
  typed variables, scalar/vector/boolean/integer math, modulo/power/square root,
  rounding, trigonometry, interpolation/remapping, comparisons and bitwise integer
  operations, Vector2/3/4 arithmetic and Vector3 component extraction,
  angle/project/reflect/rotate operations, quaternion/matrix transforms and
  general bounds/intersection geometry,
  strings, time, seeded random, entity references, transforms, input, game cameras, materials,
  sprites, basic audio, game UI, progress-data/whole-game persistence and result
  events, primitive physics, character movement, animation playback, navigation,
  AI state, streaming chunk selection, combat, quest progression, inventory, authored autosave,
  game-clock samples, local replication authority/revision, logging, assertions and C++ Code.
  Chunk selection does not load/unload worlds; local replication has no network transport;
  game-clock samples do not measure CPU/GPU performance. This remains a subset of the 29-category roadmap.
- Invalid links, unknown node types, cycles and invalid numeric literals are
  reported before export. Runtime errors report the originating node.
- Infinite loops are bounded by an instruction budget.
- Deterministic export, atomic JSON saves, CMake/Ninja and a static native runtime.
- Python/PySide6/NodeGraphQt and native build dependencies installed on this host.
- Obsidian docks, node search, typed connections, graph undo/redo, inspector,
  save/load, workspace settings, asynchronous native builds and local-socket IPC.
- New projects and entity create/duplicate/rename/delete, undoable transforms and
  mesh assignments, shared mesh rendering, and glTF/GLB dependency copying.
- Typed scene variables, homogeneous arrays, string-keyed maps, checked 64-bit
  integers and nested For Each. Preview and compiled code share their native
  behavior; loop item/index scope and known variable type conflicts are checked
  before export. Initial variable edits use the existing scene undo and IPC reload.
- Project-owned nested Struct/Enum values, typed Get/Set nodes, native
  global/scene/entity scopes and Sort/Filter/Map callbacks run in both the
  interpreter and generated C++ paths. Definitions and nominal type tags survive
  editor save/reopen, field reads and checkpoints. See [typed data](docs/typed-data.md)
  for **Scene > Structs and Enums…** authoring, local type/field refactors with
  stable node IDs, named function/event ports and shared project Undo. The
  [project type library](docs/project-types.md) synchronizes active/inactive
  scenes and handles legacy ID conflicts. Struct/Enum elements now work in typed
  arrays, maps and sets, including callbacks, function/event ports and checkpoints.
  Nested collections and broader GUI/performance acceptance remain open.
  Global values survive scene changes, scene values reset on entry, and entity
  values have independent owners. Author scopes in Scene Variables; explicit
  typed Global/Scene/Entity nodes and checkpoints use the same storage. See
  [variable scopes](docs/variable-scopes.md).
- Select a node and use **View / Edit Node Code…** or **Ctrl+Alt+C** to inspect its
  generated call and runtime implementation. The dedicated **C++ Code** node and
  action hooks support editable C++, line numbers, indentation, Ctrl+S and graph
  Undo/Redo, including function graphs. Preview and exported games run the same
  compiled hook; changed code triggers a rebuild. Compiler Problems open the
  originating node and code line. See [node code editor](docs/node-code-editor.md).
  The [embedded C++ robot](examples/embedded_code_demo/README.md) demonstrates both
  a dedicated code node and a hook on Set Position.
- Headless foundations now validate tilemaps, sprite state/sorting, runtime
  texture metadata, PBR/lights/Shader Graph, animation blending/IK/notifies/
  cinematics, navigation/AI/streaming, replication/inventory/combat/quests,
  autosave, profiling/plugins and editor debugger/accessibility metadata. See
  [feature pipeline](docs/feature-pipeline.md).
- Native glTF/GLB import with fastgltf; PNG/JPEG base-color textures, UVs,
  vertex colors, repeat/mirror/clamp, mipmaps, opaque/mask/blend and sRGB rendering.
  Scene-feature PBR also evaluates metallic/roughness, emissive color, imported
  normal textures and up to four directional/point lights. See [texture support and demo](docs/textures.md).
- Imported skeletons and TRS clips, per-entity playback controls, skinned rendering
  and exact animation checkpoints. The two-robot [animation playground](examples/animation_demo/project.json)
  works in Preview and generated games; see [animation](docs/animation.md).
- Reusable material assets, per-entity color/opacity/alpha/unlit nodes, Inspector
  authoring and prefab dependencies. Preview and compiled games preserve shared
  assets and independent instance overrides; see [materials](docs/materials.md).
- Scene sound assets, independently controlled voices, looping, pause/resume,
  per-voice/master volume and deterministic SDL_mixer PCM in Preview/export.
  See [audio](docs/audio.md) for device behavior, limits and remaining features.
- Blockbench 5.2.2 is installed; headless Blockbench MCP is registered and its
  actual create/edit/validate tools have been exercised successfully.
- Pure/action functions with typed parameters and multiple returns, nested calls,
  early return, graph navigation, undo and live preview reload. Play rejects stale
  runtime binaries and rebuilds when no current local/shared build is available.
- Named one-shot/repeating timers, owner-specific Flecs event delivery, deterministic
  catch-up, scoped event outputs and bounded callbacks. Pause freezes simulation;
  Stop/reload clears timers. Native snapshots include timer state.
- Typed custom events with immutable queued payloads, targeted/broadcast delivery,
  subscription control and scoped Sender/Receiver outputs. Actual Flecs observers
  select handlers; bounded queues and the shared instruction budget limit event storms.
  Definition creation, payload editing, Undo/Redo, save/reopen and native export
  work through the editor.

- Flecs component storage, runtime Spawn/Clone/Destroy, names/tags, hierarchy,
  inherited visibility and world-position queries. Destroy cleans up owned timers
  and event deliveries; scene snapshots preserve metadata and stable references.
- Typed user components, Inspector authoring, attach/remove/query/Enabled and
  property access, deep value copies on clone and scene serialization. Component
  queries and mutations work through the shared native runtime and action functions.
- Inherited entity activity, layers 0–31 and active layer queries. Disabling a
  branch suspends its timers and invalidates queued custom-event deliveries;
  reactivation preserves manual Pause and subscription preferences.

Current limits: fixed component schemas after creation, physics constraints and collider gizmos, one-level typed
collections, one active scene with a separate gameplay graph and reusable functions per
scene, and Windows/Vulkan verified only. Additive scenes, general macros, broader
extraction boundaries and function/event deletion are not implemented. Feature metadata
is validated and tilemap/sprite-state/runtime texture files enter the graphical resource/update
path; full replacement workflows and GUI gates remain open. Animation, Shader Graph, AI
and procedural workspaces are unavailable. Gameplay nodes can play skinned models, but
clip/skeleton Inspector controls and timeline remain pending. Native animation
state transitions, notify events and a two-bone IK solve are available. Scene-feature PBR, imported normal-map sampling and up to four directional/point lights
are implemented; clustered multi-light scaling and authored Shader Graph remain pending. Non-PBR
materials use fixed face lighting.

Prefab asset capture, variant/nested resolution, native Instantiate/lookup nodes,
typed-reference remapping and editor creation/placement are available. Native
snapshots preserve actual Flecs ownership and instance membership. Editor Apply/Reset
propagates authored template changes, preserves instance overrides and reconciles
structural/component edits. Gameplay Apply/Reset preserves the running simulation;
explicit component/property writes survive serialization and template updates.
Gameplay Apply updates dependent templates and live instances with validated
transactions. Complete independent children can now be adopted as nested asset
bindings. The File menu registers prefab files and imports saved project libraries.
Per-binding Apply/Reset selection and dedicated external asset editing/refresh
remain pending.

Next: remaining scene/application lifecycle events, complete prefab integration,
further function authoring, richer assets and
rendering, and shared build caching. See [roadmap](docs/roadmap.md),
[integration audit](docs/ui-integration-notes.md) and
[validation report](docs/validation-report.md).

The [physics runtime](docs/physics.md) uses pinned Jolt 5.6.0 for primitive rigid
bodies, collisions, forces and queries. Thirty-six physics nodes and `On Fixed Update`
run a shared 60 Hz simulation, synchronize scene transforms and preserve physics
through game Save/Load. The Blockbench demo has real editor and four-host evidence.
Six collision/trigger event nodes support scoped contacts and checkpoint continuity.
The Inspector and prefabs store initial collider settings. Raycast and primitive
sphere/box/capsule casts expose hit, entity, point, normal, fraction and distance
from one query execution. Open `examples/physics_queries_demo/project.json` for
four live ground probes on the robot. Sphere/Box/Capsule overlaps return sorted
entity arrays; `examples/physics_overlaps_demo/project.json` demonstrates region
entry/exit and HUD counts. Compound convex and static indexed-mesh colliders
now synchronize and roundtrip through native Save/Load. Collider gizmos,
per-part handles and constraints remain pending.

~~~powershell
.\.venv\Scripts\python.exe -u -m pytest -q
.\.venv\Scripts\python.exe tools\verify_desktop.py --build
.\.venv\Scripts\python.exe tools\verify_scene_workflow.py
.\.venv\Scripts\python.exe tools\verify_collections_workflow.py
.\.venv\Scripts\python.exe tools\verify_functions_workflow.py
.\.venv\Scripts\python.exe tools\verify_function_embedding.py
.\.venv\Scripts\python.exe tools\verify_timers_workflow.py
.\.venv\Scripts\python.exe tools\verify_components_workflow.py
.\.venv\Scripts\python.exe tools\verify_activity_workflow.py
.\.venv\Scripts\python.exe tools\verify_prefabs_workflow.py
.\.venv\Scripts\python.exe tools\verify_prefab_edits_workflow.py
.\.venv\Scripts\python.exe tools\verify_prefab_reset_workflow.py
.\.venv\Scripts\python.exe tools\verify_prefab_apply_workflow.py
.\.venv\Scripts\python.exe tools\verify_nested_prefab_workflow.py
.\.venv\Scripts\python.exe tools\verify_prefab_import_workflow.py
.\.venv\Scripts\python.exe tools\verify_component_overrides_workflow.py
~~~

The desktop check opens real Qt/SDL windows and verifies build responsiveness,
model rendering, pause/stop, live property IPC and crash recovery. Evidence is
saved under `artifacts/validation/`.
