"""Named timers keep a menu responsive and resume a frozen Blockbench scene."""
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.camera import default_camera
from editor.core.codegen import export
from editor.core.document import default_scene,save_json
from editor.core.registry import ROOT
from editor.core.ui import new_asset

GAME='node-engine-unscaled-timer-demo'
SLOT='timers'


def create(directory=ROOT/'examples/unscaled_timer_demo'):
    directory=Path(directory); assets=directory/'assets'; assets.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'examples/blockbench_demo/assets/robot.gltf',assets/'robot.gltf')
    scene=default_scene(); scene['entities'][0].update(name='Game timer',mesh='assets/robot.gltf',position=[-1.3,0,0])
    scene['entities'] += [dict(id='menu',name='Unscaled timer',position=[1.3,0,0],rotation=[0,0,0],scale=[1,1,1],mesh='assets/robot.gltf'),
        dict(id='camera',name='Camera',position=[0,1,7],rotation=[0,0,0],scale=[1,1,1],camera=default_camera())]
    scene['active_camera']='camera'
    markup='''<rml><head><style>body {width:100%;height:100%;font-family:node-ui;font-size:14px;color:#ffffff;pointer-events:none;}
    #help {position:absolute;left:8px;top:8px;padding:8px;width:94%;max-width:490px;box-sizing:border-box;background-color:#171e32dd;}</style></head>
    <body><div id="help">Independent timer clocks<br/>
    Left: game timer / Right: unscaled timer<br/>
    0: freeze / 1: normal / 2: quarter / 3: double<br/>
    R: freeze and resume automatically after 2 seconds<br/>
    P/U: pause/resume right timer / S/L: save/load</div></body></rml>'''
    scene['ui_assets']=[dict(new_asset(rml=markup),id='hud')]
    b=GraphBuilder('Independent timer clocks')
    def action(source,nid,name,port='Out',**values):
        b.add(nid,name,**values); b.connect(source,port,nid,'In'); return nid
    b.add('start','On Game Start')
    end=action('start','storage','Open Save Storage',**{'Game ID':GAME})
    end=action(end,'hud','Create Widget')
    end=action(end,'game_timer','Start Timer',Name='game',Seconds=.25,Repeat=True)
    action(end,'menu_timer','Start Timer',Name='menu',Seconds=.25,Repeat=True,Unscaled=True)
    for name,entity in [('game','player'),('menu','menu')]:
        b.add(name+'_event','On Timer Finished',Filter=name)
        action(name+'_event',name+'_turn','Rotate',Entity=entity,Degrees=[0,15,0])
    b.add('resume_event','On Timer Finished',Filter='resume')
    action('resume_event','auto_resume','Set Time Scale',Scale=1.)
    for key,name,values in [('0','Set Time Scale',dict(Scale=0)),('1','Set Time Scale',dict(Scale=1)),
            ('2','Set Time Scale',dict(Scale=.25)),('3','Set Time Scale',dict(Scale=2)),
            ('R','Set Time Scale',dict(Scale=0)),('P','Pause Timer',dict(Name='menu')),
            ('U','Resume Timer',dict(Name='menu')),('S','Save Game',dict(Slot=SLOT)),('L','Load Game',dict(Slot=SLOT))]:
        b.add('update_'+key,'On Update'); b.add('key_'+key,'Is Key Pressed',Key=key)
        branch=action('update_'+key,'if_'+key,'Branch'); b.connect('key_'+key,'Value',branch,'Condition')
        end=action(branch,'action_'+key,name,port='True',**values)
        if key=='R': action(end,'resume_timer','Start Timer',Name='resume',Seconds=2,Unscaled=True)
    b.add('update','On Update')
    end='update'
    for name in ('game','menu','resume'):
        b.add(name+'_remaining','Get Timer Remaining',Name=name)
        end=action(end,name+'_store','Set Variable',Name=name+'_remaining'); b.connect(name+'_remaining','Value',end,'Value')
    for i,node in enumerate(b.graph['nodes']): node['position']=[i%7*270,i//7*220]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Independent timer clocks',scene='scenes/main.json',graph='graphs/gameplay.json'))
    export(b.compile(scene),directory/'generated'); return directory


if __name__=='__main__': print(create())
