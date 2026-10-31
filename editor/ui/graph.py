"""NodeGraphQt adapter. Stable domain IDs are independent of graphics objects."""
import json
import uuid
import hashlib
from dataclasses import asdict
from copy import deepcopy
from PySide6.QtCore import QObject, Signal, Qt, QPointF
from PySide6.QtGui import QColor, QPolygonF, QUndoStack
from PySide6.QtWidgets import QApplication
from NodeGraphQt import BaseNode, NodeGraph
from NodeGraphQt.constants import PortTypeEnum
from NodeGraphQt.widgets.viewer import NodeViewer
from NodeGraphQt.qgraphics.node_abstract import AbstractNodeItem
from NodeGraphQt.qgraphics.port import PortItem
from NodeGraphQt.qgraphics.pipe import PipeItem
from editor.core.registry import Registry
from editor.core.compiler import validate, GraphError
from editor.core.scene import finite_number
from editor.core.functions import scoped_registry, ENTRY, RETURN, MIN_FUNCTION_ID
from editor.core.switches import node_spec, checked_cases, default_cases, case_port
from .theme import PIN_COLORS
from .search import SearchDialog


class GraphViewer(NodeViewer):
    port_dropped = Signal(str, str, str, QPointF)

    def cancel_connection(self):
        # NodeGraphQt detaches the visual wire before committing its undo command.
        self._start_port.hovered = False
        if self._detached_port and self._detached_port not in self._start_port.connected_ports:
            self.establish_connection(self._start_port, self._detached_port)
        self._detached_port = None
        self.end_live_connection()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self._LIVE_PIPE.isVisible():
            self.cancel_connection()
            event.accept()
            return
        super().keyPressEvent(event)

    def apply_live_connection(self, event):
        if not self._LIVE_PIPE.isVisible():
            return
        if event.button() == Qt.MouseButton.RightButton:
            self.cancel_connection()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            empty = True
            for item in self.scene().items(event.scenePos()):
                while item:
                    if item is not self._LIVE_PIPE and isinstance(item, (AbstractNodeItem, PortItem, PipeItem)):
                        empty = False
                        break
                    item = item.parentItem()
            distance = (self.mapFromScene(event.scenePos()) - self._origin_pos).manhattanLength()
            if empty and distance > QApplication.startDragDistance():
                origin = self._start_port
                identity = (origin.node.id, origin.port_type, origin.name)
                self.cancel_connection()
                self.port_dropped.emit(*identity, event.scenePos())
                return
        super().apply_live_connection(event)


def port_painter(kind):
    def paint(painter, rect, info):
        painter.save()
        painter.setPen(QColor(*info["border_color"]))
        painter.setBrush(QColor(*info["color"]))
        center = rect.center()
        x, y = center.x(), center.y()
        r = 4.5
        if kind == "exec":
            painter.drawPolygon(QPolygonF([QPointF(x-r,y-r),QPointF(x+r,y),QPointF(x-r,y+r)]))
        elif kind == "bool":
            painter.drawPolygon(QPolygonF([QPointF(x,y-r),QPointF(x+r,y),QPointF(x,y+r),QPointF(x-r,y)]))
        elif kind == 'int' or kind.startswith(('array<','map<','set<')):
            painter.drawRect(int(x-r),int(y-r),int(2*r),int(2*r))
            if kind.startswith(('array<','map<','set<')):
                painter.drawLine(QPointF(x,y-r),QPointF(x,y+r))
                if kind.startswith('map<'):
                    painter.drawLine(QPointF(x-r,y),QPointF(x+r,y))
        else:
            painter.drawEllipse(center, r, r)
            if kind in ("vec2", "vec3", "vec4", "quat", "mat4"):
                painter.setBrush(QColor("#171C25"))
                painter.drawEllipse(center, 1.5, 1.5)
        painter.restore()
    return paint


def class_name(spec):
    name=f'NodeN{-spec.id}' if spec.id<0 else f'Node{spec.id}'
    if spec.user_type or spec.id >= 700000 or spec.event_id or spec.component_id or spec.id in (ENTRY, RETURN):
        digest = hashlib.sha256(json.dumps(asdict(spec),sort_keys=True).encode()).hexdigest()[:12]
        return f'{name}_{digest}'
    return name


