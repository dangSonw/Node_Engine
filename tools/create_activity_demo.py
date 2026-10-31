"""A scene timer toggles a robot group while an independent beacon keeps running."""
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
    project=ROOT/'examples/activity_demo'
    (project/'assets').mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'examples/components_demo/assets/robot.gltf',project/'assets/robot.gltf')
    scene=default_scene()
    template=dict(scene['entities'][0],mesh='assets/robot.gltf',layer=3)
    scene['entities']=[
        dict(scene['entities'][0],id='group',name='Robot group'),
        dict(template,id='player',name='Timed robot',parent='group',position=[-2.2,0,0]),
        dict(template,id='child',name='Group companion',parent='group',position=[0,0,0]),
        dict(template,id='beacon',name='Always active beacon',layer=7,position=[2.2,0,0]),
    ]
    b=GraphBuilder('Activity and layers')
    nodes=[
        ('start','On Game Start',{}),
        ('toggle_timer','Start Timer',{'Name':'toggle','Seconds':.5,'Repeat':True}),
        ('worker_timer','Start Timer',{'Name':'work','Seconds':.25,'Repeat':True,'Owner':'player'}),
        ('initial_query','Find Entities By Layer',{'Layer':3}),
        ('initial_save','Set Entity Array Variable',{'Name':'active_actors'}),
        ('toggle','On Timer Finished',{'Filter':'toggle'}),
        ('active','Is Entity Active',{'Entity':'group'}),('invert','NOT',{}),
        ('set_active','Set Entity Active',{'Entity':'group'}),
        ('query','Find Entities By Layer',{'Layer':3}),
        ('save_query','Set Entity Array Variable',{'Name':'active_actors'}),
        ('worker','On Timer Finished',{'Receiver':'player','Filter':'work'}),
        ('rotate_worker','Rotate',{'Degrees':[0,15,0]}),
        ('update','On Update',{}),('rotate_beacon','Rotate',{'Entity':'beacon','Degrees':[0,1,0]}),
    ]
    for i,(nid,name,values) in enumerate(nodes):
        b.add(nid,name,**values); b.graph['nodes'][-1]['position']=[(i%5)*270,(i//5)*240]
    for edge in [
        ('start','Out','toggle_timer','In'),('toggle_timer','Out','worker_timer','In'),
        ('worker_timer','Out','initial_save','In'),('initial_query','Value','initial_save','Value'),
        ('toggle','Out','set_active','In'),('active','Value','invert','Value'),('invert','Value','set_active','Active'),
        ('set_active','Out','save_query','In'),('query','Value','save_query','Value'),
        ('worker','Out','rotate_worker','In'),('update','Out','rotate_beacon','In'),
    ]: b.connect(*edge)
    save_json(project/'scenes/main.json',scene); save_json(project/'graphs/gameplay.json',b.graph)
    save_json(project/'project.json',{'version':1,'name':'Activity and layers',
        'graph':'graphs/gameplay.json','scene':'scenes/main.json','assets':['assets/robot.gltf']})
    export(compile_graph(b.graph,scene),project/'generated')
    return project


if __name__=='__main__': print(create())
