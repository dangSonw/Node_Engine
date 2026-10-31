# Game templates

Two playable native games, authored with ordinary nodes and reusable functions.
Each folder has a Node_Engine `.nen` manifest, graph, scene, assets, generated C++
and deterministic native gameplay replays. Open the `.nen` through the startup
Project Manager to inspect/edit the graph, then press Play.

- `flappy_bird/flappy_bird.nen`: Space/left click to start or flap, P to pause,
  R to restart. Fly through seeded/recycled pipe gaps, earn points and avoid
  pipes, the ground and ceiling. Includes score/best and an original sprite HUD.
- `isometric_snake_3d/isometric_snake_3d.nen`: WASD/arrows to turn, P to pause,
  R to restart. Eat food to grow, avoid the wall and your own body. Includes
  an isometric board, shared cube meshes, body/food rendering and score/best HUD.

Run each folder's `Play.cmd` for its packaged native build, or `Replay.cmd` for
the supplied scoring replay. `dist/` includes the Windows executable, DLLs,
assets, fonts, shaders and licenses; Python and Qt are unnecessary for playing.
Best score survives round resets within the current process. The old `game.py`
and `project.json` files are legacy fixtures and are not used by native gameplay.

`acceptance.json` records explicit gameplay assertions, before/after observations
and replay files. See [native acceptance](../../docs/template-games.md) for the
four-host state/GPU checks, editor proof and relocated package commands.

The generator writes each template's known source/asset/replay files without
deleting its folder. Use a fresh output directory when experimenting:

```powershell
.\.venv\Scripts\python.exe tools\create_template_games.py --output path\to\fresh-templates
```

Regeneration creates source projects. Build/package them using the documented
commands to create or replace their standalone `dist/` snapshots.
