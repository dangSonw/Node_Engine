"""Versioned domain files; UI layouts are optional and never runtime behavior."""
import json
import os
import tempfile
from pathlib import Path
from .scene import validate_scene
from .project_format import load_manifest, nen_manifest

VERSION = 1


def write_text_if_changed(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text("utf-8") == text:
        return False
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def save_json(path, data):
    return write_text_if_changed(path, json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")


def load_graph(path):
    value = json.loads(Path(path).read_text("utf-8"))
    if not isinstance(value, dict):
        raise ValueError('Graph document must be an object')
    if value.get("version") != VERSION:
        raise ValueError(f"Unsupported graph version {value.get('version')}; expected {VERSION}")
    if not isinstance(value.get("nodes"), list) or not isinstance(value.get("links"), list):
        raise ValueError("Graph must contain nodes and links arrays")
    return value


def empty_graph():
    return {"version": VERSION, "name": "Gameplay", "nodes": [], "links": []}


def default_scene():
    return {"entities": [{"id": "player", "name": "Player", "position": [0., 0., 0.],
                          "rotation": [0., 0., 0.], "scale": [1., 1., 1.]}], "variables": {}}


def load_project(path, scene_id=None):
    path = Path(path).resolve()
    data = load_manifest(path)
    from .projects import load_scene_documents
    graph,scene=load_scene_documents(path,data,scene_id)
    return data,graph,scene


def create_project(directory, name):
    """Create a new folder without replacing any existing project or user file."""
    root = Path(directory).resolve()
    if not isinstance(name, str) or not name.strip():
        raise ValueError('Project name cannot be empty')
    root.mkdir(parents=True, exist_ok=False)
    graph = empty_graph()
    graph['nodes'] = [{'id':'start', 'type':1001, 'values':{}, 'position':[0,0]},
                      {'id':'update', 'type':1002, 'values':{}, 'position':[0,180]}]
    save_json(root/'graphs/gameplay.json', graph)
    save_json(root/'scenes/main.json', default_scene())
    from .project_markdown import default_readme, PROJECT_GITIGNORE
    write_text_if_changed(root/'README.md', default_readme(name.strip()))
    write_text_if_changed(root/'.gitignore', PROJECT_GITIGNORE)
    for folder in ('models', 'textures', 'audio', 'ui', 'prefabs'):
        (root/'assets'/folder).mkdir(parents=True, exist_ok=True)
    manifest = root/(root.name+'.nen')
    # Write the manifest last; a failed creation never looks like a valid project.
    save_json(manifest, nen_manifest({'version':2, 'name':name.strip(), 'entry_scene':'main',
        'scenes':[{'id':'main', 'name':'Main', 'graph':'graphs/gameplay.json', 'scene':'scenes/main.json'}], 'assets':[]}))
    return manifest
