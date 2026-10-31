"""Validate typed domain graphs and lower to a small, deterministic structured IR."""
from dataclasses import dataclass
from graphlib import TopologicalSorter, CycleError
import re
from .registry import Registry
from .scene import validate_scene
from .data_types import literal_valid, variable
from .typed_schema import build_schema, validate_variable, with_types
from .functions import signatures, scoped_registry, ENTRY, RETURN
from .switches import node_spec, checked_cases, default_cases, case_port
from .node_code import validate_embedded_code


@dataclass(frozen=True)
class Problem:
    node: str
    message: str


class GraphError(ValueError):
    def __init__(self, problems):
        self.problems = problems
        super().__init__("\n".join(f"{p.node}: {p.message}" for p in problems))


def validate(graph, registry=None):
    registry = registry or Registry()
    problems = []
    if not isinstance(graph, dict):
        return [Problem("graph", "Graph must be an object")]
    if graph.get('struct_definitions') or graph.get('enum_definitions'):
        try:
            inherited = getattr(registry, 'type_schema', None)
            structs = list(inherited.structs.values()) if inherited else []
            enums = list(inherited.enums.values()) if inherited else []
            structs = list({d['name']: d for d in structs + graph.get('struct_definitions', [])}.values())
            enums = list({d['name']: d for d in enums + graph.get('enum_definitions', [])}.values())
            registry = with_types(registry, structs, enums)
        except ValueError as e:
            return [Problem('definitions', str(e))]
    if graph.get('functions') or 'event_definitions' in graph:
        try:
            registry = scoped_registry(registry, graph.get('functions', []), event_definitions=graph.get('event_definitions', registry.event_definitions))
        except ValueError as e:
            return [Problem('definitions', str(e))]
    if not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("links"), list):
        return [Problem("graph", "Nodes and links must be arrays")]
    if graph.get("version") != 1:
        problems.append(Problem("graph", "Unsupported graph version"))
    nodes, specs = {}, {}
    for node in graph.get("nodes", []):
        if not isinstance(node, dict):
            problems.append(Problem("graph", "Node must be an object"))
            continue
        nid = str(node.get("id", ""))
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", nid):
            problems.append(Problem(nid, "Node ID must contain 1-128 letters, digits, underscores or hyphens"))
        if nid in nodes:
            problems.append(Problem(nid, "Missing or duplicate node ID"))
        if not isinstance(node.get("values", {}), dict):
            problems.append(Problem(nid, "Node values must be an object"))
            continue
        nodes[nid] = node
        try:
            if type(node.get('type')) is not int:
                raise ValueError('Node type ID must be an integer')
            specs[nid] = node_spec(registry, node)
            code = node.get('code', '')
            editable = specs[nid].kind in ('action', 'action_result') and bool(specs[nid].function)
            for diagnostic in validate_embedded_code(code, editable=editable):
                problems.append(Problem(nid, f'Embedded code line {diagnostic.line}: {diagnostic.message}'))
        except ValueError as error:
            problems.append(Problem(nid, str(error)))
        except (KeyError, TypeError):
            problems.append(Problem(nid, f"Unavailable node type: {node.get('type')}"))
    incoming, outgoing = {}, {}
    data_dependencies = {n: set() for n in nodes}
    exec_dependencies = {n: set() for n in nodes}
    for link in graph.get("links", []):
        try:
            src, out = link["from"]
            dst, inp = link["to"]
            src, dst = str(src), str(dst)
            sp = next(p for p in specs[src].outputs if p.name == out)
            dp = next(p for p in specs[dst].inputs if p.name == inp)
        except (KeyError, ValueError, TypeError, StopIteration):
            problems.append(Problem("graph", f"Unknown node or port in link: {link}"))
            continue
        if sp.type != dp.type:
            problems.append(Problem(dst, f"Type mismatch: {sp.type} -> {dp.type} at {inp}; add an explicit conversion"))
        if dp.type != "exec" and (dst, inp) in incoming:
            problems.append(Problem(dst, f"Input {inp} has multiple sources"))
        if sp.type == "exec" and (src, out) in outgoing:
            problems.append(Problem(src, f"Execution output {out} has multiple targets; use Sequence"))
        incoming[dst, inp] = (src, out)
        outgoing[src, out] = (dst, inp)
        # Flow control inputs mutate state and terminate this path; they cannot
        # create a cycle through that node's execution outputs.
        if not (sp.type == 'exec' and specs[dst].kind == 'flow' and inp != 'In'):
            (exec_dependencies if sp.type == "exec" else data_dependencies)[dst].add(src)
    for nid, spec in specs.items():
        for port in spec.data_inputs:
            if (nid, port.name) not in incoming:
                value = nodes[nid].get("values", {}).get(port.name, port.default)
                if not literal_valid(value, port.type, getattr(registry, 'type_schema', None)):
                    problems.append(Problem(nid, f"Input {port.name} requires {port.type}"))
    for label, dependencies in (("Data", data_dependencies), ("Execution", exec_dependencies)):
        try:
            tuple(TopologicalSorter(dependencies).static_order())
        except CycleError as e:
            for nid in dict.fromkeys(e.args[1]):
                problems.append(Problem(nid, f"{label} cycle; use a structured Loop node"))
    return problems


