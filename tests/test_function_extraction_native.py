"""Before/after extraction behavior through real interpreted and generated C++."""
from copy import deepcopy
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene
from editor.core.function_extraction import extract_function
from editor.core.functions import new_function
from tests.test_functions import port,assert_parity,double_function,action_function,graph
from tests.test_core import node,link
from tests.test_native import native
from tests.test_physics_scene import chain
from tests.test_function_extraction import math_graph,mutable_graph
from tests.test_scene_session import key,replay


def compare(native,document,selection,*,scene=None,frames=3,extra=(),current_function=None):
    scene=scene or default_scene()
    before=assert_parity(*native(document,scene=scene,frames=frames,extra=extra))
    edited,info=extract_function(document,selection,'Extracted',scene,current_function=current_function)
    after=assert_parity(*native(edited,scene=scene,frames=frames,extra=extra))
    # Qualified node IDs change intentionally; world state and observable execution must not.
    for key in ('entities','variables','logs','frame','time','timers','persistence','scene_session','application'):
        assert before.get(key)==after.get(key),(key,before.get(key),after.get(key))
    return after,edited,info


def test_pure_chain_and_nested_function_extraction(native):
    state,_,_=compare(native,math_graph(),{'add','times'},frames=0)
    assert state['variables']['answer']=={'type':'int','value':35}
    f=double_function(); a=action_function(f)
    g=graph([node('start',1001),node('call',a['id'],Number=7),node('set',3111,Name='result')],
            [link('start','Out','call','In'),link('call','Out','set','In'),link('call','Result','set','Value')],[f,a])
    state,_,_=compare(native,g,{'twice'},current_function=f['id'],frames=0)
    assert state['variables']['result']['value']==14


def test_lazy_unselected_overflow_branch_is_not_evaluated(native):
    b=GraphBuilder(); b.add('start','On Game Start'); chain(b,'start',('set','Set Integer Variable',{'Name':'answer'}))
    b.add('bad','Integer Add',A=9223372036854775807,B=1); b.add('select','Select Integer',**{'Condition':False,'False':8})
    b.connect('bad','Value','select','True').connect('select','Value','set','Value')
    state,_,_=compare(native,b.graph,{'select'},frames=0)
    assert state['variables']['answer']['value']==8


def test_mutable_reads_across_delay_and_root_outputs_stay_lazy(native):
    scene=default_scene(); scene['variables']={'counter':1.}
    state,_,_=compare(native,mutable_graph(),{'read_before','write','wait','read_after'},scene=scene)
    assert state['variables']['before']==1 and state['variables']['after']==10
    b=GraphBuilder(); b.add('start','On Game Start'); chain(b,'start',('write','Set Variable',{'Name':'counter','Value':2}),
        ('later','Set Variable',{'Name':'counter','Value':9}),('set','Set Variable',{'Name':'answer'}))
    b.add('read','Get Variable',Name='counter'); b.add('times','Multiply',B=2)
    b.connect('read','Value','times','A').connect('times','Value','set','Value')
    state,_,info=compare(native,b.graph,{'write','read','times'},scene=scene,frames=0)
    assert state['variables']['answer']==18 and info['retained']==['read','times']


@pytest.mark.parametrize('kind',['For Loop','For Each Integer','While Loop','Sequence'])
def test_complete_structured_regions_preserve_execution(native,kind):
    b=GraphBuilder(); b.add('start','On Game Start'); chain(b,'start',('region',kind,{}))
    b.add('increment','Set Integer Variable',Name='counter'); b.add('read','Get Integer Variable',Name='counter'); b.add('add','Integer Add',B=1)
    b.connect('read','Value','add','A').connect('add','Value','increment','Value')
    b.add('done','Print Log',Message='done'); selected={'region','increment','add'}
    if kind=='While Loop':
        b.add('less','Integer Less',B=3); b.connect('read','Value','less','A').connect('less','Value','region','Condition')
    if kind=='For Loop': b.graph['nodes'][1]['values']={'Count':3}
    if kind=='For Each Integer': b.graph['nodes'][1]['values']={'Array':[2,3,4]}
    b.connect('region','First' if kind=='Sequence' else 'Body','increment','In')
    b.connect('region','Then' if kind=='Sequence' else 'Done','done','In')
    s=default_scene(); s['variables']={'counter':{'type':'int','value':0}}
    state,_,_=compare(native,b.graph,selected,scene=s,frames=0)
    assert state['variables']['counter']['value']==(1 if kind=='Sequence' else 3) and state['logs']==['done']


