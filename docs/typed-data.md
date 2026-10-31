# Typed variables and collections

The shared native runtime supports ten scalar types: `float` (double precision),
`int` (signed 64-bit), `bool`, `string` (UTF-8), `vec2`, `vec3`, `vec4`, `quat`,
`mat4` and `entity`. Entity references
are distinct from strings in both graph validation and native storage. Each scalar
also has a homogeneous `array<T>`, a string-keyed `map<T>` and an insertion-ordered
unique `set<T>` type: 40 builtin value types. Declared Struct/Enum types also
support these three collection families. Nested collections remain future work;
named Struct/Enum values and typed collection callbacks are supported.

This milestone introduced the typed collection families and callback variants. The
current registry includes 1175 builtin definitions. These include type variants
of the same collection operations, rather than independent gameplay systems.
The family declarations and explicit ID offsets in `nodes/registry.yaml` generate
the UI classes, port types and native adapters. Existing IDs remain unchanged.
Do not change family ID bases or type offsets; doing so would break saved graphs.

## Authoring

Use **Scene > Scene Variables…** to add, edit or remove initial values. Choose a
type from the cell dropdown and enter values as JSON. The dialog validates names,
types, duplicates and values before committing. OK is one scene undo step; Cancel
leaves both authoring and runtime state untouched. Save/reopen preserves the types.

The Scope column selects native scene, global or entity storage and lifetime.
Explicit typed scope nodes also support the scalar/array/map/set families; see
[variable scopes](variable-scopes.md) for ownership, scene transitions and saves.

A change to initial variables resets the native scene. A paused preview stays
stopped; a running preview resumes after successful reload, executing On Start
once against the new initial state. Undo follows the same rules. The dialog edits
initial scene data, not a live variable debugger/watch window.

The node library and quick-add search accept words in either order, for example
`entity each` or `integer map`. Collection pins have a square/grid cue and retain
the element type's color. Tooltips expose the complete port type.

## Data and execution rules

- Version-one numeric variable entries remain floats, preserving older projects.
  Other types use an explicit declaration, for example
  `"ready": {"type": "bool", "value": true}` or
  `"inventory": {"type": "map<int>", "value": {"coin": 10, "potion": 2}}`.
  A plain JSON integer is still a legacy float variable; use a declaration for int.
- `Get Variable` / `Set Variable` retain their original float behavior and IDs.
  Other types have typed Get/Set nodes. The first assignment initializes a variable;
  subsequent assignments cannot silently change its native type. Known-name type
  conflicts are reported at compilation. Computed names are checked at runtime.
- Arrays, maps and sets have value semantics. Collection operations return a new
  collection; connect that result to a typed Set Variable to persist it. Reading
  and transforming one variable does not mutate another variable.
- `Concat {label} Arrays` returns the left array followed by the right array.
  `Slice {label} Array` uses a checked half-open range `[Start, End)` and keeps
  element order; invalid or reversed ranges report the collection node.
- Sets preserve insertion order and ignore duplicate additions. Remove and Contains
  use value equality for the element type; JSON stores a set as a typed array so
  scene/save formats remain deterministic and portable.
- Struct declarations use `struct:Name` with named fields and validated defaults;
  enum declarations use `enum:Name` with stable labels. Runtime enum values are
  labels; numeric definition metadata does not make integer literals enum values.
  Make/Break support nested structs and enum fields in both native execution
  paths. The library exposes typed Get/Set variable nodes for each declared
  Struct/Enum, with automatic or explicit Global/Scene/Entity storage. Native
  field reads retain nominal type tags, and checkpoints retain the definitions.
  Graph and scene declarations survive editor save/reopen and code navigation.
  Use **Scene > Structs and Enums…** to create/edit/rename/delete definitions.
  Project type/field refactors migrate values, Make/Break ports and wires in every scene;
  referenced deletion and destructive field/label changes are rejected.
  Stable node/variable IDs and retired IDs preserve identity. A shared Undo step
  retains earlier graph history; Cancel or failed reconstruction keeps old state.
  Arbitrary embedded C++ references are not rewritten. A manifest-owned library
  synchronizes definitions and stable identities across active/inactive scenes,
  with one Undo, staged saves and legacy collision handling; see
  [project-types.md](project-types.md). Each declaration additionally exposes
  `array<struct:Name>`, `map<struct:Name>`, `set<struct:Name>` or the corresponding
  `enum:Name` forms. Their typed Get/Set, collection operations, Select and For Each
  nodes keep the complete nominal type, including empty values. Struct fields may
  contain these collections; recursive struct definitions remain invalid.
  Named Struct/Enum function inputs/results and event payloads now retain nominal
  identity through nested calls, queued delivery, Delay and checkpoint restoration.
  Signature editors validate defaults, migrate local call/handler ports and
  preserve graph wires through compatible renames/reorders. Unsupported collection types and recursive
  struct definitions are rejected during validation.
