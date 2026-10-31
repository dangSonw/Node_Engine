"""One robot graph controlled by keyboard, mouse, D-pad and analog bindings."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.document import save_json
from tools.create_input_events_demo import create as create_events

GAME='node-engine-input-bindings-demo'; SLOT='bindings'

def bindings():
    button=lambda name:dict(button=name,controller=0)
    axis=lambda name:dict(axis=name,controller=0,dead_zone=.2,invert=False)
    return dict(version=2,actions={'turn':['Space','MouseLeft',button('South')]},axes={
        'horizontal':dict(negative=['A','Left',button('DpadLeft')],positive=['D','Right',button('DpadRight')],gamepads=[axis('LeftX')]),
        'vertical':dict(negative=['Up'],positive=['Down'],gamepads=[axis('LeftY')]),
        'trigger':dict(negative=[],positive=[],gamepads=[axis('LeftTrigger')])})

def replay_trace():
    def connect(f,id,on=True): return dict(frame=f,type='gamepad_connection',controller=id,connected=on)
    def axis(f,id,name,value): return dict(frame=f,type='gamepad_axis',controller=id,axis=name,value=value)
    def pad(f,id,name,down): return dict(frame=f,type='gamepad_button',controller=id,button=name,down=down)
    def key(f,name,down): return dict(frame=f,button=name,down=down)
    setup=[connect(0,7),connect(0,9),axis(0,7,'LeftX',.6),axis(0,9,'LeftX',-.9),axis(0,7,'LeftTrigger',.6),
        key(0,'Space',True),pad(0,7,'South',True),key(1,'Space',False),pad(1,9,'South',True),pad(1,7,'South',False),key(2,'S',True)]
    future=[key(3,'S',False),connect(4,9,False),pad(5,7,'South',True),pad(5,7,'South',False),pad(5,7,'South',True),
        key(6,'D',True),key(7,'A',True),dict(frame=8,release_all=True),pad(9,7,'DpadLeft',True),
        connect(10,12),axis(10,12,'LeftX',1),axis(10,12,'LeftY',.6),pad(10,12,'South',True),
        pad(11,7,'DpadLeft',False),pad(12,12,'South',False),dict(frame=20,release_all=True)]
    return setup,future

def create(directory=ROOT/'examples/input_bindings_demo'):
    directory=create_events(directory)
    scene=json.loads((directory/'scenes/main.json').read_text('utf-8')); scene['input']=bindings()
    scene['variables'].update({k:dict(type='float',value=0) for k in ('horizontal','vertical','trigger')})
    scene['variables']['turn_held']=dict(type='bool',value=False)
    rml=scene['ui_assets'][0]['rml'].replace('Input events: ordered keyboard, mouse and mapped actions','Input bindings: keyboard, mouse and gamepad')
    rml=rml.replace('Space / left mouse: turn once per action press','Space / left mouse / South: one shared turn action')
    rml=rml.replace('A/D or arrows: move / R: reset pose / S/L: save/load','Left stick / D-pad / arrows / A/D: move<br/>R: reset pose / S/L: save/load')
    rml=rml.replace('</div>', '<br/>Axes: <span id="horizontal">0</span>, <span id="vertical">0</span> / trigger: <span id="trigger">0</span></div>')
    scene['ui_assets'][0]['rml']=rml
    b=GraphBuilder(); b.graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for n in b.graph['nodes']:
        if n['id']=='storage': n['values']['Game ID']=GAME
        if n['id'] in ('save','load'): n['values']['Slot']=SLOT
    b.add('vertical_axis','Get Input Axis',Axis='vertical'); b.add('vertical_amount','Multiply'); b.add('vertical_speed','Multiply',B=3)
    b.connect('vertical_axis','Value','vertical_amount','A').connect('dt','Value','vertical_amount','B')
    b.connect('vertical_amount','Value','vertical_speed','A').connect('vertical_speed','Value','direction','Z')
    b.add('trigger_axis','Get Input Axis',Axis='trigger'); b.add('turn_held','Is Action Held',Action='turn')
    end='move'
    for name,source in [('horizontal','axis'),('vertical','vertical_axis'),('trigger','trigger_axis'),('turn_held','turn_held')]:
        nid='capture_'+name; b.add(nid,'Set Boolean Variable' if name=='turn_held' else 'Set Variable',Name=name)
        b.connect(end,'Out',nid,'In').connect(source,'Value',nid,'Value'); end=nid
    b.add('axes_hud','On Late Update'); end='axes_hud'
    for name,source in [('horizontal','axis'),('vertical','vertical_axis'),('trigger','trigger_axis')]:
        b.add('text_'+name,'Format Float'); b.connect(source,'Value','text_'+name,'Value')
        b.add('show_'+name,'Set Widget Text',Element=name); b.connect(end,'Out','show_'+name,'In').connect('text_'+name,'Value','show_'+name,'Text'); end='show_'+name
    for i,n in enumerate(b.graph['nodes']): n['position']=[i%6*280,i//6*270]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Shared input bindings',scene='scenes/main.json',graph='graphs/gameplay.json'))
    setup,future=replay_trace(); save_json(directory/'input-replay.json',dict(version=3,events=setup+future))
    export(b.compile(scene),directory/'generated'); return directory

if __name__=='__main__': print(create())
