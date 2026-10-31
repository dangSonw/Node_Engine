from copy import deepcopy
import json
import pytest
from editor.core.compiler import compile_graph, GraphError
from editor.core.data_types import TYPES, SCALARS, default_value
from editor.core.functions import new_function, signatures, ENTRY, RETURN
from tests.test_core import node, link
from tests.test_native import native


def port(name, kind):
    return {'name':name, 'type':kind}


def graph(nodes, links=(), functions=()):
    return {'version':1, 'nodes':nodes, 'links':list(links), 'functions':list(functions)}


def double_function():
    f = new_function('Double', [port('Number','int')], [port('Result','int')], True)
    f['graph'] = graph([node('entry', ENTRY), node('twice',4032,B=2), node('return',RETURN)],
        [link('entry','Number','twice','A'), link('twice','Value','return','Result')])
    return f


def action_function(double):
    f = new_function('Increment and return', [port('Number','int')], [port('Result','int')], definitions=[double])
    f['graph'] = graph([node('entry',ENTRY), node('double',double['id']), node('set',3111,Name='total'),
                       node('return',RETURN)],
        [link('entry','Out','set','In'),link('entry','Number','double','Number'),
         link('double','Result','set','Value'),link('set','Out','return','In'),
         link('double','Result','return','Result')])
    return f


def assert_parity(a, b):
    assert a.returncode == b.returncode == 0, a.stderr+b.stderr
    assert json.loads(a.stdout) == json.loads(b.stdout)
    return json.loads(a.stdout)


def test_native_nested_typed_functions(native):
    double = double_function()
    action = action_function(double)
    g = graph([node('start',1001), node('call',action['id'],Number=9007199254740993),
               node('set',3111,Name='result')],
              [link('start','Out','call','In'),link('call','Out','set','In'),link('call','Result','set','Value')],
              [double,action])
    result = assert_parity(*native(g, frames=0))
    assert result['variables'] == {k:{'type':'int','value':18014398509481986} for k in ('total','result')}


def test_native_all_function_parameter_and_result_types(native):
    from editor.core.registry import Registry
    functions = []
    # Cover all builtin types while respecting the 32-port signature limit.
    for offset in range(0, len(TYPES), 20):
        group = list(enumerate(TYPES))[offset:offset+20]
        f = new_function(f'Identity {offset}', [port(f'p{i}',t) for i,t in group],
                         [port(f'r{i}',t) for i,t in group], True, definitions=functions)
        f['graph']['links'] = [link('entry',f'p{i}','return',f'r{i}') for i,t in group]
        functions.append(f)
    scalar_values = {'float':1.25,'int':9007199254740993,'bool':True,'string':'Việt\x00語',
                     'vec3':[1,2,3],'vec2':[4,5],'vec4':[1,2,3,4],
                     'quat':[0,0,.5,.5],
                     'mat4':[1,0,0,0,0,1,0,0,0,0,1,0,2,3,4,1],
                     'entity':'player'}
    values = []
    for t in TYPES:
        if t in SCALARS:
            values.append(deepcopy(scalar_values[t]))
        else:
            element=t[t.index('<')+1:-1]
            values.append([deepcopy(scalar_values[element])] if t.startswith(('array<','set<'))
                          else {'a':deepcopy(scalar_values[element])})
    nodes = [node('start',1001)]
    for group,f in enumerate(functions):
        nodes.append(node(f'call{group}',f['id'],**{f'p{i}':values[i] for i in range(group*20,min(len(TYPES),(group+1)*20))}))
    links = []
    registry = Registry()
    prev = 'start'
    for i,t in enumerate(TYPES):
        spec = next(s for s in registry.nodes.values() if s.variable_type==t and s.variable_access=='write' and not s.variable_scope)
        nodes.append(node(f'set{i}',spec.id,Name=f'v{i}'))
        links.extend([link(prev,'Out',f'set{i}','In'),link(f'call{i//20}',f'r{i}',f'set{i}','Value')])
        prev=f'set{i}'
    result = assert_parity(*native(graph(nodes,links,functions), frames=0))
    for i,t in enumerate(TYPES):
        assert result['variables'][f'v{i}'] == (values[i] if t=='float' else {'type':t,'value':values[i]})


