"""Entity/component storage, hierarchy and native lifetime integration."""
from copy import deepcopy
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.compiler import compile_graph, GraphError
from editor.core.document import default_scene
from editor.core.scene import validate_scene, set_entity_property, delete_entity
from editor.core.events import new_event
from tests.test_native import native


def pair(native, builder, scene=None, frames=0):
    a,b=native(builder.graph,scene=scene,frames=frames)
    assert a.returncode==b.returncode==0,a.stderr+b.stderr
    result=json.loads(a.stdout)
    assert result==json.loads(b.stdout)
    return result


def make_scene():
    scene=default_scene()
    for eid,parent in [('child','player'),('grandchild','child'),('other','')]:
        item=deepcopy(scene['entities'][0]); item.update(id=eid,name=eid,parent=parent)
        scene['entities'].append(item)
    return scene


@pytest.mark.parametrize('edit',[
    {'parent':'missing'}, {'parent':'grandchild'}, {'visible':1}, {'tags':['a','a']},
    {'tags':['a\0']}, {'tags':[{}]}, {'id':'x\0'}, {'name':'\n'}, {'name':'é'*257},
])
def test_scene_rejects_invalid_hierarchy_metadata(edit):
    scene=make_scene(); scene['entities'][0].update(edit)
    with pytest.raises(ValueError): validate_scene(scene)


def test_scene_parent_edit_delete_and_depth_are_validated_transactionally():
    scene=make_scene(); before=deepcopy(scene)
    with pytest.raises(ValueError,match='cycle'): set_entity_property(scene,'player','parent','grandchild')
    assert scene==before
    detached=set_entity_property(scene,'child','parent','')
    assert len(delete_entity(detached,'player')['entities'])==3
    assert [e['id'] for e in delete_entity(scene,'child')['entities']]==['player','other']
    deep=default_scene()
    for i in range(256):
        deep['entities'].append(dict(deep['entities'][0],id=f'n{i}',parent='player' if i==0 else f'n{i-1}'))
    with pytest.raises(ValueError,match='256'): validate_scene(deep)


def test_spawn_output_requires_its_execution_path():
    b=GraphBuilder(); b.add('start','On Game Start'); b.add('spawn','Spawn Entity')
    b.add('move','Set Position'); b.connect('start','Out','move','In'); b.connect('spawn','Entity','move','Entity')
    with pytest.raises(GraphError,match='after that action'): compile_graph(b.graph,default_scene())


def test_deleted_references_stay_dead_after_scene_serialization(native):
    b=GraphBuilder(); b.add('start','On Game Start'); b.add('spawn','Spawn Entity')
    b.add('save','Set Entity Variable',Name='dead'); b.add('destroy','Destroy Entity')
    for a,c in [('start','spawn'),('spawn','save'),('save','destroy')]: b.connect(a,'Out',c,'In')
    b.connect('spawn','Entity','save','Value'); b.connect('spawn','Entity','destroy','Entity')
    state=pair(native,b)
    assert state['variables']['dead']['value']=='spawned_1' and state['scene']['entity_serial']==1
    next_graph=GraphBuilder(); next_graph.add('start','On Game Start'); next_graph.add('spawn','Spawn Entity')
    next_graph.connect('start','Out','spawn','In')
    loaded=pair(native,next_graph,scene=state['scene'])
    assert 'spawned_2' in loaded['entities'] and 'spawned_1' not in loaded['entities']


