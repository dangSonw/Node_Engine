"""Transactional prefab Apply/Reset and template reconciliation for scene authoring.

Builtins preserve Flecs component ownership. User components merge at property
granularity against the previous template; arrays/maps are single property values.
No operation mutates the caller's scene or silently flattens asset dependencies.
"""
from copy import deepcopy
import uuid

from .components import signatures
from .prefabs import (BUILTIN_FIELDS, PrefabLibrary, _normalized, _references)
from .scene import entity, validate_scene


def instance_record(scene, eid):
    entity(scene, eid)
    for record in scene.get('prefab_instances', []):
        if eid in record['mapping'].values():
            return record
    raise ValueError('Select a member of a prefab instance')


def _entities(library, aid, mapping):
    return {e['id']: e for e in library.instantiate_entities(aid, mapping=mapping)['entities']}


def _owned(record, local, current, previous):
    explicit = set(record.get('owned_components', {}).get(local, []))
    return [name for name, fields in BUILTIN_FIELDS.items()
            if name in explicit or any(current[p] != previous[p] for p in fields)]


def _merge_components(previous, current, updated, overrides):
    result = deepcopy(updated)
    for cid in previous.keys() | current.keys() | overrides.keys():
        mask = overrides.get(cid, {})
        if 'present' in mask:
            if mask['present']:
                result[cid] = deepcopy(current[cid])
            else:
                result.pop(cid, None)
            continue
        if cid not in current:
            result.pop(cid, None)  # The instance explicitly removed this component.
        elif cid not in previous:
            result[cid] = deepcopy(current[cid])
        elif mask or current[cid] != previous[cid]:
            if cid not in updated:
                result[cid] = deepcopy(current[cid])
                continue
            old, own = previous[cid], current[cid]
            if mask.get('enabled') or own['enabled'] != old['enabled']:
                result[cid]['enabled'] = own['enabled']
            for field, value in own['properties'].items():
                if int(field) in mask.get('properties', []) or value != old['properties'][field]:
                    result[cid]['properties'][field] = deepcopy(value)
    return result


def _members_and_children(scene, record):
    children = {}
    for item in scene['entities']:
        children.setdefault(item.get('parent', ''), []).append(item['id'])
    found, pending = set(), list(record['mapping'].values())
    while pending:
        eid = pending.pop()
        if eid not in found:
            found.add(eid)
            pending.extend(children.get(eid, []))
    return found


