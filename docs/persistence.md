# Gameplay persistence

Category 23 provides versioned per-game slots, typed variables, JSON records and
bounded whole-game checkpoints. The native Preview interpreter and generated
games call the same C++ implementation. Checkpoint operations and four result
events brought the registry to **374 builtin definitions** at that milestone
(411 after physics and contact-event integration). The supported save boundary and limits
below are part of the contract; category 23 and the full engine remain incomplete.

## Save and load the running game

Open **Save Storage** at startup, then execute **Save Game** or **Load Game** with
a slot label. Their **Accepted** output means the request was queued. It does
not mean I/O succeeded. **Game Save Pending** stays true until the host processes
the request after graph execution, event/timer callbacks, audio, clock advancement
and UI layout. Startup requests run after On Game Start and its queued callbacks.
At most one game request is accepted per boundary; a second request returns false
without replacing the first. A graph error cancels its pending request.

Connect **On Save Completed / On Save Failed / On Load Completed / On Load
Failed** to handle the result at that boundary. Every handler receives the exact
**Slot** label; failed handlers also receive **Error**. These are global handlers,
with outputs scoped to their own execution path. They use the existing bounded
Flecs event queue and share the frame's instruction budget. Multiple handlers run
in stable node-ID order. Only accepted, processed game requests emit a result;
rejected requests (`Accepted=false`), canceled requests and progress-data calls
do not. Use the rejected action's Out path to read **Get Save Error**.

Normal application shutdown also processes pending saves and their result
callbacks after On Application Quit, within the shutdown instruction budget and
a 64-request bound. New Load Game requests during cleanup reject; a prior Load
cannot erase host quit intent. Quit flags are not part of game checkpoints, so
an exit save can be loaded in a fresh process. For save-before-close behavior
that stays open on failure, request Quit Application from On Save Completed.
See [application-quit.md](application-quit.md).

A save captures the game before its own completion handlers. A successful load
restores the world and its handler bindings before emitting its result; it does
not replay the earlier save completion. A handler may queue another save/load,
which waits for the next boundary. Handler errors are ordinary graph errors and
do not undo a completed disk write or load. Handler changes to the restored game
are intentional changes after commit; they are not part of failed-load rollback.

Polling **Game Save Pending** and **Save Operation Succeeded / Get Save Error**
on the next update remains supported. Another storage operation replaces that
status, while a failure event's Error payload retains the original error. A status
read in the requesting execution chain does not indicate completion. Changing
the open storage while a request is pending fails it instead of redirecting it.

Load stages the saved scene, entity IDs, hierarchy/components/prefabs, variables,
game camera, input, timers/events, sound, UI, optional native physics and clock independently. It verifies
resources and exact recapture before replacing the live context. Failed reads,
compatibility checks or preparation preserve the running game and existing file;
host error/status changes remain visible. Load does not execute On Game Start
again. Diagnostics, storage location, instruction budget, audio output/capture
and the editor's orbit camera remain host state. A game-camera entity is saved.

Compatibility is deliberately strict: SHA-256 of canonical program IR, runtime
source/build definitions and the full project assets directory, plus scene/prefab
models elsewhere in the project and their external glTF/GLB buffers/images, plus platform,
pointer size, SDL/mixer versions and the packaged UI font. Resource paths are
relative, so relocation and Preview/generated execution remain compatible.
Changing even an unused asset invalidates old checkpoints; migration is not
implemented. The combined resource set is limited to 4096 regular files and 1 GiB
total, with no links. Model documents outside `assets/` are limited to 64 MiB;
dependency URIs must resolve to local files beneath the model's directory.
Percent-encoded names and Unicode paths are supported. Hashing occurs during
setup and each request. Saved mesh,
sprite, audio and UI libraries must match the already prepared program catalog;
GPU loads reuse the preloaded resources. Builds replace their generated assets
copy so deleted source files cannot leave a conflicting stale package identity.
Build also stages scene and unspawned prefab models outside `assets/`, preserving
their project-relative paths and declared buffer/image dependencies. The generated
`.model-assets.json` in `build/` records ownership and content hashes so rebuilds
can remove stale files without overwriting unrelated or manually modified output.
Sources and collisions are checked and copied to temporary storage before changing
the previous output. Replacement of the entire build is not a single filesystem
transaction; after interruption, rebuild or use a fresh build directory.

