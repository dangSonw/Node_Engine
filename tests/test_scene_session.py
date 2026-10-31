"""Production C++ interpreted/generated scene replacement and checkpoint parity."""
import copy
import json
import subprocess
import pytest
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene, save_json
from editor.core.functions import new_function
from tests.test_native import native
from tests.test_physics_scene import chain


def scenes():
    result={}
    for name in ('menu','level'):
        b=GraphBuilder(name); b.add('loaded','On Scene Loaded'); chain(b,'loaded',('log','Print Log',{'Message':name}))
        b.add('start','On Game Start'); chain(b,'start',('started','Print Log',{'Message':name+' start'}))
        result[name]=b
    return result


def program(graphs):
    return dict(version=1,entry_scene='menu',scenes={name:b.compile() for name,b in graphs.items()})


def play(native,graphs,frames=1,extra=()):
    a,b=native(program=program(graphs),frames=frames,extra=extra)
    assert a.returncode==b.returncode==0,a.stderr+b.stderr
    left,right=json.loads(a.stdout),json.loads(b.stdout)
    assert left==right
    return left


def key(b,letter,action,**values):
    b.add(letter,'On Key Pressed',Filter=letter); chain(b,letter,(letter+'_act',action,values))


def replay(path,events):
    save_json(path,dict(version=1,events=[dict(frame=f,button=k,down=d) for f,k,d in events])); return ['--input-replay',str(path)]


def test_deferred_transition_and_scene_local_state(native):
    g=scenes(); b=g['menu']
    chain(b,'started',('timer','Start Timer',{'Name':'old','Seconds':0}),('change','Change Scene',{'Scene':'level'}),('after','Print Log',{'Message':'after request'}))
    b.add('timer_event','On Timer Finished',Filter='old'); chain(b,'timer_event',('old','Print Log',{'Message':'discarded'}))
    chain(g['level'],'log',('move','Translate',{'Delta':[4,0,0]}))
    s=play(native,g,frames=2)
    assert s['logs']==['menu','menu start','after request','level']
    assert s['scene_session']==dict(active='level',success=True,error='',pending='')
    assert s['entities']['player']['position']==[4,0,0] and s['frame']==2 and not s['timers']


def test_loaded_requests_wait_for_next_boundary_and_keep_pause(native):
    g=scenes(); chain(g['menu'],'started',('pause','Pause World',{}),('change','Change Scene',{'Scene':'level'}))
    chain(g['level'],'log',('back','Change Scene',{'Scene':'menu'}))
    s=play(native,g,frames=1)
    assert s['logs']==['menu','menu start','level','menu']
    assert s['scene_session']['active']=='menu' and s['clock']['paused'] and s['time']==0


def test_reload_resets_scene_but_preserves_game_clock_and_only_initial_start(native,tmp_path):
    g=scenes(); chain(g['menu'],'log',('move','Translate',{'Delta':[2,0,0]})); key(g['menu'],'R','Reload Scene')
    s=play(native,g,frames=5,extra=replay(tmp_path/'keys.json',[(2,'R',True)]))
    assert s['logs']==['menu','menu start','menu'] and s['entities']['player']['position']==[2,0,0]
    assert s['frame']==5 and s['time']==pytest.approx(5/60)


def test_unknown_scene_rejects_immediately_with_error(native):
    g=scenes(); b=g['menu']; chain(b,'started',('change','Change Scene',{'Scene':'missing'}),('accepted','Set Boolean Variable',{'Name':'accepted'}),('error','Set String Variable',{'Name':'error'}))
    b.connect('change','Accepted','accepted','Value'); b.add('query','Get Scene Error'); b.connect('query','Value','error','Value')
    s=play(native,g)
    assert not s['variables']['accepted']['value'] and s['variables']['error']['value']=='Unknown scene ID'
    assert not s['scene_session']['success'] and s['scene_session']['active']=='menu'


def test_first_pending_scene_wins_and_quit_cancels_transition(native):
    g=scenes(); chain(g['menu'],'started',('change','Change Scene',{'Scene':'level'}),('again','Reload Scene',{}))
    assert play(native,g)['scene_session']['active']=='level'
    chain(g['menu'],'again',('quit','Quit Application',{}))
    s=play(native,g); assert s['scene_session']['active']=='menu' and s['frame']==0 and s['logs']==['menu','menu start']


def test_scene_load_failed_keeps_old_world_and_has_typed_outputs(native):
    g=scenes(); b=g['menu']; chain(b,'started',('change','Change Scene',{'Scene':'level'}))
    b.add('failure','On Scene Load Failed'); chain(b,'failure',('failed','Set String Variable',{'Name':'failed'}))
    b.connect('failure','Scene','failed','Value')
    p=program(g); p['scenes']['level']['scene']['audio_assets']=[dict(version=1,id='tone',name='Missing',type='sound',file='absent.wav')]
    a,z=native(program=p,frames=2); assert a.returncode==z.returncode==0,a.stderr+z.stderr
    s=json.loads(a.stdout); assert s==json.loads(z.stdout)
    assert s['scene_session']['active']=='menu' and not s['scene_session']['success']
    assert s['variables']['failed']['value']=='level' and s['logs']==['menu','menu start']