def reconcile_prefab_assets(scene, assets, *, _reset=(), _adopt=None, _consume=(), keep_placement=True):
    """Replace an authored library, propagating changes to all its live instances.

    Existing local IDs keep their entity IDs, including deleted-child tombstones.
    Template removals retire IDs; reintroducing the same local ID restores that ID.
    Added ordinary children survive propagation; if their parent was removed they
    move to the nearest surviving ancestor. Invalid dependent assets reject the
    entire edit, so callers can repair a dependency together in the same transaction.
    """
    validate_scene(scene)
    old = PrefabLibrary(scene.get('prefab_assets', []), scene.get('component_definitions', []), scene.get('material_assets', []), scene.get('sprite_assets', []))
    new = PrefabLibrary(assets, scene.get('component_definitions', []), scene.get('material_assets', []), scene.get('sprite_assets', []))
    schemas = signatures(new.component_definitions)
    original = {e['id']: _normalized(e, schemas) for e in scene['entities']}
    result = deepcopy(scene)
    result['prefab_assets'] = new.assets
    result['component_definitions'] = new.component_definitions
    if new.material_assets: result['material_assets'] = new.material_assets
    if new.sprite_assets: result['sprite_assets'] = new.sprite_assets
    result.pop('prefab_templates', None)
    live = deepcopy(original)
    reset, adopt = set(_reset), _adopt or {}
    reserved = set(original)
    for record in scene.get('prefab_instances', []):
        reserved.update(record['mapping'].values())
        reserved.update(record.get('retired', {}).values())
    def allocate():
        while (eid := uuid.uuid4().hex) in reserved:
            pass
        reserved.add(eid)
        return eid

    records, erased = [], set()
    for record in scene.get('prefab_instances', []):
        root, aid = record['root'], record['prefab']
        if root in _consume:
            continue
        template = new.resolve(aid)
        if old.resolve(aid)['root'] != template['root']:
            raise ValueError('An instantiated prefab cannot replace its root local ID')
        previous = _entities(old, aid, record['mapping'])
        mapping, retired = {}, deepcopy(record.get('retired', {}))
        locals_ = {e['id'] for e in template['entities']}
        retired.update({local: sid for local, sid in adopt.get(root, {}).items() if local not in locals_})
        for local in sorted(locals_):
            if local in record['mapping']:
                mapping[local] = record['mapping'][local]
            elif local in adopt.get(root, {}):
                mapping[local] = adopt[root][local]
            elif local in retired:
                mapping[local] = retired.pop(local)
            else:
                mapping[local] = allocate()
        for local, eid in record['mapping'].items():
            if local not in mapping:
                retired[local] = eid
                erased.add(eid)
        updated = _entities(new, aid, mapping)
        if root in reset:
            erased.update(_members_and_children(scene, record) - set(mapping.values()))
        ownership, component_overrides = {}, {}
        for local, eid in mapping.items():
            current = original.get(eid)
            if current is None and local in record['mapping'] and root not in reset:
                continue  # Preserve an instance's explicit deletion override.
            target = updated[eid]
            owned = []
            if current is not None and eid in previous and root not in reset:
                before = previous[eid]
                owned = _owned(record, local, current, before)
                for group in owned:
                    for prop in BUILTIN_FIELDS[group]:
                        target[prop] = deepcopy(current[prop])
                for prop in ('name', 'parent'):
                    if current[prop] != before[prop]:
                        target[prop] = current[prop]
                masks = record.get('component_overrides', {}).get(local, {})
                target['components'] = _merge_components(before['components'], current['components'], target['components'], masks)
                if masks:
                    component_overrides[local] = deepcopy(masks)
            if eid == root:
                target['parent'] = current['parent']
                if keep_placement:
                    displaced = any(target[p] != current[p] for p in BUILTIN_FIELDS['transform'])
                    for prop in BUILTIN_FIELDS['transform']:
                        target[prop] = deepcopy(current[prop])
                    if ('transform' in _owned(record, local, current, previous[eid]) or
                            displaced):
                        owned = ['transform', *[n for n in owned if n != 'transform']]
            ownership[local] = owned
            live[eid] = target
        next_record = dict(prefab=aid, root=root, mapping=mapping, owned_components=ownership)
        if component_overrides:
            next_record['component_overrides'] = component_overrides
        if retired:
            next_record['retired'] = retired
        records.append(next_record)

    # A new template descendant of an explicitly deleted member also starts as
    # a tombstone; existing detached members keep their authored parent overrides.
    suppressed = {sid for r in records for sid in r['mapping'].values() if sid not in live}
    pending = True
    while pending:
        added = {sid for sid, item in live.items() if sid not in original and item['parent'] in suppressed}
        for sid in added:
            live.pop(sid)
        suppressed.update(added)
        pending = bool(added)
    # A Reset may remove an added instance root; also remove all of its detached
    # members. Normal propagation only erases removed template members.
    pending = True
    while pending:
        previous_erased = set(erased)
        for record in records:
            if record['root'] in erased:
                erased.update(_members_and_children(scene, record))
        pending = previous_erased != erased
    for eid in erased:
        live.pop(eid, None)
    for item in live.values():
        visited = set()
        while item['parent'] in erased:
            parent = item['parent']
            if parent in visited:
                raise ValueError('Removed prefab parent chain has a cycle')
            visited.add(parent)
            item['parent'] = original.get(parent, {}).get('parent', '')
    result['entities'] = list(live.values())
    from .camera import prune_active_camera
    prune_active_camera(result)
    result['prefab_instances'] = [r for r in records if r['root'] in live]
    return validate_scene(result)


def reset_prefab_instance(scene, eid, *, keep_placement=True):
    """Restore an entire instance, including deleted members and component values.

    Added descendants are removed. Root parenting always stays in the scene;
    its transform stays by default, or can explicitly be reset to template values.
    """
    record = instance_record(scene, eid)
    return reconcile_prefab_assets(scene, scene['prefab_assets'],
                                  _reset=(record['root'],), keep_placement=keep_placement)


def _delta(before, after, overrides=None):
    overrides = overrides or {}
    patch = {p: deepcopy(v) for p, v in after.items()
             if p not in ('id', 'components') and v != before[p]}
    components = {}
    for cid in before['components'].keys() | after['components'].keys():
        if cid not in after['components']:
            components[cid] = None
        elif cid not in before['components']:
            components[cid] = deepcopy(after['components'][cid])
        elif overrides.get(cid, {}).get('present'):
            components[cid] = deepcopy(after['components'][cid])
        else:
            old, new = before['components'][cid], after['components'][cid]
            mask = overrides.get(cid, {})
            edit = {}
            if mask.get('enabled') or old['enabled'] != new['enabled']:
                edit['enabled'] = new['enabled']
            props = {k: deepcopy(v) for k, v in new['properties'].items()
                     if int(k) in mask.get('properties', []) or v != old['properties'][k]}
            if props:
                edit['properties'] = props
            if edit:
                components[cid] = edit
    if components:
        patch['components'] = components
    return patch


def _combine_patch(existing, changes):
    for prop, value in changes.items():
        if prop != 'components':
            existing[prop] = deepcopy(value)
            continue
        components = existing.setdefault('components', {})
        for cid, edit in value.items():
            if edit is None or components.get(cid) is None:
                components[cid] = deepcopy(edit)
            else:
                target = components[cid]
                if 'enabled' in edit:
                    target['enabled'] = edit['enabled']
                if 'properties' in edit:
                    target.setdefault('properties', {}).update(deepcopy(edit['properties']))


