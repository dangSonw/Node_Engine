"""Project type libraries and migrations of every scene's typed nodes and values."""
from copy import deepcopy
from .typed_schema import build_schema, with_types
from .type_edits import definitions, stable_definitions, edit_type
from .components import with_components
from .registry import Registry


def project_retired_ids(project):
    value=project.get('retired_type_ids',dict(nodes=[],variables=[]))
    if not isinstance(value,dict) or set(value)!={'nodes','variables'} or any(
        not isinstance(ids,list) or len(ids)>100000 or any(type(n) is not int for n in ids) for ids in value.values()):
        raise ValueError('Invalid project retired type identities')
    return deepcopy(value)


def project_type_library(project):
    project_retired_ids(project)
    library=project.get('type_definitions')
    if 'type_definitions' not in project: return None
    if not isinstance(library,dict) or set(library)!={'structs','enums'}:
        raise ValueError('Project type_definitions requires structs and enums arrays')
    schema=build_schema(library['structs'],library['enums'])
    structs,enums=stable_definitions(list(schema.structs.values()),list(schema.enums.values()))
    return dict(structs=structs,enums=enums)


def with_project_types(project,graph,scene):
    library=project_type_library(project)
    if library is None: return graph,scene
    graph,scene=deepcopy(graph),deepcopy(scene)
    for document in (graph,scene):
        for key in ('struct_definitions','enum_definitions'):
            local=document.get(key,[])
            if not isinstance(local,list) or any(not isinstance(d,dict) for d in local):
                raise ValueError('Local type definitions require arrays of objects')
    local_structs,local_enums=definitions(graph,scene)
    canonical={d['name']:d for d in library['structs']+library['enums']}
    for index,definition in enumerate(local_structs+local_enums):
        known=canonical.get(definition.get('name'))
        if known is None: raise ValueError('Local type is absent from project library: '+str(definition.get('name')))
        legacy_node=700000+index*2 if index<len(local_structs) else 700000+len(local_structs)*2+index-len(local_structs)
        if definition.get('node_id',legacy_node)!=known['node_id'] or definition.get('variable_id',800000+index*16)!=known['variable_id']:
            raise ValueError('Local type identity conflicts with project library: '+known['name'])
    for document in (graph,scene):
        for key,group in [('struct_definitions','structs'),('enum_definitions','enums')]:
            canonical={d['name']:d for d in library[group]}
            local=document.get(key,[])
            if not isinstance(local,list) or any(not isinstance(d,dict) for d in local):
                raise ValueError('Local type definitions require arrays of objects')
            for definition in local:
                known=canonical.get(definition.get('name'))
                if known is None:
                    raise ValueError('Local type is absent from project library: '+str(definition.get('name')))
                if definition==known: continue
                candidate=deepcopy(library)
                candidate[group]=[definition if d['name']==known['name'] else d for d in candidate[group]]
                normalized=project_type_library({'type_definitions':candidate})
                replacement=next(d for d in normalized[group] if d['name']==known['name'])
                if any(replacement.get(k)!=v for k,v in known.items() if k not in ('node_id','variable_id')) or any(
                    k in definition and definition[k]!=known.get(k) for k in ('node_id','variable_id')):
                    raise ValueError('Local type conflicts with project library: '+known['name'])
            document[key]=deepcopy(library[group])
    retired=project_retired_ids(project)
    if any(retired.values()):
        local=project_retired_ids(scene)
        scene['retired_type_ids']={key:sorted(set(local[key]+retired[key])) for key in retired}
    return graph,scene


