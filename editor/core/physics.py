"""Authored rigid-body settings; live motion belongs to the native physics world."""
from .scene import finite_number
import math


def default_body():
    return dict(shape='box', motion='dynamic', half_extents=[.5, .5, .5], radius=.5,
                half_height=.5, mass=1., friction=.5, restitution=0., gravity_scale=1.,
                linear_damping=.05, angular_damping=.05, mask=4294967295,
                sensor=False, continuous=False, enabled=True)


def default_character():
    return dict(max_slope=45., step_height=.3, floor_snap=.4, max_strength=100.)


def validate_body(value):
    if value is None:
        return
    if not isinstance(value, dict) or value.keys() - {'character', 'parts'} != default_body().keys():
        raise ValueError('Rigid body requires all shape, motion and material settings')
    if value['shape'] not in ('box', 'sphere', 'capsule', 'compound', 'mesh'):
        raise ValueError('Collider shape must be box, sphere, capsule, compound or mesh')
    if value['shape'] in ('compound', 'mesh'):
        parts = value.get('parts')
        if not isinstance(parts, list) or not 1 <= len(parts) <= 256:
            raise ValueError('Compound and mesh colliders require 1 to 256 parts')
        if value['shape'] == 'mesh' and (value['motion'] != 'static' or len(parts) != 1 or parts[0].get('shape') != 'mesh'):
            raise ValueError('Mesh colliders require one static mesh part')
        for part in parts:
            if not isinstance(part, dict) or set(part) != {'shape', 'position', 'rotation', 'half_extents', 'radius', 'half_height', 'vertices', 'triangles'}:
                raise ValueError('Collider parts require shape, transform and geometry')
            if part['shape'] not in ('box', 'sphere', 'capsule', 'mesh'):
                raise ValueError('Invalid collider part shape')
            for key in ('position', 'half_extents'):
                vector = part[key]
                if not isinstance(vector, list) or len(vector) != 3 or any(not finite_number(v) for v in vector):
                    raise ValueError(f'Collider part {key} must be a finite vec3')
            if any(abs(v) > 1e9 for v in part['position']):
                raise ValueError('Collider part position is out of range')
            if any(not .001 <= v <= 1e5 for v in part['half_extents']):
                raise ValueError('Collider part half extents require values from 0.001 to 100000')
            rotation = part['rotation']
            if not isinstance(rotation, list) or len(rotation) != 4 or any(not finite_number(v) for v in rotation) or sum(v*v for v in rotation) < 1e-24:
                raise ValueError('Collider part rotation must be a nonzero finite quaternion')
            for key, low, high in [('radius', .001, 1e5), ('half_height', .001, 1e5)]:
                if not finite_number(part[key]) or not low <= part[key] <= high:
                    raise ValueError(f'Collider part {key} must be from {low:g} to {high:g}')
            if not isinstance(part['vertices'], list) or not isinstance(part['triangles'], list):
                raise ValueError('Collider mesh data must be arrays')
            if part['shape'] == 'mesh':
                if not 3 <= len(part['vertices']) <= 1000000 or not 1 <= len(part['triangles']) <= 1000000:
                    raise ValueError('Collider mesh requires bounded vertices and triangles')
                for vertex in part['vertices']:
                    if not isinstance(vertex, list) or len(vertex) != 3 or any(not finite_number(v) or abs(v) > 1e6 for v in vertex):
                        raise ValueError('Collider mesh vertices must be finite vec3 values')
                for triangle in part['triangles']:
                    if not isinstance(triangle, list) or len(triangle) != 3 or any(type(index) is not int or not 0 <= index < len(part['vertices']) for index in triangle):
                        raise ValueError('Collider mesh triangles contain an invalid index')
            elif part['vertices'] or part['triangles']:
                raise ValueError('Primitive collider parts cannot contain mesh data')
        if value['shape'] == 'compound' and value['motion'] != 'static' and any(part['shape'] == 'mesh' for part in parts):
            raise ValueError('A dynamic compound collider cannot contain a mesh part')
    elif 'parts' in value:
        raise ValueError('Primitive colliders cannot contain parts')
    if value['motion'] not in ('static', 'kinematic', 'dynamic'):
        raise ValueError('Body motion must be static, kinematic or dynamic')
    for key in ('sensor', 'continuous', 'enabled'):
        if type(value[key]) is not bool:
            raise ValueError(f'Rigid body {key} must be boolean')
    if type(value['mask']) is not int or not 0 <= value['mask'] <= 4294967295:
        raise ValueError('Collision mask must be an integer from 0 to 4294967295')
    half = value['half_extents']
    if not isinstance(half, list) or len(half) != 3 or any(
            not finite_number(v) or not .001 <= v <= 1e5 for v in half):
        raise ValueError('Box half extents require three numbers from 0.001 to 100000')
    for key, low, high in [('radius', .001, 1e5), ('half_height', .001, 1e5),
                         ('mass', .001, 1e9), ('friction', 0, 10), ('restitution', 0, 1),
                         ('gravity_scale', -1000, 1000), ('linear_damping', 0, 1000),
                         ('angular_damping', 0, 1000)]:
        if not finite_number(value[key]) or not low <= value[key] <= high:
            raise ValueError(f'Rigid body {key} must be from {low:g} to {high:g}')
    if 'character' in value:
        config = value['character']
        if not isinstance(config, dict) or config.keys() != default_character().keys():
            raise ValueError('Character requires slope, step, floor snap and strength settings')
        if value['shape'] != 'capsule' or value['motion'] != 'kinematic' or value['sensor']:
            raise ValueError('Character needs a non-sensor kinematic capsule')
        for key, low, high in [('max_slope',1,89), ('step_height',0,100),
                               ('floor_snap',0,100), ('max_strength',0,1e9)]:
            if not finite_number(config[key]) or not low <= config[key] <= high:
                raise ValueError(f'Character {key} must be from {low:g} to {high:g}')


