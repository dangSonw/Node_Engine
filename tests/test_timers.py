"""Timer semantics exercised through both actual C++ execution paths."""
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.compiler import GraphError
from editor.core.document import default_scene
from editor.core.functions import new_function
from tests.test_native import native


def pair(native, b, frames=1, dt=.1, **kwargs):
    a, c = native(b.graph, frames=frames, extra=['--dt', str(dt), *kwargs.pop('extra', [])], **kwargs)
    assert a.returncode == c.returncode == 0, a.stderr+c.stderr
    state = json.loads(a.stdout)
    assert state == json.loads(c.stdout)
    return state


def test_timer_owner_filter_payload_and_repeat_catchup(native):
    b = GraphBuilder()
    for nid, name, values in [
        ('start','On Game Start',{}),
        ('player','Start Timer',{'Name':'pulse','Seconds':.1,'Repeat':True,'Owner':'player'}),
        ('scene','Start Timer',{'Name':'pulse','Seconds':0}),
        ('wrong','Start Timer',{'Name':'ignored','Seconds':.1,'Owner':'player'}),
        ('handler','On Timer Finished',{'Filter':'pulse','Receiver':'player'}),
        ('rotate','Rotate',{'Degrees':[0,10,0]}),
        ('name','Print Log',{}), ('self','Get Self',{}),
        ('same','Compare References',{}), ('check','Assert',{}),
        ('scene_handler','On Timer Finished',{'Filter':'pulse'}),
        ('scene_log','Print Log',{'Message':'scene'}),
    ]:
        b.add(nid,name,**values)
    for edge in [('start','Out','player','In'),('player','Out','scene','In'),('scene','Out','wrong','In'),
                 ('handler','Out','rotate','In'),('handler','Owner','rotate','Entity'),
                 ('rotate','Out','name','In'),('handler','Name','name','Message'),
                 ('self','Entity','same','A'),('handler','Owner','same','B'),
                 ('name','Out','check','In'),('same','Value','check','Condition'),
                 ('scene_handler','Out','scene_log','In')]:
        b.connect(*edge)
    state = pair(native,b,frames=6,dt=.05)
    assert state['logs'] == ['scene','pulse','pulse','pulse']
    assert state['entities']['player']['rotation'] == [0,30,0]
    assert len(state['timers']) == 1
    assert state['timers'][0]['remaining'] == pytest.approx(.1)


@pytest.mark.parametrize('unscaled',[False,True])
def test_pause_resume_preserves_remaining_and_idempotence(native,unscaled):
    b=GraphBuilder()
    for nid,name,values in [
        ('start','On Game Start',{}),('timer','Start Timer',{'Seconds':1,'Unscaled':unscaled}),
        ('pause','Pause Timer',{}),('pause_again','Pause Timer',{}),
        ('update','On Update',{}),('frame','Get Frame Count',{}),
        ('equal','Nearly Equal',{'B':2}),('branch','Branch',{}),
        ('resume','Resume Timer',{}),('resume_again','Resume Timer',{}),
        ('handler','On Timer Finished',{}),('log','Print Log',{'Message':'done'}),
        ('paused','Is Timer Paused',{}),('assert','Assert',{}),
        ('remaining','Get Timer Remaining',{}),('save','Set Variable',{})]:
        b.add(nid,name,**values)
    for e in [('start','Out','timer','In'),('timer','Out','pause','In'),('pause','Out','pause_again','In'),
              ('pause_again','Out','assert','In'),('paused','Value','assert','Condition'),
              ('update','Out','branch','In'),('frame','Value','equal','A'),('equal','Value','branch','Condition'),
              ('branch','True','resume','In'),('resume','Out','resume_again','In'),
              ('resume_again','Out','save','In'),('remaining','Value','save','Value'),
              ('handler','Out','log','In')]: b.connect(*e)
    state=pair(native,b,frames=4,dt=.25)
    assert state['logs']==[]
    assert state['variables']['score']==1
    assert state['timers'][0]['remaining']==.5
    assert not state['timers'][0]['paused']
    completed=pair(native,b,frames=6,dt=.25)
    assert completed['logs']==['done'] and completed['timers']==[]


def test_deadline_order_stop_pending_repeat_and_listener_order(native):
    b=GraphBuilder()
    for nid,name,values in [
        ('start','On Game Start',{}),('late','Start Timer',{'Name':'late','Seconds':.2,'Repeat':True}),
        ('early','Start Timer',{'Name':'early','Seconds':.1,'Repeat':True}),
        ('z_handler','On Timer Finished',{}),('z_log','Print Log',{'Message':'z'}),
        ('a_handler','On Timer Finished',{'Filter':'early'}),('stop','Stop Timer',{'Name':'late'}),
        ('a_log','Print Log',{'Message':'a'})]: b.add(nid,name,**values)
    for e in [('start','Out','late','In'),('late','Out','early','In'),('a_handler','Out','stop','In'),
              ('stop','Out','a_log','In'),('z_handler','Out','z_log','In')]: b.connect(*e)
    state=pair(native,b,dt=.5)
    assert state['logs']==['a','z']*5
    assert [t['name'] for t in state['timers']]==['early']


