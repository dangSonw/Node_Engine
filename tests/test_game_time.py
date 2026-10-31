"""Clock scaling through actual generated/interpreted frame loops."""
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene
from tests.test_native import native
from tests.test_physics_scene import chain,run


def graph(scale):
    b=GraphBuilder(); b.add('start','On Game Start')
    chain(b,'start',('scale','Set Time Scale',{'Scale':scale}),('timer','Start Timer',{'Name':'pulse','Seconds':.125,'Repeat':True}))
    b.add('timer_event','On Timer Finished',Filter='pulse')
    chain(b,'timer_event',('timer_hit','Rotate',{'Degrees':[0,1,0]}))
    b.add('fixed','On Fixed Update')
    chain(b,'fixed',('tick','Translate',{'Delta':[1,0,0]}),('fixed_dt','Set Variable',{'Name':'fixed_dt'}))
    b.add('dt','Get Delta Time'); b.connect('dt','Value','fixed_dt','Value')
    b.add('update','On Update'); end='update'
    for nid,name in [('dt_update','Get Delta Time'),('unscaled','Get Unscaled Delta Time'),('real','Get Real Time'),('game','Get Game Time'),('scale_query','Get Time Scale'),('fixed_query','Get Fixed Delta Time')]:
        b.add(nid,name); end=chain(b,end,(nid+'_store','Set Variable',{'Name':nid})); b.connect(nid,'Value',end,'Value')
    return b,end


@pytest.mark.parametrize('scale',[0,.25,1,2])
def test_clock_fixed_updates_and_timers(native,scale):
    b,_=graph(scale); state=run(native,b,frames=8,extra=['--dt','.125'])
    assert state['time']==scale and state['clock']['real_time']==1
    assert state['clock']['scale']==scale and state['clock']['dt']==.125*scale
    assert state['variables']['dt_update']==.125*scale
    assert state['variables']['unscaled']==.125 and state['variables']['real']==.875
    assert state['variables']['game']==.875*scale and state['variables']['scale_query']==scale
    assert state['variables']['fixed_query']==1/60
    assert state['entities']['player']['position'][0]==int(60*scale)
    assert state['entities']['player']['rotation'][1]==int(8*scale)
    if scale: assert state['variables']['fixed_dt']==1/60


def test_scale_changes_on_next_frame_and_input_can_resume(native,tmp_path):
    b,end=graph(1)
    for key,scale in [('P',0),('R',2)]:
        b.add('key_'+key,'Is Key Pressed',Key=key); branch=chain(b,end,('if_'+key,'Branch',{}))
        b.connect('key_'+key,'Value',branch,'Condition'); b.add('scale_'+key,'Set Time Scale',Scale=scale)
        b.connect(branch,'True','scale_'+key,'In'); end='scale_'+key
    # Separate update event for resume so it is reachable while P is not pressed.
    b.graph['links']=[e for e in b.graph['links'] if e['to']!=['if_R','In']]
    b.add('resume_update','On Update'); b.connect('resume_update','Out','if_R','In')
    path=tmp_path/'input.json'; path.write_text(json.dumps(dict(version=1,events=[dict(frame=0,button='P',down=True),dict(frame=1,button='P',down=False),dict(frame=3,button='R',down=True)])))
    state=run(native,b,frames=5,extra=['--dt','.125','--input-replay',str(path)])
    assert state['time']==.375 and state['clock']['real_time']==.625 and state['clock']['scale']==2
    assert state['entities']['player']['rotation'][1]==3
    assert state['entities']['player']['position'][0]==22 # 22 ticks plus a half tick carried forward.


def test_invalid_scale_identifies_node(native):
    b,_=graph(-1); a,z=native(b.graph,frames=1)
    assert a.returncode==z.returncode==1 and json.loads(a.stderr)==json.loads(z.stderr)
    assert json.loads(a.stderr)['node']=='scale' and 'nonnegative' in json.loads(a.stderr)['message']


def test_zero_duration_timer_is_frozen_until_resume(native):
    b,_=graph(0)
    next(n for n in b.graph['nodes'] if n['id']=='timer')['values'].update(Seconds=0,Repeat=False)
    state=run(native,b,frames=3,extra=['--dt','.125'])
    assert state['timers'][0]['remaining']==0 and state['entities']['player']['rotation'][1]==0


def test_zero_host_delta_preserves_zero_duration_timer_delivery(native):
    b,_=graph(1)
    next(n for n in b.graph['nodes'] if n['id']=='timer')['values'].update(Seconds=0,Repeat=False)
    state=run(native,b,frames=1,extra=['--dt','0'])
    assert not state['timers'] and state['entities']['player']['rotation'][1]==1
