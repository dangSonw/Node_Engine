# Gameplay input contexts

Open `examples/input_contexts_demo/project.json`, or run
`artifacts/demos/input-contexts-playground/Play.cmd`. A/D, arrows, D-pad and left
stick move the Blockbench robot; Space, left mouse and South turn it. M opens or
closes the menu by toggling gameplay input. Raw S/L save/load remain available.
`Replay.cmd` exercises the transitions without requiring a physical controller.
The menu gates input only; simulation time, animation and timers keep running.

## Authoring and nodes

**Scene > Input Actions and Axes > Contexts** lists named contexts, their initial
enabled state and a member-selection dialog for existing action/axis names.
Accept validates the whole scene input definition, participates in scene
Undo/Redo, reloads the same preview process and survives save/reopen/export.
Renaming or deleting a referenced binding requires correcting its membership;
missing members stay visible for removal and prevent acceptance until corrected.

| Node | Stable ID | Behavior |
|---|---|---|
| Set Input Context Enabled | 10021 | Execution input/output, Context string and Enabled boolean; changes runtime state. |
| Is Input Context Enabled | 10022 | Context string to boolean; reads current runtime state. |

Both default to context `gameplay`. Literal unknown names fail compilation at
the offending node; dynamic unknown names fail at runtime with node attribution.
An unchanged enabled value has no side effects. These two nodes bring the
builtin registry to **519**. Existing action/axis nodes remain the gameplay API.

Binding **version 3** extends the version-2 keyboard/mouse/gamepad schema with
a required `contexts` object. For example:

```json
{
  "version": 3,
  "actions": {"turn": ["Space", {"button": "South", "controller": 0}]},
  "axes": {"horizontal": {"negative": ["A"], "positive": ["D"]}},
  "contexts": {
    "gameplay": {"enabled": true, "actions": ["turn"], "axes": ["horizontal"]}
  }
}
```

Versions 1 and 2 remain accepted without contexts. There may be at most 64
contexts. Names are case sensitive, 1–128 UTF-8 bytes, with no control characters.
Each definition has exactly `enabled`, `actions` and `axes`, with a strict
boolean and unique existing member names. At least one member is required;
each list allows up to 256 members. An empty context map is valid.

## Transition rules

- Unassigned actions and axes are always available. A member is available while
  **any** context containing it is enabled. There is no priority or consumption.
- A disabled named axis returns zero. Enabling resumes its current digital and
  analog value immediately, using the existing dead-zone/mixing rules.
- Disabling an action clears its polling edges, cancels pending mapped
  press/release deliveries, and emits one cleanup release if it is logically
  held. Raw key, mouse and gamepad reads/callbacks remain available.
- Re-enabling an already-held action suppresses it until **all** its alternatives
  have returned to neutral. A later fresh press is accepted. Switching between
  held alternatives cannot bypass this rearming rule.
- Toggling one context while another keeps a member available creates no edge,
  cancellation or suppression for that member.

Cancellation applies only to actions whose aggregate availability changes. It
also stops the remaining listeners of a mapped delivery currently executing,
even if a callback disables and re-enables the context before returning. Other
actions retain their deliveries. A raw menu callback can therefore cancel a
queued gameplay press before its listener runs; a cleanup release may still
follow if that action was held. Conversely, pending releases can be canceled.
Callbacks are not a guaranteed balanced press/release history across context
changes. Use Is Action Held when the current state matters.

Already-dispatched latent graphs, such as a Delay from an earlier press, continue;
changing input availability does not cancel ongoing game logic. Contexts are
scene-wide, not per entity or player. RmlUi interception rules are unchanged.

## Save/Load and physical controls

Input checkpoint **version 5** stores the binding definition, enabled context
names and suppressed actions alongside raw device state and polling edges.
Runtime toggles leave authored initial defaults unchanged. Exact replay and
fresh-process restoration retain queued cleanup releases, suppressed held
actions and delayed callbacks. Invalid names, duplicates, impossible suppression
or queued presses for unavailable actions reject during staged restoration.
Failure leaves the live game and saved bytes unchanged.

Physical Load/Pause clear transient raw input and reconcile live devices while
retaining runtime context enabled state. The host suppresses already-held
hardware until release/repress; current analog samples resume where the context
allows them. Focus loss releases held input without disabling contexts.
Stop/fresh Play restores the authored initial enabled states.

Standalone input checkpoints 1–4 remain readable with their older semantics.
Whole-game saves still require the exact program/resource compatibility checks;
the checkpoint reader does not provide cross-build game-save migration.

## Verification and boundaries

`tests/test_input_contexts.py` covers schema rejection, dialog editing and
roundtrips, compiler diagnostics, and interpreted/generated native traces.
The gamepad probe covers overlapping contexts, in-flight listener cancellation,
rearming, malformed checkpoint rollback and legacy readers. The workflow tool
compares four native hosts, independent-process restoration and GPU pixels.
The editor verifier uses actual Qt controls and embedded SDL, Windows keyboard
and focus transitions, plus SDL virtual gamepads. See
[validation-report.md](validation-report.md) for measured results and hashes.

Runtime rebinding, priority/consumption, analog-to-action thresholds, durable
player/device assignment and separately saved binding preferences remain open.
Physical USB/Bluetooth compatibility and other platforms/DPI configurations
require their own evidence. The complete engine goal remains active.
