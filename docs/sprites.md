# Sprites and frame atlases

The editor and native renderer support PNG/JPEG sprites on a double-sided XY
quad. Each entity has its own frame and X/Y flip state. Entity position,
rotation, scale, hierarchy, visibility and activity apply normally. A sprite
can coexist with a static mesh on the same entity.

## Authoring

1. Open **Scene > Sprites…**, choose **Import Image…**, and select PNG/JPEG.
   The editor copies the image into the project's `assets/sprites` directory.
2. Choose **Edit…** to set the grid's columns/rows, world width/height, pivot
   and nearest/linear filter. The grid must divide the image exactly.
3. Select an entity, assign **Sprite** in the Inspector, then choose its frame
   and **Flip X / Flip Y**. Frame numbers start at zero and run left to right,
   then top to bottom. Pivot `[0,0]` is the bottom left; `[0.5,0.5]` is the center.
4. Play, save or build normally. Undo/Redo includes library edits, assignment,
   frame and flips. Undo retains imported image files for Redo.

Sprites use alpha blending and unlit color by default. Assigning an existing
material overrides color, opacity, alpha mode/cutoff and lighting as it does
for a mesh. Linear filtering clamps samples to each frame's interior to avoid
color bleeding from neighbouring frames. This atlas path does not generate mipmaps.

## Nodes

Rendering IDs **14101–14110** are generated from `nodes/registry.yaml` and call
the same native functions in Preview and exported games.

| Node | Behavior |
|---|---|
| Set Sprite | Assign a registered sprite; reset frame to 0 and clear flips |
| Get Sprite | Return its asset ID, or an empty string if unassigned |
| Clear Sprite | Remove the binding; preserve the entity and its other components |
| Set / Get Sprite Frame | Select/read the zero-based frame |
| Get Sprite Frame Count | Read columns × rows |
| Set Sprite Flip | Set both flip flags without changing transform or pivot |
| Get Sprite Flip X / Y | Read the flip flags |
| Sprite Exists | Check the scene library for an asset ID |

Unknown assets, absent sprite bindings for frame/flip operations, invalid
entities and out-of-range frames report the originating node. Frame setters
reject invalid values before mutation; they do not silently clamp or wrap.

## Persistence and runtime

Scene `sprite_assets` contain version-1 asset definitions: ID/name, relative
texture path, grid, dimensions, pivot and filter. Entity `sprite` values hold
`asset`, `frame`, `flip_x`, `flip_y`, or null. Native Flecs components support
clone, prefab inheritance, explicit overrides, Apply/Reset and snapshots.
Prefab capture stores sprite dependencies; cross-project library import copies
the images and rewrites project-relative paths. Conflicting IDs are rejected.

Images must be inside project assets. Encoded and decoded images are limited
to 64 MiB, with at most 8192 pixels per axis. A library has at most 1024 assets
and an atlas at most 65536 frames. The native scene limits decoded sprite
textures to 256 MiB. Bad files or grid dimensions abort reload before replacing
the running scene/GPU resources.

## Example and evidence

Open `examples/sprite_demo/project.json`. Space advances the top-left sprite
and wraps after four frames; X/Y toggle flips. Its graph uses the existing
integer/branch/input nodes. The other sprites demonstrate shared-image,
independent-frame rendering. `tools/create_sprite_demo.py` recreates the example.

`tests/test_sprites.py`, `tests/test_sprite_gpu.py` and
`tools/verify_sprite_workflow.py` cover authoring, pixels, native execution,
prefab portability, failed reload and a relocated native build. Current results
are recorded in [validation-report.md](validation-report.md).

Sprite animation clips/state machines, arbitrary atlas rectangles, nine-slice
UI, sprite sorting layers, runtime image-file loading and texture slot overrides
remain pending. Transparent primitives currently sort by center depth; this
does not solve intersecting transparent surfaces. The broader engine goal remains active.
