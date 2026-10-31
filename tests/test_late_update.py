"""The late frame phase observes completed simulation in both native hosts."""
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.camera import default_camera
from editor.core.document import default_scene
from editor.core.events import new_event
from tests.test_native import native
from tests.test_physics_scene import chain,run


def graph(scale=1):
    b=GraphBuilder(); b.add('start','On Game Start')
    chain(b,'start',('scale','Set Time Scale',{'Scale':scale}),
          ('start_log','Print Log',{'Message':'start'}),
          ('timer','Start Timer',{'Seconds':0,'Unscaled':True}))
    for nid,event,label in [('update','On Update','update'),('timer_event','On Timer Finished','timer'),
                             ('fixed','On Fixed Update','fixed'),('late','On Late Update','late')]:
        b.add(nid,event); chain(b,nid,(nid+'_log','Print Log',{'Message':label}))
    return b


@pytest.mark.parametrize('scale,expected',[(0,['start','update','timer','late']),
                                          (1,['start','update','timer','fixed','late']),
                                          (2,['start','update','timer','fixed','fixed','late'])])
def test_late_update_runs_once_after_timer_and_all_fixed_steps(native,scale,expected):
    b=graph(scale)
    end=chain(b,'late_log',('delta','Set Variable',{'Name':'delta'}),('frame','Set Variable',{'Name':'frame'}))
    b.add('dt','Get Delta Time'); b.connect('dt','Value','delta','Value')
    b.add('frame_count','Get Frame Count'); b.connect('frame_count','Value',end,'Value')
    state=run(native,b,frames=1)
    assert state['logs']==expected
    assert state['variables']['delta']==scale/60
    assert state['variables']['frame']==0 and state['frame']==1


def test_late_camera_tracks_post_physics_position(native):
    b=graph()
    chain(b,'timer',('gravity','Set Physics Gravity',{'Gravity':[0,0,0]}),
          ('body','Create Sphere Rigid Body',{}),('damping','Set Damping',{'Linear':0.,'Angular':0.}),
          ('velocity','Set Velocity',{'Value':[3,0,0]}))
    chain(b,'late_log',('follow','Camera Follow',{'Offset':[0,1,6]}))
    scene=default_scene(); scene['entities'].append(dict(id='camera',name='Camera',position=[0,1,6],rotation=[0,0,0],scale=[1,1,1],camera=default_camera()))
    scene['active_camera']='camera'
    state=run(native,b,scene,frames=30)
    player=state['entities']['player']['position']; camera=state['entities']['camera']['position']
    assert player[0]==pytest.approx(1.5,abs=1e-6)
    assert camera==pytest.approx([player[0],player[1]+1,player[2]+6])


def test_timer_started_late_is_delivered_in_next_frame(native):
    b=GraphBuilder(); b.add('late','On Late Update')
    chain(b,'late',('log','Print Log',{'Message':'late'}),('timer','Start Timer',{'Seconds':0}))
    b.add('timer_event','On Timer Finished'); chain(b,'timer_event',('timer_log','Print Log',{'Message':'timer'}))
    assert run(native,b,frames=1)['logs']==['late']
    assert run(native,b,frames=3)['logs']==['late','timer','late','timer','late']


def test_late_errors_keep_origin_node_identity(native):
    b=GraphBuilder(); b.add('late','On Late Update'); chain(b,'late',('broken','Assert',{'Condition':False,'Message':'late failure'}))
    a,z=native(b.graph,frames=1)
    assert a.returncode==z.returncode==1
    assert json.loads(a.stderr)==json.loads(z.stderr)
    assert json.loads(a.stderr)['node']=='broken'


def test_custom_events_sent_late_drain_before_frame_end(native):
    definition=new_event('Late Ping'); definition['id']=100001
    b=GraphBuilder(event_definitions=[definition]); b.add('late','On Late Update')
    chain(b,'late',('send','Send Late Ping',{}),('late_log','Print Log',{'Message':'late'}))
    b.add('event','On Late Ping'); chain(b,'event',('event_log','Print Log',{'Message':'event'}),
          ('save_frame','Set Variable',{'Name':'received_frame'}))
    b.add('frame','Get Frame Count'); b.connect('frame','Value','save_frame','Value')
    state=run(native,b,frames=2)
    assert state['logs']==['late','event','late','event']
    assert state['variables']['received_frame']==1 and state['events']['pending']==0


def test_existing_graph_without_late_phase_still_runs(native):
    b=GraphBuilder(); b.add('update','On Update'); chain(b,'update',('log','Print Log',{'Message':'update'}))
    assert 'late_update' not in b.compile()['events']
    assert run(native,b,frames=2)['logs']==['update','update']
