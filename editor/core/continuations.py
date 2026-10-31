"""Lower latent graphs to resumable blocks shared by both native hosts."""
from copy import deepcopy


def lower_continuations(ir, graph, registry):
    def statements(body):
        for s in body:
            yield s
            for key in ('body', 'yes', 'no'):
                if key in s:
                    yield from statements(s[key])
            for branch in s.get('branches', []):
                yield from statements(branch)

    roots = [s['body'] for group in ir['events'].values() for s in group]
    roots += [f['body'] for f in ir.get('functions', {}).values()]
    if not any(s['op'] == 'latent' for body in roots for s in statements(body)):
        for event in ('start', 'update', 'fixed_update', 'late_update', 'quit', 'scene_loaded'):
            if event in ir['events']:
                ir['events'][event] = [s for entry in ir['events'][event] for s in entry['body']]
        return ir

    program = dict(instructions=[], blocks=[], entries=[], functions={})
    event_types = {str(n['id']): n['type'] for n in graph['nodes']}

    def ports(node, specs):
        return [dict(node=node, port=p.name, type=p.type) for p in specs if p.type != 'exec']

    def block(body, scope):
        bid = len(program['blocks']); ids = []; program['blocks'].append(ids)
        scope = list(scope)
        for original in body:
            s = deepcopy(original)
            iid = len(program['instructions']); ids.append(iid); program['instructions'].append(s)
            s['locals'] = list(scope)
            op = s['op']
            if op in ('for', 'while', 'foreach'):
                inner = ports(s['node'], registry[s['type']].outputs) if op == 'foreach' else []
                s['body'] = block(original['body'], scope + inner)
            elif op == 'branch':
                for key in ('yes', 'no'):
                    s[key] = block(original[key], scope)
            elif op in ('flow', 'switch'):
                inner = ports(s['node'], registry[s['type']].outputs) if op == 'flow' else []
                s['branches'] = [block(branch, scope + inner) for branch in original['branches']]
            if op in ('function_call', 'action_result'):
                scope += ports(s['node'], registry[s['type']].outputs)
        return bid

    for event, handlers in ir['events'].items():
        for handler in handlers:
            nid = handler['node']; type_id = event_types[nid]
            captures = ports(nid, registry[type_id].outputs)
            eid = len(program['entries'])
            program['entries'].append(dict(node=nid, captures=captures, body=block(handler['body'], captures)))
            handler['body'] = [dict(op='continuation_entry', node=nid, type=type_id, args=[], entry=eid, captures=captures)]
        if event in ('start', 'update', 'fixed_update', 'late_update', 'quit', 'scene_loaded'):
            ir['events'][event] = [s for entry in handlers for s in entry['body']]
    for fid, f in ir.get('functions', {}).items():
        if not f['pure']:
            program['functions'][fid] = dict(inputs=f['inputs'], outputs=f['outputs'], body=block(f['body'], []))
    ir['continuations'] = program
    return ir
