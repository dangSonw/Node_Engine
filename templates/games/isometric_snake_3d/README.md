# Isometric Snake 3D

Open `isometric_snake_3d.nen` in Node_Engine, then Play. Click the game window.
Use WASD or arrows, P to pause/resume, R to restart. Eat coral cubes, avoid the
rim and your body. The initial food is three cells ahead. Best score survives
round restarts during the current session. The game starts immediately.

Every gameplay rule is an editable native graph. Reusable functions in the
graph contain board refresh, bounded food placement, reset, tick, death and
turn validation. The board is 12 by 12 with a 0.18 second native repeating timer.
The 144 body entities share one project-local cube glTF mesh. Inactive pool
entities are activated as the snake grows; no hidden Python gameplay is used.

`acceptance.json` and `replays/*.json` describe native test scenarios. Regenerate
with `tools/create_isometric_snake_template.py --output DIRECTORY`. This writes
only this template's known files and preserves its project UUID.
