# Reusable function graphs

Functions are scene-owned typed graphs stored in the optional `functions` array
of the gameplay JSON document. Old version-one graphs still load without it.
Function Input/Output use stable builtin IDs 6001/6002; each call uses its function's
persisted integer ID from 1,000,000 through 2,147,483,647. Renaming a definition in
the document does not retarget calls. Function names never become C++ identifiers.
The builtin registry contains concrete definitions; scene functions add
their own call definitions from their signatures.

## Authoring

Use **Graph > New Function…** to enter a name, choose Pure or Action, and add typed
input/output ports. The signature editor supports all 40 existing value types.
Input defaults use JSON. Saving the subsequent graph editor creates the function;
cancelling either dialog leaves the project untouched. **Graph > Edit Function
Signature…** changes an existing signature, as described below. **Graph > Extract
Function…** creates a reusable function from selected nodes. Function deletion
remains future work.

Functions appear in category 06 of the node library and quick-add search. Add a
call just like a builtin node. Double-click the **body** of a call to open its
function graph; the title retains NodeGraphQt's label-edit behavior. **Graph >
Edit Function…** also opens a definition without a call site. The function graph
dialog has its own library, inspector and undo/redo. Double-click nested calls or
use the graph chooser to navigate; the breadcrumb identifies the active graph.
Enter commits an input field without saving/closing the editor.

**Save** applies all edited function bodies as one gameplay undo step. **Cancel**
discards them. Applying, undoing or redoing a function edit resets the native
scene; a paused preview stays stopped, while a running preview resumes only after
successful IR reload. Ordinary gameplay nodes and their undo history are retained.
Function definitions, body positions, stable call IDs and typed wires survive
project save/reopen. Runtime Problems entries with `function-id/node-id` open the
corresponding function graph.

## Execution rules

- Pure functions have at least one result, exactly one Function Input and one
  Function Output. They may use their parameters, context-free pure builtin nodes,
  and other pure functions. Scene reads, time/input reads and actions are rejected.
  Results are evaluated lazily when consumed, so multiple consumers may evaluate
  the pure function again; there is no hidden mutable cache.
- Action functions have exec In/Out on calls. Their Function Input starts the
  body; Function Output returns immediately, including from nested loops/branches.
  Functions with results must return on every execution path. A function with no
  results may fall through. Multiple input/output values are passed by value.
- Action result pins become available on that call's Out path, including nested
  branches/loops reached from it. Reading a result before execution or outside
  its loop/branch scope is rejected at compilation.
- Each call has an isolated parameter/local frame. Calling a function inside For
  Each preserves the caller's Item/Index and prior call results. Scene variables
  and entity state remain shared, so action functions can mutate game state.
- Break Loop and Continue Loop apply only to a loop Body in the current action
  function. They cannot control the caller's loops. Return still leaves the
  entire function. See [flow-control.md](flow-control.md).
- Do Once/Do N/Gate/Flip Flop/Multi Gate keep state per qualified function/node ID and Owner,
  shared across calls. Set Owner to an entity for independent instance state;
  an empty Owner shares scene-wide state. Counter/Is A/Index stay inside the emitted
  branch. These stateful nodes are not valid in pure functions.
- Nested calls share the existing instruction budget. Both backends cap call
  depth at 128 and report errors with qualified source node IDs. Recursive call
  cycles are currently rejected before preview/export.
- Signature limits: 256 definitions per scene, 32 inputs and 32 outputs per
  function. Port names are identifiers; `In`/`Out` are reserved. Connections never
  silently coerce types.

The compiler builds a function table in IR; the native interpreter executes call
frames and propagates returns through structured flow. C++ export emits typed
functions returning `std::tuple<...>`, ordinary calls and native return statements.
Both paths still use the same runtime node functions. There is no Python game
interpreter or duplicated arithmetic/entity behavior in templates.

## Example and verification

~~~powershell
.\.venv\Scripts\python.exe -m editor.main examples\functions_demo\project.json
~~~

Two calls to **Spin Robot** use the same action function with different target and
speed arguments. Spin Robot calls the pure **Rotation Delta** function. The left
robot turns 45 degrees/second, the right -90; the action's rotation result is saved
to a typed vector variable. At 120 deterministic frames they reach `[0,90,0]` and
`[0,-180,0]`. `tools/create_functions_demo.py --output PATH` recreates this example
in a fresh folder without replacing existing user projects.

