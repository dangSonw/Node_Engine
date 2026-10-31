"""Scene-owned PNG/JPEG sprite atlases. Frames run left to right, top to bottom."""
from copy import deepcopy
from pathlib import PurePosixPath
import re
import uuid
from .scene import asset_path, entity_text, finite_number

ASSET_FIELDS = frozenset(('version', 'type', 'id', 'name', 'texture', 'columns', 'rows',
                         'width', 'height', 'pivot', 'filter'))

def new_asset(texture, name='Sprite'):
    return dict(version=1, type='sprite', id=uuid.uuid4().hex, name=name,
                texture=texture, columns=1, rows=1, width=1., height=1.,
                pivot=[.5, .5], filter='nearest')


def validate_assets(values):
    if not isinstance(values, list) or len(values) > 1024:
        raise ValueError('At most 1024 sprite assets are allowed')
    result = {}
    for value in values:
        if not isinstance(value, dict) or value.keys() != ASSET_FIELDS:
            raise ValueError('Invalid sprite asset fields')
        if type(value['version']) is not int or value['version'] != 1 or value['type'] != 'sprite':
            raise ValueError('Unsupported sprite version/type')
        sid = value['id']
        if not isinstance(sid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', sid) or sid in result:
            raise ValueError('Invalid or duplicate sprite ID')
        if not entity_text(value['name'], 512): raise ValueError('Invalid sprite name')
        path = PurePosixPath(asset_path(value['texture']))
        if (not entity_text(value['texture'], 4096) or ':' in value['texture'] or path.as_posix() != value['texture'] or
                path.parts[0] != 'assets' or path.suffix.lower() not in ('.png', '.jpg', '.jpeg')):
            raise ValueError('Sprite texture must be a PNG/JPEG file in the project assets directory')
        for key in ('columns', 'rows'):
            if type(value[key]) is not int or not 1 <= value[key] <= 8192:
                raise ValueError('Sprite grid requires positive integers up to 8192')
        if value['columns'] * value['rows'] > 65536: raise ValueError('At most 65536 sprite frames are allowed')
        for key in ('width', 'height'):
            if not finite_number(value[key]) or not 0 < value[key] <= 1e6:
                raise ValueError('Sprite dimensions must be positive, at most 1000000 world units')
        pivot = value['pivot']
        if not isinstance(pivot, list) or len(pivot) != 2 or any(not finite_number(v) or not 0 <= v <= 1 for v in pivot):
            raise ValueError('Sprite pivot requires two numbers between 0 and 1')
        if value['filter'] not in ('nearest', 'linear'): raise ValueError('Invalid sprite filter')
        result[sid] = value
    return result


def merge_assets(*libraries):
    result = {}
    for values in libraries:
        for sid, asset in validate_assets(values).items():
            if sid in result and result[sid] != asset: raise ValueError(f'Conflicting sprite asset: {sid}')
            result[sid] = deepcopy(asset)
    validate_assets(list(result.values()))
    return [result[k] for k in sorted(result)]


def scene_assets(scene):
    prefabs = scene.get('prefab_assets', [])
    if not isinstance(prefabs, list) or any(not isinstance(a, dict) for a in prefabs):
        raise ValueError('Prefab assets must be an array of objects')
    return merge_assets(scene.get('sprite_assets', []), *(a.get('sprite_assets', []) for a in prefabs))


def binding(sid):
    return dict(asset=sid, frame=0, flip_x=False, flip_y=False) if sid else None


def validate_binding(value, assets):
    if value is None: return
    if not isinstance(value, dict) or set(value) != {'asset', 'frame', 'flip_x', 'flip_y'}:
        raise ValueError('Sprite binding requires asset, frame, flip_x and flip_y')
    if not isinstance(value['asset'], str) or value['asset'] not in assets:
        raise ValueError('Sprite binding references an unknown asset')
    asset = assets[value['asset']]
    if type(value['frame']) is not int or not 0 <= value['frame'] < asset['columns'] * asset['rows']:
        raise ValueError('Sprite frame is outside its atlas')
    if type(value['flip_x']) is not bool or type(value['flip_y']) is not bool:
        raise ValueError('Sprite flips must be boolean')


def put_asset(scene, asset):
    from .scene import validate_scene
    validate_assets([asset])
    result = deepcopy(scene)
    assets = {a['id']: a for a in scene_assets(result)}
    assets[asset['id']] = deepcopy(asset)
    result['sprite_assets'] = list(assets.values())
    for prefab in result.get('prefab_assets', []):
        for i, old in enumerate(prefab.get('sprite_assets', [])):
            if old['id'] == asset['id']: prefab['sprite_assets'][i] = deepcopy(asset)
    return validate_scene(result)


def inspect_texture(path, asset=None):
    from pathlib import Path
    from PySide6.QtGui import QImageReader
    path = Path(path)
    if path.suffix.lower() not in ('.png', '.jpg', '.jpeg') or not 0 < path.stat().st_size <= 64*1024*1024:
        raise ValueError('Sprite requires a PNG/JPEG file of at most 64 MiB')
    reader = QImageReader(str(path)); reader.setDecideFormatFromContent(True)
    size = reader.size()
    if bytes(reader.format()).lower() not in (b'png', b'jpeg', b'jpg') or not (0 < size.width() <= 8192 and
            0 < size.height() <= 8192 and size.width()*size.height()*4 <= 64*1024*1024):
        raise ValueError('Sprite image is invalid or exceeds 8192 per axis / 64 MiB decoded')
    if asset and (size.width() % asset['columns'] or size.height() % asset['rows']):
        raise ValueError('Sprite grid must divide texture dimensions exactly')
    if reader.read().isNull(): raise ValueError('Cannot decode sprite texture: ' + reader.errorString())
    return size.width(), size.height()


def texture_file(root, asset):
    from pathlib import Path
    root = Path(root).resolve()
    path = (root / asset['texture']).resolve()
    if not path.is_relative_to(root / 'assets'): raise ValueError('Sprite texture escapes project assets directory')
    inspect_texture(path, asset)
    return path


def import_texture(scene, project_root, source):
    """Copy a validated source once. Undo keeps the copied file available for Redo."""
    from pathlib import Path
    import shutil
    root, source = Path(project_root).resolve(), Path(source).resolve()
    inspect_texture(source)
    asset = new_asset('', source.stem)
    relative = Path('assets/sprites') / (asset['id'] + source.suffix.lower())
    target = root / relative
    if not target.resolve().is_relative_to(root): raise ValueError('Sprite destination escapes project directory')
    asset['texture'] = relative.as_posix()
    result = put_asset(scene, asset)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Unique IDs keep existing project files intact.
    with source.open('rb') as src, target.open('xb') as dst: shutil.copyfileobj(src, dst)
    return result, asset['id']


def remove_asset(scene, sid):
    from .scene import validate_scene
    result = deepcopy(scene)
    result['sprite_assets'] = [a for a in scene_assets(result) if a['id'] != sid]
    for prefab in result.get('prefab_assets', []):
        if 'sprite_assets' in prefab:
            prefab['sprite_assets'] = [a for a in prefab['sprite_assets'] if a['id'] != sid]
    return validate_scene(result)
