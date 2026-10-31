"""Break/Continue lexical scope and real interpreter/generated C++ parity."""
import json
from copy import deepcopy
from pathlib import Path
import pytest
from editor.core.builder import GraphBuilder
from editor.core.compiler import GraphError
from editor.core.codegen import CppEmitter
from editor.core.document import default_scene
from editor.core.functions import new_function
from tests.test_native import native
from tests.test_physics_scene import chain,run


def build(loop='For Loop', control='Break Loop'):
    b=GraphBuilder(); b.add('start','On Game Start')
    values={'Count':5} if loop=='For Loop' else {'Condition':True} if loop=='While Loop' else {'Array':[1,2,3,4,5]}
    b.add('loop',loop,**values); b.connect('start','Out','loop','In')
    b.add('control',control); b.connect('loop','Body','control','In')
    b.add('done','Print Log',Message='done'); b.connect('loop','Done','done','In')
    return b


@pytest.mark.parametrize('control',['Break Loop','Continue Loop'])
@pytest.mark.parametrize('path',['event','done','shared'])
def test_reject_control_outside_lexical_loop(control,path):
    b=build(control=control)
    if path=='event': b.connect('start','Out','control','In'); b.graph['links'].pop(0)
    elif path=='done':
        b.graph['links']=[x for x in b.graph['links'] if x['from']!=['loop','Done']]
        b.connect('loop','Done','control','In')
    else:
        b.add('update','On Update'); b.connect('update','Out','control','In')
    with pytest.raises(GraphError,match='inside a loop Body') as error: b.compile()
    assert error.value.problems[0].node=='control'


@pytest.mark.parametrize('control',['Break Loop','Continue Loop'])
def test_function_cannot_control_callers_loop(control):
    f=new_function('Invalid helper')
    body=GraphBuilder(functions=[f],function=f['id']); body.add('entry','Function Input')
    chain(body,'entry',('control',control,{})); f['graph']=body.graph
    b=GraphBuilder(functions=[f]); b.add('start','On Game Start'); b.add('loop','For Loop')
    b.add('call','Invalid helper'); b.connect('start','Out','loop','In').connect('loop','Body','call','In')
    with pytest.raises(GraphError,match='inside a loop Body') as error: b.compile()
    assert error.value.problems[0].node==str(f['id'])+'/control'


@pytest.mark.parametrize('op,type_id',[('break',2005),('continue',2006)])
def test_cpp_export_rejects_unscoped_raw_ir(op,type_id):
    b=GraphBuilder(); ir=b.compile()
    ir['events']['start']=[dict(op=op,node='bad',type=type_id,args=[])]
    with pytest.raises(ValueError,match='outside a loop Body'): CppEmitter().generate(ir)


@pytest.mark.parametrize('loop',['For Loop','While Loop','For Each Integer'])
@pytest.mark.parametrize('control',['Break Loop','Continue Loop'])
def test_conditional_control_skips_sequence_tail_and_done_runs_once(native,loop,control):
    b=build(loop,control)
    b.graph['links']=[x for x in b.graph['links'] if x['from']!=['loop','Body']]
    b.add('counter','Get Variable',Name='counter'); b.add('add','Add',B=1)
    b.connect('counter','Value','add','A')
    b.add('inc','Set Variable',Name='counter'); b.connect('add','Value','inc','Value').connect('loop','Body','inc','In')
    chain(b,'inc',('sequence','Sequence',{}))
    b.add('branch','Branch'); b.connect('sequence','First','branch','In')
    b.add('equal','Nearly Equal',B=2); b.connect('counter','Value','equal','A').connect('equal','Value','branch','Condition')
    b.connect('branch','True','control','In')
    b.add('log','Print Log',Message='visited'); b.connect('sequence','Then','log','In')
    chain(b,'log',('sum_store','Set Variable',{'Name':'sum'}))
    b.add('sum_get','Get Variable',Name='sum'); b.add('sum_add','Add')
    b.connect('sum_get','Value','sum_add','A').connect('counter','Value','sum_add','B').connect('sum_add','Value','sum_store','Value')
    if loop=='While Loop':
        b.add('less','Less',B=5); b.connect('counter','Value','less','A').connect('less','Value','loop','Condition')
    s=default_scene(); s['variables']={'counter':0.,'sum':0.}
    result=run(native,b,s)
    assert result['logs']==['visited']*(1 if control=='Break Loop' else 4)+['done']
    assert result['variables']['sum']==(1 if control=='Break Loop' else 13)
    assert result['variables']['counter']==(2 if control=='Break Loop' else 5)


