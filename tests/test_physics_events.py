"""Collision delivery, scoped payloads and mutation during real native simulation."""
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.codegen import CppEmitter
from editor.core.compiler import GraphError
from editor.core.document import default_scene
from editor.core.events import new_event
from tests.test_native import native

EVENTS=[f'On {kind} {phase}' for kind in ('Collision','Trigger') for phase in ('Enter','Stay','Exit')]


def action(b,source,nid,label,port='Out',**values):
    b.add(nid,label,**values); b.connect(source,port,nid,'In'); return nid


def setup(sensor=False,definitions=(),character=False):
    scene=default_scene(); scene['entities'][0]['position']=[0,.84 if character else .49,0]
    scene['variables'].update(step=0.,recreated={'type':'bool','value':False})
    scene['entities'].append(dict(id='floor',name='Floor',position=[0,-.5,0],rotation=[0,0,0],scale=[1,1,1]))
    b=GraphBuilder(event_definitions=definitions); b.add('start','On Game Start')
    end=action(b,'start','floor','Create Box Rigid Body',Entity='floor',Motion='static',Sensor=sensor,**{'Half Extents':[5,.5,5]})
    action(b,end,'body','Create Character' if character else 'Create Box Rigid Body')
    return b,scene


def run(native,b,scene,frames):
    a,z=native(b.graph,scene=scene,frames=frames)
    assert a.returncode==z.returncode==0,a.stderr+z.stderr
    result=json.loads(a.stdout); assert result==json.loads(z.stdout)
    assert result['events']['pending']==0
    return result


@pytest.mark.parametrize('label',EVENTS)
def test_contact_payload_is_scoped_and_receiver_is_constant(label):
    b=GraphBuilder(event_definitions=[new_event('Unrelated')])
    b.add('event',label,Receiver='player')
    action(b,'event','normal','Set Vector3 Variable',Name='normal')
    b.connect('event','Normal','normal','Value')
    ir=b.compile(); assert ir['events']['physics'][0]['owner']=='player'
    assert 'rt::BindPhysicsEvent' in CppEmitter().generate(ir)
    b.add('start','On Game Start'); action(b,'start','leak','Set Vector3 Variable',Name='leak')
    b.connect('event','Point','leak','Value')
    with pytest.raises(GraphError,match='inside that physics event handler'): b.compile()
    b.graph['links'].pop(); b.add('self','Get Self'); b.connect('self','Entity','event','Receiver')
    with pytest.raises(GraphError,match='constant in the Inspector'): b.compile()


def test_contact_receiver_must_exist():
    b=GraphBuilder(); b.add('event','On Trigger Enter',Receiver='missing')
    with pytest.raises(GraphError,match='receiver entity does not exist'): b.compile()


@pytest.mark.parametrize('sensor',[False,True])
@pytest.mark.parametrize('character',[False,True])
def test_enter_stay_exit_and_oriented_payloads(native,sensor,character):
    b,scene=setup(sensor,character=character)
    b.add('fixed','On Fixed Update'); action(b,'fixed','increment','Set Variable',Name='step')
    b.add('count','Get Variable',Name='step'); b.add('add','Add',B=1)
    b.connect('count','Value','add','A').connect('add','Value','increment','Value')
    action(b,'increment','third','Branch'); b.add('equal','Nearly Equal',B=3)
    b.connect('count','Value','equal','A').connect('equal','Value','third','Condition')
    action(b,'third','away','Set Position',port='True',Value=[0,5,0])
    kind='Trigger' if sensor else 'Collision'
    for phase in ('Enter','Stay','Exit'):
        for prefix,owner in [('global',''),('floor','floor'),('player','player')]:
            nid=prefix+phase; b.add(nid,f'On {kind} {phase}',Receiver=owner)
            end=action(b,nid,nid+'_log','Print Log',Message=nid)
            for field in ('Entity','Other','Point','Normal'):
                end=action(b,end,nid+'_'+field,'Set Entity Variable' if field in ('Entity','Other') else 'Set Vector3 Variable',Name=prefix+'_'+field)
                b.connect(nid,field,end,'Value')
    result=run(native,b,scene,4)
    assert result['logs']==[prefix+phase for phase in ('Enter','Stay','Exit') for prefix in ('global','floor','player')]
    values=result['variables']
    assert values['global_Entity']['value']==values['floor_Entity']['value']=='floor'
    assert values['global_Other']['value']==values['floor_Other']['value']=='player'
    assert values['player_Entity']['value']=='player' and values['player_Other']['value']=='floor'
    assert values['floor_Normal']['value'][1]>.9 and values['player_Normal']['value'][1]<-.9
    assert values['floor_Point']==values['player_Point']


