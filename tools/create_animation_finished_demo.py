"""Author a one-shot Wave -> Idle graph and completion-triggered save in Python."""
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

GAME='node-engine-animation-finished-demo'
SLOT='animation'
FINISHED_SLOT='finished'


def create(directory=ROOT/'examples/animation_finished_demo'):
    directory=Path(directory); create_robot(directory/'assets')
    scene=default_scene(); scene['variables']={'completed':0.,'late_completed':0.}
    scene['entities'][0].update(name='One-shot Wave robot',mesh='assets/robot.glb',position=[-1.1,0,0])
    scene['entities'].append(dict(id='walker',name='Looping Walk robot',mesh='assets/robot.glb',position=[1.1,0,0],rotation=[0,-25,0],scale=[1,1,1]))
    scene['entities'].append(dict(id='camera',name='Camera',position=[0,1.0,6],rotation=[0,0,0],scale=[1,1,1],camera=default_camera()))
    scene['active_camera']='camera'
    markup='''<rml><head><style>body {width:100%;height:100%;font-family:node-ui;font-size:14px;color:#ffffff;pointer-events:none;}
    #help {position:absolute;left:8px;top:8px;padding:8px;width:92%;max-width:450px;box-sizing:border-box;background-color:#171e32dd;}</style></head>
    <body><div id="help">Animation completion playground<br/>Left: Wave once, then Idle / Right: Walk loop<br/>
    1: Wave / B: Reverse Wave / X: Stop<br/>
    P: Pause / R: Resume / 0: Freeze / 2: Normal time<br/>
    S: Save / L: Load / K: Load completion checkpoint<br/>
    Each completed Wave saves the new Idle state.</div></body></rml>'''
    scene['ui_assets']=[dict(new_asset(rml=markup),id='hud')]
    b=GraphBuilder('Animation completion playground')
    def action(source,nid,name,port='Out',**values):
        b.add(nid,name,**values); b.connect(source,port,nid,'In'); return nid
    b.add('start','On Game Start')
    end=action('start','storage','Open Save Storage',**{'Game ID':GAME})
    end=action(end,'hud','Create Widget')
    end=action(end,'wave','Play Animation',Clip='Wave',Loop=False)
    action(end,'walk','Play Animation',Entity='walker',Clip='Walk')
    b.add('finished','On Animation Finished',Receiver='player',**{'Clip Filter':'Wave'})
    end=action('finished','count','Set Variable',Name='completed')
    b.add('completed','Get Variable',Name='completed'); b.add('add','Add',B=1)
    b.connect('completed','Value','add','A').connect('add','Value','count','Value')
    end=action(end,'last_clip','Set String Variable',Name='last_clip'); b.connect('finished','Clip',end,'Value')
    end=action(end,'last_entity','Set Entity Variable',Name='last_entity'); b.connect('finished','Entity',end,'Value')
    end=action(end,'idle','Play Animation',Clip='Idle'); b.connect('finished','Entity',end,'Entity')
    action(end,'save_finished','Save Game',Slot=FINISHED_SLOT)
    b.add('late','On Late Update'); action('late','late_count','Set Variable',Name='late_completed')
    b.connect('completed','Value','late_count','Value')
    for key,label,values in [('1','Play Animation',{'Clip':'Wave','Loop':False}),
            ('B','Play Animation',{'Clip':'Wave','Loop':False,'Speed':-1.}),('X','Stop Animation',{}),
            ('P','Pause Animation',{}),('R','Resume Animation',{}),
            ('0','Set Time Scale',{'Scale':0}),('2','Set Time Scale',{'Scale':1}),
            ('S','Save Game',{'Slot':SLOT}),('L','Load Game',{'Slot':SLOT}),('K','Load Game',{'Slot':FINISHED_SLOT})]:
        b.add('update_'+key,'On Update'); b.add('key_'+key,'Is Key Pressed',Key=key)
        branch=action('update_'+key,'if_'+key,'Branch'); b.connect('key_'+key,'Value',branch,'Condition')
        if key in ('P','R'):
            b.add('playing_'+key,'Is Animation Playing'); b.add('paused_'+key,'Is Animation Paused')
            b.add('selected_'+key,'OR'); b.connect('playing_'+key,'Value','selected_'+key,'A'); b.connect('paused_'+key,'Value','selected_'+key,'B')
            branch=action(branch,'has_'+key,'Branch',port='True'); b.connect('selected_'+key,'Value',branch,'Condition')
        action(branch,'action_'+key,label,port='True',**values)
    for i,node in enumerate(b.graph['nodes']): node['position']=[(i%8)*270,(i//8)*210]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Animation completion playground',scene='scenes/main.json',graph='graphs/gameplay.json'))
    export(b.compile(scene),directory/'generated')
    return directory


if __name__=='__main__': print(create())