def test_spawn_clone_lookup_tags_visibility_and_hierarchy(native):
    b=GraphBuilder(); b.add('start','On Game Start'); last='start'
    def action(nid,name,**values):
        nonlocal last
        b.add(nid,name,**values); b.connect(last,'Out',nid,'In'); last=nid
    def save(nid,name,node,port='Value'):
        action(nid,name,Name=nid); b.connect(node,port,nid,'Value')
    action('root','Spawn Entity',Name='Root',Position=[10,0,0])
    action('clone','Clone Entity',Name='Child')
    action('position','Set Position',Value=[1,2,3]); b.connect('clone','Entity','position','Entity')
    action('parent','Set Parent'); b.connect('clone','Entity','parent','Child'); b.connect('root','Entity','parent','Parent')
    action('tag','Add Entity Tag',Tag='actor'); b.connect('clone','Entity','tag','Entity')
    b.add('has','Has Entity Tag',Tag='actor'); b.connect('clone','Entity','has','Entity')
    save('tagged','Set Boolean Variable','has')
    b.add('namefind','Find Entities By Name',Name='Child'); save('byname','Set Entity Array Variable','namefind')
    b.add('tagfind','Find Entities By Tag',Tag='actor'); save('bytag','Set Entity Array Variable','tagfind')
    b.add('world','Get World Position'); b.connect('clone','Entity','world','Entity'); save('worldpos','Set Vector3 Variable','world')
    b.add('children','Get Children'); b.connect('root','Entity','children','Parent'); save('kids','Set Entity Array Variable','children')
    b.add('parentget','Get Parent'); b.connect('clone','Entity','parentget','Entity'); save('parentref','Set Entity Variable','parentget','Entity')
    b.add('count','Get Entity Count'); save('counted','Set Integer Variable','count')
    action('rename','Set Entity Name',Name='Con rô-bốt'); b.connect('clone','Entity','rename','Entity')
    b.add('name','Get Entity Name'); b.connect('clone','Entity','name','Entity'); save('renamed','Set String Variable','name')
    action('hide','Set Entity Visibility',Visible=False); b.connect('root','Entity','hide','Entity')
    b.add('visible','Is Entity Visible'); b.connect('clone','Entity','visible','Entity'); save('visibility','Set Boolean Variable','visible')
    action('untag','Remove Entity Tag',Tag='actor'); b.connect('clone','Entity','untag','Entity'); save('emptytags','Set Entity Array Variable','tagfind')
    b.add('lookup','Get Entity By ID',ID='missing'); save('missing','Set Entity Variable','lookup','Entity')
    b.add('all','Get All Entities'); save('allrefs','Set Entity Array Variable','all')
    result=pair(native,b)
    v={k:x['value'] for k,x in result['variables'].items()}
    assert v==dict(tagged=True,byname=['spawned_2'],bytag=['spawned_2'],worldpos=[11,2,3],kids=['spawned_2'],
                  parentref='spawned_1',counted=3,renamed='Con rô-bốt',visibility=False,emptytags=[],missing='',
                  allrefs=['player','spawned_1','spawned_2'])
    child=next(e for e in result['scene']['entities'] if e['id']=='spawned_2')
    assert child['parent']=='spawned_1' and child['tags']==[] and child['visible'] is True
    # Serialized Flecs state is a valid scene and reloads without losing relationships.
    validate_scene(result['scene'])
    empty=GraphBuilder()
    reloaded=pair(native,empty,scene=result['scene'])
    assert reloaded==result


def test_world_transform_parent_rotation_and_scale(native):
    scene=make_scene(); scene['entities'][0].update(position=[10,0,0],rotation=[0,0,90],scale=[2,3,1])
    scene['entities'][1]['position']=[1,0,0]
    scene['entities'][2]['position']=[0,2,0]
    # Parent references do not depend on serialized entity order.
    scene['entities'].reverse()
    b=GraphBuilder(); b.add('start','On Game Start'); b.add('read','Get World Position',Entity='grandchild')
    b.add('save','Set Vector3 Variable',Name='world'); b.connect('start','Out','save','In'); b.connect('read','Value','save','Value')
    result=pair(native,b,scene=scene)
    assert result['variables']['world']['value']==pytest.approx([4,2,0])
    assert result['entities']['grandchild']['position']==[0,2,0]


def test_destroy_subtree_cancels_queued_events_and_timers(native):
    definition=new_event('Ping')
    b=GraphBuilder(event_definitions=[definition]); b.add('start','On Game Start'); previous='start'
    for owner in ['player','child','grandchild','other']:
        for prefix,name in [('timer','Start Timer'),('send','Send Ping')]:
            nid=prefix+owner
            values={'Owner':owner,'Name':'tick','Seconds':.01,'Repeat':True} if prefix=='timer' else {'Recipient':owner}
            b.add(nid,name,**values); b.connect(previous,'Out',nid,'In'); previous=nid
        b.add('handler'+owner,'On Ping',Receiver=owner); b.add('log'+owner,'Print Log',Message=owner)
        b.connect('handler'+owner,'Out','log'+owner,'In')
    b.add('destroy','Destroy Entity',Entity='child'); b.connect(previous,'Out','destroy','In')
    b.add('again','Destroy Entity',Entity='child'); b.connect('destroy','Out','again','In')
    result=pair(native,b,scene=make_scene(),frames=3)
    assert set(result['entities'])=={'player','other'}
    assert result['logs']==['player','other']
    assert {x['owner'] for x in result['timers']}=={'player','other'}
    assert {x['receiver'] for x in result['events']['subscriptions']}=={'player','other'}


