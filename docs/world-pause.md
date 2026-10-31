# World pause and resume

Pause World (7001), Resume World (7002) and Is World Paused (7003) control the
current simulation world. On Game Pause (1017) and On Game Resume (1018) are
global Gameplay events. The nodes are available in the Library, Python GraphBuilder,
interpreted Preview and generated C++ games.

The state changes immediately for Is World Paused. Like Time Scale, its effect on
simulation is sampled at the next frame start, so the current frame finishes with
one consistent delta. A pause during On Game Start freezes the first frame.
Resume preserves the requested Time Scale, including changes made while paused.
Resume at scale zero remains frozen; set a positive scale to advance simulation.
Time Scale zero by itself does not change Is World Paused or emit pause events.

| Work while the world is paused | Behavior |
|---|---|
| Game time, scaled delta | Frozen / zero |
| Fixed Update, physics, animation, scaled timers and scaled Delay | Frozen; remaining progress survives |
| Input and UI event handlers, Update, Late Update, Wait Until | Still execute |
| Real time, frame count, unscaled delta/timers/Delay, audio | Continue |
| UI animation clock | Uses game time and freezes; controls and text updates remain responsive |
| Whole-game Save/Load, Quit Application | Remain available |

Multiply movement by Get Delta Time or guard direct gameplay writes with Is World
Paused. Pause freezes simulation time, not arbitrary graph mutations. Use input
contexts to disable gameplay actions while keeping menu/resume controls available.
Pause Sound/Resume Sound in the lifecycle handlers can also silence selected voices.

Each actual state transition queues one event through the existing bounded event
system. Repeated Pause or Resume has no additional effect. Events run after the
current graph chain returns to event draining, with listeners sorted by stable
node ID; Out continues first. Pause followed by Resume in one chain emits both
events in request order. A state query in either handler returns the latest state.
Opposing requests made by handlers cannot recurse without bound: normal event and
instruction budgets apply, with originating-node diagnostics. Delayed callback work
uses the normal serialized continuation mechanism.
Hosts validate the optional handler array, event IDs, node strings and statement
arrays before replacing live state; malformed reloads preserve the current world.

Checkpoints store the pause flag with the game clock and preserve queued transition
events through normal event serialization. Staging validates boolean types and
binding identities before replacing live state. Loading a paused or running save
does not synthesize Pause/Resume events: use On Load Completed to react to restoration.
Version-2 clock records without the optional `paused` field default to false when
their program/resource identity is otherwise compatible. Runtime identity checks
still apply; this is not a general cross-version save migration API.

Editor Pause is a debugging control: it stops the entire preview frame loop and
audio output. Editor Play resumes that loop without changing World Pause or emitting
game transitions. Stop/reload constructs a fresh unpaused world. Saved gameplay
state does not include the editor's debugger state.

Open `examples/world_pause_demo/project.json`, authored by
`tools/create_world_pause_demo.py`. Three Blockbench robots demonstrate animation,
scaled timer rotation and physics. P/R pause/resume; 0/1/2/3 select time scale
0/0.25/1/2; S/L save/load; Q quits. The HUD counts transitions and an unscaled timer.
The standalone package is in `artifacts/demos/world-pause-playground`.

```powershell
.\tools\build.ps1 -Project examples/world_pause_demo/project.json
.\.venv\Scripts\python.exe -m pytest tests/test_world_pause.py -q
.\.venv\Scripts\python.exe tools/verify_world_pause_native.py
.\.venv\Scripts\python.exe tools/verify_world_pause_workflow.py
.\.venv\Scripts\python.exe tools/verify_world_pause_editor.py
.\.venv\Scripts\python.exe tools/package_world_pause_demo.py
```

See [validation-report.md](validation-report.md) for measured results. Pause applies
to the active world and persists across Change/Reload Scene; see [scenes](scenes.md).
Independently paused simultaneous worlds remain open. Windows is the tested platform.
