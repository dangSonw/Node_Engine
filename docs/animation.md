# Animation playback and skeletons

Global [Time Scale](time.md) multiplies the frame delta before per-player Speed
is applied. Scale zero freezes all clip clocks while input and UI event handlers
continue to run. Whole-game Load restores scale and exact animation state.

The native `node_animation` library reads glTF 2.0/GLB skeletons and TRS clips,
evaluates poses through ozz-animation 0.17.0, and computes skin positions with GLM.
Eighteen gameplay nodes control imported clips and a bounded two-bone IK solve
through the shared native runtime,
including a timed clip transition that blends node and skin matrices during a
crossfade. Both headless and graphical hosts advance the same per-entity clocks; SDL_GPU
renders the deformed vertices. Whole-game checkpoints preserve playback state.
Dedicated clip/skeleton Inspector controls and the Animation workspace remain open.

## Playback nodes

IDs 13001–13013 provide Get Animation Clips, Play, Stop, Pause, Resume, Set Speed,
Set Loop, Set Time, Get Time, Get Progress, Get Duration, Is Playing and Is Paused.
Each targets an entity's model. Clip names come from Get Animation Clips; duration
is measured in seconds and progress is normalized to 0–1. No selected clip gives
time/progress zero and both status flags false.

Play selects a clip and restarts it at zero, or its duration for negative speed.
Speed ranges from -100 to 100; zero holds the pose without changing playing status.
Pause retains the time; Resume continues a paused player. A non-looping clip stops
at its end and keeps the final pose; Play restarts it. Stop removes playback and
restores the bind pose. Set Time clamps to the clip interval and retains playback
status. Zero-duration clips hold their only pose without becoming active players.
Controls that need a selected clip report an error if Play has not selected one.

ID 13015, Play Animation Blended, keeps the selected clip as the transition source
and blends it into the target clip for 0–60 seconds. The source clock, target clock,
blend progress and duration are saved and restored; zero duration uses normal Play.
Preview and generated games use the same native pose interpolation.

On Animation Notify (13016) emits authored notify names while the selected clip
clock crosses their times. Scene metadata stores `features.3d.animation.notifies`
as `{clip, time, name}` entries; forward, reverse and looping playback handle
wraparound, and an exact Notify Filter may scope a listener. Entity and Notify
outputs are captured in the callback and queued through the same checkpointable
event system as completion events.

Set Animation State (13017) resolves a named state from
`features.3d.animation.states`. A state can be a clip string or an object with
`clip`, `loop` and `speed`; transitions use the same native crossfade as
Play Animation Blended.

Solve Two Bone IK (13018) computes a finite planar elbow position from root,
target, upper length and lower length. The clamped solve is available in both
interpreter and generated C++ paths. Full skeleton joint application,
retargeting, root motion and multi-chain 3D IK remain separate work.

Each host advances animation once per game update after physics/audio and before
checkpoint processing. Inactive entities freeze their clocks; invisible active
entities continue. Clone copies the selected clip, clock and settings by value.
Destroy and prefab model replacement discard obsolete players. Host Pause freezes
all simulation; Stop/reload recreates the authored scene with no selected clips.

The current checkpoint includes entity/model identity, clip, time, speed, loop,
playing and paused flags. Loading prepares independent state and checks each asset
before committing; failures leave the running game and slot intact. Runtime and
asset hashes still determine compatibility. Saves from earlier native revisions
are not automatically migrated.
Older checkpoint containers remain readable through progress-variable/JSON nodes;
this does not bypass the stricter whole-game restoration checks.

## Completion events

On Animation Finished (13014) runs when a non-looping clip naturally reaches its
end, or zero while playing backwards. It emits once per playback. Looping clips,
Stop, Pause and Set Time do not emit completion themselves. Seeking a playing
clip to its endpoint allows the next nonzero animation advance to complete it.
Zero speed, inactive entities, Time Scale zero and Editor Pause prevent normal
advancement. Visibility does not stop playback.

