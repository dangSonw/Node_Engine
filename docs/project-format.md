# Project manager and .nen projects

Run `python -m editor.main` (or `node-engine`) to start at the project manager.
Choose **New Project**, browse a project, or select a recent project and click
**Open Project**. The editor is constructed only after this choice. Passing a
project on the command line preselects it in the manager; it still requires Open.
Use **File > Project Manager…** or Ctrl+Shift+O to choose another project.
Save/Discard/Cancel protects current work before switching. Missing documents,
unsupported formats and incompatible engine versions appear in the manager.

The browser follows the three-column arrangement of Unreal Engine's Project
Browser: category tiles, a searchable thumbnail grid, and a preview/details pane.
The footer contains the project path/name and Open/Create controls. **Games**
offers Blank 3D and Blank 2D; the latter creates a real orthographic camera.
These are starting presets using the same project format and native runtime.
Their `editor.node_workflow` preference selects `3d` or `2d` node suggestions;
`all` enables both. Existing projects default to `all`. The preference survives
Save/reopen and never changes compilation or removes existing nodes. The node
library, quick add and port search use this filter; port search additionally
requires exact matching types and valid function/event scope. Function editors
inherit it and offer the same selector. See [node-workflows.md](node-workflows.md).
Double-click or press Enter on an existing project to open it. Selecting a new
template only selects it; creation requires **Create Project**. The supported
categories are Recent Projects, Games and Examples. Artwork is drawn by this
editor; Unreal assets/logos are not included. Layout references:
[Epic: creating projects](https://dev.epicgames.com/documentation/en-us/unreal-engine/creating-a-new-project-in-unreal-engine),
[Epic: opening projects](https://dev.epicgames.com/documentation/en-us/unreal-engine/opening-an-existing-unreal-engine-project).

Recent history is now stored independently of project folders and engine
installation versions in the user's `NodeEngine/project-history.json` application
data file. It retains the latest 100 paths, records actual open times, migrates
older settings lists/string values and uses an interprocess lock plus atomic JSON
writes. Missing projects stay visible. Legacy backup manifests of a converted
project are collapsed when its .nen file is opened, without deleting files.
Explicitly injected/test settings use a neighboring `.projects.json` file;
verification no longer writes test projects into the user's real history.

Existing projects in `projects`, `examples`, `templates/games` and added search
folders are discoverable even if the old editor never recorded their history.
Use **Add project folder…** to find projects stored elsewhere; the folder choice
survives restarts. Discovery is bounded to known folders, avoids generated/cache
trees and prefers .nen over legacy backup manifests. Discovered entries are
labeled **Existing project** with no invented last-open timestamp. Optional
`ProjectThumbnail.png`, `.node_engine/thumbnail.png`, or a project-relative
`thumbnail` manifest field supplies a thumbnail; otherwise a generated image is
used. Browsing/discovery does not rewrite project files.

New projects create a new folder; existing folders are never replaced:

```text
MyGame/
  MyGame.nen
  graphs/gameplay.json
  scenes/main.json
  assets/
    models/
    textures/
    audio/
    ui/
    prefabs/
```

`generated/` and `build/` are created when exporting/building. `.nen` is the UTF-8
JSON manifest identifying the whole project. It references separate scene,
gameplay-graph and asset documents; it is not a packed archive. Copy the whole
project folder when moving it. Scene/graph paths are relative, distinct, and must
stay inside that folder. Asset imports retain the existing asset validation.

## Manifest and engine versions

```json
{
  "format": "NodeEngine.Project",
  "format_version": 1,
  "project_id": "00000000-0000-0000-0000-000000000000",
  "name": "My game",
  "engine": {
    "created_with": "0.1.0",
    "last_saved_with": "0.1.0",
    "minimum_version": "0.1.0"
  },
  "version": 2,
  "entry_scene": "main",
  "scenes": [
    {"id": "main", "name": "Main", "scene": "scenes/main.json", "graph": "graphs/gameplay.json"}
  ],
  "assets": []
}
```

`format_version` versions the .nen container. `version` versions the existing
scene manifest: layouts 1 (single graph/scene) and 2 (named scenes) are readable.
Project identity survives relocation and saves. `created_with` is retained;
`last_saved_with` records the saving engine, and each save raises `minimum_version`
to at least that engine version. This is a conservative compatibility boundary.
Unknown optional manifest/engine metadata survives a compatible save.

The engine rejects unsupported container/scene formats and requirements newer
than the running engine before opening/editing project documents. This supports
known older formats and declared compatible files; it does not promise support
for every future engine release. Future format migrations must be implemented and
tested explicitly. Renaming a legacy JSON file to .nen is insufficient.

## Existing projects and tools

Legacy `project.json` files in layouts 1 and 2 remain readable and keep their
original format on normal Save. Stop Preview, then choose **File > Convert to
.nen…** to create `<folder-name>.nen` beside the existing documents. All scene
documents are checked first, occupied target names are rejected, and the original
manifest remains as a backup. Continue editing through the .nen file: the old
manifest is not synchronized. Existing files/graph node IDs/assets are retained.
Runtime checkpoints are not migrated across a changed compiled program.

The compiler and native build service accept either manifest extension:

```powershell
.\.venv\Scripts\python.exe -m editor.main path\MyGame.nen
.\.venv\Scripts\python.exe -m editor.cli --project path\MyGame.nen --output path\generated
```

Prefab-library import also accepts .nen. Windows file association/installer
registration is not included; open the engine and browse, or use the command line.

**Scene > Structs and Enums…** creates a manifest-owned `type_definitions` library
shared by every scene. Stable node identities, legacy collisions, staged
multi-scene refactors, Undo/Redo and save failure recovery are described in
[project-types.md](project-types.md). Scene/graph copies must agree with that
library. New scenes inherit it; projects without the field retain their legacy
scene-owned definitions until their first project type edit.
The starter game templates now have .nen manifests; their complete native
gameplay remains a separate pending goal.

Run `python tools/verify_project_launcher.py --output <fresh-folder>` for the
actual startup/New/Save/Open flow and screenshots. Unit/GUI cases live in
`tests/test_project_launcher.py`; the native startup-scene comparison is in
`tests/test_project_format_native.py`.
