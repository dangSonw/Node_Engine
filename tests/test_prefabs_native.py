"""Real Flecs prefab relationships, owned overrides and native execution parity."""
from copy import deepcopy
import json
import pytest

from editor.core.builder import GraphBuilder
from editor.core.compiler import compile_graph, GraphError
from editor.core.document import default_scene
from editor.core.prefabs import PrefabLibrary, prepare_scene_prefabs
from editor.core.scene import validate_scene
from tests.test_entities import pair
from tests.test_native import native
from tests.test_prefabs import robot, variant, by_id
from editor.core.prefab_edits import apply_prefab_overrides, reconcile_prefab_assets, reset_prefab_instance
from editor.core.prefabs import instantiate_scene_prefab
from editor.core.scene import set_entity_property, delete_entity, create_entity, entity
from editor.core.components import edit_instance


def prefab_scene():
    assets = [robot(), variant(overrides={'root': {'layer': 5, 'components': {'1': {'properties': {'5': 200}}}}})]
    return {'version': 1, 'entities': [], 'variables': {}, 'prefab_assets': assets}


def builder(scene):
    return GraphBuilder(component_definitions=PrefabLibrary(scene['prefab_assets']).component_definitions)


def test_component_write_masks_match_authoring_and_survive_native_reload(native):
    scene = prefab_scene()
    scene, root = instantiate_scene_prefab(scene, 'robot')
    child = scene['prefab_instances'][0]['mapping']['e1']
    fields = entity(scene, root)['components']['1']['properties']
    b = builder(scene)
    b.add('start', 'On Game Start')
    previous = 'start'
    expected = scene
    for index, (name, operation, field, value) in enumerate([
        ('Set Links Health', 'set', 5, 100), ('Set Links Label', 'set', 4, 'player'),
        ('Set Links Friends', 'set', 2, fields['2']), ('Set Links Target', 'set', 1, child),
        ('Set Links Slots', 'set', 3, fields['3']), ('Set Links Enabled', 'enable', None, True),
    ]):
        nid = 'write' + str(index)
        b.add(nid, name, Entity=root, **{'Enabled' if operation == 'enable' else 'Value': value})
        b.connect(previous, 'Out', nid, 'In')
        previous = nid
        expected = edit_instance(expected, root, 1, operation, value, field)
    result = pair(native, b, scene)
    record = result['scene']['prefab_instances'][0]
    assert record['component_overrides'] == expected['prefab_instances'][0]['component_overrides']
    assert record['component_overrides']['root']['1'] == {'enabled': True, 'properties': [1, 2, 3, 4, 5]}
    assert pair(native, builder(scene), result['scene']) == result
    changed_assets = deepcopy(scene['prefab_assets'])
    component = next(e for e in changed_assets[0]['entities'] if e['id'] == 'root')['components']['1']
    component['enabled'] = False
    component['properties'].update({'1': '', '2': [], '3': {}, '4': 'changed', '5': 25})
    changed = reconcile_prefab_assets(result['scene'], changed_assets)
    assert entity(changed, root)['components'] == entity(scene, root)['components']
    propagated = pair(native, builder(changed), changed)
    assert propagated['scene']['prefab_instances'][0]['component_overrides'] == record['component_overrides']
    reset = builder(changed)
    reset.add('start', 'On Game Start')
    reset.add('reset', 'Reset Prefab Instance', Instance=root)
    reset.connect('start', 'Out', 'reset', 'In')
    restored = pair(native, reset, propagated['scene'])
    assert 'component_overrides' not in restored['scene']['prefab_instances'][0]
    assert entity(restored['scene'], root)['components']['1'] == component


