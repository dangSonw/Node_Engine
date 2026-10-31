from copy import deepcopy
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.functions import new_function
from editor.core.events import new_event
from editor.core.typed_schema import build_schema
from editor.core.document import save_json
from tests.test_named_ports import root,echo
from tests.test_native import native


def parity(native,b,**kw):
    a,c=native(b.graph,**kw)
    assert a.returncode==c.returncode==0,a.stderr+c.stderr
    state=json.loads(a.stdout); assert state==json.loads(c.stdout)
    return state


def delayed():
    inner,structs,enums=echo(pure=False)
    schema=build_schema(structs,enums)
    inner['name']='Delayed echo'
    body=GraphBuilder(functions=[inner],function=inner['id'],struct_definitions=structs,enum_definitions=enums)
    body.add('entry','Function Input'); body.add('wait','Delay',Seconds=.5); body.add('return','Function Output')
    body.connect('entry','Out','wait','In').connect('wait','Out','return','In')
    body.connect('entry','Stats','return','Result').connect('entry','Mode','return','State')
    inner['graph']=body.graph
    outer=new_function('Nested echo',inner['inputs'],inner['outputs'],definitions=[inner],schema=schema)
    body=GraphBuilder(functions=[inner,outer],function=outer['id'],struct_definitions=structs,enum_definitions=enums)
    for nid,name in [('entry','Function Input'),('call','Delayed echo'),('return','Function Output')]: body.add(nid,name)
    body.connect('entry','Out','call','In').connect('call','Out','return','In')
    body.connect('entry','Stats','call','Stats').connect('entry','Mode','call','Mode')
    body.connect('call','Result','return','Result').connect('call','State','return','State')
    outer['graph']=body.graph
    event=new_event('Captured',[dict(name='Data',type='struct:Stats'),dict(name='State',type='enum:Mode'),
        dict(name='Items',type='set<string>')],schema=schema)
    b=GraphBuilder(functions=[inner,outer],event_definitions=[event],struct_definitions=structs,enum_definitions=enums)
    for nid,name,values in [('start','On Game Start',{}),('open','Open Save Storage',{'Game ID':'named-port-test'}),
        ('send','Broadcast Captured',dict(Data=dict(hp=42),State='Run',Items=['b','a'])),
        ('change','Set Stats Variable',dict(Name='source',Value=dict(hp=99))),
        ('event','On Captured',{}),('call','Nested echo',{}),
        ('store','Set Stats Variable',dict(Name='result')),('mode','Set Mode Variable',dict(Name='mode')),
        ('original','Set Stats Variable',dict(Name='original')),('items','Set String Set Variable',dict(Name='items'))]:
        b.add(nid,name,**values)
    for chain in [('start','open','send','change'),('event','call','store','mode','original','items')]:
        for a,c in zip(chain,chain[1:]): b.connect(a,'Out',c,'In')
    b.connect('event','Data','call','Stats').connect('event','State','call','Mode')
    b.connect('call','Result','store','Value').connect('call','State','mode','Value')
    b.connect('event','Data','original','Value').connect('event','Items','items','Value')
    for key,action in [('S','Save Game'),('L','Load Game')]:
        b.add(key,'On Key Pressed',Filter=key); b.add(key+'action',action,Slot='pending')
        b.connect(key,'Out',key+'action','In')
    return b


def test_native_named_pure_function_event_roundtrip(native):
    b,f,event=root()
    state=parity(native,b,frames=0)
    assert state['variables']['stats']==dict(type='struct:Stats',value=dict(hp=42))


def test_native_named_nested_functions_event_capture_and_restore(native,tmp_path):
    b=delayed()
    replay=tmp_path/'save.json'; save_json(replay,dict(version=1,events=[dict(frame=1,button='S',down=True)]))
    saves=tmp_path/'saves'
    waiting=parity(native,b,frames=2,extra=['--dt','.1','--save-root',str(saves),'--input-replay',str(replay)])
    assert waiting['persistence']['success'] and len(waiting['continuations']['tasks'])==1
    slot=next(saves.rglob('*.json')); checkpoint=json.loads(slot.read_text('utf-8'))['checkpoint']
    frames=checkpoint['continuations']['tasks'][0]['frames']
    assert len(frames)==3
    assert frames[1]['parameters'][0]==dict(type='struct:Stats',value=dict(hp=42))
    assert frames[2]['parameters'][1]==dict(type='enum:Mode',value='Run')
    save_json(replay,dict(version=1,events=[dict(frame=0,button='L',down=True)]))
    resumed=parity(native,b,frames=6,extra=['--dt','.1','--save-root',str(saves),'--input-replay',str(replay)])
    assert resumed['persistence']['success'],resumed['persistence']
    assert not resumed['continuations']['tasks']
    for name in ('result','original'): assert resumed['variables'][name]==dict(type='struct:Stats',value=dict(hp=42))
    assert resumed['variables']['source']==dict(type='struct:Stats',value=dict(hp=99))
    assert resumed['variables']['mode']==dict(type='enum:Mode',value='Run')
    assert resumed['variables']['items']==dict(type='set<string>',value=['b','a'])


@pytest.mark.parametrize('damage',['struct','enum','nominal'])
def test_native_named_continuation_corruption_rejected_before_commit(native,tmp_path,damage):
    b=delayed(); replay=tmp_path/'keys.json'; saves=tmp_path/'saves'
    save_json(replay,dict(version=1,events=[dict(frame=1,button='S',down=True)]))
    parity(native,b,frames=2,extra=['--dt','.1','--save-root',str(saves),'--input-replay',str(replay)])
    slot=next(saves.rglob('*.json')); saved=json.loads(slot.read_text('utf-8'))
    parameters=saved['checkpoint']['continuations']['tasks'][0]['frames'][-1]['parameters']
    if damage=='struct': parameters[0]['value']['hp']='bad'
    elif damage=='enum': parameters[1]['value']='Unknown label'
    else: parameters[0]['type']='struct:Missing'
    save_json(slot,saved); before=slot.read_bytes()
    save_json(replay,dict(version=1,events=[dict(frame=0,button='L',down=True)]))
    state=parity(native,b,frames=1,extra=['--dt','.1','--save-root',str(saves),'--input-replay',str(replay)])
    assert not state['persistence']['success'] and state['persistence']['error']
    assert 'result' not in state['variables'] and len(state['continuations']['tasks'])==1
    assert slot.read_bytes()==before