These operations are synchronous at the boundary. Audio reconstruction replays
its bounded journal and can stall for long histories; a practical latency bound
and asynchronous loading remain open. UI requires released pointer buttons and
closed select menus. Caret/gesture/IME/animation limitations in the UI section
still apply. Display dimensions/DPI are restored for staging, then follow the
current host viewport on subsequent layout; they are not a permanent window size.

Open `examples/game_save_demo/project.json` for a rotating Blockbench robot with
a game camera, timer, sound and HUD. Save/Load buttons or S/L create/restore a
checkpoint; startup loads an existing slot. Its default Game ID is
`node-engine-game-save-demo`. The older `persistence_demo` remains a separate
example of explicit progress variables.

`examples/game_save_events_demo/project.json` uses the four result handlers to
update the HUD and log. S/L or the buttons save/load; F requests an invalid save
slot and M requests a missing load slot to demonstrate failure handling. Its
separate Game ID is `node-engine-game-save-events-demo`.

## Author a save flow

1. Add **Open Save Storage** after **On Game Start**. Set **Game ID** to a stable,
   unique ID for your game, such as `studio-robot-adventure`. It accepts lowercase
   ASCII letters, digits, `_` and `-`, starts with a letter/digit, and has at most
   64 characters. The empty default deliberately requires a choice. Keep this ID
   when renaming, updating or moving a game. Use a different ID for independent
   projects, even when they have the same display name.
2. Connect its **Value** boolean to **Branch**, and execute save nodes only on
   success. **Get Save Error** provides a message for the failure branch.
3. Define scene variables in **Scene Variables…**. **Save Variables** writes the
   named variables to one slot in one transaction. **Load Variables** restores
   them only when every requested name exists and has exactly the declared type.
4. Apply loaded values to the scene/UI with ordinary nodes. For example, read
   rotation into a Vector3 variable before saving; pass that variable to
   **Set Rotation** after loading.
5. Use **Save Slot Exists** before an optional startup load. A missing slot is a
   successful query with Value=false. A damaged slot still exists; loading it
   reports failure, preserving the current game variables and existing file.

Progress-data file operations have an execution input/output. Their **Value** result is
available on the outgoing execution path. File reads are deliberately actions,
so wiring data ports cannot trigger repeated reads unexpectedly.

| Stable ID | Node | Value output |
|---|---|---|
| 23001 | Open Save Storage | success boolean |
| 23002 | Create Save Slot | success boolean; existing valid slot is preserved |
| 23003 | Delete Save Slot | success boolean; missing slot is an error |
| 23004 | Save Slot Exists | existence boolean |
| 23005 | List Save Slots | sorted string array, including damaged slots |
| 23006–23007 | Save Variable / Load Variable | success boolean |
| 23008–23009 | Save Variables / Load Variables | success boolean for the whole batch |
| 23010–23011 | Save JSON / Load JSON | success boolean / canonical JSON string |
| 23012 | Get Save Version | positive format version, or -1 on error |
| 23013 | Validate Save Data | success boolean |
| 23014–23015 | Save Operation Succeeded / Get Save Error | last operation's status/message; pure queries |
| 23016–23017 | Save Game / Load Game | **Accepted** boolean; deferred boundary request |
| 23018 | Game Save Pending | pending boolean; pure query |
| 23101 | On Save Completed | Slot; exec handler after successful write |
| 23102 | On Save Failed | Slot, Error; exec handler after failed processing |
| 23103 | On Load Completed | Slot; exec handler in the restored game |
| 23104 | On Load Failed | Slot, Error; exec handler in the existing game |