Set the constant Receiver to an entity ID for that entity's completions, or leave
it empty for all entities. Clip Filter is an exact, case-sensitive name, or empty
for every clip (at most 512 UTF-8 bytes, no NUL). The Entity and Clip output values
are captured when playback finishes and are available only in that handler's
execution path. Get Self is the receiver, or the empty scene reference for a
global listener. A global callback may carry an entity reference that was deleted
by an earlier callback; check Entity Exists before accessing that entity.

All players advance before the host drains the completion queue, then Late
Update runs. A handler may start the next clip, destroy entities or send custom
events safely. A new clip starts at its initial pose; its clock first advances
in the next frame. Same-frame completions follow entity-ID order, global listeners
before the entity's listeners, and node-ID order inside each receiver. Removing
or deactivating a receiver cancels its remaining deliveries. Prefab recreation
restores its bindings without reviving stale queued completions.

A zero-duration, non-looping clip completes immediately when Play selects its
only pose. Its callback is queued until the current graph finishes, including
when Time Scale is zero. A zero-duration looping clip does not emit completion.
Stop does not retract a completion already emitted; deleting/deactivating the
receiver still cancels its delivery. Loading or cloning a stopped zero-duration
player does not emit another completion.

Whole-game saves preserve completion subscriptions, clip filters and pending
payloads. A save requested from a completion handler is processed after Late
Update and includes any clip transition made by that handler. Loading prepares
playback without replaying completion. Incompatible bindings and malformed
payloads reject the entire restoration and preserve the live game.

`examples/animation_finished_demo/project.json` demonstrates Wave -> Idle on the
left robot and uninterrupted looping Walk on the right. It saves a separate
completion checkpoint after each Wave. The Python authoring source is
`tools/create_animation_finished_demo.py`; 1/B play forward/backward, P/R pause
and resume, X stops, 0/2 freeze/resume time, S/L save/load, K loads the last
completion checkpoint. `artifacts/demos/animation-finished-playground/Play.cmd`
launches the packaged native demo.

```powershell
.\tools\build.ps1 -Project examples/animation_finished_demo/project.json
.\.venv\Scripts\python.exe -m pytest tests/test_animation_finished.py tests/test_core.py -q
.\.venv\Scripts\python.exe tools/verify_animation_finished_workflow.py
.\.venv\Scripts\python.exe tools/verify_animation_finished_editor.py
```

## Native API

`AnimationAsset::Load(path)` publishes an immutable asset only after validation.
`clips()`, `node_names()`, `parents()` and `skin_joints()` expose metadata.
`rest_pose()` and `sample(clip, seconds, loop)` return node matrices in document
order and skin palettes in the skin's authored joint order. Skeleton construction
retains non-joint ancestors, multiple roots and matrix-authored static nodes.
Internally, ozz's depth-first skeleton order is mapped back to document IDs.

Sampling preserves glTF's STEP discontinuities, linear translation/scale,
shortest-arc quaternion slerp and time-scaled cubic Hermite curves. Cubic
quaternions are normalized after evaluation. Source curves are evaluated directly
so the initial importer does not approximate STEP/CUBICSPLINE by baking them to a
fixed frame rate. Ozz `LocalToModelJob` evaluates the resulting SoA pose. Compressed
ozz animation streams and animation state-machine authoring are later integration
work; the current blend is a deterministic native crossfade.

Non-looping time is clamped to the clip duration, then individual tracks hold
their first/last values outside their key range. Looping uses positive modulo,
including negative times; zero-duration single-key clips hold their only value.
Each evaluation starts from the rest pose and has no mutable sampling history.

Skin palettes multiply each joint's model matrix by its inverse bind. The glTF
mesh node transform is not applied again to skinned vertices. The engine entity
transform is applied separately by the renderer. Missing inverse
binds are identities; accessors may contain unused trailing bind matrices.
`SkinPosition` normalizes positive weight sums and supports up to 16 influences.

The renderer accepts contiguous JOINTS/WEIGHTS sets 0–3, unsigned byte/short joints,
float or normalized byte/short weights, and static or animated unskinned mesh
nodes. Textures, vertex colors, material overrides and transparency retain their
existing behavior. Deformed centers drive transparent primitive ordering.

