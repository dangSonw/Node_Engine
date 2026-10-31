"""Literal and scene-variable types shared by the compiler and authoring UI."""
from copy import deepcopy
import math

SCALARS = ('float', 'int', 'bool', 'string', 'vec3', 'vec2', 'vec4', 'quat', 'mat4', 'entity')
COLLECTIONS = ('array', 'map', 'set')
TYPES = SCALARS + tuple(f'{kind}<{t}>' for kind in COLLECTIONS for t in SCALARS)
MAX_COLLECTION = 65536
MAX_STRING = 1048576
INT_MIN, INT_MAX = -(2**63), 2**63 - 1


def element_type(type_name, kind):
    prefix = kind + '<'
    return type_name[len(prefix):-1] if type_name.startswith(prefix) and type_name.endswith('>') else None


def literal_valid(value, type_name, schema=None):
    if type_name == 'float':
        try:
            return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        except OverflowError:
            return False
    if type_name == 'int':
        return isinstance(value, int) and not isinstance(value, bool) and INT_MIN <= value <= INT_MAX
    if type_name == 'bool':
        return isinstance(value, bool)
    if type_name in ('string', 'entity'):
        return isinstance(value, str) and not any(0xD800 <= ord(c) <= 0xDFFF for c in value) and len(value.encode('utf-8')) <= MAX_STRING
    if type_name in ('vec2', 'vec3', 'vec4', 'quat', 'mat4'):
        size = {'vec2': 2, 'vec3': 3, 'vec4': 4, 'quat': 4, 'mat4': 16}[type_name]
        return isinstance(value, list) and len(value) == size and all(literal_valid(v, 'float') for v in value)
    if schema is not None and type_name not in TYPES:
        return schema.literal_valid(value, type_name)
    if type_name.startswith('struct:'):
        return isinstance(value, dict)
    if type_name.startswith('enum:'):
        return isinstance(value, (str, int)) and not isinstance(value, bool)
    if t := element_type(type_name, 'array'):
        return (t in SCALARS or t.startswith(('struct:', 'enum:'))) and isinstance(value, list) and len(value) <= MAX_COLLECTION and all(literal_valid(v, t, schema) for v in value)
    if t := element_type(type_name, 'map'):
        return (t in SCALARS or t.startswith(('struct:', 'enum:'))) and isinstance(value, dict) and len(value) <= MAX_COLLECTION and all(
            literal_valid(k, 'string') and literal_valid(v, t, schema) for k, v in value.items())
    if t := element_type(type_name, 'set'):
        if not (t in SCALARS or t.startswith(('struct:', 'enum:'))) or not isinstance(value, list) or len(value) > MAX_COLLECTION:
            return False
        return all(literal_valid(item, t, schema) for item in value) and all(
            not any(item == previous for previous in value[:index]) for index, item in enumerate(value))
    return False


def default_value(type_name, schema=None):
    if type_name.startswith('array<'):
        return []
    if type_name.startswith('map<'):
        return {}
    if type_name.startswith('set<'):
        return []
    if schema is not None and type_name.startswith(('struct:', 'enum:')):
        return schema.default_value(type_name)
    if type_name.startswith('struct:'):
        return {}
    if type_name.startswith('enum:'):
        return ''
    return deepcopy({'float': 0.0, 'int': 0, 'bool': False, 'string': '',
                     'vec2': [0.0, 0.0], 'vec3': [0.0, 0.0, 0.0],
                     'vec4': [0.0, 0.0, 0.0, 0.0], 'quat': [0.0, 0.0, 0.0, 1.0],
                     'mat4': [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0,
                              0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0],
                     'entity': ''}[type_name])


def variable(value, schema=None):
    """Legacy numbers remain float variables; all other types are explicit."""
    if literal_valid(value, 'float'):
        return 'float', value
    if isinstance(value, dict) and set(value) == {'type', 'value'}:
        t = value['type']
        if isinstance(t, str) and (t in TYPES or (schema is not None and schema.is_type(t))) and literal_valid(value['value'], t, schema):
            return t, value['value']
    raise ValueError('Variable requires a finite number or a valid {type, value} declaration')


def variable_name_valid(name):
    return isinstance(name, str) and bool(name.strip()) and '\0' not in name and literal_valid(name, 'string') and len(name.encode('utf-8')) <= 512


def declaration(type_name, value, schema=None):
    if not literal_valid(value, type_name, schema):
        raise ValueError(f'Expected {type_name}')
    return deepcopy(value) if type_name == 'float' else {'type': type_name, 'value': deepcopy(value)}
