# Reusable materials and instance parameters

Open `examples/material_demo/project.json` and press Play. Three Blockbench robots
share the same material. Click the viewport, then press T to tint the center robot,
F to fade it, O to restore its imported glTF materials, or R to assign the shared
material again. The two side robots keep their own parameters. Esc restores editor
keyboard focus. `tools/create_material_demo.py` recreates the example.

Launch with `.venv\Scripts\python.exe -m editor.main examples/material_demo/project.json`.
For a manual root build, run `tools/build.ps1 -Project examples/material_demo/project.json`,
then `build/node_game_view.exe --project-root examples/material_demo`. The root build
uses project assets in place; the editor's Build Game stages the standalone assets.

## Authoring

**Scene > Materials…** creates, edits and removes scene-owned material assets.
Each asset has a stable ID; names can change without breaking bindings. Deleting
an asset still referenced by an entity or prefab fails without changing the scene.
Choose the asset in an entity's Inspector **Material** dropdown. **Edit Material
Instance…** stores only changed parameters on that entity; **Reset Material
Parameters** removes those overrides. **Imported mesh material** clears the assignment.
All these scene changes support Undo/Redo, save/reopen and native preview reload.
Structural/material edits reset simulation, as other structural scene edits do.

Material input fields on main-graph Set Material / Material Exists nodes offer an
asset-name picker and store the stable ID. A missing ID remains visibly missing;
it is never silently reassigned. Data wires can still supply IDs at runtime.

## Contract

| Parameter | Meaning |
|---|---|
| Color | Linear RGB, three finite numbers in [0, 1]; replaces the imported base-color factor |
| Opacity | Finite number in [0, 1]; multiplied by texture/vertex alpha |
| Alpha mode | `opaque` ignores alpha; `mask` discards below cutoff; `blend` blends with depth writes disabled |
| Alpha cutoff | Finite number in [0, 1], used by mask |
| Unlit | True disables fixed face lighting |

An assigned material applies to every primitive of that entity. Imported texture,
UV transforms, samplers and COLOR_0 stay in use. Clearing the assignment restores
the mesh's original per-primitive factors, alpha settings and unlit flag. Instance
setters never mutate the asset or another entity sharing the mesh/material.

The scene's `material_assets` array contains at most 1024 version-1 `material`
objects, with `id`, `name` and the five parameters. IDs are 1–48 ASCII letters,
digits, underscores or hyphens. An entity's `material` is null or an object with
`asset` and `overrides`; overrides contain any subset of the five parameters.
Unknown fields, missing references, conflicting IDs, invalid types, non-finite
numbers and out-of-range values are rejected in authoring and native loading.

Prefab capture includes referenced material definitions. Library import copies
these dependencies and rejects conflicting definitions for the same ID. Editing
a shared asset updates matching captured definitions. Material binding is one
Flecs component for prefab Apply/Reset ownership; its parameter map is per-asset
instance state, not independent prefab-property ownership. Clone copies the map.
Snapshots preserve assets, bindings and explicit cleared prefab overrides.

## Nodes

| Stable IDs | Nodes |
|---|---|
| 14001–14003 | Set Material, Get Material, Clear Material |
| 14004–14005 | Get / Set Material Color |
| 14006–14007 | Get / Set Material Opacity |
| 14008 | Reset Material Parameters |
| 14009–14010 | Get / Set Material Alpha Mode |
| 14011–14012 | Get / Set Material Alpha Cutoff |
| 14013–14014 | Is Material Unlit, Set Material Unlit |
| 14015 | Material Exists |

Set Material resets old overrides. Get Material returns an empty string when no
asset is assigned; Material Exists returns false for an unknown ID. Parameter
getters/setters and Reset require an assigned asset and report a source-node
error otherwise. Missing/deleted entity references also fail explicitly.
The builtin registry now contains 309 definitions.

## Verification and limits

`tests/test_materials.py` checks authoring, portable prefab dependencies,
Apply/Reset, independent instances, clones, snapshot roundtrip and native
interpreter/generated-code equivalence. `tests/test_material_gpu.py` measures
actual Vulkan pixels for replacement factors, preserved COLOR_0/texture/UV,
alpha modes, lighting, reset and independent mesh instances.
`tools/verify_material_workflow.py` exercises real Qt dialogs/Inspector, Undo/Redo,
reload recovery, save/reopen, asynchronous Build Game and a relocated package
with only Windows system directories on PATH. Four input-replay checkpoints
compare preview and compiled state and GPU bytes. Evidence is under
`artifacts/validation/material-*`; see [validation report](validation-report.md).

The renderer now has a scene-feature PBR path for metallic/roughness, emissive
color, imported normal textures and up to four directional/point lights. The
original base-color material asset remains the authoring surface; per-primitive
material-slot authoring, runtime texture/UV replacement, external material files,
multi-light clustering, authored Shader Graph/SDL_shadercross and the Materials
graph workspace remain pending. Only Windows/Vulkan is verified.
