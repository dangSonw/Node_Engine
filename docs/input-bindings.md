# Shared keyboard, mouse and gamepad bindings

Open `examples/input_bindings_demo/project.json`, or run the packaged
`artifacts/demos/input-bindings-playground/Play.cmd`. Left stick, D-pad, arrows
and A/D move the Blockbench robot. Space, left mouse and South all invoke the
same turn action. R resets; S/L save/load. `Replay.cmd` needs no physical controller.

## Authoring

**Scene > Input Actions and Axes…** has Keyboard / mouse, Gamepad and Contexts tabs. Repeat
the same name to combine alternatives across either tab. Gamepad rows select an
Action, a digital Axis buttons pair, or an Analog axis. Analog rows also expose
dead zone and inversion. Errors stay in the dialog for correction. Accepting is
one scene Undo/Redo operation and reloads the preview in the same process with
simulation reset; save/reopen/export preserve the configuration.

Bindings with only the original keyboard/mouse controls retain version 1. Adding
gamepad rows opts into version 2. Contexts use version 3; see
[input contexts](input-contexts.md). Existing nodes remain the interface:
Is Action Held/Pressed/Released, On Action Pressed/Released, and Get Input Axis.
No additional node types or per-device graphs are required.

```json
{
  "version": 2,
  "actions": {
    "turn": ["Space", "MouseLeft", {"button":"South", "controller":0}]
  },
  "axes": {
    "horizontal": {
      "negative": ["A", {"button":"DpadLeft", "controller":0}],
      "positive": ["D", {"button":"DpadRight", "controller":0}],
      "gamepads": [
        {"axis":"LeftX", "controller":0, "dead_zone":0.2, "invert":false}
      ]
    }
  }
}
```

Controller **0 in a binding means any connected gamepad**. A positive value is
an exact SDL connection ID (1..4294967295), which may change on reconnect. This
does not assign a permanent device to a player. The separate low-level Get
Gamepad Axis node still uses 0 to select the lowest live ID; bindings deliberately
aggregate devices to let one action work with any controller.

## Action and axis semantics

An action is held while any alternative is held, across keyboard, mouse and all
matching gamepads. Pressing a second alternative does not press again. Releasing
one while another remains held does not release the action. Releasing the last
alternative, including by unplug, emits one mapped release. Duplicate physical
transitions are ignored; rapid down/up/down within a frame retains every callback.
Raw button callbacks precede mapped callbacks; simultaneous mapped transitions
are ordered by action name. Polling exposes the final held state and both edge
flags if both occurred. Existing scoped Action values survive Delay and Save/Load.

A digital axis contribution is positive-held minus negative-held; multiple held
alternatives in one direction count once. Each analog binding applies its axial
dead zone, rescales the remaining magnitude, and optionally negates it. For an
any-controller analog binding, the greatest absolute value wins; equal magnitudes
choose the lowest connection ID. Controllers are not summed within that binding.
The digital result and each distinct analog binding are then summed and clamped
to [-1,1]. Thus A held against a +0.5 stick gives -0.5, and D held with +0.5 gives
+1. Trigger axes normally contribute 0..1 and inversion makes them negative.

Axis names, button names and normalized ranges follow [gamepad.md](gamepad.md).
Dead zone is finite in [0,1), default 0.15 in the authoring dialog. The demo uses
0.2. Each action and each digital direction allows up to 16 unique bindings.
An axis may have 1..16 analog bindings; duplicate controller/axis pairs are
rejected even if inversion or dead zone differs. Exact duplicate buttons are
rejected, as is the same button/controller pair in both directions. In version 2,
either digital direction may be empty, but an axis needs at least one digital or
analog binding. There are at most 256 action names and 256 axis names, each at
most 128 UTF-8 bytes without control characters. Controller IDs and inversion
must have the correct types; boolean IDs and numeric inversion are rejected.

Focus/Pause/Load follow the same device rules as raw gamepad input. Focus loss
releases gameplay controls. Resume/Load sample current analog values and suppress
buttons that were already held until release/repress; they do not synthesize a
mapped press from held hardware. Stop/fresh Play resets graph state. Replays
preserve exact logical state without opening physical devices.

## Persistence and verification

Input checkpoint version 4 introduced version-2 binding definitions; current
version 5 also preserves context enabled state and action suppression. Both embed bindings
alongside raw device state and polling edges. Input/event/latent restoration
retains mapped state and pending callbacks without redispatching old transitions.
Whole-game Load checks that the input bindings agree with the saved scene and
stages validation before committing. Malformed or incompatible data leaves the
live game and saved bytes intact. Full-game compatibility still requires the
same program/resources; this is not a cross-build save migration mechanism.

`tests/test_input.py` exercises old version-1 and new mixed bindings, malformed
data, dialog correction/Undo/Redo/save/reopen, and actual native execution.
`tools/gamepad_probe/main.cpp` adds multi-device handoff, tie resolution, trigger
inversion, D-pad mixing, strict native validation and queued checkpoint recovery.
`tools/verify_input_bindings_workflow.py` compares four native hosts, fresh-process
restoration and GPU pixels. `tools/verify_input_bindings_editor.py` edits the real
dialog and drives the real embedded host with physical Windows keyboard/mouse
input and an SDL virtual gamepad. See [validation-report.md](validation-report.md)
for measured results and fingerprints.

Runtime rebinding nodes, context priority/consumption, analog-to-action thresholds, device
assignment for local multiplayer and binding preferences saved separately from
the game remain open. Physical USB/Bluetooth models, wireless reconnect and
mapping databases need hardware evidence. This delivery does not complete the
engine or certify other platforms/DPI configurations.
