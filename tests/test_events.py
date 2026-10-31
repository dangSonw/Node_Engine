"""Project event authoring and real C++ preview/export equivalence."""
from copy import deepcopy
import json
import pytest
from editor.core.events import new_event, signatures, node_id
from editor.core.builder import GraphBuilder
from editor.core.compiler import compile_graph, GraphError
from editor.core.codegen import CppEmitter
from editor.core.registry import Registry
from editor.core.functions import new_function
from editor.core.data_types import TYPES, declaration
from editor.core.document import default_scene
from tests.test_native import native


def event(name='Ping', parameters=(), eid=100001):
    value=new_event(name,parameters)
    value['id']=eid
    return value


def pair(native,b,frames=0,**kwargs):
    a,c=native(b.graph,frames=frames,**kwargs)
    assert a.returncode==c.returncode==0,a.stderr+c.stderr
    state=json.loads(a.stdout)
    assert state==json.loads(c.stdout)
    assert state['events']['pending']==0
    return state


def test_all_event_payload_types_are_exact_values(native):
    scalars={'float':1.25,'int':2**60+13,'bool':True,'string':'Xin chào\0Z',
             'vec3':[1.5,-2,3],'vec2':[4.5,-6.],
             'vec4':[1.,2.,3.,4.],'quat':[0.,0.,.5,.5],
             'mat4':[1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,2.,3.,4.,1.],
             'entity':'player'}
    values={}
    for t in TYPES:
        element=t[t.index('<')+1:-1] if '<' in t else t
        values[t]=([scalars[element]] if t.startswith(('array<','set<'))
                    else {'κ\0':scalars[element]} if t.startswith('map<') else scalars[t])
    # Event signatures have a 32-port limit; exercise every type in two events.
    groups=[list(enumerate(TYPES))[offset:offset+20] for offset in range(0,len(TYPES),20)]
    definitions=[event(f'Payload{g}',[{'name':f'P{i}','type':t} for i,t in group],100001+g)
                 for g,group in enumerate(groups)]
    b=GraphBuilder(event_definitions=definitions)
    b.add('start','On Game Start'); previous_send='start'
    for g,group in enumerate(groups):
        sender=f'send{g}'; handler=f'handler{g}'
        b.add(sender,f'Send Payload{g}',**{f'P{i}':values[t] for i,t in group})
        b.add(handler,f'On Payload{g}')
        b.connect(previous_send,'Out',sender,'In'); previous_send=sender
        previous=handler
        for i,t in group:
            setter=next(s for s in b.registry.nodes.values() if s.variable_type==t and s.variable_access=='write' and not s.variable_scope)
            b.add(f'save{i}',setter.name,Name=f'v{i}')
            b.connect(previous,'Out',f'save{i}','In'); b.connect(handler,f'P{i}',f'save{i}','Value')
            previous=f'save{i}'
    state=pair(native,b)
    for i,(t,value) in enumerate(values.items()):
        assert state['variables'][f'v{i}']==declaration(t,value)


def test_target_broadcast_sender_receiver_and_deterministic_listener_order(native):
    b=GraphBuilder(event_definitions=[event('Ping',[{'name':'Message','type':'string'}])])
    for nid,name,values in [('start','On Game Start',{}),('send','Send Ping',{'Recipient':'player','Sender':'player','Message':'target'}),
        ('broadcast','Broadcast Ping',{'Sender':'player','Message':'all'}),('z_player','On Ping',{'Receiver':'player'}),
        ('a_player','On Ping',{'Receiver':'player'}),('scene','On Ping',{}),
        ('zlog','Print Log',{'Message':'z'}),('alog','Print Log',{}),('slog','Print Log',{'Message':'scene'}),
        ('self','Get Self',{}),('same','Compare References',{}),('sender','Compare References',{'B':'player'}),
        ('checkself','Assert',{}),('checksender','Assert',{})]: b.add(nid,name,**values)
    for edge in [('start','Out','send','In'),('send','Out','broadcast','In'),('z_player','Out','zlog','In'),
        ('a_player','Out','alog','In'),('a_player','Message','alog','Message'),('scene','Out','slog','In'),
        ('alog','Out','checkself','In'),('checkself','Out','checksender','In'),
        ('self','Entity','same','A'),('a_player','Receiver','same','B'),('same','Value','checkself','Condition'),
        ('a_player','Sender','sender','A'),('sender','Value','checksender','Condition')]: b.connect(*edge)
    state=pair(native,b)
    assert state['logs']==['target','z','scene','all','z']


