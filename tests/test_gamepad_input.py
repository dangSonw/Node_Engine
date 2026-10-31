"""Controller graph semantics, scoped callbacks and validation in both native hosts."""
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene,save_json
from editor.core.compiler import GraphError
from tests.test_native import native

def connect(frame,id=7,connected=True): return dict(frame=frame,type='gamepad_connection',controller=id,connected=connected)
def axis(frame,value,name='LeftX',id=7): return dict(frame=frame,type='gamepad_axis',controller=id,axis=name,value=value)
def button(frame,down,name='South',id=7): return dict(frame=frame,type='gamepad_button',controller=id,button=name,down=down)

@pytest.mark.parametrize('values',[{'Axis':'leftx'},{'Controller':-1},{'Controller':4294967296},{'Dead Zone':1},{'Dead Zone':-.1}])
def test_invalid_literal_gamepad_arguments(values):
    b=GraphBuilder(); b.add('axis','Get Gamepad Axis',**values)
    with pytest.raises(GraphError): b.compile(default_scene())

def test_invalid_filter_and_unscoped_payload():
    b=GraphBuilder(); b.add('button','On Gamepad Button',Filter='A')
    with pytest.raises(GraphError): b.compile(default_scene())
    b=GraphBuilder(); b.add('button','On Gamepad Button'); b.add('update','On Update'); b.add('save','Set Integer Variable',Name='id')
    b.connect('update','Out','save','In').connect('button','Controller','save','Value')
    scene=default_scene(); scene['variables']['id']=dict(type='int',value=0)
    with pytest.raises(GraphError): b.compile(scene)

def test_gamepad_replay_polling_order_and_captured_controller(native,tmp_path):
    b=GraphBuilder(); scene=default_scene(); scene['variables'].update(
        axes=dict(type='array<float>',value=[]),controllers=dict(type='array<int>',value=[]),event_ids=dict(type='array<int>',value=[]))
    b.add('update','On Update'); b.add('axis','Get Gamepad Axis',**{'Dead Zone':.2}); b.add('axes','Get Float Array Variable',Name='axes')
    b.add('append','Append Float Item'); b.add('save','Set Float Array Variable',Name='axes')
    b.connect('axes','Value','append','Array').connect('axis','Value','append','Item').connect('append','Value','save','Value').connect('update','Out','save','In')
    b.add('connected','Get Connected Controllers'); b.add('connected_save','Set Integer Array Variable',Name='controllers')
    b.connect('save','Out','connected_save','In').connect('connected','Value','connected_save','Value')
    b.add('button','On Gamepad Button'); b.add('format','Format Boolean'); b.add('log','Print Log')
    b.connect('button','Down','format','Value').connect('format','Value','log','Message').connect('button','Out','log','In')
    b.add('ids','Get Integer Array Variable',Name='event_ids'); b.add('id_add','Append Integer Item'); b.add('id_save','Set Integer Array Variable',Name='event_ids')
    b.connect('ids','Value','id_add','Array').connect('button','Controller','id_add','Item').connect('id_add','Value','id_save','Value').connect('log','Out','id_save','In')
    b.add('delayed','On Gamepad Button',Filter='South'); b.add('delay','Delay',Seconds=0); b.add('id_text','Format Integer'); b.add('later','Print Log')
    b.connect('delayed','Out','delay','In').connect('delay','Out','later','In').connect('delayed','Controller','id_text','Value').connect('id_text','Value','later','Message')
    replay=tmp_path/'pads.json'; save_json(replay,dict(version=3,events=[connect(0),axis(0,.1),button(0,True),button(0,True),button(0,False),
        axis(1,1),button(1,True),connect(2,connected=False),connect(3,id=12),axis(3,-1,id=12),button(3,True,id=12),
        dict(frame=4,release_all=True)]))
    a,c=native(b.graph,scene=scene,frames=6,extra=['--input-replay',str(replay)])
    assert a.returncode==c.returncode==0,a.stderr+c.stderr
    state=json.loads(a.stdout); assert state==json.loads(c.stdout)
    assert state['variables']['axes']['value']==[0,1,0,-1,0,0]
    assert state['variables']['controllers']['value']==[12]
    assert state['variables']['event_ids']['value']==[7,7,7,7,12,12]
    assert state['logs']==['true','false','7','true','7','false','7','true','12','false','12']

def test_axis_ranges_missing_device_and_dynamic_runtime_errors(native,tmp_path):
    b=GraphBuilder(); b.add('start','On Game Start'); b.add('axis','Get Gamepad Axis',Axis='LeftTrigger',**{'Dead Zone':0}); b.add('save','Set Variable',Name='score')
    b.connect('start','Out','save','In').connect('axis','Value','save','Value')
    a,c=native(b.graph,frames=0); assert a.returncode==c.returncode==0 and json.loads(a.stdout)==json.loads(c.stdout)
    assert json.loads(a.stdout)['variables']['score']==0
    b.add('bad','String',Value='unknown'); b.connect('bad','Value','axis','Axis')
    a,c=native(b.graph,frames=0); assert a.returncode==c.returncode==1
    assert json.loads(a.stderr)==json.loads(c.stderr) and json.loads(a.stderr)['node']=='axis'
