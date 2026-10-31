import json
import subprocess
import pytest
from editor.core.builder import GraphBuilder
from editor.core.codegen import CppEmitter
from editor.core.document import default_scene,save_json
from editor.core.events import new_event
from tests.test_native import native
from tests.test_physics_scene import chain,run


def graph():
    b=GraphBuilder()
    for nid,event in [('start','On Game Start'),('update','On Update'),('late','On Late Update'),('quit','On Application Quit')]:
        b.add(nid,event); chain(b,nid,(nid+'_log','Print Log',{'Message':nid}))
    return b


def test_quit_codegen_and_legacy_optional_phase():
    b=graph(); ir=b.compile(); assert ir['events']['quit'][0]['node']=='quit_log'
    source=CppEmitter().generate(ir); assert 'void OnQuit(rt::Ctx& ctx)' in source
    empty=GraphBuilder().compile(); assert 'quit' not in empty['events']
    assert 'void OnQuit(rt::Ctx& ctx)' in CppEmitter().generate(empty)


@pytest.mark.parametrize('phase,expected,frames',[
    ('start',['start','after request','quit'],0),
    ('update',['start','update','after request','late','quit'],1),
    ('late',['start','update','late','after request','quit'],1)])
def test_request_finishes_current_frame_and_quits_once(native,phase,expected,frames):
    b=graph(); chain(b,phase+'_log',('request','Quit Application',{}),('after','Print Log',{'Message':'after request'}))
    chain(b,'quit_log',('repeat','Quit Application',{}))
    result=run(native,b,frames=50)
    assert result['logs']==expected and result['frame']==frames


@pytest.mark.parametrize('frames',[0,2])
def test_frame_limit_dispatches_normal_quit(native,frames):
    result=run(native,graph(),frames=frames)
    assert result['logs']==['start']+['update','late']*frames+['quit']
    assert result['frame']==frames


def test_fixed_request_finishes_all_steps_of_current_frame(native):
    b=graph(); b.add('fixed','On Fixed Update')
    chain(b,'fixed',('fixed_log','Print Log',{'Message':'fixed'}),('request','Quit Application',{}))
    result=run(native,b,frames=50,extra=['--dt',str(1/30)])
    assert result['frame']==1 and result['logs']==['start','update','fixed','fixed','late','quit']


def test_quit_drains_custom_callbacks(native):
    event=new_event('Goodbye'); event['id']=100001
    b=GraphBuilder(event_definitions=[event]); b.add('quit','On Application Quit')
    chain(b,'quit',('send','Send Goodbye',{}),('log','Print Log',{'Message':'quit'}))
    b.add('receiver','On Goodbye'); chain(b,'receiver',('received','Print Log',{'Message':'delivered'}))
    assert run(native,b)['logs']==['quit','delivered']


def test_quit_does_not_wait_for_latent_work(native):
    b=graph(); chain(b,'start_log',('request','Quit Application',{}))
    chain(b,'quit_log',('wait','Delay',{'Seconds':0}),('late_log2','Print Log',{'Message':'not reached'}))
    ir=b.compile(); assert ir['events']['quit'][0]['op']=='continuation_entry'
    result=run(native,b,frames=20)
    assert result['frame']==0 and result['logs']==['start','quit']
    assert len(result['continuations']['tasks'])==1


def test_save_on_quit_and_completion_callbacks(native,tmp_path):
    b=graph(); chain(b,'start_log',('storage','Open Save Storage',{'Game ID':'quit-test'}))
    chain(b,'quit_log',('save','Save Game',{'Slot':'exit'}))
    b.add('saved','On Save Completed'); chain(b,'saved',('saved_log','Print Log',{'Message':'saved'}))
    result=run(native,b,frames=2,extra=['--save-root',str(tmp_path)])
    assert result['logs'][-2:]==['quit','saved'] and result['persistence']['success']
    saved=json.loads((tmp_path/'quit-test/slot-65786974.json').read_text('utf-8'))['checkpoint']
    assert saved['clock']['frame']==2 and not any('quit' in k for k in saved)


def test_load_is_rejected_during_quit_without_restarting(native,tmp_path):
    b=graph(); chain(b,'start_log',('storage','Open Save Storage',{'Game ID':'quit-load-test'}))
    chain(b,'quit_log',('load','Load Game',{}),('accepted','Set Boolean Variable',{'Name':'accepted'}),
          ('error_log','Print Log',{}))
    b.add('error','Get Save Error'); b.connect('load','Accepted','accepted','Value').connect('error','Value','error_log','Message')
    result=run(native,b,frames=0,extra=['--save-root',str(tmp_path)])
    assert result['variables']['accepted']==dict(type='bool',value=False)
    assert result['logs'][-1]=='Cannot load a game during application shutdown'


@pytest.mark.parametrize('loop',[False,True])
def test_quit_failure_reports_origin_and_budget(native,loop):
    b=GraphBuilder(); b.add('quit','On Application Quit')
    chain(b,'quit',('broken','While Loop',{'Condition':True}) if loop else ('broken','Assert',{'Condition':False,'Message':'quit failure'}))
    a,z=native(b.graph,frames=0,extra=['--budget','100'])
    assert a.returncode==z.returncode==1 and json.loads(a.stderr)==json.loads(z.stderr)
    assert json.loads(a.stderr)['node']=='broken'


def test_native_rejects_malformed_quit_phase(native,tmp_path):
    b=graph(); results=native(b.graph,frames=0); assert all(r.returncode==0 for r in results)
    ir=b.compile(); ir['events']['quit']={}; bad=tmp_path/'bad.ir.json'; save_json(bad,ir)
    args=list(results[0].args); args[args.index('--ir')+1]=str(bad)
    result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==1 and 'IR quit statements must be an array' in result.stderr


def test_save_callback_cycle_has_bounded_shutdown(native,tmp_path):
    b=GraphBuilder(); b.add('start','On Game Start'); chain(b,'start',('storage','Open Save Storage',{'Game ID':'quit-cycle'}))
    b.add('quit','On Application Quit'); chain(b,'quit',('first','Save Game',{}))
    b.add('saved','On Save Completed'); chain(b,'saved',('again','Save Game',{}))
    a,z=native(b.graph,frames=0,extra=['--save-root',str(tmp_path)])
    assert a.returncode==z.returncode==1 and json.loads(a.stderr)==json.loads(z.stderr)
    assert 'shutdown exceeded 64 pending save requests' in json.loads(a.stderr)['message']
    assert not list(tmp_path.rglob('.write-*.tmp'))


def test_quit_inside_action_function_returns_before_shutdown(native):
    from editor.core.functions import new_function
    f=new_function('Exit game'); f['graph']['nodes'].append(dict(id='request',type=26001,values={}))
    f['graph']['links']=[dict(**{'from':['entry','Out'],'to':['request','In']}),dict(**{'from':['request','Out'],'to':['return','In']})]
    b=GraphBuilder(functions=[f]); b.add('start','On Game Start'); b.add('quit','On Application Quit')
    chain(b,'start',('call','Exit game',{}),('returned','Print Log',{'Message':'returned'}))
    chain(b,'quit',('quitting','Print Log',{'Message':'quit'}))
    state=run(native,b,frames=30); assert state['frame']==0 and state['logs']==['returned','quit']