def test_subscriptions_snapshot_rejects_stale_envelopes_after_resubscribe(native):
    b=GraphBuilder(event_definitions=[event('Ping',[{'name':'Message','type':'string'}])])
    b.add('start','On Game Start')
    previous='start'
    for nid,name,values in [('drop','Send Ping',{'Message':'disabled'}),('sub','Subscribe Ping',{}),
        ('old','Send Ping',{'Message':'stale'}),('unsub','Unsubscribe Ping',{}),('resub','Subscribe Ping',{}),
        ('sub_again','Subscribe Ping',{}),('fresh','Send Ping',{'Message':'fresh'})]:
        b.add(nid,name,**values); b.connect(previous,'Out',nid,'In'); previous=nid
    b.add('handler','On Ping',InitiallySubscribed=False); b.add('log','Print Log')
    b.connect('handler','Out','log','In'); b.connect('handler','Message','log','Message')
    state=pair(native,b)
    assert state['logs']==['fresh']
    assert state['events']['subscriptions']==[{'event':100001,'receiver':'','enabled':True}]


def test_payload_is_captured_before_variable_changes(native):
    b=GraphBuilder(event_definitions=[event('Copy',[{'name':'Items','type':'array<int>'}])])
    for nid,name,values in [('start','On Game Start',{}),('set','Set Integer Array Variable',{'Name':'items','Value':[2**60+1]}),
        ('get','Get Integer Array Variable',{'Name':'items'}),('send','Send Copy',{}),
        ('edit','Set Integer Array Variable',{'Name':'items','Value':[7]}),('handler','On Copy',{}),
        ('save','Set Integer Array Variable',{'Name':'received'})]: b.add(nid,name,**values)
    for e in [('start','Out','set','In'),('set','Out','send','In'),('send','Out','edit','In'),('get','Value','send','Items'),
              ('handler','Out','save','In'),('handler','Items','save','Value')]: b.connect(*e)
    state=pair(native,b)
    assert state['variables']['items']==declaration('array<int>',[7])
    assert state['variables']['received']==declaration('array<int>',[2**60+1])


def test_event_fifo_and_timer_phase(native):
    definitions=[event('A'),event('B',eid=100002)]
    b=GraphBuilder(event_definitions=definitions)
    for nid,name,values in [('start','On Game Start',{}),('a','Send A',{}),('b','Send B',{}),
        ('timer','Start Timer',{'Seconds':0}),('a_handler','On A',{}),('alog','Print Log',{'Message':'A'}),
        ('nested','Send B',{}),('blog','Print Log',{'Message':'B'}),('b_handler','On B',{}),
        ('timer_handler','On Timer Finished',{}),('timer_send','Send A',{}),('update','On Update',{}),
        ('update_log','Print Log',{'Message':'update'})]: b.add(nid,name,**values)
    for e in [('start','Out','a','In'),('a','Out','b','In'),('b','Out','timer','In'),
        ('a_handler','Out','alog','In'),('alog','Out','nested','In'),('b_handler','Out','blog','In'),
        ('timer_handler','Out','timer_send','In'),('update','Out','update_log','In')]: b.connect(*e)
    assert pair(native,b,frames=1)['logs']==['A','B','B','update','A','B']


def test_unsubscribe_in_first_listener_finishes_current_delivery_only(native):
    b=GraphBuilder(event_definitions=[event()])
    for nid,name,values in [('start','On Game Start',{}),('send','Send Ping',{}),('again','Send Ping',{}),
        ('a','On Ping',{}),('unsubscribe','Unsubscribe Ping',{}),('alog','Print Log',{'Message':'a'}),
        ('z','On Ping',{}),('zlog','Print Log',{'Message':'z'})]: b.add(nid,name,**values)
    for e in [('start','Out','send','In'),('send','Out','again','In'),('a','Out','unsubscribe','In'),
        ('unsubscribe','Out','alog','In'),('z','Out','zlog','In')]: b.connect(*e)
    assert pair(native,b)['logs']==['a','z']


def test_event_storm_and_queue_capacity_are_bounded(native):
    for cycle in (False,True):
        b=GraphBuilder(event_definitions=[event()])
        b.add('start','On Game Start'); b.add('send','Send Ping'); b.add('handler','On Ping')
        if cycle:
            b.add('again','Send Ping'); b.connect('start','Out','send','In'); b.connect('handler','Out','again','In')
            extra=['--budget','100']
        else:
            b.add('loop','For Loop',Count=4097); b.connect('start','Out','loop','In'); b.connect('loop','Body','send','In')
            extra=[]
        a,c=native(b.graph,frames=0,extra=extra)
        assert a.returncode==c.returncode==1
        error=json.loads(a.stderr)
        assert error==json.loads(c.stderr)
        assert ('budget' if cycle else '4096') in error['message']
        assert error['node'] in ('send','handler','again')


