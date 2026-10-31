"""Relative mouse lock and visibility requests on the shared pointer demo."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from editor.core.builder import GraphBuilder
from editor.core.document import save_json
from editor.core.codegen import export
from tools.create_pointer_demo import create as create_pointer

GAME='node-engine-cursor-demo'; SLOT='cursor'

def create(directory=ROOT/'examples/cursor_demo'):
    directory=create_pointer(directory)
    scene=json.loads((directory/'scenes/main.json').read_text('utf-8'))
    b=GraphBuilder('Cursor lock and visibility'); b.graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    b.graph['name']='Cursor lock and visibility'
    scene['variables'].update(locked=dict(type='bool',value=False),visible=dict(type='bool',value=True))
    markup=scene['ui_assets'][0]['rml'].replace('Mouse input: position, motion and wheel','Cursor lock and visibility')
    markup=markup.replace('Left-drag: rotate / Wheel: move robot nearer or farther',
        'K/U: lock/unlock / H/V: hide/show<br/>Locked mouse or left-drag: rotate / Wheel: move robot')
    markup=markup.replace('S/L: save/load / R: reset pose','S/L: save/load / R: reset pose<br/>Esc: release cursor<br/>Requested lock: <span id="locked">false</span> / visible: <span id="visible">true</span>')
    scene['ui_assets'][0]['rml']=markup
    for node in b.graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']=GAME
        if node['id'] in ('save','load'): node['values']['Slot']=SLOT
    def set_request(source,nid,kind,value):
        name,port,variable=('Lock Cursor','Locked','locked') if kind=='lock' else ('Set Cursor Visible','Visible','visible')
        b.add(nid,name,**{port:value}); b.add(nid+'_remember','Set Boolean Variable',Name=variable,Value=value)
        b.connect(source,'Out',nid,'In').connect(nid,'Out',nid+'_remember','In'); return nid+'_remember'
    for key,kind,value in [('K','lock',True),('U','lock',False),('H','visible',False),('V','visible',True)]:
        b.add('key_'+key,'On Key Pressed',Filter=key); set_request('key_'+key,'cursor_'+key,kind,value)
    b.add('escape','On Key Pressed',Filter='Escape'); end=set_request('escape','escape_unlock','lock',False); set_request(end,'escape_show','visible',True)
    b.graph['links']=[link for link in b.graph['links'] if link['to']!=['drag_branch','Condition']]
    b.add('locked','Get Boolean Variable',Name='locked'); b.add('rotate_condition','OR')
    b.connect('drag','Value','rotate_condition','A').connect('locked','Value','rotate_condition','B').connect('rotate_condition','Value','drag_branch','Condition')
    end='show_total_wheel'
    for key in ('locked','visible'):
        b.add('hud_'+key,'Get Boolean Variable',Name=key); b.add('text_'+key,'Format Boolean'); b.add('show_'+key,'Set Widget Text',Element=key)
        b.connect('hud_'+key,'Value','text_'+key,'Value').connect('text_'+key,'Value','show_'+key,'Text').connect(end,'Out','show_'+key,'In'); end='show_'+key
    for i,node in enumerate(b.graph['nodes']): node['position']=[i%6*280,i//6*270]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Cursor robot',scene='scenes/main.json',graph='graphs/gameplay.json'))
    save_json(directory/'input-replay.json',dict(version=2,events=[
        dict(frame=0,type='position',x=25.5,y=50.25),dict(frame=0,button='K',down=True),
        dict(frame=1,button='H',down=True),dict(frame=1,type='motion',x=40.5,y=45.25,dx=15,dy=-5),
        dict(frame=1,type='wheel',x=.25,y=1.5),dict(frame=2,button='V',down=True),
        dict(frame=2,type='motion',x=50.75,y=48,dx=10.25,dy=2.75),dict(frame=2,type='wheel',x=-.5,y=-.25),
        dict(frame=2,button='S',down=True),dict(frame=3,button='S',down=False),
        dict(frame=4,type='motion',x=80.75,y=58,dx=30,dy=10),dict(frame=5,button='U',down=True),
        dict(frame=6,type='motion',x=-10,y=20,dx=-90.75,dy=-38),
        dict(frame=7,button='H',down=False),dict(frame=7,button='H',down=True),
        dict(frame=7,type='wheel',x=.125,y=-.5),dict(frame=9,release_all=True),dict(frame=10,type='position',x=120,y=90)]))
    export(b.compile(scene),directory/'generated'); return directory

if __name__=='__main__': print(create())
