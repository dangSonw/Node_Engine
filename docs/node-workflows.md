# 2D and 3D workflows

Blank 2D and Blank 3D configure a starting scene and suggested tools. Both use
the same `.nen` manifest, scene/entity documents, gameplay graph, typed registry,
compiler and native runtime. A scene can contain sprite/tilemap geometry,
skeletal models, cameras, shared materials, input, UI and physics together.

This follows the distinction between defaults and engine capabilities described
in [Unity's 2D/3D editor modes](https://docs.unity3d.com/6000.0/Documentation/Manual/2DAnd3DModeSettings.html)
and [Unreal's Paper 2D workflow](https://dev.epicgames.com/documentation/en-us/unreal-engine/2d-in-unreal-engine).
Unity permits changing editor modes. Unreal's Paper 2D supports combined 2D/3D
gameplay and rendering.

**Node Library > Node suggestions** controls the library, Tab/quick add and port
search. Blank 2D starts with **2D + shared nodes**; Blank 3D starts with **3D +
shared nodes**. Choose **All compatible nodes** to author a hybrid scene.
Function graph editors inherit the preference and have their own selector.
The main preference is saved as `editor.node_workflow` (`2d`, `3d`, `all`).
Old projects without the field use `all`. Invalid preference values are rejected.

The registry annotates sprite/frame/state operations as `2d` and skeletal clip
operations as `3d`. Logic, data/math, transforms, input, UI, physics, materials
and cameras are shared. The existing planar IK operation remains shared. These
labels guide discovery; they do not remove loaded nodes or impose runtime modes.
Selecting a narrower filter keeps existing hybrid graphs, wires and behavior.

Port search requires the exact port type, excludes event configuration inputs
and respects pure/action function restrictions. Vector2 cannot connect directly
to Vector3; construct the intended value explicitly. Invalid/unknown node types,
links and literals are rejected before replacing the current graph. Runtime
resource checks still apply: a clip needs an animated mesh and a sprite frame
must belong to its atlas. A suggestion filter cannot prove dynamic resource
references valid for every future execution path.

Node_Engine currently uses one Jolt physics world and Vector3 transforms for
both kinds of rendered objects. A sprite's visible plane does not automatically
create a collider, constrain motion to XY or give a tilemap collision geometry.
Author explicit bodies and movement. Separate Rigidbody2D/Collider2D simulation
is not implemented. Camera projection can change independently of node filters.

Regression coverage: `tests/test_node_workflows.py`, `tests/test_port_search.py`
and `tests/test_hybrid_scene.py`. The hybrid fixture executes sprite state,
tilemap geometry, a skinned Wave clip, box/sphere bodies and camera projection
from one graph in interpreted Preview and generated C++ Game.
