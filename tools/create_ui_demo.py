"""Blockbench robot plus a reusable HUD driven by ordinary game nodes."""
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.registry import ROOT
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene,save_json
from editor.core.codegen import export
from editor.core.ui import new_asset


def create(directory=ROOT/'examples/ui_demo'):
    directory=Path(directory); (directory/'assets').mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'examples/blockbench_demo/assets/robot.gltf',directory/'assets/robot.gltf')
    scene=default_scene(); scene['entities'][0].update(name='Blockbench robot',mesh='assets/robot.gltf')
    scene['ui_assets']=[dict(new_asset(),id='hud')]
    scene['variables']={'score':0.,'horizontal':0.,'clicks_outside':0.,'volume':.5,
                        'player_name':{'type':'string','value':'Player'}}
    scene['input']=dict(version=1,actions={'world_click':['MouseLeft']},
        axes={'horizontal':{'negative':['A'],'positive':['D']}})
    b=GraphBuilder('HUD: Add point rotates robot; A/D move; Enter submits name')
    nodes=[('start','On Game Start',{}),('create','Create Widget',{'Template':'hud','Widget':'hud'}),
        ('click','On Button Click',{'Widget Filter':'hud','Element Filter':'add'}),
        ('score','Get Variable',{'Name':'score'}),('increment','Add',{'B':1.}),
        ('store','Set Variable',{'Name':'score'}),('text','Set Widget Text',{'Text':'Point added!'}),
        ('score_string','Format Float',{}),('score_label','Concat Strings',{'A':'Score: '}),
        ('portion','Divide',{'B':10.}),('clamp','Clamp',{'Min':0.,'Max':1.}),
        ('progress','Set Widget Value',{'Element':'progress'}),('turn','Rotate',{'Degrees':[0,30,0]}),
        ('submitted','On UI Text Submitted',{'Widget Filter':'hud','Element Filter':'name'}),
        ('save_name','Set String Variable',{'Name':'player_name'}),('welcome','Concat Strings',{'A':'Welcome, '}),
        ('status','Set Widget Text',{'Element':'status'}),
        ('changed','On UI Value Changed',{'Widget Filter':'hud','Element Filter':'enabled'}),
        ('enable','Set Widget Enabled',{'Element':'add'}),
        ('slider','On UI Value Changed',{'Widget Filter':'hud','Element Filter':'volume'}),
        ('volume','Get Widget Value',{'Element':'volume'}),('save_volume','Set Variable',{'Name':'volume'}),
        ('update','On Update',{}),('axis','Get Input Axis',{'Axis':'horizontal'}),
        ('save_axis','Set Variable',{'Name':'horizontal'}),('dt','Get Delta Time',{}),
        ('distance','Multiply',{}),('direction','Make Vector3',{}),('move','Translate',{}),
        ('world_update','On Update',{}),('world_pressed','Is Action Pressed',{'Action':'world_click'}),
        ('world_branch','Branch',{}),('world_count','Get Variable',{'Name':'clicks_outside'}),
        ('world_add','Add',{'B':1.}),('world_save','Set Variable',{'Name':'clicks_outside'})]
    for i,(nid,name,values) in enumerate(nodes):
        b.add(nid,name,**values); b.graph['nodes'][-1]['position']=[(i%6)*260,(i//6)*220]
    for edge in [('start','Out','create','In'),('click','Out','store','In'),('score','Value','increment','A'),
        ('increment','Value','store','Value'),('store','Out','text','In'),('text','Out','progress','In'),
        ('score','Value','score_string','Value'),('score_string','Value','score_label','B'),('score_label','Value','text','Text'),
        ('score','Value','portion','A'),('portion','Value','clamp','Value'),('clamp','Value','progress','Value'),
        ('progress','Out','turn','In'),('submitted','Out','save_name','In'),('submitted','Value','save_name','Value'),
        ('submitted','Value','welcome','B'),('save_name','Out','status','In'),('welcome','Value','status','Text'),
        ('changed','Out','enable','In'),('changed','Checked','enable','Enabled'),
        ('slider','Out','save_volume','In'),('volume','Value','save_volume','Value'),
        ('update','Out','save_axis','In'),('axis','Value','save_axis','Value'),('save_axis','Out','move','In'),
        ('axis','Value','distance','A'),('dt','Value','distance','B'),('distance','Value','direction','X'),
        ('direction','Value','move','Delta'),('world_update','Out','world_branch','In'),
        ('world_pressed','Value','world_branch','Condition'),('world_branch','True','world_save','In'),
        ('world_count','Value','world_add','A'),('world_add','Value','world_save','Value')]: b.connect(*edge)
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Robot HUD playground',graph='graphs/gameplay.json',
        scene='scenes/main.json',assets=['assets/robot.gltf']))
    export(b.compile(scene),directory/'generated')
    return directory


if __name__=='__main__': print(create())
