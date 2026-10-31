# Seeded random playground

Open project.json in the Node_Engine editor, then Play.

- Space: random robot position, dice roll (1–6), and 25% bonus robot chance.
- R: reset seed 42. The next Space reproduces the first roll and position.
- S / L: save and load the whole game, including the random stream.

The Python source is tools/create_random_demo.py in the workspace. Five general
random nodes share the native runtime between Preview and the exported game.
