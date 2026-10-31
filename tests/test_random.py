"""Seeded graph draws, reference outputs, captured values and native parity."""
import json
import math
import pytest
from editor.core.builder import GraphBuilder
from editor.core.compiler import GraphError
from editor.core.document import default_scene
from tests.test_native import native
from tests.test_physics_scene import chain,run


def graph(seed=0):
    b=GraphBuilder(); b.add('start','On Game Start')
    chain(b,'start',('seed','Set Random Seed',{'Seed':seed}))
    return b


def sample(b,previous,nid,label,kind='Integer',**values):
    end=chain(b,previous,(nid,label,values),(nid+'_store','Set '+kind+' Variable' if kind!='Float' else 'Set Variable',{'Name':nid}))
    b.connect(nid,'Value',end,'Value')
    return end


def value(state,name):
    value=state['variables'][name]
    return value['value'] if isinstance(value,dict) else value


def test_reference_sequence_and_reseed_capture(native):
    b=graph(); end='seed'
    for i in range(3): end=sample(b,end,'n'+str(i),'Random Integer',Minimum=-(2**63),Maximum=2**63-1)
    end=chain(b,end,('reset','Set Random Seed',{'Seed':0}))
    end=sample(b,end,'again','Random Integer',Minimum=-(2**63),Maximum=2**63-1)
    chain(b,end,('copy','Set Integer Variable',{'Name':'copy'})); b.connect('again','Value','copy','Value')
    state=run(native,b)
    words=[0xe220a8397b1dcdaf,0x6e789e6aa1b965f4,0x06c45d188009454f]
    assert [value(state,'n'+str(i)) for i in range(3)]==[n-2**63 for n in words]
    assert value(state,'again')==value(state,'copy')==value(state,'n0')
    assert state['random']=={'algorithm':'splitmix64-v1','seed':0,'state':'9e3779b97f4a7c15'}


@pytest.mark.parametrize('seed',[-2**63,-1,42,2**63-1])
def test_seed_roundtrip_ranges_and_no_draw_endpoints(native,seed):
    b=graph(seed)
    b.add('get','Get Random Seed'); end=chain(b,'seed',('saved_seed','Set Integer Variable',{'Name':'seed'}))
    b.connect('get','Value','saved_seed','Value')
    end=sample(b,end,'fixed','Random Integer',Minimum=-9,Maximum=-9)
    end=sample(b,end,'constant','Random Float','Float',Minimum=1.25,Maximum=1.25)
    end=sample(b,end,'no','Random Boolean','Boolean',Probability=0)
    end=sample(b,end,'yes','Random Boolean','Boolean',Probability=1)
    end=sample(b,end,'wide','Random Float','Float',Minimum=-1.7976931348623157e308,Maximum=1.7976931348623157e308)
    end=sample(b,end,'small','Random Integer',Minimum=-5,Maximum=5)
    end=sample(b,end,'chance','Random Boolean','Boolean',Probability=.25)
    state=run(native,b)
    assert value(state,'seed')==seed and value(state,'fixed')==-9
    assert value(state,'constant')==1.25 and value(state,'no') is False and value(state,'yes') is True
    assert -1.7976931348623157e308<=value(state,'wide')<1.7976931348623157e308
    assert -5<=value(state,'small')<=5 and isinstance(value(state,'chance'),bool)
    assert state['random']['state']==f'{(seed+3*0x9e3779b97f4a7c15)%(2**64):016x}'


@pytest.mark.parametrize('label,values,message',[
    ('Random Integer',{'Minimum':5,'Maximum':4},'Minimum'),
    ('Random Float',{'Minimum':2,'Maximum':1},'Minimum'),
    ('Random Boolean',{'Probability':-0.1},'Probability'),
    ('Random Boolean',{'Probability':1.1},'Probability')])
def test_invalid_draw_reports_node(native,label,values,message):
    b=graph(); chain(b,'seed',('bad',label,values))
    a,z=native(b.graph,frames=0)
    assert a.returncode==z.returncode==1 and json.loads(a.stderr)==json.loads(z.stderr)
    assert json.loads(a.stderr)['node']=='bad' and message in json.loads(a.stderr)['message']


def test_random_output_requires_execution_scope():
    b=graph(); b.add('draw','Random Float'); chain(b,'seed',('store','Set Variable',{'Name':'x'}))
    b.connect('draw','Value','store','Value')
    with pytest.raises(GraphError): b.compile(default_scene())


