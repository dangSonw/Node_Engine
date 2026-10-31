# Node Code Editor

Select a graph node and use **View / Edit Node Code…** in the Inspector or Graph
menu, or press **Ctrl+Alt+C**. Function graphs offer the same control. The dialog
has separate tabs for the editable hook, generated C++ and runtime implementation.
For a valid graph, the generated view shows actual input expressions and the
surrounding event/condition/function body, positioned at the selected node.
For an invalid graph it shows the validation problem and signature preview,
so code editing remains available. The dialog shows the C++ call emitted for
the selected node and a read-only excerpt of the runtime implementation used
by that call. Action and action-result nodes also expose an editable embedded
code hook.

Use **C++ Code** (ID 27006, Debug & Profiling) for a dedicated node to write C++.
Its default runtime call does nothing. The editor supplies line numbers,
four-space Tab/Shift+Tab, automatic indentation, text Undo/Redo and **Ctrl+S**.
Saving the dialog creates one graph property edit, with graph Undo/Redo support.

The hook is stored as the node's optional `code` field in the graph document,
so save/reopen, duplicate, copy/paste and undo keep it with the node. The
editor performs size, NUL, delimiter, entry-point, namespace and preprocessor
checks before accepting the text. The native C++ compiler remains responsible
for symbol and type checking during Build.

Hooks are compiled into `generated/node-code.generated.cpp`, linked into Preview,
Game and both graphical hosts. All four execute the same callback, including
action-result and resumed Delay/Wait Until instructions. Changed or missing
compiled hooks require a rebuild; they are never silently ignored. Play rebuilds
when the project's hook fingerprint differs from the built executable.

The callback exposes `ctx` and read-only `input_0`, `input_1`, … in data-port order.
For action-result nodes, `result` is available after `{{call}}` (a tuple when the
node has several outputs). Each snippet gets its own scope.

Snippets run before the normal runtime call. Use `{{call}}` once to place that generated
call inside a wrapper; for example:

```cpp
{
    // code written in the node editor
    {{call}}
}
```

For example, on Set Time Scale, `{{call}}` followed by
`ctx.time_scale = input_0 * 0.5;` applies half the input scale in both Preview and
Game. On C++ Code, `rt::SetTimeScale(ctx, 0.25);` needs no marker.

Without the marker, the normal runtime call is emitted after the snippet.
Pure nodes and event declarations show their generated lowering read-only;
their behavior remains owned by the shared runtime and graph compiler.

Editor validation understands multiline comments, raw strings and numeric
separators. It is a structural check; Build runs the actual C++ compiler.
Clang errors carry the originating scene/node and snippet line. Activate an entry
in **Problems** to focus the graph and open the code editor at that line/column.
Errors in ordinary generated graph code still use the existing graph navigation.

Open `examples/embedded_code_demo/project.json` for a rotating/moving robot with
dedicated C++ nodes and a Set Position hook.

The feature is intentionally scoped to node body integration. It does not
allow includes, pragmas, a second entry point or namespace directives, and it
does not turn the graph into an arbitrary Python or JavaScript execution host.

