"""Blockbench robot tour with suspended functions, loops and a debounced signal."""
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
from tools.create_multi_gate_demo import POSITIONS

GAME='node-engine-latent-flow-demo'
SLOT='tour'


def create(directory=ROOT/'examples/latent_flow_demo'):
    directory=Path(directory); (directory/'assets').mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'examples/animation_demo/assets/robot.glb',directory/'assets/robot.glb')
    scene=json.loads((ROOT/'examples/multi_gate_demo/scenes/main.json').read_text('utf-8'))
    scene['variables']={'started':{'type':'bool','value':False},'progress':{'type':'int','value':0}}
    markup='''<rml><head><style>body {width:100%;height:100%;font-family:node-ui;font-size:14px;color:#ffffff;pointer-events:none;}
    #help {position:absolute;left:8px;top:8px;padding:8px;width:94%;max-width:480px;box-sizing:border-box;background-color:#171e32dd;}</style></head>
    <body><div id="help">Latent flow: delayed robot tour<br/>
    Space: start / R: restart 0.5-second signal delay<br/>S: save while waiting / L: restore and continue<br/>
    <span id="status">Waiting for Space</span><br/>Stations visited: <span id="progress">0</span> / 4<br/>
    Signal: <span id="signal">Idle</span></div></body></rml>'''
    scene['ui_assets']=[dict(new_asset(rml=markup),id='hud')]
    f=new_function('Delayed destination',inputs=[dict(name='Destination',type='vec3',default=[0,0,0])],outputs=[dict(name='Point',type='vec3')])
    body=GraphBuilder(functions=[f],function=f['id']); body.add('entry','Function Input')
    body.add('delay','Delay',Owner='player',Seconds=.5); body.add('return','Function Output')
    body.connect('entry','Out','delay','In').connect('delay','Out','return','In').connect('entry','Destination','return','Point')
    f['graph']=body.graph
    b=GraphBuilder('Latent robot tour',functions=[f])
    def action(source,nid,name,port='Out',**values):
        b.add(nid,name,**values); b.connect(source,port,nid,'In'); return nid
    def pressed(key):
        b.add('input_'+key,'On Update'); b.add('key_'+key,'Is Key Pressed',Key=key)
        branch=action('input_'+key,'if_'+key,'Branch'); b.connect('key_'+key,'Value',branch,'Condition'); return branch
    b.add('start','On Game Start'); end=action('start','storage','Open Save Storage',**{'Game ID':GAME})
    end=action(end,'hud','Create Widget'); end=action(end,'idle','Play Animation',Clip='Idle')
    end=action(end,'wait','Wait Until',Owner='player')
    b.add('started','Get Boolean Variable',Name='started'); b.connect('started','Value','wait','Condition')
    end=action(end,'status','Set Widget Text',Element='status',Text='Tour running: Delay inside a function')
    end=action(end,'tour','For Each Vector3',Array=POSITIONS)
    call=action(end,'destination','Delayed destination',port='Body'); b.connect('tour','Item',call,'Destination')
    end=action(call,'move','Set Position'); b.connect(call,'Point',end,'Value')
    end=action(end,'progress','Set Integer Variable',Name='progress')
    b.add('increment','Integer Add',B=1); b.connect('tour','Index','increment','A').connect('increment','Value',end,'Value')
    end=action(end,'show','Set Widget Text',Element='progress'); b.add('format','Format Integer')
    b.connect('increment','Value','format','Value').connect('format','Value',end,'Text')
    action('tour','done','Set Widget Text',port='Done',Element='status',Text='Tour complete')
    action(pressed('Space'),'begin','Set Boolean Variable',port='True',Name='started',Value=True)
    end=action(pressed('R'),'pending','Set Widget Text',port='True',Element='signal',Text='Pending (each R restarts the delay)')
    end=action(end,'debounce','Retriggerable Delay',Owner='player',Seconds=.5)
    action(end,'signal','Set Widget Text',Element='signal',Text='Settled')
    for key,label in [('S','Save Game'),('L','Load Game')]: action(pressed(key),'action_'+key,label,port='True',Slot=SLOT)
    for i,node in enumerate(b.graph['nodes']): node['position']=[i%6*280,i//6*280]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Latent flow robot tour',scene='scenes/main.json',graph='graphs/gameplay.json'))
    export(b.compile(scene),directory/'generated'); return directory


if __name__=='__main__': print(create())
