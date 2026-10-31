# Frame lifecycle events

On Game Start (1001) runs once when gameplay starts. On Update (1002) and On Late
Update (1005) run once per active host frame. On Fixed Update (1004) runs once per
1/60-second simulation step, which may occur zero or several times in a frame.
These are global Gameplay entry nodes. Multiple entries of the same kind run in
stable node-ID order. Functions may be called from them, but event entries belong
in the Gameplay graph.

Both interpreted Preview and generated games use this frame order:

On a fresh Play, initial [entity Created/Enabled events](entity-lifecycle.md) are
queued and drained before On Game Start. Checkpoint Load does not repeat them.

1. Capture the frame's Time Scale and advance input. Resume pending latent graphs
   in suspension order, drain ordered keyboard/mouse/action callbacks and custom
   events, then dispatch queued UI input. Input-handler delays begin advancing
   on the following frame.
2. Run On Update, then drain custom events.
3. Advance scaled/unscaled timers, dispatch timer callbacks and drain events.
4. Run fixed physics steps: Fixed Update, simulation, pose synchronization and
   collision/trigger callbacks for each step.
5. Advance audio with the unscaled delta and animation with the scaled delta,
   then dispatch animation completion callbacks and their queued events.
6. Run On Late Update, then drain custom events sent by those handlers.
7. Advance public frame/time counters, update UI and dispatch UI events.
8. Process a pending whole-game Save/Load request, then render in the SDL host.

Pointer delta and wheel reset during input advancement and accumulate that
frame's events. Absolute position persists. All phases read the same values
without consuming them, including Late Update and Time Scale zero.

Use On Late Update for Camera Follow and other work that needs the current
frame's final physical transform or advanced animation time. Get Delta Time in
this phase returns the enclosing scaled frame delta, restored after fixed steps.
Get Frame Count and Get Game Time still refer to the start of the frame, as in
On Update. A scale change takes effect in the following frame.

On Update and On Late Update still run at Time Scale zero. Editor Pause stops
the host loop and both callbacks. Stop rebuilds initial state, and the next Play
runs On Game Start again. Loading a checkpoint restores the saved world and
counters; the next frame uses the current program's late handler as usual.

Late Update is not another physics step. Forces applied there are consumed by
the next simulation step. Timers started there first advance in the next host
frame; even a zero-duration timer cannot run retroactively in the current timer
phase. Audio/animation playback started there receives its next time advance in
the next frame. Widget changes are visible in the following UI update of the
same frame. Save/Load requests remain deferred until the normal frame boundary.

Existing graphs and IR documents without a late phase keep working. The C++
exporter emits an empty OnLateUpdate for them. Host loading validates required
start/update and optional fixed/late/quit event arrays before replacing a live world.
A failed reload preserves the current world and editor graph.

Open `examples/late_update_demo/project.json`. An animated Blockbench robot moves
through physics, while the camera follows its final position from Late Update.
Two stationary robots make the camera movement visible. A/D select left/right
velocity; Space stops movement. 0/1/2 select frozen/normal/double time, and S/L
save/load from late callbacks. `tools/create_late_update_demo.py` authors it via
the same Python GraphBuilder used by other examples.

```powershell
.\tools\build.ps1 -Project examples/late_update_demo/project.json
.\.venv\Scripts\python.exe -m pytest tests/test_late_update.py tests/test_core.py -q
.\.venv\Scripts\python.exe tools/verify_late_update_workflow.py
.\.venv\Scripts\python.exe tools/verify_late_update_editor.py
```

See [validation-report.md](validation-report.md) for completed checks and current
limits. Entity Created/Enabled/Disabled/Destroyed are implemented; Destroyed runs
inside the structural operation before deletion. Quit Application and
On Application Quit now finish at a host boundary, with bounded cleanup/save
draining and no extra simulation frame; see [application quit](application-quit.md).
Game Pause/Resume are queued state-transition handlers for Pause/Resume World;
see [world pause](world-pause.md). They do not replace the editor's debugging pause.
Scene Loaded remains separate work.
