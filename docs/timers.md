# Named timers and Flecs events

Eight builtin timer nodes brought the foundation to 243 definitions at the timer
milestone. It reached 268 definitions at the later activity milestone:

| ID | Node | Behavior |
|---|---|---|
| 1003 | On Timer Finished | Receive matching timer expirations for one owner |
| 5010 | Start Timer | Create or replace a named timer; optional repeat and unscaled clock |
| 5011 | Stop Timer | Remove it, including pending catch-up callbacks |
| 5012 | Pause Timer | Freeze its remaining time |
| 5013 | Resume Timer | Continue a paused timer |
| 5014 | Timer Exists | True for a running or paused timer |
| 5015 | Is Timer Paused | True only for an existing paused timer |
| 5016 | Get Timer Remaining | Seconds left, or zero when missing |

## Authoring

Connect On Game Start -> Start Timer. Set Name, Seconds, Repeat and Unscaled in the
Inspector. Owner is an entity ID, or empty for a scene timer. The key is the pair
`(Owner, Name)`: two entities can each have a timer called `turn`.

Unscaled defaults to false, including in existing graphs. Set it to true (or
connect a Boolean) to count Get Unscaled Delta Time independently of Time Scale.
This permits a menu timer or automatic resume countdown while game time is frozen.
Starting the same owner/name replaces the timer even when its clock mode changes.
Stop/Pause/Resume/Exists/Remaining and On Timer Finished work with either mode.
Remaining is measured in seconds of the selected clock, so a scaled timer with
one second left at quarter speed takes four unscaled seconds to finish.

Add On Timer Finished. Set Receiver to the same owner, and Filter to the exact
name. An empty Filter receives every timer name belonging to that receiver.
Receiver and Filter are static Inspector values and reject data wires.
Subscriptions are bound before On Game Start. A missing receiver entity is a
compile error. Timer action/query Owner inputs may use data wires.

Name and Owner outputs are available only along that event's Out execution path,
including nested loops, branches and calls to functions. Get Self in a handler
returns its owner (empty for a scene timer); the previous Self and temporary
locals are restored afterward, including on error. Event entry nodes belong in
Gameplay; action functions can start/control timers.

## Timing and cancellation

- On Game Start runs before timer callbacks. Even a zero-second one-shot waits
  for the first update.
- Each frame runs On Update, drains queued custom events, advances timers by their selected delta,
  dispatches expirations and drains custom events again. Physics and animation
  then advance, followed by Late Update and the public frame/time counters.
  See [frame phases](frame-events.md). Get Game Time/Get Frame Count in
  timer callbacks therefore refer to that frame's start, as in On Update.
  Timers started in On Update count that frame's selected delta.
- Expirations run in order of their position within the current host frame,
  with creation order breaking exact ties. Each deadline is compared against its
  own clock and divided by that clock's frame step. Repeating
  timers catch up all elapsed intervals, interleaved with other due timers.
  Listeners for the same owner run in stable node-ID order.
  Callbacks still dispatch at the timer phase, not between physics substeps.
- A one-shot is removed before its handlers run. A repeating timer advances its
  deadline before delivery. Stopping/replacing it in a handler cancels further
  old catch-up callbacks; all matching listeners still receive the current event.
- Timers created, replaced or resumed inside callbacks join the next frame's
  batch. Zero-second callback restarts execute at most once per frame.
- Pause/Resume are idempotent. Stop/Pause/Resume of missing timers do nothing;
  queries return false/zero. Invalid entity owners still produce errors.
- Editor Pause freezes all timers; Play resumes them. Stop, scene/graph reload
  and a fresh runtime clear timers and rebuild subscriptions. Timers are runtime
  state and are not automatically saved in project files.
- Entity activity also suspends owned timers, including inactive ancestors. This
  preserves remaining time independently of manual Pause/Resume; scene-owned
  timers continue. See [activity and layers](activity.md) for callback cancellation
  and reactivation rules.

Durations must be finite and nonnegative; repeating durations must be positive.
Names use the existing bounded name rules: 1-512 UTF-8 bytes, not whitespace
only, no NUL. At most 4,096 running/paused timers may exist. Each expiration and
listener uses the shared instruction budget, including when no listener matches.
Tiny repeating intervals fail rather than hang. Deadlines that cannot advance
at the current numeric precision are rejected. Internal accumulation uses extended
precision; observable seconds remain the engine's double-precision float type.

