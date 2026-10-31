# Typed custom events

Custom events let independent gameplay paths exchange typed data. Define one
signature per scene; the editor creates five nodes from it. They share the
existing native runtime and Flecs observers in preview and exported games.
The current builtin registry has 873 definitions; each scene event adds five
scene-owned definitions, rather than five new builtin systems.

## Authoring

Choose **Graph > Define Event…**, enter a name and add typed parameters with JSON
defaults. All 40 existing value types are supported: float, int, bool, string,
vec2, vec3, vec4, quat, mat4, entity, and homogeneous arrays/string-keyed maps and insertion-ordered unique sets
of those ten types.
Create the signature with OK; creation is one shared Undo/Redo step. Cancel
discards it. Search its name in Events & Signals, then add its nodes:

| Node | Purpose |
|---|---|
| On EventName | Handle deliveries to the configured Receiver |
| Send EventName | Queue a payload for one Recipient |
| Broadcast EventName | Queue a payload for every active receiver of this event |
| Subscribe EventName | Enable that recipient's handlers |
| Unsubscribe EventName | Disable them and invalidate their queued deliveries |

Copy/Paste preserves typed connections and participates in Undo/Redo. Pasting
nodes from another project requires matching event/function IDs and signatures;
the whole selection is rejected before changing the graph if any copied node
is unavailable, incompatible, or disallowed in the current function scope.

On EventName has static **Receiver** and **InitiallySubscribed** Inspector values;
data wires into these two inputs are rejected. Empty Receiver means the scene.
All handlers for the same `(event, Receiver)` must agree on their initial state.
The entity must exist in the scene at compilation. Multiple handlers can listen
to the same receiver; subscription operations control that group together.

Send/Subscribe/Unsubscribe accept dynamic **Recipient** entity inputs. Send and
Broadcast also accept an explicit **Sender**; empty means the scene. Wire Get
Self when the current handler's receiver should be the sender. A nonempty sender
or recipient must identify an existing entity. Sending to a valid but unhandled
or disabled recipient is a no-op after payload validation. Subscribe/Unsubscribe
require a handler group; they report a node error if none exists.

On EventName exposes **Sender**, **Receiver**, and every payload parameter along
its Out execution path. These values can pass through nested branches/loops or
into functions. They cannot be read from unrelated execution paths. Get Self
inside the handler returns Receiver; previous Self and temporary locals are
restored afterward, including on error. Handlers belong in Gameplay. Action
functions can send, broadcast and change subscriptions; pure functions cannot.

## Delivery and ordering

Payloads are immutable value snapshots captured when sending. Later variable
edits cannot change a queued message. Signed 64-bit integers, UTF-8 text with
embedded NUL, entity references and collection elements preserve their types.

Handlers are bound before On Game Start. Delivery is queued, not recursively
invoked from the sending node. The frame phases are:

1. Initial entity Created/Enabled notifications, then On Game Start and its queued events.
2. Each frame advances input, resumes latent tasks, drains input/custom callbacks
   and dispatches UI input, then runs On Update and drains events.
3. Timers, fixed physics and animation have their own callback/event drain phases.
4. On Late Update and its events precede incrementing public frame/time counters.

See [frame events](frame-events.md) for the complete phase order and
[entity lifecycle](entity-lifecycle.md) for inactive-receiver delivery and the
synchronous before-deletion exception. Destroyed cannot be sent or queued.

FIFO deliveries run until the queue is empty or the shared instruction budget
fails. A handler's Send/Broadcast appends to the same queue. Broadcast captures
the currently enabled receiver groups in lexicographic entity-ID order (scene
first); handlers within one group run in stable node-ID order.

Changing a subscription's enabled state invalidates older queued deliveries for
that group. Unsubscribe followed by Subscribe therefore does not resurrect old
messages. Duplicate Subscribe or duplicate Unsubscribe is idempotent. If a
handler unsubscribes its own receiver, the other handlers for the current
delivery still execute; subsequent queued deliveries are skipped.

Entity activity is checked separately. An inactive entity or ancestor prevents
delivery without changing its subscription preference. Deactivation also
invalidates queued deliveries; unlike Unsubscribe, deactivation during a callback
stops the remaining callbacks for that delivery. See [activity](activity.md).

Custom events sent by timer handlers run after the timer dispatch phase, not
between its due timer callbacks. For example, an unsubscribe in a later timer
callback can cancel a broadcast queued by an earlier callback that frame.

Editor Pause freezes simulation. Stop and scene/graph reload create a fresh
event world, clear queued messages and restore initial subscriptions. The native
snapshot includes enabled subscription groups and pending-delivery count.
Runtime subscriptions and pending messages are not saved in project documents.

## Bounds and native implementation

- At most 256 event definitions, each with at most 32 parameters.
- Event names are unique ignoring case, nonempty, at most 128 characters and
  contain no control characters. Parameter names are ASCII identifiers up to
  64 characters. In, Out, Recipient, Receiver, Sender and InitiallySubscribed
  are reserved.
- Existing value limits still apply: 65,536 collection elements and 1 MiB per
  string, plus valid finite numbers and signed 64-bit integers.
- One payload is limited to a conservative 16 MiB storage estimate. The queue
  allows at most 4,096 receiver deliveries and a 64 MiB estimate. Broadcast
  preflights all recipients before enqueuing; the full payload is charged per
  receiver even though immutable storage is shared internally.
- Each delivery and handler consumes the common instruction budget. Cyclic
  emissions fail at an originating node instead of recursing indefinitely.
  Dispatch errors discard the remaining queue before propagating the error.

