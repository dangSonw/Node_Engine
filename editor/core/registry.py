from dataclasses import dataclass
from pathlib import Path
from copy import deepcopy
import yaml

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Port:
    name: str
    type: str
    default: object = None


@dataclass(frozen=True)
class NodeSpec:
    id: int
    name: str
    category: int
    kind: str
    inputs: tuple[Port, ...]
    outputs: tuple[Port, ...]
    function: str = ""
    context: bool = False
    event: str = ""
    variable_type: str = ""
    variable_access: str = ""
    function_id: int = 0
    event_id: int = 0
    component_id: int = 0
    component_operation: str = ''
    component_field: int = 0
    variable_scope: str = ''
    user_type: str = ''
    workflow: str = 'shared'
    collection_type: str = ''
    collection_operation: str = ''

    @property
    def data_inputs(self):
        return tuple(p for p in self.inputs if p.type != "exec")

    @property
    def constant_inputs(self):
        return self.event in ('timer', 'custom', 'persistence', 'scene_failure', 'physics', 'animation_finished', 'animation_notify', 'entity_lifecycle', 'input') or self.event.startswith('ui_')


class Registry:
    def __init__(self, path=None):
        data = yaml.safe_load(Path(path or ROOT / "nodes/registry.yaml").read_text("utf-8"))
        self.categories = data["categories"]
        self.nodes = {}
        self.event_definitions = []
        self.component_definitions = []
        definitions = list(data["nodes"])
        for family in data.get('families', []):
            for type_name in family['types']:
                variant = dict(data['type_variants'][type_name], type=type_name)
                def expand(value):
                    if isinstance(value, dict):
                        return {k: expand(v) for k, v in value.items()}
                    if isinstance(value, list):
                        return [expand(v) for v in value]
                    if value == '$default':
                        return deepcopy(variant['default'])
                    return value.format_map(variant) if isinstance(value, str) else value
                for template in family['nodes']:
                    definition = expand(template)
                    definition['id'] = template['id'] + variant['offset']
                    definitions.append(definition)
        for n in definitions:
            n = dict(n)
            for side in ("inputs", "outputs"):
                n[side] = tuple(Port(**p) for p in n.get(side, []))
            spec = NodeSpec(**n)
            if spec.workflow not in ('shared', '2d', '3d'):
                raise ValueError(f'Unknown node workflow: {spec.workflow}')
            if spec.id in self.nodes:
                raise ValueError(f"Duplicate stable node type ID {spec.id}")
            self.nodes[spec.id] = spec

    def __getitem__(self, key):
        return self.nodes[int(key)]

    def by_name(self, name):
        return next(n for n in self.nodes.values() if n.name == name)
