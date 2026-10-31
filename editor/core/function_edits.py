"""Transactional function signature edits across a scene's gameplay and function graphs."""
from copy import deepcopy
from .functions import signatures,ENTRY,RETURN
from .data_types import default_value,literal_valid
from .compiler import compile_graph,GraphError,Problem
from .typed_schema import build_schema
from .type_edits import definitions as type_definitions


def migrate_signature(document,function_id,definition,origins=None,scene=None):
    result=deepcopy(document); functions=result.get('functions',[])
    schema=build_schema(*type_definitions(document,scene or {}))
    existing=signatures(functions,schema)
    if function_id not in existing: raise ValueError('Unknown function ID')
    old=deepcopy(existing[function_id]); new=deepcopy(definition)
    if new.get('id')!=function_id: raise ValueError('Editing a signature must preserve its function ID')
    if new.get('pure')!=old['pure']: raise ValueError('Keep the function kind; create another function to change Pure/Action')
    new['graph']=deepcopy(old['graph'])
    functions[functions.index(existing[function_id])]=new
    signatures(functions,schema)
    mappings={}
    if origins is not None and (not isinstance(origins,dict) or set(origins)-{'inputs','outputs'}):
        raise ValueError('Port origins must identify inputs and outputs')
    for side in ('inputs','outputs'):
        before={p['name']:p for p in old[side]}; after={p['name']:p for p in new[side]}
        mapping=origins.get(side,{}) if origins is not None else {name:name for name in after if name in before}
        if (not isinstance(mapping,dict) or set(mapping)-after.keys() or any(not isinstance(v,str) or v not in before for v in mapping.values())
                or len(set(mapping.values()))!=len(mapping)):
            raise ValueError('Each existing port may map to at most one new port')
        mappings[side]={previous:name for name,previous in mapping.items()}

    def normalized(f):
        return (f['name'],f['pure'],
                [(p['name'],p['type'],p.get('default',default_value(p['type'],schema))) for p in f['inputs']],
                [(p['name'],p['type']) for p in f['outputs']])
    if normalized(old)==normalized(new) and all(a==b for mapping in mappings.values() for a,b in mapping.items()) and all(
            len(mappings[side])==len(old[side]) for side in mappings):
        return deepcopy(document),dict(calls=0,graphs=0)

    def fail(scope,node,message): raise GraphError([Problem(f'{scope}/{node}' if scope else node,message)])
    def remap_values(node,side,scope):
        values=node.get('values',{}); before={p['name']:p for p in old[side]}; after={p['name']:p for p in new[side]}
        mapped=mappings[side]; updated={}
        for name,port in before.items():
            fallback=port.get('default',default_value(port['type'],schema)) if side=='inputs' else default_value(port['type'],schema)
            value=deepcopy(values.get(name,fallback))
            if name not in mapped:
                if value!=fallback: fail(scope,node['id'],f'Cannot remove {name}: it has an authored value. Reset it before removing the port.')
                continue
            replacement=after[mapped[name]]
            if not literal_valid(value,replacement['type'],schema):
                if value!=fallback: fail(scope,node['id'],f'{name}: authored value is incompatible with {replacement["type"]}')
                value=deepcopy(replacement.get('default',default_value(replacement['type'],schema)))
            updated[mapped[name]]=value
        for name,port in after.items():
            if name not in updated: updated[name]=deepcopy(port.get('default',default_value(port['type'],schema)))
        node['values']=updated

    calls=0; changed_graphs=set()
    for scope,graph in [('',result)]+[(str(f['id']),f['graph']) for f in functions]:
        incoming={}; outgoing={}
        for node in graph['nodes']:
            nid=str(node['id'])
            if node['type']==function_id:
                incoming[nid]='inputs'; outgoing[nid]='outputs'; remap_values(node,'inputs',scope)
                if node.get('label')==old['name']: node['label']=new['name']
                calls+=1; changed_graphs.add(scope)
            if scope==str(function_id):
                if node['type']==ENTRY: outgoing[nid]='inputs'
                if node['type']==RETURN: incoming[nid]='outputs'; remap_values(node,'outputs',scope)
        for link in graph['links']:
            for direction,lookup in [('from',outgoing),('to',incoming)]:
                nid,port=link[direction]; side=lookup.get(str(nid))
                if side is None or port in ('In','Out'): continue
                if port not in mappings[side]: fail(scope,str(nid),f'Cannot remove connected port {port}; disconnect it first')
                link[direction]=[nid,mappings[side][port]]
    compile_graph(result,scene)
    return result,dict(calls=calls,graphs=len(changed_graphs))