After a list, existence, JSON or version query, use **Save Operation Succeeded**
to distinguish an empty/missing result from an I/O or validation failure. Status
queries leave the last result intact. The next file operation replaces it.

## Storage and data guarantees

The default directory is SDL's user preference location under `NodeEngine` and
the chosen Game ID. On Windows this is normally
`%APPDATA%/NodeEngine/<game-id>/`. Saves remain outside the installation/project
directory and survive moving the exported game. Preview and exported games with
the same Game ID intentionally share progress. For an isolated run, each native
executable accepts `--save-root <directory>` and uses its `<game-id>` subfolder.

Slot labels are 1–64 UTF-8 bytes without control characters. Labels are encoded
into filenames, so slashes, `..`, Unicode and Windows device names cannot choose
an external path. File operations reject links and directories in place of a
slot file. The user-selected save root is an application boundary, not a defense
against another privileged process changing filesystem topology during a call.

Each slot contains `format`, `version`, `game_id`, `slot`, `variables` and `json`.
Format version 1 stores an explicit type and value for all 40 runtime value types:
ten scalars, their homogeneous arrays, string-keyed maps and insertion-ordered
unique sets. Integers keep their
signed 64-bit precision; strings and keys preserve Unicode. Entity references
store IDs; loading a variable does not recreate an entity or resolve a stale ID.
Save Game upgrades an existing valid version-1 slot to version 2, retaining its
independent variables/JSON and adding `checkpoint`. Progress operations preserve
that checkpoint. Load Game rejects a progress-only slot. Validate Save Data
checks the envelope and progress value types; only Load Game performs full
program/resource and subsystem restoration validation. Explicit Save Game may
replace an old incompatible checkpoint in an otherwise valid slot.

Writes validate the complete result before touching the existing save, flush a
new temporary file and replace the destination atomically. Temporary files are
cleaned after handled failures; files left by a process kill are ignored. A
storage-directory lock excludes competing engine processes from a read/modify/
replace transaction. A busy lock reports a recoverable error rather than
waiting inside a graph. Existing damaged or future-version data is never silently
overwritten by a variable/JSON update or Create Save Slot. Delete Save Slot can
explicitly remove a damaged regular file.

Limits: 1024 slots per game, 16 MiB per version-1 slot, 80 MiB per version-2 slot
(with a 64 MiB checkpoint), 64 JSON nesting levels including
the envelope, and the existing runtime value limits (1 MiB per string, 65536
items per collection). JSON records are at most 1 MiB each. Duplicate JSON keys,
non-finite numbers, malformed envelopes and wrong game/slot identities fail.
Get Save Version can inspect a future positive version; loading it requires a
migration that is not yet implemented.

## Playable example

Open `examples/persistence_demo/project.json` in the editor. Click **Add point**
to turn the Blockbench robot, enter a player name, then **Save**. Change the score
and press **Load**, or Stop/Play, or close/reopen the game. The saved score, name
and rotation return. The Save button also reads unsubmitted text from the input.
The default Game ID is `node-engine-robot-save-demo`.

## Verification on Windows

`tests/test_persistence.py` passes 20 native integration cases. Separate processes
roundtrip all 40 types, Unicode and integer boundaries. Failed batch writes keep
the prior file; failed batch loads keep all current variables. Truncated,
oversized, duplicate-key, deeply nested, wrong-type, wrong-identity and
future-version files fail without being overwritten. Additional checks cover
slot/JSON lifecycle, namespace separation, readonly replacement failure and
cleanup, competing process locks, and directories occupying slot filenames.
The persistence, UI runtime and build-stamp selection passes 29 tests in total.