def node_class(spec, registry):
    def init(self):
        BaseNode.__init__(self)
        self.create_property("stable_id", uuid.uuid4().hex)
        self.create_property("type_id", spec.id)
        # Optional C++ integration hook edited by the Node Code dialog.  It is
        # kept on the domain node so save/reopen, duplicate and undo preserve it.
        self.create_property("embedded_code", "")
        if spec.kind == 'switch':
            self.create_property('switch_cases', default_cases(spec))
            self.set_port_deletion_allowed(True)
        self.set_color(35, 43, 56)
        self.set_property("text_color", (240, 243, 249), push_undo=False)
        for p in spec.data_inputs:
            self.create_property("value_" + p.name, deepcopy(p.default))
        for p in spec.inputs:
            port = self.add_input(p.name, multi_input=p.type == "exec",
                                  color=PIN_COLORS[p.type], painter_func=port_painter(p.type))
            port.view.setToolTip(f"{p.name}: {p.type}" + (' — set a constant in the Inspector' if spec.constant_inputs else ''))
            # Reject constraints are explicit for every incompatible endpoint.
            for other in registry.nodes.values():
                for out in other.outputs:
                    if out.type != p.type or spec.constant_inputs:
                        self.add_reject_port_type(port, {"port_name": out.name, "port_type": PortTypeEnum.OUT.value,
                                                       "node_type": f"obsidian.{class_name(other)}"})
        for p in (() if spec.kind == 'switch' else spec.outputs):
            port = self.add_output(p.name, multi_output=p.type != "exec",
                                   color=PIN_COLORS[p.type], painter_func=port_painter(p.type))
            port.view.setToolTip(f"{p.name}: {p.type}")
            for other in registry.nodes.values():
                for inp in other.inputs:
                    if inp.type != p.type or other.constant_inputs:
                        self.add_reject_port_type(port, {'port_name':inp.name, 'port_type':PortTypeEnum.IN.value,
                                                        'node_type':f'obsidian.{class_name(other)}'})
        if spec.kind == 'switch':
            from .switches import configure_node
            configure_node(self, self.get_property('switch_cases'), registry)
    methods = {"__identifier__": "obsidian", "NODE_NAME": spec.name, "__init__": init}
    if spec.kind == 'switch':
        def set_ports(self, data):
            from .switches import configure_node, validate_serialized_ports
            resolved=node_spec(registry,dict(type=spec.id,cases=self.get_property('switch_cases')))
            validate_serialized_ports(resolved,data)
            configure_node(self,self.get_property('switch_cases'),registry)
        methods['set_ports']=set_ports
    return type(class_name(spec), (BaseNode,), methods)


