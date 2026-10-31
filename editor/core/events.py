"""Project-defined event signatures and their stable, typed node families."""
from copy import copy, deepcopy
import re
import uuid
from .data_types import TYPES, default_value, literal_valid
from .registry import NodeSpec, Port

MIN_EVENT_ID, MAX_EVENT_ID, ROLE_STRIDE = 100_000, 199_999, 100_000
EVENT_ROLES = ('on', 'send', 'broadcast', 'subscribe', 'unsubscribe')
RESERVED = {'In','Out','Recipient','Receiver','Sender','InitiallySubscribed'}


def signatures(definitions, schema=None):
    if not isinstance(definitions,list) or len(definitions)>256:
        raise ValueError('Events must be an array of at most 256 definitions')
    result, names = {}, set()
    for event in definitions:
        if not isinstance(event,dict):
            raise ValueError('Event must be an object')
        eid,name=event.get('id'),event.get('name')
        if type(eid) is not int or not MIN_EVENT_ID<=eid<=MAX_EVENT_ID or eid in result:
            raise ValueError('Event IDs must be unique integers from 100000 to 199999')
        if (not isinstance(name,str) or not name.strip() or len(name)>128 or name.casefold() in names
            or not literal_valid(name,'string') or any(ord(c)<32 or ord(c)==127 for c in name)):
            raise ValueError('Event names must be nonempty, unique and at most 128 characters')
        parameters=event.get('parameters')
        if not isinstance(parameters,list) or len(parameters)>32:
            raise ValueError(f'{name}: parameters must be an array of at most 32 ports')
        seen=set()
        for p in parameters:
            if (not isinstance(p,dict) or not isinstance(p.get('name'),str)
                or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}',p['name'])):
                raise ValueError(f'{name}: parameter names must be identifiers')
            if p['name'] in seen or p['name'] in RESERVED:
                raise ValueError(f'{name}: duplicate or reserved parameter name {p["name"]}')
            t=p.get('type')
            if not isinstance(t,str) or (t not in TYPES and not (schema and schema.is_type(t))):
                raise ValueError(f'{name}.{p["name"]}: unsupported value type')
            if not literal_valid(p.get('default',default_value(t,schema)),t,schema):
                raise ValueError(f'{name}.{p["name"]}: invalid default value')
            seen.add(p['name'])
        result[eid]=event
        names.add(name.casefold())
    return result


def node_id(event_id, role):
    return event_id + ROLE_STRIDE * EVENT_ROLES.index(role)


def with_events(base, definitions):
    schema=getattr(base,'type_schema',None)
    events=signatures(definitions,schema)
    registry=copy(base)
    registry.nodes={key:spec for key,spec in base.nodes.items() if not spec.event_id}
    registry.event_definitions=deepcopy(definitions)
    for eid,e in events.items():
        args=tuple(Port(p['name'],p['type'],deepcopy(p.get('default',default_value(p['type'],schema)))) for p in e['parameters'])
        outputs=tuple(Port(p['name'],p['type']) for p in e['parameters'])
        for role,label,kind,inputs,results in [
            ('on','On','event',(Port('Receiver','entity',''),Port('InitiallySubscribed','bool',True)),
             (Port('Out','exec'),Port('Sender','entity'),Port('Receiver','entity'))+outputs),
            ('send','Send','emit_event',(Port('In','exec'),Port('Recipient','entity',''),Port('Sender','entity',''))+args,(Port('Out','exec'),)),
            ('broadcast','Broadcast','broadcast_event',(Port('In','exec'),Port('Sender','entity',''))+args,(Port('Out','exec'),)),
            ('subscribe','Subscribe','subscribe_event',(Port('In','exec'),Port('Recipient','entity','')),(Port('Out','exec'),)),
            ('unsubscribe','Unsubscribe','unsubscribe_event',(Port('In','exec'),Port('Recipient','entity','')),(Port('Out','exec'),))]:
            nid=node_id(eid,role)
            if nid in registry.nodes:
                raise ValueError(f'Event node ID collides with an existing node: {nid}')
            registry.nodes[nid]=NodeSpec(nid,f'{label} {e["name"]}',1,kind,inputs,results,
                                        context=True,event='custom' if role=='on' else '',event_id=eid)
    return registry


def new_event(name, parameters=(), definitions=(), *, schema=None):
    used={e['id'] for e in definitions}
    eid=MIN_EVENT_ID+uuid.uuid4().int%(MAX_EVENT_ID-MIN_EVENT_ID+1)
    while eid in used:
        eid=MIN_EVENT_ID+(eid-MIN_EVENT_ID+1)%(MAX_EVENT_ID-MIN_EVENT_ID+1)
    result={'id':eid,'name':name,'parameters':deepcopy(list(parameters))}
    signatures([*definitions,result],schema)
    return result