@pytest.mark.parametrize('limit',['payload','queue'])
def test_event_storage_limits_fail_at_the_sender(native,limit):
    # Build large payloads during execution so this also exercises value copying
    # and storage checks without embedding megabytes into generated source code.
    definition=event('Large',[{'name':'Items','type':'array<string>'}])
    b=GraphBuilder(event_definitions=[definition])
    for nid,name,values in [('start','On Game Start',{}),
        ('seed','Set String Variable',{'Name':'chunk','Value':'x'*4096}),
        ('double','For Loop',{'Count':8}),('chunk','Get String Variable',{'Name':'chunk'}),
        ('concat','Concat Strings',{}),('grow','Set String Variable',{'Name':'chunk'}),
        ('empty','Set String Array Variable',{'Name':'items','Value':[]}),
        ('fill','For Loop',{'Count':17 if limit=='payload' else 1}),
        ('items','Get String Array Variable',{'Name':'items'}),('append','Append String Item',{}),
        ('save','Set String Array Variable',{'Name':'items'}),('repeat','For Loop',{'Count':1 if limit=='payload' else 65}),
        ('send','Send Large',{}),('handler','On Large',{})]: b.add(nid,name,**values)
    for e in [('start','Out','seed','In'),('seed','Out','double','In'),('double','Body','grow','In'),
        ('chunk','Value','concat','A'),('chunk','Value','concat','B'),('concat','Value','grow','Value'),
        ('double','Done','empty','In'),('empty','Out','fill','In'),('fill','Body','save','In'),
        ('items','Value','append','Array'),('chunk','Value','append','Item'),('append','Value','save','Value'),
        ('fill','Done','repeat','In'),('repeat','Body','send','In'),('items','Value','send','Items')]: b.connect(*e)
    a,c=native(b.graph,frames=0)
    assert a.returncode==c.returncode==1
    error=json.loads(a.stderr)
    assert error==json.loads(c.stderr)
    assert ('16 MiB' if limit=='payload' else '64 MiB') in error['message']
    assert error['node']=='send'


def test_action_function_emits_event_and_event_locals_survive_nested_calls(native):
    definition=event('Result',[{'name':'Number','type':'int'}])
    emit=new_function('Publish',[{'name':'Number','type':'int'}],[]); emit['id']=1000001
    consume=new_function('Double',[{'name':'Number','type':'int'}],[{'name':'Result','type':'int'}]); consume['id']=1000002
    definitions=[emit,consume]
    b=GraphBuilder(functions=definitions,function=emit['id'],event_definitions=[definition])
    b.add('entry','Function Input'); b.add('send','Send Result')
    b.connect('entry','Out','send','In'); b.connect('entry','Number','send','Number'); emit['graph']=b.graph
    b=GraphBuilder(functions=definitions,function=consume['id'],event_definitions=[definition])
    b.add('entry','Function Input'); b.add('twice','Integer Multiply',B=2); b.add('return','Function Output')
    b.connect('entry','Out','return','In'); b.connect('entry','Number','twice','A'); b.connect('twice','Value','return','Result'); consume['graph']=b.graph
    b=GraphBuilder(functions=definitions,event_definitions=[definition])
    for nid,name,values in [('start','On Game Start',{}),('publish','Publish',{'Number':21}),('handler','On Result',{}),
        ('call','Double',{}),('save','Set Integer Variable',{'Name':'double'}),('original','Set Integer Variable',{'Name':'original'})]: b.add(nid,name,**values)
    for e in [('start','Out','publish','In'),('handler','Out','call','In'),('handler','Number','call','Number'),
        ('call','Out','save','In'),('call','Result','save','Value'),('save','Out','original','In'),('handler','Number','original','Value')]: b.connect(*e)
    state=pair(native,b)
    assert state['variables']['double']==declaration('int',42)
    assert state['variables']['original']==declaration('int',21)


@pytest.mark.parametrize('values',[{'Recipient':'missing'},{'Sender':'missing'}])
def test_invalid_event_entities_report_send_node(native,values):
    b=GraphBuilder(event_definitions=[event()]); b.add('start','On Game Start'); b.add('bad','Send Ping',**values)
    b.connect('start','Out','bad','In')
    a,c=native(b.graph,frames=0)
    assert a.returncode==c.returncode==1
    assert json.loads(a.stderr)==json.loads(c.stderr)
    assert json.loads(a.stderr)['node']=='bad'


