"""Native typed selection and editable Switch routing, including suspended paths."""
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.compiler import GraphError
from editor.core.document import default_scene
from editor.core.functions import new_function
from editor.core.registry import Registry
from tests.test_native import native
from tests.test_physics_scene import chain,run


@pytest.mark.parametrize('label,value,cases,expected',[
    ('Switch Integer',9223372036854775807,[-9223372036854775808,9223372036854775807],'1'),
    ('Switch Integer',9,[1,2],'default'),
    ('Switch String','đi\x00A',['đi','đi\x00A'],'1'),
    ('Switch String','a',['A','B'],'default'),
    ('Switch Integer',0,[],'default')])
def test_switch_routes_exactly_one_branch(native,label,value,cases,expected):
    b=GraphBuilder(); b.add('start','On Game Start')
    chain(b,'start',('switch',label,dict(Value=value,cases=[dict(id='c'+str(i),value=x) for i,x in enumerate(cases)])))
    for i in range(len(cases)):
        b.add('log'+str(i),'Print Log',Message=str(i)); b.connect('switch','Case c'+str(i),'log'+str(i),'In')
    b.add('default','Print Log',Message='default'); b.connect('switch','Default','default','In')
    assert run(native,b)['logs']==[expected]


def test_select_all_value_types_and_both_conditions(native):
    b=GraphBuilder(); b.add('start','On Game Start'); end='start'; expected={}
    values={'float':2.5,'int':9223372036854775807,'bool':True,'string':'Chọn\x00☀',
            'vec3':[1,2,3],'vec2':[4,5],'vec4':[1,2,3,4],
            'quat':[0,0,.5,.5],
            'mat4':[1,0,0,0,0,1,0,0,0,0,1,0,2,3,4,1],
            'entity':'player'}
    for spec in Registry().nodes.values():
        if spec.kind!='select': continue
        t=spec.outputs[0].type
        element=t[t.index('<')+1:-1] if '<' in t else t
        chosen=[values[element]] if t.startswith(('array<','set<')) else {'op':values[element]} if t.startswith('map<') else values[t]
        setter=next(s for s in b.registry.nodes.values() if s.variable_access=='write' and s.variable_type==t)
        for condition in (False,True):
            nid=f'select_{spec.id}_{int(condition)}'; name=nid+'_result'
            b.add(nid,spec.name,Condition=condition,**{'True':chosen,'False':spec.data_inputs[2].default})
            end=chain(b,end,(name,setter.name,{'Name':name})); b.connect(nid,'Value',end,'Value')
            value=chosen if condition else spec.data_inputs[2].default
            expected[name]=value if t=='float' else dict(type=t,value=value)
    assert run(native,b)['variables']==expected


def test_select_does_not_evaluate_unselected_errors(native):
    b=GraphBuilder(); b.add('start','On Game Start'); chain(b,'start',('set','Set Variable',{'Name':'selected'}))
    b.add('select','Select Float',Condition=True,**{'True':7.}); b.add('bad','Divide',A=1,B=0)
    b.connect('bad','Value','select','False').connect('select','Value','set','Value')
    result=run(native,b); assert result['variables']['selected']==7
    b.graph['nodes']=[n for n in b.graph['nodes'] if n['id']!='bad']; b.graph['links']=[l for l in b.graph['links'] if l['from'][0]!='bad']
    b.add('missing','Get Variable',Name='never_initialized'); b.connect('missing','Value','select','False')
    assert run(native,b)['variables']==result['variables']


def test_select_works_inside_pure_function(native):
    f=new_function('Choose integer',inputs=[dict(name='Flag',type='bool',default=False)],outputs=[dict(name='Result',type='int')],pure=True)
    body=GraphBuilder(functions=[f],function=f['id']); body.add('entry','Function Input'); body.add('return','Function Output')
    body.add('choose','Select Integer',**{'True':8,'False':9}); body.connect('entry','Flag','choose','Condition').connect('choose','Value','return','Result')
    f['graph']=body.graph; b=GraphBuilder(functions=[f]); b.add('start','On Game Start')
    chain(b,'start',('set','Set Integer Variable',{'Name':'result'})); b.add('call','Choose integer',Flag=True); b.connect('call','Result','set','Value')
    assert run(native,b)['variables']['result']['value']==8


def test_switch_function_returns_and_lazy_input(native):
    f=new_function('Route',inputs=[dict(name='Mode',type='string',default='go')],outputs=[dict(name='Result',type='int')])
    body=GraphBuilder(functions=[f],function=f['id']); body.add('entry','Function Input')
    chain(body,'entry',('switch','Switch String',dict(cases=[dict(id='go',value='go')]))); body.connect('entry','Mode','switch','Value')
    for port,value in [('Case go',10),('Default',20)]:
        nid=str(value); body.add(nid,'Function Output',Result=value); body.connect('switch',port,nid,'In')
    f['graph']=body.graph; b=GraphBuilder(functions=[f]); b.add('start','On Game Start')
    chain(b,'start',('call','Route',{}),('set','Set Integer Variable',{'Name':'result'})); b.connect('call','Result','set','Value')
    assert run(native,b)['variables']['result']['value']==10


def test_switch_break_continue_and_delayed_route_capture(native):
    b=GraphBuilder(); b.add('start','On Game Start'); chain(b,'start',('each','For Each Integer',{'Array':[0,1,2,3]}))
    b.add('switch','Switch Integer',cases=[dict(id='skip',value=0),dict(id='wait',value=1),dict(id='stop',value=2)])
    b.connect('each','Body','switch','In').connect('each','Item','switch','Value')
    b.add('continue','Continue Loop'); b.connect('switch','Case skip','continue','In')
    b.add('delay','Delay',Seconds=0); b.connect('switch','Case wait','delay','In')
    chain(b,'delay',('log','Print Log',{'Message':'delayed'}))
    b.add('break','Break Loop'); b.connect('switch','Case stop','break','In')
    b.add('bad','Print Log',Message='wrong'); b.connect('switch','Default','bad','In')
    b.add('done','Print Log',Message='done'); b.connect('each','Done','done','In')
    assert run(native,b,frames=1)['logs']==['delayed','done']


@pytest.mark.parametrize('cases',[[dict(id='a',value=1),dict(id='b',value=1)],[dict(id='a',value=1),dict(id='a',value=2)],
    [dict(id='a',value=True)],[dict(id='a',value=1.5)],[dict(id='a',value=2**63)],[dict(id='',value=0)],[dict(id='a',value=0,extra=0)]])
def test_switch_rejects_invalid_case_metadata(cases):
    b=GraphBuilder(); b.add('switch','Switch Integer'); b.graph['nodes'][0]['cases']=cases
    with pytest.raises(GraphError): b.compile()


def test_case_limit_and_unknown_deleted_ports():
    b=GraphBuilder(); b.add('switch','Switch Integer',cases=[dict(id=str(i),value=i) for i in range(256)])
    b.add('log','Print Log'); b.connect('switch','Case 255','log','In'); b.compile()
    b.graph['nodes'][0]['cases'].pop()
    with pytest.raises(GraphError,match='Unknown node or port'): b.compile()