Skinning currently runs on the CPU and streams separate vertex buffers for each
visible instance to SDL_GPU; textures, indices and original geometry remain shared.
Animated models are limited to 500,000 expanded triangle vertices. Face lighting
is recomputed after deformation, matching the existing fixed-light renderer.
Vertex-shader skinning and large-crowd performance are subsequent renderer work.
Orbit auto-framing currently uses bind-pose bounds. Checkpoint identity covers
the full `assets/` library plus scene and prefab models elsewhere in the project,
including external glTF/GLB buffers and images. Build preserves these relative
paths and stages their dependencies; see [persistence.md](persistence.md).

## Validation and current bounds

- glTF/GLB and base64/external local buffers; percent-encoded filenames and
  Unicode paths; sparse and interleaved float accessors.
- At most 1024 document nodes, hierarchy depth 256, 256 skins/clips/buffers,
  one million channel keys, 64 MiB document and 128 MiB declared buffer data.
  Individual accessors also have a one-million-element cap.
- Reject cycles/duplicate parents, malformed buffer ranges and sparse indices,
  escaping external paths, disconnected skin joints, invalid skeleton roots,
  missing scene skeletons and insufficient inverse-bind matrices.
- Reject duplicate channels, invalid time order, non-finite values, non-unit
  key rotations, matrix-targeted animation, shear and malformed cubic tracks.
  Degenerate interpolated quaternions fail explicitly instead of emitting NaNs.
- Morph targets/weight animation are explicitly unsupported. Root motion,
  retargeting and full skeletal IK remain open; clip crossfade, state transitions and
  metadata-driven notify events are supported by the animation nodes.

`design.md` Flow A is not fully complete: dedicated asset/clip/skeleton Inspector
references, clip browsing and timeline authoring still need their editor flow.
Gameplay graph authoring, native playback/rendering and saved continuation are
covered by the verifiers below; Linux and crowd performance remain unverified.

## Reproduce

Dependencies need CMake 3.30 or newer. The shared Windows installation currently
uses CMake 4.4.4. `tools/fetch_ozz.py` verifies the pinned archive and preserves an
existing dependency directory. Builds stage the upstream MIT license.

```powershell
.venv/Scripts/python.exe tools/create_animated_robot.py
.venv/Scripts/python.exe -X utf8 tools/verify_animation_assets.py
.venv/Scripts/python.exe tools/create_animation_demo.py
./tools/build.ps1 -Project examples/animation_demo/project.json
.venv/Scripts/python.exe -X utf8 tools/verify_animation_workflow.py
.venv/Scripts/python.exe -X utf8 tools/verify_animation_editor.py
```

The verifier builds `node_animation_probe` before running analytic reference and
invalid-asset cases, then records source/binary hashes in
`artifacts/validation/animation-assets-checks.json`. It compares independent
processes, glTF/GLB/external/base64 forms and the rigged Blockbench robot.

`examples/animation_assets/robot.gltf` and `robot.glb` derive from the existing
nine-cube Blockbench mesh. Six joints provide Idle, Wave and Walk clips. The
gltf file uses `animation data.bin`; the GLB is self-contained. This asset folder
is a fixture. `examples/animation_demo/project.json` is the playable two-robot
project, with independent Wave/Walk, keyboard playback controls and S/L checkpoints.

The four-host verifier relocates the game to a Unicode folder with developer
tools absent from PATH. It compares complete snapshots and GPU pixels, fresh
process continuation and invalid-save rollback. Native graph tests exercise all
13 nodes, negative speed, looping, completion and entity lifecycle. GPU tests
compare skinning with independently baked geometry, including quantized weights
across two influence sets, and reject malformed skins.

Primary references: [ozz 0.17.0 release](https://github.com/guillaumeblanc/ozz-animation/releases/tag/0.17.0),
[glTF skinning and interpolation specification](https://github.com/KhronosGroup/glTF/blob/main/specification/2.0/Specification.adoc).