`tools/verify_persistence_workflow.py --desktop` passes 47 checks. It edits the
Game ID in the actual Qt Inspector, exercises Undo/Redo/save/reopen, then accepts
real mouse clicks on Add and Save in the embedded game. Stop/Play restores the
saved robot. Four standalone executables subsequently save, restart from a
Vietnamese-named relocated package, and manually Load after changing progress.
All paths have identical snapshots and saved bytes. Preview/compiled GPU captures
match byte-for-byte at each of the three phases. Unicode player names restore,
and both loading paths leave the save file unchanged. The package runs with only
Windows directories on PATH. See `artifacts/validation/persistence-workflow-checks.json`
and `persistence-restored.png`; the restored robot/HUD capture was visually inspected.

~~~powershell
./tools/build.ps1 -Project examples/persistence_demo/project.json
.venv/Scripts/python.exe -m pytest tests/test_persistence.py tests/test_ui_runtime.py tests/test_runtime_build.py -q
.venv/Scripts/python.exe tools/verify_persistence_workflow.py --desktop
~~~

The desktop variant waits for a tester to click Add once and Save; omit
`--desktop` for the automatic authoring/package checks. These checks do not prove
power-loss durability on every filesystem or Linux/macOS behavior.

## Native timer/event checkpoint groundwork

`EventCheckpoint` and `RestoreEventCheckpoint` now serialize and restore the
native timer/event subsystem used by the public whole-game Save/Load nodes.
The versioned record preserves timer deadlines and both logical clocks as decimal
strings at native `long double` precision, each timer's scaled/unscaled mode,
creation order, manual pause and
entity suspension. Event state includes subscriptions, cancellation/activity
epochs and the complete FIFO queue, including already-invalidated deliveries.
All 40 payload types and originating node IDs survive restoration.

Callbacks are resolved from the current program's matching event signatures and
listener identities. The file carries no executable code or native entity handles.
The caller must provide the candidate scene first; saved activity must agree with
that scene. Bindings whose owner was destroyed remain dormant and reconnect when
prefab Reset recreates the same entity ID. A queued sender may have been destroyed
after sending, so its reference is retained without requiring it to remain alive.

Both APIs reject calls during timer/event dispatch. Restoration validates into
a separate event system and replaces the target only after every record passes.
Failed staging removes its Flecs observers/event identities. Repeated successful
replacements likewise release the old system. Existing timer count, payload and
queue-memory limits also apply to restored data.

Run `.venv/Scripts/python.exe tools/verify_event_checkpoint.py` after configuring
the native build. It builds the optional `node_event_probe` target and records
the original 45-check milestone in `artifacts/validation/event-checkpoint-checks.json`: exact
roundtrips, 160-frame continuation, all typed payloads, invalid data rollback,
native lifetime accounting, callback-boundary rejection, budget attribution and
prefab recreation. A writer process exits before a fresh reader resolves its own
callbacks and reproduces the reference trace. Reading leaves the file unchanged.
These are internal runtime checks, not editor/GPU proof of full-game restoration.
The accompanying timer/event/activity/persistence/build-stamp regression run
passes 80 tests; see `artifacts/validation/event-checkpoint-regression.log`.

The unscaled-timer extension uses internal event record version 2. Its reader also
accepts version 1 as scaled timers, initializing the additional clock from the
old clock. This internal conversion does not relax whole-game runtime identity.
Current evidence is in `unscaled-timer-probe.json` (50 checks) and
`unscaled-timer-event-write.json` / `unscaled-timer-event-read.json` (3 checks):
two-clock precision, manual/owner suspension, deleted owners, mixed continuation,
invalid-mode/clock rollback and a separate-process 160-frame trace. The matching
editor, four-host and GPU evidence is recorded in [validation-report.md](validation-report.md).

## Native scene, input and audio checkpoints

`SceneIdentityCheckpoint` preserves reserved entity IDs and the mesh preload
library, including IDs and meshes whose last entity has been destroyed. Pass it
alongside `Snapshot(ctx)["scene"]` to `LoadScene` on a fresh candidate context.
`CreateSceneWorld` validates the record against live entities and prefab mappings
before returning its new world. The existing scene snapshot supplies transforms,
hierarchy, components, prefab templates/ownership/retired mappings, camera and
typed variables. The identity record stays separate from authored scene JSON.