@pytest.mark.parametrize('unscaled',[False,True])
def test_zero_timer_restart_deferred_and_one_shot_inactive_in_handler(native,unscaled):
    b=GraphBuilder()
    for nid,name,values in [('start','On Game Start',{}),('timer','Start Timer',{'Seconds':0}),
        ('handler','On Timer Finished',{}),('exists','Timer Exists',{}),('not','NOT',{}),
        ('assert','Assert',{}),('log','Print Log',{'Message':'tick'}),('restart','Start Timer',{'Seconds':0})]:
        b.add(nid,name,**values)
    for e in [('start','Out','timer','In'),('handler','Out','assert','In'),('exists','Value','not','Value'),
        ('not','Value','assert','Condition'),('assert','Out','log','In'),('log','Out','restart','In')]: b.connect(*e)
    for node in b.graph['nodes']:
        if node['id'] in ('timer','restart'): node['values']['Unscaled']=unscaled
    assert pair(native,b,frames=0)['logs']==[]
    state=pair(native,b,frames=3,dt=0)
    assert state['logs']==['tick']*3
    assert len(state['timers'])==1


def test_restart_replaces_pending_deadline_and_owner_scope(native):
    b=GraphBuilder()
    for nid,name,values in [('start','On Game Start',{}),('old','Start Timer',{'Seconds':.1}),
        ('replace','Start Timer',{'Seconds':1}),('entity','Start Timer',{'Seconds':.1,'Owner':'player'}),
        ('stop','Stop Timer',{}),('handler','On Timer Finished',{'Receiver':'player'}),
        ('log','Print Log',{'Message':'entity'})]: b.add(nid,name,**values)
    for e in [('start','Out','old','In'),('old','Out','replace','In'),('replace','Out','entity','In'),
              ('entity','Out','stop','In'),('handler','Out','log','In')]: b.connect(*e)
    state=pair(native,b,dt=.1)
    assert state['logs']==['entity'] and state['timers']==[]


@pytest.mark.parametrize('values,needle', [({'Seconds':-1},'duration'),({'Seconds':0,'Repeat':True},'duration'),
    ({'Name':'\0bad'},'name'),({'Name':' '*5},'name'),({'Owner':'missing'},'Missing entity')])
def test_timer_runtime_errors_report_origin(native,values,needle):
    b=GraphBuilder(); b.add('start','On Game Start'); b.add('invalid','Start Timer',**values)
    b.connect('start','Out','invalid','In')
    a,c=native(b.graph,frames=1)
    assert a.returncode==c.returncode==1
    error=json.loads(a.stderr)
    assert error==json.loads(c.stderr)
    assert error['node']=='invalid' and needle in error['message']


def test_timer_storm_is_bounded_without_listeners(native):
    b=GraphBuilder(); b.add('start','On Game Start'); b.add('storm','Start Timer',Seconds=1e-9,Repeat=True)
    b.connect('start','Out','storm','In')
    a,c=native(b.graph,frames=1,extra=['--budget','100'])
    assert a.returncode==c.returncode==1
    assert json.loads(a.stderr)==json.loads(c.stderr)
    assert json.loads(a.stderr)['node']=='storm'
    assert 'budget' in json.loads(a.stderr)['message']


def test_callback_failure_stays_in_cpp_error_channel(native):
    b=GraphBuilder()
    b.add('start','On Game Start'); b.add('timer','Start Timer',Seconds=0)
    b.add('handler','On Timer Finished'); b.add('bad_handler','Assert',Condition=False,Message='timer failure')
    b.connect('start','Out','timer','In'); b.connect('handler','Out','bad_handler','In')
    a,c=native(b.graph,frames=1)
    assert a.returncode==c.returncode==1
    assert json.loads(a.stderr)==json.loads(c.stderr)=={'event':'node_error','node':'bad_handler','message':'timer failure'}


def test_function_can_schedule_timer_and_receive_callback_parameters(native):
    f=new_function('Schedule',[{'name':'Label','type':'string'}],[])
    f['id']=1000001
    inner=GraphBuilder('Schedule',[f],f['id'])
    inner.add('entry','Function Input'); inner.add('timer','Start Timer',Seconds=0)
    inner.connect('entry','Out','timer','In'); inner.connect('entry','Label','timer','Name')
    f['graph']=inner.graph
    b=GraphBuilder(functions=[f]); b.add('start','On Game Start'); b.add('call','Schedule',Label='Xin chào')
    b.add('handler','On Timer Finished'); b.add('log','Print Log')
    b.connect('start','Out','call','In'); b.connect('handler','Out','log','In'); b.connect('handler','Name','log','Message')
    state=pair(native,b)
    assert state['logs']==['Xin chào'] and state['timers']==[]


def test_timer_payload_cannot_escape_handler_and_listener_configuration_is_static():
    b=GraphBuilder(); b.add('handler','On Timer Finished'); b.add('update','On Update'); b.add('log','Print Log')
    b.connect('update','Out','log','In'); b.connect('handler','Name','log','Message')
    with pytest.raises(GraphError,match='inside that timer event handler'): b.compile()
    b=GraphBuilder(); b.add('handler','On Timer Finished'); b.add('name','String')
    b.connect('name','Value','handler','Filter')
    with pytest.raises(GraphError,match='constant'): b.compile()
    b=GraphBuilder(); b.add('handler','On Timer Finished',Receiver='missing')
    with pytest.raises(GraphError,match='does not exist'): b.compile()


def test_timer_handlers_are_sorted_and_codegen_is_deterministic():
    from editor.core.codegen import CppEmitter
    b=GraphBuilder(); b.add('z','On Timer Finished'); b.add('a','On Timer Finished')
    ir=b.compile(default_scene())
    assert [h['node'] for h in ir['events']['timers']]==['a','z']
    first=CppEmitter().generate(ir)
    b.graph['nodes'].reverse()
    assert CppEmitter().generate(b.compile())==first
