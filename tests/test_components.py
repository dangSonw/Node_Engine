from copy import deepcopy
import json
import pytest
from editor.core.components import new_component, signatures, node_id, edit_instance, with_components
from editor.core.document import default_scene
from editor.core.scene import validate_scene
from editor.core.registry import Registry
from editor.core.builder import GraphBuilder
from editor.core.compiler import compile_graph, GraphError
from editor.core.codegen import CppEmitter
from tests.test_native import native


def health():
    return {'id':1, 'name':'Health', 'properties':[
        {'id':1, 'name':'Points', 'type':'int', 'default':100},
        {'id':2, 'name':'Title', 'type':'string', 'default':'Nhân vật\0A'}]}


def scene_with(definitions):
    s=default_scene(); s['component_definitions']=definitions
    return s


def run_pair(native, b, scene, frames=0):
    a,c=native(b.graph,scene=scene,frames=frames)
    assert a.returncode==c.returncode==0,a.stderr+c.stderr
    left,right=json.loads(a.stdout),json.loads(c.stdout)
    assert left==right
    return left


@pytest.mark.parametrize('edit',[
    {'id':True}, {'id':4000}, {'name':'\0'}, {'properties':{}},
    {'properties':[{'id':0,'name':'A','type':'int'}]},
    {'properties':[{'id':1,'name':'A','type':'int','default':True}]},
    {'properties':[{'id':1,'name':'A','type':'map<int>','default':{'x':1.2}}]},
])
def test_bad_component_schema_is_rejected(edit):
    d=health(); d.update(edit)
    with pytest.raises(ValueError): signatures([d])


@pytest.mark.parametrize('instances',[
    {'01':{}}, {'2':{}}, {'1':{'enabled':1}}, {'1':{'properties':{'3':1}}},
    {'1':{'properties':{'1':1.5}}}, {'1':{'properties':[]}}, [],
])
def test_bad_component_instance_is_rejected(instances):
    s=scene_with([health()]); s['entities'][0]['components']=instances
    with pytest.raises(ValueError): validate_scene(s)


def test_property_ids_survive_rename_and_registry_isolation():
    d=health(); s=scene_with([d]); b=GraphBuilder(component_definitions=[d])
    b.add('start','On Game Start'); b.add('add','Add Health Component'); b.connect('start','Out','add','In')
    b.add('get','Get Health Points'); b.add('save','Set Integer Variable',Name='points')
    b.connect('add','Out','save','In'); b.connect('get','Value','save','Value')
    original=deepcopy(b.graph)
    d['name']='Vitality'; d['properties'][0]['name']='Remaining'
    ir=compile_graph(b.graph,s,b.registry)
    emitter = CppEmitter()
    assert 'GetComponentProperty<std::int64_t>' in emitter.generate(ir)
    assert emitter.registry.by_name('Get Vitality Remaining').id == node_id(1, 'get', 1)
    assert b.graph==original
    with pytest.raises(GraphError,match='Unavailable'): compile_graph(b.graph,default_scene(),b.registry)
    assert not any(n.component_id for n in Registry().nodes.values())
    base=Registry()
    extended=with_components(base,[health()])
    assert len(extended.nodes)==len(base.nodes)+6+2*len(health()['properties'])