def test_integer_rejection_and_adjacent_float_bounds(native):
    b=graph(); end=sample(b,'seed','first','Random Integer',Minimum=-(2**63),Maximum=0)
    end=sample(b,end,'second','Random Integer',Minimum=-(2**63),Maximum=0)
    state=run(native,b)
    assert value(state,'first')==-(2**63)+0xe220a8397b1dcdaf%(2**63+1)
    assert value(state,'second')==-(2**63)+0xf88bb8a8724c81ec%(2**63+1)
    assert state['random']['state']==f'{(4*0x9e3779b97f4a7c15)%(2**64):016x}'
    sample(b,end,'tiny','Random Float','Float',Minimum=1.,Maximum=1.0000000000000002)
    assert value(run(native,b),'tiny')==1.


def test_vector_reference_axis_order_and_constants(native):
    b=graph()
    end=sample(b,'seed','box','Random Vector','Vector3',Minimum=[-2,7,10],Maximum=[2,7,20])
    end=sample(b,end,'constant','Random Vector','Vector3',Minimum=[3,2,1],Maximum=[3,2,1])
    end=sample(b,end,'after','Random Float','Float')
    chain(b,end,('copy','Set Vector3 Variable',{'Name':'copy'})); b.connect('box','Value','copy','Value')
    state=run(native,b)
    u=[(w>>11)*2**-53 for w in [0xe220a8397b1dcdaf,0x6e789e6aa1b965f4,0x06c45d188009454f]]
    assert value(state,'box')==value(state,'copy')==pytest.approx([-2+4*u[0],7,10+10*u[1]])
    assert value(state,'constant')==[3,2,1] and value(state,'after')==u[2]
    assert state['random']['state']==f'{(3*0x9e3779b97f4a7c15)%(2**64):016x}'


def test_vector_extreme_finite_and_adjacent_bounds(native):
    b=graph(); largest=1.7976931348623157e308
    sample(b,'seed','wide','Random Vector','Vector3',Minimum=[-largest,1,0],Maximum=[largest,math.nextafter(1,2),5e-324])
    point=value(run(native,b),'wide')
    assert math.isfinite(point[0]) and -largest<=point[0]<largest
    assert point[1:]==[1,0]


def test_direction_reference_capture_and_reseed(native):
    b=graph(); end=sample(b,'seed','direction','Random Direction','Vector3')
    end=sample(b,end,'later','Random Direction','Vector3')
    end=chain(b,end,('copy','Set Vector3 Variable',{'Name':'copy'})); b.connect('direction','Value','copy','Value')
    end=chain(b,end,('reseed','Set Random Seed',{'Seed':0}))
    sample(b,end,'again','Random Direction','Vector3')
    state=run(native,b)
    y=1-2*((0xe220a8397b1dcdaf>>11)*2**-53)
    angle=2*math.pi*((0x6e789e6aa1b965f4>>11)*2**-53)
    radius=math.sqrt((1-y)*(1+y))
    assert value(state,'direction')==value(state,'copy')==value(state,'again')
    assert value(state,'direction')==pytest.approx([radius*math.cos(angle),y,radius*math.sin(angle)],abs=2e-15)
    assert sum(x*x for x in value(state,'direction'))==pytest.approx(1,abs=2e-15)
    assert state['random']['state']==f'{(2*0x9e3779b97f4a7c15)%(2**64):016x}'


@pytest.mark.parametrize('axis',range(3))
def test_vector_invalid_axis_reports_source_node(native,axis):
    b=graph(); high=[1,1,1]; high[axis]=-1
    chain(b,'seed',('bad','Random Vector',{'Minimum':[0,0,0],'Maximum':high}))
    a,z=native(b.graph,frames=0)
    assert a.returncode==z.returncode==1 and json.loads(a.stderr)==json.loads(z.stderr)
    assert json.loads(a.stderr)['node']=='bad' and 'every axis' in json.loads(a.stderr)['message']


@pytest.mark.parametrize('name',['Random Vector','Random Direction'])
def test_random_vectors_require_execution_scope(name):
    b=graph(); b.add('draw',name)
    chain(b,'seed',('store','Set Vector3 Variable',{'Name':'position'})); b.connect('draw','Value','store','Value')
    with pytest.raises(GraphError): b.compile()
