"""Persistent execution gates through actual interpreted/generated C++ graphs."""
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.compiler import GraphError
from editor.core.document import default_scene
from editor.core.functions import new_function
from tests.test_native import native
from tests.test_physics_scene import chain,run


def pulses(label,inputs,**values):
    b=GraphBuilder(); b.add('flow',label,**values)
    for i,port in enumerate(inputs):
        nid=f'start_{i:03}'; b.add(nid,'On Game Start'); b.connect(nid,'Out','flow',port)
    return b


def test_do_once_reset_routes_and_same_node_feedback(native):
    b=pulses('Do Once',['In','In','Reset','In','In'])
    chain(b,'flow',('log','Print Log',{'Message':'fired'}))
    result=run(native,b); assert result['logs']==['fired','fired']
    assert result['flow']['states']==[dict(owner='',node='flow',count=1,flag=False)]
    # Out -> Reset terminates rather than recursively re-entering Out.
    b.connect('log','Out','flow','Reset')
    result=run(native,b); assert result['logs']==['fired']*4 and result['flow']['states'][0]['count']==0


def test_do_n_count_is_captured_per_successful_output_and_reset(native):
    b=pulses('Do N',['In']*5+['Reset']+['In']*2,N=3)
    chain(b,'flow',('log','Print Log',{'Message':'counted'}),('store','Set Integer Variable',{'Name':'sum'}))
    b.add('sum','Get Integer Variable',Name='sum'); b.add('add','Integer Add')
    b.connect('sum','Value','add','A').connect('flow','Counter','add','B').connect('add','Value','store','Value')
    s=default_scene(); s['variables']={'sum':{'type':'int','value':0}}
    result=run(native,b,s)
    assert result['logs']==['counted']*5 and result['variables']['sum']['value']==9
    assert result['flow']['states'][0]['count']==2


@pytest.mark.parametrize('closed,expected',[(False,3),(True,2)])
def test_gate_open_close_toggle_are_control_only_inputs(native,closed,expected):
    b=pulses('Gate',['In','Close','In','Open','In','Toggle','In','Toggle','In'],**{'Start Closed':closed})
    chain(b,'flow',('log','Print Log',{'Message':'open'}))
    result=run(native,b); assert result['logs']==['open']*expected
    assert result['flow']['states'][0]['flag']


def test_flip_flop_alternates_and_reset_starts_at_a(native):
    b=pulses('Flip Flop',['In']*3+['Reset']+['In']*4)
    for port in ('A','B'):
        b.add('log_'+port,'Print Log',Message=port); b.connect('flow',port,'log_'+port,'In')
        chain(b,'log_'+port,('store_'+port,'Set Boolean Variable',{'Name':'last_'+port}))
        b.connect('flow','Is A','store_'+port,'Value')
    result=run(native,b)
    assert result['logs']==['A','B','A','A','B','A','B']
    assert result['variables']['last_A']['value'] and not result['variables']['last_B']['value']
    assert result['flow']['states'][0]['flag']


def test_do_n_zero_and_dynamic_limit_do_not_restart_counter(native):
    b=pulses('Do N',['In','In','In'],N=0); chain(b,'flow',('log','Print Log',{'Message':'out'}))
    assert not run(native,b)['logs']
    # A larger limit permits more entries without resetting progress.
    b.add('limit','Get Integer Variable',Name='limit'); b.connect('limit','Value','flow','N')
    b.add('start_001a','On Game Start'); chain(b,'start_001a',('raise','Set Integer Variable',{'Name':'limit','Value':3}))
    s=default_scene(); s['variables']={'limit':{'type':'int','value':1}}
    result=run(native,b,s); assert result['logs']==['out','out'] and result['flow']['states'][0]['count']==2


def test_reset_does_not_evaluate_do_n_limit_or_escape_counter_scope(native):
    b=pulses('Do N',['Reset'])
    b.add('divide','Divide',A=1,B=0); b.add('integer','Truncate to Integer')
    b.connect('divide','Value','integer','Value').connect('integer','Value','flow','N')
    result=run(native,b); assert result['flow']['states'][0]['count']==0
    b.add('start_leak','On Game Start'); chain(b,'start_leak',('leak','Set Integer Variable',{'Name':'leak'}))
    b.connect('flow','Counter','leak','Value')
    with pytest.raises(GraphError,match='flow node output path'): b.compile()


def test_named_function_state_is_shared_per_owner_and_clones_start_fresh(native):
    f=new_function('Once per entity',inputs=[dict(name='Entity',type='entity',default='player')])
    body=GraphBuilder(functions=[f],function=f['id']); body.add('entry','Function Input')
    chain(body,'entry',('once','Do Once',{}),('log','Print Log',{'Message':'once'})); body.connect('entry','Entity','once','Owner')
    f['graph']=body.graph
    b=GraphBuilder(functions=[f]); b.add('start','On Game Start')
    chain(b,'start',('first','Once per entity',{}),('again','Once per entity',{}),('clone','Clone Entity',{}),
          ('copy','Once per entity',{'Entity':'spawned_1'}),('remove','Destroy Entity',{'Entity':'spawned_1'}))
    result=run(native,b); assert result['logs']==['once','once']
    assert result['flow']['states']==[dict(owner='player',node=str(f['id'])+'/once',count=1,flag=False)]


