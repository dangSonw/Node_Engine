"""Project-owned typed function signatures. IDs, never names, identify call sites."""
from copy import deepcopy
from dataclasses import replace
import re
import uuid
from .data_types import default_value, literal_valid, TYPES
from .registry import NodeSpec, Port

ENTRY, RETURN = 6001, 6002
MIN_FUNCTION_ID = 1_000_000


def signatures(definitions, schema=None):
    if not isinstance(definitions, list) or len(definitions) > 256:
        raise ValueError('Functions must be an array of at most 256 definitions')
    result, names = {}, set()
    for f in definitions:
        if not isinstance(f, dict):
            raise ValueError('Function must be an object')
        fid, name = f.get('id'), f.get('name')
        if type(fid) is not int or not MIN_FUNCTION_ID <= fid <= 2147483647 or fid in result:
            raise ValueError('Function IDs must be unique integers from 1000000 to 2147483647')
        if (not isinstance(name,str) or not name.strip() or len(name)>128 or name.casefold() in names
                or not literal_valid(name,'string') or any(ord(c)<32 or ord(c)==127 for c in name)):
            raise ValueError('Function names must be nonempty, unique and at most 128 characters')
        if type(f.get('pure')) is not bool:
            raise ValueError(f'{name}: pure must be a boolean')
        for side in ('inputs', 'outputs'):
            ports = f.get(side)
            if not isinstance(ports, list) or len(ports) > 32:
                raise ValueError(f'{name}: {side} must be an array of at most 32 ports')
            seen = set()
            for p in ports:
                if (not isinstance(p,dict) or not isinstance(p.get('name'),str)
                        or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}',p['name'])):
                    raise ValueError(f'{name}: port names must be identifiers')
                if p['name'] in seen or p['name'] in ('In', 'Out'):
                    raise ValueError(f'{name}: duplicate or reserved port name {p["name"]}')
                seen.add(p['name'])
                if p.get('type') not in TYPES and not (schema and schema.is_type(p.get('type'))):
                    raise ValueError(f'{name}.{p["name"]}: unsupported value type')
                if side == 'inputs' and not literal_valid(p.get('default', default_value(p['type'],schema)), p['type'],schema):
                    raise ValueError(f'{name}.{p["name"]}: invalid default value')
        if f['pure'] and not f['outputs']:
            raise ValueError(f'{name}: pure functions require an output')
        result[fid] = f
        names.add(name.casefold())
    return result


def scoped_registry(base, definitions, current=None, event_definitions=None):
    """Copy just the registry index; builtin metadata remains the single YAML source."""
    from copy import copy
    from .events import with_events
    registry = copy(base)
    registry.nodes = {k:v for k,v in base.nodes.items() if k < MIN_FUNCTION_ID}
    registry = with_events(registry, base.event_definitions if event_definitions is None else event_definitions)
    schema=getattr(base,'type_schema',None)
    functions = signatures(definitions,schema)
    for fid, f in functions.items():
        args = tuple(Port(p['name'], p['type'], deepcopy(p.get('default', default_value(p['type'],schema)))) for p in f['inputs'])
        results = tuple(Port(p['name'], p['type']) for p in f['outputs'])
        registry.nodes[fid] = NodeSpec(fid, f['name'], 6, 'pure_call' if f['pure'] else 'function_call',
            args if f['pure'] else (Port('In','exec'),) + args,
            results if f['pure'] else (Port('Out','exec'),) + results, function_id=fid)
    if current is not None:
        f = functions[current]
        args = tuple(Port(p['name'], p['type']) for p in f['inputs'])
        results = tuple(Port(p['name'], p['type'], default_value(p['type'],schema)) for p in f['outputs'])
        registry.nodes[ENTRY] = replace(registry[ENTRY], outputs=args if f['pure'] else (Port('Out','exec'),)+args)
        registry.nodes[RETURN] = replace(registry[RETURN], inputs=results if f['pure'] else (Port('In','exec'),)+results)
    return registry


def new_function(name, inputs=(), outputs=(), pure=False, definitions=(), *, schema=None):
    used = {f['id'] for f in definitions}
    fid = MIN_FUNCTION_ID + uuid.uuid4().int % (2147483647-MIN_FUNCTION_ID)
    while fid in used:
        fid += 1
    f = {'id':fid, 'name':name, 'pure':pure, 'inputs':deepcopy(list(inputs)), 'outputs':deepcopy(list(outputs)),
         'graph':{'version':1, 'nodes':[{'id':'entry', 'type':ENTRY, 'position':[0,0], 'values':{}},
                                      {'id':'return', 'type':RETURN, 'position':[450,0], 'values':{}}],
                  'links':[]}}
    if not pure:
        f['graph']['links'].append({'from':['entry','Out'], 'to':['return','In']})
    signatures([*definitions, f],schema)
    return f
