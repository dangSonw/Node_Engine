"""Create a Blockbench robot scene with typed broadcasts and subscription control."""
import argparse
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.events import new_event
from editor.core.functions import new_function
from editor.core.document import create_project, save_json
from editor.core.project_format import load_manifest
from editor.core.codegen import export
from editor.core.registry import ROOT


def create(destination):
    event=new_event('Turn',[{'name':'Angle','type':'float','default':15}]); event['id']=100001
    function=new_function('Turn Robot',[{'name':'Target','type':'entity'},{'name':'Angle','type':'float'},
        {'name':'Multiplier','type':'float','default':1}],[]); function['id']=1000001
    def add(b,nid,name,x,y,**values):
        b.add(nid,name,**values); b.graph['nodes'][-1]['position']=[x,y]
    b=GraphBuilder('Turn Robot',[function],function['id'],[event])
    for nid,name,x,y,values in [('entry','Function Input',0,0,{}),('multiply','Multiply',240,210,{}),
        ('degrees','Make Vector3',480,210,{}),('rotate','Rotate',700,0,{}),('return','Function Output',960,0,{})]:
        add(b,nid,name,x,y,**values)
    for edge in [('entry','Out','rotate','In'),('entry','Target','rotate','Entity'),('entry','Angle','multiply','A'),
        ('entry','Multiplier','multiply','B'),('multiply','Value','degrees','Y'),('degrees','Value','rotate','Degrees'),
        ('rotate','Out','return','In')]: b.connect(*edge)
    function['graph']=b.graph
    b=GraphBuilder('Typed event broadcasts',[function],event_definitions=[event])
    for nid,name,x,y,values in [
        ('start','On Game Start',0,0,{}),('pulse','Start Timer',210,0,{'Name':'pulse','Seconds':.25,'Repeat':True}),
        ('detach_timer','Start Timer',520,0,{'Name':'detach','Seconds':1}),
        ('subscribe','Subscribe Turn',840,0,{'Recipient':'partner'}),
        ('pulse_event','On Timer Finished',0,270,{'Filter':'pulse'}),('broadcast','Broadcast Turn',310,270,{'Angle':15}),
        ('detach_event','On Timer Finished',0,500,{'Filter':'detach'}),('detach','Unsubscribe Turn',310,500,{'Recipient':'partner'}),
        ('boost','Send Turn',630,500,{'Recipient':'player','Angle':60}),
        ('player_event','On Turn',0,750,{'Receiver':'player'}),('player_turn','Turn Robot',310,750,{}),
        ('partner_event','On Turn',630,750,{'Receiver':'partner','InitiallySubscribed':False}),
        ('partner_turn','Turn Robot',940,750,{'Multiplier':-1})]: add(b,nid,name,x,y,**values)
    for edge in [('start','Out','pulse','In'),('pulse','Out','detach_timer','In'),('detach_timer','Out','subscribe','In'),
        ('pulse_event','Out','broadcast','In'),('detach_event','Out','detach','In'),('detach','Out','boost','In'),
        ('player_event','Out','player_turn','In'),('player_event','Receiver','player_turn','Target'),('player_event','Angle','player_turn','Angle'),
        ('partner_event','Out','partner_turn','In'),('partner_event','Receiver','partner_turn','Target'),('partner_event','Angle','partner_turn','Angle')]: b.connect(*edge)
    scene={'version':1,'entities':[
        {'id':'player','name':'Always listening','position':[-1,0,0],'rotation':[0,0,0],'scale':[1,1,1],'mesh':'assets/robot.gltf'},
        {'id':'partner','name':'Unsubscribe after 1s','position':[1,0,0],'rotation':[0,0,0],'scale':[1,1,1],'mesh':'assets/robot.gltf'}],
        'variables':{}}
    ir=b.compile(scene)
    manifest=create_project(destination,'Typed Events Demo')
    save_json(manifest.parent/'graphs/gameplay.json',b.graph)
    save_json(manifest.parent/'scenes/main.json',scene)
    shutil.copy2(ROOT/'examples/blockbench_demo/assets/robot.gltf',manifest.parent/'assets/robot.gltf')
    project=load_manifest(manifest); project['assets']=['assets/robot.gltf']
    save_json(manifest,project)
    export(ir,manifest.parent/'generated')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'examples/events_demo')
    print(create(parser.parse_args().output))
