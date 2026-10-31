"""Generate calls into the shared typed runtime, never duplicate node behavior."""
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from .document import write_text_if_changed, save_json
from .registry import Registry, ROOT
from .data_types import SCALARS, INT_MIN
from .functions import scoped_registry
from .user_collections import is_user_collection

class _CppTypes(dict):
    def __missing__(self, key):
        if is_user_collection(key):
            value = 'rt::UserCollectionValue'
        elif key.startswith('struct:'):
            value = 'rt::StructValue'
        elif key.startswith('enum:'):
            value = 'rt::EnumValue'
        elif key.startswith('array<'):
            value = f'rt::Array<{self[key[6:-1]]}>'
        elif key.startswith('map<'):
            value = f'rt::Map<{self[key[4:-1]]}>'
        elif key.startswith('set<'):
            value = f'rt::Set<{self[key[4:-1]]}>'
        else:
            raise KeyError(key)
        self[key] = value
        return value

CPP_TYPES = _CppTypes({"float": "double", "int": "std::int64_t", "bool": "bool", "string": "std::string", "entity": "rt::EntityRef", "vec2": "rt::Vec2", "vec3": "rt::Vec3", "vec4": "rt::Vec4", "quat": "rt::Quat", "mat4": "rt::Mat4"})
CPP_TYPES.update({f'{kind}<{t}>': f'rt::{kind.title()}<{CPP_TYPES[t]}>' for kind in ('array', 'map', 'set') for t in SCALARS})
ENV = Environment(loader=FileSystemLoader(ROOT / "templates"), undefined=StrictUndefined,
                  trim_blocks=True, lstrip_blocks=True, autoescape=False,
                  variable_start_string="<<", variable_end_string=">>")


def quoted(s):
    # JSON's \\u0000 spelling is not a valid C++ universal character escape.
    # Fixed-width octal escapes also avoid consuming following hexadecimal digits.
    return '"' + ''.join(f'\\{ord(c):03o}' if ord(c) < 32 or ord(c) == 127
                         else json.dumps(c, ensure_ascii=False)[1:-1] for c in str(s)) + '"'


def cpp_string(value):
    return f'std::string({quoted(value)}, {len(value.encode("utf-8"))})'


def cpp_literal(expr):
    v, t = expr["value"], expr["type"]
    if is_user_collection(t):
        return f'rt::UserCollectionValue{{{cpp_string(t)}, rt::Json::parse({quoted(json.dumps(v,ensure_ascii=False,separators=(",", ":")))})}}'
    if t.startswith('struct:'):
        return f'rt::StructValue{{{cpp_string(t)}, rt::Json::parse({quoted(json.dumps(v, ensure_ascii=False, separators=(",", ":")))})}}'
    if t.startswith('enum:'):
        return f'rt::EnumValue{{{cpp_string(t)}, {cpp_string(v)}}}'
    if t == "float":
        return repr(float(v))
    if t == 'int':
        return 'std::numeric_limits<std::int64_t>::min()' if v == INT_MIN else f'std::int64_t{{{v}LL}}'
    if t == "bool":
        return "true" if v else "false"
    if t in ("vec2", "vec3", "vec4"):
        return CPP_TYPES[t] + "{" + ",".join(repr(float(x)) for x in v) + "}"
    if t == "quat":
        return CPP_TYPES[t] + "{" + ",".join(repr(float(x)) for x in (v[3], v[0], v[1], v[2])) + "}"
    if t == "mat4":
        columns = ["rt::Vec4{" + ",".join(repr(float(x)) for x in v[i:i + 4]) + "}" for i in range(0, 16, 4)]
        return CPP_TYPES[t] + "{" + ",".join(columns) + "}"
    if t.startswith(('array<', 'set<')):
        element = t[t.index('<') + 1:-1]
        return CPP_TYPES[t] + '{' + ','.join(cpp_literal({'type':element, 'value':x}) for x in v) + '}'
    if t.startswith('map<'):
        return CPP_TYPES[t] + '{' + ','.join('{' + cpp_string(k) + ',' + cpp_literal({'type':t[4:-1], 'value':v[k]}) + '}' for k in sorted(v)) + '}'
    if t == 'entity':
        return 'rt::EntityRef{' + cpp_string(v) + '}'
    return cpp_string(v)


