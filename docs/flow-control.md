# Flow control: loops, persistent gates and latent execution

Break Loop (2005) and Continue Loop (2006) are execution nodes in category 02.
Connect their In port from inside a For Loop, While Loop or any typed For Each
Body. They have no output port and do not accept a target loop reference.

Break stops the nearest enclosing loop and runs that loop's Done path once.
Continue skips the rest of the current iteration, including subsequent Sequence
branches inside that iteration. For/For Each advance to the next iteration;
While reevaluates its condition. Done runs when the loop ends, including an empty
loop, but does not run once per Continue. A Continue-only While with a permanently
true condition still exhausts the normal instruction budget.

Both controls are lexical: an inner loop consumes its own controls. A control
on an inner loop's Done path belongs to the enclosing outer Body, if one exists.
A control on the outermost Done path is invalid. Sharing a control node between
a loop Body and an event entry also fails validation, even if a runtime branch
would avoid the invalid path.

Action functions can use these nodes inside their own loops. They cannot break
or continue a caller's loop. Return continues to leave the entire current
function, including all its nested loops. Pure functions cannot contain execution
nodes. Disconnected nodes may remain on the canvas while editing; every reachable
control must have a valid loop scope before Preview or Export succeeds.

For Each snapshots its input array once. Changing the source collection during
the body cannot invalidate the traversal. Item/Index remain scoped to Body and
are removed when it exits, including Break/Return. Function calls keep the
caller's local values separate. Instructions in the skipped portion are not
evaluated and cannot mutate the world or consume instruction budget.

For graphs without latent nodes, the Python compiler emits typed structured IR. The native
interpreter propagates an internal control result until the nearest loop consumes
it. C++ export emits ordinary break/continue statements. Both paths tick the
originating node before executing the control; raw interpreted IR cannot use an
unscoped control to escape a function or event. No persistent loop-control state
is introduced for these synchronous loops. Whole-game saves occur at frame
boundaries after execution has finished or yielded on a latent node.

## Example

Open `examples/loop_control_demo/project.json`, authored by
`tools/create_loop_control_demo.py`. Its Select Available Robot action function
scans the sorted entity list, uses Continue to skip the camera/inactive robots,
and uses Break when it selects the first available target. The caller enlarges
the selected robot and displays its name. Visited/scans variables expose exactly
how much of the list ran.

- 1/2/3 toggle each robot's availability.
- Space scans again; no available target yields an empty reference.
- S/L save/load selection, activity, animation and variables.
- Initially robot 1 is inactive, so robot 2 is selected after three visits:
  camera, robot 1, robot 2. Robot 3 is not visited.

The standalone package is
`artifacts/demos/loop-control-playground/Play.cmd`.

```powershell
.\tools\build.ps1 -Project examples/loop_control_demo/project.json
.\.venv\Scripts\python.exe -m pytest tests/test_loop_control.py tests/test_core.py -q
.\.venv\Scripts\python.exe tools/verify_loop_control_workflow.py
.\.venv\Scripts\python.exe tools/verify_loop_control_editor.py
```

## Persistent gates

Four additional category-02 nodes keep state across event invocations and frames:

| Node | In behavior | Control inputs | Captured data |
|---|---|---|---|
| Do Once (2007) | Fires Out once until Reset | Reset allows another execution | None |
| Do N (2008) | Fires Out while the count is less than N | Reset sets count to zero | Counter, starting at 1 |
| Gate (2009) | Fires Out when open | Open, Close, Toggle | None |
| Flip Flop (2010) | Alternates A, B, A, B | Reset chooses A next | Is A |

Each control input changes state and ends its own execution path; it does not
fire Out/A/B. Other Sequence branches can still execute. A wire from a node's
downstream path back to Reset is valid, including direct Out-to-Reset feedback.
The editor allows these connections and uses the compiler's separate execution
and data cycle checks. A wire back to In remains an error before Play or Export.
Invalid cycles may appear temporarily while editing; validation reports them.

Do N accepts a nonnegative signed 64-bit limit. N=0 blocks every entry. Changing
N preserves the existing count: raising it permits additional entries, while
lowering it blocks until the limit exceeds the count or Reset runs. A blocked
entry does not increment the count. Reset does not evaluate the unused N input.
Gate's Start Closed value initializes state on first use only; later input
values do not overwrite Open/Close/Toggle decisions. Its input expression is
still evaluated on each entry. Flip Flop begins with A.

Counter and Is A capture the accepted entry's result. They are available only
inside that node's emitted execution branch, including nested branches/loops.
They cannot be read from a separate event or after the branch has ended. Loop
Break/Continue and function Return propagate through the selected branch.
An action function with result ports must still return on every path: a gate
that can block does not establish a guaranteed return, while both returning
branches of Flip Flop do.

Owner defaults to the empty entity reference, giving scene-wide state for that
node. Set Owner to a live entity to partition it by entity ID. Missing owners
fail at the originating node. State is keyed by node identity and owner, not
by call site: the same node inside an action function shares state across calls
for the same owner, using its qualified function/node ID. Different owners stay
independent. These nodes cannot appear in pure functions.

