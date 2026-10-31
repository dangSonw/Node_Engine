# Gamepad input

Open `examples/gamepad_demo/project.json`, or run
`artifacts/demos/gamepad-playground/Play.cmd`. Left stick moves the Blockbench
robot; the South face button turns it. A/D provide keyboard movement, R resets
the pose, and S/L save/load. The HUD displays axes, connected count, button edges
and the controller ID captured by a delayed callback. The included version-3
replay exercises two simultaneous controllers, disconnect/reconnect and Save/Load.

| ID | Node | Interface |
|---|---|---|
| 10018 | Get Connected Controllers | Sorted Integer Array of live SDL instance IDs |
| 10019 | Get Gamepad Axis | Controller, Axis and Dead Zone inputs; Float result |
| 10020 | On Gamepad Button | Constant optional Filter; scoped Button, Down and Controller outputs |

Controller 0 in Get Gamepad Axis selects the lowest connected ID. An explicit
missing ID returns zero; IDs outside 0..4294967295 are invalid. Connection and
replay IDs must be positive. Up to 16 controllers are supported. IDs identify
one connection, not a permanent physical device or player assignment. Reconnecting
can produce a new ID. Save files retain logical IDs; physical Load replaces the
input inventory with the devices actually connected in the current process.

Axis names are `LeftX`, `LeftY`, `RightX`, `RightY`, `LeftTrigger`, `RightTrigger`.
Sticks range from -1 to 1, with left/up negative and right/down positive. Triggers
range from 0 to 1. The engine normalizes SDL's signed 16-bit samples, preserving
both endpoints. See [SDL axis semantics](https://wiki.libsdl.org/SDL3/SDL_GetGamepadAxis).

Dead Zone defaults to 0.15 and must be finite in [0,1). It is applied independently
to each axis: magnitudes at or below the threshold become zero; the remainder is
rescaled to reach one at the endpoint. Set it to zero for raw normalized values.
Tune it for the controller used by the game; this is an axial, not radial, dead
zone. Movement usually multiplies analog values by delta time.

Button names describe physical positions: South/East/West/North, Back, Guide,
Start, LeftStick/RightStick, LeftShoulder/RightShoulder, DpadUp/Down/Left/Right,
Misc1..Misc6, RightPaddle1/LeftPaddle1/RightPaddle2/LeftPaddle2 and Touchpad. These
are case-sensitive; unsupported controls simply do not generate events. The
common vocabulary lives in `editor/core/input.py` and generates native tables.
The SDL enum size is checked when opening the device subsystem.

On Gamepad Button delivers both down and up transitions, in original input order.
Duplicate downs/ups are suppressed. An empty Filter accepts all names; otherwise
it must name one supported button. Use a Branch on Down for press-only actions.
Controller identifies the device that produced that particular edge, including
after Delay. Input callbacks run before On Update through the shared event queue.
They remain independent of keyboard/mouse action mappings and RmlUi navigation.
For one graph action shared by keyboard, mouse and gamepad, use the version-2
[Input Actions and Axes bindings](input-bindings.md). Raw gamepad events remain
available alongside those mapped action callbacks.

Disconnect emits releases for held buttons, in button-name order, then removes
that device's axes. Release-all clears every controller's axes/buttons while
retaining connections. Pause and physical Load clear buttons and queued input
callbacks without inventing edges. A button held through Pause/Load or focus loss
must be released and pressed again. Focus return/Resume sample current analog
values. The host keeps SDL hardware samples current in the background but gates
gameplay on running state, native viewport focus and editor focus release. Input
received over Qt panels does not move the game. Remapping releases only the
affected controller and requires new presses for held buttons.
Gamepad focus reconciliation only resets gamepad controls; it preserves the
mouse-button hold that brought focus back to the viewport.

## Replay and checkpoints

All four native hosts accept version-3 input replay, with the existing button,
pointer and release-all records plus:

```json
{"version":3,"events":[
  {"frame":0,"type":"gamepad_connection","controller":7,"connected":true},
  {"frame":0,"type":"gamepad_axis","controller":7,"axis":"LeftX","value":0.6},
  {"frame":1,"type":"gamepad_button","controller":7,"button":"South","down":true},
  {"frame":2,"type":"gamepad_connection","controller":7,"connected":false}
]}
```

Connect a device before sending its axes/buttons. Axis values are normalized
before dead-zone processing. Types, fields, ID/range bounds and ordered frames
are validated. Invalid raw batches reject before changing input or queuing new
callbacks. Replay version 1 (buttons) and 2 (pointer) remain accepted. Physical
devices are not opened during input/UI replay; headless input comes from replay.

Input checkpoint version 4 includes connected IDs, all six axes and held buttons.
The event checkpoint separately preserves pending button deliveries and listener
filters, and latent execution retains captured Controller/Down/Button values.
Restoration validates temporary state before committing. Version-1/2/3 standalone
input records upgrade with no invented devices. Full-game saves continue to
require exact program/resource compatibility; this is not cross-build migration.

## Verification and remaining work

`tests/test_gamepad_input.py` covers compiler validation, both native graph paths,
dead zones, scoped/delayed controller identity, hotplug and ordered releases.
`tools/gamepad_probe/main.cpp` covers malformed batches/checkpoints and actual
SDL virtual-device events. The editor verifier drives the same `runtime/src/app.cpp`
inside a test executable that exposes virtual-device controls only in tests;
production binaries do not expose those commands. It checks the real Qt child
window, native focus and host loop. Four-host workflow checks compare complete
state and GPU pixels after fresh-process restoration. See the gamepad milestone
in [validation-report.md](validation-report.md) for measured results.

Virtual controllers use [SDL's virtual-joystick API](https://wiki.libsdl.org/SDL3/SDL_AttachVirtualJoystick).
These checks do not certify physical USB/Bluetooth models, platform drivers,
wireless reconnection or mapping databases. Vibration, touch/sensors,
runtime rebinding, context priority/consumption and durable player-device
assignment remain open. Other platforms and DPI/device configurations require
separate evidence. The whole-engine goal remains active.
