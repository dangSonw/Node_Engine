"""Create two robots driven by independent named timers and Flecs observers."""
import argparse
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.document import create_project, save_json
from editor.core.codegen import export
from editor.core.registry import ROOT


def create(destination):
    b=GraphBuilder('Robot timers')
    def add(nid,name,x,y,**values):
        b.add(nid,name,**values)
        b.graph['nodes'][-1]['position']=[x,y]
    add('start','On Game Start',0,0)
    add('left_timer','Start Timer',250,0,Name='turn',Seconds=.25,Repeat=True,Owner='player')
    add('right_timer','Start Timer',600,0,Name='turn',Seconds=.5,Repeat=True,Owner='partner')
    add('left_event','On Timer Finished',0,300,Filter='turn',Receiver='player')
    add('left_turn','Rotate',350,300,Degrees=[0,15,0])
    add('right_event','On Timer Finished',0,520,Filter='turn',Receiver='partner')
    add('right_turn','Rotate',350,520,Degrees=[0,-30,0])
    for e in [('start','Out','left_timer','In'),('left_timer','Out','right_timer','In'),
              ('left_event','Out','left_turn','In'),('left_event','Owner','left_turn','Entity'),
              ('right_event','Out','right_turn','In'),('right_event','Owner','right_turn','Entity')]: b.connect(*e)
    scene={'version':1,'entities':[
        {'id':'player','name':'Robot 0.25s','position':[-1,0,0],'rotation':[0,0,0],'scale':[1,1,1],'mesh':'assets/robot.gltf'},
        {'id':'partner','name':'Robot 0.5s','position':[1,0,0],'rotation':[0,0,0],'scale':[1,1,1],'mesh':'assets/robot.gltf'}],
        'variables':{}}
    ir=b.compile(scene)
    manifest=create_project(destination,'Timers Demo')
    save_json(manifest.parent/'graphs/gameplay.json',b.graph)
    save_json(manifest.parent/'scenes/main.json',scene)
    shutil.copy2(ROOT/'examples/blockbench_demo/assets/robot.gltf',manifest.parent/'assets/robot.gltf')
    save_json(manifest,{'version':1,'name':'Timers Demo','graph':'graphs/gameplay.json',
                        'scene':'scenes/main.json','assets':['assets/robot.gltf']})
    export(ir,manifest.parent/'generated')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'examples/timers_demo')
    print(create(parser.parse_args().output))
