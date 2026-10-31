"""Version-one scene documents shared by UI, validation and game export."""
from copy import deepcopy
import math
import re
from pathlib import PurePosixPath, PureWindowsPath
import uuid
from .data_types import variable, variable_name_valid
from .typed_schema import build_schema, validate_variable, SCOPES


def asset_path(value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError('Asset path must use relative forward-slash notation')
    path = PurePosixPath(value)
    if path.is_absolute() or PureWindowsPath(value).drive or '..' in path.parts:
        raise ValueError('Asset path must stay within the project')
    return value


def finite_number(value):
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def entity_text(value, limit):
    return (isinstance(value, str) and bool(value.strip()) and
            len(value.encode('utf-8')) <= limit and all(ord(c) >= 32 and ord(c) != 127 for c in value))


def descendant_ids(scene, eid):
    children = {}
    for item in scene['entities']:
        children.setdefault(item.get('parent', ''), []).append(item['id'])
    result, pending = set(), list(children.get(eid, []))
    while pending:
        child = pending.pop()
        if child in result:
            continue
        result.add(child)
        pending.extend(children.get(child, []))
    return result


def validate_scene(scene):
    from .components import signatures, validate_instances
    from .camera import validate_camera
    from .physics import validate_body, validate_body_transforms
    from .materials import scene_assets, validate_assets, validate_binding
    from . import sprites, sprite_states, audio, ui
    from . import tilemaps
    from .feature_pipeline import validate_feature_document
    if not isinstance(scene, dict) or scene.get('version', 1) != 1:
        raise ValueError('Unsupported scene document/version')
    if not isinstance(scene.get('entities'), list) or not isinstance(scene.get('variables'), dict):
        raise ValueError('Scene requires entities array and variables object')
    validate_feature_document(scene)
    ids = set()
    materials = validate_assets(scene_assets(scene))
    sprite_assets = sprites.validate_assets(sprites.scene_assets(scene))
    state_assets = sprite_states.scene_assets(scene, sprite_assets)
    tilemaps.validate_assets(tilemaps.scene_assets(scene, sprite_assets), sprite_assets)
    audio.validate_assets(scene.get('audio_assets', []))
    ui.validate_assets(scene.get('ui_assets', []))
    if 'input' in scene:
        from .input import validate_input
        validate_input(scene['input'])
    components = signatures(scene.get('component_definitions', []))
    schema = build_schema(scene.get('struct_definitions', []), scene.get('enum_definitions', []))
    serial = scene.get('entity_serial', 0)
    if type(serial) is not int or not 0 <= serial <= 2**63-1:
        raise ValueError('Entity serial must be an integer between 0 and INT64_MAX')
    if len(scene['entities']) > 65536:
        raise ValueError('At most 65536 entities are allowed')
    for e in scene['entities']:
        if not isinstance(e, dict):
            raise ValueError('Entity must be an object')
        eid = e.get('id')
        if not entity_text(eid, 128) or eid in ids:
            raise ValueError('Entity IDs must be nonempty, unique text, at most 128 UTF-8 bytes, without control characters')
        ids.add(eid)
        validate_camera(e.get('camera'))
        validate_body(e.get('rigid_body'))
        validate_binding(e.get('material'), materials)
        sprites.validate_binding(e.get('sprite'), sprite_assets)
        sprite_states.validate_binding(e.get('sprite_state'), state_assets)
        validate_instances(e.get('components', {}), components)
        if not entity_text(e.get('name', eid), 512):
            raise ValueError(f'{eid}: entity name must be nonempty text, at most 512 UTF-8 bytes, without control characters')
        for flag in ('visible', 'active'):
            if type(e.get(flag, True)) is not bool:
                raise ValueError(f'{eid}: {flag} must be boolean')
        if type(e.get('layer', 0)) is not int or not 0 <= e.get('layer', 0) <= 31:
            raise ValueError(f'{eid}: layer must be an integer between 0 and 31')
        sorting_layer = e.get('sorting_layer', 'default')
        if not isinstance(sorting_layer, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', sorting_layer):
            raise ValueError(f'{eid}: sorting_layer must be an identifier')
        if type(e.get('sorting_order', 0)) is not int or not -1000000 <= e.get('sorting_order', 0) <= 1000000:
            raise ValueError(f'{eid}: sorting_order must be between -1000000 and 1000000')
        tags = e.get('tags', [])
        if not isinstance(tags, list) or len(tags) > 256 or any(not entity_text(t, 128) for t in tags) or len(set(tags)) != len(tags):
            raise ValueError(f'{eid}: tags must be unique text, at most 256 tags of 128 UTF-8 bytes each')
        for prop in ('position', 'rotation', 'scale'):
            v = e.get(prop)
            if not isinstance(v, list) or len(v) != 3 or not all(finite_number(x) for x in v):
                raise ValueError(f'{eid}: {prop} requires three finite numbers')
        if e.get('mesh'):
            asset_path(e['mesh'])
    parents = {e['id']: e.get('parent', '') for e in scene['entities']}
    selected = scene.get('active_camera', '')
    if not isinstance(selected, str) or (selected and not any(e['id'] == selected and e.get('camera') is not None for e in scene['entities'])):
        raise ValueError('Active camera must reference a live camera entity or be empty')
    for eid, parent in parents.items():
        if not isinstance(parent, str) or (parent and parent not in ids):
            raise ValueError(f'{eid}: missing parent')
    for eid in parents:
        visited, current = set(), eid
        while current:
            if current in visited:
                raise ValueError(f'{eid}: entity hierarchy cycle')
            visited.add(current)
            if len(visited) > 256:
                raise ValueError(f'{eid}: entity hierarchy exceeds 256 levels')
            current = parents[current]
    validate_body_transforms(scene)
    scopes = scene.get('variable_scopes', {})
    if not isinstance(scopes, dict):
        raise ValueError('variable_scopes must be an object')
    if set(scopes) - set(scene['variables']):
        raise ValueError('variable_scopes cannot reference unknown variables')
    for name, scope in scopes.items():
        if not isinstance(scope, str) or scope not in SCOPES:
            raise ValueError(f'{name}: variable scope must be one of {", ".join(SCOPES)}')
    for name, value in scene['variables'].items():
        if not variable_name_valid(name):
            raise ValueError('Variable names must be nonempty UTF-8 text, without NUL, at most 512 bytes')
        try:
            validate_variable(value, schema)
        except ValueError as error:
            raise ValueError(f'{name}: {error}') from error
    for field in ('global_variables', 'entity_variables', 'scene_variables'):
        if field not in scene:
            continue
        stores = scene[field]
        if not isinstance(stores, dict) or len(stores) > 65536:
            raise ValueError(f'{field} must be an object of at most 65536 entries')
        if field == 'entity_variables' and set(stores) - ids:
            raise ValueError('Entity variable owner does not exist')
        for owner, store in (stores.items() if field == 'entity_variables' else [('', stores)]):
            if not isinstance(store, dict) or len(store) > 65536:
                raise ValueError('Variable storage must contain at most 65536 values')
            for name, value in store.items():
                if not variable_name_valid(name):
                    raise ValueError('Invalid scoped variable name')
                kind, _ = validate_variable(value, schema)
                if field == 'scene_variables' and scopes.get(name, 'scene') == 'scene':
                    raise ValueError(f'{name}: redundant scene variable state')
                scope = 'entity' if field == 'entity_variables' else 'global' if field == 'global_variables' else 'scene'
                if scopes.get(name) == scope:
                    expected = validate_variable(scene['variables'][name], schema)
                    if kind != expected[0]:
                        raise ValueError(f'{name}: scoped variable type mismatch')
        if field == 'global_variables':
            for name, scope in scopes.items():
                if scope == 'global' and (name not in stores or validate_variable(stores[name], schema) != validate_variable(scene['variables'][name], schema)):
                    raise ValueError(f'{name}: global state disagrees with declaration')
    if 'prefab_assets' in scene or 'prefab_instances' in scene:
        from .prefabs import validate_scene_prefabs
        validate_scene_prefabs(scene)
    return scene


def entity(scene, eid):
    try:
        return next(e for e in scene['entities'] if e['id'] == eid)
    except StopIteration:
        raise ValueError(f'Entity does not exist: {eid}') from None


def is_active(scene, eid, entities=None):
    """Effective activity, including all ancestors, in a validated scene."""
    if entities is None:
        entities = {e['id']: e for e in scene['entities']}
    if eid not in entities:
        return False
    while eid:
        item = entities[eid]
        if not item.get('active', True):
            return False
        eid = item.get('parent', '')
    return True


def unique_name(scene, name):
    name = name.strip() or 'Entity'
    names = {e.get('name', e['id']) for e in scene['entities']}
    result, index = name, 2
    while result in names:
        result = f'{name} {index}'
        index += 1
    return result


def create_entity(scene, name='Entity', mesh=None):
    result = deepcopy(scene)
    e = {'id': uuid.uuid4().hex, 'name': unique_name(scene, name),
         'position':[0.,0.,0.], 'rotation':[0.,0.,0.], 'scale':[1.,1.,1.]}
    if mesh:
        e['mesh'] = asset_path(mesh)
    result['entities'].append(e)
    return validate_scene(result), e['id']


def duplicate_entity(scene, eid):
    result = deepcopy(scene)
    e = deepcopy(entity(scene,eid))
    e['id'], e['name'] = uuid.uuid4().hex, unique_name(scene,e.get('name',eid))
    result['entities'].append(e)
    if eid in result.get('entity_variables', {}):
        result['entity_variables'][e['id']] = deepcopy(result['entity_variables'][eid])
    return validate_scene(result), e['id']


def delete_entity(scene, eid):
    entity(scene,eid)
    result = deepcopy(scene)
    removed, pending = set(), [eid]
    children = {}
    for item in scene['entities']:
        children.setdefault(item.get('parent', ''), []).append(item['id'])
    instances = {r['root']: r for r in scene.get('prefab_instances', [])}
    # Instance roots also own members detached from the authored hierarchy.
    while pending:
        current = pending.pop()
        if current in removed:
            continue
        removed.add(current)
        pending.extend(children.get(current, []))
        if current in instances:
            pending.extend(instances[current]['mapping'].values())
    result['entities'] = [e for e in result['entities'] if e['id'] not in removed]
    if 'entity_variables' in result:
        result['entity_variables'] = {owner: values for owner, values in result['entity_variables'].items() if owner not in removed}
    from .camera import prune_active_camera
    prune_active_camera(result)
    if 'prefab_instances' in result:
        result['prefab_instances'] = [r for r in result['prefab_instances'] if r['root'] not in removed]
        for record in result['prefab_instances']:
            for local, sid in record['mapping'].items():
                if sid in removed:
                    record.get('owned_components', {}).pop(local, None)
                    record.get('component_overrides', {}).pop(local, None)
    return validate_scene(result)


def set_entity_property(scene, eid, prop, value):
    if prop not in ('name','position','rotation','scale','mesh','parent','visible','active','layer','tags','sorting_layer','sorting_order','camera','material','sprite','sprite_state','rigid_body'):
        raise ValueError(f'Unsupported entity property: {prop}')
    result = deepcopy(scene)
    from .prefabs import record_instance_write
    record_instance_write(result, eid, prop)
    target = entity(result,eid)
    if prop == 'mesh' and not value:
        target.pop('mesh', None)
    else:
        target[prop] = deepcopy(value)
    if prop == 'camera':
        from .camera import prune_active_camera
        prune_active_camera(result)
    return validate_scene(result)
