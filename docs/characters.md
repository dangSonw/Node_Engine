# Character controllers

Characters use the pinned Jolt 5.6.0 `CharacterVirtual`, shared by interpreted and
generated games. `examples/character_demo/project.json` is a playable Blockbench
robot with a low step, wall and low roof. W/A/D or arrows move, Space jumps, C
crouches, V tries to stand, R returns to the start, and S/L save/load the game.
The standing capsule cannot enter the roof; crouching fits, and standing remains
blocked until the character leaves it. The rigid-body examples remain separate.

## Nodes and authoring

Eight nodes in **Character & Movement** bring the builtin registry to 425:

| Node | Behavior |
|---|---|
| Create Character | Creates a kinematic capsule on an existing entity. Radius and half height are local dimensions; mass and four controller settings are explicit inputs. Rejects an existing body. |
| Remove Character | Removes the controller and its capsule body, keeping the scene entity. No effect if it has no character. |
| Has Character | Tests whether the entity has a live controller. |
| Character Move | Sets persistent world X/Z velocity; Y must be zero. |
| Character Jump | Queues a grounded jump; Accepted reports whether the request was accepted. |
| Character Resize | Changes local radius/half height while keeping world foot height. Resized is false if blocked; body, entity and binding remain unchanged. |
| Configure Character | Sets maximum slope, step height, floor snap and push strength. |
| Character Ground Check | Captures Grounded, State, Entity, Point, Normal and Velocity from one query. Velocity belongs to the support body. |

Select the entity's **Add/Edit Rigid Body…** action and enable **Character
controller**. The dialog enforces a non-sensor kinematic capsule and edits all
four settings. The optional `rigid_body.character` object contains `max_slope`,
`step_height`, `floor_snap` and `max_strength`; ordinary collider records retain
their existing format. Authoring validates world Y-up orientation and positive
uniform scale, including ancestors. Scene save/reopen, Undo/Redo and inherited
prefab overrides use the existing collider ownership rules.

Clone Entity copies the live capsule, controller settings, desired movement,
velocity and pending jump, with fresh contact detection for the new identity.
Prefab Instantiate/Apply/Reset uses the existing staged scene/physics transaction;
replaced colliders restart from authored settings, while unchanged characters
retain their simulation. Stop restores authored settings and transforms; Play
does not duplicate the controller. Runtime resizing changes the live binding,
not the prefab's authored default. The demo adjusts its child mesh only after a
successful resize; changing a collider does not automatically rescale a mesh.

The existing **On Collision/Trigger Enter/Stay/Exit** handlers also receive
character capsule contacts, globally or scoped to an entity. The capsule enables
Jolt's kinematic-versus-static contact detection while a controller is attached;
detaching restores the ordinary body's policy. The virtual controller solves
movement, while capsule manifolds supply gameplay event points and normals.
These include Jolt's speculative contact margin; use Character Ground Check for
walkable support rather than treating any Collision Enter as landing.

Filters, enabling, removal and recreation follow the rigid-body event lifecycle.
Removed bodies retain one final Exit, recreated bodies deliver the old Exit before
their new Enter, and callbacks can destroy or deactivate receivers without
invoking their remaining owner handlers. A save requested by a callback is
processed after the completed physics step.

`examples/character_events_demo/project.json` adds a center trigger, live collision
and trigger HUD rows, and a checkpoint on the first solid contact. K reloads this
landing save; C/V still crouch/stand and S/L use the normal save slot.

Uniform entity/ancestor scaling updates the capsule around the entity's center
and requires clearance. Character Resize instead preserves foot height and writes
the resulting local entity transform back under its parent. Tilt is rejected.
Existing Set Position/Set World Position teleport, Get/Set Velocity access the
controller velocity, and body layer/mask/activity/enabling apply to characters.
Controller velocity is the velocity supplied to movement integration; when a wall
blocks movement, it can differ from displacement divided by elapsed time.

## Native API and movement

Create a non-sensor, stationary kinematic capsule with the existing rigid-body
API, then call `attach_character(id, settings)`. The body retains its existing
ID, layer, mask and enabled state. The virtual controller uses the same primitive
shape; after each character step its pose is copied to the body, so raycasts,
overlaps and other physics bodies can see it. Removing the body also removes
its controller. `detach_character` removes the controller and leaves the
kinematic body in place.

The capsule origin is its center, dimensions are world metres, and up is world
Y. Rotation can contain yaw; tilting the capsule is rejected. Settings expose
maximum walkable slope in degrees, step height, floor-snap distance and maximum
force for pushing dynamic bodies. Mass and gravity scale use the body's existing
settings. Jolt supplies capsule sweeps, penetration recovery, wall sliding,
stairs, floor following, ground velocity and dynamic-body contact response.

`character_move` sets the desired world X/Z velocity in metres per second. It
persists until replaced. Y must be zero; vertical speed comes from gravity and
jumping. Horizontal control is immediate, including in the air. The character
advances before the rigid-body simulation in `PhysicsWorld::step`. The host
retains responsibility for fixed-step timing.

