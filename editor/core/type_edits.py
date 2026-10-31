"""Transactional user-type authoring, stable node identities and value migrations."""
from copy import deepcopy
from .typed_schema import build_schema, with_types
from .registry import Registry
from .data_types import default_value, literal_valid, element_type


def definitions(graph, scene):
    return tuple(list({d['name']:d for d in scene.get(key,[])+graph.get(key,[])}.values())
                 for key in ('struct_definitions','enum_definitions'))


def stable_definitions(structs, enums):
    build_schema(structs,enums)
    structs,enums=deepcopy(structs),deepcopy(enums)
    for index,d in enumerate(structs+enums):
        legacy=700000+index*2 if index<len(structs) else 700000+len(structs)*2+index-len(structs)
        d.setdefault('node_id',legacy); d.setdefault('variable_id',800000+index*16)
    build_schema(structs,enums)
    return structs,enums


def edit_type(graph, scene, kind, definition=None, *, original=None, origins=None, reserved_nodes=()):
    from .compiler import compile_graph
    from .components import with_components
    from .functions import scoped_registry
    if kind not in ('struct','enum'): raise ValueError('Expected struct or enum')
    graph,scene=deepcopy(graph),deepcopy(scene)
    structs,enums=stable_definitions(*definitions(graph,scene))
    old_schema=build_schema(structs,enums)
    base=with_components(Registry(),scene.get('component_definitions',[]))
    registry=scoped_registry(with_types(base,structs,enums),graph.get('functions',[]),event_definitions=graph.get('event_definitions',[]))
    group=structs if kind=='struct' else enums
    old=next((d for d in group if d['name']==original),None) if original is not None else None
    if original is not None and old is None: raise ValueError('Unknown user type: '+original)
    retired=deepcopy(scene.get('retired_type_ids',dict(nodes=[],variables=[])))
    if not isinstance(retired,dict) or set(retired)!={'nodes','variables'} or any(
        not isinstance(v,list) or len(v)>100000 or any(type(n) is not int for n in v) for v in retired.values()):
        raise ValueError('Invalid retired type identities')
    if definition is None and old is None: raise ValueError('Choose a type to delete')
    new=deepcopy(definition)
    if new is not None:
        if old:
            new['node_id'],new['variable_id']=old['node_id'],old['variable_id']
        else:
            used=set(registry.nodes)|set(retired['nodes'])|set(reserved_nodes)
            new['node_id']=next((n for n in range(700000,799999,2) if n not in used and n+1 not in used),None)
            used_variables=set(retired['variables'])|{d['variable_id'] for d in structs+enums}
            new['variable_id']=next((n for n in range(800000,900000,16)
                if n not in used_variables and not set(range(n,n+8))&used),None)
            if new['node_id'] is None or new['variable_id'] is None: raise ValueError('User type identity space is exhausted')
    old_type=kind+':'+old['name'] if old else None
    new_type=kind+':'+new['name'] if new else None
    if old:
        group.remove(old)
        if new is not None: group.insert((list(old_schema.structs) if kind=='struct' else list(old_schema.enums)).index(original),new)
    elif new is not None: group.append(new)

    def renamed(t):
        if old_type and t==old_type and new_type: return new_type
        for kind in ('array','map','set'):
            item=element_type(t,kind)
            if item: return f'{kind}<{renamed(item)}>'
        return t
    if new_type:
        for d in structs:
            for field in d['fields']: field['type']=renamed(field['type'])
    if old and new and kind=='struct':
        before={f['name']:f for f in old['fields']}
        origins=origins if origins is not None else {f['name']:f['name'] for f in new['fields'] if f['name'] in before}
        if set(origins)-{f['name'] for f in new['fields']} or any(v not in before for v in origins.values()) or len(set(origins.values()))!=len(origins):
            raise ValueError('Field origins must identify distinct existing fields')
        field_names={v:k for k,v in origins.items()}
    else: field_names={}
    if old and new and kind=='enum':
        labels=old_schema.enum_names(original)
        new_labels=[v if isinstance(v,str) else v['name'] for v in new['values']]
        origins=origins if origins is not None else {n:n for n in new_labels if n in labels}
        if set(origins)-set(new_labels) or any(v not in labels for v in origins.values()) or len(set(origins.values()))!=len(origins):
            raise ValueError('Enum origins must identify distinct existing labels')
        enum_names={v:k for k,v in origins.items()}
    else: enum_names={}

    def value(t,v):
        for collection_kind in ('array','map','set'):
            item=element_type(t,collection_kind)
            if item:
                if item==old_type and new is None: raise ValueError('Cannot delete a referenced collection element type: '+original)
                mapped={k:value(item,x) for k,x in v.items()} if collection_kind=='map' else [value(item,x) for x in v]
                if collection_kind=='set' and any(x in mapped[:i] for i,x in enumerate(mapped)):
                    raise ValueError('Type edit would merge distinct set elements')
                return mapped
        if t==old_type and new is None: raise ValueError('Cannot delete a referenced type: '+original)
        if t==old_type and kind=='enum':
            if v not in enum_names: raise ValueError('Cannot remove a used enum label: '+str(v))
            return enum_names[v]
        if t.startswith('struct:') and t[7:] in old_schema.structs:
            fields=old_schema.structs[t[7:]]['fields']
            if t==old_type and new is not None:
                result={}
                for f in new['fields']:
                    source=origins.get(f['name'])
                    if source is None:
                        result[f['name']]=deepcopy(f.get('default',default_value(f['type'],old_schema)))
                        continue
                    previous=next(p for p in fields if p['name']==source)
                    saved=value(previous['type'],v[source])
                    if not literal_valid(saved,f['type'],old_schema):
                        if v[source]!=previous['default']: raise ValueError('Cannot change the type of authored field: '+source)
                        saved=deepcopy(f.get('default',default_value(f['type'],old_schema)))
                    result[f['name']]=saved
                for f in fields:
                    if f['name'] not in field_names and v[f['name']]!=f['default']:
                        raise ValueError('Cannot remove an authored field: '+f['name'])
                return result
            return {f['name']:value(f['type'],v[f['name']]) for f in fields}
        return deepcopy(v)

    # Defaults in other structs may embed the edited type.
    for d in structs:
        if old and d['node_id']==old['node_id']: continue
        previous=old_schema.structs.get(d['name'])
        if previous:
            for f,p in zip(d['fields'],previous['fields']):
                f['default']=value(p['type'],p['default'])
    for key in ('variables','global_variables','scene_variables'):
        for name,entry in scene.get(key,{}).items():
            if isinstance(entry,dict) and set(entry)=={'type','value'}:
                entry['value']=value(entry['type'],entry['value']); entry['type']=renamed(entry['type'])
    for store in scene.get('entity_variables',{}).values():
        for entry in store.values():
            if isinstance(entry,dict) and set(entry)=={'type','value'}:
                entry['value']=value(entry['type'],entry['value']); entry['type']=renamed(entry['type'])

    old_functions=deepcopy(graph.get('functions',[]))
    documents=[(None,graph)]+[(f['id'],f['graph']) for f in graph.get('functions',[])]
    for f in graph.get('functions',[]):
        for port in f['inputs']+f['outputs']:
            if port['type']==old_type and new is None: raise ValueError('Cannot delete a type used by function ports')
            if 'default' in port: port['default']=value(port['type'],port['default'])
            port['type']=renamed(port['type'])
    for event in graph.get('event_definitions',[]):
        for port in event['parameters']:
            if port['type']==old_type and new is None: raise ValueError('Cannot delete a type used by event ports')
            if 'default' in port: port['default']=value(port['type'],port['default'])
            port['type']=renamed(port['type'])
    for function_id,document in documents:
        active_registry=scoped_registry(registry,old_functions,function_id) if function_id is not None else registry
        remap_in,remap_out={},{}
        linked={(str(l['to'][0]),l['to'][1]) for l in document['links']}
        for node in document['nodes']:
            spec=active_registry[node['type']]
            if spec.user_type and spec.variable_type:
                # A type rename must not change a variable's implicit old name.
                for port in spec.data_inputs:
                    if port.name=='Name': node.setdefault('values',{}).setdefault('Name',deepcopy(port.default))
            if old_type and new_type!=old_type and old_type in node.get('code',''):
                raise ValueError('Update embedded code type references before refactoring node '+str(node['id']))
            if old_type and spec.user_type==old_type and new is None:
                raise ValueError('Cannot delete a type used by node '+str(node['id']))
            if old_type and spec.user_type==old_type and spec.kind=='struct_make':
                remap_in[str(node['id'])]=field_names
                authored=node.get('values',{})
                old_fields={p['name']:p for p in old_schema.structs[original]['fields']}
                for name,v in authored.items():
                    if name not in field_names and v!=old_fields[name]['default']:
                        raise ValueError('Cannot remove an authored node field: '+name)
                node['values']={field_names[n]:value(old_fields[n]['type'],v) for n,v in authored.items() if n in field_names}
            elif old_type and spec.user_type==old_type and spec.kind=='struct_break':
                remap_out[str(node['id'])]=field_names
                if 'Value' in node.get('values',{}): node['values']['Value']=value(old_type,node['values']['Value'])
            elif old_type and spec.user_type==old_type and spec.kind=='enum_value':
                if any(a!=b for a,b in enum_names.items()) or len(enum_names)!=len(old_schema.enum_names(original)):
                    if (str(node['id']),'Value') in linked: raise ValueError('Update dynamic enum construction before renaming or deleting labels')
                node.setdefault('values',{})['Value']=value(old_type,node.get('values',{}).get('Value',spec.data_inputs[0].default))
            else:
                for port in spec.data_inputs:
                    if port.name in node.get('values',{}): node['values'][port.name]=value(port.type,node['values'][port.name])
            if spec.user_type==old_type and node.get('label')==spec.name:
                node['label']=spec.name.replace(original,new['name'])
        for link in document['links']:
            for side,mappings in (('to',remap_in),('from',remap_out)):
                nid,port=link[side]
                if str(nid) in mappings:
                    mapping=mappings[str(nid)]
                    if port not in mapping: raise ValueError('Disconnect the removed field first: '+str(nid)+'.'+port)
                    link[side]=[nid,mapping[port]]
    if old and new is None:
        retired['nodes']+=([old['node_id'],old['node_id']+1] if kind=='struct' else [old['node_id']])
        retired['variables'].append(old['variable_id'])
        scene['retired_type_ids']={k:sorted(set(v)) for k,v in retired.items()}
    build_schema(structs,enums)
    graph['struct_definitions'],graph['enum_definitions']=deepcopy(structs),deepcopy(enums)
    scene['struct_definitions'],scene['enum_definitions']=deepcopy(structs),deepcopy(enums)
    compile_graph(graph,scene)
    return graph,scene
