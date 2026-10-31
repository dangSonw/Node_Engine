"""Authored sprite state machines shared by scene validation and native export."""
from copy import deepcopy
import re
import uuid
from .scene import entity_text, finite_number

ASSET_FIELDS = frozenset(('version', 'type', 'id', 'name', 'sprite', 'states', 'initial', 'fps', 'loop'))


def new_asset(sprite, name='Sprite State Machine'):
    return dict(version=1, type='sprite_state_machine', id=uuid.uuid4().hex, name=name,
                sprite=sprite, states={'idle': [0]}, initial='idle', fps=12., loop=True)


def validate_assets(values, sprites=None):
    if not isinstance(values, list) or len(values) > 1024:
        raise ValueError('At most 1024 sprite state machines are allowed')
    sprites = sprites or {}
    result = {}
    for value in values:
        if not isinstance(value, dict) or value.keys() != ASSET_FIELDS:
            raise ValueError('Invalid sprite state machine fields')
        if type(value['version']) is not int or value['version'] != 1 or value['type'] != 'sprite_state_machine':
            raise ValueError('Unsupported sprite state machine version/type')
        sid = value['id']
        if not isinstance(sid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', sid) or sid in result:
            raise ValueError('Sprite state machine IDs must be unique')
        if not entity_text(value['name'], 512):
            raise ValueError('Invalid sprite state machine name')
        if not isinstance(value['sprite'], str) or value['sprite'] not in sprites:
            raise ValueError('Sprite state machine references an unknown sprite asset')
        states = value['states']
        if not isinstance(states, dict) or not states or len(states) > 256:
            raise ValueError('Sprite state machine requires 1–256 states')
        frame_count = sprites[value['sprite']]['columns'] * sprites[value['sprite']]['rows']
        for state, frames in states.items():
            if not isinstance(state, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', state):
                raise ValueError('Sprite state names must be identifiers')
            if not isinstance(frames, list) or not frames or len(frames) > 65536 or any(
                    type(frame) is not int or not 0 <= frame < frame_count for frame in frames):
                raise ValueError(f'Sprite state {state} contains an invalid frame')
        if not isinstance(value['initial'], str) or value['initial'] not in states:
            raise ValueError('Sprite state machine initial state is unknown')
        if not finite_number(value['fps']) or not 0 < value['fps'] <= 240:
            raise ValueError('Sprite state machine fps must be between 0 and 240')
        if type(value['loop']) is not bool:
            raise ValueError('Sprite state machine loop must be boolean')
        result[sid] = value
    return result


def scene_assets(scene, sprites):
    prefabs = scene.get('prefab_assets', [])
    if not isinstance(prefabs, list) or any(not isinstance(item, dict) for item in prefabs):
        raise ValueError('Prefab assets must be an array of objects')
    values = list(scene.get('sprite_state_assets', []))
    values.extend(item.get('sprite_state_assets', []) for item in prefabs)
    flattened = []
    for item in values:
        flattened.extend(item if isinstance(item, list) else [item])
    return validate_assets(flattened, sprites)


def binding(asset, state=None):
    return None if not asset else {'asset': asset, 'state': state or ''}


def validate_binding(value, assets):
    if value is None:
        return
    if not isinstance(value, dict) or not {'asset', 'state'} <= set(value) or set(value) - {'asset', 'state', 'frame', 'elapsed', 'playing'}:
        raise ValueError('Sprite state binding requires asset and state')
    if not isinstance(value['asset'], str) or value['asset'] not in assets:
        raise ValueError('Sprite state binding references an unknown asset')
    if not isinstance(value['state'], str) or value['state'] not in assets[value['asset']]['states']:
        raise ValueError('Sprite state binding references an unknown state')
    if 'frame' in value and (type(value['frame']) is not int or value['frame'] not in assets[value['asset']]['states'][value['state']]):
        raise ValueError('Sprite state binding frame is outside the selected state')
    if 'elapsed' in value and (not finite_number(value['elapsed']) or value['elapsed'] < 0):
        raise ValueError('Sprite state binding elapsed time is invalid')
    if 'playing' in value and type(value['playing']) is not bool:
        raise ValueError('Sprite state binding playing flag must be boolean')


def put_asset(scene, asset):
    from .scene import validate_scene
    sprites = __import__('editor.core.sprites', fromlist=['scene_assets']).scene_assets(scene)
    validate_assets([asset], {item['id']: item for item in sprites})
    result = deepcopy(scene)
    assets = {item['id']: item for item in scene_assets(result, {item['id']: item for item in sprites})}
    assets[asset['id']] = deepcopy(asset)
    result['sprite_state_assets'] = list(assets.values())
    return validate_scene(result)
