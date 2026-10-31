from copy import deepcopy
import pytest
from editor.core.builder import GraphBuilder
from editor.core.compiler import compile_graph,GraphError
from editor.core.document import default_scene
from editor.core.function_extraction import extract_function
from editor.core.functions import new_function
from tests.test_core import node,link
from tests.test_functions import graph,port,double_function
from tests.test_physics_scene import chain


def math_graph():
    b=GraphBuilder(); b.add('start','On Game Start'); chain(b,'start',('set','Set Integer Variable',{'Name':'answer'}))
    b.add('add','Integer Add',A=3,B=4); b.add('times','Integer Multiply',B=5)
    b.connect('add','Value','times','A').connect('times','Value','set','Value')
    return b.graph


def test_pure_extraction_promotes_literals_and_rewires_all_consumers():
    before=math_graph(); original=deepcopy(before)
    after,info=extract_function(before,{'add','times'},'Calculation')
    assert before==original and info['pure'] and info['removed']==['add','times'] and info['retained']==[]
    f=after['functions'][-1]; assert [p['default'] for p in f['inputs']]==[3,4,5]
    assert len(f['outputs'])==1 and set(n['id'] for n in f['graph']['nodes'])>={'add','times'}
    assert link(info['call_id'],'times_Value','set','Value') in after['links']; compile_graph(after)


def test_external_pure_cone_is_copied_to_preserve_lazy_evaluation():
    b=GraphBuilder(); b.add('start','On Game Start'); chain(b,'start',('set','Set Integer Variable',{'Name':'answer'}))
    b.add('overflow','Integer Add',A=9223372036854775807,B=1); b.add('choose','Select Integer',**{'Condition':False,'False':8})
    b.connect('overflow','Value','choose','True').connect('choose','Value','set','Value')
    after,info=extract_function(b.graph,{'choose'},'Lazy Choice')
    assert info['copied']==['overflow'] and 'overflow' in {n['id'] for n in after['nodes']}
    assert not any(e['from'][0]=='overflow' and e['to'][0]==info['call_id'] for e in after['links'])
    compile_graph(after)


def mutable_graph():
    b=GraphBuilder(); b.add('start','On Game Start'); chain(b,'start',('read_before','Set Variable',{'Name':'before'}),
        ('write','Set Variable',{'Name':'counter','Value':10}),('wait','Delay',{'Seconds':0}),('read_after','Set Variable',{'Name':'after'}))
    b.add('read','Get Variable',Name='counter'); b.connect('read','Value','read_before','Value').connect('read','Value','read_after','Value')
    return b.graph


def test_action_reads_stay_dynamic_across_write_and_delay():
    doc=mutable_graph(); after,info=extract_function(doc,{'read_before','write','wait','read_after'},'Mutate')
    assert not info['pure'] and info['copied']==['read']
    assert not info['outputs']; compile_graph(after)


def test_root_lazy_results_remain_in_root_after_action_extraction():
    b=GraphBuilder(); b.add('start','On Game Start'); chain(b,'start',('set','Set Variable',{'Name':'counter','Value':2}),
        ('later','Set Variable',{'Name':'counter','Value':9}),('read_out','Set Variable',{'Name':'result'}))
    b.add('read','Get Variable',Name='counter'); b.add('twice','Multiply',B=2)
    b.connect('read','Value','twice','A').connect('twice','Value','read_out','Value')
    after,info=extract_function(b.graph,{'set','read','twice'},'Write')
    assert info['retained']==['read','twice'] and info['removed']==['set'] and not info['outputs']; compile_graph(after)


def test_loop_and_captured_results_can_cross_a_function_boundary():
    f=new_function('Value',outputs=[port('Result','int')]); f['graph']['nodes'][1]['values']={'Result':13}
    b=GraphBuilder(functions=[f]); b.add('start','On Game Start'); chain(b,'start',('call','Value',{}),('set','Set Integer Variable',{'Name':'result'}))
    b.connect('call','Result','set','Value'); after,info=extract_function(b.graph,{'call'},'Wrapper')
    assert info['outputs']==[dict(name='call_Result',type='int')] and len(after['functions'])==2; compile_graph(after)


def test_extraction_inside_function_updates_only_that_body():
    f=double_function(); doc=graph([],functions=[f]); before=deepcopy(doc)
    after,info=extract_function(doc,{'twice'},'Multiply body',current_function=f['id'])
    assert after['nodes']==[] and len(after['functions'])==2 and before==doc
    assert info['inputs'][0]['name']=='entry_Number' and info['pure']; compile_graph(after)


@pytest.mark.parametrize('case',['none','unknown','event','multi_result','scene_read','multi_entry','multi_exit','partial_loop','shared_tail','partial_sequence'])
def test_reject_unsafe_selections_without_mutation(case):
    b=GraphBuilder(); b.add('start','On Game Start'); chain(b,'start',('loop','For Loop',{'Count':2}))
    b.add('done','Print Log',Message='done'); b.connect('loop','Done','done','In')
    b.add('body','Print Log',Message='body'); b.connect('loop','Body','body','In'); selected={'loop','body'}
    if case=='none': selected=set()
    if case=='unknown': selected={'missing'}
    if case=='event': selected={'start'}
    if case=='multi_result':
        b.add('a','Integer Add'); b.add('z','Integer Add'); selected={'a','z'}
    if case=='scene_read': b.add('read','Get Variable'); selected={'read'}
    if case=='multi_entry': selected={'body','done'}
    if case=='multi_exit':
        b.add('branch','Branch'); b.add('other','Print Log'); b.connect('body','Out','branch','In').connect('branch','True','other','In').connect('branch','False','done','In'); selected={'branch'}
    if case=='partial_loop': selected={'loop'}
    if case=='shared_tail':
        b.graph['links'].remove(link('loop','Done','done','In')); b.connect('loop','Done','body','In')
    if case=='partial_sequence':
        b=GraphBuilder(); b.add('start','On Game Start'); chain(b,'start',('sequence','Sequence',{}))
        b.add('first','Print Log'); b.add('then','Print Log'); b.connect('sequence','First','first','In').connect('sequence','Then','then','In'); selected={'sequence','then'}
    before=deepcopy(b.graph)
    with pytest.raises((ValueError,GraphError)): extract_function(b.graph,selected,'Unsafe')
    assert b.graph==before
