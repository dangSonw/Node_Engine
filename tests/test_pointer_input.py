"""Pointer reads run through the same native interpreter and generated code."""
import json
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene, save_json
from tests.test_native import native


def trace_graph():
    b=GraphBuilder('Pointer frame samples'); b.add('start','On Game Start'); b.add('update','On Update')
    scene=default_scene()
    for event in ('start','update'):
        previous=event
        for field in ('Position','Delta','Wheel'):
            name=event+'_'+field.lower(); scene['variables'][name]=dict(type='array<vec3>',value=[])
            b.add(name,'Get Mouse '+field); b.add(name+'_get','Get Vector3 Array Variable',Name=name)
            b.add(name+'_append','Append Vector3 Item'); b.add(name+'_save','Set Vector3 Array Variable',Name=name)
            b.connect(name+'_get','Value',name+'_append','Array').connect(name,'Value',name+'_append','Item')
            b.connect(name+'_append','Value',name+'_save','Value').connect(previous,'Out',name+'_save','In')
            previous=name+'_save'
    return b,scene


def test_pointer_accumulation_frame_reset_and_release(native,tmp_path):
    b,scene=trace_graph(); replay=tmp_path/'pointer.json'
    save_json(replay,dict(version=2,events=[
        dict(frame=0,type='motion',x=10.25,y=-2.5,dx=3.5,dy=-1.25),
        dict(frame=0,type='wheel',x=-.25,y=1.5),
        dict(frame=0,type='motion',x=14.75,y=3,dx=4.5,dy=5.5),
        dict(frame=0,type='wheel',x=.5,y=-.25),
        dict(frame=2,type='motion',x=20,y=4,dx=5.25,dy=1),
        dict(frame=2,type='wheel',x=0,y=8),dict(frame=2,release_all=True),
        dict(frame=2,type='motion',x=21,y=6,dx=1,dy=2),
        dict(frame=3,type='position',x=-5.5,y=100.125)]))
    left,right=native(b.graph,scene=scene,frames=5,extra=['--input-replay',str(replay)])
    assert left.returncode==right.returncode==0,left.stderr+right.stderr
    data=json.loads(left.stdout); assert data==json.loads(right.stdout)
    v=data['variables']
    assert all(v['start_'+f]['value']==[[0,0,0]] for f in ('position','delta','wheel'))
    assert v['update_position']['value']==[[14.75,3,0],[14.75,3,0],[21,6,0],[-5.5,100.125,0],[-5.5,100.125,0]]
    assert v['update_delta']['value']==[[8,4.25,0],[0,0,0],[1,2,0],[0,0,0],[0,0,0]]
    assert v['update_wheel']['value']==[[.25,1.25,0],[0,0,0],[0,0,0],[0,0,0],[0,0,0]]


def test_pointer_same_frame_repeat_reads_and_late_update(native,tmp_path):
    b=GraphBuilder(); scene=default_scene()
    for event,label in [('update','On Update'),('late','On Late Update')]:
        b.add(event,label); previous=event
        for suffix in ('first','second'):
            name=event+'_'+suffix; scene['variables'][name]=dict(type='vec3',value=[0,0,0])
            b.add(name,'Get Mouse Delta'); b.add(name+'_save','Set Vector3 Variable',Name=name)
            b.connect(name,'Value',name+'_save','Value').connect(previous,'Out',name+'_save','In'); previous=name+'_save'
    replay=tmp_path/'pointer.json'; save_json(replay,dict(version=2,events=[dict(frame=0,type='motion',x=11,y=12,dx=3.25,dy=-5.5)]))
    left,right=native(b.graph,scene=scene,frames=1,extra=['--input-replay',str(replay)])
    assert left.returncode==right.returncode==0,left.stderr+right.stderr
    data=json.loads(left.stdout); assert data==json.loads(right.stdout)
    assert all(data['variables'][event+'_'+suffix]['value']==[3.25,-5.5,0] for event in ('update','late') for suffix in ('first','second'))