def generate_adapters(registry=None):
    registry = registry or Registry()
    adapters, result_adapters = [], []
    for spec in sorted(registry.nodes.values(), key=lambda s: s.id):
        if spec.kind not in ("pure", "action", "action_result") or spec.component_id or spec.user_type:
            continue
        args = (["ctx"] if spec.context else []) + [
            f"std::get<{CPP_TYPES[p.type]}>(args.at({i}))" for i, p in enumerate(spec.data_inputs)]
        call = f"rt::{spec.function}(" + ", ".join(args) + ")"
        outputs = [p for p in spec.outputs if p.type != 'exec']
        if spec.kind == 'action_result' and len(outputs) > 1:
            result_adapters.append({'id': spec.id, 'count': len(spec.data_inputs), 'call': call,
                                    'result_values': ', '.join(f'std::get<{i}>(result)' for i in range(len(outputs)))})
            continue
        adapters.append({"id": spec.id, "count": len(spec.data_inputs),
                         "body": f"return {call};" if spec.kind in ("pure", "action_result") else f"{call}; return 0.0;"})
    from .input import BUTTONS, GAMEPAD_AXES, GAMEPAD_BUTTONS
    buttons = ','.join(cpp_string(key) for key in BUTTONS)
    return (ENV.get_template("adapters.cpp.j2").render(adapters=adapters, result_adapters=result_adapters) +
            '\nnamespace rt { bool IsInputButton(const std::string& button) {\n' +
            '    static const std::set<std::string> buttons = {' + buttons + '};\n' +
            '    return buttons.contains(button);\n}\n' +
            'const std::vector<std::string> GamepadAxisNames = {' + ','.join(cpp_string(x) for x in GAMEPAD_AXES) + '};\n' +
            'const std::vector<std::string> GamepadButtonNames = {' + ','.join(cpp_string(x) for x in GAMEPAD_BUTTONS) + '};\n}\n')