def test_event_payload_and_external_loop_item_are_captured(native,tmp_path):
    b=GraphBuilder(); b.add('start','On Game Start'); chain(b,'start',('each','For Each Integer',{'Array':[2,3,4]}))
    b.add('wait','Delay',Seconds=0); b.add('store','Set Integer Variable',Name='item')
    b.connect('each','Body','wait','In').connect('wait','Out','store','In').connect('each','Item','store','Value')
    state,_,info=compare(native,b.graph,{'wait','store'},frames=3)
    assert state['variables']['item']['value']==4 and any(p['name']=='each_Item' for p in info['inputs'])
    b=GraphBuilder(); b.add('key','On Key Pressed',Filter='K'); chain(b,'key',('wait','Delay',{'Seconds':0}),('log','Print Log',{}))
    b.connect('key','Key','log','Message')
    state,_,_=compare(native,b.graph,{'wait','log'},extra=replay(tmp_path/'key.json',[(0,'K',True)]))
    assert state['logs']==['K']


def test_extracted_action_multiple_returns_and_save_restore(native,tmp_path):
    f=new_function('Pair',outputs=[port('One','int'),port('Two','int')]); f['graph']['nodes'][1]['values']={'One':7,'Two':9}
    b=GraphBuilder(functions=[f]); b.add('start','On Game Start'); chain(b,'start',('storage','Open Save Storage',{'Game ID':'extract-test'}))
    b.add('B','On Key Pressed',Filter='B'); chain(b,'B',('wait','Delay',{'Seconds':.3}),('pair','Pair',{}),
        ('one','Set Integer Variable',{'Name':'one'}),('two','Set Integer Variable',{'Name':'two'}))
    b.connect('pair','One','one','Value').connect('pair','Two','two','Value'); key(b,'S','Save Game'); key(b,'L','Load Game')
    edited,info=extract_function(b.graph,{'wait','pair'},'Delayed pair',default_scene())
    assert len(info['outputs'])==2
    common=['--dt','.1','--save-root',str(tmp_path/'save')]
    first=assert_parity(*native(edited,frames=2,extra=[*common,*replay(tmp_path/'keys.json',[(0,'B',True),(1,'B',False),(1,'S',True)])]))
    assert first['persistence']['success'] and len(first['continuations']['tasks'])==1
    restored=assert_parity(*native(edited,frames=8,extra=[*common,*replay(tmp_path/'keys.json',[(0,'L',True)])]))
    assert restored['persistence']['success'] and not restored['continuations']['tasks']
    assert restored['variables']['one']['value']==7 and restored['variables']['two']['value']==9


@pytest.mark.parametrize('kind,values,logs',[('Branch',{'Condition':False},[]),('Branch',{'Condition':True},['next']*3),
    ('Do Once',{},['next']),('Gate',{'Start Closed':True},[])])
def test_extract_preserves_paths_that_do_not_continue(native,kind,values,logs):
    b=GraphBuilder(); b.add('update','On Update'); chain(b,'update',('control',kind,values))
    b.add('next','Print Log',Message='next'); b.connect('control','True' if kind=='Branch' else 'Out','next','In')
    state,_,info=compare(native,b.graph,{'control'})
    assert state['logs']==logs and info['guarded'] and len(info['added'])==2


@pytest.mark.parametrize('condition',[False,True])
def test_guarded_delayed_result_only_reaches_original_continuation(native,condition):
    f=new_function('Answer',outputs=[port('Value','int')]); f['graph']['nodes'][1]['values']={'Value':42}
    b=GraphBuilder(functions=[f]); b.add('start','On Game Start'); chain(b,'start',('branch','Branch',{'Condition':condition}))
    b.add('wait','Delay',Seconds=.1); b.add('answer','Answer'); b.add('store','Set Integer Variable',Name='answer')
    b.connect('branch','True','wait','In').connect('wait','Out','answer','In')
    b.connect('answer','Out','store','In').connect('answer','Value','store','Value')
    state,_,info=compare(native,b.graph,{'branch','wait','answer'},frames=4,extra=['--dt','.1'])
    assert info['guarded'] and len(info['outputs'])==2
    assert state['variables'].get('answer')==({'type':'int','value':42} if condition else None)
    assert not state['continuations']['tasks']