def test_native_component_lifecycle_clone_query_and_snapshot(native):
    d=health(); s=scene_with([d]); b=GraphBuilder(component_definitions=[d])
    b.add('start','On Game Start'); previous='start'
    def action(nid,name,**values):
        nonlocal previous
        b.add(nid,name,**values); b.connect(previous,'Out',nid,'In'); previous=nid
    action('add','Add Health Component')
    action('set','Set Health Points',Value=75)
    action('again','Add Health Component')
    action('clone','Clone Entity',Name='Copy')
    action('clonepoints','Set Health Points',Value=42); b.connect('clone','Entity','clonepoints','Entity')
    action('disable','Set Health Enabled',Enabled=False); b.connect('clone','Entity','disable','Entity')
    b.add('all','Find Entities With Health',EnabledOnly=False)
    action('storeall','Set Entity Array Variable',Name='all'); b.connect('all','Value','storeall','Value')
    b.add('active','Find Entities With Health')
    action('storeactive','Set Entity Array Variable',Name='active'); b.connect('active','Value','storeactive','Value')
    b.add('points','Get Health Points')
    action('save','Set Integer Variable',Name='points'); b.connect('points','Value','save','Value')
    action('remove','Remove Health Component'); action('removeagain','Remove Health Component')
    b.add('has','Has Health Component')
    action('savehas','Set Boolean Variable',Name='has'); b.connect('has','Value','savehas','Value')
    state=run_pair(native,b,s)
    values={k:v['value'] for k,v in state['variables'].items()}
    assert values=={'all':['player','spawned_1'],'active':['player'],'points':75,'has':False}
    copied=next(e for e in state['scene']['entities'] if e['id']=='spawned_1')
    assert copied['components']['1']=={'enabled':False,'properties':{'1':42,'2':'Nhân vật\0A'}}
    reloaded=run_pair(native,GraphBuilder(component_definitions=[d]),state['scene'])
    assert reloaded==state


def test_all_component_value_types_and_copy_independence(native):
    scalar={'float':2.5,'int':2**60+3,'bool':True,'string':'Xin chào\0Z',
            'vec3':[1.5,-2.,3.],'vec2':[4.5,-6.],'vec4':[1.,2.,3.,4.],
            'quat':[0.,0.,.5,.5],
            'mat4':[1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,2.,3.,4.,1.],
            'entity':'player'}
    samples=dict(scalar)
    samples.update({f'array<{t}>':[v] for t,v in scalar.items()})
    samples.update({f'map<{t}>':{'khóa':v} for t,v in scalar.items()})
    samples.update({f'set<{t}>':[v] for t,v in scalar.items()})
    properties=[{'id':i+1,'name':f'P{i}','type':t,'default':v} for i,(t,v) in enumerate(samples.items())]
    d={'id':3999,'name':'Data','properties':properties}; s=scene_with([d]); s=edit_instance(s,'player',3999,'add')
    b=GraphBuilder(component_definitions=[d]); b.add('start','On Game Start'); b.add('clone','Clone Entity')
    b.connect('start','Out','clone','In'); previous='clone'
    for i,p in enumerate(properties):
        nid=f'set{i}'; b.add(nid,f'Set Data P{i}',Value=p['default']); b.connect(previous,'Out',nid,'In')
        b.add(f'get{i}', f'Get Data P{i}')
        b.connect(f'get{i}', 'Value', nid, 'Value')
        b.connect('clone','Entity',nid,'Entity'); previous=nid
    state=run_pair(native,b,s)
    entities=state['scene']['entities']
    assert entities[0]['components']==entities[1]['components']
    assert len(entities[0]['components']['3999']['properties'])==40


def test_component_missing_access_reports_graph_node(native):
    d=health(); b=GraphBuilder(component_definitions=[d]); b.add('start','On Game Start')
    b.add('get','Get Health Points'); b.add('save','Set Integer Variable',Name='points')
    b.connect('start','Out','save','In'); b.connect('get','Value','save','Value')
    a,c=native(b.graph,scene=scene_with([d]),frames=0)
    assert a.returncode==c.returncode==1
    assert 'get' in a.stderr and 'get' in c.stderr and 'lacks component' in a.stderr