def test_gate_preserves_loop_continue_break_and_function_returns(native):
    b=GraphBuilder(); b.add('start','On Game Start')
    chain(b,'start',('loop','For Loop',{'Count':5}))
    b.add('gate','Do N',N=2); b.connect('loop','Body','gate','In')
    chain(b,'gate',('log','Print Log',{'Message':'loop'}),('continue','Continue Loop',{}))
    b.add('done','Print Log',Message='done'); b.connect('loop','Done','done','In')
    assert run(native,b)['logs']==['loop','loop','done']
    f=new_function('Alternating result',outputs=[dict(name='Number',type='int')])
    body=GraphBuilder(functions=[f],function=f['id']); body.add('entry','Function Input'); chain(body,'entry',('flip','Flip Flop',{}))
    for branch,value in [('A',10),('B',20)]:
        body.add(branch,'Function Output',Number=value); body.connect('flip',branch,branch,'In')
    f['graph']=body.graph; b=GraphBuilder(functions=[f]); b.add('start','On Game Start')
    chain(b,'start',('a','Alternating result',{}),('b','Alternating result',{}),('store','Set Integer Variable',{'Name':'number'}))
    b.connect('b','Number','store','Value'); assert run(native,b)['variables']['number']['value']==20


@pytest.mark.parametrize('label,values,fragment',[
    ('Do N',{'N':-1},'nonnegative'),('Do Once',{'Owner':'missing'},'entity')])
def test_bad_inputs_report_flow_node(native,label,values,fragment):
    b=pulses(label,['In'],**values)
    a,z=native(b.graph,frames=0)
    assert a.returncode==z.returncode==1 and json.loads(a.stderr)==json.loads(z.stderr)
    error=json.loads(a.stderr); assert error['node']=='flow' and fragment in error['message'].lower()


def test_flow_output_back_to_in_is_still_a_cycle():
    b=pulses('Do Once',['In']); b.connect('flow','Out','flow','In')
    with pytest.raises(GraphError,match='Execution cycle'): b.compile()


def test_map_literals_and_function_defaults_are_not_flow_instructions(native):
    data={'op':'flow','node':'payload','type':'not-a-node-type'}
    f=new_function('Store payload',inputs=[dict(name='Data',type='map<string>',default=data)])
    body=GraphBuilder(functions=[f],function=f['id']); body.add('entry','Function Input')
    chain(body,'entry',('store','Set String Map Variable',{'Name':'payload'}))
    body.connect('entry','Data','store','Value'); f['graph']=body.graph
    b=GraphBuilder(functions=[f]); b.add('start','On Game Start')
    chain(b,'start',('call','Store payload',{}),('once','Do Once',{}),('log','Print Log',{'Message':'out'}))
    result=run(native,b)
    assert result['variables']['payload']['value']==data and result['logs']==['out']
    assert result['flow']['bindings']=={'once':2007}


def test_blocked_function_path_still_requires_a_return():
    f=new_function('Bad result',outputs=[dict(name='Number',type='int')])
    body=GraphBuilder(functions=[f],function=f['id']); body.add('entry','Function Input')
    chain(body,'entry',('once','Do Once',{}),('return','Function Output',{'Number':1})); f['graph']=body.graph
    with pytest.raises(GraphError,match='Every execution path'): GraphBuilder(functions=[f]).compile()


def multi_pulses(inputs,**values):
    b=pulses('Multi Gate',inputs,**values)
    b.add('000_seed','On Game Start'); chain(b,'000_seed',('seed','Set Random Seed',{'Seed':42}))
    for i in range(8):
        b.add('log_'+str(i),'Print Log',Message=str(i)); b.connect('flow','Out '+str(i),'log_'+str(i),'In')
        chain(b,'log_'+str(i),('last_'+str(i),'Set Integer Variable',{'Name':'last'}))
        b.connect('flow','Index','last_'+str(i),'Value')
    return b


@pytest.mark.parametrize('values,expected',[
    ({'Branches':8},list(range(8))),
    ({'Branches':3,'Start Index':2},[2,0,1]),
    ({'Branches':3,'Start Index':2,'Loop':True},[2,0,1,2,0,1,2,0,1,2]),
    ({'Branches':1,'Loop':True},[0]*10)])
def test_multi_gate_order_limits_start_and_loop(native,values,expected):
    result=run(native,multi_pulses(['In']*10,**values))
    assert result['logs']==list(map(str,expected)) and result['variables']['last']['value']==expected[-1]
    assert result['random']['state']=='000000000000002a'