`tools/verify_functions_workflow.py` performs 26 real Qt/native checks, including
mouse double-click navigation, input fields, typed signature creation, creating
and executing a new Triple function, live reset/undo/redo/cancel, GUI build,
save/reopen, and preview/compiled state and GPU equality. Canvas wires in the test
are connected through the domain adapter; this does not certify physical mouse
wire dragging. The test's added Triple function returns integer 21 for input 7.

Evidence: `artifacts/validation/functions-workflow-checks.json`,
`functions-preview-120.*`, `functions-compiled-120.*`, `function-signature.png` and
`function-graph.png`. `tools/verify_function_embedding.py` additionally captures
the desktop compositor before and after modal editing, proving that the native
robot viewport remains visible. Widget/window-only screenshots may omit the
foreign SDL child; use `functions-desktop-after.png` for the actual composed UI.

Native tests cover all 40 parameter/result types, Unicode/NUL/large integers,
nested calls, early return from loops, local isolation, qualified errors and
shared budgets. Compile-time cases reject impurities, recursion, missing returns,
unknown functions, incompatible types and use of results before execution.

## Runtime freshness and remaining work

Successful GUI and PowerShell builds record `build/runtime-build.json` with hashes
of native sources, shaders, registry and the preview binary. Play checks the local
build, then the shared engine build, and starts a build if neither matches. A
changed binary, changed native source or missing stamp cannot silently use an old
interpreter. Sources changed during compilation reject the new stamp. This is
freshness validation, not a shared compiled-library cache across projects.

Future function work includes general macros and broader extraction boundaries,
deletion/refactoring tools, local variables, recursion policy, interfaces,
overrides and callbacks/delegates. Custom events/timers, Flecs, renderer expansion
and the wider engine catalogue remain in the active goal.

Action functions can now suspend on Delay, Wait Until and Retriggerable Delay.
Their captured parameters, scoped action outputs, loop progress and caller stack
resume through both native paths and whole-game Save/Load. Pure functions still
reject latent nodes. See [flow-control.md](flow-control.md) for reentry, ordering,
owner lifetime and resource limits.

Switch Integer/String can be authored inside action functions, including editing
cases from the function Inspector. Every case and Default must return when the
function has results. Select's 40 typed variants are also available in pure
functions and evaluate only the selected expression. Suspended Switch branches
retain their choice and caller state across Save/Load.

## Editing signatures

Select a function call and choose **Graph > Edit Function Signature…**, or use
the same command with no call selected to search definitions. Rename the function
or its input/output ports, change their order with **Move up/down**, add ports,
or change types/defaults. Pure versus Action stays fixed; create another function
to change that kind.

**Apply** validates a complete candidate before changing the scene's gameplay
graph, all nested callers and Function Input/Output nodes. Function IDs, call
IDs, positions, custom labels, literal values and wires remain associated with
the original ports, even when names are swapped or ports are reordered. All
changes form one Undo step. Earlier node edits still undo/redo correctly; a
failed canvas application rolls the migration back. Cancel or unchanged Apply
does not add a migration step. Library entries and new call nodes use the current
signature. Saving and reopening preserves the migration.

Connected ports cannot be removed. Removing a port with a non-default literal,
including a Function Output literal, is also rejected: disconnect/reset it first.
A type change must leave every body/caller wire and authored literal valid. An
incompatible old default may reset to the new typed default; non-default values
are not silently converted. Changing an input default preserves values captured
by existing calls; calls created afterward use the new default. New ports receive
their declared/type default. The dialog keeps validation errors visible so the
edit can be corrected or cancelled.

Signatures belong to one scene. Editing one does not change another scene's
independent definition, even if IDs coincide. Applying, undoing or redoing reloads
an available native preview from its initial state: a running preview resumes;
a paused/stopped preview stays stopped. It does not migrate a live suspended
invocation or an older whole-game save into a changed program. Save compatibility
continues to require matching program/resource identity.

