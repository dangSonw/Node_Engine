"""Versioned prefab assets and deterministic authoring resolution.

Assets retain their base/nested dependencies and patches. ``resolve`` is a
derived view, not a replacement for the authored file or a native instance.
Entity-valued component fields use local IDs; cross-scene references are rejected.
"""
from copy import deepcopy
import json
from pathlib import Path
import re
import uuid

from .components import signatures, validate_instances
from .data_types import default_value
from .scene import descendant_ids, entity, entity_text, validate_scene
from .materials import merge_assets, scene_assets
from . import sprites

MAX_ASSETS = 1024
MAX_ENTITIES = 65536
MAX_DEPENDENCY_DEPTH = 32
_ID = re.compile(r'[A-Za-z0-9_-]{1,48}')
_FIELDS = frozenset(('name', 'parent', 'position', 'rotation', 'scale', 'mesh',
                     'visible', 'active', 'layer', 'tags', 'components', 'camera', 'material', 'sprite', 'rigid_body'))
_ASSET_FIELDS = frozenset(('version', 'type', 'id', 'name', 'root', 'entities',
                          'base', 'nested', 'overrides', 'removed', 'component_definitions', 'material_assets', 'sprite_assets'))


def _identifier(value, label):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f'{label} requires 1–48 letters, digits, underscores or hyphens')
    return value


def _object(value, label):
    if not isinstance(value, dict):
        raise ValueError(f'{label} must be an object')
    return value


def _array(value, label, limit=MAX_ENTITIES):
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError(f'{label} requires an array of at most {limit} items')
    return value


def _known(value, allowed, label):
    _object(value, label)
    if extra := value.keys() - allowed:
        raise ValueError(f'{label}: unsupported fields {sorted(extra)}')


def _component_defaults(schema):
    return {'enabled': True, 'properties': {
        str(p['id']): deepcopy(p.get('default', default_value(p['type'])))
        for p in schema['properties']}}


def _normalized(item, schemas):
    _known(item, _FIELDS | {'id'}, 'Prefab entity')
    result = dict(name=item['id'], parent='', mesh='', visible=True, active=True,
                  layer=0, tags=[], components={}, camera=None, material=None, sprite=None, rigid_body=None)
    result.update(deepcopy(item))
    # Flecs serializes Tags as a set. Keep the authored comparison canonical so
    # a native roundtrip cannot turn ordering alone into an instance override.
    if isinstance(result['tags'], list) and all(isinstance(t, str) for t in result['tags']):
        result['tags'].sort()
    validate_instances(result['components'], schemas)
    for cid, instance in result['components'].items():
        _known(instance, {'enabled', 'properties'}, f'Component instance {cid}')
        complete = _component_defaults(schemas[int(cid)])
        complete['enabled'] = instance.get('enabled', True)
        complete['properties'].update(instance.get('properties', {}))
        result['components'][cid] = complete
    return result


def _references(item, schemas, remap):
    """Rewrite only typed references; identical strings and map keys stay intact."""
    for cid, instance in item.get('components', {}).items():
        for field in schemas[int(cid)]['properties']:
            key, kind = str(field['id']), field['type']
            if key not in instance.get('properties', {}):
                continue
            value = instance['properties'][key]
            if kind == 'entity':
                instance['properties'][key] = remap(value)
            elif kind == 'array<entity>':
                instance['properties'][key] = [remap(v) for v in value]
            elif kind == 'map<entity>':
                instance['properties'][key] = {k: remap(v) for k, v in value.items()}


def _patch(entities, patches, schemas):
    _object(patches, 'Prefab overrides')
    for local, patch in patches.items():
        if local not in entities:
            raise ValueError(f'Override targets missing local entity: {local}')
        _known(patch, _FIELDS, f'Override {local}')
        target = entities[local]
        for prop, value in patch.items():
            if prop != 'components':
                target[prop] = deepcopy(value)
                continue
            for cid, edit in _object(value, 'Component overrides').items():
                if cid not in {str(k) for k in schemas}:
                    raise ValueError(f'Unknown component override: {cid}')
                instances = target['components']
                if edit is None:
                    if cid not in instances:
                        raise ValueError(f'Cannot remove absent component {local}.{cid}')
                    del instances[cid]
                    continue
                _known(edit, {'enabled', 'properties'}, f'Component override {cid}')
                instance = instances.setdefault(cid, _component_defaults(schemas[int(cid)]))
                if 'enabled' in edit:
                    instance['enabled'] = deepcopy(edit['enabled'])
                if 'properties' in edit:
                    instance['properties'].update(deepcopy(_object(edit['properties'], 'Property overrides')))
        validate_instances(target['components'], schemas)