`InputCheckpoint` / `RestoreInputCheckpoint` preserve bindings, held keyboard and
mouse buttons, key edges and action edges. A press and release in the same frame
are both retained. Restoration validates into temporary state and swaps only
after success; it does not replay events or synthesize an extra key press.
Input event queues retain individual transitions and filtered handler identities.
The interactive SDL host clears held buttons/edges and queued input callbacks
after a successful Load, without synthetic releases. A saved held key therefore
cannot remain stuck in a later physical session; press it again to act. Headless
and deterministic replay preserve saved input for exact continuation. This host
policy does not change the checkpoint record or its staged validation.

`AudioCheckpoint` / `RestoreAudioCheckpoint` preserve asset identity, voice
creation order, play/pause/stop state, per-voice and master gain, sample counters
and the fractional mixer clock. Version 2 records ordered playback controls and
exact mixing request sizes, compressing adjacent identical requests. Integer
seeking and replaying elapsed totals alone cannot reconstruct buffered resampling
state; the combined-game test caught that flaw in version 1. Restoration replays
the journal in an independent mixer and compares the entire resulting checkpoint
before replacement. Failed restoration leaves the original audio running. No
replayed PCM reaches the audio device or capture file. Version 1 is rejected.

Run `.venv/Scripts/python.exe tools/verify_state_checkpoint.py`. The optional
native `node_state_probe` verifies **81 checks**, with a writer exiting before a
fresh reader restores six checkpoints taken at different playback/game states.
Their **389 subsequent frames** match uninterrupted scene/input/event/audio
state. Every corresponding PCM capture is byte-identical, including
22.05/44.1/48/96 kHz WAV and MP3, loops, pause/resume, natural EOF, explicit Stop,
voice replacement and gain changes. Deleted prefab members return with their
stable IDs; a deleted mesh carrier does not prevent spawning that mesh later.
Fifty-five malformed-record cases cover rollback of input, scene identity and
audio, including replay limits and invalid history. A recording-exhaustion check
confirms playback/controls continue while checkpoints fail explicitly.
Reports, source/binary hashes and captures are under
`artifacts/validation/state-checkpoint*`. The existing event probe also still
passes 45 checks after these runtime changes.

The targeted input/audio/scene/build regression run passes **41 tests** in
152.33 seconds, with zero skipped/failing cases. See
`artifacts/validation/state-checkpoint-regression.xml` and `.log`.

These are internal Windows APIs, not exposed Save/Load Game nodes. Audio history
has limits of 65,536 entries, 16 MiB, one hour of mixed output and 1,080,000 mixing
calls. Recording exhaustion leaves playback running but rejects checkpoints
until scene reset. Replay cost still depends on history and active voices; these
ceilings do not establish interactive load latency. Ogg/FLAC continuation,
program/file compatibility and host/editor/export integration remain open.

## Native UI checkpoints

`UiCheckpoint` / `RestoreUiCheckpoint` preserve template/instance identity,
document order and visibility, text/style edits, form values, checked/enabled
state, progress, scrolling, focus history, selected character ranges, hover and
the queued UI event payloads/generations. Listener callbacks are resolved from
the current program. Stale queued events stay stale after a document was hidden;
destroy/recreate keeps its normal generation semantics after restoring.

Restoration constructs a separate session and replaces the live UI only after
validation and exact recapture of the serialized fields. A malformed checkpoint
leaves the original session, pending events and subsequent input working. Both
APIs reject calls from inside UI event dispatch. Source templates/bindings must
match, and styles retain shorthand/longhand call order. Journals, element counts,
input text and event queues have bounded sizes; the session record is limited
to 32 MiB. Exhausted generation counters fail before changing live documents.

