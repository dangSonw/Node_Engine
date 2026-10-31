"""A sequential/random four-station robot tour authored with Python graphs."""
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

GAME='node-engine-multi-gate-demo'
SLOT='routes'
POSITIONS=[[-1.5,0,-1],[1.5,0,-1],[1.5,0,1],[-1.5,0,1]]


def create(directory=ROOT/'examples/multi_gate_demo'):
    directory=Path(directory); assets=directory/'assets'; assets.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'examples/animation_demo/assets/robot.glb',assets/'robot.glb')
    scene=default_scene(); scene['entities'][0].update(name='Touring robot',mesh='assets/robot.glb')
    for i,position in enumerate(POSITIONS):
        scene['entities'].append(dict(id='station'+str(i),name='Station '+str(i),position=[position[0],-.5,position[2]],rotation=[0,0,0],scale=[.25]*3,mesh='assets/robot.glb'))
    scene['entities'].append(dict(id='camera',name='Camera',position=[0,1.5,8],rotation=[0,0,0],scale=[1,1,1],camera=default_camera()))
    scene['active_camera']='camera'
    scene['variables']={'selected':{'type':'int','value':-1},'history':{'type':'string','value':''},
                        'random':{'type':'bool','value':False},'loop':{'type':'bool','value':False}}
    markup='''<rml><head><style>body {width:100%;height:100%;font-family:node-ui;font-size:14px;color:#ffffff;pointer-events:none;}
    #help {position:absolute;left:8px;top:8px;padding:8px;width:94%;max-width:480px;box-sizing:border-box;background-color:#171e32dd;}</style></head>
    <body><div id="help">Multi Gate: four-station robot tour<br/>
    Space: next route / M: toggle random / T: toggle loop<br/>
    R: reset tour and seed 42 / S: save / L: load<br/>
    <span id="mode">Sequential</span> / <span id="loop">Stop after four routes</span><br/>
    Route history: <span id="history"></span></div></body></rml>'''
    scene['ui_assets']=[dict(new_asset(rml=markup),id='hud')]
    b=GraphBuilder('Multi Gate robot tour')
    def action(source,nid,name,port='Out',**values):
        b.add(nid,name,**values); b.connect(source,port,nid,'In'); return nid
    def pressed(key,nid=None):
        nid=nid or key; b.add('input_'+nid,'On Update'); b.add('key_'+nid,'Is Key Pressed',Key=key)
        branch=action('input_'+nid,'if_'+nid,'Branch'); b.connect('key_'+nid,'Value',branch,'Condition'); return branch
    b.add('start','On Game Start'); end=action('start','storage','Open Save Storage',**{'Game ID':GAME})
    end=action(end,'hud','Create Widget'); end=action(end,'seed','Set Random Seed',Seed=42)
    action(end,'idle','Play Animation',Clip='Idle')
    b.add('route','Multi Gate',Owner='player',Branches=4)
    b.connect(pressed('Space'),'True','route','In')
    for name,key,element,on,off in [('random','M','mode','Random without repeats','Sequential'),('loop','T','loop','Loop enabled','Stop after four routes')]:
        b.add('get_'+name,'Get Boolean Variable',Name=name); b.connect('get_'+name,'Value','route',name.title())
        branch=action(pressed(key),'toggle_'+name,'Branch',port='True'); b.connect('get_'+name,'Value',branch,'Condition')
        for port,value,text in [('True',False,off),('False',True,on)]:
            end=action(branch,'set_'+name+port,'Set Boolean Variable',port=port,Name=name,Value=value)
            action(end,'label_'+name+port,'Set Widget Text',Element=element,Text=text)
    b.add('selected','Set Integer Variable',Name='selected'); b.connect('route','Index','selected','Value')
    for i,position in enumerate(POSITIONS):
        end=action('route','position'+str(i),'Set Position',port='Out '+str(i),Value=position)
        end=action(end,'rotation'+str(i),'Set Rotation',Value=[0,i*90,0]); b.connect(end,'Out','selected','In')
    end=action('selected','history','Set String Variable',Name='history')
    b.add('old_history','Get String Variable',Name='history'); b.add('index','Format Integer')
    b.connect('route','Index','index','Value'); b.add('space','Concat Strings',B=' '); b.connect('index','Value','space','A')
    b.add('append','Concat Strings'); b.connect('old_history','Value','append','A').connect('space','Value','append','B').connect('append','Value','history','Value')
    action(end,'show_history','Set Widget Text',Element='history'); b.connect('old_history','Value','show_history','Text')
    end=action(pressed('R','R_pose'),'reset_position','Set Position',port='True',Value=[0,0,0])
    end=action(end,'reset_rotation','Set Rotation',Value=[0,0,0]); end=action(end,'reset_selected','Set Integer Variable',Name='selected',Value=-1)
    end=action(end,'reset_history','Set String Variable',Name='history',Value='')
    end=action(end,'clear_history','Set Widget Text',Element='history',Text=''); action(end,'reset_seed','Set Random Seed',Seed=42)
    b.connect(pressed('R','R_gate'),'True','route','Reset')
    for key,label in [('S','Save Game'),('L','Load Game')]: action(pressed(key),'action_'+key,label,port='True',Slot=SLOT)
    for i,node in enumerate(b.graph['nodes']): node['position']=[i%7*280,i//7*280]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Multi Gate robot tour',scene='scenes/main.json',graph='graphs/gameplay.json'))
    export(b.compile(scene),directory/'generated'); return directory


if __name__=='__main__': print(create())
