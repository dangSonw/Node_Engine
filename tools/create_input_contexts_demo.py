"""A gameplay/menu context on the shared-input Blockbench robot."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.document import save_json
from tools.create_input_bindings_demo import create as create_bindings
GAME='node-engine-input-contexts-demo'; SLOT='contexts'

def trace():
    def key(f,k,down): return dict(frame=f,button=k,down=down)
    def pad(f,down): return dict(frame=f,type='gamepad_button',controller=7,button='South',down=down)
    return [dict(frame=0,type='gamepad_connection',controller=7,connected=True),
        dict(frame=0,type='gamepad_axis',controller=7,axis='LeftX',value=1),pad(0,True),
        key(1,'M',True),key(2,'M',False),key(3,'M',True),key(4,'M',False),pad(5,False),pad(6,True),key(7,'D',True),
        key(8,'M',True),key(9,'M',False),pad(9,False),key(10,'M',True),pad(10,True),key(11,'M',False),pad(11,False),
        pad(12,True),pad(13,False),dict(frame=16,release_all=True)]

def replay_trace(cut=2):
    events=trace()+[dict(frame=cut-1,button='S',down=True),dict(frame=cut,button='S',down=False)]
    events.sort(key=lambda e:e['frame'])
    return [e for e in events if e['frame']<cut],[e for e in events if e['frame']>=cut]

def create(directory=ROOT/'examples/input_contexts_demo'):
    directory=create_bindings(directory)
    scene=json.loads((directory/'scenes/main.json').read_text('utf-8')); scene['input']['version']=3
    scene['input']['contexts']={'gameplay':dict(enabled=True,actions=['turn'],axes=['horizontal','vertical','trigger'])}
    scene['variables']['game_enabled']=dict(type='bool',value=True)
    markup=scene['ui_assets'][0]['rml'].replace('Input bindings: keyboard, mouse and gamepad','Input context: M toggles gameplay controls')
    markup=markup.replace('</style>','#menu{position:absolute;bottom:24px;left:24px;right:24px;padding:14px;background-color:#3c3554;display:none;}</style>')
    markup=markup.replace('</body>','<div id="menu">Gameplay input disabled. Press M to resume; S/L still save/load.</div></body>')
    markup=markup.replace('</div>', '<br/>Gameplay context: <span id="context">true</span></div>',1)
    scene['ui_assets'][0]['rml']=markup
    b=GraphBuilder(); b.graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for n in b.graph['nodes']:
        if n['id']=='storage': n['values']['Game ID']=GAME
        if n['id'] in ('save','load'): n['values']['Slot']=SLOT
    b.add('menu_key','On Key Pressed',Filter='M'); b.add('context_enabled','Is Input Context Enabled'); b.add('context_not','NOT'); b.add('context_set','Set Input Context Enabled')
    b.connect('context_enabled','Value','context_not','Value').connect('context_not','Value','context_set','Enabled').connect('menu_key','Out','context_set','In')
    b.add('context_late','On Late Update'); b.add('context_capture','Set Boolean Variable',Name='game_enabled')
    b.connect('context_late','Out','context_capture','In').connect('context_enabled','Value','context_capture','Value')
    b.add('context_format','Format Boolean'); b.add('context_text','Set Widget Text',Element='context')
    b.connect('context_enabled','Value','context_format','Value').connect('context_format','Value','context_text','Text').connect('context_capture','Out','context_text','In')
    b.add('context_display','Select String',**{'True':'none','False':'block'})
    b.add('context_panel','Set Widget Style',Element='menu',Property='display')
    b.connect('context_enabled','Value','context_display','Condition').connect('context_display','Value','context_panel','Value').connect('context_text','Out','context_panel','In')
    for i,n in enumerate(b.graph['nodes']): n['position']=[i%6*280,i//6*270]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Gameplay input contexts',scene='scenes/main.json',graph='graphs/gameplay.json'))
    setup,future=replay_trace(); save_json(directory/'input-replay.json',dict(version=3,events=setup+future))
    export(b.compile(scene),directory/'generated'); return directory

if __name__=='__main__': print(create())