def test_component_presence_masks_clone_and_destruction_match_authoring(native):
    scene = prefab_scene()
    scene, root = instantiate_scene_prefab(scene, 'robot')
    child = scene['prefab_instances'][0]['mapping']['e1']
    b = builder(scene)
    b.add('start', 'On Game Start')
    steps = [('remove', 'Remove Links Component', dict(Entity=root)), ('add', 'Add Links Component', dict(Entity=root)),
             ('same', 'Set Links Health', dict(Entity=root, Value=100)),
             ('no_op', 'Add Links Component', dict(Entity=root)),
             ('absent', 'Remove Links Component', dict(Entity=child)),
             ('clone', 'Clone Entity', dict(Source=root))]
    previous = 'start'
    for nid, name, values in steps:
        b.add(nid, name, **values)
        b.connect(previous, 'Out', nid, 'In')
        previous = nid
    result = pair(native, b, scene)
    masks = result['scene']['prefab_instances'][0]['component_overrides']
    assert masks == {'root': {'1': {'present': True, 'properties': [5]}}, 'e1': {'1': {'present': False}}}
    assert entity(result['scene'], 'spawned_1')['components'] == entity(result['scene'], root)['components']
    assert 'spawned_1' not in result['prefab_state']['entities']
    assert pair(native, builder(scene), result['scene']) == result
    b = builder(scene)
    b.add('start', 'On Game Start')
    b.add('destroy', 'Destroy Entity', Entity=child)
    b.connect('start', 'Out', 'destroy', 'In')
    deleted = pair(native, b, result['scene'])
    assert 'e1' not in deleted['scene']['prefab_instances'][0]['component_overrides']
    validate_scene(deleted['scene'])


def test_explicit_authoring_masks_remain_separate_between_instances(native):
    scene = prefab_scene()
    scene, a = instantiate_scene_prefab(scene, 'robot')
    scene, b = instantiate_scene_prefab(scene, 'robot')
    scene = edit_instance(scene, a, 1, 'set', 100, 5)
    scene = edit_instance(scene, b, 1, 'set', 'player', 4)
    state = pair(native, builder(scene), scene)
    records = {r['root']: r for r in state['scene']['prefab_instances']}
    assert records[a]['component_overrides'] == {'root': {'1': {'properties': [5]}}}
    assert records[b]['component_overrides'] == {'root': {'1': {'properties': [4]}}}
    changed = edit_instance(state['scene'], b, 1, 'set', 50, 5)
    applied = apply_prefab_overrides(changed, b)
    result = pair(native, builder(applied), applied)
    assert entity(result['scene'], a)['components']['1']['properties']['5'] == 100
    assert entity(result['scene'], b)['components']['1']['properties']['5'] == 50


def test_authoring_apply_reset_and_propagation_reload_as_real_native_instances(native):
    scene = prefab_scene()
    scene['component_definitions'] = PrefabLibrary(scene['prefab_assets']).component_definitions
    scene, first = instantiate_scene_prefab(scene, 'robot', position=[-3, 0, 0])
    scene, second = instantiate_scene_prefab(scene, 'variant', position=[3, 0, 0])
    scene = set_entity_property(scene, first, 'layer', 11)
    scene = edit_instance(scene, first, 1, 'set', 'applied', 4)
    scene = edit_instance(scene, second, 1, 'set', 777, 5)
    scene, extra = create_entity(scene, 'Extra')
    scene = set_entity_property(scene, extra, 'parent', first)
    scene = edit_instance(scene, first, 1, 'set', extra, 1)
    changed = apply_prefab_overrides(scene, first)
    state = pair(native, builder(changed), changed)
    entities = by_id(state['scene'])
    assert entities[first]['layer'] == 11 and entities[second]['layer'] == 5
    assert entities[second]['components']['1']['properties']['4'] == 'applied'
    assert entities[second]['components']['1']['properties']['5'] == 777
    for record in state['scene']['prefab_instances']:
        assert len(record['mapping']) == 3
        assert entities[record['root']]['components']['1']['properties']['1'] in record['mapping'].values()
    assert state['prefab_state']['entities'][first]['owned_components'] == ['transform']
    assert state['prefab_state']['templates']['variant']['root']['base'] == {'asset': 'robot', 'local': 'root'}
    # Reconcile from a genuine native snapshot; Reset recovers the variant's value.
    reset = reset_prefab_instance(state['scene'], second)
    restored = pair(native, builder(reset), reset)
    assert by_id(restored['scene'])[second]['components']['1']['properties']['5'] == 200
    assert pair(native, builder(reset), restored['scene']) == restored


