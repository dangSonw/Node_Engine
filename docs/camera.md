# Game cameras

Camera entities use the same transforms, hierarchy and Flecs world as other
entities. Native preview and exported C++ call the same lens/follow functions.
The registry adds 15 definitions (15001–15015), including screen/world projection
helpers. The current builtin count is recorded in the acceptance audit.

Use Camera Follow from [On Late Update](frame-events.md) to observe a body's
final position after the current frame's physics steps. The
`examples/late_update_demo/project.json` example combines this with animated
Blockbench meshes and Save/Load requested from late callbacks.

## Play and author

```powershell
.\.venv\Scripts\python.exe -m editor.main examples\camera_demo\project.json
```

Press Play and click the viewport. WASD/arrows move the Blockbench robot;
Space/left mouse turns it, R resets it and C switches perspective/orthographic.
The camera follows with exponential smoothing and looks at a point above the
player's origin. Two stationary robots make relative movement visible. Esc
returns keyboard focus to Qt. Build Game creates the standalone executable.

- **Scene > Create Camera** adds a camera at `[0, 2, 6]`. The first authored camera
  becomes active. It initially faces local -Z; edit its rotation or use Look At.
- Select a camera in Hierarchy and click **Edit Camera…** in Inspector to change
  projection, vertical FOV, orthographic height and near/far clipping together.
  Invalid values keep the dialog open and show an explanation.
- **Use as Game Camera** selects the inspected camera. **Scene > Choose Active
  Camera…** also selects a camera or clears the selection.
- Uncheck **View > Game Camera** to use the editor's right-drag orbit and wheel
  zoom. Rechecking restores the game camera. This changes the preview view only;
  it does not modify the scene or the exported game.
- Creation, lens changes, selection, duplication and deletion share scene
  Undo/Redo, save/reopen and preview reload. Selecting another camera must reload
  the native scene even when no entity property changed.

## Nodes and semantics

| Nodes | Behavior |
|---|---|
| Create Camera | Returns a new camera entity; use Set Active Camera to select it |
| Has Camera | True for a live entity with a camera, including an inactive entity |
| Set / Get Active Camera | Select/query a scene camera; an empty reference clears the selection |
| Set Camera Perspective / Orthographic | Select the projection and set FOV/height plus clipping planes |
| Get / Set Camera FOV | Vertical FOV in degrees, retained even while orthographic |
| Get / Set Camera Orthographic Size | Full vertical world-space height, retained even while perspective |
| Set Camera Clipping Planes | Atomically set positive near/far distances |
| Camera Follow | Move toward target world position plus a world-space offset |
| Camera Look At | Orient local -Z toward a world-space point using the requested up vector |
| World To Screen | Project a world-space point to top-left-origin viewport pixels; the viewport is `[width,height]`. |
| Screen To World | Unproject a top-left-origin viewport pixel and normalized depth (`0` near, `1` far) to world space. |

Position/Rotation/Parent nodes already accept the returned entity reference.
Camera transforms use degrees and the existing Y-X-Z rotation order. Placement
inherits the complete parent transform. Lens orientation inherits rotations;
parent/entity scale does not change FOV or orthographic height. Follow converts
the desired world position back into parent space and rejects a singular parent
transform. Look At rejects coincident positions, zero Up and parallel Up/direction.

Follow Rate is nonnegative and measured per second. Zero snaps immediately;
positive rates interpolate with `1 - exp(-rate * delta_time)`. Follow updates only
when its execution input runs; a typical graph invokes it on Update, followed by
Look At. It does not implicitly rotate the camera. Pause stops the graph.

FOV must be 1–179 degrees; height must be positive and at most 1e9. Clip distances
require `0 < near < far <= 1e9`. All values must be finite. Scene loading, the
editor dialog and native node setters validate these bounds. Failed native
setters leave the previous lens intact; graph faults report the source node.

No selected camera uses the existing orbit view. A selected camera with inactive
self/ancestor clears the view until active again. Camera Visible only controls
its optional mesh, not its lens. A destroyed camera clears its selection; Undo
deletion in the editor restores both the camera and its selection.

## Scene and prefab data

An optional entity `camera` object contains `projection`, `fov`, `size`, `near`,
and `far`. Null/absent means no camera. Scene `active_camera` is the selected
entity ID, or empty/absent. Older scenes remain valid and keep the orbit view.

Camera settings are a builtin Flecs component with prefab inheritance. Editing
one lens owns that instance's entire camera settings group. Clone copies the
lens without selecting the clone. Capture, instantiate, Apply/Reset, template
reconciliation and native snapshots preserve settings and explicit absence.
Removing an inherited selected camera prunes its scene reference. An explicit
instance override can retain a camera removed from its template.

## Verification and remaining work

`tests/test_camera.py` checks lens boundaries, actual Qt dialog authoring,
Undo/Redo/save, C++ interpretation/export parity, camera creation/query/clone/
destruction, hierarchy with rotation/nonuniform scale, smoothing over one second,
source-node errors and prefab inheritance/Apply/Reset/removal.

`tools/verify_camera_workflow.py` exercises the visible Windows editor, physical
keyboard input, native view switching, camera authoring/reload, invalid scene
rejection, inactive-camera rendering, editor Build Game and GPU captures from
both packaged executables. Artifacts are in `artifacts/validation/camera-*`;
the JSON report names its isolated project and bitmap hashes. See the latest
camera section of [validation-report.md](validation-report.md) for results.

On this Windows host, the delivery passes 36 desktop/build/GPU workflow checks
and 149 distinct tests across camera and related regressions (using the latest
result for repeated cases). Existing NodeGraphQt/Windows modal diagnostics are
recorded in the validation report rather than treated as warning-free output.

`Evaluate Cinematic Camera` (15016) reads the authored
`features.3d.cinematic_camera` keyframes and linearly interpolates a camera
position for a graph-supplied time. The interpreter and generated C++ paths
share validation for finite three-dimensional values and strictly increasing
keyframe times. A graph can feed the result into ordinary transform/camera
nodes; rail authoring, blending and timeline editing remain open.

Multiple viewports, camera masks, game orbit gestures, camera blending/shake,
collision avoidance, rails and cinematic timelines remain open. The current
camera writes produce complete node-level errors, but camera gizmos, viewport
selection and dedicated camera transform tools are not implemented. This does
not close the full Camera & Cinematics category or the engine goal.
