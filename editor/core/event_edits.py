"""Migrate a scene event's typed payload across senders and handlers atomically."""
from copy import deepcopy
from .events import signatures,node_id,EVENT_ROLES
from .data_types import default_value,literal_valid
from .compiler import compile_graph,GraphError,Problem
from .typed_schema import build_schema
from .type_edits import definitions as type_definitions


def migrate_event_signature(document,event_id,definition,origins=None,scene=None):
    result=deepcopy(document); definitions=result.get('event_definitions',[])
    schema=build_schema(*type_definitions(document,scene or {}))
    existing=signatures(definitions,schema)
    if event_id not in existing: raise ValueError('Unknown event ID')
    old=existing[event_id]; new=deepcopy(definition)
    if new.get('id')!=event_id: raise ValueError('Editing a signature must preserve its event ID')
    definitions[definitions.index(old)]=new; signatures(definitions,schema)
    before={p['name']:p for p in old['parameters']}; after={p['name']:p for p in new['parameters']}
    origins=({name:name for name in after if name in before} if origins is None else origins)
    if (not isinstance(origins,dict) or set(origins)-after.keys()
        or any(not isinstance(v,str) or v not in before for v in origins.values())
        or len(set(origins.values()))!=len(origins)):
        raise ValueError('Each existing parameter may map to at most one new parameter')
    mapping={previous:name for name,previous in origins.items()}
    def normalized(e):
        return (e['name'],[(p['name'],p['type'],p.get('default',default_value(p['type'],schema))) for p in e['parameters']])
    if normalized(old)==normalized(new) and mapping=={name:name for name in before}:
        return deepcopy(document),dict(nodes=0,graphs=0)
    def fail(scope,nid,message): raise GraphError([Problem(f'{scope}/{nid}' if scope else str(nid),message)])
    roles={node_id(event_id,role):role for role in EVENT_ROLES}; count=0; changed_graphs=set()
    for scope,graph in [('',result)]+[(str(f['id']),f['graph']) for f in result.get('functions',[])]:
        inputs=set(); outputs=set()
        for node in graph['nodes']:
            role=roles.get(node['type'])
            if role is None: continue
            count+=1; changed_graphs.add(scope); nid=str(node['id'])
            if node.get('label')==f'{role.title()} {old["name"]}': node['label']=f'{role.title()} {new["name"]}'
            if role=='on': outputs.add(nid)
            if role not in ('send','broadcast'): continue
            inputs.add(nid); values=node.get('values',{})
            updated={k:deepcopy(v) for k,v in values.items() if k not in before}
            for name,p in before.items():
                fallback=p.get('default',default_value(p['type'],schema)); value=deepcopy(values.get(name,fallback))
                if name not in mapping:
                    if value!=fallback: fail(scope,nid,f'Cannot remove {name}: it has an authored value. Reset it before removing the parameter.')
                    continue
                replacement=after[mapping[name]]
                if not literal_valid(value,replacement['type'],schema):
                    if value!=fallback: fail(scope,nid,f'{name}: authored value is incompatible with {replacement["type"]}')
                    value=deepcopy(replacement.get('default',default_value(replacement['type'],schema)))
                updated[mapping[name]]=value
            for name,p in after.items():
                if name not in updated: updated[name]=deepcopy(p.get('default',default_value(p['type'],schema)))
            node['values']=updated
        for edge in graph['links']:
            for direction,affected in [('from',outputs),('to',inputs)]:
                nid,port=edge[direction]
                if str(nid) not in affected or port not in before: continue
                if port not in mapping: fail(scope,nid,f'Cannot remove connected parameter {port}; disconnect it first')
                edge[direction]=[nid,mapping[port]]
    compile_graph(result,scene)
    return result,dict(nodes=count,graphs=len(changed_graphs))
