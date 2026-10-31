"""Scene-owned typed component schemas and stable property node identities."""
from copy import copy, deepcopy
import re
import uuid
from .data_types import TYPES, default_value, literal_valid
from .registry import NodeSpec, Port

BASE, STRIDE, MAX_ID = 600_000, 100, 3999
ROLES = ('add', 'remove', 'has', 'enable', 'enabled', 'query')


def signatures(definitions):
    if not isinstance(definitions, list) or len(definitions) > 256:
        raise ValueError('Components require an array of at most 256 definitions')
    result, names = {}, set()
    for definition in definitions:
        if not isinstance(definition, dict):
            raise ValueError('Component definition must be an object')
        cid, name = definition.get('id'), definition.get('name')
        if type(cid) is not int or not 1 <= cid <= MAX_ID or cid in result:
            raise ValueError('Component IDs must be unique integers from 1 to 3999')
        if (not isinstance(name, str) or not name.strip() or len(name) > 128
            or not literal_valid(name, 'string') or any(ord(c) < 32 or ord(c) == 127 for c in name)
            or name.casefold() in names):
            raise ValueError('Component names must be unique nonempty text, at most 128 characters')
        properties = definition.get('properties')
        if not isinstance(properties, list) or len(properties) > 32:
            raise ValueError(f'{name}: at most 32 properties are supported')
        ids, fields = set(), set()
        for p in properties:
            if not isinstance(p, dict) or type(p.get('id')) is not int or not 1 <= p['id'] <= 32 or p['id'] in ids:
                raise ValueError(f'{name}: property IDs must be unique integers from 1 to 32')
            field, t = p.get('name'), p.get('type')
            if not isinstance(field, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', field) or field in fields:
                raise ValueError(f'{name}: property names must be unique identifiers')
            if not isinstance(t, str) or t not in TYPES:
                raise ValueError(f'{name}.{field}: unsupported property type')
            if not literal_valid(p.get('default', default_value(t)), t):
                raise ValueError(f'{name}.{field}: invalid default value')
            ids.add(p['id']); fields.add(field)
        result[cid] = definition; names.add(name.casefold())
    return result


def node_id(component_id, role, property_id=0):
    if role not in (*ROLES, 'get', 'set'):
        raise ValueError('Unsupported component node role')
    slot = ROLES.index(role) if role in ROLES else 10 + property_id * 2 + (role == 'set')
    return BASE + component_id * STRIDE + slot


def with_components(base, definitions):
    schemas = signatures(definitions)
    registry = copy(base)
    registry.nodes = {k: v for k, v in base.nodes.items() if not v.component_id}
    registry.component_definitions = deepcopy(definitions)
    entity = (Port('Entity', 'entity', 'player'),)
    for cid, schema in schemas.items():
        name = schema['name']
        specs = [
            ('add', f'Add {name} Component', 'action', entity, (), 0),
            ('remove', f'Remove {name} Component', 'action', entity, (), 0),
            ('has', f'Has {name} Component', 'pure', entity, (Port('Value', 'bool'),), 0),
            ('enable', f'Set {name} Enabled', 'action', entity + (Port('Enabled', 'bool', True),), (), 0),
            ('enabled', f'Is {name} Enabled', 'pure', entity, (Port('Value', 'bool'),), 0),
            ('query', f'Find Entities With {name}', 'pure', (Port('EnabledOnly', 'bool', True),), (Port('Value', 'array<entity>'),), 0),
        ]
        for p in schema['properties']:
            specs.extend([
                ('get', f'Get {name} {p["name"]}', 'pure', entity, (Port('Value', p['type']),), p['id']),
                ('set', f'Set {name} {p["name"]}', 'action', entity + (Port('Value', p['type'], deepcopy(p.get('default', default_value(p['type'])))),), (), p['id']),
            ])
        for role, label, kind, inputs, outputs, field in specs:
            nid = node_id(cid, role, field)
            if nid in registry.nodes:
                raise ValueError(f'Component node ID collision: {nid}')
            registry.nodes[nid] = NodeSpec(nid, label, 8, kind,
                ((Port('In', 'exec'),) + inputs) if kind == 'action' else inputs,
                (Port('Out', 'exec'),) if kind == 'action' else outputs,
                context=True, component_id=cid, component_operation=role, component_field=field)
    return registry


def new_component(name, properties=(), definitions=(), *, reserved_nodes=()):
    used = {d['id'] for d in definitions}
    properties=list(properties); reserved=set(reserved_nodes)
    cid = 1 + uuid.uuid4().int % MAX_ID
    for _ in range(MAX_ID):
        nodes={node_id(cid,role) for role in ROLES}
        nodes.update(node_id(cid,role,index+1) for index in range(len(properties)) for role in ('get','set'))
        if cid not in used and not nodes&reserved: break
        cid = 1 + cid % MAX_ID
    else: raise ValueError('Component node identity space is exhausted')
    result = {'id': cid, 'name': name, 'properties': [dict(deepcopy(p), id=i+1) for i, p in enumerate(properties)]}
    signatures([*definitions, result])
    return result


def validate_instances(instances, definitions):
    if not isinstance(instances, dict):
        raise ValueError('Entity components must be an object')
    for key, instance in instances.items():
        if not isinstance(key, str) or not key.isascii() or not key.isdigit() or str(int(key)) != key or int(key) not in definitions:
            raise ValueError(f'Unknown component ID: {key}')
        if not isinstance(instance, dict) or type(instance.get('enabled', True)) is not bool:
            raise ValueError('Component instance requires boolean enabled')
        values = instance.get('properties', {})
        if not isinstance(values, dict):
            raise ValueError('Component properties must be an object')
        properties = {str(p['id']): p for p in definitions[int(key)]['properties']}
        for field, value in values.items():
            if field not in properties or not literal_valid(value, properties[field]['type']):
                raise ValueError(f'Invalid component property {key}.{field}')


def edit_instance(scene, eid, cid, operation, value=None, field=None):
    from .scene import entity, validate_scene
    from .prefabs import record_component_write
    result = deepcopy(scene)
    schema = signatures(result.get('component_definitions', []))[cid]
    instances = entity(result, eid).setdefault('components', {})
    key = str(cid)
    if operation == 'add':
        if key in instances:
            return validate_scene(result)
        instances.setdefault(key, {'enabled': True, 'properties': {
            str(p['id']): deepcopy(p.get('default', default_value(p['type']))) for p in schema['properties']}})
    elif operation == 'remove':
        instances.pop(key, None)
    elif key not in instances:
        raise ValueError('Entity does not have this component')
    elif operation == 'enable':
        instances[key]['enabled'] = value
    elif operation == 'set':
        instances[key].setdefault('properties', {})[str(field)] = deepcopy(value)
    else:
        raise ValueError('Unsupported component operation')
    record_component_write(result, eid, cid, operation, field)
    return validate_scene(result)