`runtime/src/events.cpp` owns the queue and subscriptions. Each event type and
receiver has an actual Flecs identity; `ecs_emit` invokes receiver observers.
Observers snapshot the listeners; graph handlers run immediately after ecs_emit,
outside its defer scope, so spawning and destroying entities inside a handler is
safe. Exceptions propagate through the existing node-error protocol. Entity
destruction cancels owned queued deliveries/subscriptions and stops remaining
listeners for that receiver. Interpreter and generated typed C++ use the same
Send/Broadcast/subscription/dispatch functions. No Python event runtime ships
with the exported game.

Graph document version 1 now accepts an optional root `event_definitions` array:

```json
{"id":100001,"name":"Turn","parameters":[{"name":"Angle","type":"float","default":15}]}
```

IDs range from 100000 to 199999. The On/Send/Broadcast/Subscribe/Unsubscribe node
IDs are event ID plus 0/100000/200000/300000/400000 respectively. They remain
stable when a name changes in a document, are distinct from builtin/function
IDs, and are scoped to the scene. A function body inherits its scene's root
definitions; it cannot declare nested events. Event-definition deletion and
dynamic handler graphs remain later work. Whole-game Save/Load preserves queued
deliveries, cancellation epochs, subscriptions, binding identities and suspended
event-handler payloads for a matching program/resource identity; see
[persistence](persistence.md). Builtin scene ECS and hierarchy are implemented;
see [entities](entities.md).

## Editing a signature

Choose **Graph > Edit Event Signature…**. Selecting any of the event's five node
roles opens that event directly; otherwise the searchable picker lists the
current scene's events. Change the name, reorder/rename parameters, edit their
types/defaults, or add/remove eligible parameters, then choose **Apply**.

The entire candidate is validated before mutation. The edit migrates Gameplay
handlers, Send/Broadcast nodes and all action-function senders together. Event
and node IDs, positions, custom labels, fixed Sender/Receiver/Recipient routing,
initial subscriptions and payload wires remain associated with their original
parameters, including simultaneous name swaps. New parameter defaults populate
existing senders; changing an existing default preserves captured sender values.
Only senders created afterward use that changed default. Compatible type edits
must keep every authored value and sender/handler wire valid; an incompatible old
default may reset to the new typed default, but non-default values are protected.

Removing a connected parameter or a non-default sender literal is rejected with
a diagnostic in the dialog. Disconnect/reset it first. Cancel and unchanged Apply
leave the graph and Undo history untouched. A valid edit is one Undo step and
preserves earlier node edits; a canvas failure rolls the transaction back. Library
nodes, the function editor and saved/reopened projects use the updated signature.
Other scenes keep their independent definitions even when event IDs coincide.

Apply/Undo/Redo reload an available native preview from its initial state. A
running preview resumes; a paused/stopped preview stays stopped. Live deliveries
and suspended invocations are not migrated across edits, and old game saves still
require matching program/resource identity. This is authoring-time refactoring.

`examples/event_signature_demo/project.json` was edited through these dialogs.
**Publish Turn** broadcasts **Rotate Notice(Degrees, Note)** from inside a function.
The event parameters are reordered to Note/Degrees, and the new Degrees default
is 5; existing broadcast values remain 15 and the targeted boost remains 90.
At 120 fixed frames the player rotates to `[0,210,0]`, while the partner has
unsubscribed at one second and remains at `[0,-45,0]`. Run the standalone game
with `artifacts/demos/event-signatures/Play.cmd`. Evidence is in
`artifacts/validation/event-signatures/` and `event-signatures-*.xml`; scripts are
`tools/verify_event_signature_editor.py` and `tools/verify_event_signature_export.py`.

## Example and verification

`examples/events_demo/project.json` broadcasts Turn(15) every 0.25 seconds to
two Blockbench robots. The second receiver starts disabled and subscribes at
On Game Start. At one second it unsubscribes, while Send Turn(60) boosts only
the first robot. Both handlers call a reusable Turn Robot action function.
At 120 frames/60 Hz their Y rotations are +180 and -45 degrees; cancellation
removes the partner's queued fourth turn at the one-second boundary.

```powershell
.\tools\build.ps1 -Project examples/events_demo/project.json
.\.venv\Scripts\python.exe -m editor.main examples/events_demo/project.json
.\.venv\Scripts\python.exe -m pytest tests/test_events.py -q
.\.venv\Scripts\python.exe tools/verify_events_workflow.py
```

The desktop workflow additionally authors a Notice event with an integer payload,
receives its default value 7, verifies Undo/Redo and save/reopen, exercises native
Pause/Stop/resubscribe, and compares standalone GPU frames/state. Read the
recorded results and platform limits in [validation-report.md](validation-report.md).


## Named Struct and Enum ports

Signature editors also accept declared `struct:Name` and `enum:Name` types.
Defaults and payloads must match the declaration, including nested field types
and enum labels. Compatible local signature/type refactors migrate call/handler
ports, literals and wires with shared Undo and saved-project persistence.
Both native hosts preserve nominal identities through nested function calls,
queued events and delayed execution. Checkpoint frames and pending payloads
are schema-validated before commit; a corrupted nominal tag or field value
rejects restoration transactionally. Existing 32-port signature limits apply.
Project-wide type refactors synchronize these signatures across scenes; see
[project-types.md](project-types.md). User-defined collection elements remain
open. See [typed-data.md](typed-data.md) and the validation report.
