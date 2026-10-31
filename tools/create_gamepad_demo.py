"""Analog/controller callbacks driving the Blockbench robot through shared nodes."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from editor.core.builder import GraphBuilder
from editor.core.document import save_json
from editor.core.codegen import export
from tools.create_input_events_demo import create as create_input
GAME='node-engine-gamepad-demo'; SLOT='gamepad'

def replay_trace():
    def connect(f,id,on=True): return dict(frame=f,type='gamepad_connection',controller=id,connected=on)
    def axis(f,id,name,value): return dict(frame=f,type='gamepad_axis',controller=id,axis=name,value=value)
    def button(f,id,name,down): return dict(frame=f,type='gamepad_button',controller=id,button=name,down=down)
    setup=[connect(0,7),axis(0,7,'LeftX',1),axis(0,7,'LeftY',.15),axis(0,7,'LeftTrigger',.575),button(0,7,'South',True),
        button(1,7,'South',False),button(1,7,'East',True),dict(frame=2,button='S',down=True)]
    future=[dict(frame=3,button='S',down=False),axis(4,7,'LeftX',-.575),button(4,7,'South',True),connect(5,7,False),
        connect(6,9),axis(6,9,'LeftX',-1),axis(6,9,'LeftY',1),button(6,9,'South',True),button(7,9,'South',False),
        connect(8,12),button(8,12,'East',True),dict(frame=9,release_all=True),connect(10,9,False),axis(12,12,'LeftX',.575),dict(frame=20,release_all=True)]
    return setup,future

def create(directory=ROOT/'examples/gamepad_demo'):
    directory=create_input(directory); scene=json.loads((directory/'scenes/main.json').read_text('utf-8'))
    scene['variables']={k:dict(type=t,value=v) for k,t,v in [
        ('left_x','float',0),('left_y','float',0),('trigger','float',0),('controllers','array<int>',[]),
        ('count','int',0),('presses','int',0),('releases','int',0),('last_controller','int',0),('last_button','string','None'),
        ('delayed_controller','int',0)]}
    scene['ui_assets'][0]['rml']='''<rml><head><style>body{width:100%;height:100%;font-family:node-ui;font-size:15px;color:#f4f5ff;pointer-events:none;} #help{position:absolute;left:8px;top:8px;right:8px;max-width:520px;padding:8px;background-color:#171d2c;}</style></head><body><div id="help">Gamepad: analog and ordered button events<br/>
    Left stick: move / South face button: turn<br/>A/D: keyboard movement / R: reset / S/L: save/load<br/>
    Connected: <span id="count">0</span> / left stick: <span id="left_x">0</span>, <span id="left_y">0</span><br/>
    Left trigger: <span id="trigger">0</span><br/>Presses: <span id="presses">0</span> / releases: <span id="releases">0</span><br/>
    Last button: <span id="last_button">None</span> / controller: <span id="last_controller">0</span><br/>
    Controller retained after delay: <span id="delayed_controller">0</span></div></body></rml>'''
    b=GraphBuilder('Gamepad robot')
    def action(source,nid,name,**values): b.add(nid,name,**values); b.connect(source,'Out',nid,'In'); return nid
    def increment(source,name,port='Out'):
        b.add('get_'+name,'Get Integer Variable',Name=name); b.add('add_'+name,'Integer Add',B=1)
        b.connect('get_'+name,'Value','add_'+name,'A'); end='save_'+name; b.add(end,'Set Integer Variable',Name=name); b.connect(source,port,end,'In')
        b.connect('add_'+name,'Value',end,'Value'); return end
    b.add('start','On Game Start'); end=action('start','storage','Open Save Storage',**{'Game ID':GAME})
    end=action(end,'hud','Create Widget'); action(end,'idle','Play Animation',Clip='Idle')
    for key,name in [('S','Save Game'),('L','Load Game')]:
        b.add('key_'+key,'On Key Pressed',Filter=key); action('key_'+key,'save' if key=='S' else 'load',name,Slot=SLOT)
    b.add('key_R','On Key Pressed',Filter='R'); end=action('key_R','reset_pos','Set Position'); action(end,'reset_rot','Set Rotation',Value=[0,0,0])
    b.add('button','On Gamepad Button'); end=action('button','remember_button','Set String Variable',Name='last_button'); b.connect('button','Button',end,'Value')
    end=action(end,'remember_id','Set Integer Variable',Name='last_controller'); b.connect('button','Controller',end,'Value')
    b.add('edge','Branch'); b.connect(end,'Out','edge','In').connect('button','Down','edge','Condition')
    for port,name in [('True','presses'),('False','releases')]:
        increment('edge',name,port)
    b.add('turn','On Gamepad Button',Filter='South'); b.add('turn_down','Branch'); b.add('rotate','Rotate',Degrees=[0,90,0])
    b.connect('turn','Down','turn_down','Condition').connect('turn','Out','turn_down','In').connect('turn_down','True','rotate','In')
    end=action('rotate','delay','Retriggerable Delay',Seconds=.2,Unscaled=True)
    end=action(end,'remember_delayed','Set Integer Variable',Name='delayed_controller'); b.connect('turn','Controller',end,'Value')
    b.add('update','On Update'); end='update'
    for variable,axis in [('left_x','LeftX'),('left_y','LeftY'),('trigger','LeftTrigger')]:
        b.add('axis_'+variable,'Get Gamepad Axis',Axis=axis)
        end=action(end,'write_'+variable,'Set Variable',Name=variable); b.connect('axis_'+variable,'Value',end,'Value')
    b.add('pads','Get Connected Controllers'); b.add('length','Integer Array Length'); b.connect('pads','Value','length','Array')
    end=action(end,'write_controllers','Set Integer Array Variable',Name='controllers'); b.connect('pads','Value',end,'Value')
    end=action(end,'write_count','Set Integer Variable',Name='count'); b.connect('length','Value',end,'Value')
    b.add('keys','Get Input Axis',Axis='horizontal'); b.add('sum','Add'); b.connect('axis_left_x','Value','sum','A').connect('keys','Value','sum','B')
    b.add('direction','Make Vector3'); b.connect('sum','Value','direction','X').connect('axis_left_y','Value','direction','Z')
    b.add('dt','Get Delta Time'); b.add('speed','Multiply',B=3); b.connect('dt','Value','speed','A')
    b.add('movement','Vector Scale'); b.connect('direction','Value','movement','Vector').connect('speed','Value','movement','Scale')
    end=action(end,'move','Translate'); b.connect('movement','Value',end,'Delta')
    b.add('late','On Late Update'); end='late'
    for name in ('count','left_x','left_y','trigger','presses','releases','last_button','last_controller','delayed_controller'):
        kind=scene['variables'][name]['type']; label={'int':'Integer','float':'Float','string':'String'}[kind]
        getter='Get Variable' if kind=='float' else 'Get '+label+' Variable'; b.add('value_'+name,getter,Name=name); source='value_'+name
        if kind!='string': b.add('text_'+name,'Format '+label); b.connect(source,'Value','text_'+name,'Value'); source='text_'+name
        end=action(end,'show_'+name,'Set Widget Text',Element=name); b.connect(source,'Value',end,'Text')
    for i,node in enumerate(b.graph['nodes']): node['position']=[i%6*280,i//6*270]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Gamepad robot',scene='scenes/main.json',graph='graphs/gameplay.json'))
    setup,future=replay_trace(); save_json(directory/'input-replay.json',dict(version=3,events=setup+future))
    export(b.compile(scene),directory/'generated'); return directory

if __name__=='__main__': print(create())