`character_jump` accepts a positive speed only while supported by walkable
ground and not already moving upward or holding a pending jump. The request is
consumed once on the next enabled step. Disabled bodies freeze controller state;
their pending input resumes after re-enabling. A jump request made while disabled
or airborne returns false. Removing, disabling or filtering out the support
clears reported grounding.

`character_state` returns position, controller velocity, ground state, support
entity, contact point, normal and support velocity. Ground states are
`on_ground`, `steep_ground`, `unsupported`, `in_air` and `disabled`. Ground contact
geometry comes from the most recent controller update; teleport refreshes it.
`pose` returns the controller's velocity together with the capsule body
pose. Filters respect both bodies' masks, explicit ignored pairs and disabled
bodies; triggers do not block movement.

`character_resize` changes capsule radius/half height while preserving foot
height. It checks clearance first and returns false if the new shape is blocked,
leaving body and controller state unchanged. This supports crouching and refusing
to stand under a ceiling. Generic shape replacement, non-kinematic body type,
angular velocity, manual sleeping and rigid-body kinematic targets are rejected
while a controller is attached. Use character movement, resizing and body
enabling instead. Teleporting uses the existing transform API and clears a
pending jump. Setting linear velocity also sets the desired horizontal velocity.

## Checkpoints

Worlds without characters retain the existing physics checkpoint version 1.
Worlds with characters use version 2 and include each controller's configuration,
desired movement, queued jump and native saved state. The body allocator still
owns stable IDs; each virtual character derives its ID from its capsule body.

Jolt's native controller state includes pose/velocity, ground contacts, last
step timing and collision contacts needed for later slope response. Its pinned
binary layout is checked before Jolt reads it: bounded contact counts, native
body IDs, primitive subshapes, finite numbers, normalized rotations/normals,
enums and booleans. Native state is limited to 16 MiB per record and the combined
physics checkpoint to 48 MiB. At most 1024 stored contacts per character are
accepted. This implementation collides through ordinary body proxies; direct
virtual-character references in checkpoint contacts are rejected.

Restoration builds an independent physics world, restores rigid bodies, rebuilds
controllers and restores their state. Controller and capsule poses must agree,
and the whole checkpoint must recapture exactly before commit. A malformed
record leaves the original world unchanged. Existing game save compatibility
still requires the same runtime/program/assets identity; this adds no migration
for older game binaries.

Scene restoration also checks controller dimensions against the local binding
and world scale, the recorded/scene/native poses, and effective activity. A
numerically valid but inconsistent binding is rejected before committing the
loaded game. Authored settings and live crouching state are preserved separately.

## Verification and limits

Run `tools/verify_characters.py` using the project Python. It builds
`node_character_probe`, checks actual character trajectories and invalid-input
rollback, then compares eight saved scenarios against independent-world and
fresh-process continuations for 1120 frames. Scenarios include a queued jump,
midair motion, a disabled character with pending input, crouching below a ceiling,
a moving platform, a wall contact, a removed support and initial penetration.

The independent build in `tools/physics_probe/CMakeLists.txt` enables Jolt's
internal assertions and also exposes `node_character_probe`. Pass its configured
build directory to `verify_characters.py --build ... --output ...` to exercise
the same cases with assertions.

`tests/test_characters.py` checks authoring/ownership/dialog validation and native
graph creation, movement, captured ground outputs, jumping, clone/removal,
parent-scaled resizing, live scale changes, prefab reset and originating-node
diagnostics. Ground contacts describe the latest controller update; a character
must reach the floor before a grounded jump can succeed.

`tools/verify_character_scene.py` checks the relocated demo in all four native
hosts, including actual wall/step/roof movement, crouched and airborne Save/Load,
fractional-step continuation, malformed/inconsistent checkpoint rollback and
equal full state/GPU output. `tools/verify_character_editor.py` exercises actual
Inspector and graph editing, Undo/Redo/save/reopen, embedded simulation, physical
D/C/V/Space input, Pause and Stop/Play. Reports/screenshots are under
`artifacts/validation/character-*`; see [validation-report.md](validation-report.md).

Pass `--events` to either workflow verifier for the contact demo. The four-host
workflow verifies one Enter followed by Stay, leaving the trigger, hitting the
wall and exact continuation from the callback-triggered save without repeating
Enter. `tests/test_physics_events.py` runs the same scoped-payload, destruction,
recreation, activity, custom-event and budget-fault cases for ordinary bodies and
characters. Native contact tests also exercise detaching/reattaching and masks.

Arbitrary up axes, acceleration/movement modes, root motion, swimming/flying/
climbing, animated crouching and larger crowds remain later work. Horizontal
control is immediate, including in the air. Larger crowds and large-world
performance need additional gameplay coverage. These checks cover Windows;
Linux and cross-platform determinism remain unverified.