The pinned RmlUi focus-history adapter is applied and checked by CMake; see
[rmlui-checkpoint-patch.md](rmlui-checkpoint-patch.md). Public `Focus()` calls
alone cannot recover the history left by hiding the last focused document.
Text controls also invalidate layout when their value changes, so multiline
caret navigation uses current text geometry in headless and GPU runs.

`tools/verify_ui_checkpoint.py` passes **105 checks**. A writer exits after
saving three cuts; a fresh reader reproduces **21 continuation frames per mode**
in headless and GPU execution. Six reference/restored BMP pairs match byte for
byte: each cut immediately after restoring, and after subsequent input/events.
The cut-6 restored capture was visually inspected. Cases include Unicode range
replacement, focus fallback when hiding windows, text scrolling, stale events,
malformed-record rollback, no-UI scenes, reentrant calls and counter exhaustion.
Evidence is in `artifacts/validation/ui-checkpoint-checks.json` and
`ui-checkpoint/`. The existing packaged dependency probe also passes **103
checks** in headless, SDR and SDR_LINEAR modes. UI authoring/runtime/build
regressions pass **20 tests**, including clean-source patch application,
idempotence and rejection of an unknown RmlUi header.

The internal UI API now backs the public game nodes. Saves require released pointer buttons
and closed select menus. Selection endpoints are normalized; selection direction,
vertical caret navigation's preferred column, caret blink phase, double-click
history, active gestures, IME composition and CSS animation/transition progress
are not serialized. The comparison proves the fields and interactions exercised
above, not arbitrary UI continuation. Full game persistence must define and
implement those transient-state semantics. Staging now defers cursor and text
keyboard changes until commit; the combined transaction below verifies the
window handoff separately.

## Combined game checkpoint transaction

`GameCheckpoint`, `StageGameCheckpoint` and `CommitGameCheckpoint` combine scene,
reserved identities, input, timers/events, audio, UI, optional native physics,
animation, the deterministic random stream and
the frame/time/delta/self clock in a version-2 record limited to 64 MiB. The caller supplies the current
program/resource identity; it must match the saved identity exactly. The current
host computes the production IR/resource fingerprint described above.
The `random` record stores `splitmix64-v1`, the signed original seed and exact
current stream state. It restores before commit, so future random draws match an
uninterrupted run. Older envelope variants remain readable by progress-data nodes;
full game restoration still requires the current exact runtime/schema identity.
The flow field saves Do Once/Do N counters, Gate/Flip Flop flags, Multi Gate's
route count/visited mask/cursor, and their node/owner bindings. The random field
restores the shared generator used by random route selection. Restore checks
binding identity, owner existence, duplicate
entries and valid values before committing. Clone does not copy owned gate state;
destroyed entities leave no saved gate entries. See [flow-control.md](flow-control.md).
Older envelopes without flow remain readable through progress variables/JSON,
but whole-game restoration requires the matching runtime and complete schema.
Executable callbacks always come from the current
program. Interpreter and generated entry points track graph execution depth;
checkpoint/restore requires an execution boundary outside callbacks/functions.

The physics field is null when no native physics world or fixed-step state exists.
Scene entities may also contain `rigid_body` initial settings, inherited through
prefabs. Checkpoint restoration loads these settings without spawning initial
bodies, then restores the separate native physics state. This preserves runtime
body removal, current mass/velocity and contacts without replaying creation.
Otherwise it wraps body configuration/IDs, allocation generations, forces,
velocities, sleep/contact state and current events, together with scene bindings,
observed transforms, the fixed-step remainder and tick count; see [physics.md](physics.md).
Its native binary format is pinned to Jolt 5.6.0. It is restored in a separate
world before commit. The current graph's fixed-update callback survives the
transaction. The native checkpoint probe configures its world through C++; the
separate physics example creates bodies with graph nodes and advances them in
both hosts, including exact continuation from a fractional-step checkpoint.
Collision/trigger listeners share the event checkpoint binding identity. Their
automatic subscription state is validated against receiver existence/activity;
tampered disabled listeners reject the staged load. The contact demo also saves
from Collision Enter and resumes in a fresh process with matching state/GPU
output and no repeated Enter delivery.

