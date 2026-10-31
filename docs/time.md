# Game clocks and time scale

Category 05 exposes Set/Get Time Scale (5030/5031), Get Unscaled Delta Time
(5032), Get Real Time (5033) and Get Fixed Delta Time (5034), alongside the
existing Get Delta Time, Get Game Time and Get Frame Count.

Set Time Scale accepts a finite nonnegative value. Zero freezes simulation;
0.25 runs at quarter speed, 1 is normal, and 2 doubles speed. The host samples
the scale once at frame start. A change in Update, a timer or a physics callback
takes effect on the next frame; current-frame delta and subsystem order stay
consistent. The query returns the requested scale immediately.

Update, Late Update and input/UI event dispatch still run at zero scale. Multiply movement
by Get Delta Time to respect slow motion; scripts which change state directly
can still do so while frozen. Scaled timers, including zero-duration callbacks,
and fixed physics updates do not advance while scale is zero. Start Timer's
Unscaled option instead counts the unscaled host step and can resume a frozen
game from its callback; see [timers](timers.md). Animation clocks and
RmlUi animation time follow game time. Audio uses the unscaled frame step and
keeps playing at its normal pitch. Use Pause Sound to pause it explicitly.

Physics keeps its 1/60-second integration step. Slowing time produces fewer
fixed updates, speeding time produces more; accumulated partial steps survive
freeze/resume and Save/Load. Get Delta Time inside Fixed Update returns 1/60,
while Get Unscaled Delta Time still describes the enclosing host frame.

Get Real Time accumulates elapsed host time independently of scale. It excludes
Editor Pause and is restored with Save/Load; it is not an OS timestamp. The live
SDL host caps the unscaled simulation step at 0.1 seconds after a stall, but the
real clock retains the full elapsed interval. Get Unscaled Delta Time reports
that capped step. Headless/replay hosts use their specified deterministic step.

Get Game Time is elapsed simulation time, sampled at frame start in gameplay
callbacks. Get Frame Count advances even at scale zero. Editor Pause stops the
host simulation loop; Play resumes it, and Stop rebuilds the initial world with
scale 1 and zero elapsed clocks. A startup scale node can override that default.
Pause/Resume World adds a separate saved pause flag without changing Time Scale;
see [world pause](world-pause.md). It follows the same captured-frame timing rules.

Whole-game checkpoints store scale, both elapsed clocks and the last scaled and
unscaled deltas. Validation stages the complete clock record with other systems
before replacing live state. A bad record preserves the running game and slot
bytes. Old saves remain usable as progress-variable containers; whole-game
restoration requires the matching runtime identity.

The scaled step is bounded to one second per host frame, matching the existing
physics catch-up budget. Larger products or nonfinite values fail before
gameplay; lower the scale or frame delta. No reverse-time simulation is implied
by this node; use animation playback speed for reversing a clip.

Open `examples/time_demo/project.json`: left robot animates, middle robot turns
on a repeating timer and right robot moves through physics. Keys 0/1/2/3 select
freeze/quarter/normal/double speed, S saves and L loads. Keyboard input continues
while frozen. The Python authoring script is `tools/create_time_demo.py`.

Verification commands:

```powershell
.\tools\build.ps1 -Project examples/time_demo/project.json
.\.venv\Scripts\python.exe -m pytest tests/test_game_time.py -q
.\.venv\Scripts\python.exe tools/verify_time_workflow.py
```

See [validation-report.md](validation-report.md) for recorded results and current
platform limitations. Unscaled timers and serializable latent Delay are implemented;
dedicated Countdown nodes remain future work.
