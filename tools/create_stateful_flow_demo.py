"""Python graph authoring for four persistent gates controlling a Blockbench robot."""
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

GAME='node-engine-stateful-flow-demo'
SLOT='gates'


def create(directory=ROOT/'examples/stateful_flow_demo'):
    directory=Path(directory); assets=directory/'assets'; assets.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'examples/animation_demo/assets/robot.glb',assets/'robot.glb')
    scene=default_scene(); scene['entities'][0].update(name='Gate-controlled robot',mesh='assets/robot.glb')
    scene['entities'].append(dict(id='camera',name='Camera',position=[.7,1.2,7],rotation=[0,0,0],scale=[1,1,1],camera=default_camera()))
    scene['active_camera']='camera'; scene['variables']={'used':{'type':'int','value':0},'is_a':{'type':'bool','value':False}}
    markup='''<rml><head><style>body {width:100%;height:100%;font-family:node-ui;font-size:14px;color:#ffffff;pointer-events:none;}
    #help {position:absolute;left:8px;top:8px;padding:8px;width:94%;max-width:480px;box-sizing:border-box;background-color:#171e32dd;}</style></head>
    <body><div id="help">Persistent flow gates<br/>
    O: lift once until reset (Do Once)<br/>N: step right, at most 3 times (Do N)<br/>
    G: toggle rotation (Gate)<br/>F: alternate large/small (Flip Flop)<br/>
    R: reset gates and robot / S: save / L: load</div></body></rml>'''
    scene['ui_assets']=[dict(new_asset(rml=markup),id='hud')]
    b=GraphBuilder('Persistent flow gates')
    def action(source,nid,name,port='Out',**values):
        b.add(nid,name,**values); b.connect(source,port,nid,'In'); return nid
    def pressed(key,nid=None):
        nid=nid or key; b.add('input_'+nid,'On Update'); b.add('key_'+nid,'Is Key Pressed',Key=key)
        branch=action('input_'+nid,'if_'+nid,'Branch'); b.connect('key_'+nid,'Value',branch,'Condition'); return branch
    b.add('start','On Game Start'); end=action('start','storage','Open Save Storage',**{'Game ID':GAME})
    end=action(end,'hud','Create Widget'); action(end,'idle','Play Animation',Clip='Idle')
    for nid,label,values,key,entry in [('once','Do Once',{},'O','In'),('quota','Do N',{'N':3},'N','In'),
            ('gate','Gate',{'Start Closed':True},'G','Toggle'),('flip','Flip Flop',{},'F','In')]:
        b.add(nid,label,Owner='player',**values); b.connect(pressed(key),'True',nid,entry)
    action('once','lift','Translate',Delta=[0,.5,0])
    end=action('quota','step','Translate',Delta=[.5,0,0]); action(end,'used','Set Integer Variable',Name='used')
    b.connect('quota','Counter','used','Value')
    b.add('z_drive','On Update'); b.connect('z_drive','Out','gate','In')
    action('gate','rotate','Rotate')
    b.add('dt','Get Delta Time'); b.add('degrees','Vector Scale',Vector=[0,90,0])
    b.connect('dt','Value','degrees','Scale').connect('degrees','Value','rotate','Degrees')
    for port,size in [('A',1.25),('B',.75)]:
        end=action('flip','scale_'+port,'Set Scale',port=port,Value=[size]*3)
        end=action(end,'is_a_'+port,'Set Boolean Variable',Name='is_a'); b.connect('flip','Is A',end,'Value')
    end=action(pressed('R','R_pose'),'reset_position','Set Position',port='True',Value=[0,0,0])
    for nid,label,values in [('reset_rotation','Set Rotation',{'Value':[0,0,0]}),('reset_scale','Set Scale',{'Value':[1,1,1]}),
            ('reset_used','Set Integer Variable',{'Name':'used','Value':0}),('reset_is_a','Set Boolean Variable',{'Name':'is_a','Value':False})]:
        end=action(end,nid,label,**values)
    for nid,entry in [('once','Reset'),('quota','Reset'),('flip','Reset'),('gate','Close')]: b.connect(pressed('R','R_'+nid),'True',nid,entry)
    for key,label in [('S','Save Game'),('L','Load Game')]: action(pressed(key),'action_'+key,label,port='True',Slot=SLOT)
    for i,node in enumerate(b.graph['nodes']): node['position']=[i%7*270,i//7*220]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Persistent flow gates',scene='scenes/main.json',graph='graphs/gameplay.json'))
    export(b.compile(scene),directory/'generated'); return directory


if __name__=='__main__': print(create())