- `Sort {label} Array`, `Filter {label} Array` and `Map {label} Array` require a
  pure callback with signatures `(T)->float`, `(T)->bool` and `(T)->T`. Both
  interpreter and generated C++ paths snapshot the input before callbacks run.
  These signatures also apply to Struct/Enum arrays. Nominal collection types
  appear in variable, function and event type selectors; exact compatible-port
  search retains the declared element type. Type/field/enum-label refactors migrate
  collection contents and signatures together, including inactive project scenes.
- Array indices are integers, zero-based and checked. Insert accepts the end
  position; Get/Set/Remove require an existing item. Find returns `-1` when absent.
  Map Get reports a missing key; Has Key permits an explicit branch. Map Remove
  of a missing key leaves the map unchanged. Keys and Values share sorted key order.
- For Each takes one snapshot of its input array, map or set when execution enters the
  node. A set snapshot keeps insertion order, so `For Each Integer Set` over
  `[3, 1, 2]` visits `3`, `1`, then `2`. Item and Index are available only in
  that node's Body, including nested bodies. Map iteration follows sorted string-key
  order and exposes `Key`, `Item` and `Index`; array/set iteration exposes `Item`
  and `Index`.
  Changes to the source variable do not alter that traversal. Done also runs for an
  empty array. Nested loops have independent local bindings and use the shared
  instruction budget in interpreted and compiled execution.
- Integer math detects overflow. Truncate to Integer rounds toward zero and
  rejects out-of-range floats; Integer to Float is explicit and can round values
  beyond double's exact integer precision. No implicit wire conversion occurs.
- Split preserves empty fields and trailing fields. Split/Replace reject empty
  separators/search text. Unicode and embedded NUL survive literal code generation,
  typed storage and native JSON output. Format Float uses locale-independent JSON
  number formatting; Format Integer preserves all signed 64-bit digits.
- A collection is limited to 65,536 elements and a string to 1 MiB of UTF-8 bytes.
  Variables have nonempty names of at most 512 UTF-8 bytes, without NUL.

Python validation and IR lowering are in `editor/core/data_types.py` and
`compiler.py`. C++ value conversion is in `values.hpp` / `values.cpp`; typed storage
and functions are in `runtime.hpp` / `collections.hpp`. Codegen emits typed native
calls and ordinary loops; there is no Python game interpreter.

## Runnable example and evidence

~~~powershell
.\.venv\Scripts\python.exe -m editor.main examples\collections_demo\project.json
~~~

On Start sums the integer map's quantities and prints `Vật phẩm: 12`. On Update
iterates the entity array and rotates both robots at 45 degrees/second. Editing
the array to contain only `player` makes only the left robot rotate after reset.
The model is the previously verified Blockbench MCP robot. The example can be
recreated in a new directory with `tools/create_collections_demo.py --output PATH`.

`tools/verify_collections_workflow.py` passed 21 actual Qt/native checks, including
editing cells and the type dropdown, runtime reload, undo, cancellation, typed
entity targeting, GUI build, save/reopen and standalone execution. After 120
deterministic frames both robots have `[0, 90, 0]` rotation, inventory total is 12,
and preview/export have identical state and byte-identical GPU images.

Evidence: `artifacts/validation/collections-workflow-checks.json`,
`typed-variables.png`, `collections-editor.png`, and `collections-*-120.*`.
Native golden tests additionally exercise all six element types through array/map
operations, non-aliasing, nested traversal with source mutation, string/64-bit
roundtrips, invalid indices/keys, integer overflow and dynamic-name type errors.
The typed set parity probe covers duplicate suppression, insertion order, removal,
Contains, Length, Clear and preview/generated-game equality.

The subsequent [function milestone](functions.md) adds typed pure/action functions.
Events/timers and [seeded random](random.md), including typed uniform/weighted
selection and array shuffling, now have shared native nodes.
Seeded box vectors and uniform sphere directions are also available.
Debugger watches and richer callback graph interfaces remain open. Play now checks
native build fingerprints and rebuilds
if neither the project nor shared engine runtime matches the current sources.

The nominal collection follow-up has **58 passing Python/editor cases** in
`.work/user-collections-resumed-python.log`. The actual Qt dialog proof in
`.work/user-collections-final-proof/checks.json` covers type creation, collection
variable selection, node runtime-code inspection, editable C++ with Ctrl+S,
Undo/Redo, type/field rename, Save/Reopen and export (**8/8 checks**).
The saved project then passes **27 four-host checks** in
`.work/user-collections-four-host/checks.json`: transformed collection values and
the authored hook match across Preview/Game and both graphical hosts. GPU images
match; this collection fixture is not a visual/gameplay pipeline acceptance test.
Reproduce it with `tools/verify_user_collections_editor.py`, build its saved .nen
using `tools/build.ps1 -Project PATH`, then run
`tools/verify_user_collections_native.py --project PATH --output DIRECTORY`.
