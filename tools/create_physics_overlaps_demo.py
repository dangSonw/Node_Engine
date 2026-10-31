"""Two graph-defined detection volumes around the playable Blockbench robot."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.document import save_json
from editor.core.registry import ROOT
from tools.create_physics_authoring_demo import create as create_base

GAME='node-engine-physics-overlaps-demo'


def create(directory=ROOT/'examples/physics_overlaps_demo'):
    directory=create_base(directory)
    scene=json.loads((directory/'scenes/main.json').read_text('utf-8'))
    hud=scene['ui_assets'][0]
    hud['rml']=hud['rml'].replace('Scene colliders / robot prefab','Overlap regions / Blockbench robot').replace(
        '</div>', '<br/>Box: x +/-1m, includes center trigger<br/>Capsule: horizontal, x +/-3m<br/>'
        '<span id="box_overlap">Box overlap: waiting</span><br/>'
        '<span id="capsule_overlap">Capsule overlap: waiting</span></div>')
    b=GraphBuilder(); b.graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    b.graph['name']='Overlap regions and physics robot'
    for node in b.graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']=GAME
    for key,label,values in [('box','Physics Overlap Box',{'Half Extents':[1,3,1],'Sensors':True}),
                             ('capsule','Physics Overlap Capsule',{'Radius':1,'Half Height':2,'Rotation':[0,0,90]})]:
        b.add(key+'_update','On Update')
        b.add(key+'_query',label,Center=[0,1,0],Exclude='floor',**values)
        b.add(key+'_store','Set Entity Array Variable',Name=key+'_overlaps')
        b.connect(key+'_update','Out',key+'_store','In').connect(key+'_query','Value',key+'_store','Value')
        b.add(key+'_read','Get Entity Array Variable',Name=key+'_overlaps')
        b.add(key+'_length','Entity Array Length'); b.connect(key+'_read','Value',key+'_length','Array')
        b.add(key+'_format','Format Integer'); b.connect(key+'_length','Value',key+'_format','Value')
        b.add(key+'_label','Concat Strings',A=key.title()+' overlap: ')
        b.connect(key+'_format','Value',key+'_label','B')
        b.add(key+'_units','Concat Strings',B=' bodies'); b.connect(key+'_label','Value',key+'_units','A')
        b.add(key+'_hud','Set Widget Text',Element=key+'_overlap')
        b.connect(key+'_store','Out',key+'_hud','In').connect(key+'_units','Value',key+'_hud','Text')
    for i,node in enumerate(b.graph['nodes']): node['position']=[(i%8)*285,(i//8)*220]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    project=json.loads((directory/'project.json').read_text('utf-8')); project['name']='Overlap regions and Blockbench robot'
    save_json(directory/'project.json',project); export(b.compile(scene),directory/'generated')
    return directory


if __name__=='__main__': print(create())