Inactive owners keep their state, and explicit gate commands can still target
them. Existing event receivers follow their ordinary activity rules. Clone
starts with fresh owned state; Destroy and prefab removal erase the removed
entities' state. Empty-owner state is unaffected. Stop/reload clears all values.
The runtime permits at most 4,096 allocated owner/node states and 65,536 bound
node identities. Reaching either limit reports an error instead of discarding
existing state.

Whole-game checkpoints include exact bindings, owner IDs, counters and gate/flip
flags. Restore validates these in the staged context before replacing the live
world; incompatible bindings, nonexistent owners, duplicates and impossible
values reject the load. Older whole-game schemas require a new compatible save;
progress variables/JSON remain readable. See [persistence.md](persistence.md).

`examples/stateful_flow_demo/project.json` controls one animated Blockbench robot:
O lifts it once, N steps right up to three times, G toggles rotation, F alternates
its size, R resets, and S/L save/load. It is authored with
`tools/create_stateful_flow_demo.py`; the standalone launcher is
`artifacts/demos/stateful-flow-playground/Play.cmd`.

```powershell
.\tools\build.ps1 -Project examples/stateful_flow_demo/project.json
.\.venv\Scripts\python.exe -m pytest tests/test_stateful_flow.py tests/test_core.py -q
.\.venv\Scripts\python.exe tools/verify_stateful_flow_workflow.py
.\.venv\Scripts\python.exe tools/verify_stateful_flow_editor.py
```

## Multi Gate

Multi Gate (2011) exposes eight execution outputs, Out 0 through Out 7, and a
captured integer Index. Branches selects how many leading outputs are active,
from 1 to 8 (default 2). Each In fires exactly one unused active route. An
unconnected output still counts as visited. Index is zero-based and available
only on the selected execution path. This node currently has eight fixed ports;
it does not support adding arbitrary output ports in the editor.

With Random=false, routes run sequentially with wraparound until each has run
once. Random=true chooses uniformly among the remaining routes, using the shared
seeded generator. It does not repeat a route within a cycle. Start Index=-1 means
start at 0 for sequential selection or draw randomly. An explicit Start Index
from 0 through Branches-1 forces the first route of each cycle, including in
random mode. Subsequent selections follow the chosen mode.

Loop=false blocks after all active routes have run. Loop=true clears the visited
set on the next In and starts another cycle; it does not execute an additional
route immediately on completing a cycle. Switching Random or Loop preserves
the current visited set. Changing Branches starts a fresh cycle on the next In.
Start Index changes affect the next fresh cycle; its value must remain valid
for the current Branches even when this cycle has already started.

Reset clears the visited set and cursor without firing an output. It evaluates
only Owner, ignoring Branches/Random/Loop/Start Index. Reset does not reset or
advance the random stream. Blocked entries, sequential selections, explicitly
forced first routes and choices with only one remaining route do not draw a
random number. Set Random Seed explicitly when a repeated random sequence is
required. Owner, clone/destruction, function sharing, scoped outputs, loop
controls and Stop/reload follow the persistent-gate rules above.

Whole-game saves preserve the active route count, visited mask, cursor and
shared random stream. Restore rejects out-of-range bits, an inconsistent cursor,
impossible empty progress, duplicate records, unknown owners and extra fields.
Full restoration still requires the exact program/runtime identity.

`examples/multi_gate_demo/project.json` tours four stations with an animated
Blockbench robot. Space chooses the next route, M switches random mode, T
switches looping, R resets the gate/history and seed 42, and S/L save/load.
The HUD displays route history and both modes. Its standalone launcher is
`artifacts/demos/multi-gate-playground/Play.cmd`.

```powershell
.\tools\build.ps1 -Project examples/multi_gate_demo/project.json
.\.venv\Scripts\python.exe -m pytest tests/test_stateful_flow.py tests/test_core.py -q
.\.venv\Scripts\python.exe tools/verify_multi_gate_workflow.py
.\.venv\Scripts\python.exe tools/verify_multi_gate_editor.py
```

## Delay and Wait Until

Delay (2012), Wait Until (2013) and Retriggerable Delay (2014) suspend their current
execution chain and resume its Out path without blocking the host. Delay takes
finite nonnegative Seconds and an Unscaled flag. Wait Until checks Condition
immediately and continues synchronously if true; otherwise it reevaluates that
expression once per active host frame. Context reads see the current world;
function parameters, event payloads and earlier action outputs remain captured.

Pending graphs run after input advancement and before UI input/On Update, in
suspension order. New waits first advance in the next scheduler batch. Zero
Seconds always yields, including inside loops. Start-created waits are eligible
in the first frame. Scaled waits freeze at Time Scale zero; unscaled waits and
Wait Until still advance. Editor Pause stops all of them. A fractional frame
remaining after a delay expires is not passed to another delay created by its Out.

Each qualified node ID and Owner can have one pending invocation. Delay and Wait
Until ignore reentry while pending, without evaluating Seconds/Condition again.
The ignored invocation ends, including its caller chain. Retriggerable Delay
replaces the old invocation with the new caller, captures and full duration.
Separate lifecycle entries and event handlers have independent execution chains.
Sequence Then waits for First's chain to finish; it does not run in parallel.

