"""Follow an animated Blockbench robot after its physical motion each frame."""
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

GAME='node-engine-late-update-demo'
SLOT='late'


def create(directory=ROOT/'examples/late_update_demo'):
    directory=Path(directory); assets=directory/'assets'; assets.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'examples/animation_demo/assets/robot.glb',assets/'robot.glb')
    shutil.copy2(ROOT/'examples/blockbench_demo/assets/robot.gltf',assets/'landmark.gltf')
    scene=default_scene(); scene['entities'][0].update(name='Moving animated robot',mesh='assets/robot.glb')
    for eid,x in [('left',-3),('right',3)]:
        scene['entities'].append(dict(id=eid,name=eid+' landmark',position=[x,0,-2],rotation=[0,0,0],scale=[1,1,1],mesh='assets/landmark.gltf'))
    scene['entities'].append(dict(id='camera',name='Late follow camera',position=[0,1,7],rotation=[0,0,0],scale=[1,1,1],camera=default_camera()))
    scene['active_camera']='camera'
    markup='''<rml><head><style>body {width:100%;height:100%;font-family:node-ui;font-size:14px;color:#ffffff;pointer-events:none;}
    #help {position:absolute;left:8px;top:8px;padding:8px;width:94%;max-width:490px;box-sizing:border-box;background-color:#171e32dd;}</style></head>
    <body><div id="help">Late Update camera follow<br/>
    Camera follows the robot after physics moves it.<br/>
    A/D: move left/right / Space: stop<br/>
    0: freeze / 1: normal / 2: double speed<br/>
    S/L: save/load at the end of the frame</div></body></rml>'''
    scene['ui_assets']=[dict(new_asset(rml=markup),id='hud')]
    b=GraphBuilder('Late Update camera follow')
    def action(source,nid,name,port='Out',**values):
        b.add(nid,name,**values); b.connect(source,port,nid,'In'); return nid
    b.add('start','On Game Start')
    end=action('start','storage','Open Save Storage',**{'Game ID':GAME})
    for nid,name,values in [('hud','Create Widget',{}),('walk','Play Animation',dict(Clip='Walk')),
                          ('gravity','Set Physics Gravity',dict(Gravity=[0,0,0])),('body','Create Box Rigid Body',{}),
                          ('damping','Set Damping',dict(Linear=0.,Angular=0.)),('velocity','Set Velocity',dict(Value=[1,0,0]))]:
        end=action(end,nid,name,**values)
    for key,name,values in [('A','Set Velocity',dict(Value=[-2,0,0])),('D','Set Velocity',dict(Value=[2,0,0])),
                          ('Space','Set Velocity',dict(Value=[0,0,0])),('0','Set Time Scale',dict(Scale=0)),
                          ('1','Set Time Scale',dict(Scale=1)),('2','Set Time Scale',dict(Scale=2))]:
        b.add('update_'+key,'On Update'); b.add('key_'+key,'Is Key Pressed',Key=key)
        branch=action('update_'+key,'if_'+key,'Branch'); b.connect('key_'+key,'Value',branch,'Condition')
        action(branch,'action_'+key,name,port='True',**values)
    b.add('update','On Update'); action('update','before','Set Vector3 Variable',Name='before')
    b.add('position','Get Position'); b.connect('position','Value','before','Value')
    b.add('late','On Late Update')
    end=action('late','follow','Camera Follow',Offset=[0,1,7])
    end=action(end,'after','Set Vector3 Variable',Name='after'); b.connect('position','Value',end,'Value')
    for nid,name in [('animation','Get Animation Time'),('delta','Get Delta Time'),('late_frame','Get Frame Count')]:
        b.add(nid,name); end=action(end,nid+'_store','Set Variable',Name=nid); b.connect(nid,'Value',end,'Value')
    for key,name in [('S','Save Game'),('L','Load Game')]:
        b.add('late_'+key,'On Late Update'); b.add('key_'+key,'Is Key Pressed',Key=key)
        branch=action('late_'+key,'if_'+key,'Branch'); b.connect('key_'+key,'Value',branch,'Condition')
        action(branch,'action_'+key,name,port='True',Slot=SLOT)
    for i,node in enumerate(b.graph['nodes']): node['position']=[i%7*270,i//7*220]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Late Update camera follow',scene='scenes/main.json',graph='graphs/gameplay.json'))
    export(b.compile(scene),directory/'generated'); return directory


if __name__=='__main__': print(create())