@pytest.mark.parametrize('trigger',['event','timer'])
def test_destroy_inside_listener_stops_remaining_callbacks_and_preserves_other_receivers(native,trigger):
    definition=new_event('Ping')
    b=GraphBuilder(event_definitions=[definition]); b.add('start','On Game Start'); last='start'
    for i,owner in enumerate(['player','player','other']):
        values={'Recipient':owner} if trigger=='event' else {'Owner':owner,'Name':f't{i}','Seconds':.01,'Repeat':True}
        b.add(f'send{i}','Send Ping' if trigger=='event' else 'Start Timer',**values)
        b.connect(last,'Out',f'send{i}','In'); last=f'send{i}'
    for nid,owner in [('a','player'),('z','player'),('otherhandler','other')]:
        b.add(nid,'On Ping' if trigger=='event' else 'On Timer Finished',Receiver=owner)
    b.add('destroy','Destroy Entity',Entity='player'); b.connect('a','Out','destroy','In')
    b.add('zlog','Print Log',Message='must not run'); b.connect('z','Out','zlog','In')
    b.add('otherlog','Print Log',Message='other'); b.connect('otherhandler','Out','otherlog','In')
    result=pair(native,b,scene=make_scene(),frames=1)
    assert set(result['entities'])=={'other'} and result['logs']==['other']


def test_spawn_and_clone_inside_event_are_immediately_usable(native):
    definition=new_event('Ping')
    b=GraphBuilder(event_definitions=[definition]); b.add('start','On Game Start'); b.add('send','Send Ping')
    b.connect('start','Out','send','In'); b.add('event','On Ping'); b.add('spawn','Spawn Entity',Name='temporary')
    b.connect('event','Out','spawn','In'); b.add('clone','Clone Entity'); b.connect('spawn','Out','clone','In'); b.connect('spawn','Entity','clone','Source')
    b.add('move','Set Position',Value=[3,4,5]); b.connect('clone','Out','move','In'); b.connect('clone','Entity','move','Entity')
    b.add('destroy','Destroy Entity'); b.connect('move','Out','destroy','In'); b.connect('spawn','Entity','destroy','Entity')
    b.add('another','Spawn Entity'); b.connect('destroy','Out','another','In')
    result=pair(native,b)
    assert set(result['entities'])=={'player','spawned_2','spawned_3'}
    assert result['entities']['spawned_2']['position']==[3,4,5]


@pytest.mark.parametrize('name,values,expected',[
    ('Set Parent',{'Child':'player','Parent':'grandchild'},'cycle'),
    ('Set Parent',{'Child':'player','Parent':'missing'},'Missing entity'),
    ('Clone Entity',{'Source':'missing'},'Missing entity'),
    ('Spawn Entity',{'Mesh':'assets/missing.gltf'},'not preloaded'),
    ('Spawn Entity',{'Name':''},'Invalid entity name'),
    ('Get Position',{'Entity':'missing'},'Missing entity'),
])
def test_entity_runtime_errors_match_original_node(native,name,values,expected):
    b=GraphBuilder(); b.add('start','On Game Start'); b.add('bad',name,**values)
    if name=='Get Position':
        b.add('save','Set Vector3 Variable'); b.connect('start','Out','save','In'); b.connect('bad','Value','save','Value')
    else: b.connect('start','Out','bad','In')
    a,c=native(b.graph,scene=make_scene(),frames=0)
    assert a.returncode==c.returncode==1
    assert json.loads(a.stderr)==json.loads(c.stderr)
    assert json.loads(a.stderr)['node']=='bad' and expected in json.loads(a.stderr)['message']
