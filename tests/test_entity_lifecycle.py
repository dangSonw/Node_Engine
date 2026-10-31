"""Real generated/interpreted lifecycle delivery, hierarchy and prefab integration."""
import json
from copy import deepcopy
import pytest
from editor.core.builder import GraphBuilder
from editor.core.codegen import CppEmitter
from editor.core.compiler import GraphError
from editor.core.document import default_scene
from editor.core.functions import new_function
from editor.core.registry import ROOT
from editor.core.scene import is_active
from tests.test_native import native
from tests.test_physics_scene import chain, run
from tests.test_prefab_reset_native import scene_and_builder


def listener(b, kind, nid=None, receiver=''):
    nid=nid or kind.lower()
    b.add(nid,'On Object '+kind,Receiver=receiver)
    b.add(nid+'_id','Entity ID'); b.connect(nid,'Entity',nid+'_id','Entity')
    b.add(nid+'_flag','Format Boolean'); b.connect(nid,'Active',nid+'_flag','Value')
    b.add(nid+'_prefix','Concat Strings',A=nid+':'); b.connect(nid+'_id','Value',nid+'_prefix','B')
    b.add(nid+'_colon','Concat Strings',A=':'); b.connect(nid+'_flag','Value',nid+'_colon','B')
    b.add(nid+'_text','Concat Strings'); b.connect(nid+'_prefix','Value',nid+'_text','A').connect(nid+'_colon','Value',nid+'_text','B')
    end=chain(b,nid,(nid+'_log','Print Log',{})); b.connect(nid+'_text','Value',end,'Message')
    return end


def graph():
    b=GraphBuilder(); b.add('start','On Game Start')
    for kind in ('Created','Enabled','Disabled'): listener(b,kind)
    return b


def initial(*ids):
    return [text for eid in sorted(ids) for text in ('created:'+eid+':true','enabled:'+eid+':true')]


def test_listener_scope_static_receiver_and_typed_export():
    b=graph(); ir=b.compile(default_scene())
    assert len(ir['events']['entity_lifecycle'])==3 and 'rt::BindEntityLifecycle' in CppEmitter().generate(ir)
    chain(b,'start',('bad','Set Entity Variable',{'Name':'bad'})); b.connect('created','Entity','bad','Value')
    with pytest.raises(GraphError,match='inside that entity lifecycle'): b.compile(default_scene())
    b.graph['links'].pop(); b.add('self','Get Self'); b.connect('self','Entity','created','Receiver')
    with pytest.raises(GraphError,match='constant in the Inspector'): b.compile(default_scene())


@pytest.mark.parametrize('kind',['Created','Enabled','Disabled'])
def test_receiver_must_exist_and_listener_belongs_in_gameplay(kind):
    b=GraphBuilder(); listener(b,kind,receiver='missing')
    with pytest.raises(GraphError,match='receiver entity does not exist'): b.compile(default_scene())
    f=new_function('Action'); fb=GraphBuilder(functions=[f],function=f['id']); fb.add('entry','Function Input'); listener(fb,kind)
    f['graph']=fb.graph; b=GraphBuilder(functions=[f])
    with pytest.raises(GraphError,match='belong in Gameplay'): b.compile(default_scene())


def test_initial_entities_before_start_and_inactive_own_receiver(native):
    b=graph(); scene=default_scene(); scene['entities'][0]['active']=False
    end=listener(b,'Created','own','player'); b.add('self','Get Self')
    chain(b,end,('capture','Set Entity Variable',{'Name':'self'})); b.connect('self','Entity','capture','Value')
    chain(b,'start',('log_start','Print Log',{'Message':'start'}))
    state=run(native,b,scene)
    assert state['logs']==['created:player:false','own:player:false','start']
    assert state['variables']['self']['value']=='player' and state['events']['lifecycle_started']


def test_spawn_clone_camera_capture_final_components_and_queued_state(native):
    b=graph()
    chain(b,'start',('spawn','Spawn Entity',{'Name':'Fresh'}),('off','Set Entity Active',{'Active':False}),
          ('clone','Clone Entity',{'Name':'Inactive clone'}),('camera','Create Camera',{'Name':'Camera'}),
          ('done','Print Log',{'Message':'actions-done'}))
    result=run(native,b)
    assert result['logs']==initial('player')+['actions-done','created:spawned_1:true','enabled:spawned_1:true',
        'disabled:player:false','created:spawned_2:false','created:spawned_3:true','enabled:spawned_3:true']
    assert result['scene']['entities'][-1]['camera'] and not is_active(result['scene'],'spawned_2')


