"""Time scale across Blockbench animation, physics, timers and saved clocks."""
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

GAME='node-engine-time-demo'
SLOT='time'

def create(directory=ROOT/'examples/time_demo'):
    directory=Path(directory); assets=directory/'assets'; assets.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'examples/animation_demo/assets/robot.glb',assets/'robot.glb')
    shutil.copy2(ROOT/'examples/blockbench_demo/assets/robot.gltf',assets/'robot.gltf')
    shutil.copy2(ROOT/'examples/game_save_demo/assets/tone.wav',assets/'tone.wav')
    scene=default_scene(); scene['entities'][0].update(name='Animated robot',mesh='assets/robot.glb',position=[-1.8,0,0])
    def entity(eid,name,pos,mesh='assets/robot.gltf'):
        return dict(id=eid,name=name,position=pos,rotation=[0,0,0],scale=[.8,.8,.8],mesh=mesh)
    scene['entities'] += [entity('timer','Timer robot',[0,0,0]),entity('body','Physics robot',[1.8,0,0]),
        dict(id='camera',name='Camera',position=[0,1,8],rotation=[0,0,0],scale=[1,1,1],camera=default_camera())]
    scene['active_camera']='camera'; scene['variables']={'fixed_steps':0.}
    scene['audio_assets']=[dict(version=1,id='tone',type='sound',name='Unscaled tone',file='assets/tone.wav')]
    markup='''<rml><head><style>body {width:100%;height:100%;font-family:node-ui;font-size:14px;color:#ffffff;pointer-events:none;}
    #help {position:absolute;left:8px;top:8px;padding:8px;width:92%;max-width:450px;box-sizing:border-box;background-color:#171e32dd;}</style></head>
    <body><div id="help">Time scale playground<br/>
    0: freeze / 1: 0.25x / 2: 1x / 3: 2x<br/>S: save / L: load<br/>
    Left: animation / Middle: timer / Right: physics<br/>Audio continues when time is frozen.</div></body></rml>'''
    scene['ui_assets']=[dict(new_asset(rml=markup),id='hud')]
    b=GraphBuilder('Time scale playground')
    def action(source,nid,name,port='Out',**values):
        b.add(nid,name,**values); b.connect(source,port,nid,'In'); return nid
    b.add('start','On Game Start')
    end=action('start','storage','Open Save Storage',**{'Game ID':GAME})
    end=action(end,'hud','Create Widget')
    end=action(end,'wave','Play Animation',Clip='Wave')
    end=action(end,'gravity','Set Physics Gravity',Gravity=[0,0,0])
    end=action(end,'body','Create Box Rigid Body',Entity='body')
    end=action(end,'damping','Set Damping',Entity='body',Linear=0.,Angular=0.)
    end=action(end,'velocity','Set Velocity',Entity='body',Value=[0,0,.6])
    end=action(end,'timer_start','Start Timer',Name='turn',Seconds=.25,Repeat=True)
    action(end,'sound','Play Sound',Sound='tone',Voice='tone',Loop=True,Volume=.05)
    b.add('timer_event','On Timer Finished',Filter='turn')
    action('timer_event','turn','Rotate',Entity='timer',Degrees=[0,15,0])
    b.add('fixed','On Fixed Update'); action('fixed','count','Set Variable',Name='fixed_steps')
    b.add('ticks','Get Variable',Name='fixed_steps'); b.add('plus','Add',B=1)
    b.connect('ticks','Value','plus','A'); b.connect('plus','Value','count','Value')
    b.add('update','On Update'); end='update'
    for nid,name in [('dt','Get Delta Time'),('unscaled','Get Unscaled Delta Time'),('real','Get Real Time'),('game','Get Game Time'),('scale','Get Time Scale'),('fixed_dt','Get Fixed Delta Time')]:
        b.add(nid,name); end=action(end,nid+'_store','Set Variable',Name=nid); b.connect(nid,'Value',end,'Value')
    for key,scale in [('0',0),('1',.25),('2',1),('3',2)]:
        b.add('update_'+key,'On Update'); b.add('key_'+key,'Is Key Pressed',Key=key)
        branch=action('update_'+key,'if_'+key,'Branch'); b.connect('key_'+key,'Value',branch,'Condition')
        action(branch,'scale_'+key,'Set Time Scale',port='True',Scale=scale)
    for key,name in [('S','Save Game'),('L','Load Game')]:
        b.add('update_'+key,'On Update'); b.add('key_'+key,'Is Key Pressed',Key=key)
        branch=action('update_'+key,'if_'+key,'Branch'); b.connect('key_'+key,'Value',branch,'Condition')
        action(branch,'action_'+key,name,port='True',Slot=SLOT)
    for i,node in enumerate(b.graph['nodes']): node['position']=[i%7*270,i//7*220]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Time scale playground',scene='scenes/main.json',graph='graphs/gameplay.json'))
    export(b.compile(scene),directory/'generated'); return directory

if __name__=='__main__': print(create())
