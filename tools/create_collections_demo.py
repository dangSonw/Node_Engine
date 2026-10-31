"""Create an editable, runnable typed-data example without replacing user files."""
from pathlib import Path
import argparse
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.data_types import declaration
from editor.core.document import create_project, save_json
from editor.core.project_format import load_manifest
from editor.core.codegen import export
from editor.core.registry import ROOT


def create(destination):
    manifest=create_project(destination,'Typed Collections Demo')
    b=GraphBuilder('Inventory totals and entity groups')
    nodes=[
        ('start','On Game Start',{},[0,0]),
        ('inventory','Get Integer Map Variable',{'Name':'inventory'},[0,160]),
        ('values','Integer Map Values',{},[240,160]),
        ('sumloop','For Each Integer',{},[480,0]),
        ('total','Get Integer Variable',{'Name':'total'},[480,200]),
        ('add','Integer Add',{},[720,160]),
        ('sum','Set Integer Variable',{'Name':'total'},[960,0]),
        ('format','Format Integer',{},[720,340]),
        ('message','Get String Variable',{'Name':'message'},[480,440]),
        ('concat','Concat Strings',{},[960,340]),
        ('log','Print Log',{},[1200,200]),
        ('ready','Set Boolean Variable',{'Name':'ready','Value':True},[1440,200]),
        ('update','On Update',{},[0,680]),
        ('isready','Get Boolean Variable',{'Name':'ready'},[0,840]),
        ('branch','Branch',{},[240,680]),
        ('targets','Get Entity Array Variable',{'Name':'targets'},[240,1000]),
        ('each','For Each Entity',{},[480,680]),
        ('axis','Get Vector3 Variable',{'Name':'axis'},[480,1100]),
        ('speed','Get Variable',{'Name':'speed'},[0,1200]),
        ('dt','Get Delta Time',{},[0,1050]),
        ('angle','Multiply',{},[240,1200]),
        ('degrees','Vector Scale',{},[720,1040]),
        ('rotate','Rotate',{},[960,680]),
    ]
    for nid,name,values,position in nodes:
        b.add(nid,name,**values)
        b.graph['nodes'][-1]['position']=position
    for edge in [
        ('start','Out','sumloop','In'),('inventory','Value','values','Map'),('values','Value','sumloop','Array'),
        ('sumloop','Body','sum','In'),('sumloop','Item','add','A'),('total','Value','add','B'),
        ('add','Value','sum','Value'),('sumloop','Done','log','In'),('total','Value','format','Value'),
        ('format','Value','concat','B'),('message','Value','concat','A'),('concat','Value','log','Message'),
        ('log','Out','ready','In'),('update','Out','branch','In'),('isready','Value','branch','Condition'),
        ('branch','True','each','In'),('targets','Value','each','Array'),('each','Body','rotate','In'),
        ('each','Item','rotate','Entity'),('axis','Value','degrees','Vector'),('speed','Value','angle','A'),
        ('dt','Value','angle','B'),('angle','Value','degrees','Scale'),('degrees','Value','rotate','Degrees')]:
        b.connect(*edge)
    scene={'version':1,'entities':[
        {'id':'player','name':'Robot trái','position':[-1,0,0],'rotation':[0,0,0],'scale':[1,1,1],'mesh':'assets/robot.gltf'},
        {'id':'partner','name':'Robot phải','position':[1,0,0],'rotation':[0,0,0],'scale':[1,1,1],'mesh':'assets/robot.gltf'}],
        'variables':{'inventory':declaration('map<int>',{'coin':10,'potion':2}),
                     'total':declaration('int',0),'message':declaration('string','Vật phẩm: '),
                     'ready':declaration('bool',False),'targets':declaration('array<entity>',['player','partner']),
                     'axis':declaration('vec3',[0,1,0]),'speed':45.0}}
    ir=b.compile(scene)
    save_json(manifest.parent/'graphs/gameplay.json',b.graph)
    save_json(manifest.parent/'scenes/main.json',scene)
    shutil.copy2(ROOT/'examples/blockbench_demo/assets/robot.gltf',manifest.parent/'assets/robot.gltf')
    project=load_manifest(manifest); project['assets']=['assets/robot.gltf']
    save_json(manifest,project)
    export(ir,manifest.parent/'generated')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'examples/collections_demo')
    print(create(parser.parse_args().output))