def compile_graph(graph, scene=None, registry=None, *, global_types=None):
    from .components import with_components
    from .prefabs import prepare_scene_prefabs
    base = registry or Registry()
    scene = prepare_scene_prefabs(scene)
    scene = scene if scene is not None else {'entities': [], 'variables': {}}
    def merge_definitions(key):
        values = list(scene.get(key, [])) + list(graph.get(key, [])) if isinstance(graph, dict) else list(scene.get(key, []))
        return list({item['name']: item for item in values}.values())
    merged_structs, merged_enums = merge_definitions('struct_definitions'), merge_definitions('enum_definitions')
    scene = dict(scene)
    scene['struct_definitions'], scene['enum_definitions'] = merged_structs, merged_enums
    schema = build_schema(merged_structs, merged_enums)
    scene = validate_scene(scene)
    base = with_components(base, scene.get('component_definitions', []))
    base = with_types(base, merged_structs, merged_enums)
    if not isinstance(graph, dict):
        raise GraphError(validate(graph, base))
    definitions = graph.get('functions', [])
    try:
        functions = signatures(definitions,schema)
        registry = scoped_registry(base, definitions, event_definitions=graph.get('event_definitions', []))
        base = registry
    except ValueError as e:
        raise GraphError([Problem('functions', str(e))]) from e
    problems = validate(graph, registry)
    def input_problems(document, prefix=''):
        from .input import BUTTONS, GAMEPAD_AXES, GAMEPAD_BUTTONS
        linked = {(str(link['to'][0]), link['to'][1]) for link in document['links']}
        bindings = scene.get('input', {'actions': {}, 'axes': {}})
        for node in document.get('nodes', []):
            if not isinstance(node, dict) or type(node.get('type')) is not int or node['type'] not in registry.nodes:
                continue
            spec = registry[node['type']]
            if spec.event == 'input':
                name = node.get('values', {}).get('Filter', spec.data_inputs[0].default)
                allowed = (GAMEPAD_BUTTONS if spec.id == 10020 else bindings['actions'] if spec.id in (10011, 10012) else
                           [key for key in BUTTONS if key.startswith('Mouse') == (spec.id == 10010)])
                if name and name not in allowed:
                    problems.append(Problem(prefix + str(node['id']), f'Unknown input event filter: {name}'))
            if spec.function == 'GamepadAxis':
                values=node.get('values', {})
                for port,valid in [('Axis',lambda v:v in GAMEPAD_AXES),
                                   ('Controller',lambda v:0<=v<=4294967295),
                                   ('Dead Zone',lambda v:0<=v<1)]:
                    if (str(node['id']),port) not in linked:
                        value=values.get(port,next(p.default for p in spec.data_inputs if p.name==port))
                        if not valid(value): problems.append(Problem(prefix+str(node['id']),f'Invalid gamepad {port}: {value}'))
            if spec.function in ('ActionHeld', 'ActionPressed', 'ActionReleased', 'InputAxis','InputContextEnabled','SetInputContextEnabled'):
                port, group = (('Axis', 'axes') if spec.function == 'InputAxis' else ('Context','contexts') if spec.function in ('InputContextEnabled','SetInputContextEnabled') else ('Action', 'actions'))
                if (str(node['id']), port) not in linked:
                    name = node.get('values', {}).get(port, spec.data_inputs[0].default)
                    if isinstance(name, str) and name not in bindings.get(group,{}):
                        problems.append(Problem(prefix + str(node['id']), f'Unknown input {port.lower()}: {name}; edit Scene > Input Actions and Axes'))
    if not problems:
        input_problems(graph)
    dependencies = {fid:set() for fid in functions}
    for fid, f in functions.items():
        scoped = scoped_registry(base, definitions, fid)
        errors = validate(f.get('graph'), scoped)
        problems.extend(Problem(f'{fid}/{p.node}', p.message) for p in errors)
        if not errors:
            input_problems(f['graph'], f'{fid}/')
            if f['graph'].get('functions') or f['graph'].get('event_definitions'):
                problems.append(Problem(str(fid), 'Define functions and events at project graph level'))
            for n in f['graph']['nodes']:
                if n['type'] in functions:
                    dependencies[fid].add(n['type'])
                spec = scoped[n['type']]
                if spec.kind == 'collection_callback':
                    callback = n.get('values', {}).get('Callback', 0)
                    if type(callback) is int and callback in functions:
                        dependencies[fid].add(callback)
    try:
        tuple(TopologicalSorter(dependencies).static_order())
    except CycleError as e:
        problems.append(Problem('functions', 'Recursive call cycle: ' + ' -> '.join(functions[f]['name'] for f in e.args[1])))
    if problems:
        raise GraphError(problems)
    scene = validate_scene(scene if scene is not None else {'entities':[], 'variables':{}})
    scopes = scene.get('variable_scopes', {})
    variable_types = {(scopes.get(name, 'scene'), name): validate_variable(value, schema)[0] for name, value in scene['variables'].items()}
    variable_types.update({('global', name): kind for name, kind in (global_types or {}).items()})
    events = _lower_graph(graph, registry, variable_types, schema=schema, variable_scopes=scopes)
    subscriptions = {}
    for handler in events.get('timers', []) + events.get('custom', []) + events.get('physics', []) + events.get('animation_finished', []) + events.get('animation_notify', []) + events.get('entity_lifecycle', []):
        if handler['owner'] and handler['owner'] not in {e['id'] for e in scene['entities']}:
            raise GraphError([Problem(handler['node'], f"Event receiver entity does not exist: {handler['owner']}")])
        if 'enabled' in handler:
            key=(handler['event'],handler['owner'])
            if subscriptions.setdefault(key,handler['enabled']) != handler['enabled']:
                raise GraphError([Problem(handler['node'],'Handlers for the same event and receiver must agree on InitiallySubscribed')])
    compiled = {}
    for fid in sorted(functions):
        f = functions[fid]
        compiled[str(fid)] = {k:f[k] for k in ('id','name','pure','inputs','outputs')}
        compiled[str(fid)]['body'] = _lower_graph(f['graph'], scoped_registry(base, definitions, fid), variable_types, f, schema, scopes)
    ir = {'version':1, 'events':events, 'scene':scene,
          'type_definitions': {'structs': merged_structs, 'enums': merged_enums},
          'variable_scopes': scene.get('variable_scopes', {})}
    if registry.event_definitions:
        ir['event_definitions']=sorted(registry.event_definitions,key=lambda e:e['id'])
    if compiled:
        ir['functions'] = compiled
    from .continuations import lower_continuations
    return lower_continuations(ir, graph, registry)


