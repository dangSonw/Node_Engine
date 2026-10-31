"""World pause through real interpreted/generated hosts, not a Python simulation."""
import json
import copy
import subprocess
import pytest
from editor.core.builder import GraphBuilder
from editor.core.codegen import CppEmitter
from editor.core.document import save_json
from tests.test_native import native
from tests.test_physics_scene import chain,run


def graph():
    b=GraphBuilder(); b.add('start','On Game Start')
    for nid,event in [('a_pause','On Game Pause'),('z_pause','On Game Pause'),('resume','On Game Resume')]:
        b.add(nid,event); chain(b,nid,(nid+'_log','Print Log',{'Message':nid}))
    return b


def test_pause_bindings_compile_and_lower_latent_handlers():
    b=graph(); ir=b.compile()
    assert [h['event'] for h in ir['events']['world_pause']]==[1017,1018,1017]
    assert 'BindWorldPauseEvent(ctx, 1017' in CppEmitter().generate(ir)
    chain(b,'a_pause_log',('delay','Delay',{'Seconds':0,'Unscaled':True}))
    ir=b.compile(); assert all(h['body'][0]['op']=='continuation_entry' for h in ir['events']['world_pause'])
    assert 'world_pause' not in GraphBuilder().compile()['events']


def test_pause_idempotence_order_and_immediate_query(native):
    b=graph(); chain(b,'start',('pause','Pause World',{}),('again','Pause World',{}),
        ('query','Set Boolean Variable',{'Name':'paused'}),('out','Print Log',{'Message':'out'}))
    b.add('paused','Is World Paused'); b.connect('paused','Value','query','Value')
    s=run(native,b,frames=3)
    assert s['logs']==['out','a_pause','z_pause']
    assert s['clock']['paused'] and s['clock']['scale']==1 and s['time']==0
    assert s['clock']['real_time']>0 and s['variables']['paused']['value']


def test_opposite_requests_keep_order_and_last_requested_state(native):
    b=graph(); chain(b,'start',('p','Pause World',{}),('r','Resume World',{}),('r2','Resume World',{}),('p2','Pause World',{}))
    s=run(native,b,frames=1)
    assert s['logs']==['a_pause','z_pause','resume','a_pause','z_pause'] and s['clock']['paused']


@pytest.mark.parametrize('scale',[0,.25,2])
def test_resume_keeps_requested_scale_and_current_frame_boundary(native,tmp_path,scale):
    b=graph(); chain(b,'start',('scale','Set Time Scale',{'Scale':scale}))
    b.add('p','On Key Pressed',Filter='P'); chain(b,'p',('pause','Pause World',{}))
    b.add('r','On Key Pressed',Filter='R'); chain(b,'r',('resume_world','Resume World',{}))
    b.add('fixed','On Fixed Update'); chain(b,'fixed',('tick','Translate',{'Delta':[1,0,0]}))
    path=tmp_path/'keys.json'; save_json(path,dict(version=1,events=[dict(frame=0,button='P',down=True),dict(frame=1,button='P',down=False),dict(frame=3,button='R',down=True)]))
    s=run(native,b,frames=5,extra=['--dt','.125','--input-replay',str(path)])
    assert s['time']==.25*scale and s['clock']['real_time']==.625
    assert s['clock']['scale']==scale and not s['clock']['paused']
    assert s['entities']['player']['position'][0]==int(15*scale)
    assert s['logs']==['a_pause','z_pause','resume']


def test_unscaled_timer_resumes_scaled_timer_and_latent_work(native):
    b=graph(); chain(b,'start',('pause','Pause World',{}),('scaled','Start Timer',{'Name':'scaled','Seconds':0}),
        ('real','Start Timer',{'Name':'real','Seconds':.25,'Unscaled':True}),('delay','Delay',{'Seconds':0}),
        ('delayed','Print Log',{'Message':'delayed'}))
    b.add('timer','On Timer Finished',Filter='real'); chain(b,'timer',('resume_world','Resume World',{}))
    b.add('scaled_timer','On Timer Finished',Filter='scaled'); chain(b,'scaled_timer',('scaled_log','Print Log',{'Message':'scaled'}))
    s=run(native,b,frames=2,extra=['--dt','.125'])
    assert s['time']==0 and s['logs']==['a_pause','z_pause','resume']
    s=run(native,b,frames=3,extra=['--dt','.125'])
    assert s['time']==.125 and s['logs']==['a_pause','z_pause','resume','delayed','scaled']


