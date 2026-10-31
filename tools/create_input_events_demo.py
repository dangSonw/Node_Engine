"""Physical and mapped input callbacks on an animated Blockbench robot."""
from pathlib import Path
import json,shutil,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.document import save_json
from editor.core.registry import ROOT
from editor.core.ui import new_asset

GAME='node-engine-input-events-demo'; SLOT='input'
COUNTERS=('presses','releases','mouse_edges','turns','action_releases','settled')

def create(directory=ROOT/'examples/input_events_demo'):
    directory=Path(directory); (directory/'assets').mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'examples/animation_demo/assets/robot.glb',directory/'assets/robot.glb')
    previous=json.loads((ROOT/'examples/switch_select_demo/scenes/main.json').read_text('utf-8'))
    camera=next(e for e in previous['entities'] if e['id']=='camera')
    scene=dict(version=1,active_camera='camera',entities=[dict(id='player',name='Input robot',mesh='assets/robot.glb',position=[0,0,0],rotation=[0,0,0],scale=[1,1,1]),camera],
        input=dict(version=1,actions={'turn':['Space','MouseLeft']},axes={'horizontal':{'negative':['A','Left'],'positive':['D','Right']}}),variables={})
    scene['variables']={k:dict(type='int',value=0) for k in COUNTERS}
    scene['variables'].update(last_key=dict(type='string',value='None'),last_action=dict(type='string',value='None'),
        delayed_action=dict(type='string',value='None'),last_down=dict(type='bool',value=False))
    markup='''<rml><head><style>body {width:100%;height:100%;font-family:node-ui;font-size:15px;color:#f4f5ff;pointer-events:none;} #help {position:absolute;left:8px;top:8px;right:8px;max-width:510px;padding:8px;background-color:#171d2c;}</style></head>
    <body><div id="help">Input events: ordered keyboard, mouse and mapped actions<br/>
    Space / left mouse: turn once per action press<br/>A/D or arrows: move / R: reset pose / S/L: save/load<br/>
    Key presses: <span id="presses">0</span> / releases: <span id="releases">0</span><br/>
    Mouse edges: <span id="mouse_edges">0</span> / down: <span id="last_down">false</span><br/>
    Turns: <span id="turns">0</span> / action releases: <span id="action_releases">0</span><br/>
    Settled after delay: <span id="settled">0</span><br/>
    Last key: <span id="last_key">None</span> / action: <span id="last_action">None</span><br/>
    Captured after delay: <span id="delayed_action">None</span></div></body></rml>'''
    scene['ui_assets']=[dict(new_asset(rml=markup),id='hud')]
    b=GraphBuilder('Ordered input events')
    def action(source,nid,name,**values):
        b.add(nid,name,**values); b.connect(source,'Out',nid,'In'); return nid
    def increment(source,name):
        end=action(source,'write_'+name,'Set Integer Variable',Name=name)
        b.add('get_'+name,'Get Integer Variable',Name=name); b.add('add_'+name,'Integer Add',B=1)
        b.connect('get_'+name,'Value','add_'+name,'A').connect('add_'+name,'Value',end,'Value'); return end
    b.add('start','On Game Start'); end=action('start','storage','Open Save Storage',**{'Game ID':GAME})
    end=action(end,'hud','Create Widget'); action(end,'animation','Play Animation',Clip='Idle')
    b.add('key_press','On Key Pressed',Filter=''); end=increment('key_press','presses')
    end=action(end,'remember_key','Set String Variable',Name='last_key'); b.connect('key_press','Key',end,'Value')
    b.add('key_release','On Key Released',Filter=''); increment('key_release','releases')
    b.add('mouse','On Mouse Button'); end=increment('mouse','mouse_edges')
    end=action(end,'remember_down','Set Boolean Variable',Name='last_down'); b.connect('mouse','Down',end,'Value')
    b.add('turn','On Action Pressed',Filter='turn'); end=increment('turn','turns')
    end=action(end,'rotate','Rotate',Degrees=[0,90,0]); end=action(end,'remember_action','Set String Variable',Name='last_action')
    b.connect('turn','Action',end,'Value'); end=action(end,'settle_delay','Retriggerable Delay',Seconds=.2,Unscaled=True)
    end=increment(end,'settled'); end=action(end,'remember_delayed','Set String Variable',Name='delayed_action')
    b.connect('turn','Action',end,'Value')
    b.add('turn_release','On Action Released',Filter='turn'); increment('turn_release','action_releases')
    for key,name in [('S','Save Game'),('L','Load Game')]:
        b.add('key_'+key,'On Key Pressed',Filter=key); action('key_'+key,'save' if key=='S' else 'load',name,Slot=SLOT)
    b.add('key_R','On Key Pressed',Filter='R'); end=action('key_R','reset_pos','Set Position'); action(end,'reset_rot','Set Rotation',Value=[0,0,0])
    b.add('update','On Update'); end=action('update','move','Translate')
    b.add('axis','Get Input Axis',Axis='horizontal'); b.add('dt','Get Delta Time'); b.add('amount','Multiply')
    b.add('speed','Multiply',B=3); b.add('direction','Make Vector3')
    b.connect('axis','Value','amount','A').connect('dt','Value','amount','B').connect('amount','Value','speed','A')
    b.connect('speed','Value','direction','X').connect('direction','Value',end,'Delta')
    b.add('late','On Late Update'); end='late'
    for name in (*COUNTERS,'last_key','last_action','delayed_action','last_down'):
        end=action(end,'show_'+name,'Set Widget Text',Element=name)
        if name in COUNTERS:
            b.add('format_'+name,'Format Integer'); b.connect('get_'+name,'Value','format_'+name,'Value'); source='format_'+name
        else:
            kind='Boolean' if name=='last_down' else 'String'; b.add('get_'+name,'Get '+kind+' Variable',Name=name); source='get_'+name
            if kind=='Boolean':
                b.add('format_'+name,'Format Boolean'); b.connect(source,'Value','format_'+name,'Value'); source='format_'+name
        b.connect(source,'Value',end,'Text')
    for i,node in enumerate(b.graph['nodes']): node['position']=[i%6*280,i//6*270]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Input events robot',scene='scenes/main.json',graph='graphs/gameplay.json'))
    export(b.compile(scene),directory/'generated'); return directory

if __name__=='__main__': print(create())
