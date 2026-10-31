# Variable scope and lifetime

Use **Scene > Scene Variables…** to choose the Scope column. Old documents without
`variable_scopes` keep scene scope. Initial values still use the existing typed
JSON declarations; the dialog accepts named Struct/Enum types declared in
the graph or scene as well as scalar/array/map/set values. Declared Struct/Enum
types also have Get/Set nodes, including explicit scope variants. User-type
definitions must be available in a scene that operates on those named values;
project-wide type-definition synchronization remains part of the authoring work.

| Scope | Storage and lifetime |
|---|---|
| `scene` | Belongs to the active world; entering or reloading a scene initializes it from that scene's authored values. |
| `global` | Belongs to the current game session; all scenes see the same value, retained across Change Scene and Reload Scene. A new Preview/game session resets it. |
| `entity` | Each live entity starts from the shared typed default and owns its writes. Clone copies independent values; destroying the owner removes them. Scene changes/reloads replace those entities and their values. |

Global declarations are collected from every project scene, including scenes not
yet entered. Repeated declarations must have the same type and initial value;
conflicts are rejected. Global and scene namespaces may use the same name with
different types when accessed explicitly.

Existing **Get/Set Variable** and their typed variants resolve the selected
name's authored scope. Entity scope uses the current event actor (`Self`) and
requires a live owner. Global input handlers have no implicit entity actor; use
an explicit Entity node there instead of relying on `Self`.

Explicit nodes are available for all 40 builtin value types:

- **Get/Set Global Integer Variable**, **Get/Set Scene Float Variable**, etc.
- **Get/Set Entity Integer Variable**, with a live Entity input.
- Array/map/set variants, for example **Get Global Vector3 Array Variable** and
  **Set Entity String Map Variable**.

The compiler checks constant names within their namespace. Dynamic names retain
runtime type checks. A value cannot change its stored type; named Struct/Enum
values also keep their nominal type tag.

Save/Load Variable resolves the same authored scope as Get/Set Variable and uses
the current actor for entity values. Multi-value loads validate every value
before committing any namespace. Whole-game checkpoints restore global values,
scene values, per-entity overrides and scope declarations together. Save/Load
Variable also preserves named Struct/Enum type tags.

Scene JSON uses `variables` and `variable_scopes` for declarations. Optional
`global_variables` and `entity_variables` contain runtime state or authored
per-owner overrides. `scene_variables` preserves explicit scene values shadowed
by another declaration of the same name. Runtime snapshots expose implicit
entity values for a live current actor in the top-level `variables` view, while
`scene.variables` retains the entity template default for restoration.

The scope implementation does not add a separate named function-local variable
namespace. Function parameters, returned values and captured graph outputs keep
their existing execution-scope rules. Richer Struct/Enum graph authoring and
collection support remain part of the typed-data acceptance work.