def validate_body_transforms(scene):
    entities = {e['id']: e for e in scene['entities']}
    bodies = [e for e in entities.values() if e.get('rigid_body') is not None]
    if len(bodies) > 4096:
        raise ValueError('At most 4096 rigid bodies are allowed')
    for body in bodies:
        current, scale, up = body, [1., 1., 1.], [0., 1., 0.]
        while current:
            local = current['scale']
            if any(v <= 0 for v in local):
                raise ValueError(f"{body['id']}: rigid bodies require positive entity and ancestor scales")
            uniform = max(local) - min(local) <= 1e-9 * max(local)
            if (current is not body or body['rigid_body']['shape'] != 'box') and not uniform:
                raise ValueError(f"{body['id']}: sphere/capsule and rigid-body ancestors require uniform scale")
            scale = [a*b for a, b in zip(scale, local)]
            # Match the native YXZ rotation order while walking child to parent.
            x,y,z = map(math.radians, current['rotation'])
            a,b,c = up
            a,b = math.cos(z)*a-math.sin(z)*b, math.sin(z)*a+math.cos(z)*b
            b,c = math.cos(x)*b-math.sin(x)*c, math.sin(x)*b+math.cos(x)*c
            up = [math.cos(y)*a+math.sin(y)*c, b, -math.sin(y)*a+math.cos(y)*c]
            current = entities.get(current.get('parent', ''))
        settings = body['rigid_body']
        if 'character' in settings and sum((a-b)**2 for a,b in zip(up,[0,1,0])) > 1e-8:
            raise ValueError(f"{body['id']}: character capsule must stay upright")
        sizes = [a*b for a,b in zip(settings['half_extents'], scale)]
        sizes += [settings['radius']*scale[0], settings['half_height']*scale[1]]
        if any(not finite_number(v) or not .001 <= v <= 1e5 for v in sizes):
            raise ValueError(f"{body['id']}: world collider dimensions must be from 0.001 to 100000")
        if settings['shape'] in ('compound', 'mesh'):
            for part in settings['parts']:
                if any(not finite_number(v) or abs(v) > 1e6 for vertex in part['vertices'] for v in vertex):
                    raise ValueError(f"{body['id']}: world mesh vertex is out of range")
