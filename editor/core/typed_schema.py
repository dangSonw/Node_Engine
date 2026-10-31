"""User defined structs, enums and variable scope metadata.

The core scalar/collection type list stays stable for old graphs.  This module
adds project owned value types without making JSON documents depend on Python
classes or on a particular editor widget.
"""
from copy import deepcopy
import re

from .data_types import SCALARS, TYPES, default_value, literal_valid, element_type
from .registry import NodeSpec, Port

IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
SCOPES = ("global", "scene", "entity")


def _type_ok(type_name, names):
    if type_name in TYPES: return True
    for kind in ('array','map','set'):
        item=element_type(type_name,kind)
        if item: return (item.startswith('struct:') and item[7:] in names[0]) or (item.startswith('enum:') and item[5:] in names[1])
    return \
        (type_name.startswith("struct:") and type_name[7:] in names[0]) or \
        (type_name.startswith("enum:") and type_name[5:] in names[1])


class TypeSchema:
    def __init__(self, structs=(), enums=()):
        self.structs = {d["name"]: d for d in structs}
        self.enums = {d["name"]: d for d in enums}

    def is_type(self, type_name):
        return isinstance(type_name, str) and _type_ok(type_name, (self.structs, self.enums))

    def type_names(self):
        named=['struct:'+n for n in self.structs]+['enum:'+n for n in self.enums]
        return list(TYPES)+named+[f'{kind}<{t}>' for t in named for kind in ('array','map','set')]

    def enum_names(self, name):
        definition = self.enums[name]
        return [v if isinstance(v, str) else v["name"] for v in definition["values"]]

    def default_value(self, type_name):
        if type_name.startswith("struct:"):
            definition = self.structs[type_name[7:]]
            return {field["name"]: deepcopy(field["default"] if "default" in field else default_value(field["type"], self))
                    for field in definition["fields"]}
        if type_name.startswith("enum:"):
            names = self.enum_names(type_name[5:])
            return names[0] if names else ""
        return default_value(type_name, self)

    def literal_valid(self, value, type_name, depth=0):
        if depth > 32 or not self.is_type(type_name):
            return False
        if type_name in TYPES:
            return literal_valid(value, type_name)
        for kind in ('array','map','set'):
            item=element_type(type_name,kind)
            if item:
                if not isinstance(value,dict if kind=='map' else list) or len(value)>65536: return False
                if kind=='map':
                    return all(literal_valid(k,'string') and self.literal_valid(v,item,depth+1) for k,v in value.items())
                return all(self.literal_valid(v,item,depth+1) for v in value) and (kind!='set' or all(v not in value[:i] for i,v in enumerate(value)))
        if type_name.startswith("struct:"):
            definition = self.structs[type_name[7:]]
            if not isinstance(value, dict) or set(value) != {f["name"] for f in definition["fields"]}:
                return False
            return all(self.literal_valid(value[f["name"]], f["type"], depth + 1) for f in definition["fields"])
        if type_name.startswith("enum:"):
            return isinstance(value, str) and value in self.enum_names(type_name[5:])
        return literal_valid(value, type_name)


def build_schema(structs=(), enums=()):
    if not isinstance(structs, list) or len(structs) > 256:
        raise ValueError("Struct definitions require an array of at most 256 definitions")
    if not isinstance(enums, list) or len(enums) > 256:
        raise ValueError("Enum definitions require an array of at most 256 definitions")
    structs, enums = deepcopy(structs), deepcopy(enums)
    names = (set(), set())
    for collection, kind, slot in ((structs, "Struct", 0), (enums, "Enum", 1)):
        for definition in collection:
            if not isinstance(definition, dict) or not isinstance(definition.get("name"), str) or not IDENTIFIER.fullmatch(definition["name"]):
                raise ValueError(f"{kind} names must be identifiers")
            name = definition["name"]
            if name in names[slot] or name in names[1 - slot]:
                raise ValueError(f"Duplicate user type name: {name}")
            names[slot].add(name)
            if kind == "Struct":
                fields = definition.get("fields")
                if not isinstance(fields, list) or not 1 <= len(fields) <= 64:
                    raise ValueError(f"{name}: structs require 1 to 64 fields")
                fields_seen = set()
                for field in fields:
                    if not isinstance(field, dict) or not isinstance(field.get("name"), str) or not IDENTIFIER.fullmatch(field["name"]) or field["name"] in fields_seen:
                        raise ValueError(f"{name}: field names must be unique identifiers")
                    if not isinstance(field.get("type"), str):
                        raise ValueError(f"{name}.{field.get('name')}: missing field type")
                    fields_seen.add(field["name"])
            else:
                values = definition.get("values")
                if not isinstance(values, list) or not 1 <= len(values) <= 256:
                    raise ValueError(f"{name}: enums require 1 to 256 values")
                seen = set()
                for value in values:
                    label = value if isinstance(value, str) else value.get("name") if isinstance(value, dict) else None
                    if not isinstance(label, str) or not IDENTIFIER.fullmatch(label) or label in seen:
                        raise ValueError(f"{name}: enum values must be unique identifiers")
                    if isinstance(value, dict) and (type(value.get("value", 0)) is not int or not -2**31 <= value.get("value", 0) <= 2**31 - 1):
                        raise ValueError(f"{name}.{label}: enum value must be a signed 32-bit integer")
                    seen.add(label)
    schema = TypeSchema(structs, enums)
    used_nodes, used_variables = set(), set()
    for index, definition in enumerate(structs + enums):
        legacy_node = 700000 + index*2 if index < len(structs) else 700000 + len(structs)*2 + index-len(structs)
        nid = definition.get('node_id', legacy_node)
        vid = definition.get('variable_id', 800000 + index*16)
        if type(nid) is not int or not 700000 <= nid < 800000 or (index < len(structs) and nid == 799999):
            raise ValueError('User type node_id must be an integer in the reserved type range')
        if type(vid) is not int or not 800000 <= vid < 900000 or (vid-800000)%16:
            raise ValueError('User type variable_id must identify an aligned variable family')
        node_ids = {nid, nid+1} if index < len(structs) else {nid}
        if used_nodes & node_ids or vid in used_variables:
            raise ValueError('Duplicate user type node identity')
        used_nodes.update(node_ids); used_variables.add(vid)
    visiting, done = set(), set()
    def visit(name):
        if name in visiting:
            raise ValueError(f"Recursive Struct definition: {name}")
        if name in done:
            return
        visiting.add(name)
        for field in schema.structs[name]['fields']:
            target=field['type']
            for kind in ('array','map','set'): target=element_type(target,kind) or target
            if target.startswith('struct:') and target[7:] in schema.structs: visit(target[7:])
        visiting.remove(name)
        done.add(name)
    for name in schema.structs:
        visit(name)
    for definition in structs:
        for field in definition["fields"]:
            if not schema.is_type(field["type"]):
                raise ValueError(f"{definition['name']}.{field['name']}: unsupported type {field['type']}")
            value = field["default"] if "default" in field else schema.default_value(field["type"])
            if not schema.literal_valid(value, field["type"]):
                raise ValueError(f"{definition['name']}.{field['name']}: invalid default value")
            field["default"] = deepcopy(value)
    return schema


