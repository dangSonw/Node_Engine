# Entity activity and layers

An entity has a local `active` boolean (default true) and a `layer` integer from
0 through 31 (default 0). Activity is effective only when the local flag and all
ancestor flags are true. Layers belong to each entity and do not inherit.
These are stored in the Flecs Activity component alongside the existing transform,
mesh, identity and tags. Old scenes without these fields keep their old behavior.

## Authoring and nodes

Select an entity in Hierarchy. The Inspector has an **Active (inherits parent)**
checkbox and a **Layer** field. Inactive branches display `[inactive]` and the
tooltip distinguishes the local flag from effective activity. Local flags on
children are preserved when a parent is disabled. Undo/Redo and save/reopen cover
both properties. Editing while preview is loaded uses the existing scene reload
path and therefore restarts gameplay state; these controls edit the authored scene.

| ID | Node | Result |
|---|---|---|
| 8028 | Set Entity Active | Set the local flag and update affected descendants |
| 8029 | Is Entity Active | Effective activity; false for a missing entity |
| 8030 | Get Entity Active Self | Read the local flag |
| 8031 | Get Entity Layer | Read the layer index |
| 8032 | Set Entity Layer | Set an index from 0 through 31 |
| 8033 | Find Entities By Layer | Sorted entity references; ActiveOnly defaults true |

Get/Set operations other than Is Entity Active reject missing references and
report the originating graph node. Spawn defaults to active/layer 0; Clone copies
local flags and layer, retaining its parent. Scene snapshots and reload preserve
them. Reparenting immediately recomputes activity for the entire affected branch.

## Runtime behavior

- Inactive entities and descendants do not render. The separate Visible flag
  remains unchanged; Is Entity Visible still reports visibility inheritance only.
- Owned timers automatically suspend while their entity is effectively inactive.
  Remaining time is frozen, including timers created while inactive. Reactivation
  resumes that remaining time without accumulating expirations during inactivity.
  Manual Pause is independent: activation never resumes a manually paused timer.
  Is Timer Paused reports the manual flag; snapshots additionally include
  `suspended: true` when activity suspends a timer.
- Custom events skip inactive recipients. Disabling a recipient or ancestor
  invalidates queued deliveries even if re-enabled before the queue drains.
  Existing subscription preferences are retained. Disabling then re-enabling
  inside a timer or event callback cancels the remaining callbacks for that
  delivery, so stale work cannot continue under a new activation interval.
- Scene-owned timers/events and global On Update/On Game Start continue. A global
  graph may explicitly inspect, edit or reactivate inactive entities. There is no
  implicit per-entity On Update binding in the current graph format.
- General name/tag/component/All Entities queries retain their existing behavior
  and include inactive entities. Component EnabledOnly filters the component's
  own flag. Use Is Entity Active when filtering these lists, or the ActiveOnly
  option on Find Entities By Layer.

Created/Enabled/Disabled [lifecycle events](entity-lifecycle.md) capture inherited
activity changes. Their owned handlers still receive notifications while inactive;
custom, timer and animation delivery keep the cancellation rules above.
Destroyed also reaches inactive receivers synchronously before deletion, with
their current effective activity captured in its Active output.
Prefab Apply/Reset also propagate inherited activity and emit those transitions.
Layers support identity and selection queries; collider masks are authored
separately. Render-camera masks and layer names remain subsequent work.

## Example and verification

Open `examples/activity_demo/project.json`. A scene timer switches a parent group
off and on every half-second. Its two Blockbench robots disappear together, and
the first robot's owned timer stops rotating it. A third robot on another layer
keeps rotating. The graph records active members of layer 3 in `active_actors`.

`tools/create_activity_demo.py` recreates the fixture; `tools/build.ps1 -Project
examples/activity_demo/project.json` builds both preview and exported game.
`tools/verify_activity_workflow.py` checks real Inspector interaction, native
suspension, GPU captures and preview/export equivalence at frames 15, 45 and 75.
The targeted native/editor suite passes 19 tests. The final desktop workflow
passes 37 checks, including ownership of the captured viewport, and has been
visually inspected. The preview/export states and GPU bitmaps match exactly at
all three frame counts. See `docs/validation-report.md` for full regression status.
