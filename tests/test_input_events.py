"""Ordered physical/mapped input entry points in both native implementations."""
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene,save_json
from editor.core.compiler import GraphError
from tests.test_native import native
from tests.test_physics_scene import chain

def scene():
    result=default_scene()
    result['input']=dict(version=1,actions={'jump':['Space','MouseLeft'],'z_jump':['Space']},axes={})
    return result

def listen(b,nid,event,port,filter=''):
    b.add(nid,event,Filter=filter)
    b.add(nid+'_label','Concat Strings',A=nid+':')
    b.add(nid+'_log','Print Log')
    b.connect(nid,port,nid+'_label','B')
    b.connect(nid+'_label','Value',nid+'_log','Message')
    b.connect(nid,'Out',nid+'_log','In')
    return nid+'_log'

def run(native,b,tmp_path,events=(),frames=4,extra=()):
    replay=tmp_path/'keys.json'; save_json(replay,dict(version=1,events=events))
    left,right=native(b.graph,scene=scene(),frames=frames,extra=['--input-replay',str(replay),*extra])
    assert left.returncode==right.returncode==0,left.stderr+right.stderr
    assert json.loads(left.stdout)==json.loads(right.stdout)
    return json.loads(left.stdout)

def keys(*events): return [dict(frame=f,button=k,down=d) for f,k,d in events]

@pytest.mark.parametrize('name,filter',[('On Key Pressed','MouseLeft'),('On Key Released','space'),('On Mouse Button','Space'),('On Action Pressed','missing'),('On Action Released','missing')])
def test_invalid_filter_rejected(name,filter):
    b=GraphBuilder(); b.add('input',name,Filter=filter)
    with pytest.raises(GraphError,match='input event filter'): b.compile(scene())

def test_filter_is_constant_and_payload_is_scoped():
    b=GraphBuilder(); b.add('key','On Key Pressed'); b.add('text','String',Value='Space')
    b.connect('text','Value','key','Filter')
    with pytest.raises(GraphError,match='constant'): b.compile(scene())
    b=GraphBuilder(); b.add('key','On Key Pressed'); b.add('update','On Update'); b.add('log','Print Log')
    b.connect('update','Out','log','In'); b.connect('key','Key','log','Message')
    with pytest.raises(GraphError,match='inside that input event handler'): b.compile(scene())

def test_ordered_transitions_quick_taps_repeat_and_alternative_handoff(native,tmp_path):
    b=GraphBuilder()
    for nid,event,port in [('kp','On Key Pressed','Key'),('kr','On Key Released','Key'),
                           ('mouse','On Mouse Button','Button'),('ap','On Action Pressed','Action'),('ar','On Action Released','Action')]:
        listen(b,nid,event,port)
    b.add('update','On Update'); chain(b,'update',('frame_log','Print Log',{'Message':'update'}))
    result=run(native,b,tmp_path,keys((0,'Space',True),(0,'Space',True),(0,'MouseLeft',True),
        (0,'Space',False),(0,'MouseLeft',False),(0,'Space',True),(0,'Space',False),(2,'A',True))+[dict(frame=3,release_all=True)])
    assert result['logs']==['kp:Space','ap:jump','ap:z_jump','mouse:MouseLeft','kr:Space','ar:z_jump',
        'mouse:MouseLeft','ar:jump','kp:Space','ap:jump','ap:z_jump','kr:Space','ar:jump','ar:z_jump',
        'update','update','kp:A','update','kr:A','update']

def test_filters_listener_order_captured_mouse_down_and_current_polling(native,tmp_path):
    b=GraphBuilder()
    listen(b,'z','On Key Pressed','Key','Space'); listen(b,'a','On Key Pressed','Key','Space')
    listen(b,'ignore','On Key Released','Key','B'); listen(b,'filtered','On Action Released','Action','jump')
    b.add('mouse','On Mouse Button'); b.add('down','Format Boolean'); b.add('log','Print Log')
    b.connect('mouse','Down','down','Value'); b.connect('down','Value','log','Message'); b.connect('mouse','Out','log','In')
    chain(b,'log',('held_log','Print Log',{}))
    b.add('held','Is Key Held',Key='MouseLeft'); b.add('held_text','Format Boolean')
    b.connect('held','Value','held_text','Value'); b.connect('held_text','Value','held_log','Message')
    result=run(native,b,tmp_path,keys((0,'Space',True),(0,'Space',False),(0,'MouseLeft',True),(0,'MouseLeft',False)),frames=1)
    assert result['logs']==['a:Space','z:Space','filtered:jump','true','false','false','false','filtered:jump']

@pytest.mark.parametrize('delay,expected',[('Delay','A'),('Retriggerable Delay','B')])
def test_input_delay_waits_for_next_frame_with_first_or_latest_capture(native,tmp_path,delay,expected):
    b=GraphBuilder(); b.add('key','On Key Pressed',Filter='')
    chain(b,'key',('delay',delay,{'Seconds':0}),('log','Print Log',{}))
    b.connect('key','Key','log','Message')
    b.add('update','On Update'); chain(b,'update',('frame_log','Print Log',{'Message':'update'}))
    result=run(native,b,tmp_path,keys((0,'A',True),(0,'B',True)),frames=2)
    assert result['logs']==['update',expected,'update']

def test_held_baseline_does_not_synthesize_input_events(native):
    b=GraphBuilder(); listen(b,'press','On Key Pressed','Key'); listen(b,'action','On Action Pressed','Action')
    left,right=native(b.graph,scene=scene(),frames=2,extra=['--key','Space'])
    assert left.returncode==right.returncode==0,left.stderr+right.stderr
    assert json.loads(left.stdout)==json.loads(right.stdout)
    assert json.loads(left.stdout)['logs']==[]

def test_input_callback_budget_reports_handler_node(native,tmp_path):
    b=GraphBuilder(); b.add('press','On Key Pressed'); b.add('loop','While Loop',Condition=True); b.connect('press','Out','loop','In')
    replay=tmp_path/'keys.json'; save_json(replay,dict(version=1,events=keys((0,'Space',True))))
    left,right=native(b.graph,scene=scene(),frames=1,extra=['--input-replay',str(replay),'--budget','20'])
    assert left.returncode==right.returncode==1
    assert json.loads(left.stderr)==json.loads(right.stderr)
    assert json.loads(left.stderr)['node']=='loop' and 'budget' in left.stderr
