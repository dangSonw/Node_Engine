# Native game template acceptance

Current verified milestone: [31 October 2026 results](template-games-status.md).
Read the complete [Flappy Bird](games/flappy-bird.md) and
[Isometric Snake](games/isometric-snake.md) authoring guides. The editor's
**File > Project Markdown…** opens each project's `docs/guide.md` for reading,
editing and image preview; **F1** opens node IO/help.

The gameplay belongs to each saved `.nen` project's graph and reusable functions.
Python simulations are not proof of native gameplay. The release gate requires
explicit replays, native state assertions and graphical captures.

Each game must provide `acceptance.json` in its project folder:

```json
{
  "version": 1,
  "controls": "Space: flap; R: restart; P: pause",
  "state_paths": {"ticks": "variables.steps", "resets": "variables.resets", "reason": "variables.status"},
  "scenarios": [
    {
      "id": "score",
      "frames": 300,
      "before_frames": 1,
      "replay": "replays/score.json",
      "covers": ["scoring"],
      "assertions": [
        {"path": "variables.score", "op": "ge", "value": 1},
        {"path": "variables.alive", "op": "eq", "value": true}
      ]
    }
  ]
}
```

Replay files use the engine's version-1 input event format. Scenario names are
unique lowercase ASCII letters, numbers, underscores or hyphens. Paths in state
assertions may be dot-separated strings or arrays of keys. A final typed
`{"type": ..., "value": ...}` variable is automatically unwrapped. Supported
operators are `eq`, `ne`, `gt`, `ge`, `lt`, `le`, `len_eq`, `len_ge`, `contains`.
Flappy Bird must cover `scoring`, `death`, `restart`; Snake must cover `scoring`,
`growth`, `wall_collision`, `self_collision`, `restart`. Assertions must substantiate
those labels; merely naming a scenario does not prove a behavior.

The verifier also enforces tag semantics against runtime observations. Scoring
must increase score and simulation steps; growth must increase the actual body
array. Death must set `alive=false` after simulation has advanced and record a
nonempty reason. Wall/self collision must record the correct reason. Restart
requires a dead observation before reset, a higher reset counter, zero score,
`alive=true` and a reset round-step counter. Scoring, growth and restart scenarios
therefore require `before_frames` (at least 1 and earlier than `frames`).
Optional `before_assertions` checks the earlier observation explicitly.
Default semantic fields are `variables.score`, `variables.alive`,
`variables.steps`, `variables.resets`, `variables.snake` and `variables.status`.
Use `state_paths` to map `score`, `alive`, `ticks`, `resets`, `body`, `reason` to
the graph's actual fields. Default collision reasons are
`WALL HIT  /  R TO RESTART` and `SELF COLLISION  /  R TO RESTART`; optional
`death_reasons.wall_collision` / `death_reasons.self_collision` can map other
unambiguous reason strings. All graphical observations require positive frame
limits: a zero limit means unlimited interactive play in the graphical host.

Build each project into its own directory and run the verifier:

```powershell
tools/build.ps1 -Project templates/games/flappy_bird/flappy_bird.nen -BuildDirectory .work/flappy-build
.venv/Scripts/python.exe tools/verify_template_games.py --project templates/games/flappy_bird/flappy_bird.nen --build .work/flappy-build --output artifacts/validation/flappy-bird
.venv/Scripts/python.exe tools/package_template_games.py --project templates/games/flappy_bird/flappy_bird.nen --build .work/flappy-build --verification artifacts/validation/flappy-bird --output templates/games/flappy_bird/dist
```

Use equivalent paths for `isometric_snake_3d`. Package output must be new or empty
to avoid mixing stale files with a new build. The verifier compares the saved
project against generated IR, runs every scenario in all four native hosts,
checks gameplay assertions, compares complete states and compares graphical
pixels. `checks.json` remains failed if any gate fails. Inspect the captures
visually as well; matching pixels alone cannot establish correct presentation.
Each run invalidates previous success first, uses fresh save roots, and removes
old output/capture files before launching. Packaging checks program, contract,
replay and executable hashes to reject stale evidence.

Packaging requires passing verification and unchanged executable hashes. It
copies native dependencies, assets, UI, fonts, shaders and licenses, then runs a
relocated copy from a Unicode directory with only the Windows system PATH.
`package-checks.json` records native state/framebuffer parity. `Play.cmd` and
`Replay.cmd` provide interactive and deterministic launchers without Python/Qt.
These scripts are acceptance infrastructure; their existence does not mean either
game has passed. Current proof comes from their saved reports and runtime output.
