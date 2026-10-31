"""Mouse position, drag and wheel on the Blockbench robot, authored in Python."""
from pathlib import Path
import json,shutil,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.document import save_json
from editor.core.registry import ROOT
from editor.core.ui import new_asset

GAME='node-engine-pointer-demo'; SLOT='pointer'
FIELDS=('position','delta','wheel','total_delta','total_wheel')

def create(directory=ROOT/'examples/pointer_demo'):
    directory=Path(directory); (directory/'assets').mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'examples/animation_demo/assets/robot.glb',directory/'assets/robot.glb')
    previous=json.loads((ROOT/'examples/input_events_demo/scenes/main.json').read_text('utf-8'))
    scene=dict(version=1,active_camera='camera',entities=previous['entities'],variables={k:dict(type='vec3',value=[0,0,0]) for k in FIELDS})
    scene['variables']['start_position']=dict(type='vec3',value=[0,0,0])
    markup='''<rml><head><style>body {width:100%;height:100%;font-family:node-ui;font-size:15px;color:#f4f5ff;pointer-events:none;} #help {position:absolute;left:8px;top:8px;right:8px;max-width:500px;padding:8px;background-color:#171d2c;}</style></head>
    <body><div id="help">Mouse input: position, motion and wheel<br/>
    Left-drag: rotate / Wheel: move robot nearer or farther<br/>S/L: save/load / R: reset pose<br/>
    Position: <span id="position">0</span><br/>Frame delta: <span id="delta">0</span><br/>
    Frame wheel: <span id="wheel">0</span><br/>Total delta: <span id="total_delta">0</span><br/>
    Total wheel: <span id="total_wheel">0</span></div></body></rml>'''
    scene['ui_assets']=[dict(new_asset(rml=markup),id='hud')]
    b=GraphBuilder('Mouse position, drag and wheel')
    def action(source,nid,name,**values):
        b.add(nid,name,**values); b.connect(source,'Out',nid,'In'); return nid
    b.add('start','On Game Start'); end=action('start','storage','Open Save Storage',**{'Game ID':GAME})
    end=action(end,'hud','Create Widget'); end=action(end,'animation','Play Animation',Clip='Idle')
    end=action(end,'start_position','Set Vector3 Variable',Name='start_position')
    b.add('position','Get Mouse Position'); b.add('delta','Get Mouse Delta'); b.add('wheel','Get Mouse Wheel')
    b.connect('position','Value','start_position','Value')
    b.add('update','On Update'); end='update'
    for name in ('position','delta','wheel'):
        end=action(end,'write_'+name,'Set Vector3 Variable',Name=name); b.connect(name,'Value',end,'Value')
    for name in ('delta','wheel'):
        key='total_'+name; b.add('get_'+key,'Get Vector3 Variable',Name=key); b.add('add_'+key,'Vector Add')
        b.connect('get_'+key,'Value','add_'+key,'A').connect(name,'Value','add_'+key,'B')
        end=action(end,'write_'+key,'Set Vector3 Variable',Name=key); b.connect('add_'+key,'Value',end,'Value')
    b.add('wheel_y','Dot Product',B=[0,1,0]); b.add('wheel_speed','Multiply',B=.15); b.add('wheel_move','Make Vector3')
    b.connect('wheel','Value','wheel_y','A').connect('wheel_y','Value','wheel_speed','A').connect('wheel_speed','Value','wheel_move','Z')
    end=action(end,'move','Translate'); b.connect('wheel_move','Value',end,'Delta')
    b.add('drag','Is Key Held',Key='MouseLeft'); end=action(end,'drag_branch','Branch'); b.connect('drag','Value',end,'Condition')
    b.add('rotate','Rotate'); b.connect(end,'True','rotate','In')
    for axis,basis in [('x',[1,0,0]),('y',[0,1,0])]:
        b.add('d'+axis,'Dot Product',B=basis); b.add('s'+axis,'Multiply',B=.5)
        b.connect('delta','Value','d'+axis,'A').connect('d'+axis,'Value','s'+axis,'A')
    b.add('degrees','Make Vector3'); b.connect('sx','Value','degrees','Y').connect('sy','Value','degrees','X').connect('degrees','Value','rotate','Degrees')
    for key,name in [('S','Save Game'),('L','Load Game')]:
        b.add('key_'+key,'On Key Pressed',Filter=key); action('key_'+key,'save' if key=='S' else 'load',name,Slot=SLOT)
    b.add('key_R','On Key Pressed',Filter='R'); end=action('key_R','reset_pos','Set Position'); action(end,'reset_rot','Set Rotation',Value=[0,0,0])
    b.add('late','On Late Update'); end='late'
    for name in FIELDS:
        b.add('read_'+name,'Get Vector3 Variable',Name=name)
        for axis,basis in [('x',[1,0,0]),('y',[0,1,0])]:
            b.add(name+'_display_'+axis,'Dot Product',B=basis); b.add(name+'_text_'+axis,'Format Float')
            b.connect('read_'+name,'Value',name+'_display_'+axis,'A').connect(name+'_display_'+axis,'Value',name+'_text_'+axis,'Value')
        b.add(name+'_comma','Concat Strings',B=', '); b.add('format_'+name,'Concat Strings')
        b.connect(name+'_text_x','Value',name+'_comma','A').connect(name+'_comma','Value','format_'+name,'A')
        b.connect(name+'_text_y','Value','format_'+name,'B')
        end=action(end,'show_'+name,'Set Widget Text',Element=name); b.connect('format_'+name,'Value',end,'Text')
    for i,node in enumerate(b.graph['nodes']): node['position']=[i%6*280,i//6*270]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Pointer robot',scene='scenes/main.json',graph='graphs/gameplay.json'))
    export(b.compile(scene),directory/'generated'); return directory

if __name__=='__main__': print(create())
