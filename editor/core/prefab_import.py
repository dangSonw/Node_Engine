"""Import authored prefab libraries without linking a project to external files."""
from copy import deepcopy
from pathlib import Path
import shutil
import tempfile
import uuid

from .assets import model_dependencies
from .document import load_project
from .prefabs import MAX_ASSETS, PrefabLibrary, load_prefab, prepare_scene_prefabs
from .scene import asset_path
from . import sprites


def _mesh_slots(assets):
    # Only builtin mesh fields are paths; component strings and reference IDs are not.
    for asset in assets:
        yield from asset.get('entities', [])
        yield from asset.get('overrides', {}).values()
        for binding in asset.get('nested', []):
            yield from binding.get('overrides', {}).values()


def _merge(scene, assets, definitions=(), materials=(), sprite_assets=()):
    schemas = {d['id']: deepcopy(d) for d in scene.get('component_definitions', [])}
    for definition in definitions:
        cid = definition['id']
        if cid in schemas and schemas[cid] != definition:
            raise ValueError(f'Conflicting component definition: {cid}')
        schemas[cid] = deepcopy(definition)
    from .materials import merge_assets
    library = PrefabLibrary([*scene.get('prefab_assets', []), *assets], list(schemas.values()),
                            merge_assets(scene.get('material_assets', []), list(materials)),
                            sprites.merge_assets(scene.get('sprite_assets', []), list(sprite_assets)))
    result = deepcopy(scene)
    result['prefab_assets'] = library.assets
    result['component_definitions'] = library.component_definitions
    if library.material_assets: result['material_assets'] = library.material_assets
    if library.sprite_assets: result['sprite_assets'] = library.sprite_assets
    result.pop('prefab_templates', None)
    result = prepare_scene_prefabs(result)
    result.pop('prefab_templates', None)
    return result


def _model_files(assets, root):
    models, files = {}, set()
    for slot in _mesh_slots(assets):
        if not slot.get('mesh'):
            continue
        relative = asset_path(slot['mesh'])
        source = (root / relative).resolve()
        if not source.is_relative_to(root):
            raise ValueError(f'Prefab mesh escapes project directory: {relative}')
        if relative not in models:
            models[relative] = source.relative_to(root).as_posix()
            files.update(model_dependencies(source))
    return models, files


def register_prefab_files(scene, project_root, paths):
    """Register explicitly selected project files, resolving against existing assets."""
    root = Path(project_root).resolve()
    if not paths or len(paths) > MAX_ASSETS:
        raise ValueError(f'Select between 1 and {MAX_ASSETS} prefab files')
    assets, seen = [], set()
    for filename in paths:
        path = (root / filename).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Select prefab files inside this project; use Import Prefab Library for another project')
        if path in seen:
            raise ValueError(f'Duplicate prefab file: {path.name}')
        seen.add(path)
        assets.append(load_prefab(path))
    result = _merge(scene, assets)
    _, files = _model_files(assets, root)
    files.update(sprites.texture_file(root, a) for a in sprites.scene_assets(result))
    if any(not p.is_relative_to(root / 'assets') or not p.resolve().is_relative_to(root / 'assets') for p in files):
        raise ValueError('Registered prefab models and dependencies must be inside the project assets directory')
    return result


def import_project_prefabs(scene, project_root, source_project):
    """Copy one project's library and glTF dependencies, then return one scene edit.

    Validation precedes writes. A temporary directory is renamed only after every
    copy succeeds. Undo removes the registration but retains copied files for Redo.
    """
    root = Path(project_root).resolve()
    source_project = Path(source_project).resolve()
    _, _, source_scene = load_project(source_project)
    library = PrefabLibrary(source_scene.get('prefab_assets', []), source_scene.get('component_definitions', []), source_scene.get('material_assets', []), source_scene.get('sprite_assets', []))
    assets = library.assets
    if not assets:
        raise ValueError('The source project has no registered prefabs; save its library first')
    # Catch IDs/schema conflicts before copying anything or assigning new paths.
    _merge(scene, assets, library.component_definitions, library.material_assets, library.sprite_assets)
    source_root = source_project.parent
    models, files = _model_files(assets, source_root)
    prefix = Path('assets') / ('prefab-library-' + uuid.uuid4().hex[:12])
    sprite_assets = library.sprite_assets
    for sprite in sprite_assets:
        source = sprites.texture_file(source_root, sprite)
        files.add(source)
        sprite['texture'] = (prefix / source.relative_to(source_root)).as_posix()
    rewritten = {a['id']: a for a in sprite_assets}
    for asset in assets:
        if 'sprite_assets' in asset:
            asset['sprite_assets'] = [deepcopy(rewritten[a['id']]) for a in asset['sprite_assets']]
    for slot in _mesh_slots(assets):
        if slot.get('mesh'):
            slot['mesh'] = (prefix / models[slot['mesh']]).as_posix()
    result = _merge(scene, assets, library.component_definitions, library.material_assets, sprite_assets)
    if not files:
        return result
    asset_root = root / 'assets'
    if not asset_root.resolve().is_relative_to(root):
        raise ValueError('Destination assets directory escapes project directory')
    asset_root.mkdir(exist_ok=True)
    destination = root / prefix
    if destination.exists():
        raise FileExistsError(f'Import destination already exists: {destination}')
    # All temporary and destination paths are strictly below this project's assets.
    with tempfile.TemporaryDirectory(prefix='.prefab-import-', dir=asset_root) as temporary:
        stage = Path(temporary) / 'library'
        stage.mkdir()
        for source in sorted(files):
            if not source.resolve().is_relative_to(source_root):
                raise ValueError('Model dependency escapes source project')
            target = stage / source.relative_to(source_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        stage.rename(destination)
    return result
