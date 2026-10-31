"""Two runtime-created robots orbit a parent; a timer destroys one at one second."""
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.registry import ROOT
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene, save_json
from editor.core.compiler import compile_graph
from editor.core.codegen import export

def create():
    project=ROOT/'examples/entities_demo'
    (project/'assets').mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'examples/events_demo/assets/robot.gltf',project/'assets/robot.gltf')
    scene=default_scene()
    scene['entities'][0].update(name='Robot template',mesh='assets/robot.gltf',visible=False,tags=['template'])
    b=GraphBuilder('Entity lifecycle and hierarchy')
    nodes=[
        ('start','On Game Start',{}),('pivot','Spawn Entity',{'Name':'Orbit pivot'}),
        ('savepivot','Set Entity Variable',{'Name':'pivot'}),
        ('clone','Clone Entity',{'Name':'Orbit robot'}),('move','Set Position',{'Value':[2,0,0]}),
        ('parentclone','Set Parent',{}),('show','Set Entity Visibility',{'Visible':True}),
        ('spawn','Spawn Entity',{'Name':'Temporary robot','Mesh':'assets/robot.gltf','Position':[-2,0,0]}),
        ('parentspawn','Set Parent',{}),('savetemporary','Set Entity Variable',{'Name':'temporary'}),
        ('timer','Start Timer',{'Name':'cleanup','Seconds':1}),
        ('update','On Update',{}),('readpivot','Get Entity Variable',{'Name':'pivot'}),
        ('rotate','Rotate',{'Degrees':[0,1,0]}),
        ('expire','On Timer Finished',{'Filter':'cleanup'}),('readtemporary','Get Entity Variable',{'Name':'temporary'}),
        ('destroy','Destroy Entity',{}),('log','Print Log',{'Message':'Temporary robot destroyed; orbit robot remains.'}),
    ]
    for i,(nid,name,values) in enumerate(nodes):
        b.add(nid,name,**values)
        b.graph['nodes'][-1]['position']=[(i%5)*260,(i//5)*220]
    chain=['start','pivot','savepivot','clone','move','parentclone','show','spawn','parentspawn','savetemporary','timer']
    for a,c in zip(chain,chain[1:]): b.connect(a,'Out',c,'In')
    for edge in [
        ('pivot','Entity','savepivot','Value'),('clone','Entity','move','Entity'),
        ('clone','Entity','parentclone','Child'),('pivot','Entity','parentclone','Parent'),
        ('clone','Entity','show','Entity'),('spawn','Entity','parentspawn','Child'),
        ('pivot','Entity','parentspawn','Parent'),('spawn','Entity','savetemporary','Value'),
        ('update','Out','rotate','In'),('readpivot','Value','rotate','Entity'),
        ('expire','Out','destroy','In'),('readtemporary','Value','destroy','Entity'),('destroy','Out','log','In'),
    ]: b.connect(*edge)
    save_json(project/'scenes/main.json',scene)
    save_json(project/'graphs/gameplay.json',b.graph)
    save_json(project/'project.json',{'version':1,'name':'Entity lifecycle and hierarchy',
        'graph':'graphs/gameplay.json','scene':'scenes/main.json','assets':['assets/robot.gltf']})
    export(compile_graph(b.graph,scene),project/'generated')
    return project

if __name__=='__main__': print(create())