def test_native_component_collections_are_independent_after_clone(native):
    d = {'id': 2, 'name': 'Inventory', 'properties': [
        {'id': 1, 'name': 'Items', 'type': 'array<string>', 'default': ['coin']},
        {'id': 2, 'name': 'Counts', 'type': 'map<int>', 'default': {'coin': 1}}]}
    s = edit_instance(scene_with([d]), 'player', 2, 'add')
    b = GraphBuilder(component_definitions=[d])
    for nid, name, values in [('start', 'On Game Start', {}), ('clone', 'Clone Entity', {}),
                              ('items', 'Set Inventory Items', {'Value': ['gem']}),
                              ('counts', 'Set Inventory Counts', {'Value': {'gem': 3}})]:
        b.add(nid, name, **values)
    b.connect('start', 'Out', 'clone', 'In').connect('clone', 'Out', 'items', 'In').connect('items', 'Out', 'counts', 'In')
    b.connect('clone', 'Entity', 'items', 'Entity').connect('clone', 'Entity', 'counts', 'Entity')
    state = run_pair(native, b, s)
    entities = {e['id']: e for e in state['scene']['entities']}
    assert entities['player']['components']['2']['properties'] == {'1': ['coin'], '2': {'coin': 1}}
    assert entities['spawned_1']['components']['2']['properties'] == {'1': ['gem'], '2': {'gem': 3}}


def test_component_access_in_functions_requires_scene_context(native):
    from editor.core.functions import new_function
    f = new_function('Read health', [{'name': 'Target', 'type': 'entity'}], [{'name': 'Points', 'type': 'int'}])
    d = health()
    fb = GraphBuilder(functions=[f], function=f['id'], component_definitions=[d])
    fb.add('entry', 'Function Input'); fb.add('get', 'Get Health Points'); fb.add('return', 'Function Output')
    fb.connect('entry', 'Out', 'return', 'In').connect('entry', 'Target', 'get', 'Entity').connect('get', 'Value', 'return', 'Points')
    f['graph'] = fb.graph
    b = GraphBuilder(functions=[f], component_definitions=[d])
    b.add('start', 'On Game Start'); b.add('read', 'Read health', Target='player'); b.add('save', 'Set Integer Variable', Name='points')
    b.connect('start', 'Out', 'read', 'In').connect('read', 'Out', 'save', 'In').connect('read', 'Points', 'save', 'Value')
    s = edit_instance(scene_with([d]), 'player', 1, 'add')
    assert run_pair(native, b, s)['variables']['points']['value'] == 100
    f['pure'] = True
    f['graph']['links'] = f['graph']['links'][1:]
    b.graph['links'] = [b.graph['links'][2], {'from': ['start', 'Out'], 'to': ['save', 'In']}]
    with pytest.raises(GraphError, match='[Pp]ure'):
        compile_graph(b.graph, s)


def test_component_mutations_are_immediate_inside_flecs_event_handler(native):
    from editor.core.events import new_event
    event = new_event('Mutate'); event['id'] = 100001
    d = health(); b = GraphBuilder(event_definitions=[event], component_definitions=[d])
    b.add('start', 'On Game Start'); b.add('send', 'Send Mutate', Recipient='player')
    b.connect('start', 'Out', 'send', 'In')
    b.add('handler', 'On Mutate', Receiver='player')
    previous = 'handler'
    for nid, name, values in [('add', 'Add Health Component', {}), ('set', 'Set Health Points', {'Value': 33}),
                             ('save', 'Set Integer Variable', {'Name': 'read'}), ('remove', 'Remove Health Component', {}),
                             ('absent', 'Set Boolean Variable', {'Name': 'has'}), ('readd', 'Add Health Component', {})]:
        b.add(nid, name, **values); b.connect(previous, 'Out', nid, 'In'); previous = nid
    b.add('get', 'Get Health Points'); b.connect('get', 'Value', 'save', 'Value')
    b.add('has', 'Has Health Component'); b.connect('has', 'Value', 'absent', 'Value')
    state = run_pair(native, b, scene_with([d]))
    assert state['variables']['read']['value'] == 33 and state['variables']['has']['value'] is False
    assert state['scene']['entities'][0]['components']['1']['properties']['1'] == 100
