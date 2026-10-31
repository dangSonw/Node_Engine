"""Before-deletion delivery through both real native execution paths."""
from copy import deepcopy
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.compiler import GraphError
from editor.core.document import default_scene, save_json
from editor.core.functions import new_function
from editor.core.prefabs import PrefabLibrary
from tests.test_native import native
from tests.test_physics_scene import chain, run
from tests.test_entity_lifecycle import listener


def prefab_scene():
    base=default_scene()['entities'][0]
    asset=dict(version=1,type='prefab',id='pair',name='Pair',root='root',entities=[
        dict(deepcopy(base),id='root',name='Root'),dict(deepcopy(base),id='child',name='Child',parent='root')])
    library=PrefabLibrary([asset]); entities=[]; records=[]
    for root,child in [('player','child'),('other','other_child')]:
        rec=library.instantiate_entities('pair',mapping={'root':root,'child':child})
        entities+=rec.pop('entities'); records.append(rec)
    return dict(version=1,entities=entities,variables={},prefab_assets=library.assets,prefab_instances=records)


def capture(b,nid='destroyed',receiver=''):
    end=listener(b,'Destroyed',nid,receiver)
    b.add(nid+'_name','Get Entity Name'); b.connect(nid,'Entity',nid+'_name','Entity')
    end=chain(b,end,(nid+'_save','Set String Variable',{'Name':nid+'_name'}))
    b.connect(nid+'_name','Value',end,'Value'); return end


def test_destroyed_static_receiver_scope_and_function_exclusion():
    b=GraphBuilder(); capture(b); b.add('start','On Game Start')
    chain(b,'start',('leak','Set Entity Variable',{'Name':'leak'})); b.connect('destroyed','Entity','leak','Value')
    with pytest.raises(GraphError,match='inside that entity lifecycle'): b.compile(default_scene())
    b.graph['links'].pop(); b.add('self','Get Self'); b.connect('self','Entity','destroyed','Receiver')
    with pytest.raises(GraphError,match='constant in the Inspector'): b.compile(default_scene())


@pytest.mark.parametrize('active',[True,False])
def test_before_delete_reads_data_including_inactive_owned_receiver(native,active):
    s=default_scene(); s['entities'][0].update(active=active,name='Robot trước khi xóa')
    b=GraphBuilder(); b.add('start','On Game Start'); capture(b); capture(b,'own','player')
    chain(b,'start',('destroy','Destroy Entity',{}),('again','Destroy Entity',{}),('after','Print Log',{'Message':'after'}))
    result=run(native,b,s)
    assert result['logs']==['destroyed:player:'+str(active).lower(),'own:player:'+str(active).lower(),'after']
    assert result['variables']['destroyed_name']['value']==result['variables']['own_name']['value']=='Robot trước khi xóa'
    assert not result['entities']


def test_cascade_reentrant_self_and_other_destroy_preserve_callback_reads(native):
    s=default_scene(); base=s['entities'][0]; s['entities'] += [dict(deepcopy(base),id='child',parent='player'),dict(deepcopy(base),id='other')]
    b=GraphBuilder(); b.add('start','On Game Start'); capture(b)
    end=capture(b,'own','child')
    chain(b,end,('same','Destroy Entity',{'Entity':'child'}),('parent','Destroy Entity',{'Entity':'player'}),
          ('other','Destroy Entity',{'Entity':'other'}),('alive','Set Boolean Variable',{'Name':'other_was_alive'}))
    b.add('other_exists','Entity Exists',Entity='other'); b.connect('other_exists','Value','alive','Value')
    chain(b,'start',('destroy','Destroy Entity',{}),('after','Print Log',{'Message':'after'}))
    result=run(native,b,s)
    assert result['logs']==['destroyed:child:true','own:child:true','destroyed:player:true','destroyed:other:true','after']
    assert not result['entities'] and result['variables']['other_was_alive']['value']


def test_callback_spawn_survives_and_created_queue_waits_until_caller_finishes(native):
    b=GraphBuilder(); b.add('start','On Game Start'); listener(b,'Created')
    end=capture(b,'own','player')
    chain(b,end,('drop','Spawn Entity',{'Name':'Loot'}))
    chain(b,'start',('destroy','Destroy Entity',{}),('after','Print Log',{'Message':'after'}))
    result=run(native,b)
    assert result['logs']==['created:player:true','own:player:true','after','created:spawned_1:true']
    assert set(result['entities'])=={'spawned_1'}


def test_child_added_during_callback_is_not_deleted_without_notification(native):
    b=GraphBuilder(); b.add('start','On Game Start'); capture(b); end=capture(b,'own','player')
    chain(b,end,('spawn','Spawn Entity',{}),('attach','Set Parent',{'Parent':'player'})); b.connect('spawn','Entity','attach','Child')
    chain(b,'start',('destroy','Destroy Entity',{}))
    result=run(native,b)
    assert result['logs']==['destroyed:player:true','own:player:true','destroyed:spawned_1:true'] and not result['entities']


def test_reparent_cannot_cancel_already_notified_deletion(native):
    s=default_scene(); s['entities'].append(dict(deepcopy(s['entities'][0]),id='child',parent='player'))
    b=GraphBuilder(); b.add('start','On Game Start'); b.add('dying','On Object Destroyed',Receiver='child')
    chain(b,'dying',('rescue','Set Parent',{'Child':'child','Parent':''})); chain(b,'start',('destroy','Destroy Entity',{}))
    a,z=native(b.graph,scene=s,frames=0)
    assert a.returncode==z.returncode==1 and json.loads(a.stderr)==json.loads(z.stderr)
    assert json.loads(a.stderr)['node']=='rescue' and 'pending destruction' in json.loads(a.stderr)['message']


