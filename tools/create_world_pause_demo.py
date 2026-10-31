"""Python-authored world pause over animation, physics, timers, audio and UI."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.document import save_json
from tools.create_time_demo import create as create_time

GAME='node-engine-world-pause-demo'
SLOT='pause'

def trace():
    return [dict(frame=f,button=k,down=d) for f,k,d in [(10,'P',True),(11,'P',False),(40,'R',True),(41,'R',False)]]

def create(directory=ROOT/'examples/world_pause_demo'):
    directory=create_time(directory)
    scene=json.loads((directory/'scenes/main.json').read_text('utf-8'))
    b=GraphBuilder('World pause playground'); b.graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    b.graph['name']='World pause playground'
    for n in b.graph['nodes']:
        if n['id']=='storage': n['values']['Game ID']=GAME
        if n['id'] in ('action_S','action_L'): n['values']['Slot']=SLOT
    scene['variables'].update(pauses=0.,resumes=0.,unscaled_ticks=0.)
    def action(source,nid,name,**values):
        b.add(nid,name,**values); b.connect(source,'Out',nid,'In'); return nid
    def count(source,nid):
        b.add(nid+'_get','Get Variable',Name=nid); b.add(nid+'_add','Add',B=1)
        result=action(source,nid+'_set','Set Variable',Name=nid)
        b.connect(nid+'_get','Value',nid+'_add','A').connect(nid+'_add','Value',result,'Value'); return result
    for key,name in [('P','Pause World'),('R','Resume World'),('Q','Quit Application')]:
        b.add('pressed_'+key,'On Key Pressed',Filter=key); action('pressed_'+key,'world_'+key,name)
    for nid,event,message in [('pauses','On Game Pause','World paused'),('resumes','On Game Resume','World resumed')]:
        b.add(nid+'_event',event); end=count(nid+'_event',nid); action(end,nid+'_log','Print Log',Message=message)
    action('sound','real_timer','Start Timer',Name='unscaled',Seconds=.25,Repeat=True,Unscaled=True)
    b.add('real_event','On Timer Finished',Filter='unscaled'); count('real_event','unscaled_ticks')
    b.add('paused_query','Is World Paused'); b.add('paused_text','Select String',**{'True':'PAUSED','False':'RUNNING'})
    b.connect('paused_query','Value','paused_text','Condition')
    b.add('hud_update','On Late Update'); end=action('hud_update','status_text','Set Widget Text',Widget='hud',Element='status')
    b.connect('paused_text','Value',end,'Text')
    end=action(end,'pause_store','Set Boolean Variable',Name='world_paused'); b.connect('paused_query','Value',end,'Value')
    for name in ('pauses','resumes','unscaled_ticks'):
        b.add(name+'_text','Format Float'); b.connect(name+'_get','Value',name+'_text','Value')
        end=action(end,name+'_hud','Set Widget Text',Widget='hud',Element=name); b.connect(name+'_text','Value',end,'Text')
    markup=scene['ui_assets'][0]['rml']
    markup=markup.replace('Time scale playground','World pause playground').replace('0: freeze / 1:', 'P: pause / R: resume / Q: quit<br/>0: freeze / 1:')
    markup=markup.replace('Audio continues when time is frozen.','Audio and unscaled timers continue.<br/>State: <span id="status">RUNNING</span><br/>Pause events: <span id="pauses">0</span> / Resume events: <span id="resumes">0</span><br/>Unscaled ticks: <span id="unscaled_ticks">0</span>')
    scene['ui_assets'][0]['rml']=markup
    for i,n in enumerate(b.graph['nodes']): n['position']=[i%7*270,i//7*220]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='World pause playground',scene='scenes/main.json',graph='graphs/gameplay.json'))
    save_json(directory/'input-replay.json',dict(version=1,events=trace()))
    export(b.compile(scene),directory/'generated'); return directory

if __name__=='__main__': print(create())
