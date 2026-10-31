"""Python-authored target selection: skip unavailable robots, stop at first match."""
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.camera import default_camera
from editor.core.codegen import export
from editor.core.document import default_scene,save_json
from editor.core.functions import new_function
from editor.core.registry import ROOT
from editor.core.ui import new_asset

GAME='node-engine-loop-control-demo'
SLOT='selection'


def action(b,source,nid,name,port='Out',**values):
    b.add(nid,name,**values); b.connect(source,port,nid,'In'); return nid


def create(directory=ROOT/'examples/loop_control_demo'):
    directory=Path(directory); assets=directory/'assets'; assets.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'examples/animation_demo/assets/robot.glb',assets/'robot.glb')
    scene=default_scene(); scene['variables']={'visited':{'type':'int','value':0},'selected':{'type':'entity','value':''},'scans':0.}
    scene['entities'][0].update(name='Robot 1',mesh='assets/robot.glb',position=[-1.5,0,0],tags=['target'],active=False)
    for eid,x,name in [('robot_b',0,'Robot 2'),('robot_c',1.5,'Robot 3')]:
        scene['entities'].append(dict(id=eid,name=name,mesh='assets/robot.glb',position=[x,0,0],rotation=[0,0,0],scale=[1,1,1],tags=['target']))
    scene['entities'].append(dict(id='camera',name='Camera',position=[0,1,7],rotation=[0,0,0],scale=[1,1,1],camera=default_camera()))
    scene['active_camera']='camera'
    markup='''<rml><head><style>body {width:100%;height:100%;font-family:node-ui;font-size:14px;color:#ffffff;pointer-events:none;}
    #help {position:absolute;left:8px;top:8px;padding:8px;width:94%;max-width:470px;box-sizing:border-box;background-color:#171e32dd;}</style></head>
    <body><div id="help">Break / Continue target selection<br/>
    Continue skips non-targets and inactive robots.<br/>Break stops at the first available robot.<br/>
    1/2/3: toggle robot availability<br/>Space: scan and enlarge first available robot<br/>
    S/L: save/load<br/>Selected: <span id="selected">robot_b</span></div></body></rml>'''
    scene['ui_assets']=[dict(new_asset(rml=markup),id='hud')]
    f=new_function('Select Available Robot',inputs=[dict(name='Targets',type='array<entity>',default=[])],outputs=[dict(name='Selected',type='entity')]); f['id']=1000200
    b=GraphBuilder(functions=[f],function=f['id']); b.add('entry','Function Input')
    end=action(b,'entry','reset','Set Entity Variable',Name='selected',Value='')
    end=action(b,end,'visited_reset','Set Integer Variable',Name='visited',Value=0)
    loop=action(b,end,'scan','For Each Entity'); b.connect('entry','Targets',loop,'Array')
    end=action(b,loop,'visit','Set Integer Variable',port='Body',Name='visited')
    b.add('visited','Get Integer Variable',Name='visited'); b.add('inc','Integer Add',B=1)
    b.connect('visited','Value','inc','A').connect('inc','Value',end,'Value')
    branch=action(b,end,'tagged','Branch'); b.add('tag','Has Entity Tag',Tag='target')
    b.connect(loop,'Item','tag','Entity').connect('tag','Value',branch,'Condition')
    action(b,branch,'skip_other','Continue Loop',port='False')
    branch=action(b,branch,'available','Branch',port='True'); b.add('active','Is Entity Active')
    b.connect(loop,'Item','active','Entity').connect('active','Value',branch,'Condition')
    action(b,branch,'skip_inactive','Continue Loop',port='False')
    end=action(b,branch,'select','Set Entity Variable',port='True',Name='selected'); b.connect(loop,'Item',end,'Value')
    action(b,end,'found','Break Loop')
    b.add('selected','Get Entity Variable',Name='selected')
    end=action(b,loop,'return','Function Output',port='Done'); b.connect('selected','Value',end,'Selected'); f['graph']=b.graph
    b=GraphBuilder('Break and Continue playground',functions=[f]); b.add('start','On Game Start')
    end=action(b,'start','storage','Open Save Storage',**{'Game ID':GAME}); end=action(b,end,'hud','Create Widget')
    for i,eid in enumerate(('player','robot_b','robot_c')): end=action(b,end,'idle_'+str(i),'Play Animation',Entity=eid,Clip='Idle')
    def scan(source,prefix,port='Out'):
        last=source
        for i,eid in enumerate(('player','robot_b','robot_c')):
            last=action(b,last,prefix+'scale'+str(i),'Set Scale',port=port if i==0 else 'Out',Entity=eid,Value=[1,1,1])
        call=action(b,last,prefix+'call','Select Available Robot'); b.add(prefix+'entities','Get All Entities')
        b.connect(prefix+'entities','Value',call,'Targets')
        end=action(b,call,prefix+'count','Set Variable',Name='scans'); b.add(prefix+'count_get','Get Variable',Name='scans')
        b.add(prefix+'add','Add',B=1); b.connect(prefix+'count_get','Value',prefix+'add','A').connect(prefix+'add','Value',end,'Value')
        end=action(b,end,prefix+'status','Set Widget Text',Element='selected',Text='none')
        branch=action(b,end,prefix+'valid','Branch'); b.add(prefix+'exists','Entity Exists')
        b.connect(call,'Selected',prefix+'exists','Entity').connect(prefix+'exists','Value',branch,'Condition')
        end=action(b,branch,prefix+'enlarge','Set Scale',port='True',Value=[1.25,1.25,1.25]); b.connect(call,'Selected',end,'Entity')
        b.add(prefix+'name','Get Entity Name'); b.connect(call,'Selected',prefix+'name','Entity')
        end=action(b,end,prefix+'name_set','Set Widget Text',Element='selected'); b.connect(prefix+'name','Value',end,'Text')
    scan(end,'initial_')
    for key,eid in [('1','player'),('2','robot_b'),('3','robot_c')]:
        b.add('update_'+key,'On Update'); b.add('key_'+key,'Is Key Pressed',Key=key)
        branch=action(b,'update_'+key,'if_'+key,'Branch'); b.connect('key_'+key,'Value',branch,'Condition')
        end=action(b,branch,'toggle_'+key,'Set Entity Active',port='True',Entity=eid)
        b.add('active_'+key,'Get Entity Active Self',Entity=eid); b.add('not_'+key,'NOT')
        b.connect('active_'+key,'Value','not_'+key,'Value').connect('not_'+key,'Value',end,'Active')
    for key,label in [('S','Save Game'),('L','Load Game'),('Space',None)]:
        b.add('update_'+key,'On Update'); b.add('key_'+key,'Is Key Pressed',Key=key)
        branch=action(b,'update_'+key,'if_'+key,'Branch'); b.connect('key_'+key,'Value',branch,'Condition')
        if label: action(b,branch,'action_'+key,label,port='True',Slot=SLOT)
        else: scan(branch,'manual_',port='True')
    for graph in (b.graph,f['graph']):
        for i,node in enumerate(graph['nodes']): node['position']=[i%6*270,i//6*220]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Break and Continue playground',scene='scenes/main.json',graph='graphs/gameplay.json'))
    export(b.compile(scene),directory/'generated'); return directory


if __name__=='__main__': print(create())
