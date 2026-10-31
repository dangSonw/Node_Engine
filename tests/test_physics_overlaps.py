"""Oriented overlap arrays through real interpreted/generated graph execution."""
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene
from editor.core.physics import default_body
from tests.test_native import native
from tests.test_physics_scene import chain, run

QUERIES = [('Physics Overlap Box', {'Half Extents':[.15,2,.15],'Rotation':[0,0,45]}),
           ('Physics Overlap Capsule', {'Radius':.2,'Half Height':2,'Rotation':[0,0,45]})]


def scene():
    result=default_scene()
    result['entities'].append(dict(id='rig',name='Rig',position=[0,0,0],rotation=[0,0,0],scale=[1,1,1]))
    for nid,position in [('zeta',[-1,1,0]),('alpha',[0,0,0]),('corner',[1,1,0]),('sensor',[-.5,.5,0])]:
        item=dict(id=nid,name=nid,position=position,rotation=[0,0,0],scale=[1,1,1],
                  layer=31 if nid=='alpha' else 0,
                  rigid_body=dict(default_body(),motion='static',half_extents=[.05,.05,.05],sensor=nid=='sensor'))
        if nid=='alpha': item['parent']='rig'
        result['entities'].append(item)
    return result


def store(b,last,query,name):
    end=chain(b,last,(name,'Set Entity Array Variable',{'Name':name}))
    b.connect(query,'Value',end,'Value')
    return end


@pytest.mark.parametrize('label,values',QUERIES+[('Physics Overlap Sphere',{'Radius':1.6})])
def test_overlap_array_is_sorted_composable_and_recomputed_after_destruction(native,label,values):
    b=GraphBuilder(); b.add('start','On Game Start'); b.add('query',label,**values)
    b.add('all',label,Sensors=True,**values)
    last=store(b,'start','query','solids'); last=store(b,last,'all','captured')
    b.add('read','Get Entity Array Variable',Name='captured')
    chain(b,last,('each','For Each Entity',{})); b.connect('read','Value','each','Array')
    b.add('destroy','Destroy Entity'); b.connect('each','Body','destroy','In').connect('each','Item','destroy','Entity')
    b.add('after','Set Entity Array Variable',Name='after')
    b.connect('each','Done','after','In').connect('all','Value','after','Value')
    result=run(native,b,scene()); v=result['variables']
    solids=['alpha','corner','zeta'] if label.endswith('Sphere') else ['alpha','zeta']
    assert v['solids']['value']==solids
    assert v['captured']['value']==sorted(solids+['sensor'])
    assert v['after']['value']==[]
    assert set(result['physics']['bodies'])==({'corner'} if 'corner' not in solids else set())


@pytest.mark.parametrize('label,values',QUERIES)
def test_overlap_observes_parent_activity_filters_clone_and_body_enable(native,label,values):
    b=GraphBuilder(); b.add('start','On Game Start'); b.add('query',label,Mask=2**31,**values)
    last=store(b,'start','query','initial')
    for name,operation,settings in [
        ('moved','Set Position',{'Entity':'rig','Value':[5,0,0]}),
        ('returned','Set Position',{'Entity':'rig','Value':[0,0,0]}),
        ('inactive','Set Entity Active',{'Entity':'rig','Active':False}),
        ('active','Set Entity Active',{'Entity':'rig','Active':True}),
        ('disabled','Set Body Simulation Enabled',{'Entity':'alpha','Enabled':False}),
        ('enabled','Set Body Simulation Enabled',{'Entity':'alpha','Enabled':True}),
        ('wrong_layer','Set Entity Layer',{'Entity':'alpha','Layer':0}),
        ('restored_layer','Set Entity Layer',{'Entity':'alpha','Layer':31}),
    ]:
        last=chain(b,last,(name+'_change',operation,settings)); last=store(b,last,'query',name)
    last=chain(b,last,('clone','Clone Entity',{'Source':'alpha'}))
    b.add('excluding',label,Mask=2**31,Exclude='alpha',**values)
    last=store(b,last,'excluding','clones')
    last=chain(b,last,('delete_clone','Destroy Entity',{})); b.connect('clone','Entity','delete_clone','Entity')
    store(b,last,'excluding','cleared')
    v=run(native,b,scene())['variables']
    for key in ('initial','returned','active','enabled','restored_layer'): assert v[key]['value']==['alpha']
    for key in ('moved','inactive','disabled','wrong_layer','cleared'): assert v[key]['value']==[]
    assert v['clones']['value']==['spawned_1']


@pytest.mark.parametrize('label,values',[
    ('Physics Overlap Box',{'Half Extents':[0,.5,.5]}),
    ('Physics Overlap Box',{'Center':[1e10,0,0]}),
    ('Physics Overlap Capsule',{'Radius':0}),
    ('Physics Overlap Capsule',{'Half Height':0}),
    ('Physics Overlap Box',{'Mask':-1}),
    ('Physics Overlap Capsule',{'Mask':4294967296}),
])
def test_empty_scene_still_reports_invalid_query_at_original_node(native,label,values):
    b=GraphBuilder(); b.add('start','On Game Start'); b.add('invalid',label,**values)
    store(b,'start','invalid','result')
    a,z=native(b.graph,frames=0)
    assert a.returncode==z.returncode==1
    error=json.loads(a.stderr); assert error==json.loads(z.stderr)
    assert error['node']=='invalid' and ('out of range' in error['message'] or 'mask' in error['message'])
