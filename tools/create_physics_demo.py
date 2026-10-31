"""A graph-authored rigid-body playground using the existing Blockbench robot."""
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
from tools.export_cube_fixture import convert

GAME='node-engine-physics-demo'


def create(directory=ROOT/'examples/physics_demo'):
    directory=Path(directory); assets=directory/'assets'; assets.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'examples/blockbench_demo/assets/robot.gltf',assets/'robot.gltf')
    cube=assets/'floor.bbmodel'
    save_json(cube,dict(elements=[dict(type='cube',name='Light Floor',**{'from':[-8,-8,-8],'to':[8,8,8]})]))
    convert(cube,assets/'floor.gltf')
    scene=default_scene(); scene['entities'][0].update(name='Robot rigid body',position=[0,3,0])
    scene['entities'] += [
        dict(id='robot_mesh',name='Blockbench robot',parent='player',position=[0,-.75,0],rotation=[0,0,0],scale=[1,1,1],mesh='assets/robot.gltf'),
        dict(id='floor',name='Ground',position=[0,-.25,0],rotation=[0,0,0],scale=[10,.5,10],mesh='assets/floor.gltf'),
        dict(id='camera',name='Game camera',position=[6,5,9],rotation=[0,0,0],scale=[1,1,1],camera=default_camera()),
    ]
    scene['active_camera']='camera'
    scene['input']=dict(version=1,actions={},axes={
        'horizontal':dict(negative=['A','Left'],positive=['D','Right']),
        'vertical':dict(negative=['W','Up'],positive=['Down'])})
    scene['variables']={'fixed_steps':0.}
    markup='''<rml><head><style>body {width:100%;height:100%;pointer-events:none;font-family:node-ui;font-size:16px;color:#ffffff;}
    #help {display:block;position:absolute;left:16px;right:16px;top:16px;max-width:430px;padding:12px;background-color:#171e32ee;}</style></head>
    <body><div id="help">Physics playground<br/>W/A/D / arrows: force; Space: impulse<br/>R: reset; S: save; L: load</div></body></rml>'''
    scene['ui_assets']=[dict(new_asset(rml=markup),id='hud')]
    b=GraphBuilder('Physics robot')
    def action(source,nid,name,port='Out',**values):
        b.add(nid,name,**values); b.connect(source,port,nid,'In'); return nid
    b.add('start','On Game Start')
    last=action('start','ground','Create Box Rigid Body',Entity='floor',Motion='static')
    last=action(last,'body','Create Box Rigid Body',**{'Half Extents':[.6,.75,.3],'Continuous':True})
    last=action(last,'damping','Set Damping',Linear=.35,Angular=.5)
    last=action(last,'aim','Camera Look At',Target=[0,1,0])
    last=action(last,'hud','Create Widget')
    last=action(last,'storage','Open Save Storage',**{'Game ID':GAME})
    last=action(last,'slot','Save Slot Exists')
    last=action(last,'exists','Branch'); b.connect('slot','Value','exists','Condition')
    action(last,'startup_load','Load Game',port='True')
    b.add('fixed','On Fixed Update'); action('fixed','force','Apply Force')
    b.add('axis_x','Get Input Axis',Axis='horizontal'); b.add('axis_z','Get Input Axis',Axis='vertical')
    b.add('vector','Make Vector3'); b.connect('axis_x','Value','vector','X').connect('axis_z','Value','vector','Z')
    b.add('strength','Vector Scale',Scale=12); b.connect('vector','Value','strength','Vector').connect('strength','Value','force','Value')
    action('force','count','Set Variable',Name='fixed_steps')
    b.add('ticks','Get Variable',Name='fixed_steps'); b.add('plus','Add',B=1)
    b.connect('ticks','Value','plus','A').connect('plus','Value','count','Value')
    for prefix,key,node,values in [('jump','Space','Apply Impulse',{'Value':[0,5,0]}),
        ('reset','R','Set Position',{'Value':[0,3,0]}),('save','S','Save Game',{}),('load','L','Load Game',{})]:
        b.add(prefix+'_event','On Update'); b.add(prefix+'_pressed','Is Key Pressed',Key=key)
        action(prefix+'_event',prefix+'_branch','Branch'); b.connect(prefix+'_pressed','Value',prefix+'_branch','Condition')
        action(prefix+'_branch',prefix,node,port='True',**values)
    last=action('reset','reset_rotation','Set Rotation',Value=[0,0,0])
    last=action(last,'reset_velocity','Set Velocity',Value=[0,0,0])
    action(last,'reset_angular','Set Angular Velocity',Value=[0,0,0])
    for i,node in enumerate(b.graph['nodes']): node['position']=[(i%7)*285,(i//7)*220]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Physics robot playground',graph='graphs/gameplay.json',scene='scenes/main.json',assets=['assets/robot.gltf','assets/floor.gltf']))
    export(b.compile(scene),directory/'generated'); return directory


if __name__=='__main__': print(create())