@pytest.mark.parametrize('character',[False,True])
def test_destroying_both_entities_in_callback_cancels_owners_but_emits_final_exit(native,character):
    b,scene=setup(True,character=character)
    b.add('enter','On Trigger Enter')
    last=action(b,'enter','destroy_player','Destroy Entity')
    action(b,last,'destroy_floor','Destroy Entity',Entity='floor')
    for owner in ('floor','player'):
        b.add(owner+'_event','On Trigger Enter',Receiver=owner)
        action(b,owner+'_event',owner+'_log','Print Log',Message='must not run')
    b.add('exit','On Trigger Exit'); action(b,'exit','exited','Print Log',Message='exit')
    result=run(native,b,scene,3)
    assert result['entities']=={} and result['physics']['bodies']=={}
    assert result['logs']==['exit'] and result['physics']['ticks']==3


@pytest.mark.parametrize('character',[False,True])
def test_remove_and_recreate_body_preserves_exit_before_enter_and_custom_queue(native,character):
    event=new_event('Ping'); b,scene=setup(True,[event],character=character)
    b.add('a_enter','On Trigger Enter',Receiver='player')
    last=action(b,'a_enter','log_enter','Print Log',Message='enter')
    last=action(b,last,'send','Send Ping')
    action(b,last,'once','Branch'); b.add('done','Get Boolean Variable',Name='recreated')
    b.connect('done','Value','once','Condition')
    last=action(b,'once','remove','Remove Rigid Body',port='False')
    last=action(b,last,'recreate','Create Character' if character else 'Create Box Rigid Body')
    action(b,last,'mark','Set Boolean Variable',Name='recreated',Value=True)
    for nid,label,message in [('exit','On Trigger Exit','exit'),('ping','On Ping','ping')]:
        b.add(nid,label); action(b,nid,nid+'_log','Print Log',Message=message)
    result=run(native,b,scene,3)
    assert result['logs']==['enter','ping','exit','enter','ping']


@pytest.mark.parametrize('character',[False,True])
def test_deactivating_receiver_suppresses_remaining_owner_handlers(native,character):
    b,scene=setup(True,character=character)
    b.add('a_enter','On Trigger Enter',Receiver='player')
    action(b,'a_enter','disable','Set Entity Active',Active=False)
    b.add('z_enter','On Trigger Enter',Receiver='player')
    action(b,'z_enter','wrong','Print Log',Message='must not run')
    b.add('exit','On Trigger Exit'); action(b,'exit','exit_log','Print Log',Message='exit')
    result=run(native,b,scene,3)
    assert result['logs']==['exit']
    assert not result['physics']['bodies']['player']['enabled']


@pytest.mark.parametrize('character',[False,True])
def test_contact_callback_budget_failure_reports_the_original_node(native,character):
    b,scene=setup(True,character=character); b.add('event','On Trigger Enter')
    action(b,'event','handler_loop','While Loop',Condition=True)
    a,z=native(b.graph,scene=scene,frames=1,extra=['--budget','80'])
    assert a.returncode==z.returncode==1
    error=json.loads(a.stderr); assert error==json.loads(z.stderr)
    assert error['node']=='handler_loop' and 'budget' in error['message']