def synchronize_types(snapshot):
    """Unify compatible legacy schemas and remap colliding scene-owned node IDs."""
    result=deepcopy(snapshot)
    documents=result['scenes'] if 'scenes' in result else {'main':result}
    schemas={}; types={}; retired={key:set(value) for key,value in project_retired_ids(result).items()}
    reserved=set(); builtin=Registry()
    for scene_id,document in documents.items():
        graph,scene=document['graph'],document['scene']
        schema=build_schema(*definitions(graph,scene)); schemas[scene_id]=schema
        reserved.update(with_components(builtin,scene.get('component_definitions',[])).nodes)
        saved=scene.get('retired_type_ids',dict(nodes=[],variables=[]))
        if not isinstance(saved,dict) or set(saved)!={'nodes','variables'} or any(
            not isinstance(v,list) or any(type(n) is not int for n in v) for v in saved.values()):
            raise ValueError(f'Scene {scene_id}: invalid retired type identities')
        for key in retired: retired[key].update(saved[key])
        structs,enums=stable_definitions(list(schema.structs.values()),list(schema.enums.values()))
        for kind,group in [('struct',structs),('enum',enums)]:
            for definition in group:
                name=definition['name']
                semantic={k:v for k,v in definition.items() if k not in ('node_id','variable_id')}
                if name in types:
                    previous_kind,previous=types[name]
                    if previous_kind!=kind or semantic!={k:v for k,v in previous.items() if k not in ('node_id','variable_id')}:
                        raise ValueError(f'Scene {scene_id}: conflicting project type: {name}')
                else: types[name]=(kind,definition)
    used=reserved|retired['nodes']; used_variables=set(retired['variables'])
    for kind,definition in types.values():
        width=2 if kind=='struct' else 1
        nid=definition['node_id']; vid=definition['variable_id']
        if set(range(nid,nid+width))&used:
            nid=next((n for n in range(700000,799999,2) if not set(range(n,n+width))&used),None)
        if vid in used_variables or set(range(vid,vid+8))&used:
            vid=next((n for n in range(800000,900000,16)
                      if n not in used_variables and not set(range(n,n+8))&used),None)
        if nid is None or vid is None: raise ValueError('Project type identity space is exhausted')
        definition['node_id'],definition['variable_id']=nid,vid
        used.update(range(nid,nid+width)); used.update(range(vid,vid+8)); used_variables.add(vid)
    structs=[d for kind,d in types.values() if kind=='struct']
    enums=[d for kind,d in types.values() if kind=='enum']
    build_schema(structs,enums)
    for scene_id,document in documents.items():
        graph,scene=document['graph'],document['scene']; schema=schemas[scene_id]
        base=with_components(builtin,scene.get('component_definitions',[]))
        before=with_types(base,list(schema.structs.values()),list(schema.enums.values()))
        after=with_types(base,structs,enums)
        def identity(spec): return spec.user_type,spec.kind,spec.variable_scope,spec.variable_access,spec.collection_type,spec.collection_operation
        target={identity(spec):spec.id for spec in after.nodes.values() if spec.user_type}
        mapping={spec.id:target[identity(spec)] for spec in before.nodes.values() if spec.user_type}
        for body in [graph]+[f['graph'] for f in graph.get('functions',[])]:
            for node in body['nodes']: node['type']=mapping.get(node['type'],node['type'])
        for value in (graph,scene):
            value['struct_definitions']=deepcopy(structs); value['enum_definitions']=deepcopy(enums)
        if any(retired.values()): scene['retired_type_ids']={k:sorted(v) for k,v in retired.items()}
    result['type_definitions']=dict(structs=deepcopy(structs),enums=deepcopy(enums))
    if any(retired.values()): result['retired_type_ids']={key:sorted(value) for key,value in retired.items()}
    from .projects import compile_project
    compile_project(result)
    return result


def edit_project_type(snapshot,kind,definition=None,*,original=None,origins=None):
    result=synchronize_types(snapshot)
    documents=result['scenes'] if 'scenes' in result else {'main':result}
    builtin=Registry(); reserved=set()
    for document in documents.values():
        reserved.update(with_components(builtin,document['scene'].get('component_definitions',[])).nodes)
    for scene_id,document in documents.items():
        try:
            document['graph'],document['scene']=edit_type(document['graph'],document['scene'],kind,
                definition,original=original,origins=origins,reserved_nodes=reserved)
        except (ValueError,KeyError,TypeError) as error:
            raise ValueError(f'Scene {scene_id}: {error}') from error
    first=next(iter(documents.values()))
    structs,enums=definitions(first['graph'],first['scene'])
    result['type_definitions']=dict(structs=deepcopy(structs),enums=deepcopy(enums))
    retired=first['scene'].get('retired_type_ids')
    if retired: result['retired_type_ids']=deepcopy(retired)
    from .projects import compile_project
    compile_project(result)
    return result
