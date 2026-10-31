"""Typed captured selection/shuffle in real interpreted and generated graphs."""
import json
import pytest
from editor.core.document import default_scene
from editor.core.compiler import GraphError
from tests.test_native import native
from tests.test_physics_scene import chain,run
from tests.test_random import graph,value

CASES=[('float','Float',[1.,2.,2.,4.]),('int','Integer',[-2**63,7,7,2**63-1]),
       ('bool','Boolean',[False,True,True,False]),('string','String',['kiếm','thuốc','thuốc','']),
       ('vec3','Vector3',[[1,2,3],[0,0,0],[0,0,0],[-1,0,1]]),('entity','Entity',['player','','player','missing'])]


def test_all_types_indices_capture_and_nonmutation(native):
    b=graph(); end='seed'; scene=default_scene(); scene['variables']={}
    for kind,label,items in CASES:
        scene['variables'][kind]={'type':f'array<{kind}>','value':items}
        b.add('get_'+kind,f'Get {label} Array Variable',Name=kind)
        end=chain(b,end,(kind+'_seed','Set Random Seed',{'Seed':0}))
        for operation in ('item','weighted','shuffle'):
            nid=kind+'_'+operation
            name=f'Random {label} Item' if operation=='item' else f'Random Weighted {label} Item' if operation=='weighted' else f'Shuffle {label} Array'
            end=chain(b,end,(nid,name,{'Weights':[0,3,0,0]} if operation=='weighted' else {}))
            b.connect('get_'+kind,'Value',nid,'Array')
            setter=f'Set {label} Array Variable' if operation=='shuffle' else 'Set Variable' if kind=='float' else f'Set {label} Variable'
            end=chain(b,end,(nid+'_store',setter,{'Name':nid})); b.connect(nid,'Value',end,'Value')
            if operation!='shuffle':
                end=chain(b,end,(nid+'_index','Set Integer Variable',{'Name':nid+'_index'})); b.connect(nid,'Index',end,'Value')
                end=chain(b,end,(nid+'_copy',setter,{'Name':nid+'_copy'})); b.connect(nid,'Value',end,'Value')
    state=run(native,b,scene)
    for kind,label,items in CASES:
        assert value(state,kind)==items
        for operation,index in [('item',3),('weighted',1)]:
            assert value(state,kind+'_'+operation+'_index')==index
            assert value(state,kind+'_'+operation)==value(state,kind+'_'+operation+'_copy')==items[index]
        assert sorted(value(state,kind+'_shuffle'))==sorted(items)


def test_singleton_and_empty_shuffle_do_not_advance(native):
    b=graph(42); end='seed'
    for nid,label,values in [('one','Random String Item',{'Array':['only']}),
        ('weighted','Random Weighted Integer Item',{'Array':[1,2,3],'Weights':[0,1e-320,0]}),
        ('empty','Shuffle Boolean Array',{'Array':[]}),('single','Shuffle String Array',{'Array':['only']})]:
        end=chain(b,end,(nid,label,values))
    state=run(native,b)
    assert state['random']['state']=='000000000000002a'


@pytest.mark.parametrize('label,values,message',[
    ('Random Integer Item',{'Array':[]},'nonempty'),
    ('Random Weighted Integer Item',{'Array':[],'Weights':[]},'nonempty'),
    ('Random Weighted Integer Item',{'Array':[1,2],'Weights':[1]},'matching'),
    ('Random Weighted Integer Item',{'Array':[1,2],'Weights':[0,0]},'positive'),
    ('Random Weighted Integer Item',{'Array':[1,2],'Weights':[-1,2]},'nonnegative')])
def test_selection_errors_identify_source_node(native,label,values,message):
    b=graph(); chain(b,'seed',('bad',label,values))
    a,z=native(b.graph,frames=0)
    assert a.returncode==z.returncode==1 and json.loads(a.stderr)==json.loads(z.stderr)
    error=json.loads(a.stderr); assert error['node']=='bad' and message in error['message']


def test_collection_outputs_need_execution_and_match_types():
    b=graph(); b.add('pick','Random String Item',Array=['a'])
    end=chain(b,'seed',('store','Set String Variable',{'Name':'picked'})); b.connect('pick','Value',end,'Value')
    with pytest.raises(GraphError): b.compile()
    b.connect('seed','Out','pick','In')
    b.graph['links']=[e for e in b.graph['links'] if e!={'from':['seed','Out'],'to':['store','In']}]
    b.connect('pick','Out','store','In')
    b.compile()
    b.graph['nodes'][-1]['type']=b.registry.by_name('Set Integer Variable').id
    with pytest.raises(GraphError): b.compile()