def _validate_tree(entities, root, schemas, materials=(), sprite_assets=()):
    if root not in entities:
        raise ValueError(f'Prefab root is missing: {root}')
    if any(not isinstance(e['mesh'], str) for e in entities.values()):
        raise ValueError('Prefab mesh must be a project-relative path or an empty string')
    scene = {'version': 1, 'entities': list(entities.values()), 'variables': {},
             'component_definitions': list(schemas.values()), 'material_assets': list(materials), 'sprite_assets': list(sprite_assets)}
    validate_scene(scene)
    if entities[root]['parent'] or any(not e['parent'] for k, e in entities.items() if k != root):
        raise ValueError('A prefab must contain exactly one root and its descendants')
    def internal(value):
        if value and value not in entities:
            raise ValueError(f'Prefab reference targets missing local entity: {value}')
        return value
    for item in entities.values():
        _references(item, schemas, internal)


class PrefabLibrary:
    """Immutable asset snapshot; callers receive copies of all resolved documents."""

    def __init__(self, assets, component_definitions=(), material_assets=(), sprite_assets=()):
        _array(assets, 'Prefab assets', MAX_ASSETS)
        self._assets, self._cache = {}, {}
        for asset in assets:
            _known(asset, _ASSET_FIELDS, 'Prefab asset')
        self._material_assets = merge_assets(list(material_assets), *(a.get('material_assets', []) for a in assets))
        self._sprite_assets = sprites.merge_assets(list(sprite_assets), *(a.get('sprite_assets', []) for a in assets))
        definitions = {}
        for definition in list(component_definitions):
            signatures([definition])
            cid = definition['id']
            if cid in definitions:
                raise ValueError(f'Duplicate component definition: {cid}')
            definitions[cid] = deepcopy(definition)
        for asset in deepcopy(assets):
            _known(asset, _ASSET_FIELDS, 'Prefab asset')
            if type(asset.get('version')) is not int or asset['version'] != 1 or asset.get('type') != 'prefab':
                raise ValueError('Unsupported prefab type/version')
            aid = _identifier(asset.get('id'), 'Prefab ID')
            if aid in self._assets:
                raise ValueError(f'Duplicate prefab ID: {aid}')
            if not entity_text(asset.get('name'), 512):
                raise ValueError('Prefab name must be nonempty text, at most 512 UTF-8 bytes')
            _array(asset.get('entities', []), 'Prefab entities')
            _array(asset.get('nested', []), 'Nested prefabs')
            _array(asset.get('removed', []), 'Removed local IDs')
            _object(asset.get('overrides', {}), 'Prefab overrides')
            local_schemas = signatures(asset.get('component_definitions', []))
            for cid, schema in local_schemas.items():
                if cid in definitions and definitions[cid] != schema:
                    raise ValueError(f'Conflicting component definition: {cid}')
                definitions[cid] = schema
            self._assets[aid] = asset
        self._schemas = signatures(list(definitions.values()))
        # Validate the entire dependency graph, including unused library entries.
        for aid in self._assets:
            self._resolve(aid, ())

    @property
    def assets(self):
        return [deepcopy(self._assets[k]) for k in sorted(self._assets)]

    @property
    def material_assets(self):
        return deepcopy(self._material_assets)

    @property
    def sprite_assets(self):
        return deepcopy(self._sprite_assets)

    @property
    def component_definitions(self):
        return [deepcopy(self._schemas[k]) for k in sorted(self._schemas)]

    def resolve(self, asset_id):
        _identifier(asset_id, 'Prefab ID')
        return deepcopy(self._resolve(asset_id, ()))

    def _resolve(self, aid, chain):
        if aid in chain:
            raise ValueError('Prefab dependency cycle: ' + ' -> '.join((*chain, aid)))
        if len(chain) >= MAX_DEPENDENCY_DEPTH:
            raise ValueError(f'Prefab dependencies exceed {MAX_DEPENDENCY_DEPTH} levels')
        if aid not in self._assets:
            raise ValueError(f'Missing prefab dependency: {aid}')
        # Check depth even for cached dependencies (asset input order is irrelevant).
        if aid in self._cache:
            cached = self._cache[aid]
            if len(chain) + cached['dependency_depth'] > MAX_DEPENDENCY_DEPTH:
                raise ValueError(f'Prefab dependencies exceed {MAX_DEPENDENCY_DEPTH} levels')
            return cached
        asset, entities, dependencies, depth = self._assets[aid], {}, set(), 1
        bases = {}
        base = asset.get('base', '')
        if not isinstance(base, str):
            raise ValueError('Prefab base must be an asset ID')
        if base:
            _identifier(base, 'Base prefab ID')
            resolved = self._resolve(base, (*chain, aid))
            entities = {e['id']: deepcopy(e) for e in resolved['entities']}
            bases = {local: {'asset': base, 'local': local} for local in entities}
            root = resolved['root']
            if asset.get('root', root) != root:
                raise ValueError('A prefab variant cannot replace its inherited root ID')
            dependencies.update((base, *resolved['dependencies']))
            depth = max(depth, 1 + resolved['dependency_depth'])
        else:
            root = _identifier(asset.get('root'), 'Root local ID')
        for item in asset.get('entities', []):
            _object(item, 'Prefab entity')
            local = _identifier(item.get('id'), 'Local entity ID')
            if local in entities:
                raise ValueError(f'Duplicate local entity ID: {local}; use overrides for inherited entities')
            entities[local] = _normalized(item, self._schemas)
        for binding in asset.get('nested', []):
            _known(binding, {'id', 'prefab', 'parent', 'overrides'}, 'Nested prefab binding')
            prefix = _identifier(binding.get('id'), 'Nested local ID')
            nested_id = _identifier(binding.get('prefab'), 'Nested prefab ID')
            resolved = self._resolve(nested_id, (*chain, aid))
            dependencies.update((nested_id, *resolved['dependencies']))
            depth = max(depth, 1 + resolved['dependency_depth'])
            nested = {e['id']: deepcopy(e) for e in resolved['entities']}
            _patch(nested, binding.get('overrides', {}), self._schemas)
            _validate_tree(nested, resolved['root'], self._schemas)
            mapping = {k: prefix if k == resolved['root'] else f'{prefix}/{k}' for k in nested}
            if entities.keys() & mapping.values():
                raise ValueError(f'Nested prefab local ID collision: {prefix}')
            for local, item in nested.items():
                item['id'] = mapping[local]
                item['parent'] = binding.get('parent', '') if local == resolved['root'] else mapping[item['parent']]
                _references(item, self._schemas, lambda v: mapping[v] if v else '')
                entities[item['id']] = item
                bases[item['id']] = {'asset': nested_id, 'local': local}
            if len(entities) > MAX_ENTITIES:
                raise ValueError(f'Expanded prefab exceeds {MAX_ENTITIES} entities')
        _patch(entities, asset.get('overrides', {}), self._schemas)
        removed = asset.get('removed', [])
        if any(not isinstance(k, str) for k in removed) or len(set(removed)) != len(removed):
            raise ValueError('Removed local IDs must be unique strings')
        if root in removed:
            raise ValueError('Cannot remove the prefab root')
        missing = set(removed) - entities.keys()
        if missing:
            raise ValueError(f'Removal targets missing local entities: {sorted(missing)}')
        # Validate parent links first so cascade cannot hide a hierarchy cycle.
        validate_scene({'entities': list(entities.values()), 'variables': {},
                        'component_definitions': list(self._schemas.values()), 'material_assets': self.material_assets, 'sprite_assets': self.sprite_assets})
        children = {}
        for local, item in entities.items():
            children.setdefault(item['parent'], []).append(local)
        removed_set, pending = set(), list(removed)
        while pending:
            local = pending.pop()
            if local not in removed_set:
                removed_set.add(local)
                pending.extend(children.get(local, []))
        for local in removed_set:
            del entities[local]
            bases.pop(local, None)
        _validate_tree(entities, root, self._schemas, self.material_assets, self.sprite_assets)
        resolved = {'id': aid, 'root': root, 'entities': [entities[k] for k in sorted(entities)],
                    'dependencies': sorted(dependencies), 'dependency_depth': depth,
                    'bases': bases}
        self._cache[aid] = resolved
        return resolved

    def instantiate_entities(self, asset_id, *, mapping=None, parent='', position=None):
        """Prepare an instance for authoring/native import, retaining its ID map.

        This returns data, not a Flecs entity. Existing mappings must cover exactly
        the resolved local IDs; callers explicitly reconcile structural changes.
        """
        resolved = self.resolve(asset_id)
        locals_ = {e['id'] for e in resolved['entities']}
        if mapping is None:
            mapping = {k: uuid.uuid4().hex for k in sorted(locals_)}
        mapping = deepcopy(_object(mapping, 'Prefab instance mapping'))
        if set(mapping) != locals_:
            raise ValueError('Prefab instance mapping must cover exactly the resolved local IDs')
        if any(not entity_text(v, 128) for v in mapping.values()) or len(set(mapping.values())) != len(mapping):
            raise ValueError('Prefab instance IDs must be valid and unique')
        if not isinstance(parent, str) or (parent and (not entity_text(parent, 128) or parent in mapping.values())):
            raise ValueError('Prefab instance parent must be outside the instance')
        root = mapping[resolved['root']]
        for item in resolved['entities']:
            local = item['id']
            item['id'] = mapping[local]
            item['parent'] = '' if local == resolved['root'] else mapping[item['parent']]
            if local == resolved['root'] and position is not None:
                item['position'] = deepcopy(position)
            _references(item, self._schemas, lambda v: mapping[v] if v else '')
        validate_scene({'entities': resolved['entities'], 'variables': {},
                        'component_definitions': self.component_definitions, 'material_assets': self.material_assets, 'sprite_assets': self.sprite_assets})
        next(e for e in resolved['entities'] if e['id'] == root)['parent'] = parent
        return {'prefab': asset_id, 'root': root, 'mapping': mapping, 'entities': resolved['entities']}