def apply_prefab_overrides(scene, eid, *, keep_placement=True):
    """Commit an instance's edits to its asset and update its other instances.

    Includes ordinary additions, deleted members, hierarchy and component edits.
    Separately instantiated descendants become nested asset bindings in this
    instance. Their source assets, entity IDs and authored overrides are retained.
    References escaping the complete subtree still require an explicit repair.
    """
    validate_scene(scene)
    record = instance_record(scene, eid)
    library = PrefabLibrary(scene['prefab_assets'], scene.get('component_definitions', []), scene.get('material_assets', []), scene.get('sprite_assets', []))
    schemas = signatures(library.component_definitions)
    aid, root = record['prefab'], record['root']
    resolved = library.resolve(aid)
    previous = {e['id']: e for e in resolved['entities']}
    current = {e['id']: e for e in scene['entities']}
    selected = _members_and_children(scene, record) & current.keys()
    nested = []
    for other in scene.get('prefab_instances', []):
        if other['root'] != root and selected & set(other['mapping'].values()):
            if other['root'] not in selected or (set(other['mapping'].values()) & current.keys()) - selected:
                raise ValueError('Apply contains only part of another prefab instance; reparent its members together')
            nested.append(other)
    reverse = {v: k for k, v in record['mapping'].items()}
    adopted, bindings, captured_owned = {}, [], {}
    masks = deepcopy(record.get('component_overrides', {}))
    for other in sorted(nested, key=lambda r: r['root']):
        prefix = 'nested_' + uuid.uuid4().hex
        template = library.resolve(other['prefab'])
        local_map = {local: prefix if local == template['root'] else f'{prefix}/{local}'
                     for local in other['mapping'] | other.get('retired', {})}
        for local, sid in (other.get('retired', {}) | other['mapping']).items():
            adopted[local_map[local]] = sid
            if local in other['mapping']:
                reverse[sid] = local_map[local]
        for local, mask in other.get('component_overrides', {}).items():
            masks[local_map[local]] = deepcopy(mask)
        for local, owned in other.get('owned_components', {}).items():
            captured_owned[local_map[local]] = owned
        bindings.append((other, prefix, template, local_map))
    for sid in sorted(selected - set(reverse)):
        local = 'added_' + uuid.uuid4().hex
        reverse[sid] = local
        adopted[local] = sid
    def local_reference(value):
        if not value:
            return ''
        if value not in selected:
            raise ValueError(f'External or deleted entity reference {value!r}; repair it before Apply')
        return reverse[value]
    desired = {}
    for sid in sorted(selected):
        item = _normalized(current[sid], schemas)
        local = reverse[sid]
        item['id'] = local
        item['parent'] = '' if sid == root else local_reference(item['parent'])
        if sid != root and not item['parent']:
            raise ValueError('Reparent detached prefab members into the instance before Apply')
        _references(item, schemas, local_reference)
        if sid == root and keep_placement:
            for prop in BUILTIN_FIELDS['transform']:
                item[prop] = deepcopy(previous[local][prop])
        desired[local] = item
    assets = library.assets
    asset = next(a for a in assets if a['id'] == aid)
    for other, prefix, template, local_map in bindings:
        parent = local_reference(current[other['root']]['parent'])
        if not parent:
            raise ValueError('Reparent detached nested prefab roots into the instance before Apply')
        asset.setdefault('nested', []).append(dict(id=prefix, prefab=other['prefab'], parent=parent))
        for item in template['entities']:
            local = item['id']
            item['id'] = local_map[local]
            item['parent'] = parent if local == template['root'] else local_map[item['parent']]
            _references(item, schemas, lambda v: local_map[v] if v else '')
            previous[item['id']] = item
    used = {int(cid) for item in desired.values() for cid in item['components']}
    used.update(d['id'] for d in asset.get('component_definitions', []))
    asset['component_definitions'] = [deepcopy(schemas[cid]) for cid in sorted(used)]
    used_sprites = {item['sprite']['asset'] for item in desired.values() if item['sprite'] is not None}
    used_sprites.update(a['id'] for a in asset.get('sprite_assets', []))
    if used_sprites: asset['sprite_assets'] = [deepcopy(a) for a in library.sprite_assets if a['id'] in used_sprites]
    used_materials = {item['material']['asset'] for item in desired.values() if item['material'] is not None}
    used_materials.update(a['id'] for a in asset.get('material_assets', []))
    if used_materials: asset['material_assets'] = [deepcopy(a) for a in library.material_assets if a['id'] in used_materials]
    for local, item in desired.items():
        if local not in previous:
            asset.setdefault('entities', []).append(item)
        else:
            changes = _delta(previous[local], item, masks.get(local))
            for group in captured_owned.get(local, []):
                for prop in BUILTIN_FIELDS[group]:
                    changes[prop] = deepcopy(item[prop])
            if changes:
                _combine_patch(asset.setdefault('overrides', {}).setdefault(local, {}), changes)
    missing = set(previous) - set(desired)
    if missing:
        asset['removed'] = sorted(set(asset.get('removed', [])) | missing)
    return reconcile_prefab_assets(scene, assets, _reset=(root,),
                                  _adopt={root: adopted}, _consume={r['root'] for r in nested},
                                  keep_placement=keep_placement)
