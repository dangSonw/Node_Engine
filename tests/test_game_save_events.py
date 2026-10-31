"""Persistence result handlers run in the real interpreter and generated game."""
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.codegen import CppEmitter
from editor.core.compiler import GraphError
from editor.core.document import default_scene
from editor.core.events import new_event
from editor.core.functions import new_function
from tests.test_native import native

GAME = 'game-save-event-tests'
SLOT = 'Tiến độ số 1'
EVENTS = ['On Save Completed', 'On Save Failed', 'On Load Completed', 'On Load Failed']


def request_graph(operation='Save Game', slot=SLOT, definitions=()):
    b = GraphBuilder(event_definitions=definitions)
    b.add('start', 'On Game Start')
    b.add('open', 'Open Save Storage', **{'Game ID':GAME})
    b.add('request', operation, Slot=slot)
    b.add('queued', 'Print Log', Message='queued')
    b.connect('start','Out','open','In').connect('open','Out','request','In').connect('request','Out','queued','In')
    return b


def listener(b, node, label):
    b.add(node, label)
    b.add(node+'_label', 'Print Log', Message=label)
    b.add(node+'_slot', 'Print Log')
    b.connect(node,'Out',node+'_label','In').connect(node+'_label','Out',node+'_slot','In')
    b.connect(node,'Slot',node+'_slot','Message')
    last=node+'_slot'
    if 'Failed' in label:
        b.add(node+'_error','Print Log')
        b.connect(last,'Out',node+'_error','In').connect(node,'Error',node+'_error','Message')
        last=node+'_error'
    return last


def pair(native, tmp_path, b, frames=0, scene=None, extra=()):
    a,c=native(b.graph, frames=frames, scene=scene,
               extra=['--project-root',str(tmp_path),'--save-root',str(tmp_path/'saves'),*extra])
    assert a.returncode==c.returncode==0,a.stderr+c.stderr
    result=json.loads(a.stdout)
    assert result==json.loads(c.stdout)
    assert result['events']['pending']==0
    return result


@pytest.mark.parametrize('label', EVENTS)
def test_payload_scope_and_builtin_registry_survive_custom_definitions(label):
    definition=new_event('Unrelated')
    b=GraphBuilder(event_definitions=[definition]); listener(b,'result',label)
    ir=b.compile()
    assert ir['events']['persistence'][0]['event']==23101+EVENTS.index(label)
    assert 'rt::BindGameSaveEvent' in CppEmitter().generate(ir)
    b.add('start','On Game Start'); b.add('leak','Print Log')
    b.connect('start','Out','leak','In').connect('result','Slot','leak','Message')
    with pytest.raises(GraphError,match='inside that persistence event handler'): b.compile()
    function=new_function('Action')
    inner=GraphBuilder(functions=[function],function=function['id'])
    inner.add('entry','Function Input'); inner.add('result',label); function['graph']=inner.graph
    with pytest.raises(GraphError,match='Lifecycle events belong'):
        GraphBuilder(functions=[function]).compile()


@pytest.mark.parametrize('operation,slot,label', [
    ('Save Game', SLOT, 'On Save Completed'),
    ('Save Game', '', 'On Save Failed'),
    ('Load Game', SLOT, 'On Load Failed'),
])
def test_one_result_per_accepted_request_with_exact_payload(native,tmp_path,operation,slot,label):
    b=request_graph(operation,slot)
    for i,event in enumerate(EVENTS): listener(b,'result'+str(i),event)
    state=pair(native,tmp_path,b)
    assert state['logs'][:3]==['queued',label,slot]
    if 'Failed' in label:
        assert state['logs'][3]==state['persistence']['error']
        assert not state['persistence']['success']
    else:
        assert len(state['logs'])==3 and state['persistence']['success']
    assert state['frame']==0


def test_completion_can_queue_load_for_next_boundary_and_emit_custom_event(native,tmp_path):
    event=new_event('Ping')
    b=request_graph(definitions=[event])
    last=listener(b,'a_saved','On Save Completed')
    b.add('load','Load Game',Slot=SLOT); b.connect(last,'Out','load','In')
    b.add('ping','Send Ping'); b.connect('load','Out','ping','In')
    listener(b,'z_saved','On Save Completed')
    listener(b,'loaded','On Load Completed')
    b.add('custom','On Ping'); b.add('custom_log','Print Log',Message='custom')
    b.connect('custom','Out','custom_log','In')
    b.add('update','On Update'); b.add('changed','Set Variable',Name='score',Value=99.)
    b.connect('update','Out','changed','In')
    b.add('update_log','Print Log',Message='update'); b.connect('changed','Out','update_log','In')
    scene=default_scene(); scene['variables']['score']=0.
    state=pair(native,tmp_path,b,frames=1,scene=scene)
    assert state['logs']==['queued','On Save Completed',SLOT,'On Save Completed',SLOT,
                           'custom','update','On Load Completed',SLOT]
    assert state['frame']==0 and state['variables']['score']==0
    assert state['persistence']['success']
    path=tmp_path/'saves'/GAME/('slot-'+SLOT.encode().hex()+'.json')
    saved=json.loads(path.read_bytes())['checkpoint']
    assert saved['events']['queue']==[]
    assert len(saved['events']['bindings']['events'])==3


def test_rejected_duplicate_request_does_not_emit_failure_event(native,tmp_path):
    b=request_graph(); b.add('duplicate','Load Game',Slot='missing')
    b.connect('queued','Out','duplicate','In')
    b.add('accepted','Set Boolean Variable',Name='duplicate_accepted')
    b.connect('duplicate','Out','accepted','In').connect('duplicate','Accepted','accepted','Value')
    for i,event in enumerate(EVENTS): listener(b,'result'+str(i),event)
    state=pair(native,tmp_path,b)
    assert state['variables']['duplicate_accepted']['value'] is False
    assert state['logs']==['queued','On Save Completed',SLOT]


@pytest.mark.parametrize('loop', [False,True])
def test_handler_fault_is_graph_error_after_successful_save(native,tmp_path,loop):
    b=request_graph(); b.add('saved','On Save Completed')
    b.add('handler_fault','While Loop' if loop else 'Assert',Condition=loop)
    b.connect('saved','Out','handler_fault','In')
    listener(b,'failure','On Save Failed')
    a,c=native(b.graph,frames=0,extra=['--project-root',str(tmp_path),'--save-root',str(tmp_path/'saves'),'--budget','60'])
    assert a.returncode==c.returncode==1
    error=json.loads(a.stderr)
    assert error==json.loads(c.stderr) and error['node']=='handler_fault'
    assert ('budget' if loop else 'Assert') in error['message']
    path=tmp_path/'saves'/GAME/('slot-'+SLOT.encode().hex()+'.json')
    assert json.loads(path.read_bytes())['checkpoint']['clock']['frame']==0


def test_rejected_request_without_storage_has_no_result_event(native,tmp_path):
    b=request_graph(); b.graph['nodes']=[n for n in b.graph['nodes'] if n['id']!='open']
    b.graph['links']=[e for e in b.graph['links'] if 'open' not in (e['from'][0],e['to'][0])]
    b.connect('start','Out','request','In')
    for i,event in enumerate(EVENTS): listener(b,'result'+str(i),event)
    state=pair(native,tmp_path,b)
    assert state['logs']==['queued'] and not state['persistence']['success']
    assert 'Open Save Storage' in state['persistence']['error']
