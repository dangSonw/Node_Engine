"""Named scene documents and one immutable project snapshot for Preview/export."""
from copy import deepcopy
import json
from pathlib import Path
import re
from .document import load_graph, save_json, empty_graph, default_scene
from .scene import validate_scene
from .project_format import load_manifest, validate_manifest, nen_manifest


def save_project_documents(path,project,documents,*,expected=None):
    """Stage every changed document, publish the manifest last, roll back write failures."""
    import os
    import tempfile
    path=Path(path).resolve(); root=path.parent
    entries={entry['id']:entry for entry in scene_entries(project)}
    targets={path}
    for entry in entries.values():
        for field in ('graph','scene'):
            target=project_child(root,entry[field])
            if target in targets: raise ValueError('Project document paths must be distinct')
            targets.add(target)
    if set(documents)-entries.keys(): raise ValueError('Unknown scene document to save')
    changes={}
    for scene_id,document in documents.items():
        for field in ('graph','scene'):
            target=project_child(root,entries[scene_id][field])
            if target==path or target in changes: raise ValueError('Project document paths must be distinct')
            changes[target]=document[field]
    changes[path]=project
    payloads={target:(json.dumps(value,indent=2,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode('utf-8')
              for target,value in changes.items()}
    staged={}; backups={}; committed=[]; recovery=set()
    def stage(target,payload):
        target.parent.mkdir(parents=True,exist_ok=True)
        fd,name=tempfile.mkstemp(prefix=target.name+'.',suffix='.tmp',dir=target.parent)
        temporary=Path(name)
        try:
            with os.fdopen(fd,'wb') as file:
                file.write(payload); file.flush(); os.fsync(file.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True); raise
        return temporary
    try:
        for target,payload in payloads.items():
            original=target.read_bytes() if target.exists() else None
            if expected is not None and target in expected and original!=expected[target]:
                raise ValueError(f'Project file changed on disk; reopen before saving: {target}')
            if original==payload: continue
            staged[target]=stage(target,payload)
            backups[target]=stage(target,original) if original is not None else None
        for target,temporary in staged.items():
            os.replace(temporary,target); committed.append(target)
    except BaseException as error:
        failures=[]
        for target in reversed(committed):
            backup=backups[target]
            try:
                if backup is None: target.unlink(missing_ok=True)
                else: os.replace(backup,target)
            except OSError:
                failures.append(target)
                if backup is not None: recovery.add(backup)
        if failures:
            raise OSError('Project save rollback needs recovery for '+', '.join(map(str,failures))+
                          '; original backups retained: '+', '.join(map(str,recovery))) from error
        raise
    finally:
        for temporary in list(staged.values())+[p for p in backups.values() if p is not None]:
            if temporary not in recovery:
                try: temporary.unlink(missing_ok=True)
                except OSError: pass


def scene_entries(project):
    validate_manifest(project)
    if not isinstance(project,dict) or type(project.get('version')) is not int:
        raise ValueError('Project manifest must contain an integer version')
    if project['version']==1:
        entries=[dict(id='main',name=project.get('name','Main'),scene=project.get('scene'),graph=project.get('graph'))]
    elif project['version']==2:
        if not isinstance(project.get('entry_scene'),str):
            raise ValueError('Project entry_scene must identify one of its scenes')
        entries=project.get('scenes')
        if not isinstance(entries,list) or not 1<=len(entries)<=64:
            raise ValueError('Project must contain 1 to 64 scenes')
    else:
        raise ValueError('Unsupported project version')
    ids=set(); paths=set()
    for entry in entries:
        if not isinstance(entry,dict) or not isinstance(entry.get('id'),str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}',entry['id']):
            raise ValueError('Scene ID must start with a letter and contain at most 64 letters, digits, underscores or hyphens')
        if entry['id'] in ids: raise ValueError('Duplicate scene ID: '+entry['id'])
        ids.add(entry['id'])
        if not isinstance(entry.get('name',entry['id']),str) or not entry.get('name',entry['id']).strip():
            raise ValueError('Scene name cannot be empty')
        for field in ('graph','scene'):
            path=entry.get(field)
            if not isinstance(path,str) or not path or Path(path).is_absolute() or Path(path).drive or '..' in Path(path).parts:
                raise ValueError('Project paths must be relative and stay inside the project')
            key=Path(path).as_posix().casefold()
            if key in paths: raise ValueError('Scene and graph documents must have distinct paths')
            paths.add(key)
    if project.get('entry_scene','main') not in ids:
        raise ValueError('Project entry_scene must identify one of its scenes')
    return entries


def selected_entry(project,scene_id=None):
    entries=scene_entries(project); selected=scene_id if scene_id is not None else project.get('entry_scene','main')
    for entry in entries:
        if entry['id']==selected: return entry
    raise ValueError('Unknown project scene: '+str(selected))


def project_child(root,relative):
    root=Path(root).resolve(); result=(root/relative).resolve()
    if not result.is_relative_to(root): raise ValueError('Project path escapes its directory')
    return result


def load_scene_documents(path,project,scene_id=None):
    entry=selected_entry(project,scene_id); root=Path(path).resolve().parent
    scene=json.loads(project_child(root,entry['scene']).read_text('utf-8'))
    graph=load_graph(project_child(root,entry['graph']))
    from .project_types import with_project_types
    graph,scene=with_project_types(project,graph,scene)
    return graph,validate_scene(scene)


def project_snapshot(path,project=None,scene_id=None,graph=None,scene=None,preview=False,*,documents=None):
    """Capture every scene now; later asynchronous compilation never rereads documents."""
    path=Path(path).resolve()
    if project is None: project=load_manifest(path)
    validate_manifest(project,require_nen=path.suffix.lower()=='.nen')
    entries=scene_entries(project); selected=selected_entry(project,scene_id)['id']
    overrides=documents or {}; documents={}
    if set(overrides)-{entry['id'] for entry in entries}: raise ValueError('Unknown scene document override')
    paths=set()
    for entry in entries:
        for field in ('graph','scene'):
            resolved=project_child(path.parent,entry[field])
            if resolved in paths: raise ValueError('Scene and graph documents must have distinct paths')
            paths.add(resolved)
        if entry['id']==selected and graph is not None and scene is not None:
            g,s=deepcopy(graph),deepcopy(scene)
        elif entry['id'] in overrides:
            override=overrides[entry['id']]; g,s=deepcopy(override['graph']),deepcopy(override['scene'])
        else: g,s=load_scene_documents(path,project,entry['id'])
        from .project_types import with_project_types
        g,s=with_project_types(project,g,s)
        documents[entry['id']]=dict(graph=g,scene=s)
    if project['version']==1: return documents['main']
    return dict(version=2,entry_scene=selected if preview else project['entry_scene'],scenes=documents)


def compile_project(snapshot):
    from .compiler import compile_graph,GraphError,Problem
    if 'scenes' not in snapshot: return compile_graph(snapshot['graph'],snapshot['scene'])
    from .registry import Registry
    registry=Registry()
    programs={}
    for scene_id,documents in snapshot['scenes'].items():
        try: programs[scene_id]=compile_graph(documents['graph'],documents['scene'],registry=registry)
        except GraphError as error:
            raise GraphError([Problem(scene_id+'/'+p.node,p.message) for p in error.problems]) from error
        except (ValueError,KeyError) as error: raise ValueError(f'Scene {scene_id}: {error}') from error
    from .typed_schema import build_schema, validate_variable
    declarations = {}
    for scene_id, program in programs.items():
        schema = build_schema(program['type_definitions']['structs'], program['type_definitions']['enums'])
        scene = program['scene']
        for name, scope in scene.get('variable_scopes', {}).items():
            if scope != 'global':
                continue
            kind, value = validate_variable(scene['variables'][name], schema)
            declaration = (kind, value)
            if name in declarations and declarations[name] != declaration:
                raise ValueError(f'Scene {scene_id}: conflicting global declaration: {name}')
            declarations[name] = declaration
    global_types = {name: declaration[0] for name, declaration in declarations.items()}
    for scene_id, documents in snapshot['scenes'].items():
        try:
            programs[scene_id] = compile_graph(documents['graph'], documents['scene'], registry=registry, global_types=global_types)
        except GraphError as error:
            raise GraphError([Problem(scene_id+'/'+p.node,p.message) for p in error.problems]) from error
    return dict(version=1,entry_scene=snapshot['entry_scene'],scenes=programs)


def add_scene(path, scene_id, name=None):
    """Add new documents, then publish their manifest entry; never overwrite a document."""
    path=Path(path).resolve(); project=load_manifest(path)
    entries=deepcopy(scene_entries(project))
    entry=dict(id=scene_id,name=name or scene_id,scene=f'scenes/{scene_id}.json',graph=f'graphs/{scene_id}.json')
    updated=deepcopy(project)
    updated.update(version=2,entry_scene=project.get('entry_scene','main'),scenes=entries+[entry])
    updated.pop('scene',None); updated.pop('graph',None)
    if path.suffix.lower()=='.nen': updated=nen_manifest(updated)
    scene_entries(updated)
    targets=[project_child(path.parent,entry[field]) for field in ('graph','scene')]
    if any(target.exists() for target in targets): raise ValueError('A scene document already exists at this path')
    graph=empty_graph(); graph['name']=entry['name']
    graph['nodes']=[dict(id='loaded',type=1019,values={},position=[0,0]),dict(id='update',type=1002,values={},position=[0,180])]
    for target,data in zip(targets,(graph,default_scene())):
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('x',encoding='utf-8') as file:
            json.dump(data,file,ensure_ascii=False,indent=2,allow_nan=False)
            file.write('\n')
    save_json(path,updated)
    return updated


def convert_to_nen(path, project=None):
    """Publish a new manifest beside legacy documents; retain the original as a backup."""
    path=Path(path).resolve()
    if path.suffix.lower()=='.nen':
        raise ValueError('This project already uses .nen')
    project=load_manifest(path) if project is None else deepcopy(project)
    entries=deepcopy(scene_entries(project))
    project.update(version=2,entry_scene=project.get('entry_scene','main'),scenes=entries)
    project.pop('graph',None); project.pop('scene',None)
    result=nen_manifest(project)
    project_snapshot(path,result)
    target=path.with_name(path.parent.name+'.nen')
    content=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    with target.open('x',encoding='utf-8',newline='\n') as file:
        file.write(content)
    return target,result
