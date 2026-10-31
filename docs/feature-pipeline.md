# Feature pipeline milestone

Scene documents may contain optional `features` metadata. The editor and export
validate the same JSON contract, and generated IR preserves it. The deterministic
headless helpers in `editor/core/feature_pipeline.py` cover tilemaps, sprite
states, sorting layers, runtime texture metadata, PBR materials, normal maps,
lights, acyclic Shader Graph data, animation transitions/notifies, two-bone IK,
cinematic camera interpolation, navigation, AI, streaming, replication,
inventory, combat, quests, autosave, profiling, plugins, watches, graph delete
and accessibility labels.

The editor also provides a separate per-node code view. Action nodes may carry
an embedded C++ integration snippet; the dedicated C++ Code node provides an empty
body for authored code. Native Preview and Game share compiled hooks, stale hooks
trigger rebuilds, and compiler Problems navigate to the node/code line. Full
debugging, live code replacement without rebuild and script languages remain open.
Nominal Struct/Enum arrays/maps/sets now use the same editor and native workflow,
including node runtime-source inspection and editable action hooks; see
[typed-data.md](typed-data.md) for direct authoring and four-host evidence.

Tilemap meshes, sprite atlases, authored sprite state machines, declared runtime
texture files and the scene PBR normal-map resource now enter the SDL_GPU/resource
update path in the graphical host while metadata is preserved by the headless
host; state frame/time is serialized in native snapshots and can be changed by graph nodes.
Native navigation, AI state, combat, quest, interval autosave and inventory nodes
operate on runtime state. Streaming currently selects chunk coordinates; it does
not load/unload scenes or resources. Replication is a local authority/value journal
without network transport. Profile samples use the game clock, not a CPU/GPU timer.
Metadata validation and Python helpers do not prove an implemented native backend.
Runtime texture replacement, Shader Graph authoring/render integration, network
transport and the full GUI debugger/IME gates remain open. The two templates under
`templates/games` are starter graphs with separate Python gameplay simulations;
complete native gameplay and interactive acceptance remain open.