def test_multi_gate_random_cycles_do_not_repeat_and_seed_repeats_sequence(native):
    b=multi_pulses(['In']*10,Branches=5,Random=True,Loop=True)
    result=run(native,b); again=run(native,b)
    choices=list(map(int,result['logs']))
    assert result==again and sorted(choices[:5])==sorted(choices[5:])==list(range(5))
    assert result['random']['state']!='000000000000002a'
    forced=run(native,multi_pulses(['In']*4,Branches=3,Random=True,**{'Start Index':2}))
    assert forced['logs'][0]=='2' and sorted(forced['logs'])==['0','1','2']


def test_multi_gate_reset_ignores_controls_and_keeps_index_scoped(native):
    result=run(native,multi_pulses(['In','In','Reset','In','In'],Branches=3))
    assert result['logs']==['0','1','0','1']
    b=multi_pulses(['Reset'],Branches=0,**{'Start Index':99})
    b.add('divide','Divide',A=1,B=0); b.add('integer','Truncate to Integer')
    b.connect('divide','Value','integer','Value').connect('integer','Value','flow','Branches')
    result=run(native,b); assert result['flow']['states'][0]['multi']==dict(branches=0,used=0,next=0)
    b.add('start_leak','On Game Start'); chain(b,'start_leak',('leak','Set Integer Variable',{'Name':'leak'}))
    b.connect('flow','Index','leak','Value')
    with pytest.raises(GraphError,match='flow node output path'): b.compile()


def test_multi_gate_changing_branch_count_restarts_but_modes_preserve_used_routes(native):
    b=multi_pulses(['In']*6,Branches=2,Random=False)
    b.add('count','Get Integer Variable',Name='branches'); b.connect('count','Value','flow','Branches')
    b.add('random','Get Boolean Variable',Name='random'); b.connect('random','Value','flow','Random')
    b.add('start_001a','On Game Start'); chain(b,'start_001a',('resize','Set Integer Variable',{'Name':'branches','Value':3}))
    b.add('start_002a','On Game Start'); chain(b,'start_002a',('shuffle','Set Boolean Variable',{'Name':'random','Value':True}))
    s=default_scene(); s['variables']={'branches':{'type':'int','value':2},'random':{'type':'bool','value':False}}
    result=run(native,b,s)
    assert result['logs'][:3]==['0','1','0'] and sorted(result['logs'][3:])==['1','2']
    assert result['flow']['states'][0]['multi']['used']==7


@pytest.mark.parametrize('control,expected',[('Break Loop',['zero','done']),('Continue Loop',['zero','one','zero','one','zero','done'])])
def test_multi_gate_branches_propagate_loop_control(native,control,expected):
    b=GraphBuilder(); b.add('start','On Game Start'); chain(b,'start',('loop','For Loop',{'Count':5}))
    b.add('gate','Multi Gate',Branches=2,Loop=True); b.connect('loop','Body','gate','In')
    b.add('zero','Print Log',Message='zero'); b.connect('gate','Out 0','zero','In'); chain(b,'zero',('control',control,{}))
    b.add('one','Print Log',Message='one'); b.connect('gate','Out 1','one','In')
    b.add('done','Print Log',Message='done'); b.connect('loop','Done','done','In')
    assert run(native,b)['logs']==expected


def test_multi_gate_action_function_owners_and_clone_lifetime(native):
    f=new_function('Next owned route',inputs=[dict(name='Entity',type='entity',default='player')])
    body=GraphBuilder(functions=[f],function=f['id']); body.add('entry','Function Input')
    chain(body,'entry',('route','Multi Gate',{'Branches':3,'Loop':True})); body.connect('entry','Entity','route','Owner')
    for i in range(3):
        body.add('log'+str(i),'Print Log',Message=str(i)); body.connect('route','Out '+str(i),'log'+str(i),'In')
    f['graph']=body.graph; b=GraphBuilder(functions=[f]); b.add('start','On Game Start')
    chain(b,'start',('first','Next owned route',{}),('again','Next owned route',{}),('clone','Clone Entity',{}),
          ('copy','Next owned route',{'Entity':'spawned_1'}),('destroy','Destroy Entity',{'Entity':'spawned_1'}))
    result=run(native,b)
    assert result['logs']==['0','1','0'] and len(result['flow']['states'])==1
    assert result['flow']['states'][0]['owner']=='player' and result['flow']['states'][0]['multi']==dict(branches=3,used=3,next=2)


@pytest.mark.parametrize('values',[
    {'Branches':0},{'Branches':9},{'Branches':3,'Start Index':3},{'Start Index':-2}])
def test_multi_gate_invalid_controls_report_own_node(native,values):
    a,z=native(multi_pulses(['In'],**values).graph,frames=0)
    assert a.returncode==z.returncode==1 and json.loads(a.stderr)==json.loads(z.stderr)
    error=json.loads(a.stderr); assert error['node']=='flow' and 'Multi Gate' in error['message']