def test_pause_event_delay_can_complete_while_paused(native):
    b=graph(); chain(b,'start',('pause','Pause World',{}))
    chain(b,'a_pause_log',('delay','Delay',{'Seconds':.25,'Unscaled':True}),('done','Print Log',{'Message':'unscaled delay'}))
    s=run(native,b,frames=3,extra=['--dt','.125'])
    assert s['clock']['paused'] and s['time']==0 and s['logs']==['a_pause','z_pause','unscaled delay']


def test_reentrant_pause_resume_cycle_is_bounded(native):
    b=graph(); chain(b,'start',('pause','Pause World',{}))
    chain(b,'a_pause_log',('resume_world','Resume World',{})); chain(b,'resume_log',('pause_world','Pause World',{}))
    a,z=native(b.graph,frames=0,extra=['--budget','100'])
    assert a.returncode==z.returncode==1 and json.loads(a.stderr)==json.loads(z.stderr)
    assert 'budget' in json.loads(a.stderr)['message']


def test_paused_save_restores_without_synthetic_pause_event(native,tmp_path):
    b=graph(); chain(b,'start',('storage','Open Save Storage',{'Game ID':'pause-test'}))
    for key,action in [('P','Pause World'),('R','Resume World'),('S','Save Game'),('L','Load Game')]:
        b.add(key,'On Key Pressed',Filter=key); chain(b,key,(key+'_action',action,{}))
    def play(frames,events,store):
        path=tmp_path/'keys.json'; save_json(path,dict(version=1,events=[dict(frame=f,button=k,down=d) for f,k,d in events]))
        return run(native,b,frames=frames,extra=['--input-replay',str(path),'--save-root',str(store)])
    first=play(3,[(0,'P',True),(1,'P',False),(2,'S',True)],tmp_path/'saved')
    assert first['clock']['paused'] and first['persistence']['success']
    slot=next((tmp_path/'saved').rglob('slot-*.json')); raw=slot.read_bytes()
    reference=play(8,[(0,'P',True),(1,'P',False),(2,'S',True),(3,'S',False),(5,'R',True)],tmp_path/'reference')
    restored=play(6,[(0,'L',True),(3,'S',False),(5,'R',True)],tmp_path/'saved')
    assert reference['logs']==['a_pause','z_pause','resume'] and restored['logs']==['resume']
    reference['logs']=restored['logs']
    assert restored==reference and slot.read_bytes()==raw and not restored['clock']['paused']


def test_action_function_pause_returns_before_event(native):
    from editor.core.functions import new_function
    f=new_function('Pause simulation'); f['graph']['nodes'].append(dict(id='pause',type=7001,values={}))
    f['graph']['links']=[{'from':['entry','Out'],'to':['pause','In']},{'from':['pause','Out'],'to':['return','In']}]
    b=GraphBuilder(functions=[f]); b.add('start','On Game Start'); b.add('paused','On Game Pause')
    chain(b,'start',('call','Pause simulation',{}),('returned','Print Log',{'Message':'returned'}))
    chain(b,'paused',('event','Print Log',{'Message':'pause'}))
    s=run(native,b,frames=1); assert s['time']==0 and s['logs']==['returned','pause']


def test_native_rejects_malformed_pause_metadata(native,tmp_path):
    b=graph(); results=native(b.graph,frames=0); assert all(r.returncode==0 for r in results)
    original=b.compile()
    for index in range(9):
        ir=copy.deepcopy(original); h=ir['events']['world_pause'][0]
        if index==0: ir['events']['world_pause']={}
        elif index==1: ir['events']['world_pause']='bad'
        elif index==2: h['event']=1017.5
        elif index==3: h['event']=999
        elif index==4: h['body']={}
        elif index==5: h['node']=''
        elif index==6: h['node']=1
        elif index==7: h['extra']=0
        else: h.pop('body')
        path=tmp_path/f'bad-{index}.json'; save_json(path,ir)
        args=list(results[0].args); args[args.index('--ir')+1]=str(path)
        result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=20)
        assert result.returncode==1 and 'world_pause' in result.stderr
