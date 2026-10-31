"""Small Python authoring API for the same documents used by the node editor."""
from .registry import Registry
from .compiler import compile_graph
from .document import empty_graph, default_scene
from .functions import scoped_registry


class GraphBuilder:
    def __init__(self, name="Gameplay", functions=(), function=None, event_definitions=(), component_definitions=(), struct_definitions=(), enum_definitions=()):
        from .components import with_components
        from .typed_schema import with_types
        self.registry = scoped_registry(with_types(with_components(Registry(), list(component_definitions)), list(struct_definitions), list(enum_definitions)), list(functions), function, list(event_definitions))
        self.graph = empty_graph()
        self.graph["name"] = name
        if functions and function is None:
            self.graph['functions'] = list(functions)
        if event_definitions and function is None:
            self.graph['event_definitions'] = list(event_definitions)
        if struct_definitions and function is None:
            self.graph['struct_definitions'] = list(struct_definitions)
        if enum_definitions and function is None:
            self.graph['enum_definitions'] = list(enum_definitions)

    def add(self, node_id, node_type, **values):
        spec = self.registry.by_name(node_type)
        cases = None
        if spec.kind == 'switch':
            from .switches import checked_cases, default_cases
            cases = checked_cases(spec, values.pop('cases', default_cases(spec)))
        if any(n["id"] == node_id for n in self.graph["nodes"]):
            raise ValueError(f"Duplicate node ID: {node_id}")
        unknown = values.keys() - {p.name for p in spec.data_inputs}
        if unknown:
            raise ValueError(f"{node_id} ({spec.name}): unknown data input(s): {', '.join(sorted(unknown))}")
        self.graph["nodes"].append({"id": node_id, "type": spec.id, "values": values})
        if cases is not None:
            self.graph['nodes'][-1]['cases'] = cases
        return node_id

    def connect(self, source, output, target, input_name):
        self.graph["links"].append({"from": [source, output], "to": [target, input_name]})
        return self

    def compile(self, scene=None):
        return compile_graph(self.graph, scene if scene is not None else default_scene(), self.registry)