def capture_prefab(scene, root, name, *, asset_id=None, external_references='reject'):
    """Capture a subtree, with portable local references and its used schemas.

    External entity references require explicit opt-in to clearing; strings and
    collection keys are never interpreted as entity references.
    """
    validate_scene(scene)
    entity(scene, root)
    if external_references not in ('reject', 'clear'):
        raise ValueError('External reference policy must be reject or clear')
    selected = {root} | descendant_ids(scene, root)
    mapping = {root: 'root', **{k: f'e{i+1}' for i, k in enumerate(sorted(selected - {root}))}}
    schemas = signatures(scene.get('component_definitions', []))
    used, result = set(), []
    def local_reference(value):
        if not value or value in mapping:
            return mapping.get(value, '')
        if external_references == 'clear':
            return ''
        raise ValueError(f'External entity reference {value!r}; include it or explicitly clear external references')
    for item in scene['entities']:
        if item['id'] not in selected:
            continue
        item = _normalized(item, schemas)
        source = item['id']
        item['id'] = mapping[source]
        item['parent'] = '' if source == root else mapping[item['parent']]
        used.update(int(k) for k in item['components'])
        _references(item, schemas, local_reference)
        result.append(item)
    asset = {'version': 1, 'type': 'prefab', 'id': asset_id or uuid.uuid4().hex,
             'name': name, 'root': 'root', 'entities': sorted(result, key=lambda e: e['id']),
             'component_definitions': [deepcopy(schemas[k]) for k in sorted(used)]}
    used_sprites = {item['sprite']['asset'] for item in result if item['sprite'] is not None}
    if used_sprites:
        asset['sprite_assets'] = [a for a in sprites.scene_assets(scene) if a['id'] in used_sprites]
    used_materials = {item['material']['asset'] for item in result if item['material'] is not None}
    if used_materials:
        asset['material_assets'] = [a for a in scene_assets(scene) if a['id'] in used_materials]
    PrefabLibrary([asset])
    return asset


