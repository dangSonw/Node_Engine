"""Validation and previews for code embedded in graph nodes.

The graph stores an optional ``code`` field on a node.  The field is an
integration hook for action nodes: the generated runtime call remains the
default, while an author may add C++ statements before it or use the
``{{call}}`` marker to place the generated call inside a small wrapper.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


MAX_EMBEDDED_CODE_BYTES = 64 * 1024
CALL_MARKER = "{{call}}"
ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class CodeDiagnostic:
    line: int
    message: str


def cpp_code_mask(value: str) -> tuple[str, list[CodeDiagnostic]]:
    """Keep code positions while hiding comments and C++ string contents."""
    masked = list(value)
    diagnostics = []
    i = 0
    while i < len(value):
        start = i
        if value.startswith('//', i):
            end = value.find('\n', i)
            i = len(value) if end < 0 else end
        elif value.startswith('/*', i):
            end = value.find('*/', i + 2)
            if end < 0:
                diagnostics.append(CodeDiagnostic(value.count('\n', 0, i) + 1, 'Unterminated block comment'))
            i = len(value) if end < 0 else end + 2
        elif value.startswith('R"', i) and (raw := re.match(r'R"([^\s()\\]{0,16})\(', value[i:])):
            end = value.find(')' + raw[1] + '"', i + raw.end())
            if end < 0:
                diagnostics.append(CodeDiagnostic(value.count('\n', 0, i) + 1, 'Unterminated raw string literal'))
            i = len(value) if end < 0 else end + len(raw[1]) + 2
        elif value[i] in "'\"":
            # An apostrophe between digits is a C++ numeric separator.
            number = re.search(r"[A-Za-z0-9_']+$", value[:i]) if value[i] == "'" else None
            if number and number[0][0].isdigit() and i + 1 < len(value) and value[i + 1].isalnum():
                i += 1
                continue
            quote = value[i]
            i += 1
            while i < len(value) and value[i] != quote:
                if value[i] == '\\':
                    i += 1
                elif value[i] == '\n':
                    break
                i += 1
            if i < len(value) and value[i] == quote:
                i += 1
            else:
                diagnostics.append(CodeDiagnostic(value.count('\n', 0, start) + 1, 'Unterminated string or character literal'))
        else:
            i += 1
            continue
        for j in range(start, min(i, len(value))):
            if value[j] != '\n':
                masked[j] = ' '
    return ''.join(masked), diagnostics


def render_embedded_code(value: str, call: str) -> tuple[str, bool]:
    mask, _ = cpp_code_mask(value)
    index = mask.find(CALL_MARKER)
    if index < 0:
        return value, False
    return value[:index] + call + value[index + len(CALL_MARKER):], True


def validate_embedded_code(value: object, *, editable: bool = True) -> list[CodeDiagnostic]:
    """Return diagnostics for an embedded C++ snippet.

    This is deliberately a small editor-side guard.  The C++ compiler remains
    authoritative for type and symbol errors after export.  Includes, pragmas,
    entry points and namespace directives are rejected because a node snippet
    belongs inside the generated function body.
    """
    if value in (None, ""):
        return []
    if not isinstance(value, str):
        return [CodeDiagnostic(1, "Embedded code must be text")]
    if not editable:
        return [CodeDiagnostic(1, "This node exposes generated code as read-only")]
    if "\x00" in value:
        return [CodeDiagnostic(1, "Embedded code cannot contain NUL characters")]
    if len(value.encode("utf-8")) > MAX_EMBEDDED_CODE_BYTES:
        return [CodeDiagnostic(1, f"Embedded code exceeds {MAX_EMBEDDED_CODE_BYTES // 1024} KiB")]
    mask, diagnostics = cpp_code_mask(value)
    if mask.count(CALL_MARKER) > 1:
        return [CodeDiagnostic(1, f"Use {CALL_MARKER} at most once")]
    stack: list[tuple[str, int]] = []
    pairs = {"}": "{", ")": "(", "]": "["}
    line = 1
    for raw_line in mask.splitlines() or [""]:
        stripped = raw_line.strip()
        if re.search(r'\busing\s+namespace\b|\b(?:int|void)\s+main\s*\(', stripped):
            diagnostics.append(CodeDiagnostic(line, "Includes, pragmas, entry points and namespace directives are not allowed here"))
        if stripped.startswith("#"):
            diagnostics.append(CodeDiagnostic(line, "Preprocessor directives are not allowed inside a node"))
        i = 0
        while i < len(raw_line):
            char = raw_line[i]
            if char in "{([":
                stack.append((char, line))
            elif char in "})]":
                if not stack or stack[-1][0] != pairs[char]:
                    diagnostics.append(CodeDiagnostic(line, f"Unmatched '{char}'"))
                else:
                    stack.pop()
            i += 1
        line += 1
    diagnostics.extend(CodeDiagnostic(open_line, f"Unclosed '{char}'") for char, open_line in reversed(stack))
    return diagnostics


def default_node_code(spec) -> str:
    """Return the generated C++ call shown when a node has no override."""
    if spec.collection_type and spec.kind in ('pure','action'):
        args=', '.join(f'input_{i} /* {p.name}: {p.type} */' for i,p in enumerate(spec.data_inputs))
        call=f'rt::DispatchUserCollection(ctx, {spec.id}, std::vector<rt::Value>{{{args}}})'
    elif spec.function:
        args = (["ctx"] if spec.context else []) + [f"input_{i} /* {p.name}: {p.type} */" for i, p in enumerate(spec.data_inputs)]
        call = f"rt::{spec.function}({', '.join(args)})"
    else:
        call = f"/* {spec.name}: generated by the graph compiler */"
    if spec.kind == "action":
        return call + ";"
    if spec.kind == "action_result":
        return "auto result = " + call + ";"
    if spec.kind in ("pure", "pure_call", "select"):
        return "auto value = " + call + ";"
    return "// " + spec.name + " is lowered by the graph compiler."


def embedded_code_for(node, spec) -> tuple[str, bool]:
    """Return (text, editable) for a graph node."""
    custom = node.get_property("embedded_code") if node is not None else ""
    editable = spec.kind in ("action", "action_result") and bool(spec.function)
    return (custom or (CALL_MARKER if editable else default_node_code(spec)), editable)


_COMPILER_DIAGNOSTIC = re.compile(r'node-code:(.+):(\d+):(\d+):\s*(fatal error|error|warning|note):\s*(.*)')


def parse_compiler_diagnostic(line: str) -> dict | None:
    match = _COMPILER_DIAGNOSTIC.search(line.rstrip('\r\n'))
    if not match:
        return None
    node, row, column, severity, message = match.groups()
    return dict(node=node, line=int(row), column=int(column), severity=severity, message=message)


def generated_node_code(ir, node_id, spec) -> tuple[str, int]:
    """Show real generated code with its surrounding execution scope."""
    from .codegen import CppEmitter, cpp_string, quoted
    lines = CppEmitter().generate(ir).splitlines()
    lines = ['// CompiledProgram JSON omitted from this view.' if 'rt::Json CompiledProgram()' in line else line for line in lines]
    tick = f'rt::Tick(ctx, {quoted(node_id)});'
    event_functions = dict(start='OnStart', update='OnUpdate', fixed_update='OnFixedUpdate',
                           late_update='OnLateUpdate', quit='OnQuit', scene_loaded='OnSceneLoaded')
    event = event_functions.get(getattr(spec, 'event', None))
    for i, line in enumerate(lines):
        if tick in line or (event and line.startswith(f'void {event}(')) or ('rt::Bind' in line and cpp_string(node_id) in line):
            return '\n'.join(lines), i + 1
    text = '// This node has no separate emitted C++ body in the current graph.\n' + default_node_code(spec)
    return text, 1


def runtime_source_excerpt(spec, context_lines: int = 4, max_lines: int = 240) -> str:
    """Find the implementation used by a builtin node for the code viewer."""
    function = getattr(spec, "function", "").split('<')[0]
    if spec.collection_type:
        function='ApplyUserArrayCallback' if spec.kind=='collection_callback' else 'IterationValues' if spec.kind=='foreach' else 'DispatchUserCollection'
    if not function:
        return "// This node is lowered by the graph compiler; it has no single runtime function."
    pattern = re.compile(rf"\b{re.escape(function)}\s*\(")
    candidates = [ROOT / "runtime" / "include" / "runtime.hpp"]
    candidates += sorted((ROOT / "runtime" / "src").glob("*.cpp"))
    candidates += [ROOT / "runtime" / "generated" / "adapters.generated.cpp"]
    for path in candidates:
        try:
            source = path.read_text("utf-8")
        except (OSError, UnicodeError):
            continue
        masked, _ = cpp_code_mask(source)
        for match in pattern.finditer(masked):
            start_paren = masked.index('(', match.start())
            depth = 1
            close = start_paren + 1
            while close < len(masked) and depth:
                depth += (masked[close] == '(') - (masked[close] == ')')
                close += 1
            boundary = re.search(r'[;{]', masked[close:])
            if depth or boundary is None or boundary[0] != '{':
                continue
            brace = close + boundary.start()
            if ')' in masked[close:brace] or '=' in masked[close:brace]:
                continue
            depth, end = 1, brace + 1
            while end < len(masked) and depth:
                depth += (masked[end] == '{') - (masked[end] == '}')
                end += 1
            lines = source.splitlines()
            first_line = source.count('\n', 0, match.start())
            start = max(0, first_line - context_lines)
            last = source.count('\n', 0, end) + 1
            stop = min(last, first_line + max_lines)
            note = '\n// … implementation continues in the source file.' if stop < last else ''
            return f"// Source: {path.relative_to(ROOT).as_posix()}:{start + 1}\n" + "\n".join(lines[start:stop]) + note
    return f"// Runtime implementation for {function} was not found in the workspace."

