"""Two independent animated Blockbench robots, shared graph runtime and checkpoints."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene,save_json
from editor.core.camera import default_camera
from editor.core.codegen import export
from editor.core.registry import ROOT
from editor.core.ui import new_asset
from tools.create_animated_robot import create as create_robot

GAME='node-engine-animation-demo'
SLOT='animation'
def create(directory=ROOT/'examples/animation_demo'):
    directory=Path(directory); create_robot(directory/'assets')
    scene=default_scene(); scene['variables']={}
    scene['entities'][0].update(name='Wave robot',mesh='assets/robot.glb',position=[-1.1,0,0])
    scene['entities'].append(dict(id='walker',name='Walk robot',mesh='assets/robot.glb',position=[1.1,0,0],rotation=[0,-25,0],scale=[1,1,1]))
    scene['entities'].append(dict(id='camera',name='Camera',position=[0,1.0,6],rotation=[0,0,0],scale=[1,1,1],camera=default_camera()))
    scene['active_camera']='camera'
    markup='''<rml><head><style>body {width:100%;height:100%;font-family:node-ui;font-size:14px;color:#ffffff;pointer-events:none;}
    #help {position:absolute;left:8px;top:8px;padding:8px;width:92%;max-width:420px;box-sizing:border-box;background-color:#171e32dd;}</style></head>
    <body><div id="help">Animation playground<br/>Left robot controls<br/>
    1: Idle / 2: Wave / 3: Walk / X: Stop<br/>
    P: Pause / R: Resume / T: Seek 1s<br/>
    B: Reverse / N: Normal speed / S: Save / L: Load</div></body></rml>'''
    scene['ui_assets']=[dict(new_asset(rml=markup),id='hud')]
    b=GraphBuilder('Animation playground')
    def action(source,nid,name,port='Out',**values):
        b.add(nid,name,**values); b.connect(source,port,nid,'In'); return nid
    b.add('start','On Game Start')
    last=action('start','storage','Open Save Storage',**{'Game ID':GAME})
    last=action(last,'hud','Create Widget')
    last=action(last,'wave','Play Animation',Clip='Wave')
    action(last,'walk','Play Animation',Entity='walker',Clip='Walk')
    for key,label,values in [('1','Play Animation',{'Clip':'Idle'}),('2','Play Animation',{'Clip':'Wave'}),
            ('3','Play Animation',{'Clip':'Walk'}),('X','Stop Animation',{}),('P','Pause Animation',{}),
            ('R','Resume Animation',{}),('T','Set Animation Time',{'Time':1.}),
            ('B','Set Animation Speed',{'Speed':-1.}),('N','Set Animation Speed',{'Speed':1.}),
            ('S','Save Game',{'Slot':SLOT}),('L','Load Game',{'Slot':SLOT})]:
        b.add('update_'+key,'On Update'); b.add('key_'+key,'Is Key Pressed',Key=key)
        branch=action('update_'+key,'if_'+key,'Branch'); b.connect('key_'+key,'Value',branch,'Condition')
        # A stopped model has no selected clip; ignore controls until Play selects one.
        if key in ('P','R','T','B','N'):
            b.add('playing_'+key,'Is Animation Playing'); b.add('paused_'+key,'Is Animation Paused')
            b.add('selected_'+key,'OR'); b.connect('playing_'+key,'Value','selected_'+key,'A'); b.connect('paused_'+key,'Value','selected_'+key,'B')
            branch=action(branch,'has_'+key,'Branch',port='True'); b.connect('selected_'+key,'Value',branch,'Condition')
        action(branch,'action_'+key,label,port='True',**values)
    for i,node in enumerate(b.graph['nodes']): node['position']=[(i%8)*270,(i//8)*210]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Animation playground',scene='scenes/main.json',graph='graphs/gameplay.json'))
    export(b.compile(scene),directory/'generated')
    return directory

if __name__=='__main__': print(create())
