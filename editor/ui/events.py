"""Event creation and payload signature edits share the graph's Undo history."""
from copy import deepcopy
from PySide6.QtGui import QUndoCommand
from .functions import FunctionSignatureDialog,apply_function_graph_edit
from editor.core.events import node_id,EVENT_ROLES


class EventSignatureDialog(FunctionSignatureDialog):
    def __init__(self, definitions, parent=None, *, event_id=None, validator=None, schema=None):
        super().__init__(definitions,parent,event_mode=True,function_id=event_id,validator=validator,schema=schema)


def apply_event_signature_edit(window,after,event_id):
    family={node_id(event_id,role) for role in EVENT_ROLES}
    changed={n['id'] for n in after['nodes'] if n['type'] in family}
    apply_function_graph_edit(window,after,changed,changed,'Edit event signature')


class EventsCommand(QUndoCommand):
    def __init__(self,window,definitions,label='Define event'):
        super().__init__(label)
        self.window=window
        self.before=deepcopy(window.adapter.event_definitions)
        self.after=deepcopy(definitions)

    def redo(self):
        self.window.apply_events(self.after)

    def undo(self):
        self.window.apply_events(self.before)