def validate_variable(value, schema):
    if literal_valid(value, 'float'):
        return "float", value
    if isinstance(value, dict) and set(value) == {"type", "value"}:
        type_name = value["type"]
        if schema.is_type(type_name) and schema.literal_valid(value["value"], type_name):
            return type_name, value["value"]
    raise ValueError("Variable requires a finite number or a valid typed declaration")


def with_types(base, structs=(), enums=()):
    """Add project-owned Make/Break Struct and Enum value nodes to a registry."""
    schema = build_schema(deepcopy(list(structs)), deepcopy(list(enums)))
    from copy import copy
    registry = copy(base)
    registry.nodes = {key: value for key, value in base.nodes.items() if not value.user_type}
    for index,definition in enumerate(schema.structs.values()):
        name = definition["name"]
        value_type = f"struct:{name}"
        next_id = definition.get('node_id', 700000+index*2)
        fields = tuple(Port(f["name"], f["type"], deepcopy(f["default"])) for f in definition["fields"])
        for nid in (next_id,next_id+1):
            if nid in registry.nodes: raise ValueError(f'User type node ID collides with another node: {nid}')
        registry.nodes[next_id] = NodeSpec(next_id, f"Make {name}", 3, "struct_make", fields, (Port("Value", value_type),), user_type=value_type)
        registry.nodes[next_id + 1] = NodeSpec(next_id + 1, f"Break {name}", 3, "struct_break", (Port("Value", value_type, schema.default_value(value_type)),), fields, user_type=value_type)
    for index,definition in enumerate(schema.enums.values()):
        name = definition["name"]
        value_type = f"enum:{name}"
        next_id = definition.get('node_id', 700000+len(schema.structs)*2+index)
        values = schema.enum_names(name)
        if next_id in registry.nodes: raise ValueError(f'User type node ID collides with another node: {next_id}')
        registry.nodes[next_id] = NodeSpec(next_id, f"Make {name}", 3, "enum_value", (Port("Value", "string", values[0]),), (Port("Value", value_type),), user_type=value_type)
    for index, (name, value_type) in enumerate(
            [(n, 'struct:'+n) for n in schema.structs] + [(n, 'enum:'+n) for n in schema.enums]):
        for scope_index, scope in enumerate(('', 'global', 'scene', 'entity')):
            definition = schema.structs.get(name, schema.enums.get(name))
            nid = definition.get('variable_id', 800000 + index*16) + scope_index*2
            if nid in registry.nodes or nid+1 in registry.nodes:
                raise ValueError(f'User variable node ID collides with another node: {nid}')
            label = (scope.title()+' ' if scope else '') + name
            owner = (Port('Entity', 'entity', 'player'),) if scope == 'entity' else ()
            inputs = owner + (Port('Name', 'string', name.lower()),)
            options = dict(context=True, variable_type=value_type, variable_scope=scope, user_type=value_type)
            registry.nodes[nid] = NodeSpec(nid, f'Get {label} Variable', 3, 'pure', inputs,
                                          (Port('Value', value_type),), function='GetUserVariable', variable_access='get', **options)
            registry.nodes[nid+1] = NodeSpec(nid+1, f'Set {label} Variable', 3, 'action',
                (Port('In', 'exec'),)+inputs+(Port('Value', value_type, schema.default_value(value_type)),),
                (Port('Out', 'exec'),), function='SetUserVariable', variable_access='set', **options)
    registry.type_schema = schema
    from .user_collections import collection_specs
    for spec in collection_specs(schema,base):
        if spec.id in registry.nodes: raise ValueError(f'User collection node ID collision: {spec.id}')
        registry.nodes[spec.id]=spec
    return registry