class CppEmitter:
    def __init__(self, registry=None):
        self.registry = registry or Registry()
        self.lines = []
        self.counter = 0
        self.indent = 0
        self.locals = {}
        self.parameters = []
        self.function_results=[]
        self.loop_depth = 0
        self.continuation_expr = False

    def line(self, text):
        self.lines.append("    " * self.indent + text)

    def unique(self, prefix="v"):
        self.counter += 1
        return f"{prefix}{self.counter}"

    def tick(self, node):
        self.line(f"rt::Tick(ctx, {quoted(node)});")

    def call(self, spec, args):
        if spec.collection_type:
            call=f'rt::DispatchUserCollection(ctx, {spec.id}, std::vector<rt::Value>{{{", ".join(args)}}})'
            return f'std::get<{CPP_TYPES[spec.outputs[0].type]}>({call})' if spec.kind=='pure' else call
        if spec.variable_type.startswith(('struct:', 'enum:')):
            owner = args[0] if spec.variable_scope == 'entity' else 'rt::EntityRef{}'
            offset = 1 if spec.variable_scope == 'entity' else 0
            prefix = f'ctx, {cpp_string(spec.variable_type)}, {cpp_string(spec.variable_scope)}, {owner}, {args[offset]}'
            if spec.variable_access == 'get':
                return f'std::get<{CPP_TYPES[spec.variable_type]}>(rt::GetUserVariable({prefix}))'
            return f'rt::SetUserVariable({prefix}, {args[offset+1]})'
        if spec.component_id:
            cid, field, op = spec.component_id, spec.component_field, spec.component_operation
            if op == 'query':
                return f'rt::FindEntitiesWithComponent(ctx, {cid}, {args[0]})'
            prefix = f'ctx, {args[0]}, {cid}'
            if op in ('get', 'set'):
                t = spec.outputs[0].type if op == 'get' else spec.data_inputs[1].type
                fn = 'GetComponentProperty' if op == 'get' else 'SetComponentProperty'
                return f'rt::{fn}<{CPP_TYPES[t]}>({prefix}, {field}' + (f', {args[1]}' if op == 'set' else '') + ')'
            fn = {'add':'AddComponent','remove':'RemoveComponent','has':'HasComponent','enable':'SetComponentEnabled','enabled':'IsComponentEnabled'}[op]
            return f'rt::{fn}({prefix}' + (f', {args[1]}' if op == 'enable' else '') + ')'
        args = (["ctx"] if spec.context else []) + args
        return f"rt::{spec.function}(" + ", ".join(args) + ")"

    def embedded_code(self, code, node, default_call=None):
        """Emit a validated node integration snippet inside the generated body."""
        if not code:
            return False
        from .node_code import render_embedded_code
        rendered, used_call = render_embedded_code(code, default_call or '')
        self.line(f'// embedded node code:{node}')
        self.line(f'#line 1 {quoted("node-code:" + node)}')
        for line in rendered.splitlines() or ['']:
            self.line(line)
        self.line(f'#line 1 {quoted("node:" + node)}')
        return used_call

    def embedded_call(self, statement, args):
        return (f'rt::RunNodeCode(ctx, {statement["type"]}, {cpp_string(statement["node"])}, '
                f'{cpp_string(statement["code"])}, std::vector<rt::Value>{{{", ".join(args)}}})')

    def expr(self, expression):
        if expression["op"] == "literal":
            return cpp_literal(expression)
        if expression['op'] == 'local':
            if self.continuation_expr:
                return f'std::get<{CPP_TYPES[expression["type"]]}>(ctx.locals.at({{{cpp_string(expression["node"])}, {cpp_string(expression["port"])}}}))'
            return self.locals[expression['node'], expression['port']]
        if expression['op'] == 'parameter':
            if self.continuation_expr:
                return f'std::get<{CPP_TYPES[expression["type"]]}>(ctx.parameters.at({expression["index"]}))'
            return self.parameters[expression['index']]
        if expression['op'] == 'select':
            condition = self.expr(expression['args'][0])
            self.tick(expression['node'])
            result = self.unique('selected')
            t = CPP_TYPES[self.registry[expression['type']].outputs[0].type]
            self.line(f'auto {result} = rt::SelectValue({condition}, [&]() -> {t} {{')
            self.indent += 1
            yes = self.expr(expression['args'][1]); self.line(f'return {yes};')
            self.indent -= 1
            self.line(f'}}, [&]() -> {t} {{')
            self.indent += 1
            no = self.expr(expression['args'][2]); self.line(f'return {no};')
            self.indent -= 1
            self.line('});')
            return result
        if expression['op'] == 'invoke':
            args = [self.expr(arg) for arg in expression['args']]
            self.tick(expression['node'])
            name = self.unique()
            self.line(f'auto {name} = std::get<{expression["index"]}>(Function_{expression["type"]}(ctx{", " if args else ""}{", ".join(args)}));')
            return name
        if expression['op'] == 'struct_make':
            args = [self.expr(arg) for arg in expression['args']]
            self.tick(expression['node'])
            name = self.unique('struct')
            self.line(f'auto {name} = rt::StructValue{{{cpp_string(expression["type"])}, rt::Json::object()}};')
            for field, value in zip(expression.get('fields', []), args):
                self.line(f'{name}.fields[{cpp_string(field)}] = rt::ToJson({value});')
            self.line(f'{name} = std::get<rt::StructValue>(rt::CheckedValueFromJson(ctx, {cpp_string(expression["type"])}, {name}.fields));')
            return name
        if expression['op'] == 'struct_get':
            value = self.expr(expression['args'][0])
            self.tick(expression['node'])
            name = self.unique('field')
            self.line(f'auto {name} = std::get<{CPP_TYPES[expression["type"]]}>(rt::ReadStructField(ctx, {value}, {cpp_string(expression["field"])}, {cpp_string(expression["type"])}));')
            return name
        if expression['op'] == 'enum_value':
            args = [self.expr(arg) for arg in expression['args']]
            self.tick(expression['node'])
            name = self.unique('enum')
            self.line(f'auto {name} = std::get<rt::EnumValue>(rt::CheckedValueFromJson(ctx, {cpp_string(expression["type"])}, {args[0]}));')
            return name
        if expression['op'] == 'collection_callback':
            items = self.expr(expression['args'][0])
            self.tick(expression['node'])
            element_cpp = CPP_TYPES[expression['type'][6:-1]]
            result = self.unique('callback_result')
            if is_user_collection(expression['type']):
                callback=expression['callback']
                self.line(f'auto {result} = rt::ApplyUserArrayCallback(ctx, {cpp_string(expression["mode"])}, {items}, [&](const rt::Value& item) -> rt::Value {{ return std::get<0>(Function_{callback}(ctx, std::get<{element_cpp}>(item))); }});')
                return result
            self.line(f'rt::Array<{element_cpp}> {result};')
            mode, callback = expression['mode'], expression['callback']
            if mode == 'SortArray':
                self.line(f'{result} = {items};')
                self.line(f'std::stable_sort({result}.begin(), {result}.end(), [&](const auto& left, const auto& right) {{')
                self.indent += 1
                self.line(f'return std::get<0>(Function_{callback}(ctx, left)) < std::get<0>(Function_{callback}(ctx, right));')
                self.indent -= 1
                self.line('});')
            elif mode == 'FilterArray':
                self.line(f'for (const auto& item : {items}) if (std::get<0>(Function_{callback}(ctx, item))) {result}.push_back(item);')
            else:
                self.line(f'for (const auto& item : {items}) {result}.push_back(std::get<0>(Function_{callback}(ctx, item)));')
            return result
        spec = self.registry[expression["type"]]
        args = [self.expr(arg) for arg in expression["args"]]
        self.tick(expression["node"])
        name = self.unique()
        self.line(f"auto {name} = {self.call(spec, args)};")
        return name

    def block(self, statements):
        for s in statements:
            self.line(f"// node:{s['node']} {self.registry[s['type']].name}")
            self.line(f'#line 1 {quoted("node:" + s["node"])}')
            op = s["op"]
            if op == 'continuation_entry':
                captures = ', '.join('{{' + cpp_string(p['node']) + ', ' + cpp_string(p['port']) + '}, ' + self.locals[p['node'], p['port']] + '}' for p in s['captures'])
                self.line(f'rt::StartContinuation(ctx, {s["entry"]}, rt::CapturedValues{{{captures}}});')
                continue
            if op == "while":
                self.line("while (true) {")
                self.indent += 1
                condition = self.expr(s["args"][0])
                self.tick(s["node"])
                self.line(f"if (!({condition})) break;")
                self.loop_depth += 1
                self.block(s["body"])
                self.loop_depth -= 1
                self.indent -= 1
                self.line("}")
                continue
            args = [self.expr(arg) for arg in s["args"]]
            self.tick(s["node"])
            if op == "action":
                call = self.embedded_call(s, args) if s.get('code') else self.call(self.registry[s['type']], args)
                self.line(call + ';')
            elif op in ('break', 'continue'):
                if not self.loop_depth:
                    raise ValueError(f'{op} outside a loop Body: {s["node"]}')
                self.line(op + ';')
            elif op == 'flow':
                result = self.unique('flow')
                arguments = ['ctx', cpp_string(s['node']), cpp_string(s['input']), *args]
                self.line(f'const auto {result} = rt::{self.registry[s["type"]].function}({", ".join(arguments)});')
                saved_locals = self.locals.copy()
                if s['type'] == 2008: self.locals[s['node'], 'Counter'] = result + '.count'
                if s['type'] == 2010: self.locals[s['node'], 'Is A'] = result + '.is_a'
                if s['type'] == 2011: self.locals[s['node'], 'Index'] = result + '.index'
                for index, body in enumerate(s['branches']):
                    self.line(f'if ({result}.branch == 0) {{' if index == 0 else 'else {' if s['type']==2010 else f'else if ({result}.branch == {index}) {{')
                    self.indent += 1
                    self.block(body)
                    self.indent -= 1
                    self.line('}')
                if not s['branches']: self.line(f'(void){result};')
                self.locals = saved_locals
            elif op == 'action_result':
                result = self.unique('result')
                call = self.call(self.registry[s["type"]], args)
                code = s.get('code', '')
                if code:
                    outputs = [p for p in self.registry[s['type']].outputs if p.type != 'exec']
                    self.line(f'auto {result} = {self.embedded_call(s, args)};')
                    for i, port in enumerate(s['outputs']):
                        self.locals[s['node'], port] = f'std::get<{CPP_TYPES[outputs[i].type]}>({result}.at({i}))'
                    continue
                else:
                    self.line(f'auto {result} = {call};')
                for i, port in enumerate(s['outputs']):
                    self.locals[s['node'], port] = result if len(s['outputs']) == 1 else f'std::get<{i}>({result})'
            elif op in ('emit_event','broadcast_event'):
                offset=2 if op=='emit_event' else 1
                fn='SendEvent' if op=='emit_event' else 'BroadcastEvent'
                payload='std::vector<rt::Value>{' + ', '.join(args[offset:]) + '}'
                self.line(f'rt::{fn}(ctx, {s["event"]}, ' + ', '.join(args[:offset]+[payload]) + ');')
            elif op in ('subscribe_event','unsubscribe_event'):
                self.line(f'rt::SetEventSubscription(ctx, {s["event"]}, {args[0]}, {"true" if op=="subscribe_event" else "false"});')
            elif op == 'return':
                for index,kind in enumerate(self.function_results):
                    if kind.startswith(('struct:','enum:')) or is_user_collection(kind):
                        checked=self.unique('result')
                        self.line(f'const auto {checked} = {args[index]};')
                        self.line(f'rt::ValidateTypedValue(ctx,{cpp_string(kind)},{checked});')
                        args[index]=checked
                self.line('return std::make_tuple(' + ', '.join(args) + ');')
            elif op == 'function_call':
                result = self.unique('results')
                self.line(f'auto {result} = Function_{s["type"]}(ctx{", " if args else ""}{", ".join(args)});')
                for i, port in enumerate(s['outputs']):
                    self.locals[s['node'], port] = f'std::get<{i}>({result})'
            elif op == 'switch':
                result = self.unique('route')
                cases = cpp_literal(dict(type='array<'+self.registry[s['type']].data_inputs[0].type+'>', value=s['cases']))
                self.line(f'const auto {result} = rt::SwitchBranch({args[0]}, {cases});')
                saved_locals = self.locals.copy()
                for index, body in enumerate(s['branches']):
                    self.line("{" if len(s["branches"])==1 else "else {" if index==len(s["branches"])-1 else f'{"if" if index==0 else "else if"} ({result} == {index}) {{')
                    self.indent += 1; self.locals = saved_locals.copy()
                    self.block(body)
                    self.indent -= 1; self.line('}')
                self.locals = saved_locals
            elif op == "branch":
                self.line(f"if ({args[0]}) {{")
                self.indent += 1
                self.block(s["yes"])
                self.indent -= 1
                self.line("} else {")
                self.indent += 1
                self.block(s["no"])
                self.indent -= 1
                self.line("}")
            elif op == "for":
                count, index = self.unique("count"), self.unique("i")
                self.line(f"const int {count} = rt::LoopCount({args[0]});")
                self.line(f"for (int {index}=0; {index}<{count}; ++{index}) {{")
                self.indent += 1
                self.tick(s["node"])
                self.loop_depth += 1
                self.block(s["body"])
                self.loop_depth -= 1
                self.indent -= 1
                self.line("}")
            elif op == 'foreach':
                values, index, item = self.unique('items'), self.unique('index'), self.unique('item')
                self.line(f'const auto {values} = {args[0]};')
                spec = self.registry[s['type']]
                is_map = spec.data_inputs and spec.data_inputs[0].type.startswith('map<')
                if spec.collection_type:
                    snapshot=self.unique('snapshot')
                    self.line(f'const auto {snapshot} = rt::IterationValues({values});')
                    if is_map:
                        keys=self.unique('keys'); self.line(f'const auto {keys} = rt::IterationKeys({values});')
                    self.line(f'for (std::int64_t {index}=0; {index}<static_cast<std::int64_t>({snapshot}.size()); ++{index}) {{')
                    item_type=next(p.type for p in spec.outputs if p.name=='Item')
                    self.line(f'const auto {item} = std::get<{CPP_TYPES[item_type]}>({snapshot}.at({index}));')
                    if is_map: self.locals[s['node'],'Key']=f'{keys}.at({index})'
                elif is_map:
                    keys, key = self.unique('keys'), self.unique('key')
                    self.line(f'const auto {keys} = rt::MapKeys({values});')
                    self.line(f'for (std::int64_t {index}=0; {index}<rt::ArrayLength({keys}); ++{index}) {{')
                    self.line(f'const auto {key} = rt::ArrayGet({keys}, {index});')
                    self.line(f'const auto {item} = rt::MapGet({values}, {key});')
                    self.locals[s['node'], 'Key'] = key
                else:
                    self.line(f'for (std::int64_t {index}=0; {index}<rt::ArrayLength({values}); ++{index}) {{')
                    self.line(f'const auto {item} = rt::ArrayGet({values}, {index});')
                self.indent += 1
                self.tick(s['node'])
                self.locals[s['node'], 'Item'] = item
                self.locals[s['node'], 'Index'] = index
                self.loop_depth += 1
                self.block(s['body'])
                self.loop_depth -= 1
                del self.locals[s['node'], 'Item'], self.locals[s['node'], 'Index']
                if is_map:
                    del self.locals[s['node'], 'Key']
                self.indent -= 1
                self.line('}')
            else:
                raise ValueError(f"Unknown IR statement: {op}")

    def continuation_callbacks(self, program):
        self.continuation_expr = True
        self.line('static rt::Value EvaluateContinuation(rt::Ctx& ctx, std::size_t instruction, std::size_t argument) {')
        self.indent += 1
        self.line('switch (instruction) {')
        for i, s in enumerate(program['instructions']):
            if not s['args']: continue
            self.line(f'case {i}: switch (argument) {{')
            for j, expr in enumerate(s['args']):
                self.line(f'case {j}: {{')
                self.indent += 1
                value = self.expr(expr)
                self.line(f'return {value};')
                self.indent -= 1
                self.line('}')
            self.line('default: break; } break;')
        self.line('default: break; }')
        self.line('throw std::runtime_error("Invalid continuation expression");')
        self.indent -= 1
        self.line('}')
        self.continuation_expr = False
        self.line('static std::vector<rt::Value> ActionContinuation(rt::Ctx& ctx, std::size_t instruction, const std::vector<rt::Value>& args) {')
        self.indent += 1
        self.line('switch (instruction) {')
        for i, s in enumerate(program['instructions']):
            if s['op'] not in ('action', 'action_result'): continue
            spec = self.registry[s['type']]
            args = [f'std::get<{CPP_TYPES[p.type]}>(args.at({j}))' for j, p in enumerate(spec.data_inputs)]
            call = self.call(spec, args)
            self.line(f'case {i}: {{')
            if s.get('code'):
                self.line('return ' + self.embedded_call(s, args) + ';')
                self.line('}')
                continue
            if s['op'] == 'action':
                self.line(call + '; return {};')
            else:
                self.line('auto result = ' + call + ';')
                values = 'result' if len(s['outputs']) == 1 else ', '.join(f'std::get<{j}>(result)' for j in range(len(s['outputs'])))
                self.line('return {' + values + '};')
            self.line('}')
        self.line('default: throw std::runtime_error("Invalid continuation action"); }')
        self.indent -= 1
        self.line('}')

    def generate(self, ir):
        if 'scenes' in ir:
            return self.generate_project(ir)
        self.lines, self.counter, self.indent = [], 0, 0
        self.locals = {}
        self.parameters = []
        self.loop_depth = 0
        self.function_results = []
        functions = ir.get('functions', {})
        from .components import with_components
        from .typed_schema import with_types
        self.registry = with_components(self.registry, ir['scene'].get('component_definitions', []))
        definitions = ir.get('type_definitions', {})
        self.registry = with_types(self.registry, definitions.get('structs', []), definitions.get('enums', []))
        self.registry = scoped_registry(self.registry, list(functions.values()), event_definitions=ir.get('event_definitions', []))
        self.line('// Generated file. Do not edit.')
        self.line('#include "node_code.hpp"')
        self.line('#include <tuple>')
        program = json.dumps(ir, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.line(f"rt::Json CompiledProgram() {{ return rt::Json::parse({quoted(program)}); }}")
        self.line('rt::Json CompiledScene() { return CompiledProgram().at("scene"); }')
        def declaration(f):
            results = ', '.join(CPP_TYPES[p['type']] for p in f['outputs'])
            args = ', '.join(f'{CPP_TYPES[p["type"]]} arg{i}' for i,p in enumerate(f['inputs']))
            return f'static std::tuple<{results}> Function_{f["id"]}(rt::Ctx& ctx{", " if args else ""}{args})'
        emitted_functions = [f for f in functions.values() if f['pure'] or 'continuations' not in ir]
        for f in emitted_functions:
            self.line(declaration(f) + ';')
        for f in emitted_functions:
            self.line(declaration(f) + ' {')
            self.indent += 1
            self.line('rt::CallDepthScope call_scope(ctx);')
            for index,port in enumerate(f['inputs']):
                if port['type'].startswith(('struct:','enum:')) or is_user_collection(port['type']):
                    self.line(f'rt::ValidateTypedValue(ctx,{cpp_string(port["type"])},arg{index});')
            self.parameters = [f'arg{i}' for i in range(len(f['inputs']))]
            self.function_results=[p['type'] for p in f['outputs']]
            self.locals = {}
            self.block(f['body'])
            self.indent -= 1
            self.line('}')
        self.parameters, self.locals = [], {}
        self.function_results=[]
        if 'continuations' in ir:
            self.continuation_callbacks(ir['continuations'])
        self.line('void BindEvents(rt::Ctx& ctx) {')
        self.indent += 1
        if 'continuations' in ir:
            self.line('rt::ConfigureContinuations(ctx, CompiledProgram(), EvaluateContinuation, ActionContinuation);')
        events={e['id']:e for e in ir.get('event_definitions', [])}
        for eid,event in events.items():
            types=', '.join(cpp_string(p['type']) for p in event['parameters'])
            self.line(f'rt::DeclareEvent(ctx, {eid}, std::vector<std::string>{{{types}}});')
        for handler in ir['events'].get('custom', []):
            eid=handler['event']
            self.line(f'rt::BindEvent(ctx, {eid}, {cpp_string(handler["node"])}, rt::EntityRef{{{cpp_string(handler["owner"])}}}, {"true" if handler["enabled"] else "false"},')
            self.line('[](rt::Ctx& ctx, rt::EntityRef event_sender, rt::EntityRef event_receiver, const std::vector<rt::Value>& event_args) {')
            self.indent += 1
            self.locals={(handler['node'],'Sender'):'event_sender',(handler['node'],'Receiver'):'event_receiver'}
            for i,p in enumerate(events[eid]['parameters']):
                self.locals[handler['node'],p['name']]=f'std::get<{CPP_TYPES[p["type"]]}>(event_args.at({i}))'
            self.block(handler['body'])
            self.indent -= 1
            self.line('});')
        for handler in ir['events'].get('world_pause', []):
            self.line(f'rt::BindWorldPauseEvent(ctx, {handler["event"]}, {cpp_string(handler["node"])},')
            self.line('[](rt::Ctx& ctx, rt::EntityRef, rt::EntityRef, const std::vector<rt::Value>&) {')
            self.indent += 1
            self.locals = {}
            self.block(handler['body'])
            self.indent -= 1
            self.line('});')
        for handler in ir['events'].get('persistence', []):
            self.line(f'rt::BindGameSaveEvent(ctx, {handler["event"]}, {cpp_string(handler["node"])},')
            self.line('[](rt::Ctx& ctx, rt::EntityRef, rt::EntityRef, const std::vector<rt::Value>& event_args) {')
            self.indent += 1
            self.locals = {(handler['node'], p):f'std::get<std::string>(event_args.at({i}))'
                           for i,p in enumerate(('Slot', 'Error'))}
            self.block(handler['body'])
            self.indent -= 1
            self.line('});')
        for handler in ir['events'].get('scene_failure', []):
            self.line(f'rt::BindSceneLoadFailed(ctx, {cpp_string(handler["node"])},')
            self.line('[](rt::Ctx& ctx, rt::EntityRef, rt::EntityRef, const std::vector<rt::Value>& event_args) {')
            self.indent += 1
            self.locals = {(handler['node'],p):f'std::get<std::string>(event_args.at({i}))' for i,p in enumerate(('Scene','Error'))}
            self.block(handler['body'])
            self.indent -= 1
            self.line('});')
        for handler in ir['events'].get('physics', []):
            self.line(f'rt::BindPhysicsEvent(ctx, {handler["event"]}, {cpp_string(handler["node"])}, rt::EntityRef{{{cpp_string(handler["owner"])}}},')
            self.line('[](rt::Ctx& ctx, rt::EntityRef, rt::EntityRef, const std::vector<rt::Value>& event_args) {')
            self.indent += 1
            self.locals = {(handler['node'], p):f'std::get<{t}>(event_args.at({i}))'
                           for i,(p,t) in enumerate((('Entity','rt::EntityRef'),('Other','rt::EntityRef'),
                                                      ('Point','rt::Vec3'),('Normal','rt::Vec3')))}
            self.block(handler['body'])
            self.indent -= 1
            self.line('});')
        for handler in ir['events'].get('input', []):
            self.line(f'rt::BindInputEvent(ctx, {handler["event"]}, {cpp_string(handler["node"])}, {cpp_string(handler["filter"])},')
            self.line('[](rt::Ctx& ctx, rt::EntityRef, rt::EntityRef, const std::vector<rt::Value>& event_args) {')
            self.indent += 1
            port = 'Key' if handler['event'] in (10008, 10009) else 'Button' if handler['event'] in (10010,10020) else 'Action'
            self.locals = {(handler['node'], port):'std::get<std::string>(event_args.at(0))',
                           (handler['node'], 'Down'):'std::get<bool>(event_args.at(1))'}
            if handler['event'] == 10020:
                self.locals[(handler['node'], 'Controller')] = 'std::get<std::int64_t>(event_args.at(2))'
            self.block(handler['body'])
            self.indent -= 1
            self.line('});')
        for handler in ir['events'].get('entity_lifecycle', []):
            self.line(f'rt::BindEntityLifecycle(ctx, {handler["event"]}, {cpp_string(handler["node"])}, rt::EntityRef{{{cpp_string(handler["owner"])}}},')
            self.line('[](rt::Ctx& ctx, rt::EntityRef, rt::EntityRef, const std::vector<rt::Value>& event_args) {')
            self.indent += 1
            self.locals = {(handler['node'], p):f'std::get<{t}>(event_args.at({i}))'
                           for i,(p,t) in enumerate((('Entity','rt::EntityRef'),('Active','bool')))}
            self.block(handler['body'])
            self.indent -= 1
            self.line('});')
        for handler in ir['events'].get('animation_finished', []):
            self.line(f'rt::BindAnimationFinished(ctx, {cpp_string(handler["node"])}, rt::EntityRef{{{cpp_string(handler["owner"])}}}, {cpp_string(handler["filter"])},')
            self.line('[](rt::Ctx& ctx, rt::EntityRef, rt::EntityRef, const std::vector<rt::Value>& event_args) {')
            self.indent += 1
            self.locals = {(handler['node'], p):f'std::get<{t}>(event_args.at({i}))'
                           for i,(p,t) in enumerate((('Entity','rt::EntityRef'),('Clip','std::string')))}
            self.block(handler['body'])
            self.indent -= 1
            self.line('});')
        for handler in ir['events'].get('animation_notify', []):
            self.line(f'rt::BindAnimationNotify(ctx, {cpp_string(handler["node"])}, rt::EntityRef{{{cpp_string(handler["owner"])}}}, {cpp_string(handler["filter"])},')
            self.line('[](rt::Ctx& ctx, rt::EntityRef, rt::EntityRef, const std::vector<rt::Value>& event_args) {')
            self.indent += 1
            self.locals = {(handler['node'], p):f'std::get<{t}>(event_args.at({i}))'
                           for i,(p,t) in enumerate((('Entity','rt::EntityRef'),('Notify','std::string')))}
            self.block(handler['body'])
            self.indent -= 1
            self.line('});')
        for handler in ir['events'].get('ui', []):
            args = ', '.join(cpp_string(handler[k]) for k in ('node', 'kind', 'widget', 'element'))
            self.line(f'rt::BindUiEvent(ctx, {args}, [](rt::Ctx& ctx, const rt::UiEvent& event) {{')
            self.indent += 1
            self.locals = {(handler['node'], p):'event.' + field for p,field in
                           [('Widget','document'),('Element','element'),('Value','value'),('Checked','checked')]}
            self.block(handler['body'])
            self.indent -= 1
            self.line('});')
        for handler in ir['events'].get('timers', []):
            self.line(f'rt::BindTimer(ctx, {cpp_string(handler["node"])}, rt::EntityRef{{{cpp_string(handler["owner"])}}}, {cpp_string(handler["filter"])},')
            self.line('[](rt::Ctx& ctx, const std::string& timer_name, rt::EntityRef timer_owner) {')
            self.indent += 1
            self.locals = {(handler['node'], 'Name'):'timer_name', (handler['node'], 'Owner'):'timer_owner'}
            self.block(handler['body'])
            self.indent -= 1
            self.line('});')
        self.indent -= 1
        self.line('}')
        self.locals = {}
        for event, function in (("start", "OnStart"), ("update", "OnUpdate"), ("fixed_update", "OnFixedUpdate"),
                                ("late_update", "OnLateUpdate"), ("quit", "OnQuit"), ("scene_loaded", "OnSceneLoaded")):
            self.line(f"void {function}(rt::Ctx& ctx) {{")
            self.indent += 1
            self.line('rt::ExecutionScope execution(ctx);')
            self.block(ir["events"].get(event, []))
            self.indent -= 1
            self.line("}")
        return "\n".join(self.lines) + "\n"

    def generate_project(self,project):
        lines=['// Generated project. Do not edit.', '#include "node_code.hpp"', '#include <tuple>']
        for i,(scene_id,program) in enumerate(project['scenes'].items()):
            source=CppEmitter().generate(program)
            lines += [f'namespace Scene_{i} {{', '\n'.join(line for line in source.splitlines() if not line.startswith('#include ')), '}']
        program=json.dumps(project,ensure_ascii=False,sort_keys=True,separators=(',',':'))
        lines += [f'rt::Json CompiledProgram() {{ return rt::Json::parse({quoted(program)}); }}',
                  'rt::Json CompiledScene() { auto p=CompiledProgram(); return p.at("scenes").at(p.at("entry_scene").get<std::string>()).at("scene"); }']
        for name in ('BindEvents','OnStart','OnUpdate','OnFixedUpdate','OnLateUpdate','OnQuit','OnSceneLoaded'):
            lines.append(f'void {name}(rt::Ctx& ctx) {{')
            for i,scene_id in enumerate(project['scenes']):
                lines.append(f'if(ctx.scene_name=={cpp_string(scene_id)}) {{ Scene_{i}::{name}(ctx); return; }}')
            lines += ['throw std::runtime_error("Unknown compiled scene");','}']
        return '\n'.join(lines)+'\n'


def generate_node_code(ir):
    """Compile each reachable integration hook once, for every native host."""
    from .components import with_components
    from .typed_schema import with_types

    entries = {}
    def visit(value, registry, scene):
        if isinstance(value, dict):
            if value.get('op') in ('action', 'action_result') and value.get('code'):
                key = (scene, value['type'], value['node'], value['code'])
                entries[key] = (value, registry[value['type']])
            for child in value.values():
                visit(child, registry, scene)
        elif isinstance(value, list):
            for child in value:
                visit(child, registry, scene)

    programs = ir['scenes'].items() if 'scenes' in ir else [('main', ir)]
    for scene, program in programs:
        registry = with_components(Registry(), program['scene'].get('component_definitions', []))
        definitions = program.get('type_definitions', {})
        registry = with_types(registry, definitions.get('structs', []), definitions.get('enums', []))
        for key in ('events', 'functions', 'continuations'):
            visit(program.get(key, {}), registry, scene)

    emitter = CppEmitter()
    emitter.line('// Generated embedded C++ shared by Preview and Game. Do not edit.')
    emitter.line('#include "node_code.hpp"')
    emitter.line('void RegisterEmbeddedNodeCode() {')
    emitter.indent += 1
    for (scene, type_id, node, code), (statement, spec) in sorted(entries.items()):
        emitter.line(f'rt::RegisterNodeCode({cpp_string(scene)}, {type_id}, {cpp_string(node)}, {cpp_string(code)}, '
                     '[](rt::Ctx& ctx, const std::vector<rt::Value>& args) -> std::vector<rt::Value> {')
        emitter.indent += 1
        emitter.line(f'if (args.size() != {len(spec.data_inputs)}) throw std::runtime_error("Node code argument count mismatch");')
        for i, port in enumerate(spec.data_inputs):
            emitter.line(f'const auto& input_{i} = std::get<{CPP_TYPES[port.type]}>(args.at({i}));')
        call = emitter.call(spec, [f'input_{i}' for i in range(len(spec.data_inputs))])
        outputs = [p for p in spec.outputs if p.type != 'exec']
        if outputs:
            result_type = CPP_TYPES[outputs[0].type] if len(outputs) == 1 else 'std::tuple<' + ', '.join(CPP_TYPES[p.type] for p in outputs) + '>'
            emitter.line(f'{result_type} result{{}};')
            call = 'result = ' + call
        origin = scene + '/' + node if 'scenes' in ir else node
        used_call = emitter.embedded_code(code, origin, call + ';')
        if not used_call:
            emitter.line(call + ';')
        values = 'result' if len(outputs) == 1 else ', '.join(f'std::get<{i}>(result)' for i in range(len(outputs)))
        emitter.line('return {' + values + '};')
        emitter.indent -= 1
        emitter.line('});')
    emitter.indent -= 1
    emitter.line('}')
    return '\n'.join(emitter.lines) + '\n'


def export(ir, directory):
    directory = Path(directory)
    write_text_if_changed(directory / "game.generated.cpp", CppEmitter().generate(ir))
    write_text_if_changed(directory / "node-code.generated.cpp", generate_node_code(ir))
    save_json(directory / "game.ir.json", ir)
    return directory / "game.generated.cpp"