def _lower_graph(graph, registry, variable_types, function=None, schema=None, variable_scopes=None):
    problems = validate(graph, registry)
    if problems:
        raise GraphError(problems)
    nodes = {str(n["id"]): n for n in graph["nodes"]}
    def origin(nid):
        return f'{function["id"]}/{nid}' if function else nid
    def fail(nid, message):
        raise GraphError([Problem(origin(nid), message)])
    inputs, edges = {}, {}
    for link in graph["links"]:
        src, out = link["from"]
        dst, inp = link["to"]
        inputs[str(dst), inp] = (str(src), out)
        edges[str(src), out] = (str(dst), inp)

    for nid, node in nodes.items():
        spec = registry[node['type']]
        if spec.kind == 'collection_callback' and (nid, 'Callback') in inputs:
            fail(nid, 'Collection callback must be a constant function ID in the Inspector')
        if spec.kind == 'enum_value' and (nid, 'Value') not in inputs:
            value = node.get('values', {}).get('Value', spec.data_inputs[0].default)
            if not schema.literal_valid(value, spec.outputs[0].type):
                fail(nid, f'Unknown {spec.outputs[0].type} label: {value}')
        if spec.constant_inputs:
            for p in spec.data_inputs:
                if (nid, p.name) in inputs:
                    fail(nid, f'Event listener {p.name} must be a constant in the Inspector')
            value = node.get('values', {}).get('Filter', '')
            if value and (not value.strip() or '\0' in value or len(value.encode('utf-8')) > 512):
                fail(nid, 'Timer filter must be empty or a valid timer name (1-512 UTF-8 bytes, no NUL)')
            if spec.event == 'animation_finished':
                value = node.get('values', {}).get('Clip Filter', '')
                if '\0' in value or len(value.encode('utf-8')) > 512:
                    fail(nid, 'Animation clip filter must be at most 512 UTF-8 bytes with no NUL')
            if spec.event == 'animation_notify':
                value = node.get('values', {}).get('Notify Filter', '')
                if '\0' in value or len(value.encode('utf-8')) > 512:
                    fail(nid, 'Animation notify filter must be at most 512 UTF-8 bytes with no NUL')
            if spec.event.startswith('ui_'):
                for key in ('Widget Filter', 'Element Filter'):
                    value = node.get('values', {}).get(key, '')
                    if value and not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
                        fail(nid, f'{key} requires an empty filter or a UI identifier')
        if function:
            if spec.kind == 'event':
                fail(nid, 'Lifecycle events belong in Gameplay, not inside a function')
            if function['pure'] and (spec.context or spec.kind not in ('pure','select','pure_call','struct_make','struct_break','enum_value','collection_callback','function_entry','return')):
                fail(nid, 'Pure functions can only use parameters and context-free pure nodes')
        elif spec.kind in ('function_entry', 'return'):
            fail(nid, 'Function Input/Output belongs inside a function')
        if spec.variable_type and (nid, 'Name') not in inputs:
            port = next(p for p in spec.inputs if p.name == 'Name')
            name = node.get('values', {}).get('Name', port.default)
            scope = spec.variable_scope or (variable_scopes or {}).get(name, 'scene')
            previous = variable_types.setdefault((scope, name), spec.variable_type)
            if previous != spec.variable_type:
                problems.append(Problem(origin(nid), f'Variable {name!r} is {previous}, not {spec.variable_type}'))
    if problems:
        raise GraphError(problems)

    def expr(nid, port, scopes, depth=0):
        if depth > 256:
            fail(nid, 'Data nesting exceeds 256')
        if (nid, port.name) in inputs:
            source, output = inputs[nid, port.name]
            spec = registry[nodes[source]["type"]]
            if spec.kind == 'function_entry':
                index = next(i for i,p in enumerate(function['inputs']) if p['name'] == output)
                return {'op':'parameter', 'index':index, 'type':port.type}
            if spec.kind in ('foreach', 'function_call', 'action_result', 'flow') or spec.constant_inputs:
                if source not in scopes:
                    where = ('inside that input event handler' if spec.event == 'input' else 'inside that entity lifecycle event handler' if spec.event == 'entity_lifecycle' else 'inside that animation finished event handler' if spec.event == 'animation_finished' else 'inside that animation notify event handler' if spec.event == 'animation_notify' else 'inside that physics event handler' if spec.event == 'physics' else 'inside that persistence event handler' if spec.event == 'persistence' else 'inside that UI event handler' if spec.event.startswith('ui_') else 'inside that timer event handler' if spec.event == 'timer' else 'inside that custom event handler' if spec.event == 'custom' else
                             'inside that flow node output path' if spec.kind == 'flow' else 'inside that For Each body' if spec.kind == 'foreach' else
                             'after that function call on its Out path' if spec.kind == 'function_call' else 'after that action on its Out path')
                    fail(nid, f'{source}.{output} is only available {where}')
                return {'op': 'local', 'node': origin(source), 'port': output, 'type': port.type}
            if spec.kind == 'pure_call':
                index = next(i for i,p in enumerate(spec.outputs) if p.name == output)
                return {'op':'invoke', 'node':origin(source), 'type':spec.id, 'index':index,
                        'args':[expr(source, p, scopes, depth+1) for p in spec.data_inputs]}
            if spec.kind in ('struct_make', 'enum_value'):
                return {'op': spec.kind, 'node': origin(source), 'type': port.type,
                        'fields': [p.name for p in spec.data_inputs] if spec.kind == 'struct_make' else [],
                        'args': [expr(source, p, scopes, depth + 1) for p in spec.data_inputs]}
            if spec.kind == 'struct_break':
                return {'op': 'struct_get', 'node': origin(source), 'type': port.type,
                        'field': output, 'args': [expr(source, spec.data_inputs[0], scopes, depth + 1)]}
            if spec.kind == 'collection_callback':
                values = nodes[source].get('values', {})
                callback = values.get('Callback', 0)
                if type(callback) is not int or callback not in registry.nodes or registry[callback].kind != 'pure_call':
                    fail(source, 'Collection callback must reference a pure project function')
                callback_spec = registry[callback]
                element_type = spec.data_inputs[0].type[6:-1]
                expected_output = 'bool' if spec.function == 'FilterArray' else 'float' if spec.function == 'SortArray' else element_type
                callback_inputs = [p for p in callback_spec.inputs if p.type != 'exec']
                callback_outputs = list(callback_spec.outputs)
                if len(callback_inputs) != 1 or callback_inputs[0].type != element_type or len(callback_outputs) != 1 or callback_outputs[0].type != expected_output:
                    fail(source, f'{spec.name} callback {callback} must have signature ({element_type}) -> ({expected_output})')
                return {'op': 'collection_callback', 'node': origin(source), 'type': port.type,
                        'mode': spec.function, 'callback': callback,
                        'args': [expr(source, spec.data_inputs[0], scopes, depth + 1)]}
            if spec.kind not in ('pure', 'select'):
                fail(source, 'Data output has no available value in this execution scope')
            return {"op": "select" if spec.kind == 'select' else "call", "node": origin(source), "type": spec.id,
                    "args": [expr(source, p, scopes, depth + 1) for p in spec.data_inputs]}
        value = nodes[nid].get("values", {}).get(port.name, port.default)
        return {"op": "literal", "type": port.type, "value": value}

    def chain(nid, depth=0, scopes=(), loops=()):
        if nid is None:
            return []
        nid, entry = nid if isinstance(nid, tuple) else (nid, 'In')
        if depth > 256:
            fail(nid, 'Execution nesting exceeds 256')
        spec = registry[nodes[nid]["type"]]
        if spec.constant_inputs:
            return chain(edges.get((nid, 'Out')), depth + 1, scopes + (nid,), loops)
        ports = spec.data_inputs[:1] if spec.id in (2008,2011) and entry == 'Reset' else spec.data_inputs
        args = [expr(nid, p, scopes) for p in ports]
        def branch(name):
            return chain(edges.get((nid, name)), depth + 1, scopes, loops)
        stmt = {"op": spec.kind, "node": origin(nid), "type": spec.id, "args": args}
        if nodes[nid].get('code'):
            stmt['code'] = nodes[nid]['code']
        if spec.kind == 'switch':
            cases = checked_cases(spec, nodes[nid].get('cases', default_cases(spec)))
            stmt['cases'] = [c['value'] for c in cases]
            stmt['branches'] = [branch(case_port(c)) for c in cases] + [branch('Default')]
            return [stmt]
        if spec.kind == 'flow':
            stmt['input'] = entry
            stmt['branches'] = [chain(edges.get((nid, p.name)), depth + 1, scopes + (nid,), loops)
                                for p in spec.outputs if p.type == 'exec'] if entry == 'In' else []
            return [stmt]
        if spec.event_id:
            stmt['event'] = spec.event_id
            return [stmt] + chain(edges.get((nid, 'Out')), depth + 1, scopes, loops)
        if spec.kind in ('break', 'continue'):
            if not loops:
                fail(nid, f'{spec.name} must execute inside a loop Body in this graph')
            return [stmt]
        if spec.kind == 'return':
            return [stmt]
        if spec.kind in ('function_call', 'action_result'):
            stmt['outputs'] = [p.name for p in spec.outputs if p.type != 'exec']
            return [stmt] + chain(edges.get((nid, 'Out')), depth + 1, scopes + (nid,), loops)
        if spec.kind == "branch":
            stmt.update(yes=branch("True"), no=branch("False"))
            return [stmt]
        if spec.kind in ("for", "while"):
            stmt["body"] = chain(edges.get((nid, 'Body')), depth + 1, scopes, loops + (nid,))
            return [stmt] + branch("Done")
        if spec.kind == 'foreach':
            stmt['body'] = chain(edges.get((nid, 'Body')), depth + 1, scopes + (nid,), loops + (nid,))
            return [stmt] + branch('Done')
        if spec.kind == "sequence":
            return branch("First") + branch("Then")
        if spec.kind in ('event', 'function_entry'):
            return branch("Out")
        if spec.kind not in ("action", "latent"):
            fail(nid, 'Data node connected as execution')
        return [stmt] + branch("Out")

    if function:
        entries = [nid for nid,n in nodes.items() if n['type'] == ENTRY]
        returns = [nid for nid,n in nodes.items() if n['type'] == RETURN]
        if len(entries) != 1:
            fail('graph', 'Function needs exactly one Function Input node')
        if function['pure']:
            if len(returns) != 1:
                fail('graph', 'Pure function needs exactly one Function Output node')
            nid = returns[0]
            return [{'op':'return', 'node':origin(nid), 'type':RETURN,
                     'args':[expr(nid, p, ()) for p in registry[RETURN].data_inputs]}]
        body = chain(entries[0])
        def returns_always(statements):
            for s in statements:
                if s['op'] == 'return' or (s['op'] == 'branch' and returns_always(s['yes']) and returns_always(s['no'])) or (
                    s['op'] == 'flow' and s['type'] == 2010 and s['input'] == 'In' and all(returns_always(branch) for branch in s['branches'])) or (
                    s['op'] == 'switch' and all(returns_always(branch) for branch in s['branches'])):
                    return True
            return False
        if not returns_always(body):
            if function['outputs']:
                fail('graph', 'Every execution path must reach Function Output when a function has results')
            body.append({'op':'return', 'node':origin(entries[0]), 'type':RETURN, 'args':[]})
        return body
    events = {"start": [], "update": []}
    for nid in sorted(nodes):
        spec = registry[nodes[nid]["type"]]
        if spec.kind == "event":
            if spec.event == 'timer':
                values = nodes[nid].get('values', {})
                events.setdefault('timers', []).append({'node':nid, 'owner':values.get('Receiver', ''),
                                                       'filter':values.get('Filter', ''), 'body':chain(nid)})
            elif spec.event == 'custom':
                values=nodes[nid].get('values',{})
                events.setdefault('custom',[]).append({'node':nid,'event':spec.event_id,'owner':values.get('Receiver',''),
                    'enabled':values.get('InitiallySubscribed',True),'body':chain(nid)})
            elif spec.event in ('persistence', 'world_pause', 'scene_failure'):
                events.setdefault(spec.event, []).append({'node':nid, 'event':spec.id, 'body':chain(nid)})
            elif spec.event == 'input':
                events.setdefault('input', []).append({'node':nid, 'event':spec.id,
                    'filter':nodes[nid].get('values', {}).get('Filter', spec.data_inputs[0].default), 'body':chain(nid)})
            elif spec.event in ('physics', 'entity_lifecycle'):
                values=nodes[nid].get('values',{})
                events.setdefault(spec.event, []).append({'node':nid, 'event':spec.id,
                    'owner':values.get('Receiver',''), 'body':chain(nid)})
            elif spec.event == 'animation_finished':
                values=nodes[nid].get('values',{})
                events.setdefault('animation_finished', []).append({'node':nid,
                    'owner':values.get('Receiver',''), 'filter':values.get('Clip Filter',''), 'body':chain(nid)})
            elif spec.event == 'animation_notify':
                values=nodes[nid].get('values',{})
                events.setdefault('animation_notify', []).append({'node':nid,
                    'owner':values.get('Receiver',''), 'filter':values.get('Notify Filter',''), 'body':chain(nid)})
            elif spec.event.startswith('ui_'):
                values = nodes[nid].get('values', {})
                events.setdefault('ui', []).append({'node':nid, 'kind':spec.event[3:],
                    'widget':values.get('Widget Filter', ''), 'element':values.get('Element Filter', ''), 'body':chain(nid)})
            else:
                events.setdefault(spec.event, []).append({'node':nid, 'body':chain(nid)})
    return events
