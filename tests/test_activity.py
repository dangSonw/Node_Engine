"""Activity inheritance, layers and suspended delivery use real native runtimes."""
from copy import deepcopy
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.events import new_event
from editor.core.scene import validate_scene, is_active, set_entity_property
from tests.test_entities import make_scene, pair
from tests.test_native import native


@pytest.mark.parametrize('property,value', [
    ('active', 1), ('active', 'false'), ('active', None),
    ('layer', -1), ('layer', 32), ('layer', True), ('layer', 1.0), ('layer', '1'),
])
def test_activity_schema_validation(property, value):
    scene = make_scene()
    with pytest.raises(ValueError): set_entity_property(scene, 'child', property, value)
    assert 'active' not in scene['entities'][1] and 'layer' not in scene['entities'][1]


def test_activity_hierarchy_layers_clone_and_reload(native):
    scene = make_scene()
    scene['entities'][0].update(active=False, layer=31)
    scene['entities'][1]['layer'] = 31
    scene['entities'][2].update(active=False, layer=1)
    assert not is_active(scene, 'child') and is_active(scene, 'other')
    b = GraphBuilder(); b.add('start', 'On Game Start'); previous = 'start'
    def action(nid, name, **values):
        nonlocal previous
        b.add(nid, name, **values); b.connect(previous, 'Out', nid, 'In'); previous = nid
    def read(nid, name, variable, **values):
        b.add(nid, name, **values); action(nid+'save', 'Set '+variable+' Variable', Name=nid)
        b.connect(nid, 'Value', nid+'save', 'Value')
    read('effective', 'Is Entity Active', 'Boolean', Entity='child')
    read('local', 'Get Entity Active Self', 'Boolean', Entity='child')
    read('activeonly', 'Find Entities By Layer', 'Entity Array', Layer=31)
    read('all', 'Find Entities By Layer', 'Entity Array', Layer=31, ActiveOnly=False)
    action('clone', 'Clone Entity', Source='player')
    action('detach', 'Set Parent', Child='child', Parent='')
    read('detached', 'Is Entity Active', 'Boolean', Entity='child')
    read('grandchild', 'Is Entity Active', 'Boolean', Entity='grandchild')
    action('layer', 'Set Entity Layer', Entity='child', Layer=1)
    read('layerread', 'Get Entity Layer', 'Integer', Entity='child')
    action('enable', 'Set Entity Active', Active=True)
    read('missing', 'Is Entity Active', 'Boolean', Entity='missing')
    result = pair(native, b, scene)
    values = {k:v['value'] for k,v in result['variables'].items()}
    assert values == dict(effective=False, local=True, activeonly=[], all=['child','player'],
                         detached=True, grandchild=False, layerread=1, missing=False)
    clone = next(e for e in result['scene']['entities'] if e['id']=='spawned_1')
    assert clone['active'] is False and clone['layer']==31
    validate_scene(result['scene'])
    assert pair(native, GraphBuilder(), result['scene']) == result


def counter(b, event, name='ticks'):
    b.add(event+'get', 'Get Integer Variable', Name=name)
    b.add(event+'add', 'Integer Add', B=1)
    b.add(event+'save', 'Set Integer Variable', Name=name)
    b.connect(event,'Out',event+'save','In')
    b.connect(event+'get','Value',event+'add','A')
    b.connect(event+'add','Value',event+'save','Value')


def at_frame(b, frame, action, **values):
    prefix = f'f{frame}'
    b.add(prefix, 'On Update'); b.add(prefix+'count', 'Get Frame Count')
    b.add(prefix+'eq', 'Nearly Equal', B=frame, Epsilon=0)
    b.add(prefix+'if','Branch'); b.add(prefix+'do',action,**values)
    b.connect(prefix,'Out',prefix+'if','In'); b.connect(prefix+'count','Value',prefix+'eq','A')
    b.connect(prefix+'eq','Value',prefix+'if','Condition'); b.connect(prefix+'if','True',prefix+'do','In')
    return prefix+'do'


@pytest.mark.parametrize('operation', ['active', 'parent'])
def test_timer_freezes_under_inactive_ancestor_and_resumes_without_backlog(native, operation):
    scene = make_scene(); scene['entities'][3]['active'] = False
    scene['variables'] = {'ticks': {'type':'int','value':0}}
    b = GraphBuilder(); b.add('start','On Game Start'); b.add('timer','Start Timer',Name='tick',Seconds=.5,Repeat=True,Owner='child')
    b.connect('start','Out','timer','In'); b.add('tick','On Timer Finished',Receiver='child'); counter(b,'tick')
    if operation=='active':
        at_frame(b,2,'Set Entity Active',Active=False)
        at_frame(b,6,'Set Entity Active',Active=True)
    else:
        at_frame(b,2,'Set Parent',Child='child',Parent='other')
        at_frame(b,6,'Set Parent',Child='child',Parent='player')
    for frames,expected in [(5,1),(8,2)]:
        a,c = native(b.graph,scene=scene,frames=frames,extra=['--dt','.25'])
        assert a.returncode==c.returncode==0, a.stderr+c.stderr
        result=json.loads(a.stdout); assert result==json.loads(c.stdout)
        assert result['variables']['ticks']['value']==expected
        assert result['timers'][0]['remaining']==.5
        assert result['timers'][0].get('suspended',False)==(frames==5)
        assert result['timers'][0]['paused'] is False