def load_prefab(path):
    """Read one authored file; resolve with its dependencies through PrefabLibrary."""
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    def invalid_number(value):
        raise ValueError(f'Non-finite JSON number: {value}')
    value = json.loads(Path(path).read_text('utf-8'), object_pairs_hook=unique_pairs,
                       parse_constant=invalid_number)
    _known(value, _ASSET_FIELDS, 'Prefab asset')
    return value


def load_prefab_library(project_root, paths, component_definitions=()):
    """Only resolve explicitly listed project assets; never follow an arbitrary path."""
    from .scene import asset_path
    root = Path(project_root).resolve()
    _array(paths, 'Prefab paths', MAX_ASSETS)
    assets, seen = [], set()
    for relative in paths:
        path = (root / asset_path(relative)).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Prefab path escapes project directory')
        if path in seen:
            raise ValueError(f'Duplicate prefab asset path: {relative}')
        seen.add(path)
        assets.append(load_prefab(path))
    return PrefabLibrary(assets, component_definitions)


def validate_scene_prefabs(scene, library=None):
    """Validate instance ownership independently of editable scene parenting.

    Missing mapped children are tombstones after runtime destruction. Their IDs
    stay reserved so a later spawn cannot change the meaning of old references.
    """
    library = library or PrefabLibrary(scene.get('prefab_assets', []), scene.get('component_definitions', []), scene.get('material_assets', []), scene.get('sprite_assets', []))
    live = {e['id']: e for e in scene['entities']}
    schemas = signatures(library.component_definitions)
    claimed = set()
    for instance in _array(scene.get('prefab_instances', []), 'Prefab instances'):
        _known(instance, {'prefab', 'root', 'mapping', 'owned_components', 'component_overrides', 'retired'}, 'Prefab instance')
        resolved = library.resolve(instance.get('prefab'))
        mapping = _object(instance.get('mapping'), 'Prefab instance mapping')
        if set(mapping) != {e['id'] for e in resolved['entities']}:
            raise ValueError('Prefab instance mapping must cover exactly the resolved local IDs')
        if any(not entity_text(v, 128) for v in mapping.values()) or len(set(mapping.values())) != len(mapping):
            raise ValueError('Prefab instance IDs must be valid and unique')
        if claimed & set(mapping.values()):
            raise ValueError('Prefab instances cannot share entity IDs, including removed children')
        claimed.update(mapping.values())
        retired = _object(instance.get('retired', {}), 'Retired prefab mapping')
        if (len(retired) > MAX_ENTITIES or set(retired) & set(mapping) or
                any(not entity_text(k, 128) or not entity_text(v, 128) for k, v in retired.items()) or
                len(set(retired.values())) != len(retired) or
                set(retired.values()) & (claimed | live.keys())):
            raise ValueError('Retired prefab IDs must be unique, absent and separate from live mappings')
        claimed.update(retired.values())
        if instance.get('root') != mapping[resolved['root']] or instance['root'] not in live:
            raise ValueError('Prefab instance requires its live mapped root')
        for local, names in _object(instance.get('owned_components', {}), 'Owned prefab components').items():
            if local not in mapping or not isinstance(names, list) or any(
                    not isinstance(n, str) or n not in BUILTIN_FIELDS for n in names
            ) or len(set(names)) != len(names):
                raise ValueError('Invalid prefab owned component list')
        for local, components in _object(instance.get('component_overrides', {}), 'Prefab component overrides').items():
            if local not in mapping or mapping[local] not in live:
                raise ValueError('Component overrides require a live prefab member')
            values = live[mapping[local]].get('components', {})
            for cid, mask in _object(components, 'Prefab component overrides').items():
                if cid not in {str(k) for k in schemas}:
                    raise ValueError('Unknown prefab component override')
                _known(mask, {'present', 'enabled', 'properties'}, 'Prefab component override')
                if not mask or ('present' in mask and (
                        not isinstance(mask['present'], bool) or mask['present'] != (cid in values))):
                    raise ValueError('Prefab component presence override disagrees with entity')
                if 'enabled' in mask and (mask['enabled'] is not True or cid not in values):
                    raise ValueError('Invalid prefab component enabled override')
                if 'properties' in mask:
                    fields = mask['properties']
                    known = {p['id'] for p in schemas[int(cid)]['properties']}
                    if (cid not in values or not isinstance(fields, list) or not fields or
                            any(type(p) is not int or p not in known for p in fields) or
                            len(fields) != len(set(fields))):
                        raise ValueError('Invalid prefab component property overrides')
    return library