`examples/function_signature_demo/project.json` is the actual editor-authored
two-robot example after migration. **Turn Robot** calls **Angular Step** through
renamed/reordered ports. Existing rates remain 60 and -90 degrees/second although
new calls default to 6. After 120 fixed frames the rotations are `[0,120,0]` and
`[0,-180,0]`. `artifacts/demos/function-signatures/Play.cmd` runs the compiled game
without Python/Qt. Evidence: `artifacts/validation/function-signatures/` and
`function-signatures-*.xml`; verification scripts are
`tools/verify_function_signature_editor.py` and
`tools/verify_function_signature_export.py`. The native tests cover all 40 renamed
and reordered parameter/result types, nested calls, compatible type changes and
fresh-process Save/Load of a delayed invocation in the migrated program.

## Extracting a selection

Select nodes in Gameplay and choose **Graph > Extract Function…**. The function
graph editor has an **Extract Function…** button for selections inside an existing
function. Review the inferred kind, typed ports and copied/retained data nodes,
enter a name, then choose **Extract**. Cancel leaves the document untouched.
The selected nodes are replaced by a call; the new definition is immediately
available in the Library and function navigator. The existing signature editor
can rename/reorder the inferred ports afterward.

Literal inputs on selected nodes become editable call arguments. Incoming values
already captured by an event, loop, action or Function Input become typed parameters.
Upstream pure expressions are copied into the body, keeping their evaluation at
the point of use. This includes reads that must change after a write or Delay,
and a lazy Select branch whose unused expression could fail. An action extraction
keeps data-expression nodes in the caller when outside consumers need them later;
their captured action inputs are rewired through typed results. The review lists
such copies and retained nodes explicitly.

An action region needs one execution entry and at most one outside continuation.
Complete loops, Sequence paths, nested calls and Delay are supported. Branch/Gate
paths that stop early generate a `Continue` result and a caller-side Branch, so
the following graph only runs when the original path would reach it. A Sequence
inside the new function provides the false fallback without reading unavailable
action results. These helper nodes are editable and participate in the same Undo
step. Stateful flow identities now belong to the extracted function; the existing
function/Owner state-sharing rules apply if the call is reused.

Each extraction is one Undo step and preserves earlier node edits. Function graphs
share an Undo history across navigation, including when the current definition is
removed by Undo. Saving the function editor applies all its changes to Gameplay
as one outer Undo step. Preview is reloaded using the existing paused/running
policy. Save/reopen and new calls retain the extracted definitions and wiring.

Rejected boundaries include event/Function Input/Output entries, separate execution
entries/exits, a partial loop Body or Sequence First path, and a shared tail that
would introduce an early return. A pure extraction currently requires one exposed
result and context-free computation; this prevents evaluating independent unused
outputs eagerly. Include the consuming actions when extracting scene reads.
The existing limits of 32 inputs/results and 256 definitions per scene apply.
General macros, arbitrary multi-entry/multi-exit collapse and extraction of
independent multiple pure results remain open; existing manually authored pure
functions still support multiple outputs. Refactoring does not migrate old runtime
state or game saves to a changed program.

`examples/function_extraction_demo/project.json` was authored through the actual
dialogs. Three Gameplay nodes become **Spin Pair**; **Angular Product** is extracted
inside Rotation Delta and reused by both robots. At 120 fixed frames their rotations
remain `[0,90,0]` and `[0,-180,0]`. Standalone launcher:
`artifacts/demos/function-extraction/Play.cmd`. Evidence and scripts:
`artifacts/validation/function-extraction/`, `function-extraction-*.xml`,
`tools/verify_function_extraction_editor.py` and
`tools/verify_function_extraction_export.py`.


## Named Struct and Enum ports

Signature editors also accept declared `struct:Name` and `enum:Name` types.
Defaults and payloads must match the declaration, including nested field types
and enum labels. Compatible local signature/type refactors migrate call/handler
ports, literals and wires with shared Undo and saved-project persistence.
Both native hosts preserve nominal identities through nested function calls,
queued events and delayed execution. Checkpoint frames and pending payloads
are schema-validated before commit; a corrupted nominal tag or field value
rejects restoration transactionally. Existing 32-port signature limits apply.
Project-wide type refactors synchronize these signatures across scenes; see
[project-types.md](project-types.md). User-defined collection elements remain
open. See [typed-data.md](typed-data.md) and the validation report.
