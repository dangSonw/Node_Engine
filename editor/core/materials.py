"""Reusable base-color material assets and explicit per-entity parameter overrides."""
from copy import deepcopy
import re
import uuid
from .scene import entity_text, finite_number


def default_parameters():
    return dict(color=[1., 1., 1.], opacity=1., alpha_mode='opaque', alpha_cutoff=.5, unlit=False)


def validate_parameters(value, *, partial=False):
    keys = default_parameters().keys()
    if not isinstance(value, dict) or value.keys() - keys or (not partial and value.keys() != keys):
        raise ValueError('Material requires color, opacity, alpha_mode, alpha_cutoff and unlit')
    if 'color' in value:
        color = value['color']
        if not isinstance(color, list) or len(color) != 3 or any(not finite_number(x) or not 0 <= x <= 1 for x in color):
            raise ValueError('Material color requires three linear RGB numbers between 0 and 1')
    for key in ('opacity', 'alpha_cutoff'):
        if key in value and (not finite_number(value[key]) or not 0 <= value[key] <= 1):
            raise ValueError(f'Material {key} must be between 0 and 1')
    if 'alpha_mode' in value and value['alpha_mode'] not in ('opaque', 'mask', 'blend'):
        raise ValueError('Material alpha mode must be opaque, mask or blend')
    if 'unlit' in value and type(value['unlit']) is not bool:
        raise ValueError('Material unlit must be boolean')


def validate_assets(assets):
    if not isinstance(assets, list) or len(assets) > 1024:
        raise ValueError('At most 1024 material assets are allowed')
    result = {}
    for asset in assets:
        if not isinstance(asset, dict) or set(asset) != {'version', 'type', 'id', 'name', *default_parameters()}:
            raise ValueError('Invalid material asset fields')
        if type(asset['version']) is not int or asset['version'] != 1 or asset['type'] != 'material':
            raise ValueError('Unsupported material asset version/type')
        mid = asset['id']
        if not isinstance(mid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', mid) or mid in result:
            raise ValueError('Material IDs must be unique, 1–48 letters, digits, underscores or hyphens')
        if not entity_text(asset['name'], 512): raise ValueError('Invalid material name')
        validate_parameters({k: asset[k] for k in default_parameters()})
        result[mid] = asset
    return result


def merge_assets(*libraries):
    result = {}
    for library in libraries:
        for mid, asset in validate_assets(library).items():
            if mid in result and result[mid] != asset:
                raise ValueError(f'Conflicting material asset: {mid}')
            result[mid] = deepcopy(asset)
    validate_assets(list(result.values()))
    return [result[k] for k in sorted(result)]


def scene_assets(scene):
    prefabs = scene.get('prefab_assets', [])
    if not isinstance(prefabs, list) or any(not isinstance(a, dict) for a in prefabs):
        raise ValueError('Prefab assets must be an array of objects')
    return merge_assets(scene.get('material_assets', []),
                        *(a.get('material_assets', []) for a in prefabs))


def validate_binding(value, assets):
    if value is None: return
    if not isinstance(value, dict) or set(value) != {'asset', 'overrides'}:
        raise ValueError('Material binding requires asset and overrides')
    if not isinstance(value['asset'], str) or value['asset'] not in assets:
        raise ValueError('Material binding references an unknown asset')
    validate_parameters(value['overrides'], partial=True)


def effective_parameters(scene, binding):
    assets = validate_assets(scene_assets(scene))
    validate_binding(binding, assets)
    if binding is None: raise ValueError('Entity has no assigned material')
    result = {k: deepcopy(assets[binding['asset']][k]) for k in default_parameters()}
    result.update(deepcopy(binding['overrides']))
    return result


def new_asset(name='Material'):
    return dict(version=1, type='material', id=uuid.uuid4().hex, name=name, **default_parameters())


def put_asset(scene, asset):
    from .scene import validate_scene
    validate_assets([asset])
    result = deepcopy(scene)
    assets = {a['id']: a for a in scene_assets(result)}
    assets[asset['id']] = deepcopy(asset)
    result['material_assets'] = list(assets.values())
    # Captured prefab dependencies are snapshots of the same shared asset ID.
    for prefab in result.get('prefab_assets', []):
        for index, existing in enumerate(prefab.get('material_assets', [])):
            if existing['id'] == asset['id']: prefab['material_assets'][index] = deepcopy(asset)
    return validate_scene(result)


def remove_asset(scene, mid):
    from .scene import validate_scene
    result = deepcopy(scene)
    result['material_assets'] = [a for a in scene_assets(result) if a['id'] != mid]
    for prefab in result.get('prefab_assets', []):
        if 'material_assets' in prefab:
            prefab['material_assets'] = [a for a in prefab['material_assets'] if a['id'] != mid]
    return validate_scene(result)  # References reject removal; the caller retains its original scene.
