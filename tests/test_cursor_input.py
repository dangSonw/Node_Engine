"""Cursor requests and locked pointer anchoring in real native graph execution."""
import json
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene,save_json
from tests.test_native import native

def test_cursor_requests_and_relative_pointer_anchor(native,tmp_path):
    b=GraphBuilder(); scene=default_scene()
    b.add('start','On Game Start'); b.add('hide','Set Cursor Visible',Visible=False); b.add('lock','Lock Cursor')
    b.connect('start','Out','hide','In').connect('hide','Out','lock','In')
    b.add('release','On Key Pressed',Filter='U'); b.add('unlock','Lock Cursor',Locked=False)
    b.connect('release','Out','unlock','In')
    b.add('update','On Update'); previous='update'
    for name in ('position','delta'):
        scene['variables'][name]=dict(type='array<vec3>',value=[])
        b.add(name,'Get Mouse '+name.title()); b.add(name+'_get','Get Vector3 Array Variable',Name=name)
        b.add(name+'_append','Append Vector3 Item'); b.add(name+'_save','Set Vector3 Array Variable',Name=name)
        b.connect(name+'_get','Value',name+'_append','Array').connect(name,'Value',name+'_append','Item')
        b.connect(name+'_append','Value',name+'_save','Value').connect(previous,'Out',name+'_save','In'); previous=name+'_save'
    replay=tmp_path/'pointer.json'; save_json(replay,dict(version=2,events=[
        dict(frame=0,type='motion',x=20,y=30,dx=1200.5,dy=-800.25),
        dict(frame=1,type='position',x=400,y=500),dict(frame=1,button='U',down=True),
        dict(frame=2,type='motion',x=35.5,y=41.25,dx=2,dy=3)]))
    a,c=native(b.graph,scene=scene,frames=4,extra=['--input-replay',str(replay)])
    assert a.returncode==c.returncode==0,a.stderr+c.stderr
    state=json.loads(a.stdout); assert state==json.loads(c.stdout)
    assert state['variables']['position']['value']==[[0,0,0],[0,0,0],[35.5,41.25,0],[35.5,41.25,0]]
    assert state['variables']['delta']['value']==[[1200.5,-800.25,0],[0,0,0],[2,3,0],[0,0,0]]
