"""One query, six scoped results, shared by interpreted and generated graphs."""
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.codegen import CppEmitter, generate_adapters
from editor.core.compiler import GraphError
from editor.core.document import default_scene
from editor.core.functions import new_function, ENTRY, RETURN
from editor.core.physics import default_body
from tests.test_native import native
from tests.test_physics_scene import chain, run

QUERIES = ['Physics Raycast','Physics Sphere Cast','Physics Box Cast','Physics Capsule Cast']
FIELDS = [('Hit','bool','Boolean'),('Entity','entity','Entity'),('Point','vec3','Vector3'),
          ('Normal','vec3','Vector3'),('Fraction','float',''),('Distance','float','')]


def scene():
    result = default_scene()
    result['entities'].append(dict(id='floor',name='Floor',position=[0,-.5,0],rotation=[0,0,0],
        scale=[1,1,1],rigid_body=dict(default_body(),motion='static',half_extents=[10,.5,10])))
    return result


def store(b, query, previous=None, prefix=''):
    last = previous or query
    for field, _, label in FIELDS:
        nid = prefix + field.lower()
        last = chain(b,last,(nid,'Set '+(label+' ' if label else '')+'Variable',{'Name':nid}))
        b.connect(query,field,last,'Value')
    return last


@pytest.mark.parametrize('label',QUERIES)
def test_six_outputs_share_one_action_and_require_its_execution_path(label):
    b=GraphBuilder(); b.add('start','On Game Start'); chain(b,'start',('query',label,{})); store(b,'query')
    ir=b.compile(scene()); source=CppEmitter().generate(ir)
    function=b.registry.by_name(label).function
    assert source.count('rt::'+function+'(')==1
    adapters=generate_adapters()
    assert 'std::get<5>' in source and 'dispatch_results' in adapters and '<built-in' not in adapters
    b.add('update','On Update'); chain(b,'update',('leaked','Set Vector3 Variable',{'Name':'leaked'}))
    b.connect('query','Normal','leaked','Value')
    with pytest.raises(GraphError,match='after that action on its Out path'): b.compile(scene())


@pytest.mark.parametrize('label,fraction',list(zip(QUERIES,[.5,.45,.45,.4])))
def test_hit_results_survive_scene_mutation_and_misses_clear_every_output(native,label,fraction):
    b=GraphBuilder(); b.add('start','On Game Start')
    chain(b,'start',('query',label,{}),('remove','Remove Rigid Body',{'Entity':'floor'}))
    last=store(b,'query','remove')
    chain(b,last,('miss',label,{})); store(b,'miss',prefix='miss_')
    result=run(native,b,scene(),0); v=result['variables']
    assert v['hit']['value'] is True and v['entity']['value']=='floor'
    assert v['point']['value'][1] == pytest.approx(0,abs=1e-4)
    assert v['normal']['value'] == pytest.approx([0,1,0],abs=1e-4)
    assert v['fraction'] == pytest.approx(fraction,abs=1e-4)
    assert v['distance'] == pytest.approx(fraction*10,abs=1e-4)
    assert v['miss_hit']['value'] is False and v['miss_entity']['value']==''
    assert v['miss_point']['value']==v['miss_normal']['value']==[0,0,0]
    assert v['miss_fraction']==1 and v['miss_distance']==10


@pytest.mark.parametrize('label,values',[
    ('Physics Raycast',{'Displacement':[0,0,0]}),
    ('Physics Sphere Cast',{'Radius':-1}),
    ('Physics Box Cast',{'Half Extents':[0,.5,.5]}),
    ('Physics Capsule Cast',{'Half Height':0}),
    ('Physics Sphere Cast',{'Mask':-1}),
])
def test_invalid_query_reports_original_node_even_in_empty_scene(native,label,values):
    b=GraphBuilder(); b.add('start','On Game Start'); chain(b,'start',('bad_query',label,values))
    a,z=native(b.graph,frames=0)
    assert a.returncode==z.returncode==1
    error=json.loads(a.stderr); assert error==json.loads(z.stderr)
    assert error['node']=='bad_query' and ('out of range' in error['message'] or 'nonzero length' in error['message'] or 'mask' in error['message'])


def test_rotated_cast_and_layer_sensor_exclusion_follow_live_scene_edits(native):
    s=scene(); s['entities'][1]['layer']=31; s['entities'][1]['rigid_body']['sensor']=True
    b=GraphBuilder(); b.add('start','On Game Start')
    values={'Half Extents':[.25,1,.5],'Rotation':[0,0,90],'Mask':2**31,'Sensors':True}
    chain(b,'start',('query','Physics Box Cast',values)); last=store(b,'query')
    chain(b,last,('excluded','Physics Box Cast',dict(values,Exclude='floor'))); last=store(b,'excluded',prefix='exclude_')
    chain(b,last,('disable','Set Entity Active',{'Entity':'floor','Active':False}),('inactive','Physics Box Cast',values)); store(b,'inactive',prefix='inactive_')
    result=run(native,b,s,0); v=result['variables']
    assert v['hit']['value'] and v['fraction']==pytest.approx(.475,abs=1e-4)
    assert not v['exclude_hit']['value'] and not v['inactive_hit']['value']


def test_multi_output_action_inside_function_uses_its_local_frame(native):
    outputs=[{'name':name,'type':kind} for name,kind,_ in FIELDS]
    f=new_function('Ground Probe',outputs=outputs)
    inner=GraphBuilder(functions=[f],function=f['id']); inner.graph=f['graph']
    entry=next(n['id'] for n in inner.graph['nodes'] if n['type']==ENTRY)
    ret=next(n['id'] for n in inner.graph['nodes'] if n['type']==RETURN)
    inner.graph['links']=[]
    inner.add('query','Physics Raycast'); inner.connect(entry,'Out','query','In').connect('query','Out',ret,'In')
    for field,_,_ in FIELDS: inner.connect('query',field,ret,field)
    f['graph']=inner.graph
    b=GraphBuilder(functions=[f]); b.add('start','On Game Start'); chain(b,'start',('call','Ground Probe',{})); store(b,'call')
    result=run(native,b,scene(),0)
    assert result['variables']['entity']['value']=='floor' and result['variables']['distance']==5
