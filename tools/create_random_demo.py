"""Reproducible random loot and robot placement authored through public nodes."""
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

GAME='node-engine-random-demo'
SLOT='random'
ITEMS=['Potion','Shield','Sword']
WEIGHTS=[6.,3.,1.]
DECK=['Ace','King','Queen','Jack']

def create(directory=ROOT/'examples/random_demo'):
    directory=Path(directory); assets=directory/'assets'; assets.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'examples/blockbench_demo/assets/robot.gltf',assets/'robot.gltf')
    scene=default_scene(); scene['variables']={'roll':{'type':'int','value':0}}
    scene['entities'][0].update(mesh='assets/robot.gltf',name='Random position robot')
    scene['entities'].append(dict(id='bonus',name='Bonus robot',mesh='assets/robot.gltf',position=[2.4,0,0],
        rotation=[0,0,0],scale=[.55,.55,.55],visible=False))
    scene['entities'].append(dict(id='direction',name='Random direction marker',mesh='assets/robot.gltf',position=[0,0,0],
        rotation=[0,0,0],scale=[.24,.24,.24],visible=False))
    scene['entities'].append(dict(id='camera',name='Camera',position=[0,1,7],rotation=[0,0,0],scale=[1,1,1],camera=default_camera()))
    scene['active_camera']='camera'
    markup='''<rml><head><style>body {width:100%;height:100%;font-family:node-ui;font-size:14px;color:#ffffff;pointer-events:none;}
    #help {position:absolute;left:8px;top:8px;padding:8px;width:92%;max-width:440px;box-sizing:border-box;background-color:#171e32dd;}</style></head>
    <body><div id="help">Seeded random playground (seed 42)<br/>
    Space: new position, dice roll, 25% bonus robot<br/>
    R: reset seed / S: save / L: load<br/>Dice: <span id="roll">0</span><br/>
    Random item: <span id="item">-</span><br/>
    Weighted loot (6:3:1): <span id="loot">-</span><br/>
    Shuffled deck: <span id="deck">-</span><br/>
    Small robot: random unit direction x 1.8</div></body></rml>'''
    scene['ui_assets']=[dict(new_asset(rml=markup),id='hud')]
    b=GraphBuilder('Seeded random playground')
    def action(source,nid,name,port='Out',**values):
        b.add(nid,name,**values); b.connect(source,port,nid,'In'); return nid
    b.add('start','On Game Start')
    end=action('start','seed','Set Random Seed',Seed=42)
    end=action(end,'storage','Open Save Storage',**{'Game ID':GAME})
    action(end,'hud','Create Widget')
    for key in ('Space','R','S','L'):
        b.add('update_'+key,'On Update'); b.add('key_'+key,'Is Key Pressed',Key=key)
        action('update_'+key,'if_'+key,'Branch'); b.connect('key_'+key,'Value','if_'+key,'Condition')
    for key,label,values in [('R','Set Random Seed',{'Seed':42}),('S','Save Game',{'Slot':SLOT}),('L','Load Game',{'Slot':SLOT})]:
        action('if_'+key,'action_'+key,label,port='True',**values)
    end=action('if_Space','position','Random Vector',port='True',Minimum=[-2,0,-1],Maximum=[1.4,0,1])
    end=action(end,'dice','Random Integer',Minimum=1,Maximum=6)
    end=action(end,'bonus','Random Boolean',Probability=.25)
    end=action(end,'move','Set Position'); b.connect('position','Value',end,'Value')
    end=action(end,'visible','Set Entity Visibility',Entity='bonus'); b.connect('bonus','Value',end,'Visible')
    end=action(end,'store','Set Integer Variable',Name='roll'); b.connect('dice','Value',end,'Value')
    b.add('format','Format Integer'); b.connect('dice','Value','format','Value')
    end=action(end,'show','Set Widget Text',Element='roll'); b.connect('format','Value',end,'Text')
    for nid,label,values in [('item','Random String Item',{'Array':ITEMS}),
        ('loot','Random Weighted String Item',{'Array':ITEMS,'Weights':WEIGHTS}),
        ('deck','Shuffle String Array',{'Array':DECK})]:
        end=action(end,nid,label,**values)
        end=action(end,nid+'_store','Set String Array Variable' if nid=='deck' else 'Set String Variable',Name=nid)
        b.connect(nid,'Value',end,'Value')
        if nid!='deck':
            end=action(end,nid+'_index','Set Integer Variable',Name=nid+'_index'); b.connect(nid,'Index',end,'Value')
        text_node=nid
        if nid=='deck':
            b.add('deck_join','String Join',Separator=' / '); b.connect(nid,'Value','deck_join','Items'); text_node='deck_join'
        end=action(end,nid+'_show','Set Widget Text',Element=nid); b.connect(text_node,'Value',end,'Text')
    end=action(end,'direction','Random Direction')
    end=action(end,'direction_store','Set Vector3 Variable',Name='direction'); b.connect('direction','Value',end,'Value')
    b.add('direction_offset','Vector Scale',Scale=1.8); b.connect('direction','Value','direction_offset','Vector')
    b.add('direction_origin','Vector Add',B=[0,.8,0]); b.connect('position','Value','direction_origin','A')
    b.add('marker_position','Vector Add'); b.connect('direction_offset','Value','marker_position','A'); b.connect('direction_origin','Value','marker_position','B')
    end=action(end,'marker_move','Set Position',Entity='direction'); b.connect('marker_position','Value',end,'Value')
    action(end,'marker_visible','Set Entity Visibility',Entity='direction',Visible=True)
    for i,node in enumerate(b.graph['nodes']): node['position']=[i%7*270,i//7*220]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Seeded random playground',scene='scenes/main.json',graph='graphs/gameplay.json'))
    export(b.compile(scene),directory/'generated')
    return directory

if __name__=='__main__': print(create())
