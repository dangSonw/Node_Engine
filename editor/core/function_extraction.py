"""Extract a typed selection while retaining execution and lazy-data boundaries."""
from copy import deepcopy
import re,uuid
from .compiler import compile_graph,GraphError,Problem
from .components import with_components
from .data_types import default_value
from .functions import new_function,scoped_registry,ENTRY,RETURN
from .registry import Registry
from .switches import node_spec
from .typed_schema import with_types
from .type_edits import definitions as type_definitions


def extract_function(document,selection,name,scene=None,*,current_function=None):
    compile_graph(document,scene)
    result=deepcopy(document); definitions=result.setdefault('functions',[])
    owner=next((f for f in definitions if f['id']==current_function),None)
    if current_function is not None and owner is None: raise ValueError('Unknown containing function')
    graph=owner['graph'] if owner else result
    nodes={str(n['id']):n for n in graph['nodes']}; selected=set(map(str,selection))
    def fail(message,node='selection'):
        raise GraphError([Problem(f'{current_function}/{node}' if owner else node,message)])
    if not selected or not selected<=nodes.keys(): fail('Select existing nodes to extract')
    base=with_types(with_components(Registry(),(scene or {}).get('component_definitions',[])),*type_definitions(document,scene or {}))
    registry=scoped_registry(base,definitions,current_function,result.get('event_definitions',[]))
    schema=registry.type_schema
    specs={nid:node_spec(registry,n) for nid,n in nodes.items()}
    data_kinds={'pure','select','pure_call','struct_make','struct_break','enum_value','collection_callback'}
    if any(specs[n].kind in ('event','function_entry','return') for n in selected):
        fail('Leave event entries and Function Input/Output in their containing graph')
    actions={n for n in selected if specs[n].kind not in data_kinds}; pure=not actions
    incoming={}; outgoing={}; links=[]
    for edge in graph['links']:
        src,out=map(str,edge['from']); dst,inp=map(str,edge['to'])
        kind=next(p.type for p in specs[src].outputs if p.name==out)
        links.append((src,out,dst,inp,kind)); incoming[dst,inp]=(src,out)
        if kind=='exec': outgoing[src,out]=(dst,inp)
    external_exec=[(s,o,d,i) for s,o,d,i,t in links if t=='exec' and s not in selected and d in selected]
    exits=[(s,o,d,i) for s,o,d,i,t in links if t=='exec' and s in selected and d not in selected]
    terminals=set(); protected_ends=set(); visited=set(); entry=None
    if actions:
        targets={(d,i) for _,_,d,i in external_exec}
        if not targets:
            internal_targets={d for s,_,d,_,t in links if t=='exec' and s in actions and d in actions}
            targets={(n,'In') for n in actions-internal_targets}
        if len(targets)!=1: fail('An action function needs one execution entry; select a connected region with one entry')
        entry=next(iter(targets))
        if entry[1]!='In': fail('Include the flow node and its execution path; a control input cannot be the function entry')
        destinations={(d,i) for _,_,d,i in exits}
        if len(destinations)>1: fail('Execution exits must share one continuation; include the branch paths or extract them separately')
        walked=set()
        def walk(nid,inp,protected=False):
            if (nid,inp,protected) in walked: return
            walked.add((nid,inp,protected)); visited.add(nid)
            spec=specs[nid]
            if spec.kind=='flow' and inp!='In': return
            for port in spec.outputs:
                if port.type!='exec': continue
                nested=protected or (spec.kind in ('for','while','foreach') and port.name=='Body') or (spec.kind=='sequence' and port.name=='First')
                target=outgoing.get((nid,port.name))
                if target and target[0] in selected: walk(*target,nested)
                elif target:
                    if nested: fail('Include the whole loop Body / Sequence First path before extracting',nid)
                    terminals.add((nid,port.name))
                elif not nested: terminals.add((nid,port.name))
                else: protected_ends.add((nid,port.name))
        walk(*entry)
        if terminals & protected_ends: fail('A shared loop/sequence path cannot become an early Function Output; split that shared tail first')
        if actions-visited: fail('Selected execution nodes must all be reachable from the same entry')

    # Pure expressions used outside an action region must remain lazy in the caller.
    retained=set()
    def retain(nid):
        if nid in selected and specs[nid].kind in data_kinds and nid not in retained:
            retained.add(nid)
            for p in specs[nid].data_inputs:
                if (nid,p.name) in incoming: retain(incoming[nid,p.name][0])
    if not pure:
        for src,_,dst,_,kind in links:
            if kind!='exec' and src in selected and dst not in selected: retain(src)
    removed=selected-retained
    results=sorted({(s,o) for s,o,d,_,t in links if t!='exec' and s in removed and d not in removed})
    if pure and not results:
        used={(s,o) for s,o,d,_,t in links if t!='exec' and d in selected}
        results=sorted((n,p.name) for n in selected for p in specs[n].outputs if p.type!='exec' and (n,p.name) not in used)
    # shortcut: one pure result; expand when calls can preserve per-output laziness.
    if pure and len(results)!=1:
        fail('A pure extraction needs one exposed result to preserve lazy evaluation; extract independent results separately')
    if not pure and any(specs[n].kind in data_kinds for n,_ in results):
        fail('A lazy result must stay in its containing graph')
    # A call always returns. Preserve branches/gates that originally stopped the path.
    guarded=bool(exits) and (any(endpoint not in outgoing for endpoint in terminals)
                            or any(specs[n].kind=='flow' for n in actions))

    parameters=[]; parameter_values={}; parameter_sources={}; parameter_names={}; output_names={}
    def identifier(label,used):
        base=re.sub(r'[^A-Za-z0-9_]','_',label).strip('_')[:52] or 'Value'
        if base[0].isdigit() or base in ('In','Out'): base='Arg_'+base
        candidate=base; i=2
        while candidate in used: candidate=f'{base}_{i}'; i+=1
        return candidate
    def parameter(key,kind,value,source=None):
        if key not in parameter_names:
            label=identifier(key[0]+'_'+key[1],set(parameter_names.values()))
            parameter_names[key]=label; parameters.append(dict(name=label,type=kind,default=deepcopy(value)))
            parameter_values[label]=deepcopy(value)
            if source: parameter_sources[label]=source
        return parameter_names[key]
    outputs=[]
    for nid,port in results:
        label=identifier(nid+'_'+port,set(output_names.values())); output_names[nid,port]=label
        outputs.append(dict(name=label,type=next(p.type for p in specs[nid].outputs if p.name==port)))
    continue_port=identifier('Continue',set(output_names.values())) if guarded else None
    if guarded: outputs.append(dict(name=continue_port,type='bool'))
    # Keep original node IDs inside the new function; only boundary nodes are new.
    used_ids=set(nodes)
    def fresh(prefix):
        value=prefix+'_'+uuid.uuid4().hex
        while value in used_ids: value=prefix+'_'+uuid.uuid4().hex
        used_ids.add(value); return value
    entry_id,return_id,call_id=(fresh(prefix) for prefix in ('entry','return','call'))
    body_nodes={}; body_links=[]
    def data_source(src,out):
        spec=specs[src]
        if src in selected:
            include(src); return [src,out]
        if spec.kind in data_kinds:
            include(src); return [src,out]
        kind=next(p.type for p in spec.outputs if p.name==out)
        label=parameter((src,out),kind,default_value(kind,schema),(src,out))
        return [entry_id,label]
    def include(nid):
        if nid in body_nodes: return
        spec=specs[nid]
        if pure and (spec.context or spec.kind not in data_kinds):
            fail('Scene reads need an action function; select their consuming execution nodes too',nid)
        body_nodes[nid]=deepcopy(nodes[nid])
        for p in spec.data_inputs:
            endpoint=incoming.get((nid,p.name))
            if endpoint: source=data_source(*endpoint)
            elif nid in selected:
                value=nodes[nid].get('values',{}).get(p.name,p.default)
                source=[entry_id,parameter((nid,p.name),p.type,value)]
            else: continue
            body_links.append(dict(**{'from':source},to=[nid,p.name]))
    for nid in sorted(selected): include(nid)
    for src,out,dst,inp,kind in links:
        if kind=='exec' and src in selected and dst in selected:
            body_links.append({'from':[src,out],'to':[dst,inp]})
    boundary_nodes=[]
    if guarded:
        sequence_id,stop_id,guard_id=(fresh(prefix) for prefix in ('sequence','stop','continue'))
        boundary_nodes=[dict(id=sequence_id,type=2002,values={},position=[180,-240]),
                        dict(id=stop_id,type=RETURN,values={continue_port:False},position=[900,-240])]
        body_links += [{'from':[entry_id,'Out'],'to':[sequence_id,'In']},
                       {'from':[sequence_id,'First'],'to':list(entry)},
                       {'from':[sequence_id,'Then'],'to':[stop_id,'In']}]
    elif entry: body_links.append({'from':[entry_id,'Out'],'to':list(entry)})
    for src,out in sorted(terminals):
        if not guarded or (src,out) in outgoing: body_links.append({'from':[src,out],'to':[return_id,'In']})
    for endpoint,label in output_names.items(): body_links.append({'from':list(endpoint),'to':[return_id,label]})
    positions=[n.get('position',[0,0]) for n in body_nodes.values()]
    left=min(p[0] for p in positions); top=min(p[1] for p in positions)
    for n in body_nodes.values():
        p=n.get('position',[0,0]); n['position']=[p[0]-left+300,p[1]-top]
    definition=new_function(name,parameters,outputs,pure,definitions,schema=schema)
    definition['graph']=dict(version=1,nodes=[{'id':entry_id,'type':ENTRY,'values':{},'position':[0,0]},*body_nodes.values(),*boundary_nodes,
        {'id':return_id,'type':RETURN,'values':{continue_port:True} if guarded else {},'position':[max(p[0] for p in positions)-left+650,0]}],links=body_links)
    definitions.append(definition)
    position=[sum(nodes[n].get('position',[0,0])[axis] for n in removed)/len(removed) for axis in (0,1)]
    graph['nodes']=[n for n in graph['nodes'] if str(n['id']) not in removed]
    graph['nodes'].append(dict(id=call_id,type=definition['id'],label=name,position=position,values=parameter_values))
    graph['links']=[{'from':[s,o],'to':[d,i]} for s,o,d,i,_ in links if s not in removed and d not in removed]
    for label,endpoint in parameter_sources.items(): graph['links'].append({'from':list(endpoint),'to':[call_id,label]})
    for src,out,dst,inp,kind in links:
        if src in removed and dst not in removed and kind!='exec':
            graph['links'].append({'from':[call_id,output_names[src,out]],'to':[dst,inp]})
    for src,out,_,_ in external_exec: graph['links'].append({'from':[src,out],'to':[call_id,'In']})
    if guarded:
        graph['nodes'].append(dict(id=guard_id,type=2001,label='Continue '+name,position=[position[0]+280,position[1]],values={'Condition':False}))
        graph['links'] += [{'from':[call_id,'Out'],'to':[guard_id,'In']}, {'from':[call_id,continue_port],'to':[guard_id,'Condition']}]
    for dst,inp in sorted({(d,i) for _,_,d,i in exits}):
        graph['links'].append({'from':[guard_id,'True'] if guarded else [call_id,'Out'],'to':[dst,inp]})
    graph['nodes'].sort(key=lambda n:str(n['id'])); graph['links'].sort(key=lambda e:(e['from'],e['to']))
    compile_graph(result,scene)
    return result,dict(function_id=definition['id'],call_id=call_id,removed=sorted(removed),retained=sorted(retained),
                       copied=sorted(body_nodes.keys()-selected),pure=pure,inputs=parameters,outputs=outputs,
                       added=[call_id,guard_id] if guarded else [call_id],guarded=guarded)