class GraphAdapter(QObject):
    changed = Signal()
    selected = Signal(object)
    diagnostic = Signal(str)

    def __init__(self, parent=None, functions=(), current_function=None, event_definitions=(), *, component_definitions=(), struct_definitions=(), enum_definitions=(), undo_stack=None):
        super().__init__(parent)
        self.registry = Registry()
        from editor.core.components import with_components
        self.registry = with_components(self.registry, list(component_definitions))
        self.functions = deepcopy(list(functions))
        self.event_definitions = deepcopy(list(event_definitions))
        self.current_function = current_function
        self.node_workflow = 'all'
        self.struct_definitions, self.enum_definitions = [], []
        self.scene_structs, self.scene_enums = deepcopy(list(struct_definitions)), deepcopy(list(enum_definitions))
        from editor.core.typed_schema import with_types
        self.registry=with_types(self.registry,self.scene_structs,self.scene_enums)
        self.registry = scoped_registry(self.registry, self.functions, current_function, self.event_definitions)
        stack = undo_stack if undo_stack is not None else QUndoStack(self)
        viewer = GraphViewer(undo_stack=stack)
        self.graph = NodeGraph(parent=self, viewer=viewer, undo_stack=stack)
        viewer.port_dropped.connect(self.search_from_port, Qt.ConnectionType.QueuedConnection)
        self._search_usage = {}
        # NodeGraphQt installs window-wide undo accelerators even when embedded.
        # The editor owns the shared graph/scene shortcuts; keep context actions
        # available but remove their competing accelerators in this adapter.
        self.graph.viewer()._undo_action.setShortcuts([])
        self.graph.viewer()._redo_action.setShortcuts([])
        self.name = "Gameplay"
        self.loading = False
        # Reset/control inputs can point back to a flow node without executing
        # its outputs. The compiler validates data and execution cycles separately.
        self.graph.set_acyclic(False)
        self.graph.set_background_color(11, 15, 21)
        self.graph.set_grid_color(29, 37, 49)
        for spec in self.registry.nodes.values():
            self.graph.register_node(node_class(spec, self.registry))
        self.graph.node_selected.connect(self.selected)
        self.graph.undo_stack().indexChanged.connect(self._changed)
        self.graph.property_changed.connect(lambda *_: self._changed())
        self.graph.port_connected.connect(lambda *_: self._changed())
        self.graph.port_disconnected.connect(lambda *_: self._changed())

    def _changed(self, *_):
        if not self.loading:
            self.changed.emit()

    def add(self, type_id, pos=None):
        if not any(spec.id == type_id for spec in self.available_specs()):
            raise ValueError('This node is unavailable in the current graph')
        self.clear_selection()
        node = self.graph.create_node(f"obsidian.{class_name(self.registry[type_id])}", pos=pos or [0, 0], selected=False)
        node.set_property('selected', True, push_undo=False)
        self.selected.emit(node)
        return node

    def clear_selection(self):
        # Selection is view state. In particular, never push onto QUndoStack
        # from inside SceneCommand.undo/redo when syncing the hierarchy.
        for node in self.graph.selected_nodes():
            node.set_property('selected', False, push_undo=False)

    def spec_for(self, node):
        data=dict(type=node.get_property('type_id'))
        if self.registry[data['type']].kind=='switch': data['cases']=node.get_property('switch_cases')
        return node_spec(self.registry,data)

    def edit_switch_cases(self, node, cases):
        from .switches import configure_node
        spec=self.registry[node.get_property('type_id')]
        if spec.kind!='switch' or node not in self.graph.all_nodes():
            raise ValueError('Select a Switch node in this graph')
        cases=checked_cases(spec,cases)
        if cases==node.get_property('switch_cases'): return node
        incoming=[(p.name(),other) for p in node.input_ports() for other in p.connected_ports()]
        outgoing=[(p.name(),other) for p in node.output_ports() for other in p.connected_ports()]
        values={p.name:deepcopy(node.get_property('value_'+p.name)) for p in spec.data_inputs}
        embedded_code=node.get_property('embedded_code') or ''
        stable_id=node.get_property('stable_id'); label=node.name(); position=list(node.pos())
        self.loading=True; self.graph.begin_undo('Edit Switch cases')
        try:
            self.graph.delete_node(node)
            replacement=self.graph.create_node(f'obsidian.{class_name(spec)}',name=label,pos=position,selected=False)
            replacement.set_property('stable_id',stable_id,push_undo=False)
            replacement.set_property('embedded_code',embedded_code,push_undo=False)
            configure_node(replacement,cases,self.registry)
            for name,value in values.items(): replacement.set_property('value_'+name,value,push_undo=False)
            for name,source in incoming:
                if source.node() is not node: replacement.inputs()[name].connect_to(source)
            for name,target in outgoing:
                if name in replacement.outputs():
                    replacement.outputs()[name].connect_to(replacement.inputs()[target.name()] if target.node() is node else target)
            self.clear_selection(); replacement.set_property('selected',True,push_undo=False)
        finally:
            self.graph.end_undo(); self.loading=False
        self.changed.emit(); self.selected.emit(replacement)
        return replacement

    def compatible_ports(self, origin):
        """Use the active graph's signatures, including its project-owned nodes."""
        node = origin.node()
        if node not in self.graph.all_nodes() or origin.locked():
            return []
        source = self.spec_for(node)
        output = origin.type_() == PortTypeEnum.OUT.value
        if not output and source.constant_inputs:
            return []
        kind = next(p.type for p in (source.outputs if output else source.inputs) if p.name == origin.name())
        matches = []
        for spec in self.suggested_specs():
            if output and spec.constant_inputs:
                continue
            for port in (spec.inputs if output else spec.outputs):
                if port.type == kind:
                    matches.append((spec, port))
        return sorted(matches, key=lambda pair: -self._search_usage.get(pair[0].id, 0))

    def add_connected(self, type_id, port_name, origin, pos):
        if not any(s.id == type_id and p.name == port_name for s, p in self.compatible_ports(origin)):
            raise ValueError('This port is no longer compatible with the current graph')
        self.graph.begin_undo('Add and connect node')
        try:
            node = self.add(type_id, pos)
            ports = node.inputs() if origin.type_() == PortTypeEnum.OUT.value else node.outputs()
            # Connect from the new endpoint so NodeGraphQt records replacement
            # of an occupied single-connection port in this same undo macro.
            ports[port_name].connect_to(origin)
        finally:
            self.graph.end_undo()
        self._search_usage[type_id] = self._search_usage.get(type_id, 0) + 1
        return node

    def search_from_port(self, node_id, direction, name, position):
        node = self.graph.get_node_by_id(node_id)
        if node is None:
            return
        origin = (node.outputs() if direction == PortTypeEnum.OUT.value else node.inputs()).get(name)
        if origin is None or origin.locked():
            return
        spec = self.spec_for(node)
        output = direction == PortTypeEnum.OUT.value
        kind = next(p.type for p in (spec.outputs if output else spec.inputs) if p.name == name)
        label = f'{kind} {"output" if output else "input"}'
        items = [(f'{s.name}  ·  {p.name}: {p.type}  ·  {self.registry.categories[s.category]}', (s.id, p.name))
                 for s, p in self.compatible_ports(origin)]
        dialog = SearchDialog(items, 'Connect ' + label, self.graph.viewer().window(),
                              hint=f'{node.name()} › {name}. Suggestions: {self.node_workflow.upper()}. Change Node Library > Node suggestions to combine workflows. Esc cancels.',
                              empty_text=f'No compatible nodes for {label}. Clear the search or press Esc.')
        def finished(result):
            if result == SearchDialog.DialogCode.Accepted:
                try:
                    self.add_connected(*dialog.result_value, origin, [position.x(), position.y()])
                except ValueError as error:
                    self.diagnostic.emit(str(error))
            self.graph.viewer().setFocus()
            dialog.deleteLater()
        dialog.finished.connect(finished)
        dialog.open()

    def document(self):
        nodes, links = [], []
        for node in self.graph.all_nodes():
            spec = self.registry[node.get_property("type_id")]
            nid = node.get_property("stable_id")
            nodes.append({"id": nid, "type": spec.id, "values": {
                p.name: node.get_property("value_" + p.name) for p in spec.data_inputs},
                "position": node.pos(), "label": node.name()})
            if node.get_property("embedded_code"):
                nodes[-1]["code"] = node.get_property("embedded_code")
            if spec.kind == 'switch':
                nodes[-1]['cases'] = deepcopy(node.get_property('switch_cases'))
            for port in node.output_ports():
                for target in port.connected_ports():
                    links.append({"from": [nid, port.name()],
                                  "to": [target.node().get_property("stable_id"), target.name()]})
        result = {"version": 1, "name": self.name, "nodes": sorted(nodes, key=lambda n: n["id"]),
                  "links": sorted(links, key=lambda l: (l["from"], l["to"]))}
        if self.current_function is None and self.functions:
            result['functions'] = deepcopy(self.functions)
        if self.current_function is None and self.event_definitions:
            result['event_definitions'] = deepcopy(self.event_definitions)
        if self.current_function is None and self.struct_definitions:
            result['struct_definitions'] = deepcopy(self.struct_definitions)
        if self.current_function is None and self.enum_definitions:
            result['enum_definitions'] = deepcopy(self.enum_definitions)
        return result

    def configure_functions(self, definitions, event_definitions=None):
        if event_definitions is not None:
            self.event_definitions = deepcopy(event_definitions)
        configured = scoped_registry(self.registry, definitions, self.current_function, self.event_definitions)
        self.registry.nodes = configured.nodes
        self.registry.event_definitions = configured.event_definitions
        self.functions = deepcopy(definitions)
        registered = set(self.graph.registered_nodes())
        for spec in self.registry.nodes.values():
            if f'obsidian.{class_name(spec)}' not in registered:
                self.graph.register_node(node_class(spec, self.registry))

    def available_specs(self, registry=None, definitions=None):
        registry = registry if registry is not None else self.registry
        definitions = definitions if definitions is not None else self.functions
        for spec in registry.nodes.values():
            if self.current_function is None and spec.kind in ('function_entry','return'):
                continue
            if self.current_function is not None:
                f = next(f for f in definitions if f['id']==self.current_function)
                if spec.kind in ('event','function_entry') or spec.id==self.current_function:
                    continue
                if f['pure'] and (spec.context or spec.kind not in ('pure','select','pure_call','struct_make','struct_break','enum_value','collection_callback','return')):
                    continue
            yield spec

    def suggested_specs(self):
        for spec in self.available_specs():
            if self.node_workflow == 'all' or spec.workflow in ('shared', self.node_workflow):
                yield spec

    def configure_components(self, definitions):
        from editor.core.components import with_components
        self.registry = with_components(self.registry, definitions)
        self.configure_functions(self.functions)

    def load(self, doc, *, component_definitions=None, struct_definitions=None, enum_definitions=None, clear_history=True):
        from editor.core.typed_schema import with_types
        scene_structs = self.scene_structs if struct_definitions is None else struct_definitions
        scene_enums = self.scene_enums if enum_definitions is None else enum_definitions
        structs = list({d['name']:d for d in list(scene_structs)+doc.get('struct_definitions',[])}.values())
        enums = list({d['name']:d for d in list(scene_enums)+doc.get('enum_definitions',[])}.values())
        definitions = doc.get('functions', []) if self.current_function is None else self.functions
        events = doc.get('event_definitions', []) if self.current_function is None else self.event_definitions
        registry = scoped_registry(with_types(self.registry, structs, enums), definitions, self.current_function, events)
        if component_definitions is not None:
            from editor.core.components import with_components
            registry = with_components(registry, component_definitions)
        errors = validate(doc, registry)
        from editor.core.compiler import Problem
        allowed = {spec.id for spec in self.available_specs(registry, definitions)}
        # Function Input is structural and can only be restored by loading.
        if self.current_function is not None: allowed.add(ENTRY)
        for data in doc.get('nodes', []):
            if isinstance(data, dict) and data.get('type') not in allowed:
                errors.append(Problem(str(data.get('id', '')), 'Node is unavailable in the current graph'))
        if self.current_function is None:
            for f in definitions:
                errors.extend(Problem(f'{f["id"]}/{p.node}',p.message)
                              for p in validate(f.get('graph'),scoped_registry(registry,definitions,f['id'])))
        if errors:
            raise GraphError(errors)
        self.loading = True
        try:
            if clear_history: self.graph.clear_session()
            elif self.graph.all_nodes(): raise ValueError('Preserving history requires an empty graph')
            self.registry = registry
            self.scene_structs, self.scene_enums = deepcopy(scene_structs), deepcopy(scene_enums)
            self.struct_definitions = deepcopy(doc.get('struct_definitions', []))
            self.enum_definitions = deepcopy(doc.get('enum_definitions', []))
            if component_definitions is not None:
                self.configure_components(component_definitions)
            self.configure_functions(definitions, events)
            self.name = doc.get("name", "Gameplay")
            mapping = {}
            for i, data in enumerate(doc["nodes"]):
                n = self.graph.create_node(f"obsidian.{class_name(self.registry[data['type']])}", name=data.get("label"),
                                           pos=data.get("position", [(i % 5)*260, (i//5)*200]),
                                           selected=False, push_undo=False)
                n.set_property("stable_id", str(data["id"]), push_undo=False)
                n.set_property("embedded_code", data.get("code", ""), push_undo=False)
                if self.registry[data['type']].kind == 'switch':
                    from .switches import configure_node
                    configure_node(n,data.get('cases',default_cases(self.registry[data['type']])),self.registry)
                for p in self.registry[data["type"]].data_inputs:
                    n.set_property("value_" + p.name, deepcopy(data.get("values", {}).get(p.name, p.default)),
                                   push_undo=False)
                mapping[str(data["id"])] = n
            for link in doc["links"]:
                src, out = link["from"]
                dst, inp = link["to"]
                mapping[str(src)].outputs()[out].connect_to(mapping[str(dst)].inputs()[inp], push_undo=False)
            if clear_history: self.graph.undo_stack().clear()
            self.clear_selection()
            self.graph.fit_to_selection()
        finally:
            self.loading = False

    def focus(self, nid):
        nodes = [n for n in self.graph.all_nodes() if n.get_property("stable_id") == nid]
        if nodes:
            self.clear_selection()
            nodes[0].set_property('selected', True, push_undo=False)
            self.graph.center_on(nodes)
            self.selected.emit(nodes[0])

    def duplicate(self):
        self.graph.begin_undo("Duplicate selection")
        try:
            copies = self.graph.duplicate_nodes(self.graph.selected_nodes())
            for n in copies or []:
                n.set_property("stable_id", uuid.uuid4().hex)
        finally:
            self.graph.end_undo()

    def paste(self):
        # NodeGraphQt keeps registered classes after switching projects. Validate
        # against the current definitions before it can instantiate stale classes.
        try:
            data=json.loads(QApplication.clipboard().text())
            nodes=data['nodes']
            if not isinstance(nodes,dict) or not nodes:
                return
            available={s.id for s in self.available_specs()}
            domain={'version':1,'nodes':[],'links':[]}
            ids={key:f'paste_{i}' for i,key in enumerate(nodes)}
            for key,node in nodes.items():
                custom=node['custom']
                position=node.get('pos',[0,0])
                if not isinstance(position,list) or len(position)!=2 or not all(finite_number(x) for x in position):
                    raise ValueError('A copied node has an invalid position')
                node['pos']=position
                tid=custom['type_id']
                if type(tid) is not int or tid not in available:
                    raise ValueError('A copied node is unavailable in this project or function')
                spec=self.registry[tid]
                if node.get('port_deletion_allowed') and spec.kind != 'switch':
                    raise ValueError('Copied nodes must use their declared ports')
                if node['type_']!=f'obsidian.{class_name(spec)}':
                    raise ValueError('A copied node has a different signature in this project')
                domain['nodes'].append({'id':ids[key],'type':tid,'values':{
                    p.name:custom.get('value_'+p.name,p.default) for p in spec.data_inputs},
                    **({'code': custom.get('embedded_code', '')} if custom.get('embedded_code') else {})})
                if spec.kind == 'switch':
                    from .switches import validate_serialized_ports
                    domain['nodes'][-1]['cases']=checked_cases(spec,custom['switch_cases'])
                    if node.get('port_deletion_allowed') is not True:
                        raise ValueError('Copied Switch requires its declared dynamic ports')
                    validate_serialized_ports(node_spec(self.registry,domain['nodes'][-1]),node)
            connections=[]
            for link in data.get('connections',[]):
                src,out=link['out']; dst,inp=link['in']
                if src in ids and dst in ids:
                    domain['links'].append({'from':[ids[src],out],'to':[ids[dst],inp]})
                    connections.append(link)
            problems=validate(domain,self.registry)
            if problems:
                raise GraphError(problems)
        except (ValueError,TypeError,KeyError,AttributeError) as error:
            self.diagnostic.emit(f'Cannot paste nodes: {error}')
            return
        self.graph.begin_undo("Paste selection")
        try:
            self.clear_selection()
            # Do not import another graph's connection constraints or settings.
            copies=self.graph._deserialize({'nodes':nodes,'connections':connections},
                                            relative_pos=True,adjust_graph_style=False)
            for n,original in zip(copies,nodes.values()):
                # The library moves pasted views after recording NodeAddedCmd.
                # Record that offset too so Redo restores the pasted position.
                position=list(n.pos())
                n.set_property('pos',original['pos'],push_undo=False)
                n.set_pos(*position)
                n.set_property("stable_id", uuid.uuid4().hex)
                n.set_property('selected',True,push_undo=False)
        finally:
            self.graph.end_undo()