def test_inner_break_then_outer_continue_preserves_scopes(native):
    b=GraphBuilder(); b.add('start','On Game Start')
    chain(b,'start',('outer','For Each Integer',{'Array':[10,20,30]}))
    b.add('inner','For Each Integer',Array=[1,2,3]); b.connect('outer','Body','inner','In')
    b.add('sum','Integer Add'); b.connect('outer','Item','sum','A').connect('inner','Item','sum','B')
    b.add('store','Set Integer Variable',Name='last'); b.connect('sum','Value','store','Value').connect('inner','Body','store','In')
    chain(b,'store',('break','Break Loop',{}))
    b.add('continue','Continue Loop'); b.connect('inner','Done','continue','In')
    b.add('done','Print Log',Message='outer done'); b.connect('outer','Done','done','In')
    result=run(native,b,default_scene())
    assert result['variables']['last']['value']==31 and result['logs']==['outer done']


def test_foreach_uses_snapshot_despite_continue_and_array_mutation(native):
    b=GraphBuilder(); b.add('start','On Game Start')
    chain(b,'start',('loop','For Each Integer',{}))
    b.add('items','Get Integer Array Variable',Name='items'); b.connect('items','Value','loop','Array')
    b.add('clear','Set Integer Array Variable',Name='items',Value=[]); b.connect('loop','Body','clear','In')
    chain(b,'clear',('last','Set Integer Variable',{'Name':'last'}),('continue','Continue Loop',{}))
    b.connect('loop','Item','last','Value')
    s=default_scene(); s['variables']={'items':{'type':'array<int>','value':[7,11,19]}}
    result=run(native,b,s)
    assert result['variables']['items']['value']==[] and result['variables']['last']['value']==19


def test_action_function_break_continue_return_and_caller_item(native):
    f=new_function('Find positive',inputs=[dict(name='Items',type='array<int>',default=[])],outputs=[dict(name='Result',type='int')])
    body=GraphBuilder(functions=[f],function=f['id']); body.add('entry','Function Input')
    chain(body,'entry',('loop','For Each Integer',{})); body.connect('entry','Items','loop','Array')
    body.add('positive','Integer Less',A=0); body.connect('loop','Item','positive','B')
    body.add('branch','Branch'); body.connect('loop','Body','branch','In').connect('positive','Value','branch','Condition')
    body.add('continue','Continue Loop'); body.connect('branch','False','continue','In')
    body.add('result','Function Output'); body.connect('branch','True','result','In').connect('loop','Item','result','Result')
    body.add('missing','Function Output',Result=-1); body.connect('loop','Done','missing','In'); f['graph']=body.graph
    b=GraphBuilder(functions=[f]); b.add('start','On Game Start')
    chain(b,'start',('loop','For Each Integer',{'Array':[3,7]}))
    b.add('call','Find positive',Items=[-1,0,5,8]); b.connect('loop','Body','call','In')
    chain(b,'call',('set','Set Integer Variable',{'Name':'last'}))
    b.add('sum','Integer Add'); b.connect('loop','Item','sum','A').connect('call','Result','sum','B').connect('sum','Value','set','Value')
    result=run(native,b); assert result['variables']['last']['value']==12
    # A break in the helper reaches its fallback return, never breaks the caller.
    f['graph']['nodes']=[dict(n,type=2005) if n['id']=='continue' else n for n in f['graph']['nodes']]
    result=run(native,b); assert result['variables']['last']['value']==6


@pytest.mark.parametrize('control',['Break Loop','Continue Loop'])
def test_control_in_empty_loop_does_not_run(native,control):
    b=build('For Loop',control)
    next(n for n in b.graph['nodes'] if n['id']=='loop')['values']['Count']=0
    assert run(native,b)['logs']==['done']


def test_continue_while_keeps_budget_and_original_node(native):
    b=build('While Loop','Continue Loop')
    a,z=native(b.graph,frames=0,extra=['--budget','4'])
    assert a.returncode==z.returncode==1 and json.loads(a.stderr)==json.loads(z.stderr)
    error=json.loads(a.stderr); assert error['node']=='loop' and 'budget' in error['message']


def test_raw_ir_control_cannot_escape_function_or_event(native,tmp_path):
    from editor.core.document import save_json
    # Native fixture builds the current interpreter, then --ir selects the invalid IR.
    import subprocess
    b=build(); a,z=native(b.graph,frames=0); assert a.returncode==z.returncode==0
    executable=Path(a.args[0])
    ir=b.compile(); bad=dict(op='break',node='bad',type=2005,args=[])
    for label in ('event','function'):
        candidate=deepcopy(ir)
        if label=='event': candidate['events']['start']=[bad]
        else:
            candidate['functions']={'1000000':dict(inputs=[],outputs=[],body=[bad])}
            candidate['events']['start'][0]['body']=[dict(op='function_call',node='call',type=1000000,args=[],outputs=[])]
        file=tmp_path/(label+'.json'); save_json(file,candidate)
        result=subprocess.run([str(executable),'--ir',str(file),'--frames','0'],capture_output=True,text=True,encoding='utf-8',timeout=20)
        error=json.loads(result.stderr)
        assert result.returncode==1 and error['node']=='bad' and 'loop Body' in error['message']