def test_unhandled_send_is_a_noop_and_unbound_subscription_is_error(native):
    b=GraphBuilder(event_definitions=[event()]); b.add('start','On Game Start'); b.add('send','Send Ping')
    b.connect('start','Out','send','In')
    assert pair(native,b)['events']=={'pending':0,'subscriptions':[]}
    b.add('bad','Subscribe Ping'); b.connect('send','Out','bad','In')
    a,c=native(b.graph,frames=0)
    assert a.returncode==c.returncode==1
    assert json.loads(a.stderr)==json.loads(c.stderr)
    assert 'No handler' in json.loads(a.stderr)['message']


@pytest.mark.parametrize('mutation', ['id','name','duplicate','type','default','reserved','malformed','ports'])
def test_event_signature_validation(mutation):
    definitions=[event(parameters=[{'name':'Count','type':'int'}])]
    if mutation=='id': definitions[0]['id']=True
    elif mutation=='name': definitions[0]['name']=' '
    elif mutation=='duplicate': definitions.append(deepcopy(definitions[0]))
    elif mutation=='type': definitions[0]['parameters'][0]['type']=[]
    elif mutation=='default': definitions[0]['parameters'][0]['default']=1.5
    elif mutation=='reserved': definitions[0]['parameters'][0]['name']='Sender'
    elif mutation=='malformed': definitions.append(None)
    elif mutation=='ports': definitions[0]['parameters']=[{}]*33
    with pytest.raises(ValueError): signatures(definitions)


def test_event_scope_static_receiver_and_initial_subscription_validation():
    definition=event(parameters=[{'name':'Number','type':'int'}])
    b=GraphBuilder(event_definitions=[definition]); b.add('handler','On Ping'); b.add('start','On Game Start'); b.add('set','Set Integer Variable')
    b.connect('start','Out','set','In'); b.connect('handler','Number','set','Value')
    with pytest.raises(GraphError,match='inside that custom event handler'): b.compile()
    b=GraphBuilder(event_definitions=[definition]); b.add('handler','On Ping',Receiver='missing')
    with pytest.raises(GraphError,match='does not exist'): b.compile()
    b=GraphBuilder(event_definitions=[definition]); b.add('a','On Ping'); b.add('b','On Ping',InitiallySubscribed=False)
    with pytest.raises(GraphError,match='agree'): b.compile()
    b=GraphBuilder(event_definitions=[definition]); b.add('handler','On Ping'); b.add('owner','Entity Reference')
    b.connect('owner','Entity','handler','Receiver')
    with pytest.raises(GraphError,match='constant'): b.compile()


def test_event_handlers_and_side_effects_cannot_enter_pure_functions():
    definition=event()
    function=new_function('Pure',[],[{'name':'Result','type':'float'}],pure=True)
    for name,message in [('On Ping','Lifecycle events belong'),('Send Ping','Pure functions can only')]:
        b=GraphBuilder(functions=[function],function=function['id'],event_definitions=[definition])
        b.add('entry','Function Input'); b.add('return','Function Output'); b.add('invalid',name)
        function['graph']=b.graph
        with pytest.raises(GraphError,match=message):
            GraphBuilder(functions=[function],event_definitions=[definition]).compile()


def test_rename_preserves_ids_and_registry_does_not_leak_other_projects():
    builtin_ids=set(Registry().nodes)
    definition=event()
    b=GraphBuilder(event_definitions=[definition]); b.add('start','On Game Start'); b.add('send','Send Ping'); b.add('handler','On Ping')
    b.connect('start','Out','send','In')
    definition['name']='Renamed'
    ir=b.compile()
    assert ir['events']['start'][0]['event']==100001
    assert 'Send Renamed' in CppEmitter().generate(ir)
    stale=deepcopy(b.graph); del stale['event_definitions']
    with pytest.raises(GraphError,match='Unavailable'): compile_graph(stale,registry=b.registry)
    fresh=GraphBuilder(event_definitions=[event('Other',eid=100002)])
    assert node_id(100001,'send') not in fresh.registry.nodes
    assert set(Registry().nodes)==builtin_ids


def test_codegen_reuse_clears_previous_event_definitions():
    emitter=CppEmitter()
    b=GraphBuilder(event_definitions=[event()]); b.add('handler','On Ping')
    emitter.generate(b.compile())
    plain=GraphBuilder().compile()
    assert emitter.generate(plain)==CppEmitter().generate(plain)