def prepare_scene_prefabs(scene):
    """Compile authored prefab dependencies into native template descriptors."""
    if not isinstance(scene, dict):
        return scene  # The ordinary scene validator reports the document error.
    if not any(k in scene for k in ('prefab_assets', 'prefab_templates', 'prefab_instances')):
        return scene
    if 'prefab_templates' in scene and 'prefab_assets' not in scene:
        raise ValueError('Compiled prefab templates require authored prefab assets')
    result = deepcopy(scene)
    library = PrefabLibrary(result.get('prefab_assets', []), result.get('component_definitions', []), result.get('material_assets', []), result.get('sprite_assets', []))
    result['component_definitions'] = library.component_definitions
    if library.material_assets: result['material_assets'] = library.material_assets
    if library.sprite_assets: result['sprite_assets'] = library.sprite_assets
    # Validate ordinary entity records before the instance validator reads IDs.
    # The authored library is already validated, so omit its keys for this pass.
    validate_scene({k: v for k, v in result.items()
                    if k not in ('prefab_assets', 'prefab_templates', 'prefab_instances')})
    validate_scene_prefabs(result, library)
    templates = [library.resolve(a['id']) for a in library.assets]
    if sum(len(t['entities']) for t in templates) > MAX_ENTITIES:
        raise ValueError(f'Native prefab library exceeds {MAX_ENTITIES} template entities')
    result['prefab_templates'] = sorted(templates, key=lambda t: (t['dependency_depth'], t['id']))
    return result