The outer save-slot format remains version 2. Progress-data operations accept
older version-1 game checkpoint envelopes and preserve them. Load Game rejects
those incompatible checkpoints; a fresh Save Game can replace one while keeping
the slot's independent variables and JSON. This is replacement, not migration.

Stage constructs an independent context without output devices or active window
effects and requires exact recapture before returning it. Commit transfers the
existing audio stream/capture, clears pre-load queued PCM, suspends the old UI's
window effects, replaces the context and activates the new UI. Logs, storage
identity/status and instruction budget remain host state. Both host loops now
process queued graph requests at the boundary, validating the preloaded GPU
catalog before committing a graphical load.

`tools/verify_game_checkpoint.py` passes **67 checks**. Separate writer/reader
processes restore six cuts and reproduce **132 continuation frames**, including
variable and zero timesteps, destroyed entities, held/edge input, timer/event/UI
activity, voice replacement, looping, pause/resume and gain/mute changes. Physics
adds contact response, pending forces, disabled/reenabled bodies, destruction and
replacement with stable ID allocation. Seven
reference/restored WAV pairs match byte for byte, including capture append across
commit. Eleven malformed records, including physics corruption and a failure after audio staging, preserve
the live subsystem pointers/state, output pause state and text input. Additional
checks cover abandoned candidates, repeated commits, empty scenes, both text
keyboard activation/deactivation directions, deferred requests/rollback, and
legacy-checkpoint preservation/replacement without losing progress data. The full probe passes with the
**dummy** driver and again with actual **WASAPI** output on this machine
(`--audio-driver wasapi`). The hidden native window uses actual SDL text-input
state. This does not certify acoustic quality or the full graphical-host resource
transaction.

Evidence: `artifacts/validation/game-checkpoint-checks.json` and
`game-checkpoint-device-checks.json`, saved records/traces/captures in their
corresponding directories, and source/binary hashes in both reports. The native
runtime was rebuilt and its stamp matches the current checkpoint reports. The
separate UI probe results (105 checkpoint and 103 dependency checks) are from the
earlier UI milestone, not rerun for this physics checkpoint change.

The earlier audio/UI/function/progress-persistence/build regression run passed
**82 tests** in **323.32 seconds**, with no failures or skips. It exercises real
interpreted and generated games after the execution-boundary and platform changes;
see `game-checkpoint-regression.log` / `.xml`. Two existing NodeGraphQt deprecation
warnings remain.