## Native integration and limits

`runtime/src/events.cpp` owns scheduling and a Flecs 4.1.6 world. Each recipient
has an actual Flecs entity observer. Expirations emit Flecs custom events with a
typed timer payload. Interpreter and generated C++ register handlers against the
same implementation; no Python timer participates in exported gameplay.

Callbacks receive the current context at dispatch time, so moving a loaded scene
into the graphical runtime cannot retain a dangling context pointer. Exceptions
are caught at the Flecs C callback boundary and rethrown afterward through the
existing node-error protocol. Flecs is statically linked, and native freshness
fingerprints include its C/header sources.

User-defined typed events and Send/Broadcast/Subscribe/Unsubscribe are now
implemented; see [events.md](events.md) for their queue phases and cancellation.
Scaled timers follow the game clock; scale zero freezes even their zero-duration
callbacks until a later frame resumes time. Unscaled timers continue while scale
is zero, including zero-duration one-shots. A timer that requests a new Time Scale
still changes simulation on the next frame. Get Delta Time in every timer callback
remains the scaled frame delta; query Get Unscaled Delta Time when needed.
See [game clocks](time.md). The unscaled timer clock follows the capped host step,
not uncapped wall time: an SDL stall counts at most 0.1 seconds toward timers.
Editor Pause and inactive owners suspend both modes.

Whole-game Save/Load preserves both timer clocks, per-timer mode, remaining time,
creation order, manual pause and owner suspension. Internal event checkpoint
version 2 stores the second clock and mode. Its version-1 reader treats existing
timers as scaled and initializes the new clock from the old clock; whole-game
restoration still requires the matching program/runtime identity. Latent Delay
and dedicated Countdown nodes remain later work.
The internal native event checkpoint now preserves timer precision, ordering,
pause and suspension; see [persistence](persistence.md#native-timerevent-checkpoint-groundwork).
Scene transforms and hierarchy now reside in Flecs components; see
[entities](entities.md). Destroying an entity cancels its timers and prevents its
remaining listeners from running. Handler graphs run after the Flecs observer
returns so structural entity changes are immediately usable.

## Example and verification

Open `examples/timers_demo/project.json`. Two robots share the Blockbench mesh.
Their `turn` timers rotate by +15 degrees every 0.25 seconds and -30 degrees every
0.5 seconds. After 120 frames at 60 Hz, Y rotations are +120 and -120 degrees:
eight and four callbacks respectively.

```powershell
.\tools\build.ps1 -Project examples/timers_demo/project.json
.\.venv\Scripts\python.exe -m editor.main examples/timers_demo/project.json
.\.venv\Scripts\python.exe -m pytest tests/test_timers.py -q
.\.venv\Scripts\python.exe tools/verify_timers_workflow.py
```

Native tests cover owner/filter/payload scope, catch-up/listener ordering,
pause/resume, cancellation/replacement, zero-second restarts, one-shot lifetime,
functions, errors and instruction limits. The desktop workflow checks actual
Inspector/library gestures, Undo/Redo, pause/reset, native build, save/reopen and
GPU/state equivalence. See `docs/validation-report.md` and the recorded
`artifacts/validation/timers-*` evidence for results and limits.

`examples/unscaled_timer_demo/project.json` compares two Blockbench robots.
The left turns on a scaled timer, the right on an unscaled timer. 0 freezes;
1/2/3 select normal/quarter/double speed. R freezes and starts an unscaled
two-second timer that resumes the game. P/U pause/resume the right timer, S/L
save/load both clock domains. The project is authored by
`tools/create_unscaled_timer_demo.py`.

```powershell
.\tools\build.ps1 -Project examples/unscaled_timer_demo/project.json
.\.venv\Scripts\python.exe -m pytest tests/test_unscaled_timers.py tests/test_timers.py tests/test_game_time.py -q
.\.venv\Scripts\python.exe tools/verify_unscaled_timer_workflow.py
.\.venv\Scripts\python.exe tools/verify_unscaled_timer_editor.py
```
