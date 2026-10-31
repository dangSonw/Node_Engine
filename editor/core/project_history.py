"""Durable project history and bounded discovery; discovery never fabricates open dates."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from .document import save_json

MAX_RECENT=100


def path_key(path):
    return os.path.normcase(str(Path(path).expanduser().resolve()))


def read_history(path):
    try:
        raw=json.loads(Path(path).read_text('utf-8'))
        entries=raw.get('projects',[]) if isinstance(raw,dict) and raw.get('version')==1 else []
        result=[]
        for entry in entries:
            if not isinstance(entry,dict) or not isinstance(entry.get('path'),str) or not entry['path'].strip() or not isinstance(entry.get('opened_at',''),str): continue
            try: path_key(entry['path'])
            except (OSError,ValueError): continue
            result.append(entry)
        return result[:MAX_RECENT]
    except (OSError,ValueError,TypeError):
        return []


def merge_history(path,legacy):
    entries=read_history(path)
    known={path_key(entry['path']) for entry in entries}
    for value in legacy:
        try: key=path_key(value) if isinstance(value,str) and value.strip() else None
        except (OSError,ValueError): continue
        if key and key not in known:
            entries.append(dict(path=str(Path(value).expanduser().resolve()),opened_at=''))
            known.add(key)
    return entries[:MAX_RECENT]


def remember(path,project,legacy=()):
    project=Path(project).expanduser().resolve()
    entries=merge_history(path,legacy)
    entries=[entry for entry in entries if path_key(entry['path'])!=path_key(project)]
    if project.suffix.lower()=='.nen':
        from .projects import scene_entries
        try:
            current=json.loads(project.read_text('utf-8-sig'))
            documents={(entry['graph'],entry['scene']) for entry in scene_entries(current)}
            def backup(entry):
                source=Path(entry['path'])
                if source.name.lower()!='project.json' or path_key(source.parent)!=path_key(project.parent): return False
                try: return {(e['graph'],e['scene']) for e in scene_entries(json.loads(source.read_text('utf-8-sig')))}<=documents
                except (OSError,ValueError,TypeError,KeyError): return False
            entries=[entry for entry in entries if not backup(entry)]
        except (OSError,ValueError,TypeError,KeyError):
            pass
    entries.insert(0,dict(path=str(project),opened_at=datetime.now(timezone.utc).isoformat()))
    save_json(path,dict(version=1,projects=entries[:MAX_RECENT]))
    return entries[:MAX_RECENT]


def discover_projects(roots,depth=2):
    """Inspect only known project folders, excluding caches and generated output."""
    ignored={'build','generated','assets','deps','node_modules','.git','.venv','.cache','.work','artifacts'}
    result=[]; seen=set()
    def visit(folder,remaining):
        if len(result)>=500 or not folder.is_dir() or folder.is_symlink(): return
        try:
            children=list(folder.iterdir())
        except OSError:
            return
        manifests=sorted((p for p in children if p.is_file() and p.suffix.lower()=='.nen'),key=lambda p:p.name.casefold())
        legacy=folder/'project.json'
        if not manifests and legacy.is_file(): manifests=[legacy]
        for path in manifests:
            key=path_key(path)
            if key not in seen: result.append(path); seen.add(key)
        if manifests or remaining==0: return
        for child in sorted(children,key=lambda p:p.name.casefold()):
            if child.name not in ignored: visit(child,remaining-1)
    for root in roots: visit(Path(root).expanduser(),depth)
    return result


def describe_project(path,opened_at='',source='project'):
    path=Path(path).expanduser().resolve()
    data={}; error=''
    try:
        if path.stat().st_size>1024*1024: raise ValueError('Project manifest is too large for a thumbnail preview')
        data=json.loads(path.read_text('utf-8-sig'))
        if not isinstance(data,dict): raise ValueError('Invalid project manifest')
    except (OSError,ValueError) as failure:
        error='Project file not found' if not path.is_file() else str(failure)
    engine=data.get('engine',{})
    if not isinstance(engine,dict): engine={}
    name=data.get('name',path.parent.name)
    version=engine.get('last_saved_with',f'Legacy v{data.get("version",1)}')
    return dict(path=str(path),name=name if isinstance(name,str) else path.parent.name,
        version=str(version),opened_at=opened_at,source=source,error=error,exists=path.is_file(),
        thumbnail=data.get('thumbnail',''),scene_count=len(data['scenes']) if isinstance(data.get('scenes'),list) else 1)
