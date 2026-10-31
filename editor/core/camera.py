"""Builtin camera settings; transforms and hierarchy remain ordinary entities."""
from copy import deepcopy
from .scene import finite_number


def default_camera():
    return {'projection': 'perspective', 'fov': 60., 'size': 10., 'near': .1, 'far': 1000.}


def validate_camera(value):
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != set(default_camera()):
        raise ValueError('Camera requires projection, fov, size, near and far')
    if value['projection'] not in ('perspective', 'orthographic'):
        raise ValueError('Camera projection must be perspective or orthographic')
    if any(not finite_number(value[key]) for key in ('fov', 'size', 'near', 'far')):
        raise ValueError('Camera settings must be finite numbers')
    if not 1 <= value['fov'] <= 179:
        raise ValueError('Camera vertical FOV must be between 1 and 179 degrees')
    if not 0 < value['size'] <= 1e9:
        raise ValueError('Camera orthographic height must be positive and at most 1e9')
    if not 0 < value['near'] < value['far'] <= 1e9:
        raise ValueError('Camera clipping planes require 0 < near < far <= 1e9')


def prune_active_camera(scene):
    selected = scene.get('active_camera', '')
    if selected and not any(e['id'] == selected and e.get('camera') is not None for e in scene['entities']):
        scene.pop('active_camera', None)


def create_camera(scene):
    from .scene import create_entity, validate_scene
    result, eid = create_entity(scene, 'Camera')
    camera = next(e for e in result['entities'] if e['id'] == eid)
    camera.update(camera=default_camera(), position=[0., 2., 6.])
    if not result.get('active_camera'):
        result['active_camera'] = eid
    return validate_scene(result), eid


def set_active_camera(scene, eid):
    from .scene import validate_scene
    result = deepcopy(scene)
    if eid:
        result['active_camera'] = eid
    else:
        result.pop('active_camera', None)
    return validate_scene(result)