def test_retired_template_ids_survive_native_roundtrip_and_are_not_reused(native):
    scene = prefab_scene()
    scene['component_definitions'] = PrefabLibrary(scene['prefab_assets']).component_definitions
    library = PrefabLibrary(scene['prefab_assets'])
    record = library.instantiate_entities('robot', mapping={'root': 'root', 'e1': 'spawned_1'})
    scene['entities'] = record.pop('entities'); scene['prefab_instances'] = [record]
    old_assets = deepcopy(scene['prefab_assets'])
    scene = delete_entity(scene, 'spawned_1')
    for field, value in [(1, ''), (2, []), (3, {})]:
        scene = edit_instance(scene, 'root', 1, 'set', value, field)
    changed = apply_prefab_overrides(scene, 'root')
    b = builder(changed); b.add('start', 'On Game Start'); b.add('spawn', 'Instantiate Prefab', Prefab='robot')
    b.connect('start', 'Out', 'spawn', 'In')
    state = pair(native, b, changed)
    assert set(state['entities']) == {'root', 'spawned_2'}
    record = next(r for r in state['scene']['prefab_instances'] if r['root'] == 'root')
    assert record['retired'] == {'e1': 'spawned_1'}
    assert pair(native, builder(changed), state['scene']) == state
    restored = reconcile_prefab_assets(state['scene'], old_assets)
    result = pair(native, builder(restored), restored)
    assert result['prefab_state']['entities']['spawned_1']['base'] == {'asset': 'robot', 'local': 'e1'}
    assert entity(result['scene'], 'spawned_1')['parent'] == 'root'


def spawn_pair(b):
    b.add('start', 'On Game Start')
    for nid, prefab, position in [('a', 'robot', [-2, 0, 0]), ('b', 'variant', [2, 0, 0])]:
        b.add(nid, 'Instantiate Prefab', Prefab=prefab, Position=position)
        b.add(nid+'child', 'Get Prefab Entity', LocalID='e1')
        b.connect(nid, 'Entity', nid+'child', 'Instance')
    b.connect('start', 'Out', 'a', 'In'); b.connect('a', 'Out', 'b', 'In')


def test_real_isa_inheritance_reference_remapping_queries_and_reload(native):
    scene = prefab_scene(); original = deepcopy(scene); b = builder(scene); spawn_pair(b)
    last = 'b'
    def read(nid, label, value_type, port='Value', entity_port='Entity', source='achild'):
        nonlocal last
        b.add(nid, label); b.connect(source, 'Entity', nid, entity_port)
        b.add(nid+'save', 'Set '+value_type+' Variable', Name=nid)
        b.connect(nid, port, nid+'save', 'Value'); b.connect(last, 'Out', nid+'save', 'In'); last = nid+'save'
    read('isinstance', 'Is Prefab Instance', 'Boolean')
    read('asset', 'Get Prefab Asset', 'String')
    read('root', 'Get Prefab Root', 'Entity', 'Entity')
    read('target', 'Get Links Target', 'Entity', source='a')
    result = pair(native, b, scene)
    assert scene == original
    values = {k: v['value'] for k, v in result['variables'].items()}
    assert values == dict(isinstance=True, asset='robot', root='spawned_1', target='spawned_2')
    entities = by_id(result['scene'])
    assert set(entities) == {'spawned_1', 'spawned_2', 'spawned_3', 'spawned_4'}
    assert entities['spawned_1']['components']['1']['properties']['3'] == {'player':'spawned_2', 'empty':''}
    assert entities['spawned_3']['components']['1']['properties']['2'] == ['spawned_3','spawned_4','']
    assert entities['spawned_3']['components']['1']['properties']['5'] == 200
    assert entities['spawned_3']['components']['1']['properties']['4'] == 'player'
    state = result['prefab_state']
    assert state['templates']['robot']['root']['is_prefab']
    assert state['templates']['variant']['root']['base'] == {'asset':'robot','local':'root'}
    assert state['templates']['variant']['root']['owned_components'] == ['activity']
    assert state['entities']['spawned_2'] == {'is_prefab': False, 'owned_components': [],
                                            'base': {'asset':'robot','local':'e1'}, 'root':'spawned_1'}
    assert state['entities']['spawned_1']['owned_components'] == ['transform']
    validate_scene(result['scene'])
    assert pair(native, builder(scene), result['scene']) == result


