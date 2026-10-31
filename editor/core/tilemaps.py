"""Validated scene tilemap assets shared by editor and native export."""
from copy import deepcopy
import re
import uuid
from .scene import asset_path, entity_text, finite_number

FIELDS = frozenset(('version', 'type', 'id', 'name', 'sprite', 'width', 'height', 'tiles',
                    'tile_width', 'tile_height', 'sorting_layer', 'sorting_order'))


def new_asset(sprite, name='Tilemap', width=1, height=1):
    return dict(version=1, type='tilemap', id=uuid.uuid4().hex, name=name, sprite=sprite,
                width=width, height=height, tiles=[-1] * (width * height), tile_width=1.,
                tile_height=1., sorting_layer='default', sorting_order=0)


def validate_assets(values, sprites=None):
    if not isinstance(values, list) or len(values) > 256:
        raise ValueError('At most 256 tilemap assets are allowed')
    sprites = sprites or {}
    result = {}
    for value in values:
        if not isinstance(value, dict) or value.keys() != FIELDS:
            raise ValueError('Invalid tilemap asset fields')
        if type(value['version']) is not int or value['version'] != 1 or value['type'] != 'tilemap':
            raise ValueError('Unsupported tilemap version/type')
        if not isinstance(value['id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', value['id']) or value['id'] in result:
            raise ValueError('Invalid or duplicate tilemap ID')
        if not entity_text(value['name'], 512):
            raise ValueError('Invalid tilemap name')
        if not isinstance(value['sprite'], str) or (sprites and value['sprite'] not in sprites):
            raise ValueError('Tilemap references an unknown sprite asset')
        for key in ('width', 'height'):
            if type(value[key]) is not int or not 1 <= value[key] <= 4096:
                raise ValueError('Tilemap dimensions must be between 1 and 4096')
        if len(value['tiles']) != value['width'] * value['height'] or any(type(tile) is not int or tile < -1 for tile in value['tiles']):
            raise ValueError('Tilemap tiles must contain width*height nonnegative indices or -1')
        if any(tile >= sprites[value['sprite']]['columns'] * sprites[value['sprite']]['rows'] for tile in value['tiles'] if tile >= 0):
            raise ValueError('Tilemap tile index is outside its sprite atlas')
        for key in ('tile_width', 'tile_height'):
            if not finite_number(value[key]) or not 0 < value[key] <= 1e6:
                raise ValueError('Tilemap tile dimensions must be positive')
        if not isinstance(value['sorting_layer'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', value['sorting_layer']):
            raise ValueError('Invalid tilemap sorting layer')
        if type(value['sorting_order']) is not int or not -1000000 <= value['sorting_order'] <= 1000000:
            raise ValueError('Invalid tilemap sorting order')
        result[value['id']] = value
    return result


def scene_assets(scene, sprites):
    prefabs = scene.get('prefab_assets', [])
    libraries = [scene.get('tilemap_assets', [])] + [asset.get('tilemap_assets', []) for asset in prefabs]
    merged = {}
    for library in libraries:
        for key, value in validate_assets(library, sprites).items():
            if key in merged and merged[key] != value:
                raise ValueError(f'Conflicting tilemap asset: {key}')
            merged[key] = deepcopy(value)
    return [merged[key] for key in sorted(merged)]
