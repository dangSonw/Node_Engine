# Input actions, axes and replay

Open `examples/input_demo/project.json` and press Play. Click the native viewport,
then move the Blockbench robot with WASD or arrows. Space or the left mouse button
turns it 90 degrees once per press; R restores its position and rotation. Diagonal
movement is normalized in the graph and uses delta time. Esc returns focus to the
graph so editor shortcuts work again. The same graph builds into a standalone game.

## Authoring

**Scene > Input Actions and Axes…** edits bindings with dropdowns. Repeat an action
or axis name on another row to add alternative buttons. Action rows use the right
button column; axes use negative and positive columns. Removing or renaming a
binding also requires updating graph nodes that reference its name. The compiler
reports missing literal names at their node. Names supplied by a data connection
are checked in the shared C++ runtime with the originating node in the error.

An accepted dialog is one scene Undo/Redo command. Binding changes reload preview
in the same process and reset simulation. Save/reopen and export retain bindings.
Existing scenes without an input section remain supported.

The **Gamepad** tab also binds controller buttons and analog axes to these same
names. Version-2 mixed bindings support dead zones, inversion and any-controller
aggregation; see [shared input bindings](input-bindings.md). The version-1 format
below remains supported without conversion.

The optional scene field is:

```json
"input": {
  "version": 1,
  "actions": {"turn": ["Space", "MouseLeft"]},
  "axes": {"horizontal": {"negative": ["A", "Left"], "positive": ["D", "Right"]}}
}
```

Names are case sensitive, at most 128 UTF-8 bytes, without control characters.
Each action and each axis direction accepts 1–16 unique buttons. An axis cannot
use the same button in both directions. There are at most 256 actions and 256 axes.
The editor and generated native button validator share the vocabulary in
`editor/core/input.py`; it includes letters, digits, navigation/modifier/function
keys, punctuation and five mouse buttons. The included keyboard names were checked
against the bundled SDL3 key-name API. This is not a text-entry or IME system.

## Nodes and timing

| ID | Node | Result |
|---|---|---|
| 10001 | Is Key Held | Button is currently held; existing API, also accepts mouse names |
| 10002 | Is Key Pressed | Button transitioned down during this update |
| 10003 | Is Key Released | Button transitioned up during this update |
| 10004 | Is Action Held | Any bound button is held |
| 10005 | Is Action Pressed | Action transitioned from no held buttons to at least one |
| 10006 | Is Action Released | The last held button for the action was released |
| 10007 | Get Input Axis | Digital directions plus bound analog contributions, clamped to [−1,1] |
| 10008 | On Key Pressed | Keyboard down transition; scoped Key string |
| 10009 | On Key Released | Keyboard up transition; scoped Key string |
| 10010 | On Mouse Button | Mouse button transition; scoped Button and captured Down |
| 10011 | On Action Pressed | Mapped action becomes held; scoped Action string |
| 10012 | On Action Released | Last alternative button released; scoped Action string |
| 10013 | Get Mouse Position | Last window-content position, X right / Y down |
| 10014 | Get Mouse Delta | Relative motion accumulated during this frame |
| 10015 | Get Mouse Wheel | Horizontal/right and vertical/up scroll accumulated this frame |
| 10016 | Set Cursor Visible | Request cursor visibility; boolean Visible defaults true |
| 10017 | Lock Cursor | Request relative mouse mode; boolean Locked defaults true |
| 10018 | Get Connected Controllers | Sorted Integer Array of connected controller IDs |
| 10019 | Get Gamepad Axis | Normalized analog value with configurable dead zone |
| 10020 | On Gamepad Button | Scoped Button, Down and Controller for ordered gamepad edges |

Input entry nodes belong in Gameplay and accept a constant **Filter** in the
Inspector. Empty matches all names of that event kind; otherwise the name must
be an exact supported keyboard button, mouse button or existing scene action.
Data wires into Filter and event outputs used outside their handler are rejected.
Handlers may call action functions and suspend with Delay. Multiple matching
handlers run in graph node-ID order. Input is global; Get Self is empty.

Each physical transition is delivered in original input order. Its raw keyboard
or mouse notification precedes any mapped action transitions; multiple actions
on one button are ordered by action name. Key repeat and alternative-button
handoff do not create extra presses. A down/up/down/up sequence in one frame
produces four callbacks. Polling nodes still report final held state and whether
each edge occurred at least once; Mouse Down captures the individual transition.

