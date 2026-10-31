"""Suspend real native graphs, including loop/function state and checkpoint resume."""
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene
from editor.core.functions import new_function
from tests.test_native import native
from tests.test_physics_scene import chain, run


def delayed(label='Delay', **values):
    b=GraphBuilder(); b.add('start','On Game Start')
    chain(b,'start',('wait',label,values),('log','Print Log',{'Message':'ready'}),
          ('at','Set Variable',{'Name':'at'}))
    b.add('frame','Get Frame Count'); b.connect('frame','Value','at','Value')
    return b


@pytest.mark.parametrize('seconds,frames,at',[(0,1,0),(.2,2,1),(.3,3,2)])
def test_delay_yields_without_blocking_other_events(native,seconds,frames,at):
    b=delayed(Seconds=seconds)
    b.add('start_z','On Game Start'); chain(b,'start_z',('other','Print Log',{'Message':'other event'}))
    result=run(native,b,frames=frames,extra=['--dt','.1'])
    assert result['logs']==['other event','ready'] and result['variables']['at']==at
    assert result['continuations']['tasks']==[]


def test_update_reentry_is_ignored_and_wait_starts_next_frame(native):
    b=delayed(Seconds=.2); b.graph['nodes'][0]['type']=b.registry.by_name('On Update').id
    result=run(native,b,frames=6,extra=['--dt','.1'])
    assert result['logs']==['ready']*2 and result['variables']['at']==4
    assert len(result['continuations']['tasks'])==1


def test_wait_until_reads_world_again_and_allows_other_update_entries(native):
    b=delayed('Wait Until'); b.add('value','Get Variable',Name='counter'); b.add('condition','Greater',B=1)
    b.connect('value','Value','condition','A').connect('condition','Value','wait','Condition')
    b.add('update','On Update'); chain(b,'update',('increment','Set Variable',{'Name':'counter'}))
    b.add('add','Add',B=1); b.connect('value','Value','add','A').connect('add','Value','increment','Value')
    s=default_scene(); s['variables']={'counter':0.}
    result=run(native,b,s,4,extra=['--dt','.1'])
    assert result['logs']==['ready'] and result['variables']['at']==2 and result['variables']['counter']==4


def test_retrigger_replaces_captured_invocation(native):
    b=delayed('Retriggerable Delay',Seconds=.2)
    b.add('update','On Update'); b.add('first','Branch'); b.add('less','Less',B=3)
    b.connect('frame','Value','less','A').connect('less','Value','first','Condition')
    b.connect('update','Out','first','In').connect('first','True','wait','In')
    result=run(native,b,frames=6,extra=['--dt','.1'])
    assert result['logs']==['ready'] and result['variables']['at']==4


def test_for_each_captures_array_item_and_function_parameters(native):
    f=new_function('Delayed echo',inputs=[dict(name='Number',type='int',default=0)],outputs=[dict(name='Result',type='int')])
    body=GraphBuilder(functions=[f],function=f['id']); body.add('entry','Function Input')
    chain(body,'entry',('wait','Delay',{'Seconds':0}),('return','Function Output',{}))
    body.connect('entry','Number','return','Result'); f['graph']=body.graph
    b=GraphBuilder(functions=[f]); b.add('start','On Game Start')
    chain(b,'start',('each','For Each Integer',{'Array':[3,5,7]}))
    b.add('call','Delayed echo'); b.connect('each','Body','call','In').connect('each','Item','call','Number')
    chain(b,'call',('sum','Set Integer Variable',{'Name':'total'}))
    b.add('total','Get Integer Variable',Name='total'); b.add('add','Integer Add')
    b.connect('total','Value','add','A').connect('call','Result','add','B').connect('add','Value','sum','Value')
    b.add('done','Print Log',Message='done'); b.connect('each','Done','done','In')
    s=default_scene(); s['variables']={'total':{'type':'int','value':0}}
    result=run(native,b,s,3)
    assert result['variables']['total']['value']==15 and result['logs']==['done']
    assert not result['continuations']['tasks']


def test_continue_and_break_unwind_a_suspended_loop(native):
    b=GraphBuilder(); b.add('start','On Game Start'); chain(b,'start',('loop','For Loop',{'Count':5}))
    b.add('delay','Delay',Seconds=0); b.connect('loop','Body','delay','In')
    chain(b,'delay',('flip','Flip Flop',{}))
    b.add('continue','Continue Loop'); b.add('break','Break Loop')
    b.connect('flip','A','continue','In').connect('flip','B','break','In')
    b.add('done','Print Log',Message='done'); b.connect('loop','Done','done','In')
    result=run(native,b,frames=2)
    assert result['logs']==['done'] and not result['continuations']['tasks']