def test_manual_timer_pause_is_independent_of_entity_suspension(native):
    scene = make_scene(); scene['entities'][0]['active']=False
    scene['variables'] = {'ticks':{'type':'int','value':0}}
    b = GraphBuilder(); b.add('start','On Game Start'); last='start'
    for nid,name,values in [
        ('timer','Start Timer',{'Name':'tick','Seconds':.5,'Owner':'child'}),
        ('pause','Pause Timer',{'Name':'tick','Owner':'child'}),
        ('resume','Resume Timer',{'Name':'tick','Owner':'child'}),
        ('pauseagain','Pause Timer',{'Name':'tick','Owner':'child'}),
        ('enable','Set Entity Active',{'Active':True}),
    ]:
        b.add(nid,name,**values); b.connect(last,'Out',nid,'In'); last=nid
    b.add('tick','On Timer Finished',Receiver='child'); counter(b,'tick')
    at_frame(b,6,'Resume Timer',Name='tick',Owner='child')
    for frames,expected in [(5,0),(8,1)]:
        a,c = native(b.graph,scene=scene,frames=frames,extra=['--dt','.25'])
        assert a.returncode==c.returncode==0, a.stderr+c.stderr
        result=json.loads(a.stdout); assert result==json.loads(c.stdout)
        assert result['variables']['ticks']['value']==expected
        if frames==5:
            assert result['timers'][0]['paused'] and result['timers'][0]['remaining']==.5
        else: assert not result['timers']


@pytest.mark.parametrize('trigger', ['event','timer'])
def test_activity_toggle_inside_callback_invalidates_remaining_delivery(native, trigger):
    definition = new_event('Ping')
    b = GraphBuilder(event_definitions=[definition]); b.add('start','On Game Start')
    name = 'Send Ping' if trigger=='event' else 'Start Timer'
    values = {'Recipient':'child'} if trigger=='event' else {'Owner':'child','Name':'tick','Seconds':0}
    b.add('send',name,**values); b.connect('start','Out','send','In')
    for nid in ['a','z']:
        b.add(nid, 'On Ping' if trigger=='event' else 'On Timer Finished', Receiver='child')
    b.add('off','Set Entity Active',Active=False)
    b.add('on','Set Entity Active',Active=True)
    b.add('bad','Print Log',Message='stale callback')
    b.connect('a','Out','off','In'); b.connect('off','Out','on','In'); b.connect('z','Out','bad','In')
    assert pair(native,b,make_scene(),frames=1)['logs']==[]


def test_queued_events_cancel_on_deactivation_and_inactive_receivers_ignore_broadcast(native):
    definition = new_event('Ping')
    b = GraphBuilder(event_definitions=[definition]); b.add('start','On Game Start'); last='start'
    for nid,name,values in [
        ('queue','Send Ping',{'Recipient':'child'}),
        ('off','Set Entity Active',{'Active':False}),
        ('broadcast','Broadcast Ping',{}),
        ('on','Set Entity Active',{'Active':True}),
        ('send','Send Ping',{'Recipient':'child'}),
    ]:
        b.add(nid,name,**values); b.connect(last,'Out',nid,'In'); last=nid
    for owner in ['child','other','']:
        nid=owner or 'scene'
        b.add(nid,'On Ping',Receiver=owner); b.add(nid+'log','Print Log',Message=nid)
        b.connect(nid,'Out',nid+'log','In')
    result=pair(native,b,make_scene())
    assert result['logs']==['scene','other','child']
    assert all(s['enabled'] for s in result['events']['subscriptions'])


@pytest.mark.parametrize('node,values,message', [
    ('Set Entity Layer',{'Layer':-1},'between 0 and 31'),
    ('Set Entity Layer',{'Layer':32},'between 0 and 31'),
    ('Set Entity Active',{'Entity':'missing'},'Missing entity'),
])
def test_activity_runtime_errors_keep_origin_node(native,node,values,message):
    b=GraphBuilder(); b.add('start','On Game Start'); b.add('bad',node,**values); b.connect('start','Out','bad','In')
    a,c=native(b.graph,scene=make_scene(),frames=0)
    assert a.returncode==c.returncode==1
    assert json.loads(a.stderr)==json.loads(c.stderr)
    assert json.loads(a.stderr)['node']=='bad' and message in json.loads(a.stderr)['message']
