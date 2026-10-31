"""Completion delivery through real generated and interpreted native games."""
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.compiler import GraphError
from editor.core.codegen import CppEmitter
from editor.core.registry import ROOT
from tests.test_native import native
from tests.test_animation_playback import scene, start
from tests.test_physics_scene import chain, run
from tools.animation_fixture import rig, write


def listener(b, nid='finished', receiver='', clip='', message=None):
    b.add(nid, 'On Animation Finished', Receiver=receiver, **{'Clip Filter': clip})
    return chain(b, nid, (nid+'_log', 'Print Log', {'Message': message or nid}))


def execute(native, b, s=None, frames=10, dt=.25, root=ROOT):
    return run(native, b, scene() if s is None else s, frames,
               ['--dt', str(dt), '--project-root', str(root)])


def test_listener_scope_constants_filter_and_export():
    b=start(); listener(b, receiver='player', clip='Wave')
    chain(b,'finished_log',('capture','Set String Variable',{'Name':'clip'}))
    b.connect('finished','Clip','capture','Value')
    ir=b.compile(scene()); assert ir['events']['animation_finished'][0]['filter']=='Wave'
    assert 'rt::BindAnimationFinished' in CppEmitter().generate(ir)
    chain(b,'start',('leak','Set String Variable',{'Name':'leak'}))
    b.connect('finished','Clip','leak','Value')
    with pytest.raises(GraphError,match='inside that animation finished event handler'): b.compile(scene())
    b.graph['links'].pop(); b.add('self','Get Self'); b.connect('self','Entity','finished','Receiver')
    with pytest.raises(GraphError,match='constant in the Inspector'): b.compile(scene())


@pytest.mark.parametrize('values,fragment',[
    ({'Receiver':'missing'}, 'receiver entity does not exist'),
    ({'Clip Filter':'a\0b'}, 'no NUL'),
    ({'Clip Filter':'ế'*171}, '512 UTF-8 bytes')])
def test_invalid_listener(values,fragment):
    b=GraphBuilder(); b.add('finished','On Animation Finished',**values)
    with pytest.raises(GraphError,match=fragment): b.compile()


@pytest.mark.parametrize('speed,loop,expected',[(1,False,1),(-1,False,1),(1,True,0),(0,False,0)])
def test_endpoints_once_loop_and_speed(native,speed,loop,expected):
    b=start(); chain(b,'start',('play','Play Animation',{'Clip':'Wave','Loop':loop,'Speed':speed}))
    listener(b,clip='Wave'); listener(b,'wrong_clip',clip='Walk')
    result=execute(native,b)
    assert result['logs']==['finished']*expected and result['events']['pending']==0


def test_scoped_payload_and_all_players_advance_before_late_update(native):
    s=scene(); other=dict(s['entities'][0],id='other'); s['entities'].append(other)
    b=start(); chain(b,'start',('wave','Play Animation',{'Clip':'Wave','Loop':False}),
                    ('walk','Play Animation',{'Entity':'other','Clip':'Walk','Loop':True}))
    for nid,receiver in [('global',''),('owner','player'),('unrelated','other')]:
        end=listener(b,nid,receiver,'Wave')
        for field,type in [('Entity','Entity'),('Clip','String')]:
            end=chain(b,end,(nid+field,'Set '+type+' Variable',{'Name':nid+field}))
            b.connect(nid,field,end,'Value')
        b.add(nid+'self','Get Self')
        end=chain(b,end,(nid+'self_store','Set Entity Variable',{'Name':nid+'self'}))
        b.connect(nid+'self','Entity',end,'Value')
    b.add('other_time','Get Animation Time',Entity='other')
    chain(b,'owner_log',('observed','Set Variable',{'Name':'other_time'}))
    # Replace the owner's first wire to keep one exec chain.
    b.graph['links']=[link for link in b.graph['links'] if link['from']!=['owner_log','Out'] or link['to']==['observed','In']]
    b.connect('observed','Out','ownerEntity','In').connect('other_time','Value','observed','Value')
    end=chain(b,'ownerClip',('mark','Set Variable',{'Name':'completed','Value':1}))
    b.graph['links']=[link for link in b.graph['links'] if link['from']!=['ownerClip','Out'] or link['to']==['mark','In']]
    b.connect(end,'Out','ownerself_store','In')
    b.add('late','On Late Update'); b.add('completed','Get Variable',Name='completed')
    chain(b,'late',('late_store','Set Variable',{'Name':'late_completed'})); b.connect('completed','Value','late_store','Value')
    s['variables']['completed']=0.
    result=execute(native,b,s,frames=8); v=result['variables']
    assert result['logs']==['global','owner'] and v['other_time']==0 and v['late_completed']==1
    assert v['globalEntity']['value']==v['ownerEntity']['value']=='player'
    assert v['globalClip']['value']==v['ownerClip']['value']=='Wave'
    assert v['globalself']['value']=='' and v['ownerself']['value']=='player'