def test_rapid_toggles_hierarchy_reparent_and_idempotence(native):
    b=graph(); s=default_scene(); base=s['entities'][0]
    s['entities']+=[dict(deepcopy(base),id='child',parent='player'),dict(deepcopy(base),id='sleeping',active=False)]
    listener(b,'Disabled','own','child')
    chain(b,'start',('off','Set Entity Active',{'Active':False}),('off_again','Set Entity Active',{'Active':False}),
          ('on','Set Entity Active',{'Active':True}),('parent','Set Parent',{'Child':'child','Parent':'sleeping'}),
          ('self_off','Set Entity Active',{'Entity':'child','Active':False}),
          ('detach','Set Parent',{'Child':'child','Parent':''}),('self_on','Set Entity Active',{'Entity':'child','Active':True}))
    result=run(native,b,s)
    assert result['logs']==initial('child','player')+['created:sleeping:false',
        'disabled:child:false','own:child:false','disabled:player:false','enabled:child:true','enabled:player:true',
        'disabled:child:false','own:child:false','enabled:child:true']


def test_disabled_callback_can_reactivate_and_scope_restores(native):
    b=graph(); end=listener(b,'Disabled','own','player')
    chain(b,end,('reactivate','Set Entity Active',{'Active':True}))
    chain(b,'start',('off','Set Entity Active',{'Active':False}))
    result=run(native,b)
    assert result['logs']==initial('player')+['disabled:player:false','own:player:false','enabled:player:true']
    assert is_active(result['scene'],'player')


def test_destroy_cancels_owned_delivery_but_global_payload_is_a_snapshot(native):
    b=graph(); listener(b,'Disabled','own','player')
    chain(b,'start',('off','Set Entity Active',{'Active':False}),('destroy','Destroy Entity',{}),
          ('again','Destroy Entity',{}))
    result=run(native,b)
    assert result['logs']==initial('player')+['disabled:player:false'] and not result['entities']


def test_callback_can_spawn_without_recursion_and_infinite_emissions_are_bounded(native):
    b=GraphBuilder(); b.add('created','On Object Created')
    chain(b,'created',('spawn','Spawn Entity',{}))
    a,z=native(b.graph,frames=0,extra=['--budget','100'])
    assert a.returncode==z.returncode==1 and json.loads(a.stderr)==json.loads(z.stderr)
    assert 'budget' in json.loads(a.stderr)['message']


def test_prefab_reset_recreates_missing_id_and_rebinds_inactive_receiver(native):
    s,b=scene_and_builder(); next(e for e in s['entities'] if e['id']=='player')['active']=False
    for kind in ('Created','Enabled','Disabled'): listener(b,kind)
    listener(b,'Created','restored','child'); b.add('start','On Game Start')
    chain(b,'start',('destroy','Destroy Entity',{'Entity':'child'}),
          ('reset','Reset Prefab Instance',{'Instance':'player'}))
    result=run(native,b,s,extra=['--project-root',str(ROOT/'examples/core_demo')])
    assert result['logs'].count('created:child:false')==1
    assert result['logs'].count('created:child:true')==1 and result['logs'].count('restored:child:true')==1
    assert result['logs'].count('enabled:player:true')==1
    assert result['logs'].count('created:player:false')==1


def test_prefab_instantiate_and_apply_notify_only_committed_changes(native):
    s,b=scene_and_builder()
    for kind in ('Created','Enabled','Disabled'): listener(b,kind)
    b.add('start','On Game Start')
    chain(b,'start',('off','Set Entity Active',{'Entity':'child','Active':False}),
          ('apply','Apply Prefab Overrides',{'Instance':'player'}),
          ('spawn','Instantiate Prefab',{'Prefab':'robot'}))
    result=run(native,b,s,extra=['--project-root',str(ROOT/'examples/core_demo')])
    assert result['logs']==initial('child','other','other_child','player')+['disabled:child:false',
        'disabled:other_child:false','created:spawned_1:true','enabled:spawned_1:true','created:spawned_2:false']


def test_lifecycle_payload_survives_latent_function_and_world_changes(native):
    f=new_function('Wait',inputs=[dict(name='Item',type='entity',default=''),dict(name='WasActive',type='bool',default=False)],
        outputs=[dict(name='Item',type='entity'),dict(name='WasActive',type='bool')])
    fb=GraphBuilder(functions=[f],function=f['id']); fb.add('entry','Function Input'); fb.add('return','Function Output')
    chain(fb,'entry',('delay','Delay',{'Seconds':.05})); fb.connect('delay','Out','return','In')
    for port in ('Item','WasActive'): fb.connect('entry',port,'return',port)
    f['graph']=fb.graph; b=GraphBuilder(functions=[f]); b.add('created','On Object Created')
    chain(b,'created',('call','Wait',{}),('store','Set Boolean Variable',{'Name':'captured'}))
    b.connect('created','Entity','call','Item').connect('created','Active','call','WasActive').connect('call','WasActive','store','Value')
    b.add('start','On Game Start'); chain(b,'start',('off','Set Entity Active',{'Active':False}))
    result=run(native,b,frames=10)
    assert result['variables']['captured']['value'] and not is_active(result['scene'],'player') and not result['continuations']['tasks']
