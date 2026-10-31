# Scene authoring milestone

The editor can now create a new project, create/duplicate/rename/delete entities,
assign imported models to the selected entity, and instantiate models from Assets.
Entity and graph edits use one undo history. Stable IDs are independent of labels;
Vietnamese names are preserved in the inspector, saved scene and exported game.
Normal text editing keeps its own undo behavior; hierarchy/graph Ctrl+Z controls
the domain undo stack. Scene selection does not add spurious undo steps.

The runtime draws multiple mesh entities and shares GPU buffers for repeated
assets. Each entity has its own position/rotation/scale. Camera framing includes
transformed bounds and adapts to narrow viewports. Geometry replacement is prepared
before committing; failed loads preserve the last valid scene. A structural edit
resets the scene, while a transform edit/undo updates the current native entity.
An unsuccessful reload cannot start an old graph by falling through to Play.

The importer copies relative buffer/image dependencies in glTF and GLB, handles
URL-encoded file names, and preflights missing or out-of-directory dependencies.
Repeated imports get a distinct folder, preserving existing files. Undoing mesh
assignment removes the scene reference and keeps the imported library resource.
Textures remain unsupported by the current renderer even though their files can
be copied. The later [entity milestone](entities.md) adds Flecs component storage,
hierarchy, inherited visibility/tags and runtime Spawn/Clone/Destroy.

Seven additional general nodes: Entity Exists, Get Rotation, Set Rotation,
Get Scale, Vector Subtract, Vector Lerp and Distance. Native golden tests use them
in a real graph and compare interpreted/compiled state against independent expected
positions, rotations, scales, distance and logs. Registry total: 55.

`tools/verify_scene_workflow.py` creates a fresh project through the actual dialog,
imports a valid model with an external binary buffer, constructs a graph, edits
two robot entities, exercises real keyboard shortcuts and undo, previews them,
builds a standalone game, switches projects while preview is active, and reopens
the saved game. GPU readback checks count two separated models and test margins
in a narrow viewport. All 18 checks passed. The recorded file is
`artifacts/validation/scene-workflow-checks.json`.

The authored sample is retained at `examples/scene_demo/project.json`. Start it:

~~~powershell
.\.venv\Scripts\python.exe -m editor.main examples\scene_demo\project.json
~~~

After 120 deterministic frames at 60 Hz, only the left robot rotates 90 degrees;
the right robot stays at X=1 with zero rotation. Actual captures are stored as
`scene-authoring.png`, `scene-two-robots.bmp` and `scene-export.bmp`.
The retained sample was also rebuilt and checked in native preview and compiled
game: both state and GPU bitmap match byte-for-byte after 120 frames. See
`artifacts/validation/scene-parity-checks.json` and `scene-preview-120.*` /
`scene-compiled-120.*` for the comparison.

This historical milestone does not complete the engine. Functions/events, typed
variables/collections and builtin Flecs entities have since been implemented.
Generic components/prefabs, physics, animation, audio, game UI, specialized nodes
and cross-platform acceptance remain on the full roadmap.
