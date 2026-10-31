"""Migrated functions execute through the production interpreter and generated C++."""
from copy import deepcopy
from editor.core.builder import GraphBuilder
from editor.core.data_types import TYPES, SCALARS
from editor.core.function_edits import migrate_signature
from editor.core.functions import new_function
from editor.core.registry import Registry
from tests.test_native import native
from tests.test_core import node,link
from tests.test_functions import graph,port,assert_parity
from tests.test_function_edits import fixture,renamed
from tests.test_physics_scene import chain
from tests.test_scene_session import key,replay


def test_nested_call_migrations_preserve_native_behavior(native):
    doc,pure,action=fixture()
    before=assert_parity(*native(doc,frames=0))
    for f in (pure,action):
        candidate,origins=renamed(f); doc,_=migrate_signature(doc,f['id'],candidate,origins)
    after=assert_parity(*native(doc,frames=0))
    assert after==before
    assert after['variables']['result']==after['variables']['total']=={'type':'int','value':14}


def test_reordered_renamed_ports_preserve_all_value_types(native):
    f=new_function('Identity',[port(f'p{i}',t) for i,t in enumerate(TYPES)],
                   [port(f'r{i}',t) for i,t in enumerate(TYPES)],True)
    f['graph']['links']=[link('entry',f'p{i}','return',f'r{i}') for i in range(len(TYPES))]
    scalar_values={'float':1.25,'int':9007199254740993,'bool':True,'string':'Việt\x00語',
                   'vec3':[1,2,3],'vec2':[4,5],'vec4':[1,2,3,4],
                   'quat':[0,0,.5,.5],
                   'mat4':[1,0,0,0,0,1,0,0,0,0,1,0,2,3,4,1],
                   'entity':'player'}
    values=[]
    for t in TYPES:
        if t in SCALARS:
            values.append(deepcopy(scalar_values[t]))
        else:
            element=t[t.index('<')+1:-1]
            values.append([deepcopy(scalar_values[element])] if t.startswith(('array<','set<'))
                          else {'a':deepcopy(scalar_values[element])})
    nodes=[node('start',1001),node('call',f['id'],**{f'p{i}':v for i,v in enumerate(values)})]
    links=[]; previous='start'
    for i,t in enumerate(TYPES):
        spec=next(s for s in Registry().nodes.values() if s.variable_type==t and s.variable_access=='write')
        nodes.append(node(f'set{i}',spec.id,Name=f'v{i}'))
        links += [link(previous,'Out',f'set{i}','In'),link('call',f'r{i}',f'set{i}','Value')]; previous=f'set{i}'
    candidate=deepcopy(f); origins={}
    for side in ('inputs','outputs'):
        origins[side]={'new_'+p['name']:p['name'] for p in f[side]}
        candidate[side]=[{**p,'name':'new_'+p['name']} for p in reversed(f[side])]
    edited,_=migrate_signature(graph(nodes,links,[f]),f['id'],candidate,origins)
    result=assert_parity(*native(edited,frames=0))
    for i,t in enumerate(TYPES):
        assert result['variables'][f'v{i}']==(values[i] if t=='float' else {'type':t,'value':values[i]})


def test_compatible_type_change_and_new_default_execute(native):
    f=new_function('Identity',[port('A','float')],[port('B','float')],True)
    f['graph']['links']=[link('entry','A','return','B')]
    candidate=deepcopy(f); candidate['inputs'][0].update(type='int',default=9); candidate['outputs'][0]['type']='int'
    doc=graph([node('old',f['id'],A=0.)],functions=[f]); doc,_=migrate_signature(doc,f['id'],candidate)
    doc['nodes'] += [node('new',f['id']),node('start',1001),node('sum',4030),node('set',3111,Name='result')]
    doc['links']=[link('old','B','sum','A'),link('new','B','sum','B'),link('sum','Value','set','Value'),link('start','Out','set','In')]
    assert assert_parity(*native(doc,frames=0))['variables']['result']=={'type':'int','value':18}


def test_migrated_delayed_function_survives_save_and_fresh_process_load(native,tmp_path):
    f=new_function('Delayed value',[dict(name='Number',type='int',default=0)],[port('Result','int')])
    body=GraphBuilder(functions=[f],function=f['id']); body.add('entry','Function Input')
    chain(body,'entry',('wait','Delay',{'Seconds':.3}),('return','Function Output',{}))
    body.connect('entry','Number','return','Result'); f['graph']=body.graph
    b=GraphBuilder(functions=[f]); b.add('start','On Game Start'); chain(b,'start',('storage','Open Save Storage',{'Game ID':'signature-test'}))
    b.add('B','On Key Pressed',Filter='B'); chain(b,'B',('call','Delayed value',{'Number':7}),('result','Set Integer Variable',{'Name':'result'}))
    b.connect('call','Result','result','Value'); key(b,'S','Save Game'); key(b,'L','Load Game')
    candidate,origins=renamed(f); edited,_=migrate_signature(b.graph,f['id'],candidate,origins)
    store=tmp_path/'save'; common=['--dt','.1','--save-root',str(store)]
    saved=assert_parity(*native(edited,frames=2,extra=[*common,*replay(tmp_path/'keys.json',[(0,'B',True),(1,'B',False),(1,'S',True)])]))
    assert saved['persistence']['success'] and len(saved['continuations']['tasks'])==1 and 'result' not in saved['variables']
    slot=next(store.rglob('slot-*.json')); raw=slot.read_bytes()
    restored=assert_parity(*native(edited,frames=8,extra=[*common,*replay(tmp_path/'keys.json',[(0,'L',True)])]))
    assert restored['persistence']['success'] and restored['variables']['result']=={'type':'int','value':7}
    assert not restored['continuations']['tasks'] and slot.read_bytes()==raw
