# Application quit and exit saves

`Quit Application` (26001) requests a normal shutdown of the native game.
`On Application Quit` (1010) runs cleanup before that process closes. These two
nodes bring the registry to **521 builtins**. Preview and generated games call
the same native shutdown code.

Open `examples/application_quit_demo/project.json`, or run
`artifacts/demos/application-quit-playground/Play.cmd`. Move the robot with A/D,
arrows, D-pad or left stick; Space/left mouse/South turns it. M toggles gameplay
input. Q saves through the quit callback and closes the game. Reopen Play.cmd
and press L to resume the exit checkpoint. S saves manually. `Replay.cmd` runs
without hardware and quits after frame 13 rather than its 120-frame upper limit.

## Execution order

Quit Application has In/Out execution ports. It sets an idempotent host request;
it does not terminate the calling graph. Statements after Out, action-function
returns, remaining event callbacks and fixed steps, Late Update and pending
Save/Load finish at the current frame boundary. A request during startup finishes
startup and its queued work, then shuts down before the first update frame.

At shutdown, On Application Quit entries run once, in stable node-ID order.
Custom events and immediate UI callbacks drain. Pending Save Game requests and
their result callbacks finish before final state/optional GPU capture and audio
capture finalization. No new simulation frames, timer ticks or latent resumptions
are run to wait for cleanup. A Delay, including zero seconds, suspends its branch
as usual; the host does not wait for it. Saved continuations can still resume if
the game later loads that checkpoint.

Repeated requests, including a Quit Application inside the quit callback, cannot
dispatch the callback again. The guard is set before user code, so a failed
cleanup is not retried. The callback receives a fresh normal instruction budget;
quit-time callback/save chains share it. At most 64 pending game-save requests
are processed during shutdown, preventing an On Save Completed -> Save Game
cycle from keeping the process alive indefinitely.

The same path handles a normal SDL window close, Alt+F4, editor IPC quit and
completion of a command-line frame limit. The event requires gameplay to have
started. Closing a preview that has never started, or has been reset with Stop,
does not run gameplay cleanup. Editor Pause retains the started session, so
closing a paused preview dispatches the callback without advancing frame/time.

## Editor behavior

Both nodes are available in the Library with normal graph Undo/Redo and
save/reopen. The event belongs to the Gameplay graph; action functions can call
Quit Application. It closes the native preview process, preserves the Python
editor and authored graph, and leaves Play available to start a fresh process.

Stop, live graph reload and scene edits reset the preview inside the existing
process; they are not application-quit events. Closing the editor, changing to a
different project or rebuilding while its runtime process is active uses the
existing asynchronous IPC shutdown. The editor remains responsive and permits
10 seconds for normal cleanup before its recovery timeout force-terminates a
nonresponsive process. A forced termination is logged as potentially leaving a
pending game save incomplete.

## Persistence contract

Open Save Storage before saving. Save Game's **Accepted** output reports request
acceptance; On Save Completed/Failed reports the actual result. Shutdown drains
those completion handlers, including additional bounded save requests they queue.
An exit checkpoint captures callback changes before that save's own completion
handler, just like a normal game checkpoint.

Host quit intent and the dispatch guard are not game data and are excluded from
checkpoints. A fresh process can load an exit save and continue normally.
Conversely, committing a Load requested before shutdown cannot clear an already
pending quit request or rearm a dispatched callback. New Load Game requests
during the quit callback or its completion handlers reject with Accepted=false
and a Get Save Error message. They cannot restart the game while it is closing.

For a game that must remain open if saving fails, queue Save Game first and
invoke Quit Application from On Save Completed. The quit callback is cleanup,
not a cancellation/veto point. The demo deliberately exercises saving within
On Application Quit and reports failures through the persistence APIs, HUD and
logs; a failed save does not cancel process closure.

Graph errors during cleanup retain originating node identity and cause an
unsuccessful process exit. SDL also reports a single `application_quit` message
with started/success/frame fields; success here means cleanup completed without
a graph error, not that every requested storage operation succeeded. An explicit
final `--output` file is written for successful SDL shutdown and recoverable quit
callback errors. `--capture` includes final quit/UI changes while the window is
still available. A hidden/minimized unavailable swapchain cannot guarantee a
final GPU capture.

## Verification and limits

The native tests cover startup/update/fixed/late quit, current-frame completion,
custom events, action-function return, latent non-waiting behavior, exit saves,
shutdown Load rejection, malformed IR and bounded failure reporting. A direct
native probe checks graph-boundary rejection, duplicate/failed dispatch guards,
checkpoint exclusion/preservation and existing clock behavior. Four relocated
hosts verify state/GPU parity, independent-process resume, simultaneous Load +
Quit and failed save storage. Actual editor checks use physical keyboard Q,
standalone Alt+F4, paused IPC quit and asynchronous editor close. The combined
checkpoint regression also exercises native audio/UI/physics handoff and exact
fresh-process continuation. See [validation-report.md](validation-report.md).

Force-kill, crashes, OS termination deadlines and power loss cannot guarantee
cleanup or an exit save. No asynchronous task completion or quit-veto protocol is
implemented. Scene Loaded, Game Pause/Resume events and remaining platform nodes
remain separate work. Windows is verified; other platforms still need evidence.
The full engine goal remains active.