Input advances before pending latent graphs resume. The shared Flecs event queue
then drains input callbacks and custom events, before UI input and On Update.
Delay started by an input callback first advances on the next frame. Existing
per-node/owner behavior applies: Delay retains its first pending invocation;
Retriggerable Delay replaces it with the latest captured input. Events also run
at Time Scale zero, while Editor Pause suspends the frame loop.

Input events are consumed before On Update. Queries do not consume edges; all
reads, functions, timers and queued handlers in that frame see the same values.
Edges clear at the next update. A quick down/up pair between updates produces
both Pressed and Released, with Held false. OS key repeat does not produce new
presses. Pressing an alternative button while one is held does not press the
action again. Opposing axis buttons cancel, including multiple alternatives.

Input is scene-wide. Entity Active does not disable polling code by itself.
Use Branch with the entity's activity when input should be gated by that entity.
SDL window focus loss releases held buttons on the next update. Pause and Stop
clear input; input received while paused is discarded. Resume requires a new
press for a button held through the pause. Clicking the embedded SDL window gives
it Windows keyboard focus. Esc releases gameplay input and explicitly restores
native Qt focus; Qt Save/Undo shortcuts then work. Esc is available as a game
button in the standalone game. Right-drag orbit and wheel zoom remain the existing
view controls.
On Windows, returning to a Qt panel explicitly restores native editor focus and
queues a release-all input transition over IPC; embedded SDL focus notifications
alone are insufficient. Read-only HUD overlays should use `pointer-events:none`
when mouse clicks are intended for gameplay.

## Deterministic replay

All four native executables accept `--input-replay <path>`. The document is versioned
and its events must be ordered by zero-based update frame, from 0 to 999999. The
limit is 100000 events; events with equal frame numbers preserve file order.

```json
{"version":1,"events":[
  {"frame":0,"button":"D","down":true},
  {"frame":10,"button":"D","down":false},
  {"frame":20,"release_all":true}
]}
```

Use `--frames 30 --input-replay examples/input_demo/input-replay.json` to run the
sample deterministically. SDL uses 1/60 second when `--frames` is supplied. Headless
programs default to 1/60 and support `--dt`. Replay disables physical gameplay input
and camera gestures. On Game Start sees neutral replay input; frame-zero events
arrive before the first On Update. Missing replay frames preserve held state and
clear edges. Events beyond the requested frame count are not processed.

The older headless `--key D` option remains a constant held baseline, including
On Game Start, without synthetic press edges. Combining it with replay is rejected.
Replay describes input, not a saved game or a recording of real-time sessions.

Gamepad action/axis bindings are available in the editor; vibration/touch/sensors and runtime rebinding remain
pending. Basic game-camera nodes are described in [camera.md](camera.md).
Gamepad axes, device queries and button callbacks are described in [gamepad.md](gamepad.md).

## Pointer coordinates, motion and scroll

The three pure mouse nodes return **Vector3 (X, Y, 0)**, using the existing typed
vector ports. Use Dot Product with `[1,0,0]` or `[0,1,0]` to read one coordinate.
Position and motion use SDL window-content coordinates, not desktop coordinates
or render-target pixels; both retain fractional values. Position is the latest
sample, including button and wheel locations. It can be outside the client area
while the mouse is captured. No clamp or automatic normalization is applied.

Delta and wheel are sums over the frame; reads do not consume them. They reset
before the next frame's input, including when that frame has no events. Do not
multiply mouse delta or wheel by delta time. Wheel X is positive right; Y is
positive away from the user (normally scrolling up). SDL flipped wheel events are
normalized to these signs; high-resolution fractional scrolling is preserved.

Position remains readable over an interactive UI element, while motion and wheel
consumed by RmlUi do not control gameplay. A read-only HUD can pass pointer input
through with `pointer-events:none`. The editor's orbit view retains its existing
gestures; use a game-camera view to test gameplay camera control.

Focus release discards accumulated pointer impulses preceding the release, while
preserving subsequent events in the same frame and the last position. Pause
discards incoming gameplay input. Interactive Play/Resume and successful Load
sample the current physical pointer without creating displacement or scrolling.
Stop starts a fresh scene. Deterministic replay instead starts at `(0,0,0)` and
restores the saved pointer state exactly.

