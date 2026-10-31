"""Per-instance Switch cases; stable case IDs preserve wires through edits."""
from dataclasses import replace
from copy import deepcopy
import re
from .data_types import literal_valid
from .registry import Port


def default_cases(spec):
    values = [0, 1] if spec.data_inputs[0].type == 'int' else ['A', 'B']
    return [dict(id=f'case_{i}', value=value) for i, value in enumerate(values)]


def case_port(case):
    return 'Case ' + case['id']


def checked_cases(spec, cases):
    if not isinstance(cases, list) or len(cases) > 256:
        raise ValueError('Switch requires a list of at most 256 cases')
    ids, values = set(), set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != {'id', 'value'}:
            raise ValueError('Each Switch case needs exactly id and value')
        cid, value = case['id'], case['value']
        if not isinstance(cid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', cid) or cid in ids:
            raise ValueError('Switch case IDs must be unique identifiers of 1-64 characters')
        if not literal_valid(value, spec.data_inputs[0].type):
            raise ValueError('Switch case requires ' + spec.data_inputs[0].type)
        if value in values:
            raise ValueError('Switch case values must be unique')
        ids.add(cid); values.add(value)
    return deepcopy(cases)


def node_spec(registry, node):
    spec = registry[node['type']]
    if spec.kind != 'switch':
        if 'cases' in node:
            raise ValueError('Cases are only supported on Switch nodes')
        return spec
    cases = checked_cases(spec, node.get('cases', default_cases(spec)))
    return replace(spec, outputs=tuple(Port(case_port(c), 'exec') for c in cases) + (Port('Default', 'exec'),))