@pytest.mark.parametrize('block,unblock',[
    (('Pause Animation',{}),('Resume Animation',{})),
    (('Set Entity Active',{'Active':False}),('Set Entity Active',{'Active':True})),
    (('Set Time Scale',{'Scale':0}),('Set Time Scale',{'Scale':1}))])
def test_suspended_playback_finishes_after_resuming(native,block,unblock):
    b=start(); chain(b,'start',('play','Play Animation',{'Clip':'Wave','Loop':False}),('block',*block))
    listener(b,receiver='player'); result=execute(native,b)
    assert not result['logs'] and result['animation']['player']['time']==0
    b.add('update','On Update'); b.add('frame','Get Frame Count'); b.add('equal','Nearly Equal',B=10)
    b.connect('frame','Value','equal','A'); chain(b,'update',('branch','Branch',{}))
    b.connect('equal','Value','branch','Condition'); b.add('unblock',unblock[0],**unblock[1]); b.connect('branch','True','unblock','In')
    result=execute(native,b,frames=20)
    assert result['logs']==['finished'] and result['animation']['player']['time']==2


def test_stop_and_seek_do_not_emit_completion(native):
    b=start(); chain(b,'start',('play','Play Animation',{'Clip':'Wave','Loop':False}),
                    ('seek','Set Animation Time',{'Time':2}),('pause','Pause Animation',{}))
    listener(b); assert not execute(native,b)['logs']
    chain(b,'pause',('stop','Stop Animation',{})); assert not execute(native,b)['logs']


def test_callback_can_replace_clip_and_destroy_receiver(native):
    b=start(); chain(b,'start',('play','Play Animation',{'Clip':'Wave','Loop':False}))
    s=scene(); s['variables']['recreated']={'type':'bool','value':False}
    b.add('finished','On Animation Finished',Receiver='player',**{'Clip Filter':'Wave'})
    chain(b,'finished',('log','Print Log',{'Message':'wave'}),('branch','Branch',{}))
    b.add('done','Get Boolean Variable',Name='recreated'); b.connect('done','Value','branch','Condition')
    b.add('replay','Play Animation',Clip='Wave',Loop=False); b.connect('branch','False','replay','In')
    chain(b,'replay',
        ('mark','Set Boolean Variable',{'Name':'recreated','Value':True}),
        ('clone','Clone Entity',{}),('destroy_clone','Destroy Entity',{'Entity':'spawned_1'}))
    b.add('destroy','Destroy Entity'); b.connect('branch','True','destroy','In')
    listener(b,'z_stale',receiver='player',clip='Wave')
    result=execute(native,b,s,frames=17)
    assert result['logs']==['wave','z_stale','wave'] and 'player' not in result['entities']


def test_zero_duration_queues_after_graph_and_load_does_not_repeat(native,tmp_path):
    doc,binary=rig(); doc['animations']=[dict(doc['animations'][-1],name='Instant')]
    asset=write(tmp_path/'assets',doc,binary,mode='glb')
    s=scene(); s['entities'][0]['mesh']='assets/'+asset.name
    b=start(); chain(b,'start',('storage','Open Save Storage',{'Game ID':'instant-event'}),
        ('play','Play Animation',{'Clip':'Instant','Loop':False}),('after','Print Log',{'Message':'after-play'}))
    end=listener(b,clip='Instant'); chain(b,end,('save','Save Game',{'Slot':'instant'}))
    b.add('update','On Update'); b.add('pressed','Is Key Pressed',Key='L')
    chain(b,'update',('branch','Branch',{})); b.connect('pressed','Value','branch','Condition')
    b.add('load','Load Game',Slot='instant'); b.connect('branch','True','load','In')
    extra=['--project-root',str(tmp_path),'--save-root',str(tmp_path/'saves')]
    first=run(native,b,s,1,extra); assert first['logs']==['after-play','finished'] and first['persistence']['success']
    loaded=run(native,b,s,1,extra+['--key','L'])
    assert loaded['persistence']['success'] and loaded['logs']==['after-play','finished']
    assert loaded['events']['pending']==0 and not loaded['animation']['player']['playing']


def test_callback_budget_reports_graph_node(native):
    b=start(); chain(b,'start',('play','Play Animation',{'Clip':'Wave','Loop':False,'Speed':100}))
    b.add('finished','On Animation Finished'); chain(b,'finished',('loop','While Loop',{'Condition':True}))
    a,z=native(b.graph,scene=scene(),frames=1,extra=['--dt','.25','--budget','200','--project-root',str(ROOT)])
    assert a.returncode==z.returncode==1 and json.loads(a.stderr)==json.loads(z.stderr)
    assert json.loads(a.stderr)['node']=='loop' and 'budget' in json.loads(a.stderr)['message']