Replay **version 2** adds the following events alongside existing button/down and
release-all events. Version 1 remains accepted for button-only replays. Original
file order is retained for events with the same frame.

```json
{"version":2,"events":[
  {"frame":0,"type":"position","x":100.5,"y":80.25},
  {"frame":1,"type":"motion","x":110.75,"y":78,"dx":10.25,"dy":-2.25},
  {"frame":1,"type":"wheel","x":0.25,"y":1.5}
]}
```

Position events do not infer a delta. Motion supplies absolute and relative data
explicitly. Values must be finite numbers; booleans, missing/extra fields and
unknown event types are rejected. Invalid raw batches, including overflowing
accumulated motion/wheel, are rejected before changing input state.

Input checkpoint version 2 preserves position, delta and wheel. The standalone
input-checkpoint reader accepts legacy version 1 with neutral pointer state;
whole-game slots still require the exact compatible program/resource identity.
This is not whole-game schema migration. Staged restoration rejects malformed
pointer data before replacing the live game.

`examples/pointer_demo/project.json` uses all three nodes: left-drag rotates the
animated Blockbench robot, wheel moves it nearer/farther, R resets its pose and
S/L save/load. The HUD shows absolute position, frame impulses and accumulated
motion/scroll. Author it with `tools/create_pointer_demo.py` or run the native
`artifacts/demos/pointer-playground/Play.cmd`.

## Verification on Windows

`tests/test_input.py` checks malformed bindings, the actual dialog's scene history,
saved bindings, per-frame edge traces, opposing axes, alternate-button handoff,
quick taps, focus-release replay, missing names and native JSON rejection.
It runs real C++ interpretation and generated calls. Related compiler/function,
scene and runtime-fingerprint regressions total 63 passing tests in
`artifacts/validation/input-regressions.xml`.

`tools/verify_input_workflow.py` passes 30 checks with real Windows input sent to
the visible editor and native child window. These cover keyboard movement, key
repeat, shared keyboard/mouse actions, focus lost by clicking a Qt panel, Esc,
Ctrl+S/Ctrl+Z, pause/resume, binding reload/Undo/Redo/save/reopen and rejection of
malformed native reloads without replacing the live world. Editor Build Game
completed with 498 GUI heartbeat ticks. The packaged native preview and compiled
game produce equal state and GPU bitmap bytes after 30 replay frames. Results are
in `artifacts/validation/input-workflow-checks.json`; its project path identifies
the isolated verification project. The original example keeps R as Reset.

## Runtime checkpoint groundwork

`InputCheckpoint` and `RestoreInputCheckpoint` retain the complete binding and
button state, including both pressed/released edges during one frame and shared
keyboard/mouse action edges. Restoration validates temporary state before swapping;
malformed data leaves current input unchanged. The native scene/input/audio probe
restores six checkpoints in a fresh process and compares 389 continuation frames.
See [persistence.md](persistence.md) for the integrated full-game transaction.

The full-game checkpoint now includes ordered input deliveries and their filtered
listener identities. Restoration validates names, edge directions, global
subscriptions and filters before changing live state; it does not reconstruct
callbacks from polling edge sets. A Save Game request in an input handler commits
at the frame boundary, after that frame's input and graph work. Pending latent
input payloads survive exact replay continuation.

Interactive SDL Load clears saved held buttons and edges without synthetic
callbacks, so a saved Save/movement key cannot remain stuck in a later physical
session. A button held through Load or Pause must be released and pressed again;
OS repeat does not rearm it. Deterministic replay retains the checkpoint input state. Pause/Stop also
discard pending input callbacks; focus loss instead emits real release transitions
for held buttons. The existing queue bound is 4,096 deliveries / 64 MiB, shared
with other events. Callback execution uses the normal graph instruction budget.

The new editable example is `examples/input_events_demo/project.json`, authored
by `tools/create_input_events_demo.py`. Space/left mouse rotate the Blockbench
robot through an action handler; A/D or arrows move it, R resets its pose and S/L
save/load. A retriggerable delay displays its retained Action payload. Run the
standalone `artifacts/demos/input-events-playground/Play.cmd` without Python or Qt.

