# Named scenes and project graphs

Projects can contain up to 64 named scenes, each with its own scene document and
gameplay graph. The Python editor, headless interpreter, generated game and SDL
viewport use the same scene replacement and checkpoint code. There are **873
builtin nodes**, including these eight additions:

| ID | Node | Behavior |
|---|---|---|
| 1019 | On Scene Loaded | Runs after initial scene creation or successful Change/Reload. |
| 1020 | On Scene Load Failed | Runs on the old graph if an accepted request fails during preparation; scoped `Scene` and `Error` strings. |
| 7004 | Change Scene | Requests replacement by a project scene ID; returns `Accepted`. |
| 7005 | Reload Scene | Requests a fresh instance of the active scene; returns `Accepted`. |
| 7006 | Get Active Scene | Returns the active scene ID. |
| 7007 | Get Scene Names | Returns all project IDs in lexical order. |
| 7008 | Scene Load Succeeded | Last scene-operation status; false while a request is pending. |
| 7009 | Get Scene Error | Last scene-request/preparation error, or empty on success. |

## Authoring and building

Use **Scene > New Scene…**, **Choose Scene…** and **Use as Startup Scene**.
Scene IDs start with a letter and contain up to 64 ASCII letters, digits,
underscores or hyphens. Display names may contain Unicode. New Scene creates
separate documents and publishes the manifest last; existing files are protected.
Save/Discard/Cancel handles dirty work before switching, and an active embedded
preview shuts down before loading the next authored graph. The title and hierarchy
show which scene is being edited.

Preview begins at the scene open in the editor. Export C++ / Build Game uses the
startup scene. Both compile all scene graphs, including current unsaved edits.
Asynchronous builds capture all scene/graph documents before starting the worker;
later editor or disk document edits cannot change that request. Assets remain
files on disk and are staged at build completion. External model dependencies
from every scene and its prefabs are included. Errors identify `scene/node`;
activating a Problem navigates to the appropriate authored graph.

Version-1 projects remain readable as the single scene `main`. Adding a scene
upgrades the manifest to version 2 without replacing its original documents:

```json
{
  "version": 2,
  "name": "My game",
  "entry_scene": "menu",
  "scenes": [
    {"id": "menu", "name": "Menu", "scene": "scenes/menu.json", "graph": "graphs/menu.json"},
    {"id": "level", "name": "Level", "scene": "scenes/level.json", "graph": "graphs/level.json"}
  ]
}
```

Paths must stay inside the project and each document has a distinct path.
`python -m editor.cli --project path/project.json --output path/generated` compiles
the complete project. GraphBuilder remains the Python authoring API for each
graph; `editor.core.projects.project_snapshot` and `compile_project` assemble them.
Functions, custom events, components and node IDs are scoped to their scene.
Generated C++ places each scene's callbacks in a separate namespace.

## Runtime boundaries

A request returns before changing worlds. Existing Out paths and the current
frame finish first. The host processes at most one transition at the startup/frame
boundary, before pending persistence. A request made by On Scene Loaded or a
failure callback waits for the next boundary. Unknown IDs, a second pending
request, pending Save/Load and application shutdown reject immediately with
`Accepted=false` and an error; they do not emit On Scene Load Failed.

New entities, graph bindings, model/GPU resources, audio and UI are prepared in a
separate context. A preparation failure keeps the old world and reports its error
through the old graph. On successful commit, object-start lifecycle deliveries
run before On Scene Loaded. On Game Start runs only once per host Play session.
An error in a callback after commit is a graph error in the new scene; the completed
transition is not rolled back. Quit cancels pending scene requests.

Scene replacement resets entities, variables, input/context state, RNG, timers,
latent tasks, physics, animation, UI and scene audio. It preserves host frame/game/
real clocks, Time Scale, world pause, save-storage selection, logs, instruction
budget and host audio capture/device. Held physical input is released at the
boundary. Reload follows the same rules. Bulk scene replacement does not dispatch
per-object destruction callbacks or carry objects/variables between scenes.

Whole-game checkpoints include active scene and scene status. Loading resolves
the saved scene's trusted graph bindings, stages its resources, then restores its
exact simulation, latent tasks and event state. It does not replay On Game Start
or On Scene Loaded. Invalid data leaves the current world and save file intact.
The complete project IR, runtime and resource library must match; editing any
scene or changing the entry scene can invalidate an older checkpoint.

## Demo and validation

Open `examples/scene_session_demo/project.json` in the editor or run
`artifacts/demos/scene-playground/Play.cmd`. C enters the level, M returns to the
menu, R reloads, S/L save/load, P/U pause/resume and Q quits. X demonstrates a rejected
unknown ID. `Replay.cmd` visits both scenes automatically. The menu has one
Blockbench robot; the level has animated, timed and physical robots, UI and audio.

Evidence and exact totals are in [validation-report.md](validation-report.md).
Verification covers four relocated hosts, actual editor keyboard input, GPU/PCM
parity, failed-resource rollback, cross-scene saves, a real asynchronous editor
build and both standalone launchers. Windows/Vulkan is the tested platform.

This is replacement of one active world. Additive/multiple active scenes,
asynchronous loading/progress/cancellation, persistent-object transfer, scene-exit
events, scene renaming/deletion and a visual scene dependency browser remain open.
The original engine goal remains active.