def add_scene_prefab(scene, root, name):
    """Capture into the scene's authored library as one undoable document edit."""
    asset = capture_prefab(scene, root, name)
    result = deepcopy(scene)
    result.setdefault('prefab_assets', []).append(asset)
    result.pop('prefab_templates', None)
    validate_scene(result)
    return result, asset['id']


def instantiate_scene_prefab(scene, asset_id, *, parent='', position=None):
    """Create an authored instance with stable IDs, ready for real native IsA."""
    validate_scene(scene)
    library = PrefabLibrary(scene.get('prefab_assets', []), scene.get('component_definitions', []), scene.get('material_assets', []), scene.get('sprite_assets', []))
    if parent:
        entity(scene, parent)
    record = library.instantiate_entities(asset_id, parent=parent, position=position)
    reserved = {e['id'] for e in scene['entities']}
    for existing in scene.get('prefab_instances', []):
        reserved.update(existing['mapping'].values())
        reserved.update(existing.get('retired', {}).values())
    if reserved & set(record['mapping'].values()):
        raise ValueError('Prefab instance IDs collide with reserved scene IDs')
    result = deepcopy(scene)
    result['component_definitions'] = library.component_definitions
    if library.material_assets: result['material_assets'] = library.material_assets
    if library.sprite_assets: result['sprite_assets'] = library.sprite_assets
    result['entities'].extend(record.pop('entities'))
    record['owned_components'] = {local: [] for local in record['mapping']}
    if position is not None:
        record['owned_components'][library.resolve(asset_id)['root']] = ['transform']
    result.setdefault('prefab_instances', []).append(record)
    result.pop('prefab_templates', None)
    return validate_scene(result), record['root']


BUILTIN_FIELDS = {'transform': ('position', 'rotation', 'scale'), 'mesh': ('mesh', 'visible'),
                  'tags': ('tags',), 'activity': ('active', 'layer'), 'camera': ('camera',), 'material': ('material',), 'sprite': ('sprite',),
                  'rigid_body': ('rigid_body',)}


def record_instance_write(scene, eid, prop):
    """Mark the same Flecs component granularity used by native node writes.

    Called on a private candidate scene, before applying the actual property.
    Older records with inferred ownership retain all their existing differences.
    """
    group = next((name for name, fields in BUILTIN_FIELDS.items() if prop in fields), None)
    if group is None:
        return
    for record in scene.get('prefab_instances', []):
        local = next((key for key, value in record['mapping'].items() if value == eid), None)
        if local is None:
            continue
        owned = record.setdefault('owned_components', {})
        if local not in owned:
            library = PrefabLibrary(scene['prefab_assets'], scene.get('component_definitions', []), scene.get('material_assets', []), scene.get('sprite_assets', []))
            template = next(e for e in library.resolve(record['prefab'])['entities'] if e['id'] == local)
            current = _normalized(entity(scene, eid), signatures(library.component_definitions))
            owned[local] = [name for name, fields in BUILTIN_FIELDS.items()
                            if any(current[field] != template[field] for field in fields)]
        names = set(owned[local]) | {group}
        owned[local] = [name for name in BUILTIN_FIELDS if name in names]
        return


def record_component_write(scene, eid, cid, operation, field=None):
    """Record deliberate writes, including values equal to the current template."""
    for record in scene.get('prefab_instances', []):
        local = next((key for key, value in record['mapping'].items() if value == eid), None)
        if local is None:
            continue
        components = record.setdefault('component_overrides', {}).setdefault(local, {})
        key = str(cid)
        if operation in ('add', 'remove'):
            components[key] = {'present': operation == 'add'}
        else:
            mask = components.setdefault(key, {})
            if operation == 'enable':
                mask['enabled'] = True
            elif operation == 'set':
                mask['properties'] = sorted(set(mask.get('properties', [])) | {field})
        return