def test_reset_removes_additions_after_callbacks_and_preserves_spawned_loot(native):
    s=prefab_scene(); s['entities'].append(dict(deepcopy(s['entities'][0]),id='extra',parent='player',name='Added child'))
    b=GraphBuilder(); b.add('start','On Game Start'); end=capture(b,'own','extra')
    chain(b,end,('spawn','Spawn Entity',{'Name':'Loot'}),('nested_reset','Reset Prefab Instance',{'Instance':'player'}))
    chain(b,'start',('reset','Reset Prefab Instance',{'Instance':'player'}))
    result=run(native,b,s)
    assert result['logs']==['own:extra:true'] and result['variables']['own_name']['value']=='Added child'
    assert 'extra' not in result['entities'] and 'spawned_1' in result['entities']


def test_apply_notifies_removed_dependent_member_and_preserves_callback_changes(native):
    s=prefab_scene(); b=GraphBuilder(); b.add('start','On Game Start'); capture(b)
    end=capture(b,'own','other_child'); chain(b,end,('spawn','Spawn Entity',{'Name':'Loot'}),('move','Set Position',{'Entity':'other','Value':[3,2,1]}))
    chain(b,'start',('remove','Destroy Entity',{'Entity':'child'}),('apply','Apply Prefab Overrides',{'Instance':'player'}))
    result=run(native,b,s)
    assert result['logs']==['destroyed:child:true','destroyed:other_child:true','own:other_child:true']
    assert set(result['entities'])=={'player','other','spawned_1'} and result['entities']['other']['position']==[3,2,1]


def test_prefab_root_destroys_detached_members_and_ignores_deferred_reset_of_deleted_target(native):
    s=prefab_scene(); b=GraphBuilder(); b.add('start','On Game Start'); capture(b)
    end=capture(b,'own','player'); chain(b,end,('reset','Reset Prefab Instance',{'Instance':'player'}))
    chain(b,'start',('detach','Set Parent',{'Child':'child','Parent':''}),('destroy','Destroy Entity',{}))
    result=run(native,b,s)
    assert result['logs']==['destroyed:child:true','destroyed:player:true','own:player:true']
    assert set(result['entities'])=={'other','other_child'}


def test_inline_callback_reenters_continuation_vm_and_preserves_outer_function_parameters(native):
    f=new_function('Remove',inputs=[dict(name='Number',type='int',default=0)],outputs=[dict(name='Number',type='int')])
    fb=GraphBuilder(functions=[f],function=f['id']); fb.add('entry','Function Input'); fb.add('return','Function Output')
    chain(fb,'entry',('destroy','Destroy Entity',{}),('wait','Delay',{'Seconds':0}))
    fb.connect('wait','Out','return','In').connect('entry','Number','return','Number'); f['graph']=fb.graph
    b=GraphBuilder(functions=[f]); b.add('start','On Game Start'); end=capture(b)
    chain(b,end,('wait_global','Delay',{'Seconds':.02}),('captured','Set Entity Variable',{'Name':'dead'}))
    b.connect('destroyed','Entity','captured','Value')
    b.add('owned','On Object Destroyed',Receiver='player'); chain(b,'owned',('wait_owned','Delay',{'Owner':'player','Seconds':0}),('must_not_run','Print Log',{'Message':'cancelled owner survived'}))
    chain(b,'start',('call','Remove',{'Number':9223372036854775807}),('result','Set Integer Variable',{'Name':'result'})); b.connect('call','Number','result','Value')
    result=run(native,b,frames=5)
    assert result['variables']['result']['value']==9223372036854775807 and result['variables']['dead']['value']=='player'
    assert result['logs']==['destroyed:player:true'] and not result['continuations']['tasks']


def test_destroy_callback_saves_committed_scene_and_load_does_not_repeat_deletion(native,tmp_path):
    b=GraphBuilder(); b.add('start','On Game Start')
    chain(b,'start',('storage','Open Save Storage',{'Game ID':'destroy-save'}))
    end=capture(b); chain(b,end,('save','Save Game',{'Slot':'dead'}))
    for key,action in [('X','Destroy Entity'),('L','Load Game')]:
        b.add('update'+key,'On Update'); b.add('key'+key,'Is Key Pressed',Key=key)
        chain(b,'update'+key,('if'+key,'Branch',{})); b.connect('key'+key,'Value','if'+key,'Condition')
        b.add('action'+key,action,**({'Slot':'dead'} if key=='L' else {})); b.connect('if'+key,'True','action'+key,'In')
    replay=tmp_path/'input.json'; save_json(replay,dict(version=1,events=[dict(frame=0,button='X',down=True)]))
    args=['--save-root',str(tmp_path),'--input-replay',str(replay)]; saved=run(native,b,frames=2,extra=args)
    save_json(replay,dict(version=1,events=[dict(frame=0,button='L',down=True)])); loaded=run(native,b,frames=2,extra=args)
    assert saved['logs']==['destroyed:player:true'] and loaded['logs']==[] and saved['persistence']['success'] and loaded['persistence']['success']
    assert not loaded['entities'] and loaded['variables']['destroyed_name']==saved['variables']['destroyed_name']