The public node integration is verified separately by `tools/verify_game_save.py`:
**68 checks** compare four native paths across fresh processes and a relocated
Unicode package path, including manual load from a UI callback. State and
continuation PCM match; game-camera GPU captures match byte for byte. Slot bytes
match between interpreter/generated hosts at the same DPI. Across headless and
windowed hosts, only saved UI density differs (1.0 versus this monitor's 1.25).
The new unfocused-UI regression raises the combined probe to **48 checks**; the
existing **105 UI checkpoint checks** pass after that fix. Earlier reports and
counts in this document record their respective milestones, not new coverage.

Result events are verified by `tools/verify_game_save_events.py`: **82 checks**
exercise four native paths from a standalone Unicode package directory, startup
and repeated loads, UI requests, errors, retry and malformed builtin subscription
rollback. All eight scenarios have identical state across hosts and identical
interpreter/generated GPU captures. The original **68-check** save workflow and
**45-check** event-checkpoint probe (160 continuation frames) pass with these
changes. See validation-report.md for the Python/editor test results.

Public entity snapshots, autosave, preferences, binary
records, schema migration, practical load latency and remaining transient state
semantics remain open. Category 23 and the full engine are not complete.

Programs containing latent flow also checkpoint their suspended execution stacks.
The scheduler preserves event payloads, function parameters, For Each snapshots,
scoped results and remaining delays. Current program bindings supply native
callbacks after Load; saves contain state only. A staged load validates block
positions, callers, types, loop state, owners, program identity and bounded task
counts before committing. Legacy graphs without latent operations retain their
prior checkpoint shape. See [flow-control.md](flow-control.md).


## Pointer checkpoint state

Input checkpoint version 2 adds window-content position and the frame's accumulated
motion and two-axis wheel impulses, preserving fractional values. All three
vectors restore into the staged context before commit; malformed shapes, types
and non-finite values reject without changing the live game. Version-1 standalone
input records upgrade with neutral pointer values, while full-game saves retain
the existing exact program/resource compatibility requirement.

Interactive SDL Load clears transient impulses and samples the physical pointer
without manufacturing a delta. Replay restores the recorded state exactly. The
next frame resets delta/wheel, so a saved impulse is never applied twice.
`tools/verify_pointer_workflow.py` verifies fresh-process continuation, staged
rollback and equal state/GPU output in all four native hosts.

Input checkpoint version 3 additionally saves cursor visibility/lock requests
and their originating node ID. Strict types and complete field validation run
before commit. Malformed cursor records leave the live game and saved bytes
unchanged. Standalone version-1/2 input records receive visible/unlocked defaults;
the full-game exact-program/resource rule is unchanged. A saved cursor request
does not grant OS focus: the SDL host applies it only when running and focused,
and editor Esc retains its explicit release latch until the viewport is reclaimed.
Headless and replay hosts preserve logical intent without physical capture.
`tools/verify_cursor_workflow.py` checks all four hosts, full-state continuation
and GPU parity; actual editor Save/Load is checked separately. See [input](input.md).

Input checkpoint version 4 adds controller connection IDs, normalized axes and
held gamepad buttons. Queued input deliveries retain their original Controller,
Button and Down payloads even after disconnect; latent callbacks retain those
scoped values too. Standalone input versions 1-3 upgrade with empty device state.
Physical Load replaces saved input devices with the live SDL inventory, samples
current analog values and suppresses already-held buttons until release/repress.
Saved scene variables that store a previous connection ID remain game data; that
ID may no longer identify a current device. Replay keeps exact saved input for
deterministic continuation. See [gamepad.md](gamepad.md).

Input checkpoint version 4 also preserves version-2 mixed keyboard/mouse/gamepad
bindings. Mapped Held/Pressed/Released state and queued action callbacks restore
from the saved raw input and edge sets, without emitting the transitions again.
Whole-game restoration rejects binding definitions that disagree with the saved
scene, including otherwise-valid changes to dead zone or inversion. The mixed
input demo verifies exact fresh-process state/GPU continuation and rollback for
malformed and incompatible binding data. See [input-bindings.md](input-bindings.md).

Input checkpoint version 5 adds enabled context names and suppressed actions,
with version-3 binding definitions. Authored initial flags stay in the scene;
runtime flags and held-action rearming restore independently. Staging rejects
unknown/duplicate names, impossible suppression, unavailable queued presses and
definitions inconsistent with the saved scene. Physical Load/Pause retain context
flags while clearing transient input and reconciling live controls. Stop/fresh
Play restores authored defaults. Standalone input versions 1-4 remain readable;
full-game program/resource compatibility is unchanged. The context demo checks
exact continuation from both a disabled context and an enabled context waiting
for button release in four hosts. See [input-contexts.md](input-contexts.md).

World Pause is saved as a boolean `clock.paused`, independently of Time Scale and
the editor's debug state. Pause/Resume listeners and queued transitions use the
normal event checkpoint. Load restores the flag without synthesizing callbacks;
malformed flags reject before replacing the world. Compatible version-2 clocks
without this field default to false. See [world pause](world-pause.md).
