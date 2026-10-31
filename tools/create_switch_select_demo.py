"""A Blockbench robot with editable integer/string routes and lazy typed selection."""
from pathlib import Path
import json
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.document import save_json
from editor.core.functions import new_function
from editor.core.registry import ROOT
from editor.core.ui import new_asset

GAME='node-engine-switch-select-demo'
SLOT='route'
POSITIONS=[[-2,0,0],[0,0,0],[2,0,0],[0,1,0]]


def create(directory=ROOT/'examples/switch_select_demo'):
    directory=Path(directory); (directory/'assets').mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'examples/animation_demo/assets/robot.glb',directory/'assets/robot.glb')
    scene=json.loads((ROOT/'examples/multi_gate_demo/scenes/main.json').read_text('utf-8'))
    scene['variables']={'mode':dict(type='int',value=0),'mirror':dict(type='bool',value=False),'selected':dict(type='string',value='Idle'),'visits':dict(type='int',value=0)}
    markup='''<rml><head><style>body {width:100%;height:100%;font-family:node-ui;font-size:14px;color:#ffffff;pointer-events:none;}
    #help {position:absolute;left:8px;top:8px;padding:8px;width:94%;max-width:480px;box-sizing:border-box;background-color:#171e32dd;}</style></head>
    <body><div id="help">Switch + Select: delayed robot routing<br/>
    1/2/3: select left/center/right / 9: default case<br/>Space: apply after 0.25s / M: mirror the destination<br/>S/L: save/load a suspended route<br/>
    Mode: <span id="mode">0</span> / <span id="mirror">Normal</span><br/>
    Last route: <span id="selected">Idle</span> / Visits: <span id="visits">0</span></div></body></rml>'''
    scene['ui_assets']=[dict(new_asset(rml=markup),id='hud')]
    f=new_function('Choose destination',inputs=[dict(name='Mode',type='int',default=0)],outputs=[dict(name='Point',type='vec3'),dict(name='Label',type='string')])
    body=GraphBuilder(functions=[f],function=f['id']); body.add('entry','Function Input')
    body.add('route','Switch Integer',cases=[dict(id=name.lower(),value=i) for i,name in enumerate(['Left','Center','Right'])])
    body.connect('entry','Out','route','In').connect('entry','Mode','route','Value')
    for i,name in enumerate(['Left','Center','Right','Fallback']):
        body.add('delay'+name,'Delay',Owner='player',Seconds=.25); body.add('return'+name,'Function Output',Point=POSITIONS[i],Label=name)
        body.connect('route','Case '+name.lower() if i<3 else 'Default','delay'+name,'In').connect('delay'+name,'Out','return'+name,'In')
    f['graph']=body.graph
    b=GraphBuilder('Switch and Select robot routes',functions=[f])
    def action(source,nid,name,port='Out',**values):
        b.add(nid,name,**values); b.connect(source,port,nid,'In'); return nid
    def pressed(key):
        b.add('input_'+key,'On Update'); b.add('key_'+key,'Is Key Pressed',Key=key)
        branch=action('input_'+key,'if_'+key,'Branch'); b.connect('key_'+key,'Value',branch,'Condition'); return branch
    b.add('start','On Game Start'); end=action('start','storage','Open Save Storage',**{'Game ID':GAME})
    end=action(end,'hud','Create Widget'); action(end,'idle','Play Animation',Clip='Idle')
    for key,value in [('1',0),('2',1),('3',2),('9',9)]: action(pressed(key),'mode'+key,'Set Integer Variable',port='True',Name='mode',Value=value)
    end=action(pressed('M'),'mirror','Set Boolean Variable',port='True',Name='mirror')
    b.add('get_mirror','Get Boolean Variable',Name='mirror'); b.add('not','NOT')
    b.connect('get_mirror','Value','not','Value').connect('not','Value',end,'Value')
    call=action(pressed('Space'),'destination','Choose destination',port='True')
    b.add('get_mode','Get Integer Variable',Name='mode'); b.connect('get_mode','Value',call,'Mode')
    b.add('select','Select Vector3'); b.add('opposite','Vector Scale',Scale=-1)
    b.connect(call,'Point','opposite','Vector').connect('opposite','Value','select','True').connect(call,'Point','select','False').connect('get_mirror','Value','select','Condition')
    end=action(call,'move','Set Position'); b.connect('select','Value',end,'Value')
    end=action(end,'selected','Set String Variable',Name='selected'); b.connect(call,'Label',end,'Value')
    end=action(end,'visit','Set Integer Variable',Name='visits'); b.add('get_visits','Get Integer Variable',Name='visits'); b.add('increment','Integer Add',B=1)
    b.connect('get_visits','Value','increment','A').connect('increment','Value',end,'Value')
    b.add('late','On Late Update'); end=action('late','show_mode','Set Widget Text',Element='mode'); b.add('format_mode','Format Integer')
    b.connect('get_mode','Value','format_mode','Value').connect('format_mode','Value',end,'Text')
    end=action(end,'show_mirror','Set Widget Text',Element='mirror'); b.add('mirror_label','Select String',**{'True':'Mirrored','False':'Normal'})
    b.connect('get_mirror','Value','mirror_label','Condition').connect('mirror_label','Value',end,'Text')
    end=action(end,'show_visits','Set Widget Text',Element='visits'); b.add('format_visits','Format Integer')
    b.connect('get_visits','Value','format_visits','Value').connect('format_visits','Value',end,'Text')
    end=action(end,'show_selected','Set Widget Text',Element='selected'); b.add('get_selected','Get String Variable',Name='selected'); b.connect('get_selected','Value',end,'Text')
    end=action(end,'facing','Switch String',cases=[dict(id=name.lower(),value=name) for name in ['Left','Center','Right']]); b.connect('get_selected','Value',end,'Value')
    for name,yaw in [('left',-30),('center',0),('right',30),('Default',0)]:
        action(end,'yaw'+name,'Set Rotation',port='Default' if name=='Default' else 'Case '+name,Value=[0,yaw,0])
    for key,label in [('S','Save Game'),('L','Load Game')]: action(pressed(key),'action_'+key,label,port='True',Slot=SLOT)
    for i,node in enumerate(b.graph['nodes']): node['position']=[i%6*280,i//6*280]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Switch and Select robot routes',scene='scenes/main.json',graph='graphs/gameplay.json'))
    export(b.compile(scene),directory/'generated'); return directory


if __name__=='__main__': print(create())