def test_writes_own_inherited_values_without_mutating_other_instances_or_templates(native):
    scene = prefab_scene(); b = builder(scene); spawn_pair(b); last='b'
    for nid,name,values,target in [
        ('move','Set Position',{'Value':[9,8,7]},'achild'),
        ('hidden','Set Entity Visibility',{'Visible':False},'a'),
        ('tag','Add Entity Tag',{'Tag':'instance-only'},'a'),
        ('layer','Set Entity Layer',{'Layer':12},'a'),
        ('health','Set Links Health',{'Value':17},'a'),
        ('remove','Remove Links Component',{},'b'),
    ]:
        b.add(nid,name,**values); b.connect(last,'Out',nid,'In'); b.connect(target,'Entity',nid,'Entity'); last=nid
    result=pair(native,b,scene)
    entities=by_id(result['scene'])
    assert entities['spawned_2']['position']==[9,8,7] and entities['spawned_4']['position']==[0,0,0]
    assert entities['spawned_1']['visible'] is False and entities['spawned_3']['visible'] is True
    assert entities['spawned_1']['layer']==12 and entities['spawned_3']['layer']==5
    assert entities['spawned_1']['tags']==['actor','instance-only'] and entities['spawned_3']['tags']==['actor']
    assert entities['spawned_1']['components']['1']['properties']['5']==17
    assert 'components' not in entities['spawned_3']
    assert result['prefab_state']['entities']['spawned_1']['owned_components']==['transform','mesh','tags','activity']
    assert result['prefab_state']['entities']['spawned_2']['owned_components']==['transform']
    assert pair(native,builder(scene),result['scene'])==result


def test_same_value_write_preserves_explicit_ownership_across_snapshot(native):
    scene=prefab_scene(); b=builder(scene); spawn_pair(b)
    b.add('same','Set Entity Layer',Layer=0); b.connect('b','Out','same','In'); b.connect('achild','Entity','same','Entity')
    result=pair(native,b,scene)
    assert result['prefab_state']['entities']['spawned_2']['owned_components']==['activity']
    assert pair(native,builder(scene),result['scene'])==result


def test_nested_variant_templates_are_real_bases_and_not_live_scene_entities(native):
    scene=prefab_scene()
    scene['prefab_assets'].append({'version':1,'type':'prefab','id':'squad','name':'Squad','root':'group',
        'entities':[dict(default_scene()['entities'][0],id='group')],
        'nested':[{'id':'left','prefab':'robot','parent':'group'},
                  {'id':'right','prefab':'variant','parent':'group','overrides':{'root':{'active':False}}}]})
    b=builder(scene); b.add('start','On Game Start'); b.add('spawn','Instantiate Prefab',Prefab='squad')
    b.connect('start','Out','spawn','In')
    b.add('count','Get Entity Count'); b.add('save','Set Integer Variable',Name='count')
    b.connect('spawn','Out','save','In'); b.connect('count','Value','save','Value')
    b.add('query','Find Entities With Links'); b.add('queries','Set Entity Array Variable',Name='withlinks')
    b.connect('save','Out','queries','In'); b.connect('query','Value','queries','Value')
    result=pair(native,b,scene)
    assert result['variables']['count']['value']==5 and len(result['scene']['entities'])==5
    assert result['variables']['withlinks']['value']==['spawned_2','spawned_4']
    assert result['prefab_state']['templates']['squad']['right']['base']=={'asset':'variant','local':'root'}
    assert result['prefab_state']['templates']['squad']['right/e1']['base']=={'asset':'variant','local':'e1'}
    items=by_id(result['scene'])
    assert items['spawned_2']['components']['1']['properties']['1']=='spawned_3'
    assert items['spawned_4']['components']['1']['properties']['1']=='spawned_5'
    assert not items['spawned_4']['active']


