"""Event signature migrations exercised by the real interpreted/generated hosts."""
from copy import deepcopy
from editor.core.builder import GraphBuilder
from editor.core.event_edits import migrate_event_signature
from editor.core.data_types import TYPES,declaration
from editor.core.document import default_scene
from tests.test_native import native
from tests.test_functions import assert_parity
from tests.test_events import event
from tests.test_event_edits import fixture,renamed
from tests.test_physics_scene import chain
from tests.test_scene_session import key,replay


def test_every_payload_type_survives_rename_and_reverse_order(native):
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
    definition=event('Payload',[dict(name=f'P{i}',type=t) for i,t in enumerate(TYPES)])
    b=GraphBuilder(event_definitions=[definition]); b.add('start','On Game Start')
    b.add('send','Send Payload',**{f'P{i}':v for i,v in enumerate(values.values())}); b.add('on','On Payload')
    b.connect('start','Out','send','In'); previous='on'
    for i,t in enumerate(TYPES):
        setter=next(s for s in b.registry.nodes.values() if s.variable_type==t and s.variable_access=='write')
        b.add(f'save{i}',setter.name,Name=f'v{i}'); b.connect(previous,'Out',f'save{i}','In').connect('on',f'P{i}',f'save{i}','Value'); previous=f'save{i}'
    before=assert_parity(*native(b.graph,frames=0)); new=deepcopy(definition); new['name']='Renamed payload'
    new['parameters']=[{**p,'name':'Renamed_'+p['name']} for p in reversed(new['parameters'])]
    edited,_=migrate_event_signature(b.graph,definition['id'],new,{'Renamed_'+p['name']:p['name'] for p in definition['parameters']})
    after=assert_parity(*native(edited,frames=0)); assert before==after
    for i,(t,v) in enumerate(values.items()): assert after['variables'][f'v{i}']==declaration(t,v)


def test_nested_senders_keep_existing_defaults_and_routing(native):
    doc,e=fixture(); before=assert_parity(*native(doc,frames=0)); new,origins=renamed(e)
    after,_=migrate_event_signature(doc,e['id'],new,origins)
    actual=assert_parity(*native(after,frames=0)); assert before==actual
    assert actual['variables']['answer']==declaration('int',17)
    assert actual['variables']['sender']==declaration('entity','')


def test_compatible_type_edit_and_defaults_of_new_senders(native):
    e=event(parameters=[dict(name='Value',type='float',default=0.)]); b=GraphBuilder(event_definitions=[e])
    b.add('start','On Game Start'); b.add('send','Send Ping'); b.add('on','On Ping'); b.connect('start','Out','send','In')
    new=deepcopy(e); new['parameters']=[dict(name='Value',type='int',default=4)]
    edited,_=migrate_event_signature(b.graph,e['id'],new)
    new['parameters'][0]['default']=99; edited,_=migrate_event_signature(edited,e['id'],new)
    b=GraphBuilder(event_definitions=[new]); b.graph=edited
    b.add('fresh','Send Ping'); b.connect('send','Out','fresh','In'); b.add('sum','Get Integer Variable',Name='sum')
    b.add('add','Integer Add'); b.add('store','Set Integer Variable',Name='sum')
    b.connect('on','Out','store','In').connect('sum','Value','add','A').connect('on','Value','add','B').connect('add','Value','store','Value')
    scene=default_scene(); scene['variables']['sum']=declaration('int',0)
    actual=assert_parity(*native(b.graph,frames=0,scene=scene)); assert actual['variables']['sum']==declaration('int',103)


def test_renamed_event_payload_survives_delay_save_and_new_process_load(native,tmp_path):
    e=event(parameters=[dict(name='Number',type='int',default=11)]); b=GraphBuilder(event_definitions=[e])
    b.add('start','On Game Start'); chain(b,'start',('storage','Open Save Storage',{'Game ID':'event-edit'}))
    b.add('begin','On Key Pressed',Filter='B'); chain(b,'begin',('send','Send Ping',{'Recipient':'player','Sender':'player'}))
    b.add('handler','On Ping',Receiver='player'); chain(b,'handler',('wait','Delay',{'Seconds':.3}),('store','Set Integer Variable',{'Name':'payload'}),
        ('sender','Set Entity Variable',{'Name':'sender'}))
    b.connect('handler','Number','store','Value').connect('handler','Sender','sender','Value'); key(b,'S','Save Game'); key(b,'L','Load Game')
    new=deepcopy(e); new['name']='Notice'; new['parameters'][0]['name']='Amount'
    edited,_=migrate_event_signature(b.graph,e['id'],new,{'Amount':'Number'},default_scene())
    common=['--dt','.1','--save-root',str(tmp_path/'save')]
    first=assert_parity(*native(edited,frames=2,extra=[*common,*replay(tmp_path/'keys.json',[(0,'B',True),(1,'B',False),(1,'S',True)])]))
    assert first['persistence']['success'] and len(first['continuations']['tasks'])==1
    restored=assert_parity(*native(edited,frames=8,extra=[*common,*replay(tmp_path/'keys.json',[(0,'L',True)])]))
    assert restored['persistence']['success'] and not restored['continuations']['tasks']
    assert restored['variables']['payload']==declaration('int',11) and restored['variables']['sender']==declaration('entity','player')
    assert restored['events']==first['events']==dict(pending=0,subscriptions=[
        dict(event=10008,receiver='',enabled=True),dict(event=e['id'],receiver='player',enabled=True)])
