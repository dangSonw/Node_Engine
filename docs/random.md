# Deterministic gameplay random

Twenty-five category-05 nodes share one random stream per running game.
The scalar, seed and spatial nodes have IDs 5020–5026:

| Node | Contract |
|---|---|
| Set Random Seed | Signed 64-bit seed; resets the stream immediately. Default seed is 0. |
| Get Random Seed | Reads the last assigned seed without advancing the stream. |
| Random Float | Finite Minimum/Maximum; result is in `[Minimum, Maximum)`. Equal bounds return that bound. |
| Random Integer | Signed 64-bit inclusive bounds, including the entire int64 range. |
| Random Boolean | True with Probability in `[0,1]`. |
| Random Vector | Uniform independent coordinates between finite Minimum and Maximum vectors. Each varying axis uses `[Minimum, Maximum)`; equal bounds return that coordinate. |
| Random Direction | A unit vector sampled uniformly over the sphere surface, within floating-point precision. No input parameters; use Vector Scale for speed or radius. |

Vector coordinates consume draws in X/Y/Z order, skipping constant axes. All
three bounds are validated before consuming any state, so an invalid later axis
cannot advance the stream. The float range handling also supports opposite
extreme finite endpoints and adjacent representable bounds.

Direction sampling consumes two draws: uniform Y in `(-1,1]` and uniform azimuth
in `[0,2*pi)`. The radial projection is `sqrt((1-Y)*(1+Y))`, with X/Z from the
azimuth. This assigns equal probability to equal-area latitude bands. Results
have unit length to floating-point precision. The PRNG integer stream is fixed;
trigonometric results may differ in their last bits across math libraries, so
bit-for-bit direction parity across platforms is not promised.

Selection and shuffle each support Float, Integer, Boolean, String, Vector3 and
Entity arrays (18 concrete nodes, IDs 5100–5105, 5110–5115 and 5120–5125):

| Node family | Contract |
|---|---|
| Random Item | Uniform selection from a nonempty array; captures both Value and zero-based Index. Duplicate entries remain separate choices. |
| Random Weighted Item | One finite nonnegative weight per array item; at least one must be positive. Captures Value and Index. Zero-weight entries cannot be selected. |
| Shuffle Array | Fisher–Yates permutation in a new array, preserving duplicates and leaving the input unchanged. Empty arrays are accepted. |

Weighted selection scales by the largest weight before accumulating, so a finite
input whose raw sum overflows remains valid. Probabilities are limited by double
precision and the generator's 53-bit float samples; extremely small relative
weights can become unrepresentable. A singleton choice, exactly one positive
weight, or a shuffle of zero/one item consumes no draw. Invalid inputs fail before
advancing the stream. The existing 65,536-item collection limit applies.
Entity arrays select reference values; they do not filter missing, inactive or
empty references. Supply a filtered query result when only live targets are wanted.

Random draws have execution ports and captured outputs. One execution produces
one value; all downstream consumers read the same captured result. An output
outside its execution scope is a compiler error. Use action functions for random
draws; pure functions cannot consume state. Calls in functions/events/updates
share the same stream, so execution order is part of reproducibility.

Set Seed stores its two's-complement 64-bit bit pattern in the stream. Generation
uses [SplitMix64 by Sebastiano Vigna](https://prng.di.unimi.it/splitmix64.c), with
explicit unsigned operations and the fixed `splitmix64-v1` algorithm ID. Float
sampling takes the upper 53 bits, maps with overflow-safe interpolation and keeps
the upper bound exclusive after rounding. Integers use rejection sampling to
avoid modulo bias; the full 64-bit range is supported without signed overflow.
An operation fails after 1024 rejected candidates, preserving its incoming state.

Equal numeric bounds and Boolean probability 0 or 1 return a constant without
consuming a draw. Invalid ranges/probabilities fail before consuming state. Finite
floating-point checks also apply at graph input boundaries. Reusing a seed and
the same ordered calls reproduces the sequence in Preview and exported C++ games.
Linux execution remains unverified.

Whole-game checkpoints include the algorithm, original seed and exact current
64-bit state as 16 lowercase hexadecimal digits. Load stages and validates these
fields before committing the game. A malformed random record leaves live state
and the save file unchanged. Stop/reload resets the stream; startup seed nodes run
again on Play. Existing progress-data nodes still read older save envelopes;
whole-game checkpoints from different runtime revisions require migration.

Open `examples/random_demo/project.json` for a Blockbench robot that changes
position, rolls a six-sided die and has a 25% bonus-robot chance on **Space**.
Each draw also chooses a uniform item, chooses weighted loot (Potion/Shield/Sword
at 6:3:1), and shuffles a four-card deck. The HUD displays the choices and order;
variables retain both selected indices and the shuffled array.
Robot positions now come from Random Vector. A small robot marks the sampled
direction at radius 1.8 from a point 0.8 units above the main robot's position.
**R** resets seed 42, **S** saves and **L** loads. After Load, the next rolls and
placements continue from the saved stream. The demo is authored in Python with
`tools/create_random_demo.py` through the same GraphBuilder and registry as the editor.

Run `tests/test_random.py` for reference sequences, boundary/error cases, capture
semantics and actual native interpreter/generated parity. Run
`tools/verify_random_workflow.py` after building this demo for relocated four-host
state/GPU parity, reseeding and fresh-process Save/Load continuation. Replay input
uses simulation frame numbers, which resume from the saved frame after a load.

`tests/test_random_collections.py` covers all six types, captured Value/Index,
input preservation, duplicates, validation and execution scope in both native
paths. `node_random_probe` checks deterministic selection/permutation, invalid
input rollback, zero weights, extreme/subnormal weights and fixed-seed 40,000-draw
histograms. Build this optional target with `cmake --build build --target node_random_probe`.

The native random probe additionally checks box bounds, unit length, first and
second direction moments, equal-area height bands, octants, invalid-axis rollback
and exact continuation after restoring the stream.

Noise and multiple independent streams remain subsequent category-05 work.

Windows verification uses relocated four-host comparisons and actual Qt editor
checks (node creation/Undo/Redo, save/reopen, physical Space/R/S/L, Stop and restart).
The latest results are recorded in [validation-report.md](validation-report.md).
The compiled standalone example is under
`artifacts/demos/random-playground/Play.cmd`. Source/report/package fingerprints
are recorded in `artifacts/validation/random-summary.json`; older reports retain
their original runtime fingerprints.