def test_destroy_instance_owns_detached_members_and_cleans_timers(native):
    scene=prefab_scene(); b=builder(scene); spawn_pair(b)
    b.add('timer','Start Timer',Name='member',Seconds=10)
    b.connect('b','Out','timer','In'); b.connect('achild','Entity','timer','Owner')
    b.add('detach','Set Parent',Parent=''); b.connect('timer','Out','detach','In'); b.connect('achild','Entity','detach','Child')
    b.add('destroy','Destroy Entity'); b.connect('detach','Out','destroy','In'); b.connect('a','Entity','destroy','Entity')
    result=pair(native,b,scene)
    assert set(result['entities'])=={'spawned_3','spawned_4'} and result['timers']==[]
    assert len(result['scene']['prefab_instances'])==1
    assert result['scene']['prefab_instances'][0]['root']=='spawned_3'
    assert pair(native,builder(scene),result['scene'])==result


def test_deleted_member_mapping_survives_reload_and_does_not_alias_spawn(native):
    scene=prefab_scene(); b=builder(scene); spawn_pair(b)
    b.add('delete','Destroy Entity'); b.connect('b','Out','delete','In'); b.connect('achild','Entity','delete','Entity')
    result=pair(native,b,scene)
    record=result['scene']['prefab_instances'][0]
    assert record['mapping']['e1']=='spawned_2' and 'spawned_2' not in result['entities']
    assert pair(native,builder(scene),result['scene'])==result
    g=builder(scene); g.add('start','On Game Start'); g.add('spawn','Spawn Entity'); g.connect('start','Out','spawn','In')
    g.add('child','Get Prefab Entity',Instance='spawned_1',LocalID='e1'); g.add('save','Set Entity Variable',Name='dead')
    g.connect('spawn','Out','save','In'); g.connect('child','Entity','save','Value')
    loaded=pair(native,g,result['scene'])
    assert 'spawned_5' in loaded['entities'] and loaded['variables']['dead']['value']==''


@pytest.mark.parametrize('values,message', [({'Prefab':'missing'},'Unknown prefab'),
    ({'Prefab':'robot','Parent':'missing'},'Missing entity')])
def test_instantiation_errors_report_original_graph_node(native,values,message):
    scene=prefab_scene(); b=builder(scene); b.add('start','On Game Start'); b.add('bad','Instantiate Prefab',**values)
    b.connect('start','Out','bad','In'); a,c=native(b.graph,scene=scene,frames=0)
    assert a.returncode==c.returncode==1 and json.loads(a.stderr)==json.loads(c.stderr)
    assert json.loads(a.stderr)['node']=='bad' and message in json.loads(a.stderr)['message']


def test_initial_authored_candidate_restores_real_inheritance(native):
    scene=prefab_scene(); library=PrefabLibrary(scene['prefab_assets'])
    instance=library.instantiate_entities('robot',mapping={'root':'player','e1':'child'})
    scene['entities']=instance.pop('entities'); scene['prefab_instances']=[instance]
    b=builder(scene)
    result=pair(native,b,scene)
    assert result['prefab_state']['entities']['player']['owned_components']==[]
    assert result['scene']['entities'][1]['id']=='player'
    bad=deepcopy(scene); bad['prefab_instances'][0]['mapping']['e1']='player'
    with pytest.raises(ValueError,match='unique'): compile_graph(b.graph,bad)
    bad=deepcopy(scene); bad['prefab_instances'][0]['root']='child'
    with pytest.raises(ValueError,match='live mapped root'): compile_graph(b.graph,bad)


def test_instantiate_result_requires_execution_path():
    b=GraphBuilder(); b.add('start','On Game Start'); b.add('spawn','Instantiate Prefab',Prefab='robot')
    b.add('move','Set Position'); b.connect('start','Out','move','In'); b.connect('spawn','Entity','move','Entity')
    with pytest.raises(GraphError,match='after that action'): compile_graph(b.graph,prefab_scene())
