# Entity lifecycle events

The four Gameplay entry nodes are **On Object Created** (1006), **On Object
Enabled** (1007), **On Object Disabled** (1008), and **On Object Destroyed** (1009).
Each has a constant
**Receiver** in the Inspector: empty listens to all entities; a scene entity ID
listens only to that entity. Receiver data wires are rejected. A receiver must
exist in the authored scene. Cloning an entity copies its data, not its handlers.

The Out execution path exposes **Entity** and **Active**. Entity is the changed
object; Active captures its effective activity, including all ancestors, when
the change happens. Enabled always carries true and Disabled always carries
false. Created and Destroyed can carry either. Get Self is the configured Receiver (empty for
a global handler); wire Entity when operating on the changed object. Outputs
are scoped to their handler and can pass through action functions or Delay.

## Timing and order

After resources and bindings are ready, a fresh Play queues initial Created
events, plus Enabled for initially active entities, and drains them **before
On Game Start**. Initial inactive entities receive Created(false), without an
initial Disabled event. Stop resets this state; the next Play repeats startup.
Resuming Pause does not repeat startup. Loading a game checkpoint restores the
saved state without repeating initial lifecycle callbacks.

Runtime Spawn Entity, Create Camera, Clone Entity, and prefab Instantiate emit
Created once the entity has been assembled; an initially effective-active entity
also emits Enabled. Set Entity Active, Set Parent, prefab Reset and Apply compare
effective activity before and after the complete operation. A parent toggle
therefore notifies every affected descendant. Setting the same value, or changing
a child's local flag while its parent still keeps it inactive, emits no transition.
Prefab Reset emits Created again for a missing member that it recreates under
its stable ID. Surviving members are not reported as newly created. Temporary
worlds used to validate physics/prefab edits or Load do not emit gameplay events.

Created/Enabled/Disabled share the existing Flecs-backed FIFO event queue. They run at the
next event drain, after the current graph chain finishes, rather than recursively
inside a mutation. For one mutation, affected IDs are sorted lexicographically;
Created precedes Enabled for each new ID. A global delivery precedes the matching
owned delivery, and listeners within a delivery run in stable graph node-ID order.
Callbacks can make further changes, whose notifications append to the queue.
The normal shared instruction budget bounds cyclic emission.

Lifecycle listeners remain eligible while their receiver is inactive. Rapid
off/on changes retain both captured transitions, even if the current state has
changed again before dispatch. This differs from custom, timer and animation
delivery, which continues to follow its existing activity suspension/cancellation
rules. Destruction cancels remaining owned deliveries; global notifications keep
their captured Entity/Active payload. Check **Entity Exists** before reading a
possibly removed object. Destruction itself does not emit Disabled.

## Before deletion

On Object Destroyed runs synchronously inside Destroy Entity, before removing
the object or its components. It also runs for entities removed by prefab Reset
or Apply. Inactive objects receive it. The graph can read the name, transform,
tags and components, then create loot or update a score. Global handlers run
before the matching owned handlers, in stable graph node-ID order. Each removed
ID is notified once. Child subtrees and detached prefab members are included.

Calling Destroy again on an object already pending deletion is an idempotent
no-op. Other Destroy/Reset/Apply requests made inside the callback are deferred
until the current structural edit commits, then processed FIFO without recursive
native calls. A target removed by that commit is skipped. A newly attached child
joins the deletion set and receives its own callback. Reparenting an object
already pending deletion is rejected; the callback cannot rescue that object.
Queued Created/Enabled/Disabled/custom events drain after the graph chain, not
inside the pre-deletion callback.

Prefab edits validate a staged scene and physics world before callbacks. After
callbacks, they validate again to preserve callback-created objects, edits and
physics changes when committing. A failing callback or revalidation prevents the
structural commit, clears deferred destructive requests and reports the graph
node. Callback side effects already performed are not rolled back. Pending
deletion cannot be canceled by changing a prefab during its callback.

Callbacks can enter action functions even when the caller is a suspended-flow
task. Delay yields normally: deletion continues after the yield. An owned task
is canceled when its receiver is removed; a global task can resume with the
captured, now-stale Entity reference. Capture needed data before waiting, or
check Entity Exists on resume.

Stop, project/scene replacement and whole-game Load do not emit Destroyed. A Save
Game request made in the callback is processed at the normal frame boundary,
after removal and deferred work. Direct checkpoint capture during the callback
is rejected. Destroyed is never a queued message and cannot be sent or broadcast.

## Persistence and limits

Programs with these listeners use version 3 of the internal event checkpoint,
including the started flag, bindings and pending typed deliveries. Restoration
reconstructs the activity baseline from the candidate scene without callbacks.
Malformed fields, bindings, receiver states and payloads reject before replacing
the live event system. Existing programs keep their version-2 event checkpoint;
the outer save-slot format remains unchanged.

The existing limit of 4,096 queued receiver deliveries / 64 MiB applies, including
startup. A global Created plus Enabled listener produces two deliveries per
active entity. Large startup batches can therefore exceed the limit and report a
node error; they are not silently dropped. Activity comparison currently scans
the bounded scene after relevant mutations; large-scene performance remains
unbenchmarked. No new dependency or Python runtime is shipped with the game.

Destruction uses the same instruction budget, allows at most 4,096 deferred
destructive requests and 256 rounds of newly discovered removal targets.
Exceeding a bound reports an error instead of silently dropping callbacks.
Restoration rejects a forged queued Destroyed delivery before replacing live
state. Scene Loaded, game Pause/Resume and Application Quit nodes remain pending.

## Robot example and checks

Open `examples/entity_lifecycle_demo/project.json` or run
`artifacts/demos/entity-lifecycle-playground/Play.cmd`. T toggles a parent and its
robot descendants; N spawns a prefab, C clones a robot, X destroys the last spawn,
R resets the last live prefab, and S/L save/load. The HUD counts events, including
the inactive robot's own Disabled callback.

`examples/entity_destroyed_demo/project.json` extends that scene with pre-deletion
reads and loot. Run `artifacts/demos/entity-destroyed-playground/Play.cmd` without
Python or Qt. A attaches a temporary loot-bearing child to the last prefab;
R removes it with Reset, P applies its overrides, and X destroys the prefab and
its members. The HUD shows the last readable name/activity and removal/loot counts.

```powershell
.\tools\build.ps1 -Project examples/entity_lifecycle_demo/project.json
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_entity_lifecycle.py -q
.\.venv\Scripts\python.exe -X utf8 tools/verify_event_checkpoint.py
.\.venv\Scripts\python.exe -X utf8 tools/verify_entity_lifecycle_workflow.py
.\.venv\Scripts\python.exe -X utf8 tools/verify_entity_lifecycle_editor.py
```

For the Destroyed example, build its project, then run:

```powershell
.\tools\build.ps1 -Project examples/entity_destroyed_demo/project.json
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_entity_destroyed.py -q
.\.venv\Scripts\python.exe -X utf8 tools/verify_event_checkpoint.py
.\.venv\Scripts\python.exe -X utf8 tools/verify_entity_destroyed_workflow.py
.\.venv\Scripts\python.exe -X utf8 tools/verify_entity_destroyed_editor.py
```

See the latest entity-lifecycle/Destroyed entries in [validation-report.md](validation-report.md)
for exact results and platform limits.