def test_function_ids_and_delayed_loaded_handlers_are_scene_local(native):
    g={}
    for name in ('menu','level'):
        f=new_function('Scene function'); f['graph']['nodes'].append(dict(id='message',type=29001,values={'Message':name+' function'}))
        # Look up Print Log rather than depend on its registry ID.
        f['graph']['nodes'][-1]['type']=GraphBuilder().registry.by_name('Print Log').id
        f['graph']['links']=[{'from':['entry','Out'],'to':['message','In']},{'from':['message','Out'],'to':['return','In']}]
        b=GraphBuilder(name,functions=[f]); b.add('loaded','On Scene Loaded')
        chain(b,'loaded',('delay','Delay',{'Seconds':0}),('call','Scene function',{}))
        g[name]=b
    g['menu'].add('start','On Game Start'); chain(g['menu'],'start',('change','Change Scene',{'Scene':'level'}))
    s=play(native,g,frames=2); assert s['logs']==['level function']


def test_cross_scene_checkpoint_uses_target_bindings_without_loaded_event(native,tmp_path):
    g=scenes(); b=g['menu']; chain(b,'started',('storage','Open Save Storage',{'Game ID':'scene-test'}))
    key(b,'C','Change Scene',Scene='level'); key(b,'L','Load Game')
    key(g['level'],'S','Save Game'); key(g['level'],'M','Change Scene',Scene='menu')
    for name,b in g.items():
        b.add('load_finished','On Load Completed'); chain(b,'load_finished',('load_log','Print Log',{'Message':name+' restored'}))
    chain(g['level'],'log',('delay','Delay',{'Seconds':.1}),('delayed','Print Log',{'Message':'level delayed'}))
    store=tmp_path/'save'
    first=play(native,g,frames=4,extra=[*replay(tmp_path/'keys.json',[(0,'C',True),(1,'C',False),(2,'S',True)]),'--save-root',str(store)])
    assert first['persistence']['success'] and first['scene_session']['active']=='level'
    slot=next(store.rglob('slot-*.json')); raw=slot.read_bytes()
    # Both hosts save the same slot; loading preserves the saved frame and resumes target's continuation.
    restored=play(native,g,frames=10,extra=[*replay(tmp_path/'keys.json',[(0,'L',True)]),'--save-root',str(store)])
    assert restored['scene_session']['active']=='level' and restored['logs']==['menu','menu start','level restored','level delayed']
    assert restored['persistence']['success'] and slot.read_bytes()==raw
    bad=json.loads(raw); bad['checkpoint']['scene_session']['active']='missing'; save_json(slot,bad)
    rejected=play(native,g,frames=1,extra=[*replay(tmp_path/'keys.json',[(0,'L',True)]),'--save-root',str(store)])
    assert rejected['scene_session']['active']=='menu' and not rejected['persistence']['success']


def test_scene_request_excludes_save_until_boundary(native,tmp_path):
    g=scenes(); b=g['menu']; chain(b,'started',('storage','Open Save Storage',{'Game ID':'exclusive'}),('change','Change Scene',{'Scene':'level'}),('save','Save Game',{}),('log_save','Print Log',{}))
    b.add('format','Format Boolean'); b.connect('save','Accepted','format','Value').connect('format','Value','log_save','Message')
    s=play(native,g,extra=['--save-root',str(tmp_path/'save')]); assert s['logs'][-2:]==['false','level']
    assert not list(tmp_path.rglob('slot-*.json'))


def test_save_request_excludes_scene_until_boundary(native,tmp_path):
    g=scenes(); b=g['menu']; chain(b,'started',('storage','Open Save Storage',{'Game ID':'exclusive'}),('save','Save Game',{}),('change','Change Scene',{'Scene':'level'}))
    s=play(native,g,extra=['--save-root',str(tmp_path/'save')])
    assert s['scene_session']['active']=='menu' and not s['scene_session']['success'] and s['persistence']['success']
    assert list(tmp_path.rglob('slot-*.json'))


def test_native_rejects_malformed_project_and_failure_handler(native,tmp_path):
    p=program(scenes()); a,b=native(program=p,frames=0); assert a.returncode==b.returncode==0
    changes=[lambda p:p.update(entry_scene='missing'),lambda p:p.update(scenes=[]),lambda p:p.update(extra=True),
        lambda p:p['scenes']['level'].update(version=2),lambda p:p['scenes']['level']['events'].update(scene_loaded={}),
        lambda p:p['scenes']['level']['events'].update(scene_failure=[dict(node='bad',event=1020.5,body=[])]),
        lambda p:p['scenes']['level']['events'].update(scene_failure=[dict(node='',event=1020,body=[])]),
        lambda p:p['scenes']['level']['events'].update(scene_failure=[dict(node='bad',event=1020,body={},extra=1)])]
    for index,change in enumerate(changes):
        bad=copy.deepcopy(p); change(bad); path=tmp_path/f'bad-{index}.json'; save_json(path,bad)
        args=list(a.args); args[args.index('--ir')+1]=str(path)
        result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=20)
        assert result.returncode==1 and 'node_error' in result.stderr
