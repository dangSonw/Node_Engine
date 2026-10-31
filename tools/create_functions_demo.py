"""Create a two-robot example driven by reusable pure/action function graphs."""
from pathlib import Path
import argparse
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.functions import new_function
from editor.core.data_types import declaration
from editor.core.document import create_project, save_json
from editor.core.project_format import load_manifest
from editor.core.codegen import export
from editor.core.registry import ROOT


def port(name,kind):
    return {'name':name,'type':kind}


def add(b,nid,name,position,**values):
    b.add(nid,name,**values)
    b.graph['nodes'][-1]['position']=position


def create(destination):
    pure=new_function('Rotation Delta', [port('Speed','float'),port('Seconds','float')], [port('Degrees','vec3')], True)
    pure['id']=1000001
    action=new_function('Spin Robot', [port('Target','entity'),port('Speed','float'),port('Seconds','float')],
                        [port('Rotation','vec3')])
    action['id']=1000002
    definitions=[pure,action]
    b=GraphBuilder(pure['name'],definitions,pure['id'])
    add(b,'entry','Function Input',[0,0])
    add(b,'multiply','Multiply',[280,40])
    add(b,'degrees','Make Vector3',[540,0])
    add(b,'return','Function Output',[800,0])
    for e in [('entry','Speed','multiply','A'),('entry','Seconds','multiply','B'),
              ('multiply','Value','degrees','Y'),('degrees','Value','return','Degrees')]:
        b.connect(*e)
    pure['graph']=b.graph
    b=GraphBuilder(action['name'],definitions,action['id'])
    add(b,'entry','Function Input',[0,0])
    add(b,'delta','Rotation Delta',[260,200])
    add(b,'rotate','Rotate',[520,0])
    add(b,'rotation','Get Rotation',[520,230])
    add(b,'return','Function Output',[800,0])
    for e in [('entry','Out','rotate','In'),('entry','Target','rotate','Entity'),('entry','Target','rotation','Entity'),
              ('entry','Speed','delta','Speed'),('entry','Seconds','delta','Seconds'),('delta','Degrees','rotate','Degrees'),
              ('rotate','Out','return','In'),('rotation','Value','return','Rotation')]:
        b.connect(*e)
    action['graph']=b.graph
    b=GraphBuilder('Reusable robot functions',definitions)
    add(b,'start','On Game Start',[0,-200])
    add(b,'log','Print Log',[300,-200],Message='Hai robot dùng chung function Spin Robot')
    add(b,'update','On Update',[0,40])
    add(b,'dt','Get Delta Time',[0,230])
    add(b,'left','Spin Robot',[300,0],Target='player',Speed=45)
    add(b,'right','Spin Robot',[610,0],Target='partner',Speed=-90)
    add(b,'save','Set Vector3 Variable',[920,0],Name='left_rotation')
    for e in [('start','Out','log','In'),('update','Out','left','In'),('left','Out','right','In'),
              ('right','Out','save','In'),('left','Rotation','save','Value'),
              ('dt','Value','left','Seconds'),('dt','Value','right','Seconds')]:
        b.connect(*e)
    scene={'version':1,'entities':[
        {'id':'player','name':'Robot trái','position':[-1,0,0],'rotation':[0,0,0],'scale':[1,1,1],'mesh':'assets/robot.gltf'},
        {'id':'partner','name':'Robot phải','position':[1,0,0],'rotation':[0,0,0],'scale':[1,1,1],'mesh':'assets/robot.gltf'}],
        'variables':{'left_rotation':declaration('vec3',[0,0,0])}}
    ir=b.compile(scene)
    manifest=create_project(destination,'Reusable Functions Demo')
    save_json(manifest.parent/'graphs/gameplay.json',b.graph)
    save_json(manifest.parent/'scenes/main.json',scene)
    shutil.copy2(ROOT/'examples/blockbench_demo/assets/robot.gltf',manifest.parent/'assets/robot.gltf')
    project=load_manifest(manifest); project['assets']=['assets/robot.gltf']
    save_json(manifest,project)
    export(ir,manifest.parent/'generated')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'examples/functions_demo')
    print(create(parser.parse_args().output))