```powershell
.\tools\build.ps1 -Project examples/input_events_demo/project.json
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_input_events.py -q
.\.venv\Scripts\python.exe -X utf8 tools/verify_event_checkpoint.py
.\.venv\Scripts\python.exe -X utf8 tools/verify_input_events_workflow.py
.\.venv\Scripts\python.exe -X utf8 tools/verify_input_events_editor.py
```

See the current input-events milestone in [validation-report.md](validation-report.md)
for exact automated and actual-editor results. Text/IME and
runtime rebinding are separate remaining work.

Pointer-specific checks are in `tests/test_pointer_input.py`, the native
`tools/event_probe/main.cpp`, `tools/verify_pointer_workflow.py` and
`tools/verify_pointer_editor.py`. The latter checks actual mouse movement and
both wheel axes, client coordinates at 125% DPI, UI scroll consumption, pause,
focus, physical Load reconciliation and Library/Undo/Redo/project roundtrips.
The four-host verifier covers fractional replay, empty-frame reset, saved frame
impulses, exact fresh-process continuation and malformed-pointer rollback.
See the pointer milestone in [validation-report.md](validation-report.md).

`input-desktop.png` shows the embedded robot and the deliberately rejected input
reload in Problems. `input-compiled.png` shows the robot after two replay turns.
Both images were visually inspected. These checks cover the current Windows host,
not other platforms, all keyboard layouts, IME or physical gamepads.

## Cursor visibility and relative lock

**Set Cursor Visible** (10016) and **Lock Cursor** (10017) are actions with In/Out
execution ports and a boolean data port. They set game requests; lock always
hides the physical cursor while active. Unlock restores the last visibility
request. Fresh game state is visible and unlocked.

While locked, Get Mouse Position retains its anchor and Get Mouse Delta reports
unbounded relative motion. Motion still accumulates each frame without consuming
reads or multiplying by delta time. Lock bypasses pointer interception by RmlUi;
keyboard UI propagation is unchanged. Unlock resumes absolute position samples.

The SDL host applies these requests only during focused, running, interactive
gameplay. Hidden cursors become visible over Qt panels. Pause, focus loss, graph
errors and shutdown release confinement and show the OS cursor. Pause retains
the requests, and focused Resume reapplies them. Stop resets the game requests.
Editor Esc and Qt focus release latch the cursor free until Play/Resume or an
explicit viewport click. Standalone Esc remains a game key: this example wires
it to unlock and show. Games should provide their own menu/escape policy.

Input checkpoint **version 3** adds strict boolean visibility/lock requests and
the originating node ID. Load restores the game intent; the host independently
checks its current focus and running state. It cannot restore another session's
OS focus or confinement. Physical Resume/Load resample the cursor and clear
transient input; deterministic replay preserves exact saved pointer values.
Standalone version-1/2 input records remain readable with visible/unlocked
defaults. Whole-game saves still require exact program/resource compatibility.

Headless execution and SDL input/UI replay run the same cursor nodes without
grabbing or hiding the physical cursor. Input replay remains version 2; the
checkpoint version is a separate format.

Open `examples/cursor_demo/project.json`, or run
`artifacts/demos/cursor-playground/Play.cmd`. K/U lock/unlock; H/V hide/show;
relative movement or left-drag rotates the Blockbench robot; wheel moves it;
R resets its pose and S/L save/load. The HUD reports requested state, which may
differ from effective state while the editor releases focus.

Verification: `tests/test_cursor_input.py`, `tests/test_sdl_dependency.py`, the
native event probe, `tools/verify_cursor_workflow.py`, `tools/verify_cursor_editor.py`
and `tools/verify_cursor_standalone.py`. See [SDL focus adapter](sdl-embedded-focus.md)
for the pinned Windows source change and [validation results](validation-report.md)
for actual physical input, fresh-process continuation and regression evidence.

## Named contexts

The binding dialog's **Contexts** tab groups existing action/axis names with an
initial enabled state. Set Input Context Enabled and Is Input Context Enabled
control these groups at runtime. Unassigned bindings remain available; overlapping
members work while any member context is enabled. Raw input remains available for
menu controls. Re-enabling a held action requires all alternatives to return to
neutral before another press; axes resume immediately. Input checkpoint version
5 preserves runtime context state and suppression. See
[input-contexts.md](input-contexts.md) for delivery cancellation, persistence,
authoring, limits and the robot demo.
