# Flappy Bird

Open flappy_bird.nen in Node_Engine. Space or left click starts/flaps; P pauses;
R resets the round. Fly through gaps and score once per pipe pair. Ground,
ceiling and pipe collisions end the round. Best score survives round resets
within this game process. Restart uses the same seed for reproducible practice.

All gameplay is authored as ordinary nodes and named reusable functions in
graphs/gameplay.json. Select a function to inspect Reset Round, Flap, each pipe,
Simulate Bird, Game Over and HUD updates. No embedded C++ gameplay is used.
Read or edit docs/guide.md with File > Project Markdown (Ctrl+Shift+M).
Native acceptance is described in acceptance.json and replays/.
