from copy import deepcopy
import pytest
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene
from editor.core.type_edits import edit_type, stable_definitions
from editor.core.typed_schema import with_types, build_schema
from editor.core.registry import Registry
from editor.core.components import with_components


def source():
    structs=[dict(name='Stats',fields=[dict(name='hp',type='int',default=10)]),
             dict(name='Actor',fields=[dict(name='stats',type='struct:Stats')])]
    enums=[dict(name='Mode',values=['Idle','Run'])]
    b=GraphBuilder(struct_definitions=structs,enum_definitions=enums)
    for nid,name,values in [('start','On Game Start',{}),('make','Make Stats',dict(hp=42)),
         ('break','Break Stats',{}),('store','Set Integer Variable',dict(Name='hp'))]: b.add(nid,name,**values)
    b.connect('start','Out','store','In').connect('make','Value','break','Value').connect('break','hp','store','Value')
    scene=default_scene(); scene['struct_definitions']=structs; scene['enum_definitions']=enums
    scene['variables']=dict(actor=dict(type='struct:Actor',value=dict(stats=dict(hp=24))))
    return b,scene


def test_rename_field_and_type_migrates_nested_values_defaults_and_wires():
    b,scene=source(); before=deepcopy((b.graph,scene))
    graph,after=edit_type(b.graph,scene,'struct',dict(name='Vitals',fields=[dict(name='health',type='int',default=10)]),
                          original='Stats',origins=dict(health='hp'))
    assert (b.graph,scene)==before
    assert graph['nodes'][1]['type']==b.registry.by_name('Make Stats').id
    assert graph['nodes'][1]['values']==dict(health=42)
    assert graph['links'][-1]['from']==['break','health']
    assert after['variables']['actor']['value']==dict(stats=dict(health=24))
    schema=build_schema(after['struct_definitions'],after['enum_definitions'])
    assert schema.default_value('struct:Actor')==dict(stats=dict(health=10))
    assert schema.structs['Actor']['fields'][0]['type']=='struct:Vitals'


def test_stable_nodes_survive_reorder_and_later_definition_addition():
    b,scene=source()
    structs,enums=stable_definitions(scene['struct_definitions'],scene['enum_definitions'])
    old=with_types(Registry(),structs,enums)
    reordered=with_types(Registry(),list(reversed(structs)),enums)
    for name in ('Make Stats','Break Actor','Make Mode','Set Global Stats Variable','Get Mode Variable'):
        assert old.by_name(name).id==reordered.by_name(name).id
    graph,after=edit_type(b.graph,scene,'struct',dict(name='NewType',fields=[dict(name='enabled',type='bool')]))
    registry=with_types(Registry(),after['struct_definitions'],after['enum_definitions'])
    assert registry.by_name('Make Mode').id==b.registry.by_name('Make Mode').id
    assert registry.by_name('Get Mode Variable').id==b.registry.by_name('Get Mode Variable').id


def test_delete_referenced_type_or_authored_field_is_atomic():
    b,scene=source(); before=deepcopy((b.graph,scene))
    with pytest.raises(ValueError,match='referenced|used'):
        edit_type(b.graph,scene,'struct',original='Stats')
    with pytest.raises(ValueError,match='authored|Disconnect'):
        edit_type(b.graph,scene,'struct',dict(name='Stats',fields=[dict(name='other',type='int')]),original='Stats',origins={})
    assert (b.graph,scene)==before


def test_deleted_identities_are_retired_and_not_reused():
    b=GraphBuilder(); scene=default_scene()
    graph,scene=edit_type(b.graph,scene,'enum',dict(name='Unused',values=['A']))
    old=scene['enum_definitions'][0]
    graph,scene=edit_type(graph,scene,'enum',original='Unused')
    graph,scene=edit_type(graph,scene,'struct',dict(name='Next',fields=[dict(name='x',type='float')]))
    new=scene['struct_definitions'][0]
    assert new['node_id']!=old['node_id'] and new['variable_id']!=old['variable_id']


def test_enum_label_refactor_migrates_values_and_blocks_ambiguous_dynamic_sources():
    enums=[dict(name='Mode',values=['Idle','Run'])]
    b=GraphBuilder(enum_definitions=enums); b.add('make','Make Mode',Value='Run')
    scene=default_scene(); scene['variables']=dict(mode=dict(type='enum:Mode',value='Run'))
    graph,after=edit_type(b.graph,scene,'enum',dict(name='Mode',values=['Idle','Sprint']),original='Mode',origins=dict(Idle='Idle',Sprint='Run'))
    assert graph['nodes'][0]['values']['Value']=='Sprint'
    assert after['variables']['mode']['value']=='Sprint'
    b.add('text','String',Value='Run'); b.connect('text','Value','make','Value')
    with pytest.raises(ValueError,match='dynamic enum'):
        edit_type(b.graph,scene,'enum',dict(name='Mode',values=['Idle','Sprint']),original='Mode',origins=dict(Idle='Idle',Sprint='Run'))


def test_high_component_ids_are_preserved_and_collisions_are_rejected():
    component=dict(id=2050,name='Health',properties=[dict(id=1,name='hp',type='int',default=1)])
    base=with_components(Registry(),[component]); before={k:v for k,v in base.nodes.items() if v.component_id}
    typed=with_types(base,[],[])
    assert all(typed.nodes[k]==v for k,v in before.items())
    structs=[dict(name='Stats',fields=[dict(name='hp',type='int')],node_id=710000,variable_id=805009)]
    with pytest.raises(ValueError,match='aligned'):
        with_types(base,structs,[])
    # Use the exact aligned high component family ID for a collision.
    component['id']=2048; base=with_components(Registry(),[component]); structs[0]['variable_id']=804800
    with pytest.raises(ValueError,match='collides'):
        with_types(base,structs,[])


def test_type_rename_preserves_implicit_variable_bindings():
    structs=[dict(name='Stats',fields=[dict(name='hp',type='int',default=10)])]
    b=GraphBuilder(struct_definitions=structs)
    b.add('read','Get Stats Variable')
    scene=default_scene(); scene['variables']=dict(stats=dict(type='struct:Stats',value=dict(hp=10)))
    graph,scene=edit_type(b.graph,scene,'struct',dict(name='Vitals',fields=[dict(name='hp',type='int',default=10)]),original='Stats')
    assert graph['nodes'][0]['values']['Name']=='stats'
    assert scene['variables']['stats']['type']=='struct:Vitals'


def test_new_components_skip_active_and_retired_type_node_identities(monkeypatch):
    from types import SimpleNamespace
    from editor.core.components import new_component,node_id,MAX_ID
    monkeypatch.setattr('editor.core.components.uuid.uuid4',lambda:SimpleNamespace(int=1999))
    reserved={800000,node_id(2001,'get',1)}
    component=new_component('Health',[dict(name='hp',type='int',default=1)],reserved_nodes=reserved)
    assert component['id']==2002
    with pytest.raises(ValueError,match='exhausted'):
        new_component('Unavailable',reserved_nodes={node_id(cid,'add') for cid in range(1,MAX_ID+1)})