def test_native_return_inside_nested_loop_and_call_scope(native):
    # Both functions reuse the same local node IDs; the caller's Item must survive.
    f = new_function('First positive', [port('Items','array<int>')], [port('Found','int')])
    f['graph'] = graph([node('entry',ENTRY),node('loop',2301),node('less',4033,A=0),node('branch',2001),
                       node('yes',RETURN),node('no',RETURN,Found=-1)],
        [link('entry','Out','loop','In'),link('entry','Items','loop','Array'),
         link('loop','Body','branch','In'),link('loop','Item','less','B'),link('less','Value','branch','Condition'),
         link('branch','True','yes','In'),link('loop','Item','yes','Found'),link('loop','Done','no','In')])
    g = graph([node('start',1001),node('loop',2301,Array=[3,7]),node('call',f['id'],Items=[-1,0,5,9]),
               node('sum',4030),node('set',3111,Name='last')],
        [link('start','Out','loop','In'),link('loop','Body','call','In'),link('call','Out','set','In'),
         link('loop','Item','sum','A'),link('call','Found','sum','B'),link('sum','Value','set','Value')],[f])
    result = assert_parity(*native(g, frames=0))
    assert result['variables']['last']['value'] == 12


def test_native_function_error_and_shared_budget(native):
    f = double_function()
    g = graph([node('start',1001),node('call',f['id'],Number=9223372036854775807),node('set',3111)],
              [link('start','Out','set','In'),link('call','Result','set','Value')],[f])
    for extra, expected in [((),f'{f["id"]}/twice'), (('--budget','1'),f'{f["id"]}/twice')]:
        a,b=native(g, frames=0, extra=extra)
        assert a.returncode == b.returncode == 1
        assert json.loads(a.stderr)==json.loads(b.stderr)
        assert json.loads(a.stderr)['node']==expected


def test_native_zero_argument_and_void_function_fallthrough(native):
    pure=new_function('Greeting',outputs=[port('Text','string')],pure=True)
    pure['graph']['nodes'][1]['values']={'Text':'Không tham số'}
    action=new_function('Say greeting')
    action['graph']=graph([node('entry',ENTRY),node('text',pure['id']),node('print',27001)],
                         [link('entry','Out','print','In'),link('text','Text','print','Message')])
    # A void action may end without a Function Output; both backends return ().
    root=graph([node('start',1001),node('one',action['id']),node('two',action['id'])],
               [link('start','Out','one','In'),link('one','Out','two','In')],[pure,action])
    result=assert_parity(*native(root,frames=0))
    assert result['logs']==['Không tham số','Không tham số']


@pytest.mark.parametrize('case', ['impure','context','cycle','entry','return','scope','missing','type'])
def test_reject_invalid_functions(case):
    f=double_function()
    g=graph([node('start',1001)],functions=[f])
    if case=='impure':
        f['graph']['nodes'].append(node('set',3111))
    elif case=='context':
        f['graph']['nodes'].append(node('time',5001))
    elif case=='cycle':
        f['graph']['nodes'].append(node('recurse',f['id']))
    elif case=='entry':
        f['graph']['nodes'].append(node('extra',ENTRY))
    elif case=='return':
        f['pure']=False
    elif case=='scope':
        f=action_function(f)
        g['functions'].append(f)
        g['nodes'] += [node('call',f['id']),node('set',3111)]
        g['links'] = [link('start','Out','set','In'),link('call','Result','set','Value')]
    elif case=='missing':
        f['graph']['nodes'].append(node('unknown',1234567))
    elif case=='type':
        f['inputs'][0]['type']='float'
    with pytest.raises(GraphError):
        compile_graph(g)


def test_function_rename_keeps_calls_and_signature_validation():
    f=double_function()
    g=graph([],functions=[f])
    before=compile_graph(g)
    f['name']='Gấp đôi'
    after=compile_graph(g)
    assert before['functions'][str(f['id'])]['body']==after['functions'][str(f['id'])]['body']
    duplicate=deepcopy(f)
    duplicate['id']+=1
    with pytest.raises(ValueError,match='unique'):
        signatures([f,duplicate])