def test_time_scale_zero_freezes_scaled_delay_but_unscaled_and_condition_work(native):
    b=delayed(Seconds=0)
    b.add('start_0','On Game Start'); chain(b,'start_0',('freeze','Set Time Scale',{'Scale':0}))
    b.add('start_1','On Game Start'); chain(b,'start_1',('real','Delay',{'Seconds':.2,'Unscaled':True}),('real_log','Print Log',{'Message':'unscaled'}))
    b.add('start_2','On Game Start'); chain(b,'start_2',('true','Wait Until',{'Condition':True}),('true_log','Print Log',{'Message':'immediate'}))
    result=run(native,b,frames=4,extra=['--dt','.1'])
    assert result['logs']==['immediate','unscaled'] and len(result['continuations']['tasks'])==1


def test_destroy_owner_cancels_suspended_task(native):
    b=delayed(Seconds=0,Owner='player'); b.add('start_z','On Game Start')
    chain(b,'start_z',('destroy','Destroy Entity',{'Entity':'player'}))
    result=run(native,b,frames=4)
    assert result['logs']==[] and result['continuations']['tasks']==[]


def test_invalid_delay_reports_original_node_in_both_paths(native):
    a,z=native(delayed(Seconds=-1).graph,frames=1)
    assert a.returncode==z.returncode==1
    assert json.loads(a.stderr)==json.loads(z.stderr)
    assert json.loads(a.stderr)['node']=='wait' and 'nonnegative' in a.stderr


def test_ignored_reentry_does_not_evaluate_a_now_invalid_duration(native):
    b=delayed(); b.add('seconds','Get Variable',Name='seconds'); b.connect('seconds','Value','wait','Seconds')
    b.add('start_y','On Game Start'); chain(b,'start_y',('negative','Set Variable',{'Name':'seconds','Value':-1}))
    b.add('start_z','On Game Start'); b.connect('start_z','Out','wait','In')
    s=default_scene(); s['variables']={'seconds':.2}
    result=run(native,b,s,2,extra=['--dt','.1'])
    assert result['logs']==['ready']


def test_owner_inactivity_freezes_remaining_time_and_clone_has_no_task(native):
    b=delayed(Seconds=.3,Owner='player')
    b.add('start_y','On Game Start'); chain(b,'start_y',('clone','Clone Entity',{}),('inactive','Set Entity Active',{'Entity':'player','Active':False}))
    b.add('start_z','On Game Start'); chain(b,'start_z',('wake','Delay',{'Seconds':.2}),('active','Set Entity Active',{'Entity':'player','Active':True}))
    result=run(native,b,frames=5,extra=['--dt','.1'])
    assert result['logs']==['ready'] and result['variables']['at']==4
    assert 'spawned_1' in result['entities'] and not result['continuations']['tasks']


def test_suspended_while_rechecks_condition_and_sequence_continues_after_it(native):
    b=GraphBuilder(); b.add('start','On Game Start'); chain(b,'start',('sequence','Sequence',{}))
    b.add('loop','While Loop'); b.connect('sequence','First','loop','In')
    b.add('counter','Get Variable',Name='counter'); b.add('less','Less',B=3)
    b.connect('counter','Value','less','A').connect('less','Value','loop','Condition')
    b.add('delay','Delay',Seconds=0); b.connect('loop','Body','delay','In')
    chain(b,'delay',('increase','Set Variable',{'Name':'counter'})); b.add('add','Add',B=1)
    b.connect('counter','Value','add','A').connect('add','Value','increase','Value')
    b.add('done','Print Log',Message='done'); b.connect('sequence','Then','done','In')
    s=default_scene(); s['variables']={'counter':0.}
    result=run(native,b,s,3)
    assert result['variables']['counter']==3 and result['logs']==['done']


def test_custom_event_payload_survives_suspension(native):
    from editor.core.events import new_event
    event=new_event('Delayed message',parameters=[dict(name='Message',type='string',default='')])
    b=GraphBuilder(event_definitions=[event]); b.add('start','On Game Start')
    chain(b,'start',('send','Send Delayed message',{'Message':'captured'}))
    b.add('event','On Delayed message'); chain(b,'event',('wait','Delay',{'Seconds':0}),('log','Print Log',{}))
    b.connect('event','Message','log','Message')
    result=run(native,b,frames=1)
    assert result['logs']==['captured']


def test_retriggered_function_uses_latest_parameters_and_caller(native):
    f=new_function('Debounced echo',inputs=[dict(name='Number',type='int',default=0)],outputs=[dict(name='Result',type='int')])
    body=GraphBuilder(functions=[f],function=f['id']); body.add('entry','Function Input')
    chain(body,'entry',('wait','Retriggerable Delay',{'Seconds':0}),('return','Function Output',{}))
    body.connect('entry','Number','return','Result'); f['graph']=body.graph
    b=GraphBuilder(functions=[f])
    for i,value in enumerate([10,20]):
        b.add('start'+str(i),'On Game Start')
        chain(b,'start'+str(i),('call'+str(i),'Debounced echo',{'Number':value}),('store'+str(i),'Set Integer Variable',{'Name':'value'}))
        b.connect('call'+str(i),'Result','store'+str(i),'Value')
    result=run(native,b,frames=1)
    assert result['variables']['value']['value']==20 and not result['continuations']['tasks']