Owner defaults to empty (global). Nonempty owners must exist. An inactive owner
freezes its remaining time and condition polling. Destruction/prefab removal
cancels its pending chain; clones receive no pending work. Stop/reload clears all
continuations. After a wait resumes, destroying its owner also ends that chain.

For/While/typed For Each retain iteration position across a suspension. For Each
captures its array once. Break/Continue still target the current function's
nearest loop. Action functions retain their parameters and caller stack, then
return typed results normally. Pure functions cannot contain latent nodes.
Generated C++ supplies typed expression/action callbacks to the shared scheduler;
it does not execute node actions through the JSON interpreter. Graphs without
latent operations retain the original direct execution path.

Whole-game saves preserve pending chains, remaining durations, loop snapshots,
scoped locals and function frames. Load stages and validates the entire stack
against the current immutable program before replacing live state. It rejects
unknown owners, invalid block positions/callers, missing or mistyped captures,
inconsistent loop state, duplicate waits, invalid serials and extra fields.
Limits are 256 pending chains, 128 captured frames including the event root,
1024 execution segments per frame and 32 MiB total pending state, in addition to
the existing per-frame instruction budget. Errors cancel the active chain and
report its originating node; prior world mutations follow normal graph behavior.

Open `examples/latent_flow_demo/project.json`, or run
`artifacts/demos/latent-flow-playground/Play.cmd`. Space starts the four-station
Blockbench robot tour. Each destination returns from a delayed function inside
For Each. R restarts a separate half-second signal delay. S/L save/load midway.

```powershell
.\tools\build.ps1 -Project examples/latent_flow_demo/project.json
.\.venv\Scripts\python.exe -m pytest tests/test_latent_flow.py tests/test_stateful_flow.py -q
.\.venv\Scripts\python.exe tools/verify_latent_flow_workflow.py
.\.venv\Scripts\python.exe tools/verify_latent_flow_editor.py
```

Worker-thread async tasks, public task handles/cancellation nodes and arbitrary
parallel branches remain later work. Latent graph execution runs on the game thread.

## Switch and Select

Switch Integer (2015) and Switch String (2016) evaluate Value once and execute
exactly one matching case, or Default if nothing matches. There is no fallthrough.
An unconnected matching output ends that path; it does not run Default. Integers
retain the full signed 64-bit range. String matching is exact and case-sensitive,
including Unicode and embedded NUL characters.

Select a Switch in Gameplay or in an action function and click **Edit Cases…** in
the Inspector. Add, remove, reorder and edit up to 256 unique case values. Zero
cases is valid and always selects Default. Every case has a stable internal ID;
changing its value or order keeps its existing wire. Removing a case removes its
wire. One Undo restores both, and earlier connection commands remain usable.
Node labels display case values; Default always remains. Duplicate/copy/paste and
project/function save/reopen preserve the case identities. Forged clipboard port
names/settings are rejected before graph mutation.

Python authoring uses the same metadata, for example:

```python
b.add('route', 'Switch Integer', Value=2,
      cases=[{'id': 'walk', 'value': 1}, {'id': 'run', 'value': 2}])
b.connect('route', 'Case run', 'move', 'In')
b.connect('route', 'Default', 'idle', 'In')
```

Break/Continue/Return retain their enclosing loop/function behavior on every
Switch path. A function with outputs must return through every case and Default.
If a branch suspends, its choice remains captured even if Value changes while
waiting. Checkpoints preserve that selected branch and reject invalid routes,
child blocks or control kinds during staged restoration.

The 40 Select variants cover all ten scalar types and their array/map/set forms. Condition is evaluated once for each use. Only the
chosen True or False expression runs. Unselected divisions, missing-variable
reads and other pure expressions cannot raise runtime errors or consume budget.
Both inputs still require valid types, acyclic wiring and valid execution scope
at compile time. Action-result outputs represent earlier captured executions;
Select does not undo or defer those actions. Select works in pure/action functions
and in latent graphs. Both native paths use the same lazy selection helper, with
typed callbacks in exported C++.

`examples/switch_select_demo/project.json` routes the Blockbench robot through a
delayed Switch inside an action function. 1/2/3 choose left/center/right, 9 uses
Default, Space applies, M mirrors the destination through Select, and S/L
save/load while suspended. A String Switch controls facing from the returned
route label. Standalone: `artifacts/demos/switch-select-playground/Play.cmd`.

```powershell
.\tools\build.ps1 -Project examples/switch_select_demo/project.json
.\.venv\Scripts\python.exe -m pytest tests/test_switch_select.py tests/test_switch_editor.py -q
.\.venv\Scripts\python.exe tools/verify_switch_select_workflow.py
.\.venv\Scripts\python.exe tools/verify_switch_select_editor.py
```

Enum/state-machine dispatch and range/pattern matching remain separate work.
The new per-instance case editor does not change Multi Gate's fixed eight ports.
